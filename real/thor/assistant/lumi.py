"""Lumi voice assistant: greets every visitor, talks with them and obeys voice commands.

    python assistant/lumi.py                 # full: camera, greetings, conversation, commands
    python assistant/lumi.py --no-camera     # no camera: press Enter to start a conversation (desk testing)
    python assistant/lumi.py --no-arm        # no waving
    python assistant/lumi.py --patrol a,b    # walk between markers in a loop; stop for people in the way, talk, go on
    python assistant/lumi.py --patrol p1,p2,final,p10,home --once --pause 0.5   # drive the route once, end at the dock

Behaviour
- Every person the camera sees gets a track (an ID followed from frame to frame).
- Lumi speaks only when called: a wake word ("Lumi", "Hi Lumi", "Hi", "How are you", "루미야", "안녕하세요", "하이")
  or a wave (a hand up, facing it) from someone in the greeting zone. Someone who only stands there or walks past is
  not greeted, and nobody is greeted during a task or a drive. Greeted: the head turns to them, "Hi, I'm Lumi..."
  (a greeting never moves the arm). The talk then goes on without the wake word until a goodbye or TALK_IDLE_S of
  silence (ended without a word); then a call is needed again.
- An answer is never cut for someone new: a call while Lumi talks is answered after it, turned to the caller.
- When the person disappears from the camera (LOST_S), listening and speaking stop at once.
- Voice commands (English / Korean): go to <marker>, go home, look left/right/up/down/center, wave, stop. The arm
  waves only when asked, with an empty hand, from `look`, along a checked route (manipulation/wave.py).
- Patrol (--patrol): drive marker to marker in a loop. People are never greeted while driving (the base's own
  sensors stop it for obstacles); a wake word stops it and Lumi talks.
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
           head, lift, arm and gripper within reach, wave, the waist turned to a person for "reach out to me") and
           refuses a drive, a base turn or a waist turn (base_off says BASE_OFF_SAY; a task runs with fetch.stay_put). Tasks from the dashboard's Command box obey
           the same (api/server.py _switches). The dashboard's own buttons and "stop" work either way.
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
from assistant import detour
from assistant import abilities
from assistant import battery
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
from assistant import memory
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
TALK_IDLE_S = 20.0                 # s of silence with the visitor in view that end a conversation: the next talk needs
                                   # the wake word or a wave again (owner, 2026-10-23)
MAX_PROMPTS = 0                    # Lumi never speaks into a silence by itself: the greeting asked already (owner,
                                   # 2026-10-22: "How can I help you?" twice to someone standing silent)
TOO_CLOSE = 0.45                   # m, a running wave is stopped
MATCH_DEG = 12.0                   # a detection belongs to the track with the closest angle within this ...
MATCH_DEG_PER_M = 10.0             # ... where each m of distance difference counts as this many deg: two people at
                                   # about the same angle (one passing the followed person) keep their own tracks (estimate)
OCCLUSION_DROP = 0.3               # m; while the arm moves, a sudden drop in distance is the arm in front of
                                   # the person, not the person moving: ignore it
CLOSE_BOX = 0.85                   # a person is really closer than TOO_CLOSE only if the box is this tall (frame part)
HEAD_SIGN = 1.0                    # +image angle -> +head yaw (checked: + = robot's left)
LOOK = {"left": (40, None), "right": (-40, None), "center": (0, head.HEAD_REST_PITCH), "up": (None, 20), "down": (None, -5)}
# ^ yaw/pitch in degrees for "look" commands: +yaw = left, +pitch = up (checked on the dashboard 2026-10-12)
WAKE_UP_EN = r"wake up|wakey wakey|time to wake up"
WAKE_UP_KO = r"(?:일어나|깨어나)(?:요|세요|십시오|라|봐|봐요)?|기상"
WAKE = re.compile(rf"\b(hi|hey|hello|okay|ok|hai|high|{WAKE_UP_EN})?[\s,.!]*(lumi|lumia|loomi|loomy|lumie|lumee|lumy|lummy|lummi|looney|lu-mi|rumi|rumy|roomie)\b"
                  rf"(?:[\s,.!]*(?:{WAKE_UP_EN})\b)?"
                  rf"|(?:(?:{WAKE_UP_KO})[\s,.!~]*)?(?:헤이 ?|하이 ?)?(?:루미|누미)(?:야|아)?(?:[\s,.!~]*(?:{WAKE_UP_KO}))?"
                  rf"|^\W*(?:(?:hey|ok|okay|come on)\W+)?(?:{WAKE_UP_EN})\W*$|^\W*(?:(?:자|이제|얼른)\s+)?(?:{WAKE_UP_KO})[\s.!~]*$", re.I)
# ^ "Hey Lumi", "Lumi", "wake up (Lumi)", "Lumi, wake up", "루미야", "헤이 루미", "루미야 일어나", "일어나세요";
#   a bare "wake up" / "일어나" only as the whole utterance ("I wake up at 7" is no call)
WAKE_REPLY = {"en": "Yes? How can I help?", "ko": "네? 무엇을 도와드릴까요?"}
NAME_ONLY = re.compile(r"^\s*(?:(?:hi|hey|hello|헤이|하이)[\s,]+)?(?:lumi|loomi|rumi|루미|누미)(?:야|아)?[\s,.!?~]*$", re.I)
# ^ only the name, also "루미야" / "헤이 루미" (went to the LLM: "안녕하세요! 제 이름 불러 주셔서 기뻐요." after 2.3 s)
FETCH_STOP = re.compile(r"\b(sto+pp?|stob|halt|freeze|don'?t move)\b|^\W*(?:lumi\W+)?stopped\W*$|스탑|스텁|멈추(?:세요|십시오)|^\W*abort\W*$|\babort (?:the |this |your )?(?:mission|task|trip)\b|\bcancel (?:the |this |your )?(?:mission|task|trip)\b|"
                        r"머+엄*춰|머+엄*추(?:세요|십시오)|멈춰|멈추(?:게|시게|게나|시오|어라)|그만|정지|스톱|스땁|스떱|미션 ?취소|작업 ?취소|"
                        r"거기 ?서(?: ?봐| ?있어)?(?=[\s!.~,]*$)|(?:^|[\s,])서(?:라|요)?(?=[\s!.~,]*$)|\bhold it(?: right)? (?:there|here)\b|"
                        r"^\W*(?:\w+\W+){0,3}hold it\W*$|멈[처쳐]|그마+안|\bstahp\b|움직이지 ?마|\bemergency stop\b|\b(?:stay|hold|keep) still\b|"
                        r"^\W*(?:wait|잠깐|잠깐만|기다려)\W*$", re.I)   # not "거기서 기다려"
FETCH_GIVE = re.compile(r"\bgive (it|that|this|the \w+)( to me)?\b|\bhand (it )?(over|to me)\b|줘|주세요|건네", re.I)
FETCH_PLACE = re.compile(r"\b(put|place|set) (it|that|this|the \w+) (down|on the table)\b|테이블에 ?(놔|놓|둬)|내려 ?(놔|놓)", re.I)
FETCH_BRING_IT = re.compile(r"\bbring (it|that|this)\b|가져와|가져다 ?줘|갖다 ?줘", re.I)   # no object named
# ---- someone talks to Lumi while it is on a mission (docs/17 §4) ----
SAFETY = re.compile(r"\b(watch out|look out|danger(ous)?|emergency|be careful|my (hand|foot|leg|arm))\b|\bstop\s*!|"
                    r"\bstop[\s,!.]+stop\b|위험|조심해|비상|멈춰\s*!|아파|다쳐|스톱 ?스톱|멈춰 ?멈춰|끼었|끼여", re.I)
GO_ON = re.compile(r"\b(go on|carry on|continue|keep going|you can go|go ahead|off you go|on your way|you may go|resume|"
                   r"finish (?:it|the job|your (?:job|task)))\b|계속 ?(가|해|하|진행)|마저 ?(해|하)|"
                   r"가도 ?(돼|됩니다)|가 ?봐|그냥 ?가|다녀오세요|가던 ?길|^\s*(응|네|그래) ?가\b|\byes,? go\b", re.I)
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
                  "lift", "waist"}
BASE_ACTIONS = {"go_to", "come", "come_back", "follow", "move", "turn", "waist"}   # need Patrol on (the base, the waist)
WAIST_STEP_DEG = 30.0               # deg; "turn your waist left" with no amount: this far from where it is (estimate)
DRIVE_STEPS = {"go", "move", "turn"}                                     # mission steps that drive
FIX_SAY = (("Okay.", "네."),                                        # a command taken back in the same sentence
           ("Sorry, which one did you mean? Please say it again.", "죄송해요, 어느 쪽 말씀이세요? 다시 한 번 말씀해 주세요."))
BASE_OFF_SAY = ("I can't drive or turn my waist right now. Switch on Patrol for that.",   # Greeter only: a base /
                "지금은 이동하거나 허리를 돌릴 수 없어요. 패트롤을 켜 주세요.")             # waist motion asked for
WAIST_BACK_SAY = ("I can't turn back to the front right now, so I won't drive.",   # a drive with the waist turned
                  "지금은 앞으로 돌아설 수 없어서 이동하지 않을게요.")                   # and it can't come back (waist_home)
ARM_OFF_SAY = ("Please enable my arm first.", "먼저 제 팔을 켜 주세요.")   # an arm action with the arm switched off
ARM_TASKS = {"pick", "put", "move_object", "fetch", "give", "place", "receive", "wave"}   # + arm reach / fold


def needs_arm(action, target=""):
    """The action moves the arm (the gripper alone, open / close, does not ask for it)."""
    return action in ARM_TASKS or action == "arm" and target not in ("open", "close")


def reach_turn(angle, hand=0.0):
    """Waist turn (deg, + left) before "reach out to me" to a person at the waist-frame `angle` (None: nobody seen or
    heard) that brings the hand, held out at `hand` deg in give (fetch.give_bearing), onto them: 0 within
    REACH_FRONT_DEG, else angle - hand. Greeter only turns the waist for it too: the base stays (fetch.reach)."""
    if angle is None:
        return None
    turn = float(angle) - hand
    return 0.0 if abs(turn) <= REACH_FRONT_DEG else turn


_waist_lock = threading.Lock()     # one waist return at a time (a conversation's end and the drive after it)


def waist_turned():
    """How far (deg, + left) the waist is turned from the front now; 0 when it can't be read."""
    from tasks import fetch
    return safe(fetch._waist_turn, default=0.0) or 0.0


def waist_home(why, fold=False):
    """The waist back to the front: at a conversation's end, before every drive or base turn, when someone else takes
    over the talk. In place (the base stays), so with Greeter only too; fetch._waist_to checks the arm's sweep and the
    limits. Not while a task runs (it turns the waist itself) or the arm is out of look (a hand held out): logged, the
    waist stays, unless `fold` (an order to drive or turn): an empty arm goes back to look along the checked pose
    graph first (an arm left half way by a failed reach refused every drive after it, 2026-10-28). True when the
    waist is at the front."""
    from tasks import fetch
    with _waist_lock:
        try:
            if abs(fetch._waist_turn()) < 1.0:
                return True
            if fetch.state().get("status") == "running":
                log(f"  waist stays turned ({why}): a task runs")
                return False
            if not fetch._at_pose(fetch._look()):
                if not fold or fetch.state().get("holding"):
                    log(f"  waist stays turned ({why}): my arm is not folded in look")
                    return False
                log(f"  arm back to look first ({why})")
                arm_route.move(arm_route.plan(arm_route.HOME, holding=False), None, False)
            fetch._stop.clear()                       # no task runs: an old stop must not end this; a new one does
            if fetch._waist_to(0.0, in_place=True):
                log(f"  waist to the front ({why})")
                return True
        except Exception as e:
            log(f"  waist stays turned ({why}): {e!r}")
        return False
LIFT_VEL = 20                       # speed ratio % for a lift move asked by voice (head.VEL is 40)
LIMIT_SAY = {"yaw": (f"I can turn my head up to {head.AXIS_LIMITS[2][1]:g} degrees each way.",
                     f"고개는 좌우로 {head.AXIS_LIMITS[2][1]:g}도까지 돌릴 수 있어요."),
             "pitch": (f"I can tilt my head from {-head.PITCH_RANGE[0]:g} degrees down to {head.PITCH_RANGE[1]:g} degrees up.",
                       f"고개는 아래로 {-head.PITCH_RANGE[0]:g}도, 위로 {head.PITCH_RANGE[1]:g}도까지 움직여요."),
             "lift": (f"For now I can raise my body only up to {head.LIFT_MAX_MM:g} millimetres.",
                      f"지금은 몸을 {head.LIFT_MAX_MM:g}밀리미터까지만 올릴 수 있어요."),   # a number asked for was past the range
             "left": ("I'm already turned as far left as I can go.", "고개를 더 이상 왼쪽으로 돌릴 수 없어요."),
             "right": ("I'm already turned as far right as I can go.", "고개를 더 이상 오른쪽으로 돌릴 수 없어요."),
             "up": ("I'm already looking as far up as I can.", "고개를 더 이상 들 수 없어요."),
             "down": ("I'm already looking as far down as I can.", "고개를 더 이상 숙일 수 없어요."),
             "lift_up": ("I'm already as tall as I can go.", "더 이상 올라갈 수 없어요."),
             "lift_down": ("I'm already as low as I can go.", "더 이상 내려갈 수 없어요."),
             "waist_left": ("My waist is already turned as far left as it goes.", "허리를 더 이상 왼쪽으로 돌릴 수 없어요."),
             "waist_right": ("My waist is already turned as far right as it goes.", "허리를 더 이상 오른쪽으로 돌릴 수 없어요.")}
             # the head or the lift already at that end ("more" / "again" too): nothing moved, said plainly
DONE_TALK = re.compile(r"\b(bye+|goodbye|see you|never ?mind|nothing|that'?s (all|it)|no thanks|thanks|thank you|"
                       r"okay|ok|fine|alright|cool|whatever)\b|안녕히|잘 ?가|됐어|괜찮아|아니야|고마워|감사|그래|네|수고|알았어|"
                       r"그게 ?다|빠이|바이|나중에|안녕\s*[.!]?$", re.I)
RESUME_S = 300.0                    # s; "Lumi, keep going" this long after a stop word ended a mission does its rest
STOPPED_RECENT_S = 10.0             # s; a mission that ended this recently (a stop word cut its skill first) is the one
                                    # a stop word stopped
ENOUGH = re.compile(r"\b(enough|no more)\b|그만해|됐어 ?그만", re.I)   # with stop_order: ends a mission at once
ASK_NOT_ORDER = re.compile(r"\b(can|could|would|will) you\b|\bplease\b|줄래|줄 ?수|해 ?줘|주세요|(?<!뭐 )줘", re.I)   # a request
LOOK_HOLD_S = 35.0                  # s; a head direction asked for ("look up / left") is held this long after the last
                                    # word, or until the conversation ends or a stop word (estimate)
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
                        r"(줘|주세요|건네)|(?:들고 ?있는|손에 ?(?:든|있는)|쥐고 ?있는|잡고 ?있는) ?(?:거|것|\S+)(?:을|를)?\s*(?:좀\s*)?(?:나|저)?(?:한테|에게)?\s*(?:좀\s*)?(?:줘|주|줄|도(?=\W*$)|건네|넘겨|내놔)|^\s*건네\s*(줘|주세요)|테이블에\s*(놔|놓아|둬)|내려\s*(놔|놓아)", re.I)
EMPTY_HAND_SAY = {"en": "I'm not holding anything right now.", "ko": "지금은 손에 아무것도 들고 있지 않아요."}
ASK_PREFIX = re.compile(r"\b(do|did) you (know|happen to know)\b|\b(can|could) you (tell|find out|look up|check)( me)?\b|"
                        r"아세요|알아요|알아\?", re.I)          # "do you know who won?" is not about Lumi
ASKS_MORE = re.compile(r"\?|\b(but|can|could|what|how|where|why|when|who|one more)\b|근데|그런데|뭐|어떻게|어디|언제|누구|하나만 더|"
                       r"(?<!그만 )물어볼게|물어봐도", re.I)
THANKS_REST = re.compile(r"\b(?:a bunch|a lot|so much|very much|lovely|great|nice|cool|good to know|again|that was \w+|"
                         r"for (?:the|that|this|telling|your) \w+)\b|감사요|잘 들었어요|잘 알겠어요|[~!.,\s요]", re.I)
                         # left of "Lovely, thanks!", "고마워요~" after the thanks: nothing, so only thanks (talk_fate waits)
FOREIGN_SCRIPT = re.compile(r"[\u0400-\u04ff\u4e00-\u9fff\u3040-\u30ff]")   # Cyrillic, Chinese, Japanese
UNSURE_LOOKUP = False      # look up what the model says it is not sure of: on for gemma4:e4b, which said "not sure"
                           # instead of choosing search; gemma4:26b chooses search itself, and its "not sure" answers
                           # (2026-10-19 checks: 11 of 11) were about Lumi, Cutshion or the venue, never a lookup
NOT_KNOWN = {"en": ["I don't have exact information about that. A staff member can tell you.",
                    "I'm sorry, I don't have that information. A staff member can help you.",
                    "That one I don't know, sorry. A staff member here can tell you.",
                    "I'm not sure about that. Please ask a staff member."],
             "ko": ["그건 정확한 정보가 없어요. 직원분께 여쭤봐 주세요.",
                    "죄송해요, 그 정보는 없어요. 직원분께 여쭤봐 주세요.",
                    "그건 저도 잘 몰라요. 직원분께 물어봐 주시겠어요?",
                    "아쉽지만 그건 제가 알 수 없어요. 직원분이 알려 드릴 거예요."]}   # said when a lookup is refused


def not_known(lang):
    return random.choice(NOT_KNOWN[lang])
TALK_ASK_S = 15.0                   # s of silence while halted for someone -> "Can I go on with my task?" (asked once)
RELEASE = re.compile(r"^\s*(?:(?:ok(?:ay)?|alright|lumi|루미야?)[\s,.!]+)?(?:you can go(?: now)?|take care|가 ?보세요|가세요|가도 ?돼요?)"
                     r"[\s.!~]*$", re.I)   # said alone: the visitor lets Lumi go
THANKS = re.compile(r"\bthank(?:s| you)\b|\bthanx\b|\bcheers\b|고마워|고맙|감사|땡큐", re.I)
DONE_WORDS = re.compile(r"\bthat'?s (?:it|all|enough|everything|plenty)\b|\bno,? thanks?\b|\bnothing(?: else)?\b|\benough\b|됐어|됐습니다|"
                        r"\bi'?m (?:good|all set|fine|done)\W*(?:thanks?\W*)?(?:robot|lumi)?\W*$|^\W*(?:nah|nope),? (?:i'?m )?(?:good|fine)\W*$|"
                        r"충분해|충분합니다|^\W*(?:아뇨|아니요|아니)?\W*없어요?\W*$|(?:^|[\s,.])(?:더 )?없(?:어|어요|습니다)(?=[\s,.!~]|$|고마|감사)|"
                        r"괜찮(?:아|아요|습니다)(?=[\s,.!~]|$)|그거면 (?:돼|됐|충분)|\ball good\b|\bi'?m good\b|\bthat helped\b|"
                        r"그만", re.I)            # "that's it", "됐어요": maybe done; the LLM decides with the talk before
