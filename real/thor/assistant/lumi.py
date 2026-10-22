"""Lumi voice assistant: greets every visitor, talks with them and obeys voice commands.

    python assistant/lumi.py                 # full: camera, greetings, conversation, commands
    python assistant/lumi.py --no-camera     # no camera: press Enter to start a conversation (desk testing)
    python assistant/lumi.py --no-arm --no-drive     # no waving, no base driving
    python assistant/lumi.py --patrol a,b    # walk between markers in a loop; stop for people in the way, talk, go on
    python assistant/lumi.py --patrol p1,p2,final,p10,home --once --pause 0.5   # drive the route once, end at the dock

Behaviour
- Every person the camera sees gets a track (an ID followed from frame to frame).
- A new person who stays in the greeting zone is greeted once: Lumi turns its head to them and says hello
  (a greeting never moves the arm). A second person who arrives is greeted the same way, then the talk goes on.
- While a greeted person stays but says nothing, after PROMPT_S of silence it asks "How can I help you?" (at most MAX_PROMPTS times).
- When the person disappears from the camera (LOST_S), listening and speaking stop at once.
  Someone who comes back later is a new visit and is greeted again.
- Voice commands (English / Korean): go to <marker>, go home, look left/right/up/down/center, wave, stop. The arm
  waves only when asked, with an empty hand, from `look`, along a checked route (manipulation/wave.py).
- Patrol (--patrol): drive marker to marker in a loop. Only a person in the robot's path (PATH_HALF_WIDTH to
  each side) closer than PATROL_NEAR_MAX makes Lumi stop and greet; people sitting beside the path are ignored.
  If the person says nothing for PATROL_WAIT_S, or the talk is over, or the person left, the patrol goes on
  (the base drives around a person who still stands in the way).
  Below LOW_BATTERY % Lumi drives home to charge and continues at RESUME_BATTERY %.
- Wake word: "Hi Lumi" / "Hey Lumi" / "루미야" from anywhere, also from far away or from behind. Lumi finds the
  direction of the voice (doa.py), turns its head (or the whole base if the voice is behind) to that person,
  answers "Hi, I'm Lumi..." and listens. Words after the wake word ("Hi Lumi, come here") are obeyed at once.
- Several people: each utterance's direction picks the visible person who spoke; the head turns to them.
- "Come here" / "come to me" / "이리 와": Lumi computes where that person stands on the map and drives to a
  free spot STOP_DIST in front of them that it can reach (nav.py), stopping early when it is COME_STOP away.
- The person Lumi talks to is drawn red in the dashboard (person.focus_angle).
- Cameras: standing, the head camera watches people (it turns with the head toward them); driving, the torso
  camera watches the path (it always looks forward). A camera that gives no detections is replaced by the other
  one until it is back. While the arm waves, people too close are watched in both cameras. --camera pins one.
- Sound direction calibrates itself: while Lumi talks with the only person in view, their camera angle is the
  truth for each utterance (doa.add_sample); after enough samples doa_calib.json is written.
- Replies are streamed: Lumi starts speaking after the LLM's first sentence.

Modes (switched live from the dashboard through /dev/shm/lumi_modes.json, see api/server.py /assistant/modes):
- greeter: while standing, greet people who come close, talk, listen for "Hi Lumi".
- patrol:  while driving anywhere (a marker picked on the dashboard, "go to p2", a --patrol route), stop for a
           person in the path, greet and talk, then drive on to the same destination. Patrol also allows the
           base and the waist by voice: with it off (Greeter only) Lumi does what it can standing in place (talk,
           head, lift, arm and gripper within reach, wave) and refuses a drive, a base turn or a waist turn
           (base_off says BASE_OFF_SAY; a task runs with fetch.stay_put). The dashboard's own buttons and "stop"
           work either way.
- wave / drive: wave when asked; allow "come here" and voice "go to".
The dashboard's Go / Cancel are sent to this program (/dev/shm/lumi_cmd.json) while it runs, so it can stop
for people on the way. A calibration session for the sound direction can also be started from there.
"""
import argparse
import collections
import json
import io
import traceback
import itertools
import math
import os
import subprocess
import sys
import threading
import time

# Started with the system python (no cv2 there)? Restart with the project's venv.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))      # the project folder
VENV = os.path.join(ROOT, ".venv")
VENV_PY = os.path.join(VENV, "bin", "python")
if os.path.exists(VENV_PY) and os.path.realpath(sys.prefix) != os.path.realpath(VENV):
    os.execv(VENV_PY, [VENV_PY, os.path.abspath(__file__)] + sys.argv[1:])

import random
import re

from robot import agv
from robot import arm
from assistant import brain as brain_mod
from assistant import driving
from assistant import abilities
from assistant import voice_words
from vision import camview
from vision import reid
from audio import doa
from robot import gripper
from audio import ears
from robot import head
from audio import mic
from robot import motion
from audio import mouth
from audio import sing
from robot import nav
from manipulation import arm_route
from manipulation import skills
from manipulation import wave as wave_mod
from assistant import web
from assistant import fetch_dialog
from assistant import seeing
from assistant.brain import Brain

NEAR_MIN, NEAR_MAX = 0.5, 1.2      # m, greeting zone
PATROL_NEAR_MAX = 1.0              # m, on patrol: only people this close stop the robot
STAY_MAX = 2.5                     # m, a greeted person farther than this counts as gone
HOLD_S = 0.7                       # s in the zone before a greeting
FACE_FRAMES = 3                    # faces seen on a track before Lumi decides who it is (the first ones are poor: in
                                   # a track's first second median cosine 0.20 to the same person, the next 0.59)
FACE_WAIT_S = 1.0                  # s after HOLD_S Lumi waits for those faces at most; then the clothes decide.
                                   # 2026-10-21: 6 of 8 returns had 3 good faces within 1.7 s, the other two after 5 s
LOST_S = 2.0                       # s not seen -> the person is gone (detections can miss a few frames)
PROMPT_S = 12.0                    # s of silence before "How can I help you?"
MAX_PROMPTS = 2
TOO_CLOSE = 0.45                   # m, a running wave is stopped
MATCH_DEG = 12.0                   # a detection belongs to the track with the closest angle within this
OCCLUSION_DROP = 0.3               # m; while the arm moves, a sudden drop in distance is the arm in front of
                                   # the person, not the person moving: ignore it
CLOSE_BOX = 0.85                   # a person is really closer than TOO_CLOSE only if the box is this tall (frame part)
HEAD_SIGN = 1.0                    # +image angle -> +head yaw (checked: + = robot's left)
LOOK = {"left": (40, None), "right": (-40, None), "center": (0, 0), "up": (None, 20), "down": (None, -5)}
# ^ yaw/pitch in degrees for "look" commands: +yaw = left, +pitch = up (checked on the dashboard 2026-10-12)
WAKE = re.compile(r"\b(hi|hey|hello|okay|ok|hai|high)?[\s,.!]*(lumi|lumia|loomi|lumie|lumy|lummy|looney|lu-mi|rumi|roomie)\b"
                  r"|루미|누미", re.I)
WAKE_REPLY = {"en": "Yes? How can I help?", "ko": "네? 무엇을 도와드릴까요?"}
NAME_ONLY = re.compile(r"^\s*(hi |hey |hello )?(lumi|loomi|rumi|루미)[\s,.!?]*$", re.I)
FETCH_STOP = re.compile(r"\b(stop|halt|freeze|don'?t move)\b|멈춰|그만|정지|스톱|거기 ?서(?=[\s!.~,]*$)|움직이지 ?마", re.I)   # not "거기서 기다려"
FETCH_GIVE = re.compile(r"\bgive (it|that|this|the \w+)( to me)?\b|\bhand (it )?(over|to me)\b|줘|주세요|건네", re.I)
FETCH_PLACE = re.compile(r"\b(put|place|set) (it|that|this|the \w+) (down|on the table)\b|테이블에 ?(놔|놓|둬)|내려 ?(놔|놓)", re.I)
FETCH_BRING_IT = re.compile(r"\bbring (it|that|this)\b|가져와|가져다 ?줘|갖다 ?줘", re.I)   # no object named
# ---- someone talks to Lumi while it is on a mission (docs/17 §6) ----
TALK_WORDS = re.compile(r"\b(wait|excuse me|hold on|hey|hi|hello|sorry|stop|robot)\b|잠깐|잠시만|저기요|안녕|멈춰|스톱|로봇", re.I)
SAFETY = re.compile(r"\b(watch out|look out|danger(ous)?|emergency|be careful|my (hand|foot|leg|arm))\b|\bstop\s*!|"
                    r"\bstop[\s,!.]+stop\b|위험|조심해|비상|멈춰\s*!|아파|다쳐|스톱 ?스톱|멈춰 ?멈춰|끼었|끼여", re.I)
GO_ON = re.compile(r"\b(go on|carry on|continue|keep going|you can go|go ahead|off you go|on your way|you may go)\b|"
                   r"계속 ?(가|해)|가도 ?(돼|됩니다)|가 ?봐|그냥 ?가|다녀오세요|가던 ?길|^\s*(응|네|그래) ?가\b|\byes,? go\b", re.I)
CANCEL_TASK = re.compile(r"\b(cancel|abort|forget)\b.*\b(task|it|mission|delivery|that)\b|\bcancel\b|"
                         r"\b(don'?t|do not|no longer) need\b|필요 ?없|취소", re.I)
I_AM = re.compile(r"\b(?:i am|i'm|im|my name is|this is|it's|it is)\s+(?:the\s+)?([a-z][a-z'-]{1,20})\b(?!'s)|\b([a-z][a-z'-]{1,20}) here\b|"
                  r"(?:제가|저는|나는|내가|저|나)\s+([가-힣a-z]{1,10}?)(?:씨|님)?\s*(?:예요|이에요|입니다|이야|야|인데요?|이고)(?![가-힣])|"
                  r"(?:^|[\s,.]|루미야\s*)([가-힣]{2,5}?)(?:예요|이에요|입니다|인데요?|이야|야)(?=[\s,.!?]|$)", re.I)
NOT_NAMES = {"here", "sorry", "hungry", "important", "urgent", "me", "you", "him", "her", "nothing", "all", "ok", "루미",
             "루미야", "그게", "그거", "이거", "저거", "괜찮", "아니", "다", "뭐", "어디", "누구", "로봇", "제임스한테", "not", "busy", "fine", "okay", "ok", "lumi", "not", "just", "the", "a", "so", "very", "looking",
             "going", "back", "ready", "done", "good", "new", "from", "with", "at", "in", "on", "it", "who", "one"}
REQUEST = re.compile(r"\b(take me|bring me|come with|follow me|lead me|show me the way|go with me|come here|come to me|"
                     r"go to|drive to|help me carry|carry this|pick (this|that|it)? ?up|give me|turn around|go back|"
                     r"instead|put (it|that|this) down|i'?ll take it to|let me take it|hand it to me)\b|데려|안내해|따라와|"
                     r"이리 ?와|가져다 ?줘|(으로|로) ?가|같이 ?가|내려놔|돌아서|집어 ?줘|나 ?줘|전해 ?줄게|제가 ?전해", re.I)    # asks Lumi to go somewhere or do a job: refused while on a mission
CHANGE_WORDS = re.compile(r"\b(put|bring|take|go|place|instead|desk|table|chair|p\d+)\b|놔|갖다|가져|으로|로 ", re.I)
ELSEWHERE = re.compile(r"(으로|로)\s*(가져|갖다)|\b(to the|instead|over there)\b", re.I)   # bring it somewhere else
GIVE_ME = re.compile(r"\b(give|hand|mine|for me|to me|i'?ll take it|i will take it|i can take it)\b|주세요|줘|내 거|"
                     r"제 거|제가 받을게|받을게", re.I)
MOVING_ACTIONS = {"go_to", "come", "come_back", "follow", "move", "turn", "arm", "pick", "put", "move_object", "fetch", "give", "place", "wave",
                  "lift"}
BASE_ACTIONS = {"go_to", "come", "come_back", "follow", "move", "turn"}   # need the base: Patrol on
DRIVE_STEPS = {"go", "move", "turn"}                                     # mission steps that drive
FIX_SAY = (("Okay.", "네."),                                        # a command taken back in the same sentence
           ("Sorry, which one did you mean? Please say it again.", "죄송해요, 어느 쪽 말씀이세요? 다시 한 번 말씀해 주세요."))
BASE_OFF_SAY = ("I can't drive or turn my waist right now. Switch on Patrol for that.",   # Greeter only: a base /
                "지금은 이동하거나 허리를 돌릴 수 없어요. 패트롤을 켜 주세요.")             # waist motion asked for
ARM_OFF_SAY = ("Please enable my arm first.", "먼저 제 팔을 켜 주세요.")   # an arm action with the arm switched off
ARM_TASKS = {"pick", "put", "move_object", "fetch", "give", "place", "receive", "wave"}   # + arm reach / fold


def needs_arm(action, target=""):
    """The action moves the arm (the gripper alone, open / close, does not ask for it)."""
    return action in ARM_TASKS or action == "arm" and target not in ("open", "close")
LIFT_VEL = 20                       # speed ratio % for a lift move asked by voice (head.VEL is 40)
LIMIT_SAY = {"yaw": (f"I can turn my head up to {head.AXIS_LIMITS[2][1]:g} degrees each way.",
                     f"고개는 좌우로 {head.AXIS_LIMITS[2][1]:g}도까지 돌릴 수 있어요."),
             "pitch": (f"I can tilt my head from {-head.PITCH_RANGE[0]:g} degrees down to {head.PITCH_RANGE[1]:g} degrees up.",
                       f"고개는 아래로 {-head.PITCH_RANGE[0]:g}도, 위로 {head.PITCH_RANGE[1]:g}도까지 움직여요."),
             "lift": (f"For now I can raise my body only up to {head.LIFT_MAX_MM:g} millimetres.",
                      f"지금은 몸을 {head.LIFT_MAX_MM:g}밀리미터까지만 올릴 수 있어요.")}   # a number asked for was past the range
DONE_TALK = re.compile(r"\b(bye+|goodbye|see you|never ?mind|nothing|that'?s (all|it)|no thanks|thanks|thank you|"
                       r"okay|ok|fine|alright|cool|whatever)\b|안녕히|잘 ?가|됐어|괜찮아|아니야|고마워|감사|그래|네|수고|알았어|"
                       r"그게 ?다|빠이|바이|나중에|안녕\s*[.!]?$", re.I)
TALK_RECENT_S = 20.0                # s; someone spoke with Lumi this recently: what they say next is to Lumi too
COMPANY_Q = re.compile(r"\b(cutshion|barista robot|drawing robot|your (maker|makers|company|ceo|price)|(this|the|that|what|which) company|"
                       r"ceo of (it|this|the company)|founder of (it|this)|mega ?coffee|"
                       r"sonovictus|omron|borgwarner|bogate|cnt tech|seed round|target market|business model|(your|cutshion'?s?) awards?|how much (do|does) (you|it|this|lumi) cost)\b|"
                       r"쿳션|컷션|커션|메가커피|소노빅터스|받은 상|수상|(이|그|너희|루미) ?회사|회사 ?(대표|이름|어디)|대표님|바리스타|드로잉|(너|루미|이 로봇) ?가격", re.I)     # never looked up online: from the notes only
VENUE_Q = re.compile(r"\b(here|conference|keynote|booths?|exhibitors?|restrooms?|toilets?|bathrooms?|venue|tickets?|"
                     r"admission|entrance fee|lunch break|who is speaking|speakers today)\b|\bthis (event|show|fair|expo|building)\b|"
                     r"여기|행사|부스|화장실|입장료|입장권|키노트|발표자|몇 ?시까지|운영 ?시간|이 건물", re.I)   # this event / building
VENUE_ONLY = re.compile(r"\b(conference|keynote|booths?|exhibitors?|venue|who is speaking|speakers today)\b|"
                        r"\bthis (event|show|fair|expo|building)\b|행사|부스|키노트|발표자|이 건물", re.I)   # never about elsewhere
OUTSIDE_NAME = re.compile(r"(?<=\S )(?!I\b|Lumi\b|Cutshion\b)[A-Z][a-z]{2,}")      # a name, as typed or written by whisper
OUTSIDE = re.compile(r"\b(?:museum|park|tower|palace|mall|store|shop|"
                     r"restaurant|cafe|station|airport|library|zoo|hospital|bank|market|university)\b|"
                     r"(?<![가-힣])(?!여기|거기|이곳|저기|오늘|지금|보통|주말|평일|내일)[가-힣]{2,}?(?:은|는|이|가|의)?\s+"
                     r"(?:몇 ?시까지|운영 ?시간|입장료|입장권)", re.I)   # "루브르 몇 시까지 해?": a place elsewhere
ABOUT_LUMI = re.compile(r"\b(you|your|yourself|lumi|battery|charging|payload|gripper|lidar)\b|너|네가|니가|넌|루미|당신|로봇|"
                        r"배터리|충전|센서|카메라|라이다|그리퍼|가반하중|팔 ?길이|무게|키가|속도|마이크", re.I)   # Korean drops "you"
COMMAND_START = re.compile(r"^\s*(please\s+)?(go|come|take|bring|throw|put|give|pick|drive|move|turn|jump|dance|fly|"
                           r"push|hit|kick|open|close|grab|carry|follow|show|run|scoot|spin|extend|leave|drop|hold|pass|hand|"
                           r"sit|stand|wave|look|lift|raise|lower|climb|make|do)\b", re.I)   # an order, not a question
EMPTY_HAND = re.compile(r"\b(give|hand|pass) (it|that|this)( (over|back|here))?( to me)?\b|\bhand (it )?over\b|"
                        r"\bcan i have (it|that|this)\b|(그거|이거|그것|그걸|이걸)\s*(이제|이리|좀|빨리)?\s*(나|저)?(한테|에게)?\s*"
                        r"(줘|주세요|건네)|"
                        r"\b(put|place|set) (it|that|this) (down|on the table)\b|(그거|그것|이거|그걸|이걸)\s*(나한테|저한테|나|저)?\s*"
                        r"(줘|주세요|건네)|들고 ?있는 ?(거|것)을?\s*(나|저)?(한테|에게)?\s*(줘|주세요)|^\s*건네\s*(줘|주세요)|테이블에\s*(놔|놓아|둬)|내려\s*(놔|놓아)", re.I)
