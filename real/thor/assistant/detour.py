"""After a blocked drive: what the person asks Lumi to do about it, and where a way round could go.

    "try again", "다시 해 봐"                          -> retry   the same goal again
    "back up a little and try again", "뒤로 갔다가 다시 가" -> backup  the checked straight move back, then the goal
    "go around it", "find a way", "다른 길로 가 봐"       -> around  a free point to the side first, then the goal
    "go back", "come back", "원래 자리로 돌아가"          -> back    back to where the trip started

The last blocked drive (its goal, the rest of the mission, where the trip started) is kept in STATE_FILE: the
assistant writes it (a trip, a task or a mission whose drive got nowhere) and both the assistant and the API read it,
since the dashboard's Command box goes through lumi.route as well. Only while it is fresh do these words mean a
detour; otherwise they keep their usual meaning ("go back" = a short drive back, "try again" = the LLM decides).
The base's API (manual v1.8.8) has no call to clear its costmap: a retry sends the same goal again and the base plans
it from what its sensors see now."""
import json
import math
import os
import re
import time
from pathlib import Path

STATE_FILE = Path("/dev/shm/lumi_stuck.json")
FRESH_S = 300.0            # s; a blocked drive older than this is no longer what "try again" / "go back" means
BACKUP_M = 0.3             # m; "back up a little and try again": straight back this far first
VIA_SIDE_M = (0.8, 1.2)    # m; a way round: points this far to the left and the right of the line to the goal ...
VIA_AHEAD_M = 0.5          # ... and this far along it from where Lumi stands
VIA_CLEAR_M = 0.6          # m; such a point needs this much room to anything the lidar or the map shows (the base's
                           # radius and the arm sticking out: an estimate, tune live)

SAY = {"retry": ("Okay, I'll try again.", "네, 다시 가 볼게요."),
       "backup": ("Okay, I'll back up a little and try again.", "네, 조금 뒤로 갔다가 다시 가 볼게요."),
       "around": ("Okay, I'll try another way.", "네, 다른 길로 가 볼게요."),
       "back": ("Okay, I'm going back.", "네, 원래 자리로 돌아갈게요.")}
STILL = ("Sorry, I still can't get through. I can go back if you like.",
         "죄송해요, 아직도 지나갈 수가 없어요. 원하시면 원래 자리로 돌아갈게요.")
NO_WAY_ROUND = ("Sorry, I can't see another way around it.", "죄송해요, 돌아갈 다른 길이 안 보여요.")
NO_START = ("I don't know where I started. Where should I go?", "어디서 출발했는지 모르겠어요. 어디로 갈까요?")

# ---------- the words ----------
_KEEP_TRYING = re.compile(r"\bdon'?t give up\b|\bdo not give up\b|포기하지 ?(?:마|말고)", re.I)
_NOT = re.compile(r"\b(?:don'?t|do not|never(?! ?mind)|no need|stop trying|no more)\b|"
                  r"하지 ?(?:마|말)|가지 ?(?:마|말)|그만|안 ?해도|필요 ?없", re.I)
_ASKED = re.compile(r"\b(?:did|have|had) you\b|\bwhy\b|\bhow come\b|봤(?:어|니|나요|어요)?\s*\?|왜", re.I)
_SPEECH = re.compile(r"\b(?:say|tell|repeat|sing|speak|explain|spell)\b|말해|말씀|얘기|이야기|들려|노래|불러", re.I)
_BACK_UP = (r"\b(?:b[ae]ck (?:up|off|out)|reverse|(?:move|go|step|drive|come|get) back(?:wards?)?|backwards?)\b|"
            r"\bback(?= ?(?:좀|하))|뒤로|후진|물러|한 ?발")
_AGAIN = (r"\bagain\b|\bretry\b|\bonce more\b|\bone more time\b|\b(?:try|go) (?:on|forward)\b|"
          r"\b(?:then|and) (?:go|try)\b(?! (?:another|a different|other|some other|a new))|다시|한 ?번 ?더|재시도|다가 ?가|하고 ?가|서 ?가")
_BACKUP = re.compile(rf"(?:{_BACK_UP}).*(?:{_AGAIN})|(?:{_AGAIN}).*(?:\bback up|\breverse|후진|뒤로).*(?:\bfirst\b|먼저)",
                     re.I)