HI_ANNYEONG = re.compile(r"(?<!히)안녕(?!히)[\s.!~]*$")   # 안녕 is hello or bye: before anything is said, hello
CLEAR_BYE = re.compile(r"\b(?:bye|bay bay|goodbye|(?<!can't )(?<!cant )(?<!cannot )(?<!not )(?<!to )(?<!let's )(?<!lets )see you|see ya|good night|"
                       r"take care|i (?:have|need) to go|gotta (?:go|run)|i'?m leaving|i'?m off|have a (?:good|nice|great) (?:one|day)|"
                       r"catch you later|later,? (?:robot|lumi)|i'?m heading (?:out|off)|i'?ll let you (?:get back|go)|"
                       r"i'?ll (?:go|head off|be going|get going|be off)(?: now)?(?=\W*$|\W+(?:thanks|bye))|thanks? for everything|"
                       r"nice (?:talking|meeting|chatting)(?: (?:to|with))? you|(?:was|been) nice to meet you)\b|"
                       r"(?<=\S)[\s.,!]+안녕[\s.!~]*$|안녕히|잘 ?가|잘 ?있어|잘 ?있게|수고하세요|들어가세요|바이바이|빠이|"
                       r"(?<![가-힣])바이(?![가-힣])|(?<![가-힣])간다[\s.!~]*$|가 ?볼게요|갈게요|(?:나|저|이제) (?:이제 )?가야 ?(?:돼|해|겠|할)|"
                       r"(?:다음에|담에) (?:또 )?(?:봐|봬|뵐게|만나|올게)|또 (?:봐|봬|뵐게|올게)|나중에 (?:봐|봬|뵐게)|좋은 하루|가야겠|"
                       r"(?:^|[,.~!]\s*|(?:이제|그럼|먼저|나 이제|저 이제)\s+)갈게[~!.\s]*$|가 ?봐야 ?(?:돼|해|겠|할|됩)|그럼 이만|이만 (?:갈게|가 ?볼게|가겠|실례)|수고하십시오|수고하셔요|수고해(?:요)?[~!.\s]*$|"
                       r"(^|\s)(나|저|우리|저희) (이제 )?(집에 )?(가|간다|가요|갑니다)[\s.!]*$", re.I)
                       # a goodbye in any talk: "okay, bye", "I have to go", "수고하세요" (thanks, okay, 됐어: the LLM reads them)
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
HELLO_ONLY = re.compile(r"^(?=\W*\w)\s*(?:(?:hi|hey|hello|hiya|hai|hallo|helo|high)(?: there)?[\s,.!]*)?"   # a plain "Hi!",
                        r"(?:how are you(?: doing)?(?: today)?[\s,.!?]*)?$|"                        # "how are you?"
                        r"^\s*(?:안녕|안녕하세요|안녕하십니까|하이)[\s.!~?]*$", re.I)               # "안녕하세요", "하이"
CALL_REST = re.compile(r"^(?:[\W_]|\b(?:hi|hey|hello|hiya|hai|ok|okay|there|how are you(?: doing)?(?: today)?)\b|"
                       r"안녕(?:하세요|하십니까)?|하이|헤이|야|아)*$", re.I)   # what is left of a call without the name
CAMERA_HALF_FOV = 42.0             # deg; half the camera's view (+ the head's YAW_LIMIT for the head camera)
WAKE_MAX_S = 6.0                   # s; longer utterances are not checked for the wake word
BARGE_IN_LOGPROB = -0.6            # an interruption must be heard more clearly than a normal answer (-1.0)
ECHO_LIKELY = 0.45                 # sound match (mouth.echo) from which a barge-in is Lumi's own voice when its words
ECHO_LIKELY_SHARE = 0.4            # ... share this much with what Lumi said; echoes 0.51 / 0.54, the visitor 0.14-0.32
                                   # (2026-10-23 15:08-15:16; mouth.ECHO_MIN 0.6 alone let the weather answer's echo in)
BYE_WAVE = re.compile(r"\bb(?:ye|ay)[- ]?b(?:ye|ay)\b|바이 ?바이|빠이 ?빠이|잘 ?가", re.I)   # a goodbye with a wave
CLOSING_WAIT_S = 8.0               # s of silence after "okay" / "thank you" / "네" before Lumi says goodbye
ANSWER_ECHO_S = 10.0               # s of Lumi's speech a dialog answer is checked against for echo: only the question
                                   # (the wake reply "Yes?" 20 s earlier swallowed the answer "Yes. Yes.", 2026-10-21)
VOICE_SESSION_S = 15.0             # s a conversation started by voice (nobody in view) waits for the next words
SPEAKER_MATCH_DEG = 25.0           # a voice direction belongs to the visible person within this angle
FOCUS_EVERY_S = 0.5                # s between checks that the head is still on the person Lumi talks with
FOCUS_DEG = 8.0                    # deg that person may move off the head's direction before the head follows
FOCUS_REFIND_DEG = 15.0            # a lost track's person is found again as the new track within this angle of it
LOOK_ME_PITCH = 0.0                # deg, head pitch of the first turn to a person ("look at me"): level, a far person
                                   # fits whole; the head camera then tilts it to their height (look_me_pitch)
LOOK_ME_SETTLE_S = 0.6             # s after a head move before its camera is asked who is there
LOOK_ME_TOP_ROW = 0.08             # share of the image height from the top where the person's head should be
LOOK_ME_EDGE_PX = 8                # a box edge this near the frame edge is cut by it
LOOK_ME_UP_STEP = 10.0             # deg up when the person's head is cut by the frame top (how much is cut is unknown)
LOOK_ME_MIN_DEG = 2.0              # smaller pitch corrections are not made
LOOK_ME_TRIES = 3                  # pitch corrections at most
TORSO_FRESH_S = 2.0                # s; older torso detections are not used (idle, the service detects 1 per second)
DOA_MIN_CONF = 0.12                # below this the sound direction is not trusted
LOOK_WAIST_MAX = 120.0             # deg; "look at me" from behind with Patrol off: the waist turns at most this far
VOICE_KEEP_S = 20.0               # s a sure voice direction stands for the next words whose own sound is too weak
DOA_CLIP_MIN_CONF = 0.05           # the same with the clip voice found in the array: clip-weighted confidences run
                                   # lower (0.07 at the right -90 deg live, 2026-10-27); estimate, check live
FOLLOW_VOICE_DEG = 35.0            # while following, a voice this near the followed person's angle is theirs (estimate:
                                   # the sound direction's median error was 22-31 deg on 2026-10-22)
FOLLOW_SORRY_S = 20.0              # s; "Sorry, I'm following someone" at most this often
COME_STOP = 1.1                    # m; driving to a person stops when the camera sees them this close
COME_TIMEOUT = 60.0                # s
MAX_MOVE_M = 3.0                   # m; "move forward N metres" is limited to this
REACH_FRONT_DEG = 10.0             # deg; "reach out to me": a person further than this from where the hand points is
                                   # turned to first (the waist, Greeter or Patrol); the reach after give moves at most
                                   # fetch.RECEIVE_REACH_MM sideways (estimate)
REACH_COME_M = 1.5                 # m; a person further than this is driven to first (come_to, COME_STOP), the hand is
                                   # never held out from afar (owner, 2026-10-28)
COME_CLOSER_SAY = ("Please come a little closer.", "조금 더 가까이 와 주세요.")
STAND_IN_FRONT_SAY = ("Please stand in front of me.", "제 앞에 서 주세요.")
REACH_HOLD_S = 30.0                # s the hand stays held out after a reach, then the arm folds back to look (estimate)
REACH_DONE = re.compile(r"\b(?:thanks?|thank you|thx|ok(?:ay)?|got it|done|that'?s (?:it|all|enough)|enough|good|great|"
                        r"nice|cool|alright|all right)\b|고마워|고맙|감사|됐어|됐습니다|됐다|좋아|오케이|그만", re.I)
HAND_EMPTY_SAID = re.compile(   # the person says Lumi's hand is empty: checked again (fetch.check_hand), not just agreed
    r"\b(?:nothing|not anything) (?:is )?in (?:your|ur) hand\b|\b(?:your|ur) hand(?:'s| is) empty\b|"
    r"\byou(?:'re| are) not holding (?:anything|something)\b|\byou have nothing in (?:your|ur) hand\b|"
    r"손에 ?(?:아무것도|아무 ?것도|뭐 ?없|없)|손 ?비었|빈 ?손이", re.I)
STUCK_DRIVE_S = 20.0               # s "running" without moving -> the drive is cancelled and Lumi says so
MODES_FILE = "/dev/shm/lumi_modes.json"   # written by api/server.py: {"greeter", "patrol", "wave"}
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
WAVE_CHECK_S = 0.4                 # s between two looks for a raised hand (pose net, ~20 ms); two looks in a row
WAVE_MATCH_DEG = 15.0              # deg; a raised hand belongs to the tracked person within this angle
GAZE_MATCH_DEG = 15.0              # deg; the person this near where the head looks is the one Lumi looks at (estimate)
RAISE_HAND_S = 6.0                 # s a "raise your hand" waits for the one who gave the order
RAISE_HAND_SAY = ("Who asked? Please raise your hand.", "누가 말씀하셨어요? 손을 들어 주세요.")
WHO_ASKED_SAY = ("Sorry, I couldn't tell who asked. Please come in front of me.",
                 "누가 말씀하셨는지 모르겠어요. 제 앞으로 와 주세요.")
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


_log_day = [None]                               # the date last written to the log


def log(msg):
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    day = time.strftime("%Y-%m-%d %A")
    if day != _log_day[0]:                      # at each start and each new day: lines carry only the time, and an
        _log_day[0] = day                       # old day's talk was once read as today's (2026-10-12 vs 10-26)
        line = f"=== {day} ===\n{line}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a") as f:          # also kept in lumi.log, to read it over SSH
            f.write(line + "\n")
    except OSError:
        pass


def voice_min_conf(u):
    """The confidence from which this utterance's sound direction is trusted."""
    return DOA_CLIP_MIN_CONF if doa.clip_found(u.mics, doa.clip_ref(u)) else DOA_MIN_CONF


def safe(fn, *args, default=None):
    """Call a robot function; on a network error log it and carry on instead of crashing."""
    try:
        return fn(*args)
    except Exception as e:
        log(f"{getattr(fn, '__name__', fn)} failed: {e}")
        return default


NOISE_WORDS = re.compile(r"\W*(?:u+m+|h?m+|uh+|ah+|oh+|ahem|a?choo|cough|boom|beep|ding|bang|pop|knock|음+|어+|아+|크?흠+|큼+|"
                         r"콜록\S*|에?[취츄]|엣취)\W*", re.I)   # whisper for room sounds
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


def look_me_pitch(box, height, pitch, fy, cy):
    """Head pitch (deg, + up) that puts a person's head (their box top) near the top of the head camera's view with as
    much of them below as fits, or None when the head may stay: the whole person is in view (far), or the change is
    small. Pinhole angles without the lens distortion; the next frame corrects what is left."""
    top, bottom = box[1], box[3]
    if top <= LOOK_ME_EDGE_PX:                           # their head is cut: tilt up
        new = pitch + LOOK_ME_UP_STEP
    elif bottom < height - LOOK_ME_EDGE_PX:              # all of them is in view
        return None
    else:
        new = pitch + math.degrees(math.atan((cy - top) / fy) - math.atan((cy - LOOK_ME_TOP_ROW * height) / fy))
    new = max(head.PITCH_RANGE[0], min(head.PITCH_RANGE[1], new))
    return new if abs(new - pitch) >= LOOK_ME_MIN_DEG else None


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
                    best = min(free, default=None, key=lambda t: abs(t.angle - p["angle_deg"])
                               + MATCH_DEG_PER_M * abs(t.distance - p["distance_m"]))
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

    def seen(self):
        """Everyone in view as (waist-frame angle, distance): this camera's people and, while the head camera is in
        use, the torso camera's fresh ones too (someone beside Lumi is often outside the turned head camera's view)."""
        with self.lock:
            out = [(t.angle, t.distance) for t in self.tracks if t.distance <= STAY_MAX]
        if self.camera != "torso":
            camview.want("torso")
            try:
                d = json.loads(camview.det_path("torso").read_text())
                if time.time() - d["time"] <= TORSO_FRESH_S:
                    out += [(p["angle_deg"], p["distance_m"]) for p in d["people"]
                            if p["distance_m"] is not None and p["distance_m"] <= STAY_MAX]
            except (FileNotFoundError, ValueError, KeyError):
                pass
        return out

    @staticmethod
    def head_person(angle, since):
        """The head camera's person nearest this waist-frame angle in a frame newer than `since`, as {box, height,
        pitch (head pitch of that frame), fy, cy}, or None."""
        intr = camview.intrinsics("head")
        try:
            d = json.loads(camview.det_path("head").read_text())
            people = [p for p in d["people"] if abs(p["angle_deg"] - angle) <= SPEAKER_MATCH_DEG]
            if d["time"] <= since or not people or intr is None or not d.get("head_pose"):
                return None
            p = min(people, key=lambda p: abs(p["angle_deg"] - angle))
            return {"box": p["box"], "height": d["height"], "pitch": d["head_pose"][3],
                    "fy": intr["fy"], "cy": intr["cy"]}
        except (FileNotFoundError, ValueError, KeyError):
            return None

    def only_person(self):
        with self.lock:
            near = [t for t in self.tracks if t.distance <= 3.0]
        return near[0] if len(near) == 1 else None

    def visible(self, track):
        """Is this person tracked now, at any distance ("come here" is for far people; present() ends at STAY_MAX)?"""
        with self.lock:
            return track in self.tracks

    def anyone(self):
        """Is anybody tracked now, at any distance?"""
        with self.lock:
            return bool(self.tracks)

    def only_seen(self):
        """The one person tracked, at any distance (4.7 m away, "do you see me?" yes, "come here" said "I can't see
        you", 2026-10-28), else None."""
        with self.lock:
            return self.tracks[0] if len(self.tracks) == 1 else None

    def anyone_near(self):
        with self.lock:
            return any(t.distance <= STAY_MAX for t in self.tracks)

    def nearest_greeted(self):
        with self.lock:
            here = [t for t in self.tracks if t.greeted and t.distance <= STAY_MAX]
        return min(here, key=lambda t: t.distance, default=None)

    def follow_view(self, track):
        """(distance m, angle deg, age s, clothes signature or None) of the person being followed (tasks/follow.py),
        None once the track is gone. The distance is the nearer of the median and the newest reading: the median lags
        when they stop."""
        with self.lock:
            if track not in self.tracks:
                return None
            return min(track.distance, track.history[-1]), track.angle, time.time() - track.last_seen, track.look

    def follow_views(self):
        """[(see, distance m, angle deg, age s, look)] of everyone in view: tasks/follow.py re-locks onto one of them."""
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
        self.stuck_why = None            # (en, ko) when robot/nav_guard.py ended it (the arm would hit something)
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
        if self.mode == "patrol" and battery < LOW_BATTERY and now >= self.wait_until:
            log(f"battery {battery} % - going home to charge")
            self.pause()
            if not waist_home("going home", fold=True):          # every drive starts with the waist at the front
                self.wait_until = now + 5
                return
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
                if isinstance(st.get("guard"), (list, tuple)):
                    self.stuck, self.stuck_why = self.route[self.i], st["guard"]
                log(f"patrol move {ms} - retry in 5 s")
                self.wait_until = now + 5
            return
        if (ms == "running" and not force) or now < self.wait_until:   # something else is driving, or waiting
            return
        target = self.route[self.i]
        if not waist_home("driving", fold=True):                   # every drive starts with the waist at the front
            if self.once:                               # said by say_stuck
                self.stuck, self.stuck_why, self.mode = target, WAIST_BACK_SAY, "done"
            else:
                self.wait_until = now + 5
            return
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
        self.wave = not args.no_arm
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
                changed = {k: d[k] for k in ("greeter", "patrol", "wave") if k in d and d[k] != getattr(self, k)}
                for k, v in changed.items():
                    setattr(self, k, bool(v))
                if changed and not force:
                    log(f"modes: {changed}")
        except (FileNotFoundError, ValueError):
            pass