EMPTY_HAND_SAY = {"en": "I'm not holding anything right now.", "ko": "지금은 손에 아무것도 들고 있지 않아요."}
ASK_PREFIX = re.compile(r"\b(do|did) you (know|happen to know)\b|\b(can|could) you (tell|find out|look up|check)( me)?\b|"
                        r"아세요|알아요|알아\?", re.I)          # "do you know who won?" is not about Lumi
ASKS_MORE = re.compile(r"\?|\b(but|can|could|what|how|where|why|when|who)\b|근데|그런데|뭐|어떻게|어디|언제|누구", re.I)
FOREIGN_SCRIPT = re.compile(r"[\u0400-\u04ff\u4e00-\u9fff\u3040-\u30ff]")   # Cyrillic, Chinese, Japanese
UNSURE_LOOKUP = False      # look up what the model says it is not sure of: on for gemma4:e4b, which said "not sure"
                           # instead of choosing search; gemma4:26b chooses search itself, and its "not sure" answers
                           # (2026-10-19 checks: 11 of 11) were about Lumi, Cutshion or the venue, never a lookup
NOT_KNOWN = {"en": ["I'm sorry, I don't have that information. A staff member can help you.",
                    "That one I don't know, sorry. A staff member here can tell you.",
                    "I'm not sure about that. Please ask a staff member."],
             "ko": ["죄송해요, 그 정보는 없어요. 직원분께 여쭤봐 주세요.",
                    "그건 저도 잘 몰라요. 직원분께 물어봐 주시겠어요?",
                    "아쉽지만 그건 제가 알 수 없어요. 직원분이 알려 드릴 거예요."]}   # said when a lookup is refused


def not_known(lang):
    return random.choice(NOT_KNOWN[lang])
TALK_ASK_S = 15.0                   # s of silence while halted for someone -> "Can I go on with my task?", again -> go on
FAREWELL_ONLY = re.compile(r"^\s*(?:(?:ok(?:ay)?|alright|lumi|루미야?)[\s,.!]+)?(?:go on|you can go|good|very good|"
                           r"good job|great job|nice job|well done|take care|"
                           r"가 ?보세요|가세요|가도 ?돼요?|잘했어요?|잘했네요?|좋아|좋네요?|수고했어요?|고생했어요?|"
                           r"됐어요?,? 고마워요?)[\s.!~]*$", re.I)   # said alone: the talk is over
THANKS = re.compile(r"\bthank(?:s| you)\b|\bthanx\b|고마워|고맙|감사|땡큐", re.I)
DONE_WORDS = re.compile(r"\bthat'?s (?:it|all|enough)\b|\bno,? thanks?\b|\bnothing(?: else)?\b|\benough\b|됐어|됐습니다|"
                        r"그만", re.I)            # with thanks: "that's it, thank you", "됐어요 고마워요" end the talk
WELCOME = {"en": ["You're welcome.", "My pleasure.", "Anytime."], "ko": ["천만에요.", "별말씀을요.", "네, 언제든지요."]}
RECEIVE_OK = re.compile(r"\b(ok(ay)?|done|here you go|there you go|go ahead|thank|thanks|yes)\b|됐어|됐습니다|놨어|여기요|"
                        r"네|고마워|감사", re.I)     # the person has let go of what they handed over
FETCH_THANKS = re.compile(r"\bthank|\bthanks\b|고마워|감사", re.I)
_STATUS_P = r"^(?:(?:루미야?|너는?|넌|지금|거기서|여기서|저기요?|혹시|근데|자|음|그럼)[\s,]*)*"
STATUS_Q = re.compile(
    r"\bwhat(?:'re| are| r)? (?:exactly |else )?(?:are )?(?:you|u|ya)(?:'re| are)? (?:currently |now )?(?:doing|up to|working on|busy with)\b"
    r"(?! (?:tonight|tomorrow|later|this weekend|after|for (?:a )?(?:living|work)))|\bwhatcha doing\b|"
    r"\bwhat (?:is it )?you(?:'re| are) doing\b|\bwhat are you supposed to be doing\b|"
    r"\bwhat(?:'?s| is) your (?:current )?(?:task|mission)\b|\bwhat(?:'?s| is) your (?:current job|job (?:right )?now)\b|"
    r"\bwhat (?:task|job|mission) are you (?:doing|on|running)\b|\bwhich task are you\b|"
    r"\bare you doing (?:a|any) (?:job|task)\b|"
    r"그리퍼에 ?(?:뭐|무엇|뭔가)|어디 ?가려고|\bwhat'?s going on,? (?:lumi|robot)\b|\bwho sent you\b|\bwhat(?:'?s| is) (?:the|your) plan (?:right )?now\b|"
    r"\bwhat (?:were you told|did (?:they|someone|somebody) (?:ask|tell) you) to do\b|"
    r"\b(?:are|r) (?:you|u) (?:busy|free|available|working|on duty|on (?:a|your) (?:task|mission|way)|in the middle of something|"
    r"doing (?:something|anything|a delivery)|working on something|delivering|leaving)\b|^\s*(?:you )?busy\s*\??\s*$|\bis lumi busy\b|"
    r"\bdo you have (?:a (?:task|job)|something to do|anything to do) (?:right )?now\b|"
    r"\bwhere(?:'re| are| r)? (?:you|u|ya) (?:going|heading|headed|driving|off to|moving|taking|bringing|rolling|on your way|trying to go)\b|"
    r"\bwhere (?:do|will) you go (?:now|next)\b|\bwhere is (?:that|this|it) going\b|\bwhich way are you going\b|"
    r"\b(?:what'?s|what is|where'?s|where is) your (?:destination|goal|target|next stop)\b|"
    r"\bare you going (?:somewhere|anywhere|home)\b|\bare you going to (?:charge|your (?:charger|dock)|p\s?\d+|point \w+)\b|"
    r"\bwhat (?:\w+ )?(?:are|r|'re)? ?(?:you|u) (?:holding|carrying|bringing|delivering|hanging on to)\b|"
    r"\bwhat(?:'?s| is|s) (?:that )?in your (?:hand|hands|gripper)\b|\bwhat (?:do you have|have you got) (?:in your hand|there)\b|"
    r"\bwhat did you (?:just )?(?:pick up|grab)\b|\bare you (?:holding|carrying) (?:something|anything|a \w+)\b|"
    r"\bis your hand empty\b|\bis there (?:something|anything) in your hand\b|\bis that an? \w+ in your hand\b|"
    r"\bdo you have (?:a cup|something in your hand|anything in your hand)\b|\bwho is that (?:\w+ )?for\b|\bis that for me\b|"
    + _STATUS_P + r"(?:뭐|뭘) ?(?:해(?![줄줘주봐볼도야서라])|하니|하냐|함|하고 ?(?:있|계)|하는 ?(?:중|거))|일하고 ?있|(?:뭐|뭘|무슨 (?:일|작업)을?) ?하고 ?(?:있|계)|"
    r"무슨 (?:일|작업)을? ?하는 ?중|뭐 ?하느라|수행 ?중인 (?:작업|일)|지금 무슨 (?:일|작업)을? ?해|(?:작업|일하는|배달|배달하는|심부름|쉬는) ?중이|"
    r"지금 (?:바빠|바쁘|한가)|^(?:루미 )?바빠|바쁘세요|^(?:지금 )?한가해|(?:임무|맡은 일|하는 일|할 일)(?:이|가|은)? ?(?:뭐|있)|"
    + _STATUS_P + r"어디(?:로|에)? ?(?:가|가요|가세요|가니)[\s?.!]*$|어디(?:로)? ?가(?:고 ?있|는)|어디로 ?이동|목적지|어디까지 ?가|"
    r"다음에 어디|(?:충전하러|집에) 가는 (?:거|중)|어디로 가져가|어디 갔다 와|"
    r"(?:뭐|뭘) ?(?:들고|잡고|가지고)|손에 ?(?:뭐|든|들고|잡은|아무것도)|들고 ?있는 ?(?:게|거)|"
    r"(?:컵|병|사과|바나나|오렌지)(?:을|를)? ?들고 ?있(?:어|니|나요|어요)?\?|손이 ?비어|뭐 ?가져가는|그거 ?(?:누구 ?거|나 ?주는)", re.I)
NOT_STATUS_NOW = re.compile(r"\b(tonight|after work|weekend|tomorrow|later today|for fun|in your free time)\b|주말|쉬는 날|"
                            r"저 사람|우리|내일|퇴근|나중에", re.I)    # not about what Lumi is doing now
FAREWELL_WORDS = re.compile(r"\b(thanks?|thank you|bye|bay bay|goodbye|(?<!can't )(?<!cant )(?<!cannot )(?<!not )(?<!to )see you|see ya|that'?s all|good night)\b|(?<=\S)[\s.,!]+안녕[\s.!~]*$|고마워|감사|안녕히|잘 ?가|"
                            r"다음에|수고하세요|잘 ?있어|잘 ?있게|바이바이|빠이|(?<![가-힣])바이(?![가-힣])|땡큐|(?<![가-힣])간다[\s.!~]*$|i (have|need) to go|gotta go|i'?m leaving|"
                            r"nice (talking|meeting|chatting)( (to|with))? you|(was|been) nice to meet you|good night|take care|들어가세요|"
                            r"가 ?볼게요|갈게요|이만|나중에 봐요|또 봐요|좋은 하루|(^|\s)(나|저|우리|저희) (이제 )?(집에 )?(가|간다|가요|갑니다)[\s.!]*$",
                            re.I)
HELLO_ONLY = re.compile(r"^\s*(hi|hey|hello|hiya)( there)?[\s,.!]*$|^\s*(안녕|안녕하세요)[\s.!]*$", re.I)
CAMERA_HALF_FOV = 42.0             # deg; half the camera's view (+ the head's YAW_LIMIT for the head camera)
WAKE_MAX_S = 6.0                   # s; longer utterances are not checked for the wake word
BARGE_IN_LOGPROB = -0.6            # an interruption must be heard more clearly than a normal answer (-1.0)
BYE_WAVE = re.compile(r"\bb(?:ye|ay)[- ]?b(?:ye|ay)\b|바이 ?바이|빠이 ?빠이|잘 ?가", re.I)   # a goodbye with a wave
CLOSING_WAIT_S = 8.0               # s of silence after "okay" / "thank you" / "네" before Lumi says goodbye
ANSWER_ECHO_S = 10.0               # s of Lumi's speech a dialog answer is checked against for echo: only the question
                                   # (the wake reply "Yes?" 20 s earlier swallowed the answer "Yes. Yes.", 2026-10-21)
VOICE_SESSION_S = 15.0             # s a conversation started by voice (nobody in view) waits for the next words
SPEAKER_MATCH_DEG = 25.0           # a voice direction belongs to the visible person within this angle
DOA_MIN_CONF = 0.12                # below this the sound direction is not trusted
COME_STOP = 1.1                    # m; driving to a person stops when the camera sees them this close
COME_TIMEOUT = 60.0                # s
MAX_MOVE_M = 3.0                   # m; "move forward N metres" is limited to this
ARM_REACH_PROGRAM = "arm_reach.jks"   # Cobo π program for "reach out your hand" (to be recorded on the robot)
STUCK_DRIVE_S = 20.0               # s "running" without moving -> the drive is cancelled and Lumi says so
MODES_FILE = "/dev/shm/lumi_modes.json"   # written by api/server.py: {"greeter", "patrol", "wave", "drive"}
CMD_FILE = "/dev/shm/lumi_cmd.json"       # written by api/server.py: {"id", "cmd": go | go_point | cancel | calibrate
                                          # | fetch | fetch_give | fetch_place | fetch_stop | fetch_carry | fetch_release | fetch_steps
                                          # | fetch_pause | fetch_resume}
CALIB_FILE = "/dev/shm/lumi_calib.json"   # progress of a calibration session, for the dashboard
BUSY_FILE = "/dev/shm/lumi_busy.json"     # what runs here now, for api/server.py robot_free(): {"busy": skill |
                                          # follow | drive | wave | null} (fetch tasks are in lumi_task.json)
CALIB_S = 120.0                    # s a calibration session lasts
CALIB_NEAR = 2.0                   # m; the speaker for a calibration sample is the nearest person within this
CALIB_ALONE_DEG = 30.0             # ... with nobody else within this angle (closer than 4 m)
QUIET_S = 600.0                    # s Lumi greets nobody after "be quiet" (the wake word still works)
STUCK_S = 90.0                     # s without a main-loop pass -> stacks of all threads into the log
GREETING = "Hi, I'm Lumi, the assistant robot. How can I help you?"   # same voice as every other answer
PROMPT = {"en": "How can I help you?", "ko": "무엇을 도와드릴까요?"}
WELCOME_BACK = {"en": "Welcome back! How can I help you?", "ko": "다시 오셨네요, 무엇을 도와드릴까요?"}
RECENT_S = 150.0                   # s; someone known back within this while the talk was open: Lumi just listens on
IN_VIEW_S = 0.5                    # s; a track seen this recently is someone else in view (not the one coming back)
PATH_HALF_WIDTH = 0.4              # m to each side of the robot's centre line; on patrol only people in this
                                   # corridor are greeted (not people sitting at desks beside the aisle)
CAMERA_STALL_S = 3.0               # s without a camera frame -> reopen the camera
CAMERA_FRESH_S = 2.5               # s; a camera whose last detection is older counts as down (idle rate is 1/s)
HEALTH_S = 30.0                    # s between "camera ok" lines in the log
PATROL_WAIT_S = 8.0                # s; on patrol, after the greeting or the last answer, wait this long for speech
LOW_BATTERY, RESUME_BATTERY = 5, 60    # %
PAUSE_AT_END = 3.0                 # s to wait at each patrol point


LOG_FILE = os.path.join(ROOT, "logs", "lumi.log")
if os.path.basename(os.path.dirname(os.path.abspath(sys.argv[0]))) == "tests":
    LOG_FILE = os.devnull                       # a self-check (tests/*.py) never writes the real log


def log(msg):
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a") as f:          # also kept in lumi.log, to read it over SSH
            f.write(line + "\n")
    except OSError:
        pass


def safe(fn, *args, default=None):
    """Call a robot function; on a network error log it and carry on instead of crashing."""
    try:
        return fn(*args)
    except Exception as e:
        log(f"{getattr(fn, '__name__', fn)} failed: {e}")
        return default


NOISE_WORDS = re.compile(r"\W*(?:u+m+|h?m+|uh+|ah+|oh+|boom|beep|ding|bang|pop|knock|음+|어+|아+)\W*", re.I)   # whisper for room sounds
_doa_fit = threading.Lock()        # one sound-direction refit at a time