_AROUND = re.compile(
    r"\b(?:another|a different|different|other|some other|an other|alternative|alternate|new|a new|better) "
    r"(?:way|whey|wae|route|path|road)(?![a-z])|\b(?:go|drive|get|move|steer|head|navigate|walk|come) (?:a ?)?round\b|"
    r"\b(?:way|whey|wae) (?:a ?)?round\b|\bfind (?:a|the|your|some|another|an other) (?:way|whey|wae|path|route)\b|"
    r"\bdetour\b|\baround (?:해|하|가|돌)|\b(?:try|take|use|go by|go on) (?:the )?(?:left|right|other) side\b|"
    r"\bavoid (?:it|that|them|the)\b|\bwork your way\b|\bgo past (?:it|that|them)\b|\bsqueeze (?:past|through)\b|"
    r"\bre-?route|\brecalculate|\b(?:new|another|different|other|next) (?:aisle|passage|corridor|side)\b|"
    r"\blong way\b|\bchange (?:your|the) (?:route|path|way)|\b(?:pick|plan|take|choose) (?:a|another|a new|the) (?:route|path)|"
    r"\b(?:the )?route on the (?:left|right)|\b(?:look|search|hunt) for (?:a|another|some|the|any) (?:way|path|route)|"
    r"\bfigure out (?:a|some|another|the) way|\bwork out (?:a|some|how)|\bfind (?:some|your own) way|"
    r"\bsee if there'?s (?:another|a|any) (?:way|path|route)|\bway through\b|\bfind (?:a|another) ?길|"
    r"\b(?:room|space|a gap|gap) (?:on|to|by|over)|\bgap (?:by|over|there)|\b(?:left|right) of (?:it|the|that|them)\b|"
    r"\b(?:go|pass|squeeze|keep|fit|get) (?:\w+ )?(?:by|on|to|through on|through) the (?:left|right)|"
    r"\bkeep (?:to the )?(?:left|right)\b|\balong the wall|\b(?:left|right) side|"
    r"\b(?:get|slip|navigate|squeeze|weave|edge|go|move) (?:past|through|between)\b(?!\W*$)|\b(?:hallway|corridor|aisle|passage)\b|"
    r"길 ?find|find.{0,4}길|사이로|빠져 ?나가|다른 ?데로|경로|통로|우회로|멀리 ?돌아|돌아가는 ?길|반대쪽|공간|틈|벽 ?쪽|(?:왼|오른)쪽 ?(?:으로|옆으로)? ?(?:지나|비켜|붙어)|"
    r"옆으로 ?지나|방법.{0,4}찾|길.{0,8}(?:찾|search)|(?:route|path|경로) ?바꿔|(?:way|path|route).{0,4}찾|"
    r"다른 ?(?:길|쪽|방향|경로|루트|way|route|path)|돌아서|둘러|우회|비켜서|피해서|피해 ?가|길(?:을)? ?찾|옆으로 ?(?:돌아|비켜|피해)", re.I)
_BACK = re.compile(r"\b(?:go|come|head|drive|turn|get|move) back\b|\breturn\b|\bback to (?:the )?(?:start|beginning|where)|"
                   r"\bwhere you (?:were|came from|started)\b|돌아 ?(?:와|가|오|올|갈|간)|되돌아|원래 ?(?:자리|곳|위치|데)|"
                   r"\bback ?(?:해|하|가)|제자리|처음 ?(?:자리|위치|곳)|출발(?:한|했던)? ?(?:곳|자리|데|위치)", re.I)
_AMOUNT = re.compile(r"\b(?:a (?:little|bit|tad)|slightly|a few|\d+|cm|centimet\w*|met(?:er|re)s?|steps?|inch\w*|feet|"
                     r"foot)\b", re.I)       # "go back a bit": the short drive back, as without a blocked drive