class Lumi:
    chain_thread = None                  # several commands of one sentence done in order (chain_run)
    chain_stop = threading.Event()       # set by "stop" or anything new said: the rest of the chain is not done

    def __init__(self, args):
        self.a = args
        self.brain = Brain()
        self.current = None              # the track we are talking with
        self.mission_hold = None         # "talk" / "safety": a mission is halted for someone (mission_talk)
        self.asked_go_on = False         # "Can I go on with my task?" was asked
        self.stopped_mission = None      # (task, steps left, time) a stop word ended: "Lumi, keep going" (resume_stopped)
        self.voice_until = 0.0           # a conversation started by voice with nobody in view lasts until then
        self.quiet_until = 0.0           # after "be quiet": no greetings until then
        self._yaw, self._yaw_time = 0.0, 0.0
        self.pending_text = None         # a question the visitor asked while Lumi was talking (barge-in)
        self.voice_angle, self.voice_trusted = 0.0, False   # where the last caller's voice came from
        self.closing_pending = None      # time of a weak closing word ("okay", "got it"): silence after it ends the talk
        self.lang = "en"
        self.skill_thread = None         # pick / put / move_object running in the background
        self.reached_at = 0.0            # time the hand was held out by "give me your hand" (0: not out; reach_done)
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
    def look_held(self):
        """After a "look up / left / behind" the head stays there until LOOK_HOLD_S pass with nothing said or asked,
        the conversation ends (head_rest) or a stop word."""
        return time.time() - max(getattr(self, "looked_at", 0.0), getattr(self, "last_activity", 0.0)) < LOOK_HOLD_S \
            if getattr(self, "looked_at", 0.0) else False

    def turn_head(self, yaw=None, pitch=None, force=False):
        """Automatic head moves (toward a speaker, a greeting, back to rest) wait while a look is held; force: an
        order or a task."""
        if not force and self.look_held():
            return

        def run():
            try:
                cur = head.status()
                head.turn(cur[2] if yaw is None else yaw, cur[3] if pitch is None else pitch)
            except Exception as e:
                log(f"head error: {e}")
        threading.Thread(target=run, daemon=True).start()

    def head_rest(self):
        """End a held look and send the head to rest: ahead, looking down."""
        self.looked_at = 0.0
        self.turn_head(0, head.HEAD_REST_PITCH)
        self.waist_rest()

    def waist_rest(self, why="the conversation is over"):
        """The waist back to the front too when a conversation ends (waist_home, in the background), Greeter or
        Patrol; it waits like the head while a look is held."""
        if not self.look_held():
            threading.Thread(target=waist_home, args=(why,), daemon=True).start()

    def keep_focus(self):
        """In the background: the head stays on the person Lumi talks with (self.current) as they move, a turn when
        they are more than FOCUS_DEG off. A held look waits (turn_head), except one held by "look at me": it follows
        that person (self.look_me). Not during a task, a follow, a song or a "look at me" search (head_busy)."""
        while True:
            time.sleep(FOCUS_EVERY_S)
            try:
                self.focus_step()
            except Exception as e:
                log(f"focus error: {e!r}")

    def focus_step(self):
        from tasks import follow
        t = self.current
        if t is None or getattr(self, "head_busy", False) or time.time() < self.calib_until or \
                self.doing() or follow.running() or not self.vision.present(t):
            return
        want = HEAD_SIGN * max(-head.YAW_LIMIT, min(head.YAW_LIMIT, t.angle))
        if abs(want - self.det_yaw()) > FOCUS_DEG:
            self.turn_head(want, force=t is getattr(self, "look_me", None))

    def face(self, track):
        """Turn to the person who now speaks: a waist turned for someone else comes back to the front first
        (waist_home), then the head turns to them (their angle from where the waist was, plus the turn taken back)."""
        w = waist_turned()
        if abs(w) < 1.0:
            self.turn_head(HEAD_SIGN * track.angle)
            return
        angle = track.angle

        def run():
            self.turn_head(HEAD_SIGN * (angle + w if waist_home("someone else speaks") else angle))
        threading.Thread(target=run, daemon=True).start()

    def wave(self, ok=None, quiet=False):
        """Wave because someone asked or said "bye bye" in view (never on a greeting): manipulation/wave.py checks the
        arm, the hand, the start pose and the whole path first; a refusal is said unless `quiet`. Not while following,
        on a mission or a task. `ok`: (English, Korean) said once the wave is checked, while the arm already moves
        (owner: no waiting for the words first). True if waved."""
        from tasks import follow
        if not self.modes.wave:
            log("  waving is switched off (dashboard)")
            return False
        st = self.fetch_status()
        why = (wave_mod.HOLDING if st == "holding" and self.held_now() else   # a stale "holding": checked again
               wave_mod.BUSY if self.skill_busy() or self.mission_running() else
               wave_mod.DRIVING if follow.running() else None)
        try:
            if why:
                raise wave_mod.WaveError(*why)
            if self.vision:
                self.vision.arm_watch = True
            self.publish_busy("wave")
            wave_mod.wave(on_start=(lambda: threading.Thread(target=self.fetch_say, args=ok, daemon=True).start())
                          if ok else None)
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

    def stay(self):
        """Tasks asked with only Greeter on, by voice or from the dashboard, stay in place (fetch.stay_put: head and
        lift only, no base, no waist)."""
        from tasks import fetch
        fetch.stay_put = not self.modes.patrol

    def act(self, action, target):
        log(f"action: {action} {target}")
        if action in ARM_TASKS or action == "stop":
            self.reached_at = 0.0                               # another arm job: the reach's auto fold is off
        if self.base_off(action, target, say=False):            # answer() has said why
            return
        if action in MOVING_ACTIONS and self.mission_running():
            log(f"  {action} refused: on a mission")             # the LLM's action must not take Lumi off its task
            return
        if action == "look" and target == "me":           # "look at me", "이쪽 봐": the speaker, never just the centre
            self.looked_at = time.time()                    # held like any look
            threading.Thread(target=self.look_at_speaker, daemon=True).start()
        elif action == "look" and target.split()[0:1] and (target.split()[0] in LOOK or target == "away"):
            return self.look(target)                        # a LIMIT_SAY key when the head is at its end
        elif action == "lift":
            return self.lift(target)
        elif action == "wave":
            threading.Thread(target=self.wave, daemon=True).start()   # while the reply is spoken
        elif action == "stop":
            from tasks import follow
            safe(follow.stop)                                        # first: the base gets 0 at once
            safe(agv.cancel)
            safe(skills.cancel)
            safe(motion.stop)                                        # also a wave's waiting move
        elif action == "go_to":
            self.start_trip(target)
        elif action in ("move", "turn"):
            self.move_by(action, target)
        elif action == "come_back":
            self.come_back()
        elif action == "detour":                                     # the model read it from now_doing's block
            if target in detour.SAY:
                self.detour(target, speak=False)
        elif action == "arm":
            self.arm_pose(target)
        elif action in ("pick", "put", "move_object"):
            self.object_task(action, target, confirm=False)          # the LLM's words already confirmed it
        elif action == "fetch":                                      # parse the person's own words, never the LLM's
            self.fetch_request(getattr(self, "heard", "") or target)  # wording ("ap" must not become "apple")
        elif action in ("give", "place"):
            if self.fetch_status() == "holding":
                self.fetch_finish(action)

    def look_at_speaker(self):
        """"Look at me": the person seen nearest the voice (both cameras). Nobody seen there: the head turns to the
        voice first, then to whoever the head camera finds there; nobody there either (the voice direction can be
        off): the person talked to, else the nearest person seen. Nobody seen and no voice: the head stays. Then the
        head tilts until the head camera sees the person from their head down (look_me_pitch). That person becomes
        the one talked with, and while the look is held the head follows them (look_me, keep_focus)."""
        if not self.vision:
            return
        self.head_busy = True                               # keep_focus waits: the head is turned here
        try:
            self._look_at_speaker()
        finally:
            self.head_busy = False

    def _look_at_speaker(self):
        def near(seen, angle):
            return min((s for s in seen if abs(s[0] - angle) <= SPEAKER_MATCH_DEG),
                       key=lambda s: abs(s[0] - angle), default=None)

        def face(angle, pitch=LOOK_ME_PITCH):
            safe(head.turn, HEAD_SIGN * max(-head.YAW_LIMIT, min(head.YAW_LIMIT, angle)), pitch)

        recent = time.time() - getattr(self, "voice_at", 0.0) <= VOICE_KEEP_S   # this turn's sound too weak: the
        voice = self.voice_angle if self.voice_trusted or recent else None    # caller's last sure direction
        seen = self.vision.seen()
        found = near(seen, voice) if voice is not None else None
        if found is None and voice is not None and abs(voice) > head.YAW_LIMIT:
            voice = self.turn_body_to(voice)               # behind or far aside: the head alone can't get there
        if found is None and voice is not None:
            log(f"  look me: nobody seen at the voice ({voice:+.0f} deg), turning there first")
            face(voice)
            time.sleep(LOOK_ME_SETTLE_S)                    # new head camera frames from there
            seen = self.vision.seen()
            found = near(seen, voice)
        why = "nearest the voice"
        if found is None:
            cur = self.current if self.current and self.vision.present(self.current) else None
            if cur:
                found, why = (cur.angle, cur.distance), f"the person talked with (#{cur.id})"
            elif voice is not None:                          # the voice off: the person nearest its direction, not
                found = min(seen, key=lambda s: abs(s[0] - voice), default=None)   # the nearest one far off it
                why = f"nearest the voice's side ({voice:+.0f} deg)"
            else:
                found, why = min(seen, key=lambda s: s[1], default=None), "the nearest seen, no voice direction"
        if found is None:
            log(f"  look me: nobody seen{'' if voice is None else ' at the voice either'}, the head stays")
            return
        log(f"  look me: person at {found[0]:+.0f} deg, {found[1]:.2f} m ({why})")
        face(found[0])
        for _ in range(LOOK_ME_TRIES):
            since = time.time()
            time.sleep(LOOK_ME_SETTLE_S)                    # new head camera frames from there
            p = self.vision.head_person(found[0], since)
            pitch = p and look_me_pitch(p["box"], p["height"], p["pitch"], p["fy"], p["cy"])
            if pitch is None:
                break
            log(f"  look me: box top {p['box'][1]}, pitch {p['pitch']:+.0f} -> {pitch:+.0f} deg")
            face(found[0], pitch)
        t = self.vision.near_angle(found[0], SPEAKER_MATCH_DEG)
        if t is not None:                                    # the focus: talked with, the held look follows them
            log(f"  look me: focus on person #{t.id}")
            t.greeted, self.current, self.look_me = True, t, t

    def turn_body_to(self, angle):
        """A voice past the head's reach (waist-frame deg): with Patrol the base turns to it (look_toward), else the
        waist turns in place toward it (the base stays; fetch._waist_to checks the arm's sweep). Returns the voice's
        waist-frame angle after the turn (unchanged when nothing could turn)."""
        from tasks import fetch
        if self.modes.patrol:
            self.look_toward(angle)
            return 0.0
        w = waist_turned()
        want = max(-LOOK_WAIST_MAX, min(LOOK_WAIST_MAX, w + angle))
        log(f"  look me: the voice at {angle:+.0f} deg is past the head: waist to {want:+.0f} deg")
        try:
            fetch._waist_to(want, in_place=True, look=angle)
        except Exception as e:
            log(f"  look me: waist did not turn: {e!r}")
        return angle - (waist_turned() - w)

    def look(self, target):
        """'left', 'left 30', 'down small' (brain.head_goal): the head, cut to its range. Returns "yaw" / "pitch"
        when a number asked for was past the range, the direction ("down") when the head already stands at that end
        (nothing moves; LIMIT_SAY says so), else None."""
        cur = safe(head.status)
        if cur is None:
            return None
        self.looked_at, self.look_me = time.time(), None     # held where asked, not on a person
        yaw, pitch, limited = brain_mod.head_goal(target, cur[2], cur[3], LOOK)   # the body's full range (AXIS_LIMITS):
        if limited in ("left", "right", "up", "down"):
            log(f"  look {target}: already at the end (yaw {cur[2]:.0f}, pitch {cur[3]:.0f})")
            return limited
        threading.Thread(target=lambda: safe(head.moveto, [cur[0], cur[1], yaw, pitch]),   # head.turn() keeps
                         daemon=True).start()                                              # to YAW_LIMIT
        return limited

    def lift(self, target):
        """'up', 'down', 'up small', 'up 50' (mm; brain.lift_goal): the lift, slowly, cut to 0..head.LIFT_MAX_MM.
        Returns the LIMIT_SAY key: "lift" when a number asked for was cut, "lift_up" / "lift_down" when the lift
        already stands at that end (nothing moves), else None."""
        cur = safe(head.status)
        if cur is None:
            return None
        mm, limited = brain_mod.lift_goal(target, cur[0], head.LIFT_MAX_MM)
        if limited in ("up", "down"):
            log(f"  lift {target}: already at {cur[0]:.0f} mm, the end")
            return f"lift_{limited}"
        limited = "lift" if limited else None
        log(f"  lift {cur[0]:.0f} -> {mm:.0f} mm")
        threading.Thread(target=lambda: safe(lambda: head.moveto([mm, cur[1], cur[2], cur[3]], LIFT_VEL)),
                         daemon=True).start()
        return limited

    def waist(self, target):
        """'left', 'right 45', 'center': the waist (upper body: the arm and both cameras turn with it, the base stays),
        from where it is, the front being where measure-axis was run (fetch._waist_turn); +deg = left. The move is
        fetch._waist_to (cut to the waist's range, refused when the arm's sweep is not clear), in a thread. Returns
        "waist_left" / "waist_right" when the waist already stands at that end (nothing moves), else None."""
        from tasks import fetch
        cur = safe(head.status)
        if cur is None:
            return None
        lo, hi = head.AXIS_LIMITS[1]
        front = cur[1] - (safe(fetch._waist_turn, default=0.0) or 0.0)    # the waist angle at the front
        d, _, n = target.partition(" ")
        if d == "center":
            goal = front
        else:
            goal = max(lo, min(hi, cur[1] + (1 if d == "left" else -1) * (float(n) if n else WAIST_STEP_DEG)))
            if abs(goal - cur[1]) < 1.0:
                log(f"  waist {target}: already at {cur[1]:.0f} deg, the end")
                return f"waist_{d}"
        self.stay()

        def run():
            if safe(fetch._waist_to, goal - front, default=False) is False:
                self.fetch_say("Sorry, something is in my arm's way, so I didn't turn.",
                               "죄송해요, 팔 쪽에 뭔가 있어서 돌지 않았어요.")
        log(f"  waist {cur[1]:.0f} -> {goal:.0f} deg")
        threading.Thread(target=run, daemon=True).start()
        return None

    def move_by(self, action, target):
        """'move forward 1' / 'move left 0.5' / 'turn around 180' / 'turn left 90', relative to where Lumi stands.
        Left / right are a normal base move to a map point, so obstacles are avoided; forward and back are a straight
        drive of exactly that length (fetch._move). Returns False if not possible (an amount not read or past the
        limit is never driven: driving.read has asked / refused it)."""
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
        full = action == "turn" and amount >= 360                 # all the way round: a 360 deg goal is the start
        if action == "move" and direction in ("back", "forward") or full:   # pose to navigation; fetch turns twice 180
            from tasks import fetch                               # straight with joy_control, checked like a
            log(f"  {action} {direction} {amount:g} by the task runner")   # mission's move: navigation may turn round
            self.stay()                                           # and stops within its own tolerance
            step = {"do": "turn", "deg": -360.0 if direction == "right" else 360.0} if full else \
                {"do": "move", "dir": direction, "m": amount}
            try:
                fetch.run_steps([step], say=self.fetch_say)
            except fetch.FetchError as e:
                log(f"  {action} {direction} refused: {e}")
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
        t = brain_mod._norm(text, self.markers)            # "come back booth 9" is a place, not 9 of something back
        got = driving.read(t, driving.last_command(hist), driving.talking(hist))
        if not got or got[0] not in ("speed", "look") and (self.mission_running() or got == driving.read(t, None, True)
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
            if not self.move_by("move", got[1]):
                return True
            say = driving.say_move(d, float(n), got[2], lang)
        elif got[0] == "turn":                              # "again" / "a bit more" after a turn
            hist.append((text, f"ACTION: turn {got[1]}"))
            if self.base_off("turn"):
                return True
            log(f"  action turn {got[1]} (again)")
            if not self.move_by("turn", got[1]):
                return True
            say = "Okay." if lang == "en" else "네."
        elif got[0] in ("look", "lift"):                    # "one more" / "더" after a look or a lift: further that way
            hist.append((text, f"ACTION: {got[0]} {got[1]}"))
            log(f"  action {got[0]} {got[1]} (again)")
            limited = self.look(got[1]) if got[0] == "look" else self.lift(got[1])
            say = LIMIT_SAY[limited][lang != "en"] if limited else "Okay." if lang == "en" else "네."
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
        self.stay()
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
        status = self.fetch_status()
        if status == "holding":
            from tasks import fetch
            self.fetch_say(f"I'm holding {fetch.held_name()}, where should I put it first?", f"{brain_mod.object_ko(fetch.held_name('ko'))} 들고 있어요. 먼저 어디에 둘까요?")
            return
        if status == "running":
            self.end_run(text)
        from tasks import fetch
        task, problems = brain_mod.parse_fetch(text, self.markers)
        log(f"  fetch parsed: {task} problems {problems}")
        result = fetch_dialog.run(task, self.markers, self.hear, self.fetch_say, fetch.describe, self.fetch_start)
        log(f"  fetch dialog: {result}")
        self.keep_listening()

    def stop_all(self, text=""):
        """Stop by voice: the fetch / mission runner, the base, the arm, a trip; then say so. An order said after the
        stop word ("Lumi stop, not the apple, take the cup") is done next; else a stopped mission is kept for "Lumi,
        keep going" (resume_stopped)."""
        from tasks import fetch
        log("  stop by voice")
        self.chain_stop.set()
        left = self.mission_left()
        safe(fetch.stop)
        rest = text and order_after_stop(text, self.markers, getattr(self, "brain", None))
        if rest:
            log(f"  then the order after the stop: {rest!r}")
            safe(fetch.end)                                # the run's thread is over: the new order can start
            self.pending_text = rest
        self.stopped_mission = None if rest else left
        self.act("stop", "")
        if self.patrol:
            self.patrol.pause()
            self.patrol = None
        self.looked_at = 0.0                               # a stop word ends a held look; the head stays with the
                                                           # person, it rests when the conversation ends
        self.fetch_say("Okay, I stopped.", "네, 멈췄어요.")
        self.keep_listening()

    # ---------- answers by rule: what Lumi can do, its songs, its voice ----------
    def fixed_answer(self, text, last):
        """Answered without the LLM: what Lumi can do (assistant/abilities.py; the rest on "tell me more" / "yes"),
        which songs it knows, the battery now and whether it is charging (assistant/battery.py), and right after a song "another one" / "again" / "그거 말고" (audio/sing.py). True if
        handled."""
        if last.startswith("ACTION: sing") and sing.AFTER_SONG.search(text) and sing.asked(text, last) or \
                sing.picked(text, last):                   # after the list: "the first one", "Fantastic Baby"
            self.sing_song(text)
            return True
        if sing.list_asked(text):
            say, mark = sing.list_reply(self.lang), "ACTION: none songs"
        elif battery.asked(text):                           # "battery?", "충전 중이야?": the base's status now
            say, mark = battery.answer(text, self.lang), "ACTION: none -"
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
        self.end_run(text)                                 # a running task ends for the song
        if self.skill_busy() or self.mission_running():   # the head and the speaker belong to the arm task now
            self.fetch_say("Sorry, I'm on a task right now. I can sing when I've finished.",
                           "죄송해요, 지금 다른 일을 하고 있어요. 끝나면 불러 드릴게요.")
            return
        song = sing.picked(text, self.brain.history[-1][1] if self.brain.history else "") or \
            sing.choose(text, self.lang, self.last_song)   # after the list: "the first one", a title, "아무거나"
        if song is None:                                   # a song we don't have: say which ones we know
            say = sing.unknown_reply(self.lang)
            self.brain.history.append((text, f"ACTION: none songs\n{say}"))   # a title next is sung
            log(f"  not one of our songs: {say[:70]}")
            mouth.say(say)
            self.keep_listening()
            return
        self.last_song = song
        self.brain.history.append((text, f"ACTION: sing {song}"))
        log(f"  singing {song}")
        t = self.current                                   # dance toward the listener, never back at yaw 0
        yaw = HEAD_SIGN * t.angle if t is not None and self.vision and self.vision.present(t) else self.det_yaw()
        self.song_request = (text, time.time())            # the request said again is no new one (song_abort)
        self.head_busy = True                              # keep_focus waits: the dance moves the head
        try:
            done = sing.sing(song, abort=self.song_abort, centre_yaw=yaw)   # sing.around keeps it inside YAW_LIMIT
        finally:
            self.head_busy = False
        log(f"  song {'finished' if done else 'stopped'}")
        self.keep_listening()

    def song_abort(self):
        """While singing (clip mic only, like barge_in): "stop" / "그만" ends the song; another clear request ends
        it and is answered next (pending_text). The song's own words and unclear sounds are ignored."""
        # not self.interrupted(): the head dances away from the listener, who then "left" (songs cut after 2-4 s,
        # 2026-10-23); only words end a song
        if self.peeked_stop(sing.stop_words):
            return True
        u = self.mic.next(0.0)
        if u is None or not getattr(u, "during_speech", False) or u.seconds < 0.25 or mouth.own_voice(u):
            return False
        text = (ears.transcribe(u.mono) or "").strip()
        if not text or self.own_echo(text) or not ears.understood(BARGE_IN_LOGPROB):
            return False
        if sing.stop_words(text):
            log(f"  stop singing: {text!r}")
            return True
        if brain_mod.is_backchannel(text):                 # "thank you": often whisper's guess on music; "wow"
            return False
        # the clip mic hears the song too, and the sound match (own_voice) does not know music through the room (0.2-0.4
        # against the song itself): whisper's words from it, single words and the request said again leave it going
        request, started = self.song_request
        why = sing.ignored_over_song(text, request, time.time() - started, ears.last_stt.get("speech_s"))
        if why:
            log(f"  ignored while singing ({why}): {text!r}")
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
        anyone's stop word ends it at once; anyone's new command ends it with one line and is then done as usual
        (False); the person the mission is for ("I'm James") gets it here or changes it; only an explicit "go on" (or
        a yes to "Can I go on?") goes on. True if handled here; False: answered or done as usual."""
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
        if stop_order(text, self.markers) or ENOUGH.search(text) and "?" not in text:
            log(f"  mission: stop word ({text!r}) - mission ended")   # running or paused: ended; "Lumi, keep going"
            self.mission_hold, self.asked_go_on = None, False        # starts its rest again (resume_stopped)
            self.stop_all(text)
            return True
        recipient = next((s.get("person") for s in task_steps if s.get("do") == "give" and s.get("person")), None)
        name = claimed_name(text)
        owner = next((p for p in (recipient, task.get("sender")) if p and name and same_name(name, p)), None)
        mine = owner is not None                       # the person it is for, or who sent it
        if mine:
            name = owner                               # as the mission writes it ("James", not "james")
        addressed = WAKE.search(text) or SAFETY.search(text) or mine or self.mission_hold or \
            waiting == "instruction" or waiting and GO_ON.search(text) or getattr(self, "typed_now", False)
        # only Lumi's name halts a job: talk nearby ("네, 안녕하세요.", "Very nice.") paused a pick live (2026-10-27)
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
        got, unread, _ = steps.read(text, self.markers, llm=False)
        if lumi_question(text) and not ASK_NOT_ORDER.search(text) and not (got and not unread) and not REQUEST.search(text):
            return False                               # "what is my hand?": a question, answered as usual (still halted)
        rule = brain_mod.intent(text, self.markers)
        order = (got and not unread) or REQUEST.search(text) or GIVE_ME.search(text) or rule and rule[0] in MOVING_ACTIONS
        if CANCEL_TASK.search(text) and not order:
            log(f"  mission cancelled ({text!r})")
            safe(fetch.end)
            self.mission_hold, self.asked_go_on = None, False
            self.fetch_say("Okay, I've cancelled my task.", "네, 하던 일을 취소했어요.")
            return self.keep_listening() or True
        if order:                                      # anyone's new command: the mission ends, the command is done
            self.end_run(text)
            return False
        if FETCH_STOP.search(text) and len(re.findall(r"\w+", text)) <= 3 or NAME_ONLY.match(text) or HELLO_ONLY.match(text) \
                or (WAKE.search(text) and len(WAKE.sub("", text).strip(" ,.!?")) < 3):
            self.fetch_say("Hi, I'm Lumi. I stopped for you. How can I help you?",
                           "안녕하세요, 루미예요. 멈췄어요. 무엇을 도와드릴까요?")
            return self.keep_listening() or True
        return False                                   # a question: answered as usual, still halted

    def mission_left(self):
        """(task, the steps from the one running on, time) of the mission running or just ended: what "Lumi, keep
        going" does after a stop word (resume_stopped). None when no mission runs."""
        from tasks import fetch
        st = safe(fetch.state) or {}
        task = st.get("task") or {}
        if not task.get("steps") or st.get("status") not in ("running", "stopped", "failed") or \
                st.get("status") != "running" and time.time() - (st.get("since") or 0.0) > STOPPED_RECENT_S:
            return None
        n = [int(m.group(1)) for m in (re.search(r"\bstep (\d+)/\d+:", x) for x in st.get("log") or []) if m]
        return task, task["steps"][n[-1] - 1 if n else 0:], time.time()

    def resume_stopped(self, text):
        """"Lumi, keep going" / "루미 계속해" after a stop word ended a mission: its steps from the one stopped on
        start again (a stopped pick with the thing in the hand counts as done). Only with Lumi's name, not a question,
        within RESUME_S and while nothing else ran since. True if handled."""
        from assistant import steps
        from tasks import fetch
        left = getattr(self, "stopped_mission", None)      # (Lumi.__new__ in the self-checks)
        if not left or not (WAKE.search(text) and GO_ON.search(text)) or "?" in text or lumi_question(text) or \
                steps.read(text, self.markers, llm=False)[0]:
            return False
        self.stopped_mission = None
        task, todo, t = left
        st = safe(fetch.state) or {}
        if time.time() - t > RESUME_S or st.get("status") == "running" or (st.get("task") or {}).get("steps") != task["steps"]:
            return False
        if todo[0]["do"] == "pick" and self.held_now():
            todo = [{"do": "carry"}] + todo[1:]       # stopped after the grasp: finish the lift to look first
        log(f"  mission: going on after the stop: {todo}")
        try:
            fetch.run_steps(todo, say=self.fetch_say, sender=task.get("sender"))
            if todo == [{"do": "carry"}]:              # "take the cup" stopped with the cup in the hand
                self.fetch_say(f"I have {fetch.held_name()} in my hand. Where should I put it?",
                               f"{brain_mod.object_ko(fetch.held_name('ko'))} 들고 있어요. 어디에 둘까요?")
                return self.keep_listening() or True
            self.fetch_say("Okay, I'll go on with my task.", "네, 하던 일 계속할게요.")
        except fetch.FetchError as e:
            log(f"  going on refused: {e}")
            self.fetch_say(str(e), "죄송해요, 지금은 할 수 없어요.")
        return self.keep_listening() or True

    def end_run(self, text):
        """Anyone's new command while the task runner runs (a mission, a fetch): end it with one short line; the
        command is then done. Nothing held is forgotten (a "holding" state is no run)."""
        from tasks import fetch
        if self.fetch_status() != "running":
            return
        log(f"  task ended for a new command ({text!r})")
        safe(fetch.end)
        self.mission_hold, self.asked_go_on = None, False
        self.fetch_say("Okay, I've stopped my task.", "네, 하던 일을 멈췄어요.")

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
        """Halted for someone and nobody speaks: ask once whether to go on. It goes on only when told ("go on", a yes
        to that question, the dashboard), never by itself."""
        if self.mission_hold != "talk" or self.asked_go_on or time.time() - self.last_activity < TALK_ASK_S:
            return
        self.asked_go_on = True
        self.fetch_say("Can I go on with my task?", "하던 일 계속해도 될까요?")
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
        elif detour.recent():                          # the LLM reads "find a way" / "you can go now" from this
            goal = detour.recent()["goal"]
            name = brain_mod.place_said(goal) if isinstance(goal, str) else "the point I was sent to"
            en, ko = (f"My last drive, to {name}, was blocked: something was in the way and I stopped. I can try again, "
                      f"try another way, or go back.",
                      f"{name}(으)로 가다가 길이 막혀서 멈췄어요. 다시 가거나, 다른 길로 가거나, 돌아갈 수 있어요.")
        elif held:
            en, ko = f"I'm holding {held} and waiting for what to do with it.", f"{brain_mod.object_ko(fetch.held_name('ko'))} 들고 다음 지시를 기다리고 있어요."
        else:
            return ("I'm talking with you. I'm not doing any task right now, and my hand is empty.",
                    "지금은 이야기하고 있어요. 하고 있는 일은 없고, 손도 비어 있어요.")
        if held and (running or self.traveling()):
            en += f" I'm holding {held}."
            ko += f" {brain_mod.object_ko(fetch.held_name('ko'))} 들고 있어요."
        return en, ko

    # ---------- several commands in one sentence (assistant/chain.py) ----------
    def chain_busy(self):
        return self.chain_thread is not None and self.chain_thread.is_alive()

    def chain_request(self, text, plan=None):
        """Commands, questions and talk in one sentence, done in the order said (chain.plan, or `plan` as route()
        read it). True if it was one."""
        from assistant import chain
        if self.mission_running() or self.chain_busy():
            return False
        plan = plan or chain.plan(text, self.markers, NOT_A_STEP)
        if not plan:
            return False
        log(f"  chain: {[(k, w) for k, w, _ in plan]}")
        self.chain_stop.clear()
        self.chain_thread = threading.Thread(target=self.chain_run, args=(plan,), daemon=True)
        self.chain_thread.start()
        return True

    def chain_run(self, plan):
        """Each part in turn, the next once the one before is done (chain_wait). A part that can't be done says why
        (quick_command, the mission runner, the LLM's answer) and the rest goes on; after a mission part that failed,
        the parts that drive or need the hand are not done and that is said. "Stop" or new words end it."""
        from assistant import chain, steps
        from tasks import fetch
        failed = False
        for i, (kind, words, what) in enumerate(plan):
            if self.chain_stop.is_set():
                log(f"  chain stopped before {words!r}")
                return
            log(f"  chain part {i + 1}/{len(plan)}: {kind} {words!r}")
            if failed and (kind == "steps" or kind == "quick" and what[0] in chain.DRIVES | {"pick", "put", "move_object"}):
                log(f"  chain: {words!r} not done (the part before failed)")
                self.fetch_say(f"So I didn't do this part: {words}.", "그래서 이 부분은 하지 않았어요.")
                continue
            if kind == "talk":
                self.answer(words, part=True)
            elif kind == "quick":
                self.quick_command(words, what)                 # chain.plan's reading ("나 보고", the bank's)
            else:
                if {st["do"] for st in what} & DRIVE_STEPS and self.base_off("go_to"):
                    failed = True
                    continue
                problems = steps.check(what, fetch.check_hand(), self.markers)
                if problems:
                    log(f"  chain part refused: {problems}")
                    self.fetch_say(problems[0], "죄송해요, 그렇게는 할 수 없어요.")
                    failed = True
                    continue
                self.stay()
                try:
                    fetch.run_steps(what, say=self.fetch_say)
                except fetch.FetchError as e:
                    log(f"  chain part refused: {e}")
                    self.fetch_say(str(e), "죄송해요, 지금은 할 수 없어요.")
                    failed = True
                    continue
            self.chain_wait()
            if kind == "steps" and (safe(fetch.state) or {}).get("status") in ("failed", "stopped"):
                failed = True
        log("  chain done")

    def chain_wait(self, poll_s=0.3, settle_s=0.6):
        """Until the part just started is over: a trip, a pick / put, a mission or move, a wave, the head or lift."""
        from tasks import fetch
        time.sleep(settle_s)                               # the part's thread has started its work by then
        last = None
        while not self.chain_stop.is_set():                # (a follow is only the last part: not waited for)
            busy = self.traveling() or self.skill_busy() or self.busy_now == "wave" or \
                (safe(fetch.state) or {}).get("status") == "running"
            pose = safe(head.status)
            if not busy and pose is not None and pose == last:
                return
            last = pose
            time.sleep(poll_s)

    def mission_request(self, text, read=None):
        """A command of several steps (docs/17), said by voice: read back, start on yes or silence. True if it was
        one (also when refused). A single move / turn / arm / go stays with quick_command (no read-back)."""
        from assistant import steps
        read = read or read_mission(text, self.markers)
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
        self.end_run(text)
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
        held = self.held_now()
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
            self.fetch_say(f"My hand is full, I'm holding {fetch.held_name()}.", f"손에 이미 {brain_mod.object_ko(fetch.held_name('ko'))} 들고 있어요.")
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
        if stop_order(text, self.markers):            # every stop form (also "enough!", "가지 마" whole); not "he said stop"
            log("  fetch: stop by voice")
            safe(fetch.stop)
            self.act("stop", "")
            self.fetch_say("Okay, I stopped.", "네, 멈췄어요.")
        elif (FETCH_THANKS.search(text) and fetch.state().get("step") == "giving") or \
                (RECEIVE_OK.search(text) and fetch.state().get("step") == "receiving: waiting for okay"):
            safe(fetch.release_now)                    # the person has taken it
        elif status == "holding" and not (brain_mod.direct_order(text) and not brain_mod.not_an_order(text)):
            return False                               # "엄마가 내려놓을게", "put it on our list": no order to the hand
        elif status == "holding" and (FETCH_GIVE.search(text) or FETCH_PLACE.search(text)) and (
                brain_mod.FLOOR.search(text) or re.search(r"\bon (?:his|her|my|your|their|someone'?s) head\b|머리 ?위", text)):
            self.fetch_say(*(brain_mod.REFUSE_FLOOR if brain_mod.FLOOR.search(text) else brain_mod.REFUSE_HEAD))
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
            from tasks import fetch                          # the held thing named when it is known ("the white cup")
            what = (fetch.held_name(), fetch.held_name("ko")) if (safe(fetch.state) or {}).get("holding") else ("it", "")
            what = what if what[0] != "something" else ("it", "")
            ko = brain_mod.object_ko(what[1]) + " " if what[1] else ""
            said = (f"Okay, putting {what[0]} back.", f"네, {ko}제자리에 놓을게요.") if back else \
                (f"Okay, putting {what[0]} down.", f"네, {ko}내려놓을게요.")
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
                def run():                                   # the held name for the dashboard and the replies
                    from tasks import fetch
                    self.stay()                              # Greeter only: the waist turns in place, the base stays
                    fetch.pick_here(name, colour, say=self.fetch_say)
                    fetch.held_by_skill({"object": name, "colour": colour})
            else:
                said, done = (f"Okay, I'll move the {target}.", "네, 옮겨 볼게요."), ("Done.", "다 옮겼어요.")
                run = lambda: skills.move_object(name, colour)
        if confirm:
            mouth.say(said[0] if en else said[1])

        def work():
            from tasks import fetch
            try:
                run()
                mouth.say(done[0] if en else done[1])
            except fetch.Stopped:
                log(f"  {action} {target}: stopped")
            except (skills.SkillError, fetch.FetchError) as e:
                log(f"  {action} {target}: {e}")
                mouth.say(e.args[0] if en else e.args[1] if len(e.args) > 1 else "죄송해요, 지금은 할 수 없어요.")
            except (motion.MotionError, ConnectionError, OSError) as e:
                log(f"  {action} {target} stopped: {e}")
                mouth.say("I stopped my arm." if en else "팔을 멈췄어요.")
        self.skill_thread = threading.Thread(target=work, daemon=True)
        self.skill_thread.start()
        self.keep_listening()

    def arm_pose(self, target):
        """'reach': the hand out to the person (reach_out); 'fold' / 'carry' / 'ready': to look / that pose along the
        pose graph (arm_route, checked first, moved in the background); 'open' / 'close': the gripper, never opened on something held. True when
        started, False when not learned, None when refused (the reason is said)."""
        from tasks import fetch
        held = target in ("reach", "open") and self.held_now()
        if target == "open" and held:                      # the model's "let go" while holding: it would fall
            log("  open refused: holding something")
            self.fetch_say(*brain_mod.REFUSE_OPEN)
            return None
        if target in ("open", "close"):
            st = safe(gripper.open_ if target == "open" else gripper.close)
            log(f"  gripper {target}: {st}")
            return st is not None
        if target == "reach":
            return self.reach_out(held)
        self.reached_at = 0.0                              # folding: no auto fold after it
        try:
            holding = self.fetch_status() == "holding"
            seq = arm_route.plan(arm_route.HOME if target == "fold" else target, holding=holding)   # "carry", "ready"
            threading.Thread(target=safe, args=(arm_route.move, seq, None, holding), daemon=True).start()
            return True
        except arm_route.RouteError as e:
            log(f"  arm {target} refused: {e.args[0]}")
            self.fetch_say(*e.args)
            return None
        except Exception as e:
            log(f"  arm {target}: {e}")
            return False

    def reach_out(self, held):
        """"Reach out to me", "give me your hand", "손 내밀어": something in the hand = hand it over. Else toward the
        person (the tracked one, else the one the voice came from, else the voice's direction): further than
        REACH_COME_M the base comes to them first (come_to); the head turns to them; the hand further from them than
        REACH_FRONT_DEG: the waist turns first, until the hand (not the waist's front) points at them (reach_turn, Greeter only too: the base
        stays); then fetch.reach (give pose along the graph, a short checked move toward their hand). The arm folds back on "thanks" / "okay" or after REACH_HOLD_S (reach_done).
        True when started, None when refused or handed over (said)."""
        from tasks import fetch
        if held:
            self.fetch_finish("give")
            return None
        if self.skill_thread is not None and self.skill_thread.is_alive():
            self.fetch_say("I'm still busy with my arm.", "아직 팔로 하는 일이 있어요.")
            return None
        with _waist_lock:                                  # a waist coming back to the front (face) ends first
            pass
        track = None
        if self.vision:
            track = self.speaker_track()                   # who asked: the voice, the talk, the look, a raised hand
            if track is None and self.vision.anyone():     # several seen, nobody raised a hand: raised_hand said so
                return None
        if track is not None and track.distance > REACH_COME_M:   # far: go to them first, never reach from afar
            if not self.modes.patrol:                      # Greeter only: the base stays
                self.fetch_say(*COME_CLOSER_SAY)
                return None
            log(f"  reach: person #{track.id} {track.distance:.2f} m away: coming closer first")
            self.come_to(track)
            if not self.vision.present(track) or track.distance > REACH_COME_M:
                self.fetch_say(*COME_CLOSER_SAY)
                return None
        angle = track.angle if track else None              # only to someone seen: a "sure" voice was 166 deg
                                                            # off with the person in front (2026-10-28 19:13)
        hand = safe(fetch.give_bearing, default=0.0) or 0.0
        turn = reach_turn(angle, hand)
        log(f"  reach: person at {'?' if angle is None else f'{angle:+.0f}'} deg, hand at {hand:+.0f} deg, "
            f"waist turn {turn}")
        if turn is None:
            self.fetch_say(*STAND_IN_FRONT_SAY)
            return None
        if not turn:          # a waist turn takes the head along onto them (fetch._waist_to look): no head move here,
            self.turn_head(HEAD_SIGN * max(-head.YAW_LIMIT, min(head.YAW_LIMIT, angle)), force=True)   # it raced it
        self.stay()
        try:
            fetch.reach(turn, say=self.fetch_say, look=angle)
        except fetch.FetchError as e:
            log(f"  reach refused: {e}")
            self.fetch_say(e.args[0], e.args[1] if len(e.args) > 1 else "죄송해요, 지금은 할 수 없어요.")
            return None
        self.reached_at = time.time()
        return True

    def reach_done(self, text=None):
        """The hand is held out (reach_out) and the reach has ended: "thanks" / "okay" / "고마워" / "됐어" (`text`) or
        REACH_HOLD_S without one folds the arm back to look. True when it folded."""
        if not getattr(self, "reached_at", 0.0) or self.fetch_status() == "running":
            return False
        if text is None and time.time() - self.reached_at < REACH_HOLD_S or text is not None and not REACH_DONE.search(text):
            return False
        if self.fetch_status() != "done":                  # the reach failed or was stopped: the arm stays as it is
            self.reached_at = 0.0
            return False
        log(f"  reach over ({'said ' + repr(text) if text else 'timeout'}): the arm back to look")
        return bool(self.arm_pose("fold"))

    def typed(self, text):
        """Words typed in the dashboard's Command box, answered as if said: nothing of the last voice is used (its
        whisper confidence asked "say it again" for "look at front", its direction found nobody for "come to me": the
        person in view is the one, 2026-10-27)."""
        ears.last_stt.clear()
        ears.last_stt.update(language="korean" if brain_mod.HANGUL.search(text) else "english", logprob=0.0, text=text)
        self.voice_trusted = False
        self.typed_now = True                          # to Lumi, name or not (mission_talk)
        try:
            self.answer(text)
        finally:
            self.typed_now = False

    def held_now(self):
        """Something in the hand now: the hand is checked (fetch.check_hand, which also forgets a stale "holding");
        the state when it can't be. The stale state alone refused open / wave on an empty hand (2026-10-23 17:41)."""
        from tasks import fetch
        h = safe(fetch.check_hand)
        return self.fetch_status() == "holding" if h is None else bool(h)

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
        if cmd == "heard":                                # the Command box: done as if said (route(), no read-back
            self.typed(d.get("text") or "")              # for a command or chain: /tasks/parse showed it)
        elif cmd == "go":
            self.start_trip(d["marker"])
        elif cmd == "go_point":
            self.start_trip(tuple(d["point"]))
        elif cmd == "route":
            self.start_trip(d["markers"], d.get("pause", 1.0))
        elif cmd == "cancel":
            if self.mission_running():                    # running or paused: never goes on after a cancel
                from tasks import fetch
                safe(fetch.stop)
                self.mission_hold, self.asked_go_on = None, False
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
            self.stay()
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
        detour.forget()                                   # a new trip: "try again" no longer means a blocked one
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

    def moving_now(self):
        """A trip, patrol, mission or any base move runs: anyone's stop word stops it, without the wake word."""
        return self.traveling() or self.fetch_status() == "running" or \
            (safe(agv.status, default={}) or {}).get("move_status") == "running"

    def stop_heard(self):
        """While the main loop waits on a drive (come here): True if the next utterance is anyone's stop word; other
        words are answered after the drive."""
        u = self.mic.next(0.0)
        if u is None or u.seconds < 0.25:
            return False
        text = (ears.transcribe(u.mono) or "").strip()
        if text and not stop_order(text, self.markers) and mouth.own_voice(u):
            return False
        if text and stop_order(text, self.markers):     # before own_echo: "Stop." after Lumi's "I stopped" is not
            log(f"  stop word while driving: {text!r}")   # an echo
            return True
        if text and not self.own_echo(text):
            self.pending_text = text
        return False

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
        c = doa.add_sample(u.mics, me.angle - HEAD_SIGN * self.det_yaw(), doa.clip_ref(u))
        log(f"  calibration sample {self.calib_n}: person at {me.angle:+.0f} deg, {me.distance:.1f} m"
            + (f" -> calibrated {c}" if c else ""))
        self.write_calib("calibrated" if c else "collecting", c)

    # ---------- interrupting Lumi while it talks (clip mic only) ----------
    def speak_abort(self):
        """Stop talking: the person left, someone new arrived, or the visitor interrupted ("stop", a new question)."""
        return self.interrupted() or self.barge_in()

    def barge_in(self):
        from tasks import follow
        text = self.peeked_stop(lambda t: stop_order(t, self.markers) or follow.running() and follow.stop_word(t))
        if text is None:
            u = self.mic.next(0.0)
            if u is None:
                return False
            if not getattr(u, "during_speech", False) or u.seconds < 0.25:
                return False
            own = mouth.own_voice(u)                     # the speaker's sound in the clip mic (mouth.echo)
            text = (ears.transcribe(u.mono) or "").strip()
            if self.own_stop(text, u):                   # Lumi's own "stop" ("say stop to end") is no stop
                text = ""
        if follow.running() and follow.stop_word(text):   # following: the base stops now, "stop" is answered next
            follow.stop()                                  # (anyone's: safety, never dropped as an echo)
            self.pending_text = "stop"
            return True
        if text and stop_order(text, self.markers):      # anyone's "stop" / "멈춰", one word too: motion stops now,
            log(f"  interrupted by a stop word: {text!r}")   # answered next; before every echo filter (at worst Lumi
            self.act("stop", "")                           # stops once for its own word)
            self.pending_text = text
            return True
        if own:
            log(f"  ignored own voice (sound match {mouth.last_echo:.2f})")
            return False
        if not text or self.own_echo(text):
            return False
        if (mouth.last_echo or 0) >= ECHO_LIKELY and self.own_echo(text, share=ECHO_LIKELY_SHARE):
            log(f"  ignored own voice (sound match {mouth.last_echo:.2f}, words): {text!r}")
            return False
        if follow.running() and not self.followed_speaks(u):
            log(f"  following: not the person I follow, ignored: {text!r}")
            return False
        if not ears.understood(BARGE_IN_LOGPROB):        # unclear while Lumi talks = mostly Lumi's own voice
            log(f"  ignored while talking (unclear): {text!r}")
            return False
        if call_only(text):                              # "Hi Lumi" / "루미야" while Lumi answers (another visitor):
            log(f"  called while talking: {text!r} - answer finished first, then turn to them")   # never cut for it
            self.pending_text, self.pending_call = text, (text, u)
            return False
        if seeing.recheck(text):                         # "Really?", "진짜?", "Now?" right after a seeing answer
            log(f"  interrupted by a check of what I see: {text!r}")
            self.pending_text = text
            return True
        if brain_mod.is_backchannel(text) and "?" not in text and not THANKS.search(text) and \
                (brain_mod.UNDERSTOOD.search(text) or not brain_mod.is_closing(text)):
            log(f"  back-channel while talking: {text!r} - go on")   # "uh huh", "I see", "그렇구나": listening
            return False
        if brain_mod.is_closing(text):
            log(f"  interrupted: {text!r} - stop talking, listen")
            return True
        if len(text.split()) >= 2 or brain_mod.WAKE_WORD_RE.search(text):
            log(f"  interrupted by a new question: {text!r} (sound match {mouth.last_echo and round(mouth.last_echo, 2)})")
            self.pending_text = text
            return True
        return False

    def peeked_stop(self, is_stop):
        """A stop word in the last seconds the clip mic heard while Lumi talks (mic.peek()), before that utterance
        ends: Lumi's own voice in the clip mic keeps it going (a 17.9 s answer was stopped only at its end, 2026-10-27).
        Not Lumi's own sound (mouth.own_voice) or a stop word Lumi says itself. The words heard, else None."""
        u = getattr(self.mic, "peek", lambda: None)()
        if u is None or mouth.own_voice(u):
            return None
        text = (ears.quick(u.mono) or "").strip()
        if not text or not is_stop(text) or not ears.heard_clearly(BARGE_IN_LOGPROB) or self.own_stop(text, u):
            return None
        log(f"  stop word while talking: {text!r}")
        return text

    @staticmethod
    def own_stop(text, u):
        """Every word heard is in what Lumi was saying then (its own "stop" picked up by the clip mic)."""
        said = set(re.findall(r"\w+", mouth.saying(time.time() - u.seconds - 1.0).lower()))   # just heard; the
        # clip mic lags up to 1 s
        words = set(re.findall(r"\w+", (text or "").lower()))
        return bool(words) and words <= said

    @staticmethod
    def own_echo(text, seconds=30.0, share=0.6):
        """The clip mic also hears Lumi: ignore what overlaps with what it said in the last `seconds`. A word counts
        when said, or when it starts a said word or a said word starts it ("temperature" / "temperatures", "over" /
        "overcast": whisper cuts and bends the echo)."""
        said = set(re.findall(r"\w+", mouth.recent_speech(seconds).lower()))
        words = re.findall(r"\w+", text.lower())

        def heard(w):
            return w in said or len(w) >= 4 and any(len(s) >= 4 and (s.startswith(w) or w.startswith(s)) for s in said)
        return bool(words) and sum(map(heard, words)) / len(words) >= share

    # ---------- interrupts ----------
    def interrupted(self):
        """Stop listening/speaking: the person left. Never for a newcomer: the answer is finished first, then
        someone who waves or calls is turned to (owner, 2026-10-23)."""
        if not self.vision:
            return False
        return self.current is not None and not self.vision.present(self.current)

    # ---------- behaviour ----------
    def greet(self, track):
        """Someone waved at Lumi: a greeting for someone new, a short welcome back for someone known."""
        track.greeted = True
        who, gone = self.vision.know(track)
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

    def waver(self):
        """The person in the greeting zone not greeted yet who waves at Lumi (a hand up, facing it) in two looks
        WAVE_CHECK_S apart, or None. The pose net runs only while someone waits in the zone."""
        t = self.vision.to_greet()
        now = time.time()
        if t is None or now - getattr(self, "wave_checked", 0.0) < WAVE_CHECK_S:
            return None
        self.wave_checked = now
        from vision import scene
        frames = safe(scene.snapshot, (self.vision.camera,), default=[]) or []
        up = [w for w in (safe(hands_up, frames, default=[]) or []) if self.vision.near_angle(w, WAVE_MATCH_DEG) is t]
        seen, self.wave_seen = getattr(self, "wave_seen", None), (t.id, now) if up else None
        if up and seen and seen[0] == t.id and now - seen[1] <= 2.5 * WAVE_CHECK_S:
            log(f"WAVE from person #{t.id} at {t.distance} m, {t.angle:+.0f} deg")
            self.wave_seen = None
            return t
        return None

    def warm_llm(self):
        """brain.warm in the background (markers and the task state are read there, listening starts at once)."""
        threading.Thread(target=lambda: safe(lambda: self.brain.warm(self.markers, self.now_doing()[0] + memory.arm_line())),
                         daemon=True).start()

    def talk_turn(self):
        """Listen once; answer if something was said. Returns True if the visitor spoke."""
        if self.pending_text:                              # asked while Lumi was talking
            text, self.pending_text = self.pending_text, None
            call, self.pending_call = getattr(self, "pending_call", None), None
            if call and call[0] == text:                   # a call while Lumi talked: turn to the caller first
                self.who_spoke(call[1], text)
            self.answer(text)
            return True
        self.warm_llm()                                    # the LLM's prompt start cached while they speak
        text, u = ears.listen(wait_s=4.0, on_start=lambda: log("  hearing speech"), abort=self.interrupted, full=True)
        if text and mouth.own_voice(u) and not stop_order(text, self.markers):   # the speaker's sound in the clip mic
            # (mouth.echo); a stop word is never dropped as Lumi's own voice
            log(f"  ignored own voice (sound match {mouth.last_echo:.2f}): {text!r}")
            text = None
        if text and self.own_echo(text) and not stop_order(text, self.markers) and \
                not sing.picked(text, self.brain.history[-1][1] if self.brain.history else "") and \
                (u is None or (u.during_speech if u.source == "clip" else len(text.split()) <= 2)):
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
            from tasks import follow                       # following: "okay" was to the follow, no goodbye
            here = (self.current is not None or self.vision is None or self.vision.anyone_near()) and not follow.running()
            log(f"  silence after a closing word - conversation over{'' if here else ', nobody here or following: no goodbye'}")
            self.end_conversation("okay", quiet=not here)
            return False
        if not text or self.interrupted():
            if not self.interrupted():
                log(f"  heard nothing (mic noise {ears.last.get('noise')}, threshold {ears.last.get('threshold')}, "
                    f"loudest {ears.last.get('peak')}{', ' + ears.last_stt['dropped'] if ears.last_stt.get('dropped') else ''})")
            return False
        from tasks import follow
        self.last_u = u                                    # follow_me: was "follow me" said into the clip mic?
        if self.follow_filter(text, u):                    # following: only the followed person is listened to
            return True
        if not follow.running():                           # following: the head stays on the followed person
            self.who_spoke(u, text)
        self.answer(text)
        if self.mission_hold == "talk" and not self.asked_go_on and self.mission_running():
            self.asked_go_on = True                        # answered while halted for them: may I go on?
            self.fetch_say("Can I go on with my task?", "하던 일 계속해도 될까요?")
        return True

    def _doa_sample(self, mics, true_deg, ref=None):
        try:
            c = doa.add_sample(mics, true_deg, ref)
            if c:
                log(f"sound direction calibrated: {c}")
        finally:
            _doa_fit.release()

    def say_stuck(self):
        if self.patrol and self.patrol.stuck:
            target, self.patrol.stuck = self.patrol.stuck, None
            why, self.patrol.stuck_why = self.patrol.stuck_why, None
            if why:
                mouth.say(why[0] if self.lang == "en" else why[1])
                return
            if self.patrol.once:                       # kept for "try again", "go around it", "go back" (detour)
                from tasks import fetch
                to = target if isinstance(target, str) else list(target)
                detour.remember(to, [{"do": "go", "to": to}], fetch._task["trip_from"] and list(fetch._task["trip_from"]))
            if self.lang == "en":
                name = "my charging dock" if target == "home" else brain_mod.place_said(target) \
                    if isinstance(target, str) else "there"
                mouth.say(f"Sorry, I can't find a way to {name}. Something may be blocking the path.")
            else:
                name = "충전소로" if target == "home" else f"{brain_mod.place_said(target)}(으)로" \
                    if isinstance(target, str) else "그곳으로"
                mouth.say(f"죄송해요, {name} 가는 길을 못 찾겠어요. 뭔가 길을 막고 있는 것 같아요.")

    def detour(self, how, speak=True):
        """"try again" / "back up and try again" / "go around it" / "go back" after a blocked drive (assistant/detour.py):
        said in one line, then driven by the task runner (tasks/fetch.detour: the arm in look, STOP and pause work as
        on a mission). speak False: the LLM has said its own words. True when handled."""
        from tasks import fetch
        stuck = detour.recent()
        if stuck is None:
            return False
        if self.base_off("go_to"):
            return True
        if how == "back":
            if not stuck.get("start"):
                self.fetch_say(*detour.NO_START)
                self.keep_listening()
                return True
            steps, tries = [{"do": "go", "to": stuck["start"]}], 0
        else:
            steps, tries = stuck["rest"], stuck.get("tries", 0) + 1
        if self.patrol:
            self.patrol.pause()
            self.patrol.mode = "done"
        self.stay()
        log(f"  detour {how}: {steps}")
        try:
            fetch.detour(steps, how, say=self.fetch_say, tries=tries)
        except fetch.FetchError as e:
            self.fetch_say(e.args[0], e.args[1] if len(e.args) > 1 else "죄송해요, 지금은 할 수 없어요.")
            return True
        if speak:
            self.brain.history.append((self.heard, f"ACTION: detour {how}"))
            self.fetch_say(*detour.SAY[how])
        return True

    def followed_speaks(self, u):
        """While following: does the voice come from the person followed (the sound direction against their angle
        now, within FOLLOW_VOICE_DEG)? False when it can't tell (not calibrated, unsure, not seen)."""
        from tasks import follow
        if getattr(u, "source", None) == "clip":           # no direction: theirs if "follow me" came through it too
            return getattr(self, "follow_by_clip", False)
        want = follow.followed_angle()
        if want is None or u is None or getattr(u, "mics", None) is None:
            return False
        cal = doa.load_calib()
        if not cal["fitted"]:
            return False
        ang, conf, _ = doa.estimate(u.mics, cal)
        if conf < DOA_MIN_CONF:
            return False
        heard = HEAD_SIGN * self.det_yaw() + ang
        return abs((heard - want + 180.0) % 360.0 - 180.0) <= FOLLOW_VOICE_DEG

    def follow_filter(self, text, u):
        """While following, words not from the followed person: a stop word still stops the base (safety); anything
        else is not acted on, at most one short line every FOLLOW_SORRY_S, the head not turned. True if dropped here."""
        from tasks import follow
        if not follow.running() or self.followed_speaks(u):
            return False
        if follow.stop_word(text) or stop_order(text, self.markers):
            log(f"  follow: stop word from someone else {text!r} - stopped")
            follow.stop()
            self.stop_all()
            return True
        log(f"  follow: not the person I follow, not acted on: {text!r}")
        if time.time() - getattr(self, "sorry_at", 0.0) > FOLLOW_SORRY_S:
            self.sorry_at = time.time()
            mouth.say("Sorry, I'm following someone right now." if mouth.lang_of(text) == "en"
                      else "지금은 다른 분을 따라가는 중이에요.")
        return True

    def who_spoke(self, u, text=None):
        """Use the sound direction: pick the visible person who spoke; meanwhile collect calibration samples. Someone
        else near the voice takes the talk over (and the head) only with a call, a stop word or an order in `text`;
        other words keep the focus on the person talked with."""
        if not self.vision or u is None:
            return
        self.voice_trusted = False                         # set again below only from this turn's own sound
        yaw = self.det_yaw()
        only = self.vision.only_person()
        if only is not None and only is self.current and only.distance <= 1.6 and u.seconds >= 0.8:
            # the only person in view is the one we talk to, close by: their angle is the truth
            if _doa_fit.acquire(blocking=False):          # the refit takes seconds (a grid over all samples): in the
                threading.Thread(target=self._doa_sample, args=(u.mics, only.angle - HEAD_SIGN * yaw, doa.clip_ref(u)),
                                 daemon=True).start()       # background, never before the answer (it held answers ~15 s)
            return
        cal = doa.load_calib()
        if not cal["fitted"]:
            return
        ang, conf, _ = doa.estimate(u.mics, cal, doa.clip_ref(u))   # with the clip mic: its wearer's voice
        trusted = conf >= voice_min_conf(u)
        log(f"  voice at {HEAD_SIGN * yaw + ang:+.0f} deg (confidence {conf:.2f}{doa.clip_note(u.mics, doa.clip_ref(u))}"
            f"{'' if trusted else ', not trusted'})")
        if not trusted:
            return
        self.voice_angle, self.voice_trusted = HEAD_SIGN * yaw + ang, True   # "이쪽 봐": this voice, also out of view
        self.voice_at = time.time()
        t = self.vision.near_angle(HEAD_SIGN * yaw + ang)
        if t is not None and t is not self.current:
            cur = self.current
            rule = text and brain_mod.intent(text, self.markers)   # an order; a weather or web question is no
            if text and cur is not None and self.vision.present(cur) and not (    # order ("nice weather today")
                    WAKE.search(text) or stop_order(text, self.markers) or rule and rule[0] not in ("weather", "search")):
                log(f"  voice near person #{t.id}, no call, stop or order: focus stays on #{cur.id}")
                return
            log(f"  voice from {HEAD_SIGN * yaw + ang:+.0f} deg: person #{t.id} is speaking")
            t.greeted = True
            self.current = t
            if getattr(self, "look_me", None) is not None:   # a "look at me" hold was for the one before
                self.looked_at, self.look_me = 0.0, None
            self.face(t)

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
        if action == "weather":                            # "내일 비 와?" after Jeju's weather: Jeju
            target = self.brain.weather_place(target, text)
            days = self.brain.weather_on(text)             # "and next Monday?": that day only, at the same place
        if action == "search" and private_ask(text):        # never looked up, whoever it is about
            log("  search refused: a person's private details")
            mouth.say(PRIVATE_SAY["en" if en else "ko"])
            return
        found = {}                                         # fetched while "Let me check." is said (~1 s)
        use_openai = action == "search" and web.openai_ready()
        if use_openai:                                     # OpenAI's web search answers, the free search if it can't
            fetch = threading.Thread(target=lambda: found.update(said=web.openai_answer(text, self.brain.history)),
                                     daemon=True)
        else:
            fetch = threading.Thread(target=lambda: found.update(
                facts=web.weather_on(web.weather(target), days) if action == "weather" else web.search(target)), daemon=True)
        fetch.start()
        if not use_openai:
            # the free search: the answer is fetched and made while "Let me check." plays (~1 s sooner)
            said = mouth.say_stream(self._looked_up(text, action, target, fetch, found), abort=self.speak_abort)
            log(f"lumi ({time.time() - (t0 or time.time()):.1f} s): {said}")
            if self.current is None:
                self.voice_until = time.time() + VOICE_SESSION_S
            return
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

    def _looked_up(self, text, action, target, fetch, found):
        """'Let me check.', then the answer from the facts the fetch thread finds, sentence by sentence."""
        en = self.lang == "en"
        yield "Let me check." if en else "확인해 볼게요."
        fetch.join()
        facts = found.get("facts")
        log(f"  {action} {target!r}: {(facts or 'NO INTERNET')[:120]}")
        if facts is None:
            yield ("Sorry, I'm not connected to the internet right now, so I can't look that up."
                   if en else "죄송해요, 지금은 인터넷에 연결되어 있지 않아서 찾아볼 수 없어요.")
            return
        asked = f"{text} (the weather)" if action == "weather" else text    # misheard words ("원하는 날씨가 어때요?")
        for i, sentence in enumerate(self.brain.respond_from(asked, facts)):   # made the LLM say it found nothing
            yield from mouth.first_parts(sentence) if i == 0 else [sentence]   # the voice starts sooner

    def keep_listening(self):
        if self.current is None:
            self.voice_until = time.time() + VOICE_SESSION_S
        self.last_activity = time.time()

    def end_conversation(self, text=None, quiet=False):
        """Say a goodbye that fits the conversation (none when `quiet`: nobody to say it to), forget it, and drive on if
        Lumi was on the way."""
        bye = "" if quiet else self.brain.farewell(text, self.lang)
        if bye:
            log(f"  goodbye: {bye}")
        if bye and text and BYE_WAVE.search(text) and self.current is not None and self.vision and self.vision.present(self.current):
            threading.Thread(target=self.wave, kwargs={"quiet": True}, daemon=True).start()   # only if safe: else no arm
        if bye:
            mouth.say(bye, abort=self.speak_abort)
        self.current, self.voice_until, self.closing_pending = None, 0.0, None
        self.brain.reset()
        if not quiet:                                # a goodbye ends a held look; silence keeps it (LOOK_HOLD_S)
            self.looked_at = 0.0
        self.turn_head(0, head.HEAD_REST_PITCH)      # waits while a look is held
        self.waist_rest()
        if self.traveling():
            log("  conversation over - driving on")
            self.patrol.wait_until = time.time() + 0.5

    def go_offered(self, place):
        """Drive to a place the visitor just agreed to; the conversation stays open."""
        en = self.lang == "en"
        self.brain.history.append((self.heard, f"ACTION: go_to {place}"))
        if self.base_off("go_to"):
            return
        self.start_trip(place)
        name = brain_mod.place_said(place)
        mouth.say(f"Okay, I'm going to {name}." if en else f"네, {name}로 갈게요.")
        self.keep_listening()

    def quick_command(self, text, rule=None):
        """A command the keyword rules recognise for sure: confirm with a ready phrase and act, no LLM wait. rule:
        route's / chain.plan's reading when it has one (the intent bank's, a Korean -고 part), else brain.intent."""
        rule = tuple(rule) if rule else brain_mod.intent(text, self.markers)
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
        if not rule or rule[0] not in QUICK_RULES:
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
            self.head_rest()
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
            mouth.say(LIMIT_SAY[limited][0 if en else 1] if limited else ("Okay." if en else "네."))
            return True
        if action == "fetch":
            self.fetch_request(target)
            return True
        if action == "waist":
            limited = self.waist(target)
            mouth.say(LIMIT_SAY[limited][0 if en else 1] if limited else ("Okay." if en else "네."))
            return True
        if action == "come_back":
            self.come_back(speak=True)
            return True
        if action == "come":
            self.come_to(self.current, say=True)               # drives first, says "I'm coming" as it starts
            return True
        if action == "follow":
            self.follow_me()
            return True
        if action in ("move", "turn"):
            d, n = (target.split() + ["", ""])[:2]
            if action == "turn":
                say_en = "Okay, turning around." if d == "around" else f"Okay, turning {d}."
                say_ko = "네, 뒤로 돌게요." if d == "around" else ("네, 왼쪽으로 돌게요." if d == "left" else "네, 오른쪽으로 돌게요.")
                if n == "360":
                    say_en, say_ko = "Okay, turning all the way around.", "네, 한 바퀴 돌게요."
            else:
                exact = driving.amount(brain_mod._norm(text))[1]   # "about 5 centimetres" for "a tiny bit"
                say_en, say_ko = (driving.say_move(d, float(n), exact, lang) for lang in ("en", "ko"))
            if self.move_by(action, target):
                mouth.say(say_en if en else say_ko)
            return True
        if action == "arm":
            done = {"open": ("Okay, opening my hand.", "네, 손을 펼게요."), "close": ("Okay, closing my hand.", "네, 손을 쥘게요.")}
            words = None
            if target in done:                             # said while the gripper already moves
                words = threading.Thread(target=mouth.say, args=(done[target][0] if en else done[target][1],), daemon=True)
                words.start()
            ok = self.arm_pose(target)
            if words:
                words.join()
            if ok:
                if target in ("fold", "carry", "ready"):
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

    def answer(self, text, part=False):
        """_answer, and what was said by code in that turn (a refusal, a fixed reply, a place not on the map) kept in
        the talk like the model's answers: "why?" / "really?" / "왜요?" next goes on from it."""
        h, n, t0 = self.brain.history, len(self.brain.history), time.time()
        self._answer(text, part)
        if h is self.brain.history and len(h) == n:        # nothing kept by the turn, and the talk did not end
            keep_said(self.brain, text, mouth.recent_speech(time.time() - t0))

    def _answer(self, text, part=False):
        """Stream the LLM reply: act on the action line, speak sentence by sentence.
        Clear commands (go home, go to p1, come here, be quiet...) are done at once without the LLM.
        part: one part of a sentence of several (chain_run); otherwise a chain still running ends here."""
        if not part and self.chain_busy() and not brain_mod.is_backchannel(text):
            log("  chain: new words, the rest is not done")
            self.chain_stop.set()
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
        memory.heard(claimed_name(text), self.current)    # who this talk is with (assistant/memory.py)
        mem = None if self.mission_running() else memory.reply(text, self.lang, history=self.brain.history)   # "do you remember ...?"
        if mem:                                            # before self_correct: "no" answers "Do you mean ...?"
            log(f"  memory: {mem}")
            self.brain.history.append((text, f"ACTION: none -\n{mem}"))
            mouth.say(mem, abort=self.speak_abort)
            self.keep_listening()
            return
        fixed = text if self.mission_running() else brain_mod.self_correct(text, self.markers)   # "go to start, no, end"
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
        if self.resume_stopped(text):                      # "Lumi, keep going" after a stop word ended a mission
            return
        if NAME_ONLY.match(text):                           # just "Lumi?": they want attention
            mouth.say("Yes?" if self.lang == "en" else "네?")
            self.keep_listening()
            return
        from tasks import fetch                            # the way it goes: route(), as the dashboard's Command box
        kind, data = route(text, self.markers, self.brain, self.held_now,
                           seen=lambda x: seeing.answer(x, self.lang, slow_line=mouth.say), last=last, chain_ok=not part and not self.mission_running() and not self.chain_busy())
        if kind == "stop":
            self.stop_all(text)                            # "stop", "stop, where are you going?": stop first, always
            return
        if self.pointed_drive(text):                       # "go there" / "저기로 가" with a pointing arm (pointing.py)
            return
        if kind == "detour" and self.detour(data):         # after a blocked drive: "try again", "다른 길로 가 봐"
            return
        if kind == "chain" and self.chain_request(text, data):   # "look at me and wave", "go to p5 and tell me the weather"
            return
        if kind == "seeing":                               # "do you see a cup?", "what am I holding?"
            log(f"  seeing: {data}")
            self.brain.history.append((text, f"ACTION: none -\n{data}"))   # "and you?" / "why?" next has the turn
            memory.note_seen()                             # what is in view now is kept (48 h), in the background
            mouth.say(data)
            self.keep_listening()
            return
        if HAND_EMPTY_SAID.search(text) and self.fetch_status() != "running":   # "there is nothing in your hand"
            held = self.held_now()                         # checked again (AI_1, the torso camera), never just agreed
            log(f"  told my hand is empty: checked, holding {held}")
            self.brain.history.append((text, "ACTION: none -"))
            self.fetch_say(*(("I still feel something in my hand.", "아직 손에 뭔가 있는 것 같아요.") if held else
                             ("You're right, my hand is empty.", "맞아요, 손이 비어 있어요.")))
            self.keep_listening()
            return
        if kind == "status":                               # what am I doing / where am I going
            en, ko = self.now_doing()
            log(f"  status: {en}")
            mouth.say(en if self.lang == "en" else ko)
            self.keep_listening()
            return
        if kind in ("correction", "hand") and self.hand_command(text):   # "take this from me", "put it there"
            return
        if kind == "mission" and self.mission_request(text, data):   # several steps: before give / place while holding
            return
        if self.fetch_voice(text):                         # before the closing words: "thank you" while giving
            return
        if not (kind == "quick" and data and data[0] == "arm"):
            self.reach_done(text)                          # "okay, thanks" with the hand held out: the arm back to look
        place = consent_place(text, self.brain, self.markers)
        if place:                                          # "p3로 갈 수 있어요?" ... "그럼 가 보세요."
            self.go_offered(place)
            return
        if self.fetch_status() not in ("running", "holding") and empty_hand_request(text):   # nothing held
            mouth.say(EMPTY_HAND_SAY[self.lang])
            self.keep_listening()
            return
        if kind == "end":
            self.end_conversation(text)                    # "okay, bye", "I have to go", "수고하세요": done
            return
        # fate "close" ("okay", "thanks", "됐어요"): the LLM below reads it with the talk before (its action end ends
        # the talk); when the talk goes on, silence ends it (closing_pending, set after the reply)
        fate = talk_fate(text)
        if kind == "sing":                                 # "sing a song", "노래 불러 줘", after a song "another one"
            self.sing_song(text)
            return
        if kind in ("quick", None) and self.quick_command(text, data if kind == "quick" else None):   # None: an
            # unknown place is still said here
            log(f"  done at once ({time.time() - t:.1f} s)")
            return
        bank = sing.bank_read(text, last) if kind is None else None   # a song or the songs by meaning (song_bank.py)
        if bank == "sing":
            log(f"  song bank: sing ({time.time() - t:.2f} s)")
            self.sing_song(text)
            return
        if bank == "list":
            say = sing.list_reply(self.lang)
            self.brain.history.append((text, f"ACTION: none songs\n{say}"))
            log(f"  song bank: the songs ({time.time() - t:.2f} s)")
            mouth.say(say, abort=self.speak_abort)
            self.keep_listening()
            return
        from assistant import quick_answers                # "who made you?", "몇 살이에요?": a fact at once
        say = quick_answers.answer(text, self.lang, self.brain.history) if kind is None else None
        if say:
            self.brain.history.append((text, f"ACTION: none -\n{say}"))   # "why?" / "really?" next: the LLM has it
            log(f"  quick answer ({time.time() - t:.2f} s): {say}")
            mouth.say(say, abort=self.speak_abort)
            self.keep_listening()
            return
        if self.brain.is_lookup_follow_up(text):           # "tell me more" about something looked up just now
            self.look_up(text, "search", self.brain.search_query(text), t)
            return
        about, repeating = self.brain.topic(text), self.brain.again(text)
        view = seeing.facts_for(text)
        if view:
            memory.note_seen()                             # a camera summary for the LLM: kept too
        gen = self.brain.respond_stream(text, self.markers, now=self.now_doing()[0] + memory.arm_line() + view +
                                         battery.fact_for(text))
        head_ = next(gen)
        log(f"  action {head_['action']} {head_['target']} ({time.time() - t:.1f} s)")
        if self.base_off(head_["action"], head_["target"]) or \
                needs_arm(head_["action"], head_["target"]) and self.arm_off():   # the model's "Okay" is not said
            gen.close()
            return
        if head_["action"] == "come":
            gen.close()
            self.come_to(self.current, say=True)
            return
        if head_["action"] == "follow":
            gen.close()
            self.follow_me()
            return
        if head_["action"] == "search" and lookup_refused(self.brain, head_["target"], about, text):
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
            self.head_rest()
            return
        if head_["action"] in ("receive", "give", "place"):  # the model read a hand request the rules missed
            gen.close()
            from tasks import fetch
            held = self.held_now()
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
            limited = self.act(head_["action"], head_["target"])
            if head_["action"] in ("look", "lift") and limited in LIMIT_SAY:   # at its end: said so, not the model's
                gen.close()                                                       # "okay"
                said = LIMIT_SAY[limited][self.lang != "en"]
                mouth.say(said)
                keep_said(self.brain, text, said)
                self.keep_listening()
                return
        first = next(gen, None)
        log(f"  first sentence after {time.time() - t:.1f} s")
        promise = brain_mod.promised(first) if head_["action"] == "none" and \
            not (brain_mod.not_an_order(text, asked=False) and brain_mod.promised(first) == "wave") else None   # not
            # "만약 boss 오면 … wave 해" -> "오시면 흔들게요": no wave now
        if promise == "sing" or promise == "wave" and not self.arm_off():   # the reply says it: Lumi does it
            log(f"  the reply promises {promise}: done")
            if promise == "sing":
                gen.close()
                self.sing_song(text)
                return
            self.act("wave", "")
        if promise == "motion":                            # "Okay, I'll follow you!" under the action none: ask
            gen.close()
            log(f"  the reply promises a move the action line did not ({first[:60]!r}): asked")
            say = "Sorry, what would you like me to do?" if self.lang == "en" else "죄송해요, 무엇을 해 드릴까요?"
            self.brain.history.append((text, f"ACTION: none -\n{say}"))
            mouth.say(say)
            self.keep_listening()
            return
        if head_["action"] in ("none", "sing") and not repeating and look_up_unsure(about, first, text):
            gen.close()                                    # the model does not know: look it up instead
            log(f"  not sure ({first[:60]!r}) - looking it up")
            self.look_up(text, "search", self.brain.search_terms(text), t)
            return
        said = mouth.say_stream(itertools.chain([first] if first else [], gen), abort=self.speak_abort)
        log(f"lumi ({time.time() - t:.1f} s, voice after {mouth.last_voice - t:.1f} s): {said}")
        if head_["action"] == "end" and fate == "close" and not kept_goodbye(said):
            head_["action"] = "none"                       # "Okay, thanks." -> "You're welcome.": no goodbye said
        elif head_["action"] == "none" and fate == "close" and kept_goodbye(said):
            head_["action"] = "end"                        # "thanks, that's all" -> "Have a great day!": it took leave
        if head_["action"] in ("end", "go_to"):
            self.current, self.voice_until = None, 0.0     # stay quiet with this person until a new visit
            if head_["action"] == "end":                   # the model took leave: head and waist to rest
                self.head_rest()
        elif self.current is None:
            self.voice_until = time.time() + VOICE_SESSION_S
        if fate == "close" and head_["action"] == "none":   # "thanks" taken as heard: silence now ends the talk
            log("  closing word - waiting a moment")
            self.closing_pending = time.time()

    # ---------- wake word ----------
    def check_wake(self):
        """Idle or driving: is someone calling "Lumi" / "Hi Lumi" / "Hey Lumi" (or just "Hi" / "Hey")? Handles it."""
        from tasks import follow
        if follow.running():                                  # following: talk_turn listens to the followed person only
            return False
        u = self.mic.next(0.0)
        if u is None or not (0.3 <= u.seconds <= WAKE_MAX_S):
            return False
        during = getattr(u, "during_speech", False)     # said while Lumi talks: only a stop word counts
        text = ears.transcribe(u.mono)
        if text and stop_order(text, self.markers) and self.moving_now():   # never dropped as Lumi's own voice
            log(f"  stop word while moving: {text!r} (no wake word needed)")   # "Stop." on a trip went on, 2026-10-23
            self.stop_all()
            return True
        if during:
            return False
        m = WAKE.search(text or "")
        if not m and HELLO_ONLY.match(text or ""):          # a plain "Hi!" / "Hey" said on its own
            m = HELLO_ONLY.match(text)
        if not m:
            if text:
                log(f"  heard {text!r} (no wake word)")
            return False
        rest = re.sub(r"^(?:야|아)(?![가-힣])", "", text[m.end():]).strip(" ,.!?")   # "루미야, 뭐 보여?"
        lang = ears.heard_lang("ko" if re.search(r"[가-힣]", text) else "en")
        self.lang = lang
        cal = doa.load_calib()
        ang, conf, raw = doa.estimate(u.mics, cal, doa.clip_ref(u))   # with the clip mic: its wearer's voice
        trusted = cal["fitted"] and conf >= voice_min_conf(u)
        robot_angle = HEAD_SIGN * self.det_yaw() + ang
        self.voice_angle, self.voice_trusted = robot_angle, trusted
        if trusted:
            self.voice_at = time.time()
        log(f"WAKE {text!r}: voice at {robot_angle:+.0f} deg (confidence {conf:.2f}, "
            f"{'calibrated' if cal['fitted'] else 'NOT calibrated'}{doa.clip_note(u.mics, doa.clip_ref(u))})")
        if self.traveling():                                  # someone calls while driving: stop for them
            log("  called while driving - stop and talk, then drive on")
            self.patrol.pause()
        self.quiet_until = 0.0
        self.brain.reset()
        self.closing_pending = None
        command = rest if len(rest) > 2 else text if re.search(r"how are you", text, re.I) else ""   # answered
        target = self.find_caller(robot_angle, trusted)
        if target is not None:
            target.greeted = True
            self.current = target
            self.face(target)
        if not command:                                       # just "Hi Lumi": a short answer, then listen
            mouth.say(WAKE_REPLY[lang])
        self.voice_until = time.time() + VOICE_SESSION_S
        self.last_activity, self.prompts = time.time(), 0
        if command:                                           # "Hi Lumi, go home": do it at once, no greeting
            self.answer(command)
        return True

    def speaker_track(self):
        """Who gave the order ("come here", "give me your hand", "follow me"), in this order, never a guess:
        1) this turn's voice direction when sure (find_caller: the person there, else it turns there and looks);
        2) the person talked with, still tracked (at any distance); 3) the person the head looks at (GAZE_MATCH_DEG:
        "look at me" left it on them); 4) the one person tracked; 5) else the one who raises a hand when asked
        (raised_hand). A voice direction that is not sure is never used: it was off by up to 90 deg (2026-10-28).
        None when nobody can be told."""
        if not self.vision:
            return None
        if self.voice_trusted:
            t = self.find_caller(self.voice_angle, True)
            if t is not None:
                return t
        if self.current is not None and self.vision.visible(self.current):
            return self.current
        t = self.vision.near_angle(HEAD_SIGN * self.det_yaw(), GAZE_MATCH_DEG)
        if t is not None:
            log(f"  speaker: person #{t.id}, the one I look at")
            return t
        return self.vision.only_seen() or self.raised_hand()

    def raised_hand(self):
        """Several people in view and nothing tells who spoke: they are asked to raise a hand; the tracked person whose
        hand is up in two looks is taken. None (said) when nobody does in RAISE_HAND_S; None at once when nobody is
        tracked (the caller says it can't see them)."""
        if not self.vision.anyone():
            return None
        self.fetch_say(*RAISE_HAND_SAY)
        from vision import scene
        ups, end = {}, time.time() + RAISE_HAND_S
        while time.time() < end:
            frames = safe(scene.snapshot, (self.vision.camera,), default=[]) or []
            for w in safe(hands_up, frames, default=[]) or []:
                t = self.vision.near_angle(w, WAVE_MATCH_DEG)
                if t is not None:
                    ups[t.id] = ups.get(t.id, 0) + 1
                    if ups[t.id] >= 2:
                        log(f"  speaker: person #{t.id}, hand raised at {t.angle:+.0f} deg, {t.distance:.2f} m")
                        return t
            time.sleep(WAVE_CHECK_S)
        log("  speaker: nobody raised a hand")
        self.fetch_say(*WHO_ASKED_SAY)
        return None

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
        w = waist_turned() if abs(robot_angle) > view and self.modes.patrol else None
        if w is not None and waist_home("turning to a caller", fold=True):
            log(f"  caller outside the camera ({robot_angle:+.0f} deg): turning toward the voice")
            self.turn_head(0, force=True)                     # a call or an order: also over a held look
            safe(agv.turn_by, math.radians(robot_angle + w))      # from the base's front: the waist is there now
            t0 = time.time()
            time.sleep(0.6)
            while time.time() - t0 < 8 and (safe(agv.status, default={}) or {}).get("move_status") == "running":
                time.sleep(0.2)
            time.sleep(0.8)                                   # let detection catch up
            self.voice_angle = 0.0
            t = self.vision.near_angle(0.0, 35) or self.vision.only_person()
            log("  after the turn: " + (f"person #{t.id} at {t.angle:+.0f} deg, {t.distance:.2f} m" if t else "nobody ahead"))
            return t
        was = self.det_yaw()
        self.turn_head(HEAD_SIGN * max(-head.YAW_LIMIT, min(head.YAW_LIMIT, robot_angle)), force=True)
        if self.vision.camera != "head":
            return None
        time.sleep(1.5)                                       # the camera turned with the head: look again
        t = self.vision.near_angle(robot_angle)
        if t is None:                                         # nobody there (the voice direction can be off): the
            near = min(self.vision.seen(), key=lambda s: abs(s[0] - robot_angle), default=None)   # person seen
            log(f"  nobody at the voice ({robot_angle:+.0f} deg): "  # nearest its side (not the nearest far off it)
                + (f"person seen at {near[0]:+.0f} deg, {near[1]:.2f} m" if near else "head back"))
            self.turn_head(HEAD_SIGN * max(-head.YAW_LIMIT, min(head.YAW_LIMIT, near[0])) if near else was, force=True)
            if near:
                time.sleep(1.5)
                t = self.vision.near_angle(near[0])
        return t

    def look_toward(self, robot_angle):
        """Turn the head toward a waist-frame angle; turn the base too if it is outside the head's range."""
        if abs(robot_angle) <= head.YAW_LIMIT:
            self.turn_head(HEAD_SIGN * robot_angle)
        elif self.modes.patrol:
            w = waist_turned()
            if not waist_home("turning to a voice", fold=True):
                return
            log(f"  voice behind ({robot_angle:+.0f} deg): turning the base")
            self.turn_head(0)
            safe(agv.turn_by, math.radians(robot_angle + w))      # from the base's front: the waist is there now
            t = time.time()
            time.sleep(0.5)
            while time.time() - t < 8 and (safe(agv.status, default={}) or {}).get("move_status") == "running":
                time.sleep(0.2)

    # ---------- come here ----------
    def come_to(self, track, say=False):
        """Drive to the person (a visible track) and stop about COME_STOP in front of them. `say`: "I'm coming"
        once the base has the goal, spoken while it drives (the motion never waits for the words)."""
        if track is None or not self.vision or not self.vision.visible(track):
            track = self.speaker_track()                   # who said it: the voice, the talk, the look, a raised hand
            if track is None:
                if self.vision and self.vision.anyone():   # several seen, nobody raised a hand: raised_hand said so
                    return
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
        if not waist_home("coming to a person", fold=True):         # every drive starts with the waist at the front
            mouth.say(WAIST_BACK_SAY[0 if self.lang == "en" else 1])
            return
        ok, msg = safe(agv.go_point, *goal, default=(False, "error"))
        if not ok:
            log(f"  base refused: {msg}")
            mouth.say("Sorry, I can't get closer from here.")
            return
        if say:
            threading.Thread(target=mouth.say, args=("Okay, I'm coming." if self.lang == "en" else "네, 갈게요.",),
                             daemon=True).start()
        t, last_look = time.time(), 0.0
        time.sleep(0.5)
        while time.time() - t < COME_TIMEOUT:
            st = safe(agv.status, default={}) or {}
            if st.get("move_status") != "running":
                log(f"  arrived ({st.get('move_status')})")
                if isinstance(st.get("guard"), (list, tuple)):
                    mouth.say(st["guard"][0] if self.lang == "en" else st["guard"][1])
                break
            if self.stop_heard():                         # the main loop waits here: listen for "stop" too
                self.stop_all()
                return
            if self.vision.present(track):
                if track.distance <= COME_STOP:
                    log(f"  person #{track.id} is {track.distance:.2f} m away - stop")
                    safe(agv.cancel)
                    break
                if time.time() - last_look > 1.0:             # keep looking at them while driving (also over
                    self.turn_head(HEAD_SIGN * max(-head.YAW_LIMIT, min(head.YAW_LIMIT, track.angle)), force=True)
                    last_look = time.time()                   # a held "look at me": it was them)
            time.sleep(0.2)
        else:
            safe(agv.cancel)
        if self.vision.present(track):
            self.turn_head(HEAD_SIGN * max(-head.YAW_LIMIT, min(head.YAW_LIMIT, track.angle)), force=True)
        self.last_activity = time.time()

    def pointed_drive(self, text):
        """"Go there" / "저기로 가" / "come to where I'm pointing" with a pointing arm: drive to the floor spot pointed
        at (vision/pointing.py). True when handled. "here" / "여기" without a pointing arm is left to come-here (False);
        "there" without one, or a spot that can't be told or reached, is said plainly, never guessed."""
        from vision import pointing
        word = pointing.asked(text)
        if word is None or self.base_off("go_to", "pointed"):
            return word is not None
        en = self.lang == "en"
        if self.mission_running() or self.skill_busy():
            mouth.say("Sorry, I can't drive right now." if en else "죄송해요, 지금은 이동할 수 없어요.")
            return True
        spot = safe(pointing.target, default={"why": "no_depth"}) or {"why": "no_depth"}
        log(f"POINTED ({word}): {spot}")
        if "map" not in spot:
            if word == "here" and spot["why"] in ("nobody", "not_pointing"):
                return False                               # plain "come here": today's come_to
            mouth.say(pointing.SAY[spot["why"]][0 if en else 1])
            self.keep_listening()
            return True
        far = spot["clamped"]
        if not waist_home("driving where pointed", fold=True):      # every drive starts with the waist at the front
            mouth.say(WAIST_BACK_SAY[0 if en else 1])
            return True
        mouth.say((f"Going that way, {pointing.MAX_M:g} meters." if far else "Going there.") if en else
                  (f"그쪽으로 {pointing.MAX_M:g}미터 갈게요." if far else "그곳으로 갈게요."))
        ok, msg = safe(agv.go_point, *spot["map"], default=(False, "error"))
        if not ok:
            log(f"  base refused: {msg}")
            mouth.say("Sorry, I can't go there." if en else "죄송해요, 그곳으로 갈 수 없어요.")
            return True
        t = time.time()
        time.sleep(0.5)
        while time.time() - t < COME_TIMEOUT:
            st = safe(agv.status, default={}) or {}
            if st.get("move_status") != "running":
                log(f"  pointed drive ended ({st.get('move_status')})")
                if st.get("move_status") != "succeeded":
                    mouth.say("I couldn't get there." if en else "그곳까지 못 갔어요.")
                break
            if self.stop_heard():                         # the main loop waits here: listen for "stop" too
                self.stop_all()
                return True
            time.sleep(0.2)
        else:
            safe(agv.cancel)
        self.last_activity = time.time()
        return True

    # ---------- follow me (tasks/follow.py) ----------
    def follow_me(self):
        """Lock onto the person who said "follow me" (the track talking, else the one where the voice came from)
        and follow them in the background until a stop word, they are lost, or something is in the way."""
        from tasks import follow
        en = self.lang == "en"
        self.end_run(getattr(self, "heard", "") or "follow me")
        if self.skill_busy():
            self.fetch_say("Sorry, I'm on a task right now.", "죄송해요, 지금 다른 일을 하고 있어요.")
            return
        track = self.speaker_track()                       # who asked: the voice, the talk, the look, a raised hand
        if track is None and self.vision and self.vision.anyone():   # nobody raised a hand: raised_hand said so
            return
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
        self.follow_by_clip = getattr(getattr(self, "last_u", None), "source", None) == "clip"
        log(f"FOLLOW person #{track.id} at {track.distance:.2f} m {track.angle:+.0f} deg")
        follow.start(lambda: self.vision.follow_view(track), say=self.fetch_say, people=self.vision.follow_views)
        mouth.say("Okay, I'll follow you." if en else "네, 따라갈게요.")   # while it already moves (owner: no waiting
                                                                          # for a long sentence first)
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
        threading.Thread(target=self.keep_focus, daemon=True).start()
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
        self.reach_done()                                  # the hand held out REACH_HOLD_S: back to look
        self.publish_busy(self.doing())
        if self.patrol and self.patrol.mode == "done" and not self.a.patrol and not self.patrol.stuck:   # said first
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
        greet_now = self.modes.greeter and not moving and time.time() > self.quiet_until and not following \
            and not self.doing() and self.current is None  # never during a task or while talking with someone
        candidate = self.waver() if greet_now else None    # Lumi never speaks to someone who only stands there or
        focus = self.current or candidate                  # walks past: a wave (or the wake word) calls it
        self.vision.det.focus_angle = focus.angle if focus else None    # drawn red in the dashboard
        new = candidate
        if new:                                            # someone waved at Lumi (first or second person)
            self.greet(new)
            self.last_activity, self.prompts = time.time(), 0
            return

        if self.current and not self.vision.present(self.current):
            gone = self.current                            # often the same person under a new track id (#5 -> #7 at
            again = None if following else self.vision.near_angle(gone.angle, FOCUS_REFIND_DEG)   # 19:24, 2026-10-27)
            if again is gone or again is not None and again.distance > STAY_MAX:   # the same track, only far: gone
                again = None                               # (else "seen again as" itself, ~33000 times a s, 2026-10-28)
            if again is not None:
                log(f"person #{gone.id} seen again as #{again.id} at {again.angle:+.0f} deg")
                again.greeted, self.current = True, again
                if getattr(self, "look_me", None) is gone:
                    self.look_me = again
                return
            log(f"person #{self.current.id} left - stop talking")
            self.current = None if following else self.vision.nearest_greeted()   # someone else still here?
            if self.current:
                self.turn_head(HEAD_SIGN * self.current.angle)
            else:
                # often still there, out of the frame (beside the arm): keep listening without the wake word
                # for a while, like a conversation started by voice. The head stays their way; it rests when this
                # voice session ends by silence (end_conversation)
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
            if getattr(self, "looked_at", 0.0) and not self.look_held():
                log(f"  nothing said for {LOOK_HOLD_S:.0f} s after a look: head to rest")
                self.head_rest()
            if self.voice_until:
                log("voice conversation over (silence): the wake word or a wave again")
                self.end_conversation(None, quiet=True)    # Lumi never speaks unasked: no goodbye into a silence
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
        elif not following and not self.doing() and time.time() - self.last_activity > TALK_IDLE_S:
            log(f"conversation over (nothing said for {TALK_IDLE_S:.0f} s): the wake word or a wave again")
            self.current.greeted = True                    # still here: only a new call starts the next talk
            self.end_conversation(None, quiet=True)        # Lumi never speaks unasked, no goodbye into a silence
        elif (not following and not self.interrupted() and time.time() - self.last_activity > PROMPT_S and self.prompts < MAX_PROMPTS):
            log(f"silent for {PROMPT_S:.0f} s - prompt")
            mouth.say(PROMPT[self.lang], abort=self.interrupted)
            self.last_activity, self.prompts = time.time(), self.prompts + 1

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
        memory.start(idle=lambda: self.current is None and time.time() - getattr(self, "last_activity", 0.0) > 20,
                     after=self.warm_llm)          # talks kept from now on; summed up while nobody talks
        memory.watch(arm_ok=lambda: not getattr(self, "busy_now", "") and self.doing() is None and
                     self.fetch_status() != "running", look_held=self.look_held)
        self.warm_llm()
        log("ready")
        self.run_camera() if self.vision else self.run_desk()


NOT_STOP = re.compile(   # a stop word that orders no stop: negated, about someone or something else, another meaning
    r"\b(?:don'?t|do not|never|no need to|not) (?:\w+ )?sto+p\b|\bkeep (?:going|moving|walking|driving)\b|\bcontinue\b|"
    r"\bgo on\b|\bcarry on\b|\bno,? no,? (?:go|continue|keep)\b|멈추지 ?마|그만하지 ?마|계속(?: ?(?:해|가|하세요|가세요|해요|가요))?|"
    r"(?<!\bi )\b(?:said|says|told|tells|yelled|shouted|keeps? saying)\b[^.?!]*\bsto+p\b|\bsto+p(?:ped|s|ping)\b|"
    r"\bstop (?:working|smoking|drinking|eating|talking about|laughing|crying|worrying|by|sign|motion|watch)\b|"
    r"\b(?:bus|train|tram|next|last|first) stop\b|\bcan'?t stop\b|non-?stop|정거장|정류장|"
    r"\b(?:freezes|froze|frozen|freezing)\b|"
    r"(?:다리|손|심장|시계|컴퓨터|노트북|버스|차|폰|핸드폰|화면|숨|시간|엘리베이터|에스컬레이터)(?:이|가|도|는|은)?\s*(?:\S+\s+){0,2}"
    r"(?:멈췄|멈춰(?:요|서|버렸|있)|멈춰\.?$|멈추)|(?:멈췄|멈추더라|멈추던데|멈춘다)|"
    r"(?:엄마|아빠|선생님|걔|쟤|친구|사람|그 ?분|형|누나|언니|오빠)\S*\s.*라고 ?했|"
    r"\bstop-motion\b|\bone-stop\b|\bwhy(?:'d| did| do| does)? (?:you|it|lumi) (?:freeze|stop|halt)|\b(?:would|should|could|might|will) stop\b|\blet'?s stop (?:at|for|by)\b|"
    r"\bstop (?:for|at the|at a) (?:coffee|lunch|a (?:bit|while|break)|the \w+ (?:place|shop|store|cafe))|"
    r"\b(?:when|if|once|whenever|after) [^,]{1,40},?\s*(?:you )?stop\b|"
    r"그만(?:두(?!세요|십시오|시오|어라|라|게)|뒀|둘)|그만 ?(?:먹|마시|자|놀|울|웃|싸우|뛰)|"   # "회사 그만뒀어"; "그만두세요" stops
    r"(?<![가-힣])(?!루미|로봇|누미|아야|말이야|얘야)(?:엄마|아빠|얘들아|형|언니|누나|오빠|[가-힣]{1,3}야|[가-힣]{1,3}아)\s+(?:좀\s+|거기\s+)?(?:그만|멈춰|정지)|"
    r"(?-i:\b(?!(?:Lumi|Loomi|Rumi|Robot|Hey|Hi|Okay|Ok|No|Please|Now|Wait|Hello|So|Oh|Yo)\b)[A-Z][a-z]+), stop \w+ing\b", re.I)
    # also: another meaning, someone else told off ("엄마 그만 찍어", "Jake, stop touching the robot!"), a condition


_STOPW = r"(?:sto+p|halt|freeze|멈춰|멈춰요|정지|그만|스톱|스탑)"
STOP_UNSAID = re.compile(   # a stop that is taken back, for later, said about the past, to someone else, or mocked
    rf"{_STOPW}.*[,.…—–!]\s*(?:(?:oh|uh|um|hmm+|아|어|음|wait|no|actually)\W+)*(?:never ?mind|forget (?:it|that)|"
    r"cancel(?: that| it)?|(?:아\s*)?(?:됐어|됐다|됐어요)(?: 마| 됐어)?|취소|아니다|(?:아\s*)?(?:그냥\s*)?하지 ?마(?:세요|요)?)\W*$|"
    rf"[가-힣](?:면|나면|으면)\s+(?:\S+\s+){{0,3}}{_STOPW}|"                     # "사람 나오면 그때 멈춰", "음악 멈추면 멈춰요"
    rf"\b{_STOPW}(?: \w+)? (?:when|once|after|until|as soon as|if) |\bwhen i give the signal\b|"   # "stop when you get there"
    rf"\b(?:don'?t|do not|doesn'?t|didn'?t|won'?t) (?:\w+ ){{0,2}}{_STOPW}\b|{_STOPW}\s*하지 ?마|"   # "you don't have to stop"
    rf"(?<!you )(?<!have )(?<!need )(?<!got )(?<!want )\bto {_STOPW}\b|\b(?:it|he|she) (?:doesn'?t|tried to|keeps?) |"                # "waiting for it to freeze"
    r"\b(?:heard|bet|like|guess) (?:that )?(?:you|it) (?:can|could)\b|\bi saw you\b|"
    r"리가 있나|내가 사람이다|퍽이나|[가-힣]겠다\W*$|했던데|그랬잖아|했잖아|(?:멈췄|정지했|그만했)(?:던데|잖아|으면)|"
    r"(?-i:\b(?!(?:Lumi|Loomi|Rumi|Robot|Hey|Hi|Okay|Ok|No|Please|Now|Wait|Hello|So|Oh|Yo|Stop)\b)[A-Z][a-z]+), (?:okay )?stop|"
    r"\bstop it,? (?-i:(?!Lumi\b|Robot\b)[A-Z][a-z]+)\b", re.I)


STOP_LATER = re.compile(   # a stop for later ("내일 그만하시게", "행사가 끝난 후에 멈춰 주세요") or reported ("아까 직원분이
    # 그만하라고 지시했습니다"); "내가 멈추라고 했지!" is said now
    r"(?:^|\s)(?:나중에|이따가?|있다가|내일|모레|다음에|다음 ?번에)\s|(?:끝난|끝나고|마친|마치고|끝내고) ?(?:후|뒤|다음)?에?\s|"
    r"[가-힣]고 ?나서\s|(?<!내가 )(?<!제가 )(?<!내가)(?:그만하|멈추|멈춰 ?달|정지하|서)라고\s*(?:\S+\s+)?"
    r"(?:했|하셨|그랬|말했|말씀|지시|하더|하던|한다|하네)")


STOP_PAD = re.compile(r"^(?:\W*(?:hey|hi|yo|oh|okay|ok|so|um+|uh+|listen|right|alright|all right|excuse me|mister robot|buddy|dear|"
                      r"당장|얼른|빨리|지금|바로|어서|좀|제발|"
                      r"robot|lumi|loomi|루미 ?씨|루미 ?선생|루미야?|로봇아?|로봇 양반|어+|아+|야|저기요?)\b)+|"
                      r"(?:\W*\b(?:please|plz|pls|bro|now|right now|real quick|thanks|thank you|okay|ok|would you|will you|"
                      r"right|already|lumi|robot|빨리|좀|제발|당장|루미야?)\b)+\W*$", re.I)
STOP_ONLY = re.compile(   # a whole sentence that only says stop / enough / stay (after calls and fillers): stop at once
    r"(?:(?:sto+p|stahp|stob|top it|emergency stop|enough|that'?s enough|that is enough|no more|quit it|cut it out|knock it off|whoa,? there|whoa(?:,? whoa)+|kill it|abort|"
    r"stop (?:everything|driving|moving|it|that|the robot|right there|right now)|enough (?:music|of that)|"
    r"hold it(?: (?:right )?(?:there|here))?|stop 해|그만|그만해|그만해요|그만하세요|그만하십시오|그만해 ?줄래요?|"
    r"그만해 ?주세요|그마내|그만둬|멈춰|멈쳐|멈처|멈추라고|멈춰 ?봐|거기까지|고마 ?(?:서라|해라|해|하이소)|서|don'?t go|가지 ?마|그마+안|"
    r"얼음|cut it|노래 ?꺼|음악 ?꺼|stop the (?:music|song)|music off|stay|stay (?:here|there|put|right there)|"
    r"(?:just )?wait there|stop following(?: me)?|finish follow|(?:여기|거기)(?:서)? ?(?:그대로 ?)?(?:있어|있어요|계세요|stay|서|서세요|"
    r"기다려)|그대로 있어|가만히 있어|stay 해|wait 해)\W*){1,3}", re.I)


STOP_POLITE = re.compile(   # a stop asked politely, after wording.ko_plain: "멈춰 주시겠어요?" -> "멈춰 줘?", "can you stop for me?"
    r"\W*(?:(?:좀|지금|당장|잠깐|잠시|거기서?|이제)\s*)*(?:멈춰|멈춰 서|정지해|그만해|스톱해|스탑해|서)(?: ?줘)?\W*|"
    r"\W*(?:(?:please|lumi|hey|okay|ok)\W+)*(?:can|could|would|will) (?:you|u) (?:please |just |kindly )?(?:go ahead and )?"
    r"(?:stop|halt|freeze|hold it(?: right)? (?:there|here))"
    r"(?: (?:right )?(?:now|here|there|please))?(?: for (?:me|us|a (?:second|sec|moment|bit|minute)))?(?:,? please)?\W*|"
    r"\W*(?:would|do) you mind stopping(?: (?:now|here|there))?(?: for (?:me|us|a (?:second|moment)))?(?:,? please)?\W*", re.I)


STOP_CALL = re.compile(r"^\W*(?:(?:okay|ok|오케이|hey|yo|야|어이|저기요?|자|lumi|loomi|rumi|robot|buddy|(?:루미)+|누미|류미|로봇)"
                       r"(?:\s*(?:님|씨|야|아|군))?\W+)+", re.I)   # "루미 님, …", "오케이, 야 루미, …", "okay Lumi, …"


def stop_order(text, markers):
    """stop_order_said on the words, and again without the calls in front ("루미 님, 멈춰 주실 수 있겠습니까?")."""
    bare = STOP_CALL.sub("", text or "")
    if re.fullmatch(r"\W*(?:wait|hold on|hang on|one (?:sec|second|moment)|잠깐(?:만)?(?:요)?|기다려(?:요)?)\W*", bare, re.I):
        return stop_order_said(text, markers)        # "Lumi, wait": a mission halts for a talk (mission_talk), not ended
    return stop_order_said(text, markers) or bool(bare and bare != text and stop_order_said(bare, markers))


def order_after_stop(text, markers, b):
    """"Lumi stop, not the apple, take the cup", "루미 멈춰, 제자리에 놔": the order said after the stop word (done
    after the stop), else None ("stop it", "stop, where are you going?", "stop, don't take it")."""
    m = FETCH_STOP.search(text or "")
    rest = text[m.end():].strip(" ,.!?~") if m else ""
    if len(rest.split()) < 2:
        return None
    return rest if route(rest, markers, b, chain_ok=False)[0] in ("quick", "hand", "mission", "chain") else None


def stop_order_said(text, markers):
    """"stop", "freeze", "멈춰": stop everything at once. Not "stop talking" and not a question about the stop button;
    "can you stop?", "멈출 수 있어?" and "stop, where are you going?" do stop. Not a negated stop ("don't stop", "계속
    해"), talk about stopping ("he said stop", "bus stop", "my laptop freezes", "내 다리도 자주 멈춰"); a short bare
    stop word always stops (also stretched: "stooop", "머엄춰")."""
    if NOT_STOP.search(text) and not re.fullmatch(r"\W*(?:(?:lumi|robot|hey|okay|ok)\W+)*(?:would|do) you mind stopping"
                                                  r"(?:,? (?:now|here|there|please|for (?:me|us|a (?:second|moment))))*\W*", text, re.I) \
            and not re.fullmatch(r"\W*(?:(?:no|ok|okay|lumi|루미야?|hey)\W+)*(?:sto+pp?|stob|stopped|halt|freeze|멈춰|머+엄*춰|"
                                                  r"그만|정지|스톱|스탑|stop it|stop now)\W*", text, re.I):
        return False
    if STOP_UNSAID.search(text) or STOP_LATER.search(text):
        return False                                      # "이따가 멈춰 주세요": a stop for later
    bare = STOP_PAD.sub("", text.strip()).strip(" ,.!?~")
    if bare and STOP_ONLY.fullmatch(bare):
        return True                                       # "hi Lumi, stop, okay?", "enough already", "Lumi, wait"
        # (watch out / 위험해 / "Lumi, wait" / hold on: on a mission these halt it (mission_talk), never end it)
    from assistant import wording
    plain = brain_mod.CALLING.sub("", wording.ko_plain(text)).strip()
    asked = bool(brain_mod.STOP_ASK.match(brain_mod.CALLING.sub("", text)) or STOP_POLITE.fullmatch(plain) or
                 re.match(r"^\W*(?:stop|halt|freeze|멈춰|정지|스톱)\W*[,.!]", text, re.I))
    return bool(FETCH_STOP.search(text) or asked) and (brain_mod.intent(text, markers) or ("",))[0] not in ("quiet", "look") \
        and not brain_mod.STOP_TALK.search(text) and ("?" not in text or asked)


def own_command(text, last=""):
    """One of the fixed commands answered by rule (a song, the songs, the voice, what Lumi can do): taken also when
    whisper tagged the sentence with the other language."""
    return bool(sing.asked(text, last) or sing.list_asked(text) or voice_words.read(text, last) or abilities.answer(text, "en", last))


HAND_STATE_Q = re.compile(   # how the hand is now (A1): "is your hand open?", "hand open이야?", "손 펴져 있어?", "그리퍼 열려 있어요"
    r"\b(?:is|are|r|was) (?:your|ur|the) (?:hand|gripper|claw|fingers?|arm)s? (?:still |now |already )?(?:open|opened|closed|shut|out|"
    r"extended|empty|folded|in|up|down|stretched)\b|\b(?:hand|gripper|arm) (?:open|closed?|out)\s*(?:이야|이에요|인가요?|이니|상태|\?)|"
    r"^\W*(?:(?:right|um|basically|next|so|okay)\W+)*did (?:you|u) drop (?:it|that|something|the \w+)\W*$|"
    r"(?:손|그리퍼|집게|손가락|팔)(?:이|은|는|가)? ?(?:지금 |아직 |다 )?(?:open|close|오픈|클로즈|펴져|펴진|열려|열린|닫혀|닫힌|접혀|접힌|뻗어져|오므려져|"
    r"쥐어져)\s*(?:있|상태|이야|인가)", re.I)


def status_question(text):
    """"What are you doing?", "where are you going?", "is your hand open?": answered from the task state ("들고 있는 거
    줘" is a request)."""
    hand = HAND_STATE_Q.search(text) and not re.search(r"\b(?:stretch|stick|hold|put|reach|extend|get|move|bring)\b", text, re.I)
    return bool(hand) or bool(STATUS_Q.search(text)) and not NOT_STATUS_NOW.search(text) and not EMPTY_HAND.search(text)
    # hand: not "may I ask you to stretch your arm out?" (an order)


def says_goodbye(text):
    """A goodbye whatever was said before: "okay, bye", "I have to go", "수고하세요", "you can go" alone (not "bye, but
    where is...?", not an order with it, not said to a child nearby)."""
    if brain_mod.to_someone_else(text) or re.search(r"\b(?:let me|lemme|wanna|want to|like to|love to|let'?s) see you\b", text, re.I):
        return False                                       # "Okay kids, say bye to the robot."; "lemme see you go charge"
    return bool(RELEASE.match(text) or CLEAR_BYE.search(text) and not ASKS_MORE.search(text)
                and len(text.split()) <= 10 and not brain_mod.intent(text) and not brain_mod.hand_request(text, False)
                and not COMMAND_START.search(brain_mod.CALLING.sub("", text)))   # "grab the cup, bye": an order


def talk_fate(text):
    """What short words do to the talk: "end" (a goodbye in any context: "okay, bye", "안녕히 계세요"), "close" (words
    that close a talk in one context and mean "understood, go on" in another: "okay", "thanks", "that's it", "됐어요",
    "오케이 땡큐": the LLM decides with the turns before; when it does not end, silence of CLOSING_WAIT_S ends the talk)
    or "talk" (anything else; "I see", "그렇구나", "알겠어요" alone are understanding, "I see?", "그래요?" a check)."""
    if says_goodbye(text):
        return "end"
    if brain_mod.is_closing(text) and (THANKS.search(text) or not brain_mod.UNDERSTOOD.search(text)) or \
            THANKS.search(text) and not THANKS_REST.sub("", THANKS.sub("", text)) or \
            DONE_WORDS.search(text) and not ASKS_MORE.search(text) and len(text.split()) <= 8 and not brain_mod.intent(text):
        return "close"                                     # "Thanks a bunch.", "Okay, I think that's everything."
    return "talk"


NOT_A_STEP = re.compile(r"^\W*(?:(?:please|and|then|also)\s+)*(?:dance|jump|fly|swim|climb|sit(?: down)?|sleep|cook|draw|"
                        r"sing|clap|spin|bow|kneel|do a (?:dance|flip|trick)|tell|ask|say|show|call|find|look for|search|"
                        r"bring|take|give|hand|put|carry|deliver)\b|.*(?:춤|점프|날아|수영|박수)", re.I)   # a part not read: asked


CAN_TOLD = re.compile(r"\b(?:you|u) (?:can|could|are able to|know how to)\b|(?<!줄 )(?<!주실 )(?<!줄)(?<!주실)수 ?(?:도 ?)?있(?:지|죠|잖|겠지|겠죠|을 ?걸)|"
                      r"줄 ?(?:도 ?)?알(?:지|죠|잖)", re.I)   # with a tag: Lumi's ability said back, a question (TAG)
MYEOT_SLIP = re.compile(r"(?<![가-힣])멸(?=\s*(?:센티|센치|미터|밀리|키로|킬로|그램|개|번|도|시|분|초|명|살|층|cm|mm|kg|m\b))", re.I)


def route(text, markers, b, holding=False, seen=None, last="", chain_ok=True):
    """Which way a command goes, the same for voice (Lumi.answer), the dashboard's Command box (/tasks/parse) and
    tests/command_check: (kind, data). Kinds in this order: "stop"; "detour" (data: assistant/detour.read's
    "retry" / "backup" / "around" / "back", only right after a blocked drive); "chain" (data: chain.plan); "seeing" (data: what
    seen(text) answered); "status"; "correction" (brain.correction); "hand" ((kind, what), brain.hand_request with
    the hand as it is: holding is a bool or a function asked only here); "mission" (read_mission's (steps, unread,
    by)); "end" (a goodbye); "sing"; "quick" (brain.intent's rule, one of QUICK_RULES, or the example bank's
    reading: assistant/intent_bank.py); (None, None): the LLM reads
    it. seen: seeing.answer or a stand-in; chain_ok: False on a mission or while a chain runs."""
    from assistant import chain, intent_bank
    text = MYEOT_SLIP.sub("몇", text or "")    # whisper's 멸 for 몇: "멸 센티까지 잡아?" asks, orders nothing
    text = re.sub(r"(?<=[가-힣])(?=[a-zA-Z]{2})", " ", text)   # "원래 자리에put back": the English word apart
    text = re.sub(r"\bcome on back\b", "come back", text, flags=re.I)   # not 1 m back
    text = re.sub(r"(?<=\w)\W+(?:is (?:it )?ok+ay|is ok|is (?:it )?possible|possible|you can do)(?: for you)?\s*\?*\s*$", "", text,
                  flags=re.I) or text   # "look 60 deg to right, is okkay for you?": the order, the check after it is no question
    text = re.sub(r"(?<![\d.])360(?= ?돌아)", "360도", text)   # "루미 360 돌아 봐": a full turn, not "turn round"
    if stop_order(text, markers):
        return "stop", None
    told = intent_bank.TAG.search(text) and (chain.PAST.search(text) or intent_bank.PAST_EN.search(text) or
                                             intent_bank.past_ko(text) or CAN_TOLD.search(text))
    # "you went to P5 earlier, right?", "you can lift your arm, right?", "너 팔 접을 수 있지?": asked, no order
    text = brain_mod.strip_asides(text)        # "hi Lumi, it's my birthday, put it down!": the command (A1)
    if sing.picked(text, last):                # after the list of songs: "the first one", "Fantastic Baby"
        return "sing", None
    arm_last = re.match(r"ACTION: (wave|arm (?:reach|fold))\b", last or "")
    if arm_last and ARM_AGAIN.match(text or ""):
        return "quick", tuple((arm_last.group(1).split() + [""])[:2])   # "again!", "한 번 더" right after a wave
    hold = told or brain_mod.not_an_order(text) or not brain_mod.direct_order(text) or brain_mod.held_back(text)   # only a direct
    # order to Lumi now acts (held_back: "don't ..., then ...", "yeah right, like you could ...", "..., forget it")
    stuck = detour.recent()                    # right after a blocked drive: "try again", "go around it", "go back";
    how = stuck and detour.read(text, markers, stuck["goal"])   # only a direct order (detour.read), else the LLM
    if how:
        return "detour", how
    plan = chain_ok and not brain_mod.not_an_order(text, asked=False) and brain_mod.direct_order(text) and \
        chain.plan(text, markers, NOT_A_STEP)   # not "when the show starts, go to the stage", "Jake, wave"
    picks = [i for i, (k, _, w) in enumerate(plan or []) if k == "steps" and any(st.get("do") == "pick" for st in w) or
             k == "quick" and w[0] in ("pick", "move_object")]
    frees = [i for i, (k, _, w) in enumerate(plan or []) if k == "steps" and any(st.get("do") in ("place", "give") for st in w)
             or k == "quick" and w[0] in ("put", "give")]   # "왼쪽에 내려놓고 오른편 컵 잡아 줘": the hand is free first
    if picks and not (frees and frees[0] < picks[0]) and (holding() if callable(holding) else holding):
        plan = None                            # "그 cup 들고 wave 해" with a cup in the hand: no second pick; the LLM
    if plan:
        return "chain", plan
    held_order = (holding() if callable(holding) else holding) and not hold and \
        (brain_mod.held_place(text, markers) or brain_mod.held_give(text, markers))   # "put it down ok?" with a cup:
    got = seen(text) if seen and not held_order else None                              # the hand, not "I put it down, now?"
    if got:
        return "seeing", got
    if status_question(text) and not brain_mod.to_someone_else(text):   # not "Mina, what are you doing over there?"
        return "status", None
    if (holding() if callable(holding) else holding) and not brain_mod.held_back(text) and \
            not brain_mod.ARM_TALK.search(text) and brain_mod.held_put_back(text, markers):
        return "quick", ("put", "back")        # "it's my birthday, put that back where you found it!"
    song = sing.asked(text, last)              # "Let it go 불러 줘": a song title, never the hand (A1)
    if hold and not song and not told:         # a wave / arm rule may act on a question-form request ("악수 한번 할까요?",
        arm_rule = brain_mod.intent(text, markers)   # "would it be possible to wave at me?"); intent() itself refuses
        if arm_rule and arm_rule[0] in ("wave", "arm"):   # negations, later times, remarks, ability questions (A1)
            return arm_quick(arm_rule, holding)
    if hold and not ((brain_mod.held_give(text, markers) or brain_mod.held_place(text, markers)) and
                     (holding() if callable(holding) else holding)):   # "테이블에 놔 줄래? 영상 찍고 있어": the hand's
        rule = brain_mod.intent(text, markers)   # weather / search are no motion: "Weather outside?"
        return (("end", None) if talk_fate(text) == "end" else ("sing", None) if sing.asked(text, last) else
                ("quick", rule) if rule and rule[0] in ("weather", "search") else
                (None, None))                  # no motion from a keyword: the LLM reads it from the talk
    cor = brain_mod.correction(text, b.history)
    if cor:
        return "correction", cor
    if not song and not brain_mod.ARM_TALK.search(text) and not brain_mod.held_back(text) and \
            (brain_mod.hand_request(text, False, b, markers) or brain_mod.hand_request(text, True, b, markers)):
        # not "it'd be cool if you could hand it over someday", "I heard you can take things from people"
        held = holding() if callable(holding) else holding
        hand = brain_mod.hand_request(text, held, b, markers)
        if hand:
            return "hand", (hand, held)
    read = read_mission(text, markers)
    if read:
        return "mission", read
    arm_rule = not song and brain_mod.intent(text, markers)
    if arm_rule and arm_rule[0] in ("wave", "arm"):
        return arm_quick(arm_rule, holding)    # "빠빠이 해 줘", "let's see you reach your arm out": the arm, not a goodbye
    if talk_fate(text) == "end" and (b.history or not HI_ANNYEONG.search(text)):   # "루미 안녕!" first: hello
        return "end", None
    if sing.asked(text, last):
        return "sing", None
    rule = brain_mod.intent(text, markers)
    if rule and rule[0] in QUICK_RULES - {"come_back", "weather", "search"} and brain_mod.ARM_TALK.search(text):
        return None, None                      # "자네 컵 잡는 거 제법이더군", "do you know how to drive right 30 cm?",
                                               # "70센티 앞으로 움직일 리가 있나": a remark or an ability, no motion
    if rule and rule[0] in QUICK_RULES:
        return "quick", rule
    if not rule:
        from assistant import intent_bank
        rule = None if brain_mod.GREET_ONLY.match(text or "") else \
            intent_bank.read(text, markers, holding)   # the same request in other words, by meaning ("hello robot": no wave)
        if rule and rule[0] not in ("come_back", "weather", "search") and brain_mod.ARM_TALK.search(text):
            rule = None                        # "it'd be cool if you could take your hand back someday": talk (A1)
        if rule:
            return arm_quick(rule, holding)
    return None, None


def arm_quick(rule, holding):
    """A rule's reading as route's ("quick", rule); an open hand while holding is refused (the thing would fall)."""
    if tuple(rule[:2]) == ("arm", "open") and (holding() if callable(holding) else holding):
        return "hand", (("refuse", brain_mod.REFUSE_OPEN), True)
    return "quick", rule


QUICK_RULES = {"go_to", "come", "follow", "quiet", "weather", "search", "move", "turn", "arm", "pick", "put", "move_object",
               "fetch", "look", "lift", "wave", "come_back", "waist"}   # what quick_command does at once
ARM_AGAIN = re.compile(r"^\W*(?:(?:okay|ok|yes|yeah|lumi|please|robot|루미야?|응|네)\W+)*(?:again|one more time|once more|"
                       r"do it again|(?:do it )?one more|more|again,? please|one more time,? please|한 ?번(?:만)? ?더(?: 해(?: ?줘| ?주세요)?)?|"
                       r"다시(?: 해(?: ?줘| ?주세요)?)?|또(?: 해(?: ?줘| ?봐)?)?)(?:\W+(?:please|again|lumi))*\W*$", re.I)
                       # the wave or reach just done, again ("again!", "one more time please", "한 번 더")


FILLER_PART = re.compile(r"\W*(?:(?:hey|yo|hi|okay|ok|excuse me|um+|uh+|so|now|please|thanks|thank you|real quick|quick|"
                         r"right now|lumi|robot|buddy|mister robot|bro|dude|어이|야|저기요?|루미 ?씨|루미야?|로봇아?|당장|지금|빨리|"
                         r"얼른|어서|끝까지|이제|좀|제발)\W*)+", re.I)   # a part of the words that is no step: a call, "now"


def read_mission(text, markers):
    """(steps, unread, by) when the words are a command of several steps (unread: parts not understood), else None.
    A single move / turn / arm / go, or words that are only partly a plain command, stay with the other paths."""
    from assistant import steps
    got, unread, by = steps.read(text, markers, llm=False)
    from assistant import chain
    unread = [u for u in unread if not FILLER_PART.fullmatch(u) and   # "팔 접어, 당장", "hey robot, fold your arm"
              not chain._restated(u, text.lower().replace(u, " "))]  # "컵 잡아!, 아 잡아 줄 수 있어요?": said again
    # (the parts come lower-cased: "부스 B로 가서" is the part itself, not said twice)
    rule = brain_mod.intent(text, markers) or ("", "")
    if unread and rule[0] == "look" and rule[1].endswith(f" {brain_mod.HEAD_YAW[1]:g}"):
        return None                                # "turn around and look": the head looks behind (brain.BEHIND_WORDS)
    if got and all(s["do"] == "say" for s in got):
        return None                                # "say hello in Korean", "say again?": talk, not a task
    if unread and got and ({s["do"] for s in got} & steps.MISSION_ONLY or steps.is_mission(got)):
        got, unread, by = steps.read(text, markers)          # clearly several steps: the LLM may read it
    elif unread and got and any((brain_mod.intent(u, markers) or ("",))[0] not in ("", "weather", "search", "fetch")
                                or NOT_A_STEP.match(u) or brain_mod.place_problem(u, markers) for u in unread):
        return got, unread, by                     # "go to the stage and wave": no task step, asked, never half done
    elif unread:
        return None                                # "come here, I need help": the old paths (rules, the LLM) answer it
    if not got:
        return None
    if len(got) > 1 and all(st == got[0] for st in got) and got[0]["do"] in ("arm", "wave", "look", "lift"):
        got = got[:1]                              # "reach out, reach out to me": one reach, said twice
    one_part = len(steps._split(steps._norm(steps._cut_says(text)[0], markers), markers)) == 1
    plain = not steps.is_mission(got) and (len(got) == 1 or one_part or (brain_mod.intent(text, markers) or ("",))[0] == "fetch")
    # ^ "컵 가져와 주셨으면 해요": one part a plain fetch can do stays the fetch, not a mission
    if not unread and (plain or (len(got) == 1 and got[0]["do"] in ("move", "turn", "arm"))):   # "take the cup and put
        return None                                                     # it on the chair": two steps, not a pick
    return got, unread, by


def not_online(text):
    """Questions about Cutshion or this event / building: the notes say it or nobody does, never the internet."""
    return bool(COMPANY_Q.search(text) or VENUE_ONLY.search(text) or VENUE_Q.search(text) and not (OUTSIDE.search(text) or
                                                                                            OUTSIDE_NAME.search(text)))


SAID_BYE = re.compile(r"\b(?:bye|goodbye|see you|take care|have a (?:good|nice|great|lovely|wonderful) (?:day|one|time|visit|night|evening|"
                      r"weekend|rest)|enjoy (?:the|your)|"
                      r"next time|come again|good luck)\b|안녕히|다음에|또 (?:봐|봬|만나|오세요|뵙)|좋은 하루|즐거운|조심히|들어가세요",
                      re.I)   # Lumi's own words take leave


def keep_said(brain, text, said):
    """A line Lumi said by code for `text` goes into the talk (the model sees it as its own answer), unless the turn
    is in it already."""
    if said and text and not (brain.history and brain.history[-1][0] == text):
        brain.history.append((text, f"ACTION: none -\n{said}"))


def kept_goodbye(said):
    """The model ended the talk on a closing word ("okay", "thanks"): only when its words said goodbye; "You're
    welcome." alone keeps the talk open (silence then ends it)."""
    return bool(SAID_BYE.search(said or ""))


def lookup_refused(brain, target, about, text=""):
    """not_online for the model's lookup: right after a lookup the words go with the question looked up ("How much
    is a ticket?" after Lotte World), Cutshion never goes online."""
    return bool(COMPANY_Q.search(about)) or not_online(brain.lookup_about(target, about, text))


PRIVATE_ASK = re.compile(r"\bhome address|\bwhere (does|do|did) (my|our|his|her|their|this|that) .{0,40}\blives?\b|"
                         r"\b(phone|mobile|cell) number of (?!the |a )|\b(email|e-mail) (address )?of (my|our|his|her)\b|"
                         r"\b(coworker|colleague|neighbou?r|friend|boss|classmate)'?s?\b.{0,30}\b(salary|income|address|"
                         r"phone number)|(집|자택) ?주소|(옆집|이웃|동료|친구|선생님|사람|옆자리).{0,12}(전화번호|연락처|주소|어디 살|"
                         r"연봉|월급)", re.I)
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
    if "home" in named and len(named) > 1 and all(re.search(r"dock|charg|도크|충전", m, re.I) for m in named - {"home"}):
        return None                                      # "dock 2": the dock and dock2 both heard, not guessed
    return named.pop() if len(named) == 1 else None


def empty_hand_request(text):
    """"hand it over", "테이블에 놔" with nothing held (and no object named): Lumi says its hand is empty."""
    return bool(EMPTY_HAND.search(text)) and not any(w in text.lower() for w in brain_mod.OBJECTS)


def call_only(text):
    """"Hi Lumi", "루미야", "안녕하세요", "How are you?": a call, nothing asked yet."""
    t = text or ""
    return bool(WAKE.search(t) or HELLO_ONLY.match(t)) and bool(CALL_REST.match(WAKE.sub(" ", t)))


def hands_up(frames):
    """Waist-frame bearings (deg) of the people in these camera frames (scene.snapshot) holding a hand up while facing
    Lumi: a wave or a hi at the camera."""
    from vision import pose, scene
    out = []
    for f in frames:
        for p in pose.detect(f["color"]):
            raised, _ = scene._gesture(p["kp"])
            if raised and scene._facing(p["kp"]) is not False:
                out.append(scene._bearing(f, (p["box"][0] + p["box"][2]) / 2))
    return out


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