class Track:
    _ids = itertools.count(1)

    def __init__(self, p, now):
        self.id = next(self._ids)
        self.distance, self.angle = p["distance_m"], p["angle_deg"]
        self.history = collections.deque(maxlen=7)     # recent distances, median-filtered
        self.first_seen = self.last_seen = now
        self.zone_since = None
        self.greeted = False
        self.look = self.face = None                   # clothes and face signatures (vision/reid.py)
        self.faces = 0                                 # frames with a face
        self.person = None                             # reid.Person once greeted: who this is

    def update(self, p, now, arm_moving=False, near_max=NEAR_MAX):
        self.angle, self.last_seen = p["angle_deg"], now
        if p.get("look"):
            self.look = reid.blend(self.look, p["look"])
        self.face = reid.blend_face(self.face, p.get("face"))
        self.faces += p.get("face") is not None
        if self.person is not None:
            self.person.seen(p.get("look"), p.get("face"), now)
        d = p["distance_m"]
        if not (arm_moving and self.history and d < self.distance - OCCLUSION_DROP):
            self.history.append(d)
            self.distance = sorted(self.history)[len(self.history) // 2]
        in_zone = NEAR_MIN <= self.distance <= near_max
        self.zone_since = (self.zone_since or now) if in_zone else None


def too_close(people, frame_h):
    """People really closer than TOO_CLOSE: small depth AND a box that fills the frame."""
    return [p for p in people if p["distance_m"] < TOO_CLOSE and (p["box"][3] - p["box"][1]) > CLOSE_BOX * frame_h]


class Vision(threading.Thread):
    """Person detection + simple tracking (nearest match by angle and distance)."""

    def __init__(self, camera=None, near_max=NEAR_MAX, corridor=None):
        super().__init__(daemon=True)
        self.near_max, self.corridor = near_max, corridor     # corridor: half width in m, None = everyone
        self.last_report = 0.0
        self.pinned = camera                      # None: Lumi.step sets self.prefer (head standing, torso driving)
        self.prefer = camera or "head"
        self.camera = self.pick()
        self.det = camview.RemoteDetector(self.camera, HEAD_SIGN)   # the camera service owns the cameras
        self.tracks = []
        self.people = reid.People()               # whom Lumi has greeted, in memory only
        self.lock = threading.Lock()
        self.arm_watch = False

    @staticmethod
    def alive(name):
        try:
            return time.time() - camview.det_path(name).stat().st_mtime < CAMERA_FRESH_S
        except FileNotFoundError:
            return False

    def pick(self):
        """The preferred camera, or the other one while the preferred gives no detections."""
        other = "torso" if self.prefer == "head" else "head"
        return other if not self.alive(self.prefer) and self.alive(other) else self.prefer

    def use(self, name):
        """Read people from this camera from now on (tracks are kept: both give waist-frame angles)."""
        focus = self.det.focus_angle
        self.det.close()
        self.det = camview.RemoteDetector(name, HEAD_SIGN)
        self.det.focus_angle = focus
        self.camera = name

    def run(self):
        last_frame = last_health = last_pick = time.time()
        frames = 0
        while True:
            if time.time() - last_pick > 1.0:
                last_pick = time.time()
                want = self.pick()
                if want != self.camera:
                    log(f"camera: {self.camera} -> {want}" + ("" if want == self.prefer else f" ({self.prefer} gives no detections)"))
                    self.use(want)
            try:
                color, people = self.det.read()
            except Exception as e:
                log(f"camera error: {e!r}")
                color, people = None, []
            now = time.time()
            if color is None:
                if now - last_frame > CAMERA_STALL_S:         # no frames: reopen the camera
                    log(f"camera: no frames for {now - last_frame:.0f} s - reopening")
                    self.reopen()
                    last_frame = time.time()
                continue
            last_frame, frames = now, frames + 1
            if now - last_health > HEALTH_S:                  # proves the camera is alive even with nobody around
                log(f"camera ok ({self.det.name}): {frames / (now - last_health):.1f} fps, {len(people)} people in view, "
                    f"{self.det.bad_jpeg} broken frames skipped, {self.det.reopens} reopens")
                last_health, frames = now, 0
            people = [p for p in people if p["distance_m"] is not None]
            with self.lock:
                free = list(self.tracks)
                for p in sorted(people, key=lambda p: p["distance_m"]):
                    best = min(free, default=None, key=lambda t: abs(t.angle - p["angle_deg"]))
                    if best and abs(best.angle - p["angle_deg"]) < MATCH_DEG:
                        best.update(p, now, self.arm_watch, self.near_max)
                        free.remove(best)
                    else:
                        t = Track(p, now)
                        t.update(p, now, near_max=self.near_max)
                        self.tracks.append(t)
                self.tracks = [t for t in self.tracks if now - t.last_seen < LOST_S]
                if self.tracks and now - self.last_report > 3.0:      # what the camera sees, for checking on the robot
                    self.last_report = now
                    log("see " + ", ".join(f"#{t.id} {t.distance:.2f} m {t.angle:+.0f} deg" + (" greeted" if t.greeted else "")
                                           + ("" if self.in_path(t) else " side")
                                           for t in self.tracks))
            # safety: really close = small depth AND a box that fills the frame (the arm in front of a person
            # changes the depth but not the size of the person's box)
            close = too_close(people, color.shape[0])
            if self.arm_watch and not close and self.camera != "torso":   # the torso camera looks at the arm's side
                close = self.torso_close()
            if self.arm_watch and close:
                log(f"person at {close[0]['distance_m']} m - STOP arm")
                safe(motion.stop)                 # also ends the wave's waiting move at once
                self.arm_watch = False

    @staticmethod
    def torso_close():
        camview.want("torso")                     # full detection rate while the arm moves
        try:
            d = json.loads(camview.det_path("torso").read_text())
        except (FileNotFoundError, ValueError):
            return []
        if time.time() - d["time"] > 1.5:
            return []
        return too_close([p for p in d["people"] if p["distance_m"] is not None], d["height"])

    def reopen(self):
        try:
            self.det.close()
        except Exception:
            pass
        try:
            self.use(self.pick())
        except Exception as e:
            log(f"camera reopen failed: {e!r}")
            time.sleep(2)

    def present(self, track):
        """Is this person still here (seen recently and not far away)?"""
        with self.lock:
            return track in self.tracks and track.distance <= STAY_MAX

    def know(self, track):
        """Who this track is: (known person, s since last seen) or (a new person, None). Sets track.person."""
        now = time.time()
        with self.lock:
            taken = {t.person for t in self.tracks if t is not track and t.person and now - t.last_seen < IN_VIEW_S}
            known = self.people.recall(track.look, track.face, now, taken)
            gone = None if known is None else now - known.last_seen
            track.person = known or self.people.add(track.look, track.face, now)
            track.person.seen(None, None, now)
        return track.person, gone

    def in_path(self, t):
        return self.corridor is None or abs(t.distance * math.sin(math.radians(t.angle))) <= self.corridor

    def to_greet(self):
        """Nearest person waiting in the zone (and in the robot's path on patrol) not greeted yet, once a few faces are
        seen (who it is) or FACE_WAIT_S has passed."""
        now = time.time()
        with self.lock:
            ready = [t for t in self.tracks if not t.greeted and t.zone_since and now - t.zone_since >= HOLD_S
                     and (t.faces >= FACE_FRAMES or now - t.zone_since >= HOLD_S + FACE_WAIT_S) and self.in_path(t)]
        return min(ready, key=lambda t: t.distance, default=None)

    def near_angle(self, angle, max_diff=SPEAKER_MATCH_DEG):
        """The visible person closest to this waist-frame angle (deg), or None."""
        with self.lock:
            best = min(self.tracks, default=None, key=lambda t: abs(t.angle - angle))
        return best if best is not None and abs(best.angle - angle) <= max_diff else None

    def only_person(self):
        with self.lock:
            near = [t for t in self.tracks if t.distance <= 3.0]
        return near[0] if len(near) == 1 else None

    def nearest_greeted(self):
        with self.lock:
            here = [t for t in self.tracks if t.greeted and t.distance <= STAY_MAX]
        return min(here, key=lambda t: t.distance, default=None)

    def follow_view(self, track):
        """(distance m, angle deg, age s) of the person being followed (tasks/follow.py), None once the track is
        gone. The distance is the nearer of the median and the newest reading: the median lags when they stop."""
        with self.lock:
            if track not in self.tracks:
                return None
            return min(track.distance, track.history[-1]), track.angle, time.time() - track.last_seen

    def follow_views(self):
        """[(see, distance m, angle deg, age s)] of everyone in view: tasks/follow.py re-locks onto one of them."""
        with self.lock:
            tracks = list(self.tracks)
        return [(lambda t=t: self.follow_view(t),) + v for t in tracks if (v := self.follow_view(t))]


class Patrol:
    """Drive between markers in a loop (or once); pause for people; go home to charge when the battery is low."""

    def __init__(self, route, once=False, pause_s=PAUSE_AT_END):
        self.route, self.i = route, 0
        self.once, self.pause_s = once, pause_s
        self.mode = "patrol"             # patrol | going_home | charging | done
        self.moving = False              # a move that we started is running
        self.progress = None             # (pose, time) of the last movement, to notice a stuck drive
        self.stuck = None                # target of a drive that could not get anywhere (Lumi says so)
        self.wait_until = 0.0
        self.last_poll = 0.0

    def pause(self):
        if self.moving:
            log("drive paused")
            safe(agv.cancel)
            self.moving = False

    def tick(self, force=False):
        """Call often while nobody is being talked to; polls the base once a second.
        force=True: start the first leg now, even if the base is still driving somewhere else."""
        now = time.time()
        if now - self.last_poll < 1.0 and not force:
            return
        self.last_poll = now
        st = safe(agv.status, default=None)
        if not st:
            return
        battery, ms = st.get("power_percent", 100), st.get("move_status")

        if self.mode == "done":
            return
        if self.mode == "charging":
            if battery >= RESUME_BATTERY:
                log(f"battery {battery} % - patrol again")
                self.mode = "patrol"
            return
        if self.mode == "patrol" and battery < LOW_BATTERY:
            log(f"battery {battery} % - going home to charge")
            self.pause()
            ok, msg = safe(agv.go, "home", default=(False, "error"))
            self.mode, self.moving = ("going_home", True) if ok else ("patrol", False)
            return

        if self.moving:
            if ms == "running":
                pose = st.get("current_pose") or {}
                xy = (pose.get("x", 0.0), pose.get("y", 0.0), pose.get("theta", 0.0))
                if self.progress is None or math.hypot(xy[0] - self.progress[0][0], xy[1] - self.progress[0][1]) > 0.05 \
                        or abs(xy[2] - self.progress[0][2]) > 0.1:
                    self.progress = (xy, now)                   # it moves
                elif now - self.progress[1] > STUCK_DRIVE_S:   # "running" but standing still: no way through
                    target = self.route[self.i]
                    log(f"drive to {target} STUCK: the base has not moved for {STUCK_DRIVE_S:.0f} s "
                        f"(no free path? glass door, people, no-go line) - cancelled")
                    safe(agv.cancel)
                    self.moving, self.progress = False, None
                    self.stuck = target
                    if self.once:
                        self.mode = "done"
                    else:
                        self.i = (self.i + 1) % len(self.route)
                        self.wait_until = now + 5
                return
            self.moving, self.progress = False, None
            if self.mode == "going_home":
                self.mode = "charging" if st.get("charge_state") else "patrol"
                log("docked, charging" if self.mode == "charging" else f"could not dock ({ms})")
                return
            if ms == "succeeded":
                log(f"patrol at {self.route[self.i]}")
                if self.once and self.i == len(self.route) - 1:
                    self.mode = "done"
                    log("route finished")
                    return
                self.i = (self.i + 1) % len(self.route)
                self.wait_until = now + self.pause_s
            else:
                log(f"patrol move {ms} - retry in 5 s")
                self.wait_until = now + 5
            return
        if (ms == "running" and not force) or now < self.wait_until:   # something else is driving, or waiting
            return
        target = self.route[self.i]
        if isinstance(target, (tuple, list)):
            ok, msg = safe(agv.go_point, *target, default=(False, "error"))
        else:
            ok, msg = safe(agv.go, target, default=(False, "error"))
        if ok:
            self.moving = True
            log(f"patrol -> {target}")
        else:
            log(f"patrol cannot go to {self.route[self.i]}: {msg}")
            self.wait_until = now + 5


class Modes:
    """Live switches from the dashboard (MODES_FILE); the command line gives the defaults."""

    def __init__(self, args):
        self.greeter, self.patrol = True, bool(args.patrol)
        self.wave, self.drive = not args.no_arm, not args.no_drive
        self._read, self._mtime = 0.0, None
        self.refresh(force=True)

    def refresh(self, force=False):
        now = time.time()
        if not force and now - self._read < 0.5:
            return
        self._read = now
        try:
            m = os.stat(MODES_FILE).st_mtime
            if m != self._mtime:
                self._mtime = m
                d = json.load(open(MODES_FILE))
                changed = {k: d[k] for k in ("greeter", "patrol", "wave", "drive") if k in d and d[k] != getattr(self, k)}
                for k, v in changed.items():
                    setattr(self, k, bool(v))
                if changed and not force:
                    log(f"modes: {changed}")
        except (FileNotFoundError, ValueError):
            pass


class Lumi:
    def __init__(self, args):
        self.a = args
        self.brain = Brain()
        self.current = None              # the track we are talking with
        self.mission_hold = None         # "talk" / "safety": a mission is halted for someone (mission_talk)
        self.asked_go_on = False         # "Can I go on with my task?" was asked
        self.voice_until = 0.0           # a conversation started by voice with nobody in view lasts until then
        self.quiet_until = 0.0           # after "be quiet": no greetings until then
        self._yaw, self._yaw_time = 0.0, 0.0
        self.pending_text = None         # a question the visitor asked while Lumi was talking (barge-in)
        self.voice_angle, self.voice_trusted = 0.0, False   # where the last caller's voice came from
        self.closing_pending = None      # time of a weak closing word ("okay", "got it"): silence after it ends the talk
        self.lang = "en"
        self.skill_thread = None         # pick / put / move_object running in the background
        self.busy_now = ""               # last written to BUSY_FILE ("" = nothing written yet)
        self.last_song = None            # the song sung last ("another song" is a different one)
        self.mic = mic.get()
        self.modes = Modes(args)
        self.cmd_id = None
        self.calib_until = 0.0
        self.calib_n = 0
        self.patrol = None
        if args.patrol:
            route = args.patrol.split(",")
            unknown = [m for m in route if m not in self.markers]
            if unknown:
                raise SystemExit(f"unknown markers {unknown}; markers on the map: {self.markers}")
            self.patrol = Patrol(route, args.once, args.pause)
        self.vision = None if args.no_camera else Vision(args.camera)
        log(f"markers: {self.markers}")

    @property
    def markers(self):
        """The active map's marker names (agv.known_markers: a new map is seen within seconds)."""
        return self._markers if getattr(self, "_markers", None) is not None else agv.known_markers()

    @markers.setter
    def markers(self, names):                    # a fixed list (self-checks)
        self._markers = names

    # ---------- actions ----------
    def turn_head(self, yaw=None, pitch=None):
        def run():
            try:
                cur = head.status()
                head.turn(cur[2] if yaw is None else yaw, cur[3] if pitch is None else pitch)
            except Exception as e:
                log(f"head error: {e}")
        threading.Thread(target=run, daemon=True).start()

    def wave(self, ok=None, quiet=False):
        """Wave because someone asked or said "bye bye" in view (never on a greeting): manipulation/wave.py checks the
        arm, the hand, the start pose and the whole path first; a refusal is said unless `quiet`. Not while following,
        on a mission or a task. `ok`: (English, Korean) said once the wave is checked. True if waved."""
        from tasks import follow
        if not self.modes.wave:
            log("  waving is switched off (dashboard)")
            return False
        st = self.fetch_status()
        why = (wave_mod.HOLDING if st == "holding" else
               wave_mod.BUSY if self.skill_busy() or self.mission_running() else
               wave_mod.DRIVING if follow.running() else None)
        try:
            if why:
                raise wave_mod.WaveError(*why)
            if self.vision:
                self.vision.arm_watch = True
            self.publish_busy("wave")
            wave_mod.wave(on_start=(lambda: self.fetch_say(*ok)) if ok else None)
            return True
        except wave_mod.WaveError as e:
            log(f"  wave refused: {e.args[0]}")
            if not quiet:
                self.fetch_say(*e.args)
        except (motion.MotionError, ConnectionError, OSError) as e:
            log(f"  wave stopped: {e}")
            self.fetch_say("I stopped my arm.", "팔을 멈췄어요.")
        finally:
            if self.vision:
                self.vision.arm_watch = False
            self.publish_busy(None)
        return False

    def base_off(self, action, target="", say=True):
        """Greeter only (Patrol switched off on the dashboard): Lumi works standing in place (head, lift, arm,
        gripper) but never drives, turns the base or the waist. True (and said unless `say` is False) if `action`
        needs the base. The dashboard's own buttons and "stop" are not asked here."""
        if action not in BASE_ACTIONS or self.modes.patrol:     # "stop" never reads the switches
            return False
        log(f"  {action} {target} refused: Patrol is off")
        if say:
            self.fetch_say(*BASE_OFF_SAY)
            self.keep_listening()
        return True

    def arm_off(self):
        """An arm action asked with the arm switched off (not powered / enabled in Cobo π): "Please enable my arm
        first." is said, True. An arm that does not answer is left to the task's own checks."""
        st = safe(arm.cmd, "get_robot_state")
        if not isinstance(st, dict) or "enable" not in st or st.get("power") and st.get("enable"):
            return False
        log("  the arm is switched off: asked to enable it")
        self.fetch_say(*ARM_OFF_SAY)
        self.keep_listening()
        return True

    def stay(self, voice=True):
        """Tasks asked by voice with only Greeter on stay in place (fetch.stay_put: head and lift only, no base, no
        waist); the dashboard's tasks do not."""
        from tasks import fetch
        fetch.stay_put = voice and not self.modes.patrol

    def act(self, action, target):
        log(f"action: {action} {target}")
        if self.base_off(action, target, say=False):            # answer() has said why
            return
        if action in MOVING_ACTIONS and self.mission_running():
            log(f"  {action} refused: on a mission")             # the LLM's action must not take Lumi off its task
            return
        if action == "look" and target == "me":
            angle = self.current.angle if self.current else self.voice_angle
            self.turn_head(HEAD_SIGN * max(-head.YAW_LIMIT, min(head.YAW_LIMIT, angle)), 10)
        elif action == "look" and target.split()[0:1] and (target.split()[0] in LOOK or target == "away"):
            self.look(target)
        elif action == "lift":
            self.lift(target)
        elif action == "wave":
            threading.Thread(target=self.wave, daemon=True).start()   # while the reply is spoken
        elif action == "stop":
            from tasks import follow
            safe(follow.stop)                                        # first: the base gets 0 at once
            safe(agv.cancel)
            safe(skills.cancel)
            safe(motion.stop)                                        # also a wave's waiting move
        elif action == "go_to":
            if self.modes.drive:
                self.start_trip(target)
            else:
                log("  driving by voice is switched off (dashboard: Come when called)")
        elif action in ("move", "turn"):
            self.move_by(action, target)
        elif action == "come_back":
            if self.modes.drive:
                self.come_back()
        elif action == "arm":
            self.arm_pose(target)
        elif action in ("pick", "put", "move_object"):
            self.object_task(action, target, confirm=False)          # the LLM's words already confirmed it
        elif action == "fetch":                                      # parse the person's own words, never the LLM's
            self.fetch_request(getattr(self, "heard", "") or target)  # wording ("ap" must not become "apple")
        elif action in ("give", "place"):
            if self.fetch_status() == "holding":
                self.fetch_finish(action)

    def look(self, target):
        """'left', 'left 30', 'down small' (brain.head_goal): the head, cut to its range. Returns "yaw" / "pitch"
        when a number asked for was past the range, else None."""
        cur = safe(head.status)
        if cur is None:
            return None
        yaw, pitch, limited = brain_mod.head_goal(target, cur[2], cur[3], LOOK)   # the body's full range (AXIS_LIMITS):
        threading.Thread(target=lambda: safe(head.moveto, [cur[0], cur[1], yaw, pitch]),   # head.turn() keeps
                         daemon=True).start()                                              # to YAW_LIMIT
        return limited

    def lift(self, target):
        """'up', 'down', 'up small', 'up 50' (mm; brain.lift_goal): the lift, slowly, cut to 0..head.LIFT_MAX_MM.
        Returns True when a number asked for was cut."""
        cur = safe(head.status)
        if cur is None:
            return False
        mm, limited = brain_mod.lift_goal(target, cur[0], head.LIFT_MAX_MM)
        log(f"  lift {cur[0]:.0f} -> {mm:.0f} mm")
        threading.Thread(target=lambda: safe(lambda: head.moveto([mm, cur[1], cur[2], cur[3]], LIFT_VEL)),
                         daemon=True).start()
        return limited

    def move_by(self, action, target):
        """'move forward 1' / 'move left 0.5' / 'turn around 180' / 'turn left 90', relative to where Lumi stands.
        Left / right are a normal base move to a map point, so obstacles are avoided; forward and back are a straight
        drive of exactly that length (fetch._move). Returns False if not possible (an amount not read or past the
        limit is never driven: driving.read has asked / refused it)."""
        if not self.modes.drive:
            log("  driving by voice is switched off (dashboard: Come when called)")
            return False
        parts = (target or "").split()
        direction = parts[0] if parts else "forward"
        try:
            amount = float(parts[1]) if len(parts) > 1 else (driving.DEFAULT_M if action == "move" else 90.0)
        except ValueError:
            if action == "move":
                log(f"  move {target!r}: no distance read, not driven")
                return False
            amount = 90.0
        if action == "move" and not driving.MOVE_MIN_M <= amount <= MAX_MOVE_M:
            log(f"  move {amount:g} m: outside {driving.MOVE_MIN_M:g}..{MAX_MOVE_M:g} m, not driven")
            return False
        if action == "move" and direction in ("back", "forward"):   # straight with joy_control, checked like a
            from tasks import fetch                               # mission's move: navigation may turn round and
            log(f"  move {direction} {amount:g} m straight")      # stops within its own tolerance
            self.stay()
            try:
                fetch.run_steps([{"do": "move", "dir": direction, "m": amount}], say=self.fetch_say)
            except fetch.FetchError as e:
                log(f"  move {direction} refused: {e}")
                self.fetch_say(str(e), "죄송해요, 지금은 할 수 없어요.")
                return False
            return True
        pose = safe(agv.pose)
        if pose is None:
            return False
        x, y, th = pose
        if action == "turn":
            turn = math.radians({"left": 1, "right": -1}.get(direction, 1) * (180.0 if direction == "around" else amount))
            goal = (x, y, (th + turn + math.pi) % (2 * math.pi) - math.pi)
        else:
            side = {"forward": 0.0, "back": math.pi, "left": math.pi / 2, "right": -math.pi / 2}.get(direction, 0.0)
            goal = (x + amount * math.cos(th + side), y + amount * math.sin(th + side), th)
        log(f"  {action} {direction} {amount:g} -> map ({goal[0]:.2f}, {goal[1]:.2f}, {math.degrees(goal[2]):.0f} deg)")
        self.start_trip(goal, remember=False)               # a short move is no trip: "come back" stays
        return True

    def drive_words(self, text):
        """Speed changes ("a bit faster", "너무 빨라"), "more" / "again" right after a move or a speed change, and a
        drive asked about ("move back 20": how far?) or refused (past the limit): driving.read. Plain moves are left
        to quick_command. A speed change is taken before a mission halts for talk: it applies to the move running
        now. True if handled here."""
        from tasks import fetch
        hist = self.brain.history
        t = brain_mod._norm(text)
        got = driving.read(t, driving.last_command(hist), driving.talking(hist))
        if not got or got[0] != "speed" and (self.mission_running() or got == driving.read(t, None, True)
                                              and got[0] == "move"):
            return False
        lang = "en" if self.lang == "en" else "ko"
        if got[0] == "speed":
            old = fetch.speed_factor
            new = safe(fetch.set_speed, old + got[1] * fetch.SPEED_STEP, default=old)
            say = driving.say_speed(got[1], new, new != old, lang)
            hist.append((text, f"ACTION: speed {got[1]}\n{say}"))
        elif got[0] == "move":                              # "again" / "a few centimetres more" after a move
            d, n = got[1].split()
            hist.append((text, f"ACTION: move {got[1]}"))
            if self.base_off("move"):
                return True
            log(f"  action move {got[1]} (again)")
            if not self.modes.drive:
                say = "Sorry, driving is switched off." if lang == "en" else "죄송해요, 지금은 이동할 수 없어요."
            elif not self.move_by("move", got[1]):
                return True
            else:
                say = driving.say_move(d, float(n), got[2], lang)
        elif got[0] == "turn":                              # "again" / "a bit more" after a turn
            hist.append((text, f"ACTION: turn {got[1]}"))
            if self.base_off("turn"):
                return True
            log(f"  action turn {got[1]} (again)")
            if not self.modes.drive:
                say = "Sorry, driving is switched off." if lang == "en" else "죄송해요, 지금은 이동할 수 없어요."
            elif not self.move_by("turn", got[1]):
                return True
            else:
                say = "Okay." if lang == "en" else "네."
        elif got[0] == "refuse":
            d, n = got[1].split()
            say = driving.say_refused(d, float(n), lang)
        else:
            say = driving.say_ask(got[1], lang)
        log(f"  drive words {got}: {say}")
        mouth.say(say)
        self.keep_listening()
        return True

    def skill_busy(self):
        return (self.skill_thread is not None and self.skill_thread.is_alive()) or self.fetch_status() in ("running", "holding")

    # ---------- fetch tasks (tasks/fetch.py, docs/16) ----------
    @staticmethod
    def fetch_status():
        try:
            from tasks import fetch
            st = fetch.state()
        except Exception:                              # no runner yet, or its state file is being written
            return None
        # a stopped / failed task can still have the object in the hand: give / place must still work
        return "holding" if st.get("holding") and st.get("status") != "running" else st.get("status")

    def fetch_finish(self, how, on=None, voice=True):
        """Give / place what the hand holds; a refusal ("I haven't learned how to hand things over yet") is spoken.
        `voice`: asked by voice (else from the dashboard)."""
        from tasks import fetch
        if voice and self.arm_off():
            return
        self.stay(voice)
        try:
            if how == "give":
                fetch.give(say=self.fetch_say)
            else:
                fetch.place(say=self.fetch_say, on=on)
        except fetch.FetchError as e:
            log(f"  fetch {how} refused: {e}")
            self.fetch_say(str(e), "죄송해요, 지금은 할 수 없어요.")

    def fetch_say(self, en, ko):
        """Spoken progress of the runner, in the language of the conversation."""
        mouth.say(en if self.lang == "en" else ko)

    def fetch_start(self, task):
        """Start a task; "here" becomes the robot's map pose now, so it does not move with the robot."""
        from tasks import fetch
        if any(task.get(k) not in (None, "here") for k in ("source", "dest")) and self.base_off("go_to"):
            return                                     # Greeter only: a fetch from / to a place drives
        self.stay()
        pose = safe(agv.pose)
        task = dict(task)
        for k in ("source", "dest"):
            if task.get(k) == "here" and pose:
                task[k] = dict(zip(("x", "y", "theta"), pose))
        log(f"  fetch start: {task}")
        try:
            fetch.start(task, say=self.fetch_say)
        except fetch.FetchError as e:
            log(f"  fetch refused: {e}")
            self.fetch_say(str(e), "죄송해요, 지금은 할 수 없어요.")
        self.keep_listening()

    def hear(self, wait_s):
        """One answer in a dialog: (text or None, understood)."""
        text = ears.listen(wait_s=wait_s, on_start=lambda: log("  hearing speech"))
        if not text or self.own_echo(text, ANSWER_ECHO_S):
            return None, True
        ok = ears.understood()
        log(f"  answer: {text!r} [{ears.last_stt.get('language')}, confidence {ears.last_stt.get('logprob')}]")
        if ok:
            self.lang = ears.heard_lang(self.lang)
        return text, ok

    def fetch_request(self, text):
        """A fetch said by voice: parse strictly, ask what is missing, read back, start on yes or silence."""
        if not self.modes.drive:
            self.fetch_say("Sorry, driving is switched off.", "죄송해요, 지금은 이동할 수 없어요.")
            return
        status = self.fetch_status()
        if status == "holding":
            from tasks import fetch
            self.fetch_say(f"I'm holding {fetch.held_name()}, where should I put it first?", "뭔가 들고 있어요. 먼저 어디에 둘까요?")
            return
        if status == "running":
            self.fetch_say("I'm still doing a task. Say stop to cancel it.", "아직 일하는 중이에요. 멈추려면 멈춰라고 하세요.")
            return
        from tasks import fetch
        task, problems = brain_mod.parse_fetch(text, self.markers)
        log(f"  fetch parsed: {task} problems {problems}")
        result = fetch_dialog.run(task, self.markers, self.hear, self.fetch_say, fetch.describe, self.fetch_start)
        log(f"  fetch dialog: {result}")
        self.keep_listening()

    def stop_all(self):
        """Stop by voice: the fetch / mission runner, the base, the arm, a trip; then say so."""
        from tasks import fetch
        log("  stop by voice")
        safe(fetch.stop)
        self.act("stop", "")
        if self.patrol:
            self.patrol.pause()
            self.patrol = None
        self.fetch_say("Okay, I stopped.", "네, 멈췄어요.")
        self.keep_listening()

    # ---------- answers by rule: what Lumi can do, its songs, its voice ----------
    def fixed_answer(self, text, last):
        """Answered without the LLM: what Lumi can do (assistant/abilities.py; the rest on "tell me more" / "yes"),
        which songs it knows, and right after a song "another one" / "again" / "그거 말고" (audio/sing.py). True if
        handled."""
        if last.startswith("ACTION: sing") and sing.AFTER_SONG.search(text) and sing.asked(text, last):
            self.sing_song(text)
            return True
        if sing.list_asked(text):
            say, mark = sing.list_reply(self.lang), "ACTION: none songs"
        else:
            got = abilities.answer(text, self.lang, last)
            if not got:
                return False
            say, mark = got[1], abilities.SHORT_MARK if got[0] == "short" else "ACTION: none -"
        self.brain.history.append((text, f"{mark}\n{say}"))
        log(f"  by rule: {say[:70]}")
        mouth.say(say, abort=self.speak_abort)
        self.keep_listening()
        return True

    def voice_setting(self, text, last):
        """"Speak louder", "I can't hear you", "소리 좀 줄여", "천천히 말해", and "a bit more" / "조금 더" right after:
        one step of the speaking volume or speed (assistant/voice_words.py), said at the new setting."""
        got = voice_words.read(text, last)
        if not got:
            return False
        kind, sign = got
        say = voice_words.apply(kind, sign, self.lang)
        self.brain.history.append((text, f"ACTION: voice {kind} {sign:+d}\n{say}"))
        log(f"  voice {kind} {sign:+d} (volume {mouth.volume()} %, speed {mouth.speed():.2f}): {say}")
        mouth.say(say)
        self.keep_listening()
        return True

    # ---------- singing (audio/sing.py) ----------
    def sing_song(self, text):
        """Sing a song for these words, the head moving with it. Blocks like speech; "stop" ends it at once, any
        other request ends it and is answered next ("sing another song" sings a different one)."""
        if self.skill_busy() or self.mission_running():   # the head and the speaker belong to the task now
            self.fetch_say("Sorry, I'm on a task right now. I can sing when I've finished.",
                           "죄송해요, 지금 다른 일을 하고 있어요. 끝나면 불러 드릴게요.")
            return
        song = sing.choose(text, self.lang, self.last_song)
        if song is None:                                   # a song we don't have: say which ones we know
            mouth.say(sing.unknown_reply(self.lang))
            self.keep_listening()
            return
        self.last_song = song
        self.brain.history.append((text, f"ACTION: sing {song}"))
        log(f"  singing {song}")
        done = sing.sing(song, abort=self.song_abort)
        log(f"  song {'finished' if done else 'stopped'}")
        self.keep_listening()

    def song_abort(self):
        """While singing (clip mic only, like barge_in): "stop" / "그만" ends the song; another clear request ends
        it and is answered next (pending_text). The song's own words and unclear sounds are ignored."""
        if self.interrupted():
            return True
        u = self.mic.next(0.0)
        if u is None or not getattr(u, "during_speech", False) or u.seconds < 0.25:
            return False
        text = (ears.transcribe(u.mono) or "").strip()
        if not text or self.own_echo(text) or not ears.understood(BARGE_IN_LOGPROB):
            return False
        if sing.stop_words(text):
            log(f"  stop singing: {text!r}")
            return True
        if brain_mod.is_backchannel(text):                 # "thank you": often whisper's guess on music; "wow"
            return False
        log(f"  song interrupted: {text!r}")
        self.pending_text = text
        return True

    # ---------- someone talks to Lumi on a mission ----------
    def mission_running(self):
        from tasks import fetch
        st = safe(fetch.state) or {}
        return st.get("status") == "running" and bool((st.get("task") or {}).get("steps"))

    def mission_talk(self, text):
        """Something said while a mission runs (docs/17 §6). Addressed speech halts it (fetch.pause) and Lumi talks;
        a stranger's new task is refused; the person the mission is for ("I'm James") gets it here or changes it;
        "go on" / goodbye / no answer go on. True if handled here; False: answer it as a question (still halted)."""
        from assistant import steps
        from tasks import fetch
        st = safe(fetch.state) or {}
        task = st.get("task") or {}
        task_steps = task.get("steps") or []
        waiting = (st.get("waiting") or {}).get("for")     # a wait step: time | go on | instruction | person
        if RECEIVE_OK.search(text) and st.get("step") == "receiving: waiting for okay" or \
                FETCH_THANKS.search(text) and st.get("step") == "giving":
            safe(fetch.release_now)                    # the person let go of it / has taken it
            return True
        recipient = next((s.get("person") for s in task_steps if s.get("do") == "give" and s.get("person")), None)
        name = claimed_name(text)
        owner = next((p for p in (recipient, task.get("sender")) if p and name and same_name(name, p)), None)
        mine = owner is not None                       # the person it is for, or who sent it
        if mine:
            name = owner                               # as the mission writes it ("James", not "james")
        was_halted = bool(self.mission_hold)
        addressed = WAKE.search(text) or TALK_WORDS.search(text) or SAFETY.search(text) or mine or name or \
            STATUS_Q.search(text) or \
            REQUEST.search(text) or GIVE_ME.search(text) or self.mission_hold or self.current is not None or \
            time.time() - getattr(self, "last_talk", 0.0) < TALK_RECENT_S or waiting == "instruction" or \
            waiting and GO_ON.search(text)
        self.last_talk = time.time()
        if not addressed:
            log(f"  mission: not to me, ignored: {text!r}")
            return True
        if not fetch.paused() and fetch.pause():
            log(f"  mission halted: someone talks to me ({text!r})")
            self.mission_hold, self.asked_go_on = "talk", False
        en = self.lang == "en"
        if SAFETY.search(text) and not lumi_question(text):
            self.mission_hold = "safety"
            log("  mission: safety stop, waiting for go on")
            self.fetch_say("Okay, I stopped. Tell me when I can go on.", "네, 멈췄어요. 가도 되면 말해 주세요.")
            return self.keep_listening() or True
        if getattr(self, "asked_give", False) and brain_mod.confirm_answer(text) in ("yes", "no"):
            self.asked_give = False
            if brain_mod.confirm_answer(text) == "yes":
                log(f"  mission: {recipient} takes it here")
                self.fetch_say("Here you go.", "여기 있어요.")
                self.replace_mission([{"do": "give", "person": recipient}])
            return self.keep_listening() or True
        if self.asked_go_on and brain_mod.confirm_answer(text) in ("yes", "no"):
            if brain_mod.confirm_answer(text) == "yes":
                self.resume_mission(say=True)
            else:
                self.asked_go_on = False
                self.fetch_say("Okay, I'll wait.", "네, 기다릴게요.")
            return self.keep_listening() or True
        if GO_ON.search(text) and not steps.read(text, self.markers, llm=False)[0] and not lumi_question(text):
            if waiting in ("time", "go on", "instruction"):
                safe(fetch.proceed)                    # "go on" ends a wait step
            self.resume_mission(say=True)
            return self.keep_listening() or True
        if was_halted and self.mission_hold == "talk" and DONE_TALK.search(text) and not name and \
                not steps.read(text, self.markers, llm=False)[0] and not REQUEST.search(text) and not GIVE_ME.search(text) \
                and not lumi_question(text):
            self.fetch_say("Okay, see you! I'll go on with my task.", "네, 안녕히 계세요! 하던 일 계속할게요.")
            self.resume_mission()
            return self.keep_listening() or True
        if waiting == "instruction":                   # "do what they tell you": the person here may give one task
            got, unread, _ = steps.read(WAKE.sub(" ", text).strip(" ,.!?"), self.markers)
            if got and not unread:
                self.instruction(got)
                return True
            if unread and (got or REQUEST.search(text) or COMMAND_START.search(text)):
                self.fetch_say(f"Sorry, I didn't understand: {', '.join(unread)}. Please say it again.",
                               "죄송해요, 일부를 이해하지 못했어요. 다시 말씀해 주세요.")
                return self.keep_listening() or True
        if mine:                                       # the person it is for: here, or what they say instead
            rest = WAKE.sub(" ", I_AM.sub(" ", text, count=1)).strip(" ,.!?")
            got, unread, _ = steps.read(rest, self.markers) if rest else ([], [], "")
            kinds = [s["do"] for s in got]
            if CANCEL_TASK.search(rest):
                log(f"  mission cancelled by {name}")
                self.fetch_say(f"Okay, {name}, I've cancelled it.", "네, 취소했어요.")
                safe(fetch.stop)
                self.mission_hold = None
            elif at_place(rest, self.markers) and name == recipient:     # "I'm at p5 now, bring it there"
                got = [{"do": "go", "to": at_place(rest, self.markers)}, {"do": "give", "person": recipient}]
                log(f"  mission changed by {name}: {got}")
                self.fetch_say(f"Okay, {name}. " + steps.describe(got), "네, 알겠어요. " + steps.describe(got, "ko"))
                self.replace_mission(got)
            elif got and not unread and (kinds not in (["give"], ["go", "give"]) or
                                         any(s.get("person") and not same_name(s["person"], name) for s in got)):
                if got[0]["do"] == "pick":                  # "give the bottle to Sara": the one I hold
                    got = got[1:]
                if name == recipient and got[-1]["do"] == "go":
                    got = got + [{"do": "give", "person": recipient}]       # "bring it to p10": still for them
                log(f"  mission changed by {name}: {got}")
                self.fetch_say(f"Okay, {name}. " + steps.describe(got), "네, 알겠어요. " + steps.describe(got, "ko"))
                self.replace_mission(got)
            elif rest and unread and CHANGE_WORDS.search(rest) and (not GIVE_ME.search(rest) or ELSEWHERE.search(rest)):
                self.fetch_say(f"Sorry {name}, I didn't understand. Should I give it to you here?",
                               f"{name}님, 잘 못 알아들었어요. 여기서 드릴까요?")
                self.asked_give = True
            else:
                log(f"  mission: {name} takes it here")
                self.fetch_say(f"Hi {name}, this is for you. Here you go.", f"{name}님, 이거 드릴게요.")
                self.replace_mission([{"do": "give", "person": recipient}])
            return self.keep_listening() or True
        if name and recipient and not mine and (REQUEST.search(text) or CHANGE_WORDS.search(text)) or \
                name and recipient and not mine and re.search(r"\b(give|hand|mine|for me|my name is)\b|주세요|줘|제 거|내 거", text, re.I):
            log(f"  mission: {name} is not {recipient}")
            self.fetch_say(f"Sorry, this is for {recipient}, I have to bring it to them.",
                           f"죄송해요, 이건 {recipient}님께 가져가는 거예요.")
            return self.keep_listening() or True
        got, unread, _ = steps.read(text, self.markers, llm=False)
        rule = brain_mod.intent(text, self.markers)
        insist = time.time() - getattr(self, "refused_at", 0.0) < TALK_RECENT_S and not lumi_question(text) and \
            not DONE_TALK.search(text)
        if CANCEL_TASK.search(text) or (got and not unread) or REQUEST.search(text) or GIVE_ME.search(text) or insist or \
                (rule and rule[0] in ("go_to", "come", "fetch", "move", "turn", "pick", "put", "move_object")):
            what = steps.describe(task_steps)
            log(f"  mission: a new task from someone else refused ({text!r})")
            self.refused_at = time.time()
            self.fetch_say(f"Sorry, I'm doing a task for someone: {what[0].lower() + what[1:]} I can help you when "
                           "I've finished.", "죄송해요, 지금 다른 분의 일을 하고 있어요. 끝나면 도와드릴게요.")
            return self.keep_listening() or True
        if FETCH_STOP.search(text) and len(re.findall(r"\w+", text)) <= 3 or NAME_ONLY.match(text) or HELLO_ONLY.match(text) \
                or (WAKE.search(text) and len(WAKE.sub("", text).strip(" ,.!?")) < 3):
            self.fetch_say("Hi, I'm Lumi. I stopped for you. How can I help you?",
                           "안녕하세요, 루미예요. 멈췄어요. 무엇을 도와드릴까요?")
            return self.keep_listening() or True
        return False                                   # a question: answered as usual, still halted

    def instruction(self, got):
        """The person at the place a mission waits at says what to do: read back, a spoken yes, then it is done
        there and the mission goes on (fetch.instruct; docs/17 §4)."""
        from assistant import steps
        from tasks import fetch

        def start(s):
            try:
                fetch.instruct(s)
                log(f"  mission: instruction taken: {s}")
                self.resume_mission()
            except fetch.FetchError as e:
                log(f"  mission: instruction refused: {e}")
                self.fetch_say(str(e), "죄송해요, 그렇게는 할 수 없어요.")
        log(f"  mission dialog (instruction): {fetch_dialog.run_steps(got, self.hear, self.fetch_say, steps.describe, start)}")
        self.keep_listening()

    def resume_mission(self, say=False):
        from tasks import fetch
        if say:
            self.fetch_say("Okay, I'll go on with my task.", "네, 하던 일 계속할게요.")
        log("  mission: going on")
        self.mission_hold, self.asked_go_on = None, False
        safe(fetch.resume)

    def replace_mission(self, new_steps):
        from tasks import fetch
        self.mission_hold, self.asked_go_on = None, False
        try:
            fetch.replace(new_steps, say=self.fetch_say)
        except fetch.FetchError as e:
            log(f"  mission change refused: {e}")
            self.fetch_say(str(e), "죄송해요, 지금은 할 수 없어요.")

    def mission_wait(self):
        """Halted for someone and nobody speaks: ask once whether to go on, then go on (never after a safety stop)."""
        if self.mission_hold != "talk" or time.time() - self.last_activity < TALK_ASK_S:
            return
        if not self.asked_go_on:
            self.asked_go_on = True
            self.fetch_say("Can I go on with my task?", "하던 일 계속해도 될까요?")
        else:
            log("  no answer - going on with the mission")
            self.resume_mission(say=True)
        self.last_activity = time.time()

    def now_doing(self):
        """(en, ko) of what Lumi is doing right now, from the task state and the trip, never guessed."""
        from assistant import steps
        from tasks import fetch
        st = safe(fetch.state) or {}
        task, running = st.get("task") or {}, st.get("status") == "running"
        held = fetch.held_name() if st.get("holding") else None
        w = st.get("waiting") if str(st.get("step") or "").startswith(("waiting", "receiving")) else None
        if w:                                          # a wait step: where, for what, how long still
            at = w.get("at") if w.get("at") not in (None, "here") else None
            where, where_ko = (f"at {at}", f"{at}에서") if at else ("here", "여기서")
            left = max(1, round(w["end"] - time.time())) if w.get("end") else None
            thing = f"the {w['object']}" if w.get("object") else "something"
            en, ko = {"time": (f"I'm waiting {where}, {steps._dur(left or 1)} left.",
                               f"{where_ko} 기다리고 있어요. {steps._dur(left or 1, True)} 남았어요."),
                      "go on": (f"I'm waiting {where} until someone tells me to go on.",
                                f"{where_ko} 가도 된다고 할 때까지 기다리고 있어요."),
                      "instruction": (f"I'm waiting {where} for an instruction.", f"{where_ko} 지시를 기다리고 있어요."),
                      "person": (f"I'm waiting {where} for someone to give me {thing}.",
                                 f"{where_ko} 누가 물건을 줄 때까지 기다리고 있어요.")}.get(
                w.get("for"), (f"I'm waiting {where}.", f"{where_ko} 기다리고 있어요."))
            return (en + f" I'm holding {held}." if held else en), ko
        if running and task.get("steps"):
            en, ko = f"I'm on a task: {steps.describe(task['steps'])}", "지금 일하는 중이에요: " + steps.describe(task["steps"], "ko")
            if st.get("step"):
                en += f" Right now: {st['step']}."
        elif running and task.get("object"):
            en, ko = f"I'm on a task: {fetch.describe(task)}", "지금 일하는 중이에요: " + fetch.describe(task, "ko")
        elif self.traveling():
            to = self.patrol.route[min(self.patrol.i, len(self.patrol.route) - 1)]
            name = "my charging dock" if to == "home" or self.patrol.mode == "going_home" else \
                to if isinstance(to, str) else "the point I was sent to"
            en, ko = f"I'm driving to {name}.", "충전소로 가는 중이에요." if "dock" in name else f"{name} 위치로 가는 중이에요."
        elif held:
            en, ko = f"I'm holding {held} and waiting for what to do with it.", "물건을 들고 다음 지시를 기다리고 있어요."
        else:
            return ("I'm talking with you. I'm not doing any task right now, and my hand is empty.",
                    "지금은 이야기하고 있어요. 하고 있는 일은 없고, 손도 비어 있어요.")
        if held and (running or self.traveling()):
            en += f" I'm holding {held}."
        return en, ko

    def mission_request(self, text):
        """A command of several steps (docs/17), said by voice: read back, start on yes or silence. True if it was
        one (also when refused). A single move / turn / arm / go stays with quick_command (no read-back)."""
        from assistant import steps
        read = read_mission(text, self.markers)
        if not read:
            return False
        got, unread, by = read
        if unread:
            log(f"  mission: unread {unread} ({by})")
            problem = brain_mod.place_problem(" ".join(unread), self.markers)   # "go to booth" with two booths
            if not problem and all(brain_mod.intent(u, self.markers) for u in unread):
                problem = (f"Sorry, I can't do that as part of a task: {', '.join(unread)}. Please ask me one thing at a time.",
                           "죄송해요, 그건 작업 중에 함께 할 수 없어요. 하나씩 말씀해 주세요.")
            self.fetch_say(*(problem or (f"Sorry, I didn't understand: {', '.join(unread)}. Please say it again.",
                                         "죄송해요, 일부를 이해하지 못했어요. 다시 말씀해 주세요.")))
            self.keep_listening()
            return True
        log(f"  mission ({by}): {got}")
        if {st["do"] for st in got} & DRIVE_STEPS and self.base_off("go_to"):
            return True
        if not self.modes.drive:
            self.fetch_say("Sorry, driving is switched off.", "죄송해요, 지금은 이동할 수 없어요.")
            return True
        if self.fetch_status() == "running":
            self.fetch_say("I'm still doing a task. Say stop to cancel it.", "아직 일하는 중이에요. 멈추려면 멈춰라고 하세요.")
            return True
        from tasks import fetch
        problems = steps.check(got, fetch.check_hand(), self.markers)
        if problems:
            log(f"  mission refused: {problems}")
            self.fetch_say(problems[0], "죄송해요, 그렇게는 할 수 없어요.")
            self.keep_listening()
            return True

        def start(s):
            self.stay()
            try:
                fetch.run_steps(s, say=self.fetch_say, sender=steps.sender(text))
            except fetch.FetchError as e:
                log(f"  mission refused: {e}")
                self.fetch_say(str(e), "죄송해요, 지금은 할 수 없어요.")
        result = fetch_dialog.run_steps(got, self.hear, self.fetch_say, steps.describe, start)
        log(f"  mission dialog: {result}")
        self.keep_listening()
        return True

    def hand_command(self, text):
        """Take from the person's hand / hand over / put down / open while holding, in any wording
        (brain.hand_request), and "no, the other one" right after a pick (brain.correction). True if handled."""
        from tasks import fetch
        if self.fetch_status() == "running":
            return False                               # the task's own words (fetch_voice): "okay" while receiving
        cor = brain_mod.correction(text, self.brain.history)
        if cor:
            if self.skill_thread is not None and self.skill_thread.is_alive():
                safe(skills.cancel)                    # the arm may be going for the wrong one: stop it first
            if cor[0] == "ask":
                self.fetch_say(*cor[1])
                self.keep_listening()
            else:
                self.brain.history.append((text, f"ACTION: pick {cor[1]}"))
                self.object_task("pick", cor[1])
            return True
        if not (brain_mod.hand_request(text, False, self.brain, self.markers) or
                brain_mod.hand_request(text, True, self.brain, self.markers)):
            return False
        held = self.fetch_status() == "holding" or bool(safe(fetch.check_hand))
        kind, what = brain_mod.hand_request(text, held, self.brain, self.markers) or (None, None)
        if kind is None:
            return False
        log(f"  hand: {kind} {what or ''} (holding {held})")
        self.brain.history.append((text, f"ACTION: {kind} -"))
        if kind == "receive":
            self.receive_from_hand(what, held)
        elif kind == "refuse":
            self.fetch_say(*what)
        elif not held:
            mouth.say(EMPTY_HAND_SAY[self.lang])
        else:
            self.fetch_finish(kind, on=what if kind == "place" else None)
        self.keep_listening()
        return True

    def receive_from_hand(self, name, held=False):
        """Take `name` (or whatever it is) from the person's hand: only when the camera sees it there
        (vision.scene.person_holds); can't tell -> ask once; then the mission receive step (hand out, waits for it
        and "okay")."""
        from tasks import fetch
        ko = fetch.OBJECTS.get(name, "물건")
        if held:
            self.fetch_say(f"My hand is full, I'm holding {fetch.held_name()}.", "손에 이미 물건을 들고 있어요.")
            return
        if self.arm_off():
            return
        no = name and skills.refusal(name)
        if no:                                         # "take my laptop": my fingers can't hold it
            self.fetch_say(*no)
            return
        try:
            from vision import scene
            sees = scene.person_holds(name)
        except Exception as e:                         # noqa: BLE001 - no camera answer: ask
            log(f"  person_holds: {e!r}")
            sees = None
        log(f"  receive {name}: the camera says {sees}")
        if sees is False:
            self.fetch_say(f"I don't see {('an ' if name[0] in 'aeiou' else 'a ') + name if name else 'anything'} in your hand.",
                           f"손에 {ko}{'이' if name and (ord(ko[-1]) - 0xAC00) % 28 else '가'} 안 보여요." if name else
                           "손에 아무것도 안 보여요.")
            return
        if sees is None:
            self.fetch_say("Do you have something for me? Hold it out, please.", "저한테 주실 게 있어요? 앞으로 내밀어 주세요.")
            answer, _ = self.hear(fetch_dialog.CONFIRM_S)
            try:
                sees = scene.person_holds(name)
            except Exception:                          # noqa: BLE001
                sees = None
            if not (sees or answer and (brain_mod.confirm_answer(answer) == "yes" or RECEIVE_OK.search(answer))):
                self.fetch_say("Okay.", "네.")
                return
        self.stay()
        try:
            fetch.run_steps([{"do": "receive", "object": name, "from_hand": True}], say=self.fetch_say)
        except fetch.FetchError as e:
            log(f"  receive refused: {e}")
            self.fetch_say(str(e), "죄송해요, 지금은 받을 수 없어요.")

    def fetch_voice(self, text):
        """While a task runs or holds: stop / give / place / "thank you" while giving. True if handled."""
        status = self.fetch_status()
        if status not in ("running", "holding"):
            return False
        from tasks import fetch
        if FETCH_STOP.search(text):
            log("  fetch: stop by voice")
            safe(fetch.stop)
            self.act("stop", "")
            self.fetch_say("Okay, I stopped.", "네, 멈췄어요.")
        elif (FETCH_THANKS.search(text) and fetch.state().get("step") == "giving") or \
                (RECEIVE_OK.search(text) and fetch.state().get("step") == "receiving: waiting for okay"):
            safe(fetch.release_now)                    # the person has taken it
        elif status == "holding" and not any(w in text.lower() for w in brain_mod.OBJECTS) and \
                (FETCH_GIVE.search(text) or FETCH_BRING_IT.search(text)):
            self.fetch_finish("give")                  # "bring it to me" while holding = hand it over
        elif (brain_mod.intent(text, self.markers) or ("",))[0] == "fetch":
            return False                               # a new fetch: fetch_request() answers it
        elif status == "holding" and FETCH_PLACE.search(text):
            self.fetch_finish("place")
        else:
            return False
        self.keep_listening()
        return True

    def object_task(self, action, target, confirm=True):
        """'pick white cup' / 'move_object cup' / 'put back|down' by voice. The skill runs in the background (up
        to a minute) while Lumi keeps listening, so "stop" ends it; the result or the reason is spoken."""
        en = self.lang == "en"
        if self.skill_busy():
            mouth.say("I'm still busy with my arm." if en else "아직 팔로 하는 일이 있어요.")
            return
        if self.arm_off():
            return
        if action == "put":
            back = target == "back"
            said = ("Okay, putting it back.", "네, 제자리에 놓을게요.") if back else ("Okay, putting it down.", "네, 내려놓을게요.")
            done = ("Done.", "다 했어요.")
            run = lambda: skills.put_down(back=back)
        else:
            words = (target or "").lower().split()           # the LLM may write "the white cup"
            colour = next((brain_mod.COLOURS[w] for w in words if w in brain_mod.COLOURS and w != words[-1]), None)
            name = next((c for c in sorted(set(brain_mod.OBJECTS.values()), key=len, reverse=True)   # "wine glass",
                         if " ".join(words).endswith(c)), None) or \
                next((brain_mod.OBJECTS[w] for w in reversed(words) if w in brain_mod.OBJECTS), None)   # "hot dog"
            if name is None:                                 # never a cup by default
                mouth.say("Which object do you mean?" if en else "어떤 물건이요?")
                return
            no = skills.refusal(name)
            if no:                                           # "pick up the bottle": why the fingers can't
                mouth.say(no[0] if en else no[1])
                return
            target = f"{colour} {name}" if colour else name
            if action == "pick":
                said, done = (f"Okay, I'll pick up the {target}.", "네, 집어 볼게요."), ("I've got it.", "잡았어요.")
                run = lambda: skills.pick(name, colour)
            else:
                said, done = (f"Okay, I'll move the {target}.", "네, 옮겨 볼게요."), ("Done.", "다 옮겼어요.")
                run = lambda: skills.move_object(name, colour)
        if confirm:
            mouth.say(said[0] if en else said[1])

        def work():
            try:
                run()
                mouth.say(done[0] if en else done[1])
            except skills.SkillError as e:
                log(f"  {action} {target}: {e}")
                mouth.say(e.args[0] if en else e.args[1] if len(e.args) > 1 else "죄송해요, 지금은 할 수 없어요.")
            except (motion.MotionError, ConnectionError, OSError) as e:
                log(f"  {action} {target} stopped: {e}")
                mouth.say("I stopped my arm." if en else "팔을 멈췄어요.")
        self.skill_thread = threading.Thread(target=work, daemon=True)
        self.skill_thread.start()
        self.keep_listening()

    def arm_pose(self, target):
        """'reach': the Cobo π program ARM_REACH_PROGRAM (record it once), only from look; 'fold': to look along the
        pose graph (arm_route, checked first, moved in the background); 'open' / 'close': the gripper. True when
        started, False when not learned, None when refused (the reason is said)."""
        if target in ("open", "close"):
            st = safe(gripper.open_ if target == "open" else gripper.close)
            log(f"  gripper {target}: {st}")
            return st is not None
        try:
            if target == "fold":
                holding = self.fetch_status() == "holding"
                seq = arm_route.plan(arm_route.HOME, holding=holding)
                threading.Thread(target=safe, args=(arm_route.move, seq, None, holding), daemon=True).start()
            else:
                arm_route.start_program(ARM_REACH_PROGRAM)
            return True
        except arm_route.RouteError as e:
            log(f"  arm {target} refused: {e.args[0]}")
            self.fetch_say(*e.args)
            return None
        except Exception as e:
            log(f"  arm {target}: {e}" + (f" (record {ARM_REACH_PROGRAM} in Cobo pi)" if target == "reach" else ""))
            return False

    # ---------- dashboard commands, trips ----------
    def poll_commands(self):
        try:
            d = json.load(open(CMD_FILE))
        except (FileNotFoundError, ValueError):
            return
        if d.get("id") == self.cmd_id:
            return
        first = self.cmd_id is None
        self.cmd_id = d.get("id")
        if first and time.time() - d.get("time", 0) > 5:      # an old command from before this start
            return
        cmd = d.get("cmd")
        log(f"dashboard: {cmd} {d.get('marker') or d.get('point') or d.get('markers') or ''}")
        if cmd == "go":
            self.start_trip(d["marker"])
        elif cmd == "go_point":
            self.start_trip(tuple(d["point"]))
        elif cmd == "route":
            self.start_trip(d["markers"], d.get("pause", 1.0))
        elif cmd == "cancel":
            if self.patrol:
                self.patrol.pause()
                self.patrol = None
            safe(agv.cancel)
        elif cmd == "fetch_pause":
            from tasks import fetch
            if fetch.pause():
                self.mission_hold, self.asked_go_on = "safety", False   # goes on only when told (dashboard or voice)
        elif cmd == "fetch_resume":
            self.resume_mission()
        elif cmd in ("fetch", "fetch_give", "fetch_place", "fetch_stop", "fetch_carry", "fetch_release", "fetch_steps"):
            from tasks import fetch                      # dashboard tasks are confirmed there: no read-back
            self.stay(voice=False)
            if cmd == "fetch":
                try:
                    fetch.start(d["task"], say=self.fetch_say)
                except fetch.FetchError as e:
                    log(f"  fetch refused: {e}")
            elif cmd == "fetch_stop":
                safe(fetch.stop)
            elif cmd == "fetch_release":
                safe(fetch.release_now)
            elif cmd == "fetch_carry":
                try:
                    fetch.carry_to(d["dest"], d.get("then"), say=self.fetch_say, on=d.get("on"))
                except fetch.FetchError as e:
                    log(f"  carry refused: {e}")
            elif cmd == "fetch_steps":
                try:
                    fetch.run_steps(d["steps"], say=self.fetch_say, sender=d.get("sender"))
                except fetch.FetchError as e:
                    log(f"  mission refused: {e}")
                    self.fetch_say(str(e), "죄송해요, 지금은 할 수 없어요.")
            else:
                self.fetch_finish(cmd[6:], d.get("on"), voice=False)
        elif cmd == "calibrate":
            self.calib_until = time.time() + CALIB_S if d.get("on", True) else 0.0
            self.calib_n = 0
            self.write_calib("collecting" if self.calib_until else "stopped")

    def start_trip(self, target, pause_s=0.0, remember=True):
        """Drive to a marker, a map point or a list of markers in order; with patrol mode on, people in the
        way are greeted on the way. `remember`: where Lumi stands now is where "come back" returns to."""
        if remember:
            from tasks import fetch
            fetch._task["trip_from"] = safe(agv.pose) or fetch._task["trip_from"]
        if self.patrol:
            self.patrol.pause()
        self.patrol = Patrol(list(target) if isinstance(target, list) else [target], once=True, pause_s=pause_s)
        self.patrol.tick(force=True)

    def come_back(self, speak=False):
        """Back to where Lumi stood before its last trip, task or mission (fetch._task["trip_from"]); with none
        remembered it asks where. `speak`: say so (the keyword rule; the LLM has said its own words)."""
        from tasks import fetch
        en = self.lang == "en"
        pose = fetch._task["trip_from"]
        if pose is None:
            log("  come back: no start remembered")
            mouth.say("Come back where?" if en else "어디로 돌아갈까요?")
            self.keep_listening()
            return False
        log(f"  come back to ({pose[0]:.2f}, {pose[1]:.2f}, {math.degrees(pose[2]):.0f} deg)")
        self.start_trip(tuple(pose), remember=False)
        if speak:
            mouth.say("Okay, I'm going back." if en else "네, 원래 자리로 돌아갈게요.")
        return True

    def publish_busy(self, what):
        """Tell the API what runs (it refuses the dashboard's hand controls then); written only on a change."""
        if what == getattr(self, "busy_now", ""):
            return
        self.busy_now = what
        try:
            tmp = BUSY_FILE + ".tmp"
            with open(tmp, "w") as f:
                json.dump({"busy": what, "time": time.time()}, f)
            os.replace(tmp, BUSY_FILE)
        except OSError:
            pass

    def doing(self):
        from tasks import follow
        if self.skill_thread is not None and self.skill_thread.is_alive():
            return "skill"
        if follow.running():
            return "follow"
        if self.patrol is not None and self.patrol.mode in ("patrol", "going_home"):
            return "drive"
        return None

    def traveling(self):
        return self.patrol is not None and self.patrol.mode != "done"

    def write_calib(self, state, result=None):
        try:
            with open(CALIB_FILE, "w") as f:
                json.dump({"state": state, "samples": self.calib_n, "until": self.calib_until,
                           "result": result, "time": time.time()}, f)
        except OSError:
            pass

    def calibrate_step(self):
        """Calibration session: each utterance of the nearest person (alone in their direction) is a sample."""
        u = self.mic.next(0.2)
        if u is None or u.seconds < 0.8:
            return
        with self.vision.lock:
            near = sorted((t for t in self.vision.tracks if t.distance <= 4.0), key=lambda t: t.distance)
        if not near or near[0].distance > CALIB_NEAR:
            log("  calibration: speech heard, but nobody within 2 m")
            return
        me = near[0]
        if any(abs(t.angle - me.angle) < CALIB_ALONE_DEG for t in near[1:]):
            log("  calibration: someone else stands in the same direction - skipped")
            return
        self.calib_n += 1
        c = doa.add_sample(u.mics, me.angle - HEAD_SIGN * self.det_yaw())
        log(f"  calibration sample {self.calib_n}: person at {me.angle:+.0f} deg, {me.distance:.1f} m"
            + (f" -> calibrated {c}" if c else ""))
        self.write_calib("calibrated" if c else "collecting", c)

    # ---------- interrupting Lumi while it talks (clip mic only) ----------
    def speak_abort(self):
        """Stop talking: the person left, someone new arrived, or the visitor interrupted ("stop", a new question)."""
        return self.interrupted() or self.barge_in()

    def barge_in(self):
        u = self.mic.next(0.0)
        if u is None:
            return False
        if not getattr(u, "during_speech", False) or u.seconds < 0.25:
            return False
        text = (ears.transcribe(u.mono) or "").strip()
        if not text or self.own_echo(text):
            return False
        from tasks import follow
        if follow.running() and follow.stop_word(text):   # following: the base stops now, "stop" is answered next
            follow.stop()
            self.pending_text = "stop"
            return True
        if not ears.understood(BARGE_IN_LOGPROB):        # unclear while Lumi talks = mostly Lumi's own voice
            log(f"  ignored while talking (unclear): {text!r}")
            return False
        if brain_mod.is_backchannel(text) and "?" not in text and not THANKS.search(text) and \
                (brain_mod.UNDERSTOOD.search(text) or not brain_mod.is_closing(text)):
            log(f"  back-channel while talking: {text!r} - go on")   # "uh huh", "I see", "그렇구나": listening
            return False
        if brain_mod.is_closing(text):
            log(f"  interrupted: {text!r} - stop talking, listen")
            return True
        if len(text.split()) >= 2 or brain_mod.WAKE_WORD_RE.search(text):
            log(f"  interrupted by a new question: {text!r}")
            self.pending_text = text
            return True
        return False

    @staticmethod
    def own_echo(text, seconds=30.0):
        """The clip mic also hears Lumi: ignore what overlaps with what it said in the last `seconds`."""
        said = set(re.findall(r"\w+", mouth.recent_speech(seconds).lower()))
        words = re.findall(r"\w+", text.lower())
        return bool(words) and sum(w in said for w in words) / len(words) >= 0.6

    # ---------- interrupts ----------
    def interrupted(self):
        """Stop listening/speaking: the person left, or a new person is waiting to be greeted."""
        if not self.vision:
            return False
        if self.current is None and time.time() < self.voice_until:
            return False
        return (self.current is not None and not self.vision.present(self.current)) or \
            self.vision.to_greet() is not None

    # ---------- behaviour ----------
    def greet(self, track):
        """A full greeting for someone new; someone known back: listen on, or a short welcome back."""
        track.greeted = True
        who, gone = self.vision.know(track)
        if gone is not None and gone < RECENT_S and who.talking:
            log(f"person #{track.id} is back after {gone:.0f} s - listening on")
            self.current = track
            self.turn_head(HEAD_SIGN * track.angle)
            return
        if self.current is None:
            self.brain.reset()
        self.current = track
        if gone is not None:
            log(f"WELCOME BACK person #{track.id} after {gone:.0f} s, at {track.distance} m, {track.angle:+.0f} deg")
            self.turn_head(HEAD_SIGN * track.angle)
            mouth.say(WELCOME_BACK[self.lang])
            return
        log(f"GREET person #{track.id} at {track.distance} m, {track.angle:+.0f} deg")
        self.turn_head(HEAD_SIGN * track.angle)          # speech only: a greeting never moves the arm
        mouth.say(GREETING)                              # cached at start: plays at once

    def warm_llm(self):
        """brain.warm in the background (markers and the task state are read there, listening starts at once)."""
        threading.Thread(target=lambda: safe(lambda: self.brain.warm(self.markers, self.now_doing()[0])), daemon=True).start()

    def talk_turn(self):
        """Listen once; answer if something was said. Returns True if the visitor spoke."""
        if self.pending_text:                              # asked while Lumi was talking
            text, self.pending_text = self.pending_text, None
            self.answer(text)
            return True
        self.warm_llm()                                    # the LLM's prompt start cached while they speak
        text, u = ears.listen(wait_s=4.0, on_start=lambda: log("  hearing speech"), abort=self.interrupted, full=True)
        if text and self.own_echo(text) and (u is None or (u.during_speech if u.source == "clip"
                                                            else len(text.split()) <= 2)):
            # Lumi heard itself: the clip mic while Lumi talked, or the room's echo of the last word on the head array
            # (muted while Lumi talks); a longer head-array sentence is the visitor ("okay go to P9" after a list with
            # p9, 2026-10-21). A clip-mic utterance begun after Lumi stopped is the visitor: "Lumi.", "Can you see
            # me?" seconds after a greeting were dropped 20 times on 2026-10-21
            log(f"  ignored own voice: {text!r}")
            text = None
        if text and NOISE_WORDS.fullmatch(text.strip()):     # a cough, a beep, "um": not worth "say it again"
            log(f"  ignored a sound: {text!r}")
            text = None
        if not text and self.closing_pending and time.time() - self.closing_pending > CLOSING_WAIT_S:
            log("  silence after a closing word - conversation over")
            self.end_conversation("okay")
            return False
        if not text or self.interrupted():
            if not self.interrupted():
                log(f"  heard nothing (mic noise {ears.last.get('noise')}, threshold {ears.last.get('threshold')}, "
                    f"loudest {ears.last.get('peak')})")
            return False
        self.who_spoke(u)
        self.answer(text)
        if self.mission_hold == "talk" and not self.asked_go_on and self.mission_running():
            self.asked_go_on = True                        # answered while halted for them: may I go on?
            self.fetch_say("Can I go on with my task?", "하던 일 계속해도 될까요?")
        return True

    def _doa_sample(self, mics, true_deg):
        try:
            c = doa.add_sample(mics, true_deg)
            if c:
                log(f"sound direction calibrated: {c}")
        finally:
            _doa_fit.release()

    def say_stuck(self):
        if self.patrol and self.patrol.stuck:
            target, self.patrol.stuck = self.patrol.stuck, None
            name = "my charging dock" if target == "home" else target
            mouth.say(f"Sorry, I can't find a way to {name}. Something may be blocking the path.")

    def who_spoke(self, u):
        """Use the sound direction: pick the visible person who spoke; meanwhile collect calibration samples."""
        if not self.vision or u is None:
            return
        yaw = self.det_yaw()
        only = self.vision.only_person()
        if only is not None and only is self.current and only.distance <= 1.6 and u.seconds >= 0.8:
            # the only person in view is the one we talk to, close by: their angle is the truth
            if _doa_fit.acquire(blocking=False):          # the refit takes seconds (a grid over all samples): in the
                threading.Thread(target=self._doa_sample, args=(u.mics, only.angle - HEAD_SIGN * yaw),   # background,
                                 daemon=True).start()       # never before the answer (it held answers ~15 s, 2026-10-21)
            return
        cal = doa.load_calib()
        if not cal["fitted"]:
            return
        ang, conf, _ = doa.estimate(u.mics, cal)
        if conf < DOA_MIN_CONF:
            return
        t = self.vision.near_angle(HEAD_SIGN * yaw + ang)
        if t is not None and t is not self.current:
            log(f"  voice from {HEAD_SIGN * yaw + ang:+.0f} deg: person #{t.id} is speaking")
            t.greeted = True
            self.current = t
            self.turn_head(HEAD_SIGN * t.angle)

    def det_yaw(self):
        """Current head yaw (deg), read from the body every 0.3 s (the torso camera does not know it)."""
        now = time.time()
        if now - self._yaw_time > 0.3:
            st = safe(head.status)
            if st:
                self._yaw, self._yaw_time = st[2], now
        return self._yaw

    def look_up(self, text, action, target, t0=None):
        """Weather or web facts -> short spoken answer (interruptible)."""
        en = self.lang == "en"
        if action == "search" and private_ask(text):        # never looked up, whoever it is about
            log("  search refused: a person's private details")
            mouth.say(PRIVATE_SAY["en" if en else "ko"])
            return
        found = {}                                         # fetched while "Let me check." is said (~1 s)
        if action == "search" and web.openai_ready():      # OpenAI's web search answers, the free search if it can't
            fetch = threading.Thread(target=lambda: found.update(said=web.openai_answer(text, self.brain.history)),
                                     daemon=True)
        else:
            fetch = threading.Thread(target=lambda: found.update(
                facts=web.weather(target) if action == "weather" else web.search(target)), daemon=True)
        fetch.start()
        mouth.say("Let me check." if en else "확인해 볼게요.")
        fetch.join()
        if found.get("said"):
            said = mouth.say_stream(iter([found["said"]]), abort=self.speak_abort)
            log(f"lumi ({time.time() - (t0 or time.time()):.1f} s, openai): {said}")
            self.brain.history.append((text, found["said"]))
            self.brain.last_lookup = text
            if self.current is None:
                self.voice_until = time.time() + VOICE_SESSION_S
            return
        if "said" in found:
            found["facts"] = web.search(target)
        facts = found.get("facts")
        log(f"  {action} {target!r}: {(facts or 'NO INTERNET')[:120]}")
        if facts is None:
            mouth.say("Sorry, I'm not connected to the internet right now, so I can't look that up."
                      if en else "죄송해요, 지금은 인터넷에 연결되어 있지 않아서 찾아볼 수 없어요.")
        else:
            asked = text
            if action == "weather":                        # misheard words ("원하는 날씨가 어때요?") made the LLM say it
                asked = f"{text} (the weather)"            # found nothing although the weather was there
            said = mouth.say_stream(self.brain.respond_from(asked, facts), abort=self.speak_abort)
            log(f"lumi ({time.time() - (t0 or time.time()):.1f} s): {said}")
        if self.current is None:
            self.voice_until = time.time() + VOICE_SESSION_S

    def keep_listening(self):
        if self.current is None:
            self.voice_until = time.time() + VOICE_SESSION_S
        self.last_activity = time.time()

    def end_conversation(self, text=None):
        """Say a goodbye that fits the conversation, forget it, and drive on if Lumi was on the way."""
        bye = self.brain.farewell(text, self.lang)
        log(f"  goodbye: {bye}")
        if text and BYE_WAVE.search(text) and self.current is not None and self.vision and self.vision.present(self.current):
            threading.Thread(target=self.wave, kwargs={"quiet": True}, daemon=True).start()   # only if safe: else no arm
        mouth.say(bye, abort=self.speak_abort)
        self.current, self.voice_until, self.closing_pending = None, 0.0, None
        self.brain.reset()
        self.turn_head(0, 0)
        if self.mission_hold == "talk":                   # halted for this talk: go on with the mission
            self.resume_mission()
        if self.traveling():
            log("  conversation over - driving on")
            self.patrol.wait_until = time.time() + 0.5

    def go_offered(self, place):
        """Drive to a place the visitor just agreed to; the conversation stays open."""
        en = self.lang == "en"
        self.brain.history.append((self.heard, f"ACTION: go_to {place}"))
        if self.base_off("go_to"):
            return
        if not self.modes.drive:
            mouth.say("Sorry, driving is switched off." if en else "죄송해요, 지금은 이동할 수 없어요.")
            return
        self.start_trip(place)
        name = brain_mod.place_said(place)
        mouth.say(f"Okay, I'm going to {name}." if en else f"네, {name}로 갈게요.")
        self.keep_listening()

    def quick_command(self, text):
        """A command the keyword rules recognise for sure: confirm with a ready phrase and act, no LLM wait."""
        rule = brain_mod.intent(text, self.markers)
        if not rule and brain_mod.place_problem(text, self.markers):
            agv.known_markers(fresh=True)               # not on the list: the map may have just changed
            rule = brain_mod.intent(text, self.markers)
            problem = not rule and brain_mod.place_problem(text, self.markers)
            if problem:
                log(f"  place: {problem[0]}")
                mouth.say(problem[0] if self.lang == "en" else problem[1])
                self.keep_listening()
                return True
        if rule and rule[0] in MOVING_ACTIONS and self.mission_running():
            self.fetch_say("Sorry, I'm on a task right now. I can help you when I've finished.",
                           "죄송해요, 지금 다른 일을 하고 있어요. 끝나면 도와드릴게요.")
            return True
        if rule and (self.base_off(*rule) or needs_arm(*rule) and self.arm_off()):
            return True
        if not rule or rule[0] not in ("go_to", "come", "follow", "quiet", "weather", "search", "move", "turn", "arm", "pick", "put",
                                       "move_object", "fetch", "look", "lift", "wave", "come_back"):
            return False
        action, target = rule
        en = self.lang == "en"
        log(f"  action {action} {target} (keyword rule)")
        if action == "search" and not_online(text):          # "is Cutshion listed on the stock market?"
            mouth.say(not_known(self.lang))
            return True
        if action in ("weather", "search"):                    # look it up at once, one LLM call for the answer
            self.look_up(text, action, target if action == "weather" else self.brain.search_query(target))
            return True
        self.brain.history.append((text, f"ACTION: {action} {target or '-'}"))
        if action == "quiet":
            mouth.say("Okay, I'll be quiet." if en else "네, 조용히 할게요.")
            self.quiet_until = time.time() + QUIET_S
            self.current, self.voice_until = None, 0.0
            self.turn_head(0, 0)
            return True
        if action in ("pick", "put", "move_object"):
            self.object_task(action, target)
            return True
        if action == "wave":                                   # a refusal is said by wave()
            threading.Thread(target=self.wave, args=(("Okay!", "네!"),), daemon=True).start()
            return True
        if action == "look":
            limited = self.act("look", "me") if target == "me" else self.look(target)
            mouth.say(LIMIT_SAY[limited][0 if en else 1] if limited else ("Okay." if en else "네."))
            return True
        if action == "lift":
            limited = self.lift(target)
            mouth.say(LIMIT_SAY["lift"][0 if en else 1] if limited else ("Okay." if en else "네."))
            return True
        if action == "fetch":
            self.fetch_request(target)
            return True
        if not self.modes.drive:
            mouth.say("Sorry, driving is switched off." if en else "죄송해요, 지금은 이동할 수 없어요.")
            return True
        if action == "come_back":
            self.come_back(speak=True)
            return True
        if action == "come":
            mouth.say("Okay, I'm coming." if en else "네, 갈게요.")
            self.come_to(self.current)
            return True
        if action == "follow":
            self.follow_me()
            return True
        if action in ("move", "turn"):
            d, n = (target.split() + ["", ""])[:2]
            if action == "turn":
                say_en = "Okay, turning around." if d == "around" else f"Okay, turning {d}."
                say_ko = "네, 뒤로 돌게요." if d == "around" else ("네, 왼쪽으로 돌게요." if d == "left" else "네, 오른쪽으로 돌게요.")
            else:
                exact = driving.amount(brain_mod._norm(text))[1]   # "about 5 centimetres" for "a tiny bit"
                say_en, say_ko = (driving.say_move(d, float(n), exact, lang) for lang in ("en", "ko"))
            if self.move_by(action, target):
                mouth.say(say_en if en else say_ko)
            return True
        if action == "arm":
            done = {"open": ("Okay, opening my hand.", "네, 손을 펼게요."), "close": ("Okay, closing my hand.", "네, 손을 쥘게요.")}
            if target in done:
                mouth.say(done[target][0] if en else done[target][1])
            ok = self.arm_pose(target)
            if ok:
                if target == "fold":
                    mouth.say("Okay." if en else "네.")
                elif target not in done:
                    mouth.say("Here you go." if en else "여기요.")
            elif ok is False:
                mouth.say("Sorry, I haven't learned that arm movement yet." if en else "죄송해요, 그 팔 동작은 아직 못 배웠어요.")
            return True
        self.start_trip(target)                           # go_to: start driving, then say so
        name = "my charging dock" if target == "home" else brain_mod.place_said(target)
        mouth.say(f"Okay, I'm going to {name}." if en else ("네, 충전소로 갈게요." if target == "home" else f"네, {name}로 갈게요."))
        self.current, self.voice_until = None, 0.0
        return True

    def answer(self, text):
        """Stream the LLM reply: act on the action line, speak sentence by sentence.
        Clear commands (go home, go to p1, come here, be quiet...) are done at once without the LLM."""
        self.lang = ears.heard_lang(mouth.lang_of(text))   # answer in the language just spoken
        brain_mod.FORCED_LANG["lang"] = self.lang
        self.heard = text                                  # what the person said, for a fetch the LLM recognised
        log(f"visitor #{self.current.id if self.current else 'voice'}: {text}  "
            f"[{ears.last_stt.get('language')}, confidence {ears.last_stt.get('logprob')}]")
        t = time.time()
        self.closing_pending = None
        if self.follow_stop(text):                         # before anything else, also when heard unclearly
            return
        last = self.brain.history[-1][1] if self.brain.history else ""
        if not ears.understood() and ears.heard_clearly() and own_command(text, last):
            self.lang = mouth.lang_of(text)                # "Can you sing song?" tagged Korean: the words decide
            brain_mod.FORCED_LANG["lang"] = self.lang
            log(f"  heard as {self.lang} (whisper said {ears.last_stt.get('language')})")
        elif not ears.understood():                        # garbled or another language: ask, do not guess
            log("  not understood - asking again")
            mouth.say("Sorry, I didn't catch that. Could you say it again?" if self.lang == "en"
                      else "죄송해요, 잘 못 들었어요. 다시 말씀해 주시겠어요?")
            self.keep_listening()
            return
        if FOREIGN_SCRIPT.search(text):                    # Cyrillic, Chinese, Japanese: not acted on
            mouth.say("Sorry, I only understand English and Korean." if self.lang == "en" else "죄송해요, 영어와 한국어만 이해해요.")
            self.keep_listening()
            return
        fixed = brain_mod.self_correct(text, self.markers)   # "go to start, no, end", "컵 집어, 아니 병"
        if fixed != text:
            log(f"  corrected in the sentence: {fixed!r}")
            if not fixed:                                  # None: not read for sure, asked; "": taken back ("never mind")
                mouth.say(FIX_SAY[fixed is None][self.lang != "en"])
                self.keep_listening()
                return
            text = fixed
        if self.voice_setting(text, last):                 # "speak louder", "천천히 말해", then "조금 더": before drive "again"
            return
        if self.fixed_answer(text, last):                  # "what can you do?" then "yes", the songs, after a song "again"
            return
        if self.drive_words(text):                         # "a bit faster" (also on the move running now), "again"
            return
        if self.mission_running() and self.mission_talk(text):   # on a mission: halt for them, refuse other tasks
            return
        if NAME_ONLY.match(text):                           # just "Lumi?": they want attention
            mouth.say("Yes?" if self.lang == "en" else "네?")
            self.keep_listening()
            return
        if stop_order(text, self.markers):
            self.stop_all()                                # "stop", "stop, where are you going?": stop first, always
            return
        seen = seeing.answer(text, self.lang, slow_line=mouth.say)   # "do you see a cup?", "what am I holding?"
        if seen:
            log(f"  seeing: {seen}")
            self.brain.history.append((text, f"ACTION: none -\n{seen}"))   # "and you?" / "why?" next has the turn
            mouth.say(seen)
            self.keep_listening()
            return
        if status_question(text):                         # what am I doing / where am I going
            en, ko = self.now_doing()
            log(f"  status: {en}")
            mouth.say(en if self.lang == "en" else ko)
            self.keep_listening()
            return
        if self.hand_command(text):                        # "take this from me", "give it to her", "put it there"
            return
        if self.mission_request(text):                     # several steps: before give / place while holding
            return
        if self.fetch_voice(text):                         # before the closing words: "thank you" while giving
            return
        place = consent_place(text, self.brain, self.markers)
        if place:                                          # "p3로 갈 수 있어요?" ... "그럼 가 보세요."
            self.go_offered(place)
            return
        if self.fetch_status() not in ("running", "holding") and empty_hand_request(text):   # nothing held
            mouth.say(EMPTY_HAND_SAY[self.lang])
            self.keep_listening()
            return
        fate = talk_fate(text)
        if fate == "end":
            self.end_conversation(text)                    # "okay, bye", "thanks, that's all", "수고하세요": done
            return
        if fate == "wait":                                 # "okay", "thank you", "네" alone: maybe done, maybe not
            if mouth.recent_speech().rstrip().endswith("?"):   # "Yes?" / "say it again?" -> "okay": a reply, go on
                log("  a short yes to my question - listening")
            else:                                          # after an answer: taken as heard; silence then ends
                if THANKS.search(text):
                    mouth.say(random.choice(WELCOME[self.lang]), abort=self.speak_abort)
                log("  closing word - waiting a moment")
                self.closing_pending = time.time()
            self.keep_listening()
            return
        if sing.asked(text, last):                         # "sing a song", "노래 불러 줘", after a song "another one"
            self.sing_song(text)
            return
        if self.quick_command(text):
            log(f"  done at once ({time.time() - t:.1f} s)")
            return
        if self.brain.is_lookup_follow_up(text):           # "tell me more" about something looked up just now
            self.look_up(text, "search", self.brain.search_query(text), t)
            return
        about, repeating = self.brain.topic(text), self.brain.again(text)
        gen = self.brain.respond_stream(text, self.markers, now=self.now_doing()[0] + seeing.facts_for(text))
        head_ = next(gen)
        log(f"  action {head_['action']} {head_['target']} ({time.time() - t:.1f} s)")
        if self.base_off(head_["action"], head_["target"]) or \
                needs_arm(head_["action"], head_["target"]) and self.arm_off():   # the model's "Okay" is not said
            gen.close()
            return
        if head_["action"] == "come":
            gen.close()
            mouth.say("Okay, I'm coming." if self.lang == "en" else "네, 갈게요.")
            self.come_to(self.current)
            return
        if head_["action"] == "follow":
            gen.close()
            self.follow_me()
            return
        if head_["action"] == "search" and not_online(about):
            gen.close()                                    # about Cutshion or this place: the notes say it or nobody does
            log("  search refused: a company or venue question")
            mouth.say(not_known(self.lang))
            return
        if head_["action"] in ("weather", "search"):
            gen.close()
            target = head_["target"] if head_["action"] == "weather" else self.brain.search_query(head_["target"])
            self.look_up(text, head_["action"], target, t)
            return
        if head_["action"] == "sing":                     # "can you sing?" ... "yes": a real song, not lines
            gen.close()
            self.sing_song(text)
            return
        if head_["action"] == "quiet":
            gen.close()
            mouth.say("Okay, I'll be quiet." if self.lang == "en" else "네, 조용히 할게요.")
            log(f"  quiet for {QUIET_S / 60:.0f} min (no greetings; \"Hi Lumi\" still works)")
            self.quiet_until = time.time() + QUIET_S
            self.current, self.voice_until = None, 0.0
            self.turn_head(0, 0)
            return
        if head_["action"] in ("receive", "give", "place"):  # the model read a hand request the rules missed
            gen.close()
            from tasks import fetch
            held = self.fetch_status() == "holding" or bool(safe(fetch.check_hand))
            self.brain.history.append((text, f"ACTION: {head_['action']} -"))
            if head_["action"] == "receive":
                self.receive_from_hand(brain_mod._mentions(text, self.markers).get("object"), held)
            elif not held:
                mouth.say(EMPTY_HAND_SAY[self.lang])
            else:
                self.fetch_finish(head_["action"], on=brain_mod.place_on(text) if head_["action"] == "place" else None)
            self.keep_listening()
            return
        if head_["action"] not in ("none", "end"):
            self.act(head_["action"], head_["target"])
        first = next(gen, None)
        log(f"  first sentence after {time.time() - t:.1f} s")
        if head_["action"] in ("none", "sing") and not repeating and look_up_unsure(about, first, text):
            gen.close()                                    # the model does not know: look it up instead
            log(f"  not sure ({first[:60]!r}) - looking it up")
            self.look_up(text, "search", self.brain.search_terms(text), t)
            return
        said = mouth.say_stream(itertools.chain([first] if first else [], gen), abort=self.speak_abort)
        log(f"lumi ({time.time() - t:.1f} s, voice after {mouth.last_voice - t:.1f} s): {said}")
        if head_["action"] in ("end", "go_to"):
            self.current, self.voice_until = None, 0.0     # stay quiet with this person until a new visit
        elif self.current is None:
            self.voice_until = time.time() + VOICE_SESSION_S

    # ---------- wake word ----------
    def check_wake(self):
        """Idle or driving: is someone calling "Lumi" / "Hi Lumi" / "Hey Lumi" (or just "Hi" / "Hey")? Handles it."""
        u = self.mic.next(0.0)
        if u is None or not (0.3 <= u.seconds <= WAKE_MAX_S) or getattr(u, "during_speech", False):
            return False
        text = ears.transcribe(u.mono)
        m = WAKE.search(text or "")
        if not m and HELLO_ONLY.match(text or ""):          # a plain "Hi!" / "Hey" said on its own
            m = HELLO_ONLY.match(text)
        if not m:
            if text:
                log(f"  heard {text!r} (no wake word)")
            return False
        rest = text[m.end():].strip(" ,.!?")
        lang = ears.heard_lang("ko" if re.search(r"[가-힣]", text) else "en")
        self.lang = lang
        cal = doa.load_calib()
        ang, conf, raw = doa.estimate(u.mics, cal)
        trusted = cal["fitted"] and conf >= DOA_MIN_CONF
        robot_angle = HEAD_SIGN * self.det_yaw() + ang
        self.voice_angle, self.voice_trusted = robot_angle, trusted
        log(f"WAKE {text!r}: voice at {robot_angle:+.0f} deg (confidence {conf:.2f}, "
            f"{'calibrated' if cal['fitted'] else 'NOT calibrated'})")
        if self.traveling():                                  # someone calls while driving: stop for them
            log("  called while driving - stop and talk, then drive on")
            self.patrol.pause()
        self.quiet_until = 0.0
        self.brain.reset()
        self.closing_pending = None
        command = rest if len(rest) > 2 else ""
        target = self.find_caller(robot_angle, trusted)
        if target is not None:
            target.greeted = True
            self.current = target
            self.turn_head(HEAD_SIGN * target.angle)
        if not command:                                       # just "Hi Lumi": a short answer, then listen
            mouth.say(WAKE_REPLY[lang])
        self.voice_until = time.time() + VOICE_SESSION_S
        self.last_activity, self.prompts = time.time(), 0
        if command:                                           # "Hi Lumi, go home": do it at once, no greeting
            self.answer(command)
        return True

    def find_caller(self, robot_angle, trusted):
        """The visible person who called (voice direction + camera). If the voice comes from outside what the
        camera can see (the head camera also by turning the head), turn the base toward it first, then look for
        the person in front."""
        if not self.vision:
            return None
        if not trusted:
            return self.vision.only_person() or self.vision.near_angle(0.0, 30)
        t = self.vision.near_angle(robot_angle, SPEAKER_MATCH_DEG)
        if t is not None:
            return t
        view = CAMERA_HALF_FOV + (head.YAW_LIMIT if self.vision.camera == "head" else 0.0)
        if abs(robot_angle) > view and self.modes.drive and self.modes.patrol:
            log(f"  caller outside the camera ({robot_angle:+.0f} deg): turning toward the voice")
            self.turn_head(0)
            safe(agv.turn_by, math.radians(robot_angle))
            t0 = time.time()
            time.sleep(0.6)
            while time.time() - t0 < 8 and (safe(agv.status, default={}) or {}).get("move_status") == "running":
                time.sleep(0.2)
            time.sleep(0.8)                                   # let detection catch up
            self.voice_angle = 0.0
            return self.vision.near_angle(0.0, 35) or self.vision.only_person()
        self.turn_head(HEAD_SIGN * max(-head.YAW_LIMIT, min(head.YAW_LIMIT, robot_angle)))
        if self.vision.camera == "head":                      # the camera turned with the head: look again
            time.sleep(1.5)
            return self.vision.near_angle(robot_angle)
        return None

    def look_toward(self, robot_angle):
        """Turn the head toward a waist-frame angle; turn the base too if it is outside the head's range."""
        if abs(robot_angle) <= head.YAW_LIMIT:
            self.turn_head(HEAD_SIGN * robot_angle)
        elif self.modes.drive and self.modes.patrol:
            log(f"  voice behind ({robot_angle:+.0f} deg): turning the base")
            self.turn_head(0)
            safe(agv.turn_by, math.radians(robot_angle))
            t = time.time()
            time.sleep(0.5)
            while time.time() - t < 8 and (safe(agv.status, default={}) or {}).get("move_status") == "running":
                time.sleep(0.2)

    # ---------- come here ----------
    def come_to(self, track):
        """Drive to the person (a visible track) and stop about COME_STOP in front of them."""
        if not self.modes.drive:
            mouth.say("Sorry, driving is switched off.")
            return
        if track is None or not self.vision or not self.vision.present(track):
            track = self.find_caller(self.voice_angle, self.voice_trusted)   # look where the voice came from
            if track is None:
                mouth.say("I can't see you. Could you wave or step in front of me?" if self.lang == "en"
                          else "보이지 않아요. 손을 흔들거나 제 앞으로 와 주시겠어요?")
                return
            self.current = track
            track.greeted = True
        robot = safe(agv.pose)
        waist = (safe(head.status, default=[0, 0, 0, 0]) or [0, 0, 0, 0])[1]
        if robot is None:
            return
        px, py = nav.person_on_map(track.distance, track.angle, waist, robot)
        goal = safe(nav.approach, px, py, robot)
        log(f"COME to person #{track.id} at {track.distance:.2f} m {track.angle:+.0f} deg -> map ({px:.2f}, {py:.2f}),"
            f" goal {goal}")
        if goal == "close":
            mouth.say("I'm right here.")
            return
        if goal is None:
            mouth.say("Sorry, I can't get closer from here.")
            return
        ok, msg = safe(agv.go_point, *goal, default=(False, "error"))
        if not ok:
            log(f"  base refused: {msg}")
            mouth.say("Sorry, I can't get closer from here.")
            return
        t, last_look = time.time(), 0.0
        time.sleep(0.5)
        while time.time() - t < COME_TIMEOUT:
            st = safe(agv.status, default={}) or {}
            if st.get("move_status") != "running":
                log(f"  arrived ({st.get('move_status')})")
                break
            if self.vision.present(track):
                if track.distance <= COME_STOP:
                    log(f"  person #{track.id} is {track.distance:.2f} m away - stop")
                    safe(agv.cancel)
                    break
                if time.time() - last_look > 1.0:             # keep looking at them while driving
                    self.turn_head(HEAD_SIGN * track.angle)
                    last_look = time.time()
            time.sleep(0.2)
        else:
            safe(agv.cancel)
        if self.vision.present(track):
            self.turn_head(HEAD_SIGN * track.angle)
        self.last_activity = time.time()

    # ---------- follow me (tasks/follow.py) ----------
    def follow_me(self):
        """Lock onto the person who said "follow me" (the track talking, else the one where the voice came from)
        and follow them in the background until a stop word, they are lost, or something is in the way."""
        from tasks import follow
        en = self.lang == "en"
        if not self.modes.drive:
            mouth.say("Sorry, driving is switched off." if en else "죄송해요, 지금은 이동할 수 없어요.")
            return
        if self.skill_busy():
            self.fetch_say("Sorry, I'm on a task right now.", "죄송해요, 지금 다른 일을 하고 있어요.")
            return
        track = self.current if self.current is not None and self.vision and self.vision.present(self.current) else None
        if track is None and self.vision:
            track = self.find_caller(self.voice_angle, self.voice_trusted)
        if track is None:
            mouth.say("I can't see you. Could you step in front of me?" if en else "보이지 않아요. 제 앞으로 와 주시겠어요?")
            self.keep_listening()
            return
        why = follow.ready()                               # the arm off, on the charger: said, not started
        if why:
            log(f"FOLLOW refused: {why[0]}")
            self.fetch_say(*why)
            return
        self.current, track.greeted = track, True
        log(f"FOLLOW person #{track.id} at {track.distance:.2f} m {track.angle:+.0f} deg")
        mouth.say("Okay, I'll follow you. Say stop when you want me to stay." if en
                  else "네, 따라갈게요. 멈추려면 멈춰라고 하세요.")
        follow.start(lambda: self.vision.follow_view(track), say=self.fetch_say, people=self.vision.follow_views)
        self.keep_listening()

    def follow_stop(self, text):
        """While following: a stop word ("stop", "wait", "that's enough", "거기 있어") stops everything. True if so."""
        from tasks import follow
        if not (follow.running() and follow.stop_word(text)):
            return False
        log(f"  follow: stop word {text!r}")
        follow.stop()
        self.stop_all()
        return True

    def run_camera(self):
        self.last_activity, self.prompts = time.time(), 0
        self.alive = time.time()
        threading.Thread(target=self.watchdog, daemon=True).start()
        while True:
            self.alive = time.time()
            try:
                self.step()
            except Exception as e:                     # never stop the robot program on one error
                log(f"error: {e!r}")
                time.sleep(1)

    def step(self):
        """One pass of the camera behaviour (see the module docstring)."""
        self.modes.refresh()
        self.poll_commands()
        self.publish_busy(self.doing())
        if self.patrol and self.patrol.mode == "done" and not self.a.patrol:
            self.patrol = None                             # a dashboard / voice trip has arrived
        moving = self.traveling()
        # on the way only people in the path, close by; standing: everyone in the greeting zone
        self.vision.near_max, self.vision.corridor = (PATROL_NEAR_MAX, PATH_HALF_WIDTH) if moving else (NEAR_MAX, None)
        if not self.vision.pinned:                         # driving: the path ahead; standing: the people
            self.vision.prefer = "torso" if moving else "head"
        if time.time() < self.calib_until:
            self.vision.det.focus_angle = None
            self.calibrate_step()
            return
        if self.calib_until:
            self.calib_until = 0.0
            self.write_calib("finished")
        from tasks import follow
        following = follow.running()                       # no greetings (the head would turn away), keep listening
        greet_now = (self.modes.patrol if moving else self.modes.greeter) and time.time() > self.quiet_until \
            and not following
        self.note_talk()
        candidate = self.vision.to_greet() if greet_now else None
        focus = self.current or candidate
        self.vision.det.focus_angle = focus.angle if focus else None    # drawn red in the dashboard
        new = candidate
        if new:                                            # a new visitor (first or second person)
            if self.patrol:
                self.patrol.pause()
            self.greet(new)
            self.last_activity, self.prompts = time.time(), 0
            return

        if self.current and not self.vision.present(self.current):
            log(f"person #{self.current.id} left - stop talking")
            self.current = self.vision.nearest_greeted()   # someone else still here?
            if self.current:
                self.turn_head(HEAD_SIGN * self.current.angle)
            else:
                # often still there, out of the frame (beside the arm): keep listening without the wake word
                # for a while, like a conversation started by voice
                self.turn_head(0, 0)
                self.voice_until = time.time() + VOICE_SESSION_S
            self.last_activity, self.prompts = time.time(), 0
            return

        if self.current is None:
            if self.patrol and self.patrol.moving:         # a trip runs while talking or holding: still notice it is
                self.patrol.tick()                         # stuck or there (a stale "holding" hid a stuck trip, 2026-10-21)
                self.say_stuck()
            if following:
                self.voice_until = max(self.voice_until, time.time() + VOICE_SESSION_S)
            if self.fetch_status() in ("running", "holding"):   # keep listening for stop / give / place / thanks
                self.voice_until = max(self.voice_until, time.time() + VOICE_SESSION_S)
                self.mission_wait()
            if time.time() < self.voice_until:            # talking with someone we only heard
                if self.talk_turn():
                    self.voice_until = max(self.voice_until, time.time() + VOICE_SESSION_S)
                return
            if self.voice_until:
                log("voice conversation over (silence)")
                self.end_conversation(None)
            if self.check_wake():                          # "Hi Lumi" works in every mode
                return
            if self.patrol:
                self.patrol.tick()
                self.say_stuck()
            time.sleep(0.05)
            return

        if self.traveling() and time.time() - self.last_activity > PATROL_WAIT_S:
            log(f"no answer for {PATROL_WAIT_S:.0f} s - goodbye, drive on")
            self.end_conversation(None)
            return

        if self.talk_turn():
            self.last_activity, self.prompts = time.time(), 0
        elif (not self.interrupted() and time.time() - self.last_activity > PROMPT_S and self.prompts < MAX_PROMPTS):
            log(f"silent for {PROMPT_S:.0f} s - prompt")
            mouth.say(PROMPT[self.lang], abort=self.interrupted)
            self.last_activity, self.prompts = time.time(), self.prompts + 1

    def note_talk(self):
        """Remember whom Lumi talks with and how the talk ended: with them in view (a goodbye: closed) or after they
        left (open: back within RECENT_S, Lumi listens on without a word)."""
        if self.current is not None:
            if self.current.person is None:
                self.vision.know(self.current)
            self.talked_with = self.current.person
            self.talked_with.talking = True
        elif getattr(self, "talked_with", None) and time.time() >= self.voice_until:
            self.talked_with.talking = time.time() - self.talked_with.last_seen > LOST_S
            self.talked_with = None

    def watchdog(self):
        """If the main loop is stuck for STUCK_S, write every thread's stack to the log (to find the cause)."""
        reported = 0.0
        while True:
            time.sleep(5)
            if time.time() - self.alive > STUCK_S and self.alive != reported:
                reported = self.alive
                buf = io.StringIO()
                frames = sys._current_frames()
                for th in threading.enumerate():
                    f = frames.get(th.ident)
                    if f is not None:
                        buf.write(f"--- thread {th.name}\n" + "".join(traceback.format_stack(f)[-6:]))
                log(f"MAIN LOOP STUCK for {time.time() - self.alive:.0f} s:\n{buf.getvalue()}")

    def run_desk(self):
        while True:
            input("\nPress Enter to start a conversation (Ctrl+C to quit)...")
            self.brain.reset()
            self.current = None
            mouth.say(GREETING)
            silent = 0
            while silent < 2:
                if self.talk_turn():
                    silent = 0
                else:
                    silent += 1
                    if silent == 1:
                        mouth.say(PROMPT[self.lang])

    def run(self):
        log("loading speech models...")
        threading.Thread(target=brain_mod.warm_up, daemon=True).start()
        threading.Thread(target=seeing.warm_up, daemon=True).start()
        web.keep_weather_fresh()
        ears.ensure_stt_server()
        mouth.warm_up()
        cal = doa.load_calib()
        log("sound direction " + (f"calibrated ({cal})" if cal["fitted"] else "not calibrated yet: it learns while "
                                  "talking with one person in view"))
        if self.vision:
            self.vision.start()
        self.warm_llm()
        log("ready")
        self.run_camera() if self.vision else self.run_desk()


def stop_order(text, markers):
    """"stop", "freeze", "멈춰": stop everything at once. Not "stop talking" and not a question about the stop button."""
    asked = bool(brain_mod.STOP_ASK.match(brain_mod.CALLING.sub("", text)))   # "can you stop?", "멈출 수 있어?": stop
    return bool(FETCH_STOP.search(text) or asked) and (brain_mod.intent(text, markers) or ("",))[0] not in ("quiet", "look") \
        and not brain_mod.STOP_TALK.search(text) and ("?" not in text or asked)


def own_command(text, last=""):
    """One of the fixed commands answered by rule (a song, the songs, the voice, what Lumi can do): taken also when
    whisper tagged the sentence with the other language."""
    return bool(sing.asked(text, last) or sing.list_asked(text) or voice_words.read(text, last) or abilities.answer(text, "en", last))


def status_question(text):
    """"What are you doing?", "where are you going?": answered from the task state ("들고 있는 거 줘" is a request)."""
    return bool(STATUS_Q.search(text)) and not NOT_STATUS_NOW.search(text) and not EMPTY_HAND.search(text)


def says_goodbye(text):
    """"thank you for your time", "okay, bye", "수고하세요": the talk is over (not "thanks, but where is...?").
    "thank you", "got it, thanks", "네 감사합니다" alone are not: often only "heard you" (talk_fate waits)."""
    if brain_mod.is_closing(text) and not DONE_WORDS.search(text) and not FAREWELL_WORDS.search(THANKS.sub(" ", text)):
        return False
    return bool(FAREWELL_ONLY.match(text) or FAREWELL_WORDS.search(text) and not ASKS_MORE.search(text)
                and len(text.split()) <= 8 and not brain_mod.intent(text) and not brain_mod.hand_request(text, False)
                and not COMMAND_START.search(brain_mod.CALLING.sub("", text)))   # "grab the cup, thanks": an order


def talk_fate(text):
    """What short words do to the talk: "end" (a real closing: "okay, bye", "that's it, thank you", "안녕히 계세요"),
    "wait" ("okay", "thank you", "네", "감사합니다" alone: ends only after CLOSING_WAIT_S of silence) or "talk"
    (anything else; "I see", "got it", "그렇구나", "알겠어요" are understanding, "I see?", "그래요?" a check: answered)."""
    if says_goodbye(text):
        return "end"
    if brain_mod.is_closing(text) and (THANKS.search(text) or not brain_mod.UNDERSTOOD.search(text)):
        return "wait"
    return "talk"


NOT_A_STEP = re.compile(r"^\W*(?:(?:please|and|then|also)\s+)*(?:dance|jump|fly|swim|climb|sit(?: down)?|sleep|cook|draw|"
                        r"sing|clap|spin|bow|kneel|do a (?:dance|flip|trick)|tell|ask|say|show|call|find|look for|search|"
                        r"bring|take|give|hand|put|carry|deliver)\b|.*(?:춤|점프|날아|수영|박수)", re.I)   # a part not read: asked


def read_mission(text, markers):
    """(steps, unread, by) when the words are a command of several steps (unread: parts not understood), else None.
    A single move / turn / arm / go, or words that are only partly a plain command, stay with the other paths."""
    from assistant import steps
    got, unread, by = steps.read(text, markers, llm=False)
    rule = brain_mod.intent(text, markers) or ("", "")
    if unread and rule[0] == "look" and rule[1].endswith(f" {brain_mod.HEAD_YAW[1]:g}"):
        return None                                # "turn around and look": the head looks behind (brain.BEHIND_WORDS)
    if got and all(s["do"] == "say" for s in got):
        return None                                # "say hello in Korean", "say again?": talk, not a task
    if unread and got and ({s["do"] for s in got} & steps.MISSION_ONLY or steps.is_mission(got)):
        got, unread, by = steps.read(text, markers)          # clearly several steps: the LLM may read it
    elif unread and got and any((brain_mod.intent(u, markers) or ("",))[0] not in ("", "weather", "search", "fetch")
                                or NOT_A_STEP.match(u) for u in unread):
        return got, unread, by                     # "go to the stage and wave": no task step, asked, never half done
    elif unread:
        return None                                # "come here, I need help": the old paths (rules, the LLM) answer it
    if not got:
        return None
    plain = not steps.is_mission(got) and (len(got) == 1 or (brain_mod.intent(text, markers) or ("",))[0] == "fetch")
    if not unread and (plain or (len(got) == 1 and got[0]["do"] in ("move", "turn", "arm"))):   # "take the cup and put
        return None                                                     # it on the chair": two steps, not a pick
    return got, unread, by


def not_online(text):
    """Questions about Cutshion or this event / building: the notes say it or nobody does, never the internet."""
    return bool(COMPANY_Q.search(text) or VENUE_ONLY.search(text) or VENUE_Q.search(text) and not (OUTSIDE.search(text) or
                                                                                            OUTSIDE_NAME.search(text)))


PRIVATE_ASK = re.compile(r"\bhome address|\bwhere (does|do|did) (my|our|his|her|their|this|that) .{0,40}\blives?\b|"
                         r"\b(phone|mobile|cell) number of (?!the |a )|\b(email|e-mail) (address )?of (my|our|his|her)\b|"
                         r"(집|자택) ?주소|(옆집|이웃|동료|친구|선생님|사람).{0,8}(전화번호|연락처|주소|어디 살)", re.I)
PRIVATE_SAY = {"en": "Sorry, I can't look up a person's private details.",
               "ko": "죄송해요, 개인 정보는 찾아 드릴 수 없어요."}


def private_ask(text):
    """A request for someone's home address, phone number or where they live: declined before any lookup."""
    return bool(PRIVATE_ASK.search(text or ""))


def look_up_unsure(about, first, text=None):
    """The model's first sentence says it does not know: look it up online? Not when the question (about: the words
    with the question before a short follow-up) is about Lumi, Cutshion or this place, nor when the reply already
    points to a staff member, nor for an order ("throw the cup", "go to the kitchen"). text: the words just said."""
    if not UNSURE_LOOKUP or not first or not brain_mod.UNSURE.search(first) or \
            re.search(r"staff|cutshion|직원|쿳션|문의", first, re.I):
        return False
    return not (not_online(about) or REQUEST.search(about) or COMMAND_START.search(text or about) or
                ABOUT_LUMI.search(ASK_PREFIX.sub("", about)))


CONSENT = re.compile(r"^\s*(?:(?:ok(?:ay)?|alright|yes|yeah|sure|then|so|good)[\s,.!]+)*(?:go ahead|go|yes,? go|please do|"
                     r"do it|go on then|off you go|then go|please go)[\s.!]*$|"
                     r"^\s*(?:그럼|네|응|그래|좋아요?)?[\s,.]*(?:가 ?보세요|가 ?봐요?|가세요|가 ?주세요|가 ?줘요?|그렇게 해 ?(?:줘|주세요|요)?|"
                     r"가 ?봐 ?주세요)[\s.!~]*$", re.I)   # yes to "shall I go to p3?" / "p3로 갈 수 있어요?"


def consent_place(text, brain, markers):
    """The marker of the last exchange (exactly one named in the question or the answer) when the words now are a
    plain yes / "go ahead" / "그럼 가 보세요": Lumi goes there and the talk goes on (owner, 2026-10-19)."""
    if not brain.history or not CONSENT.match(text or ""):
        return None
    asked, answer = brain.history[-1]
    offer = (re.split(r"(?<=[.!])\s+", answer.strip()) or [""])[-1]      # Lumi's own "shall I go to p3?"
    last = asked if any(brain_mod.named_place(asked, m, markers) for m in markers) else (offer if "?" in offer else "")
    named = {m for m in markers if brain_mod.named_place(last, m, markers)}
    if named == {"home", "dock2"}:
        return None
    return named.pop() if len(named) == 1 else None


def empty_hand_request(text):
    """"hand it over", "테이블에 놔" with nothing held (and no object named): Lumi says its hand is empty."""
    return bool(EMPTY_HAND.search(text)) and not any(w in text.lower() for w in brain_mod.OBJECTS)


def claimed_name(text):
    """"I'm James" / "James here" / "제가 제임스예요" -> "james" / "제임스", or None."""
    for m in I_AM.finditer(text or ""):
        n = next((g for g in m.groups() if g), "").lower()
        if n and n not in NOT_NAMES and n not in brain_mod.OBJECTS and n not in brain_mod.COLOURS and \
                not re.search(r"(ing|ed)$", n):
            return n
    return None


def at_place(text, markers):
    """"I'm at p5 now" / "지금 p5에 있어" -> "p5", else None."""
    m = re.search(r"\bi'?m (?:now )?(?:at|in|by) (\S+?)(?: now)?\b|(?:지금 )?(\S+?)에 있어", text or "", re.I)
    if not m:
        return None
    from assistant import steps
    to = steps._places(m.group(1) or m.group(2), markers)
    return to[0] if to and len(to) == 1 else None


def lumi_question(text):
    return bool(re.search(r"\?|\b(what|where|who|why|how|when|which|can you|do you|are you|is it)\b|뭐|어디|누구|왜|어떻게|언제|"
                          r"나요|까요|니\??$", text, re.I))


def same_name(a, b):
    a, b = (re.sub(r"(씨|님)$", "", x.strip().lower()) for x in (a, b))
    return a == b


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-camera", action="store_true")
    ap.add_argument("--no-arm", action="store_true")
    ap.add_argument("--no-drive", action="store_true")
    # torso camera by default: the head camera shares a USB 2 hub with the speaker and drops out while Lumi talks
    ap.add_argument("--camera", default=None, choices=camview.CAMERAS,
                    help="pin one camera (default: head standing, torso driving)")
    ap.add_argument("--patrol", help="comma-separated markers to drive between, e.g. a,b")
    ap.add_argument("--once", action="store_true", help="drive the --patrol route once instead of looping")
    ap.add_argument("--pause", type=float, default=PAUSE_AT_END, help="seconds to wait at each marker")
    try:
        Lumi(ap.parse_args()).run()
    except KeyboardInterrupt:
        print("\nbye")
        os._exit(0)          # leave at once; the camera thread would otherwise abort noisily