_TO_PERSON = re.compile(r"\b(?:here|to me|me)\b|이리|여기|나한테|저한테|내게|내 ?쪽|이쪽", re.I)
_RETURN_THING = re.compile(r"\breturn (?:the|a|an|it|this|that|my|your)\b", re.I)
_RETRY = re.compile(
    r"\bagain\b|\bag(?:a|e|i|ai)n\b|\bretry\b|\bre-try\b|\btry a ?gain\b|\bgo (?:ahead|now)\b|\b(?:once more|one more time)\b|"
    r"\b(?:another|one more) (?:try|go|shot|attempt)\b|\bgive it (?:another|one more) (?:try|go|shot)\b|"
    r"\bkeep (?:going|trying)\b|\b(?:continue|carry on|go on|resume)\b|\btry (?:it )?(?:now|harder)\b|"
    r"\bdo it again|\blet'?s try|\btry ?ag(?:ai|ia)n|\bone more\b|"
    r"\b(?:you can|you may|feel free to) go\b|\boff you go\b|\bgo for it\b|\bproceed\b|\bmove along\b|"
    r"\bget going\b|\bmove on\b|\boff you (?:go|pop|trot)\b|\bsneak (?:by|past|through|along)\b|\bgood to go\b|^\W*(?:just |then |so )?go\W*$|"
    r"\b(?:clear|free|open|gone)\b.*\b(?:go|try|carry on|proceed)\b|\b(?:moved|cleared)\b.*\bgo\b|"
    r"\ball clear\b|\bcoast is clear|\b(?:way|path|road|it|that)(?:'s| is) (?:clear|free|open)|\byou'?re clear\b|"
    r"\bobstacle(?:'s| is) gone|\bnothing(?:'s| is) in (?:the|your) way|\b(?:fine|okay|ok|alright)\W+go\b|\bgo ?해도|\bcleared the way|"
    r"다시|한 ?번만? ?더|재시도|재도전|도전|트라이|계속 ?(?:가|해|진행)|또 ?(?:가|해)|가도 ?(?:돼|되|됩)|출발|가던 ?(?:길|데)|"
    r"진행|고고|ㄱㄱ|가 ?(?:봐|보세요|볼래|주세요|줘)|(?:^|[,.!]\s*)(?:(?:그럼|자|음|그냥|이제|루미야)\s*)*가(?:세요|요|라|자)?[\s.!~]*$|"
    r"(?:치웠|비웠|비켰|열렸|뚫렸|지나갔)|움직여|막힌 ?(?:거|게) ?없|장애물 ?(?:치웠|없)|지나갈 ?수 ?있어(?![?요]?\?)|괜찮아.{0,3}가|"
    r"\bclear\b.*가", re.I)
# only a direct order now is acted on: everything else goes to the LLM, which sees the blocked drive (lumi.now_doing)
_NOT_ORDER = re.compile(   # a condition, a later time, a wish, past events, words about something else
    r"(?<!see )\bif\b(?! you (?:could|can|would|will|don'?t mind)\b| possible\b)|\bwhen(?:ever)?\b|\bunless\b|\bsuppose|\bimagine|\bin case\b|\blater\b|\btomorrow\b|"
    r"\byesterday\b|\bnext time\b|\blast time\b|\btold (?:you|it|him|her)\b|\bi(?:'d| would)\b(?! (?:like|love|appreciate|prefer)\b)|\bwe'?ll\b|"
    r"\bwe will\b|\bit (?:can'?t|cannot|couldn'?t|won'?t|will|should|has to|needs to|tried|went)\b|"
    r"\b(?:the|that|this|other|another) robot\b|\b(?:he|she) (?:can|will|should|is|has|tried|went)\b|"
    r"\bphoto|\bpicture|\bselfie|"
    r"(?:으면|다면|라면|하면|가면|되면)(?:\s|[,.!?~]|$)|이따|나중에|내일|어제|그때|지난번|아까 ?(?:도|는)|했었|었었|혼난|"
    r"안 ?(?:돼|되)|큰일|사진|찍|우리.{0,12}(?:가자|하자)|(?:다른|저) 로봇|쟤|걔", re.I)
_TAKEN_BACK = re.compile(r"\bnever ?mind\b|\bforget (?:it|that|about it)\b|\bcancel\b|\bno(?:t)? need\b|\bwait\b|"
                         r"\bhold on\b|\bstay\b|됐어|됐다|됐고|그만|취소|기다려|말자", re.I)   # after the order: taken back
_FIXED = re.compile(r"(?:^|[\s,.!?—–-])(?:no|nope|actually|i mean|아니(?:야|요)?)(?=[\s,.!?—–-])", re.I)   # a correction
_BACK_UP_RE = re.compile(_BACK_UP, re.I)
_START = re.compile(r"\bwhere\b|\bstart|\bforget\b|원래|처음|출발|제자리|있던|잊어", re.I)   # "come back where you started"
_HOME = re.compile(r"\bhome\b|홈|\b(?:dock|charger|charging station)\b|집(?:으로|에)|충전|도크", re.I)


def read(text, markers=(), goal=None):
    """"retry", "backup", "around" or "back" when the words ask that about a blocked drive, else None. A place other
    than the blocked goal named ("go back to p3", "go home") is a new trip; "come back here" comes to the person;
    a question about it ("why can't you go?"), a no ("don't try again") or talk ("say that again") is not a detour."""
    from assistant import brain
    t = _KEEP_TRYING.sub("keep trying", " ".join((text or "").lower().split()))
    t = re.split(r"말고", t)[-1] if "말고" in t else re.split(r"\b(?:instead of|rather than)\b", t)[0]
    ends = [m.end() for r in (_BACK_UP_RE, _AROUND, _BACK, _RETRY) for m in r.finditer(t)]
    if not ends or _NOT_ORDER.search(t):
        return None
    if _TAKEN_BACK.search(t, max(ends)) or _FIXED.search(t, max(ends)):
        return None                              # "try again. never mind", "go around— no, not need"
    fixed = list(_FIXED.finditer(t))
    if fixed:                                    # "go around— no, go back to the start": what follows counts
        t = t[fixed[-1].end():]
    if not t.strip(" .!?,~") or _NOT.search(t) or _ASKED.search(t) or _SPEECH.search(t):
        return None
    others = [m for m in markers if m != goal and (_HOME.search(t) if m == "home" else brain.named_place(t, m, markers))]
    if others:
        return None
    if _BACKUP.search(t):
        return "backup"
    if _AROUND.search(t):
        return "around"
    if _BACK.search(t) and goal in markers and not _START.search(t) and (_HOME.search(t) if goal == "home" else brain.named_place(t, goal, markers)):
        return "retry"                           # "go back to p3" with p3 the blocked goal: that drive again
    if _BACK.search(t):
        return None if _AMOUNT.search(t) or _TO_PERSON.search(t) or _RETURN_THING.search(t) else "back"
    if _RETRY.search(t):
        return "retry"
    return None


# ---------- the last blocked drive ----------
def remember(goal, rest, start, tries=0):
    """Keep a blocked drive: `goal` (marker or [x, y, theta]), `rest` (the mission steps from that drive on), `start`
    (where the trip started, [x, y, theta] or None), `tries` (detours already tried for it)."""
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps({"goal": goal, "rest": rest, "start": start, "tries": tries, "time": time.time()}))
    os.replace(tmp, STATE_FILE)


def recent():
    """The last blocked drive while it is fresh (FRESH_S), else None."""
    try:
        d = json.loads(STATE_FILE.read_text())
    except (FileNotFoundError, ValueError):
        return None
    return d if time.time() - d.get("time", 0) < FRESH_S else None


def forget():
    """A new trip, task or detour: the blocked drive is no longer what "try again" means."""
    try:
        STATE_FILE.unlink()
    except FileNotFoundError:
        pass


# ---------- a way round ----------
def via(pose, goal_xy, clearance):
    """A map point (x, y, theta) beside the way to `goal_xy` (Lumi's heading when unknown): VIA_AHEAD_M along it and
    VIA_SIDE_M to the left or the right, the one with the most room (clearance(x, y) in m), facing the goal; None
    when none has VIA_CLEAR_M."""
    x, y, th = pose
    d = math.atan2(goal_xy[1] - y, goal_xy[0] - x) if goal_xy else th
    best = (VIA_CLEAR_M, None)
    for side in VIA_SIDE_M:
        for s in (side, -side):
            px = x + VIA_AHEAD_M * math.cos(d) - s * math.sin(d)
            py = y + VIA_AHEAD_M * math.sin(d) + s * math.cos(d)
            room = clearance(px, py)
            if room >= best[0]:
                best = (room, (px, py, math.atan2(goal_xy[1] - py, goal_xy[0] - px) if goal_xy else th))
    return best[1]
