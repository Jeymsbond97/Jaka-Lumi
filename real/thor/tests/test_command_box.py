"""The dashboard's Command box (/tasks/parse) reads a sentence exactly as voice does (Lumi.answer, both on
lumi.route): the same plan for the same words, English and Korean. No robot, no LLM (rules only on both sides):
python tests/test_command_box.py (-v: every reading)
Then what the box plans for hundreds of cup / delivery commands, held or not, at every Korean speech level and in
English the same ways (the owner's 2026-10-26 18:40 list first), and every stop word stopping a task."""
import re
import types

re._MAXCACHE = 100000                                 # the readers use more patterns than re's cache holds: 3x faster

from assistant import brain, lumi
from tasks import fetch

M = ["home", "dock2", "exit", "final"] + [f"p{i}" for i in range(1, 11)]
SENTENCES = [
    # the owner's examples
    "let's go exit point and go p9 point", "Let's go P5 (point).", "go to p5 and tell me the weather",
    "look at me and wave", "웨이브 하고 나 봐", "고개 들고 몇 시야?", "exit 갔다가 p9로 가", "first p1 then p2",
    "take the cup, go to p5, give it to Sarah and come back", "go to p10, then go left 1 meter and give it to the person",
    "go to p9, ask them for the cup, then bring it to p1", "컵 집고 p3로 가서 테이블에 놔",
    "Let's go P10 point and wait 30 seconds then come back here again.",
    # corrections
    "go to p1, no, p2", "go to p1, never mind", "앞으로 1미터, 아니 2미터 가",
    # one command
    "turn left", "한 바퀴 돌아", "move back 1 meter", "앞으로 1미터 가", "come here", "이리 와", "follow me", "look left",
    "lift yourself up", "wave", "손 흔들어", "stop", "멈춰", "p3로 가 줘", "spin around", "pick up the red cup", "빨간 컵 집어",
    "take this from me", "이거 받아", "open your hand", "bring me the cup from p1", "p3에서 컵 가져와",
    # talk, questions, refusals
    "what time is it?", "오늘 날씨 어때?", "hello", "what's your name?", "go to p12", "dance", "go to p5 and dance",
    "루미야 너 월급 받아?",
    # read by the intent bank or the chain's per-part reading (no keyword rule), answered out loud
    "왼쪽 쳐다봐", "오른쪽을 보십시오", "시선 좀 돌려 줘", "고개 숙이고 몸 좀 내려", "so glance to your right and then look up",
    "나 쳐다보고 follow me", "speak louder", "목소리 좀 줄여 줘", "더", "one more time", "what do you see?", "what are you doing?",
    # the owner's 18:40 misses, read the same by voice
    "컵 챙겨서 exit 가서 기다려", "컵 들고 p5 가서 기다려", "exit에 컵 갖다 놔", "컵 놔", "컵 가지고 출구로 가", "put the cup at exit",
    "go to exit with the cup", "p5 가서 누가 컵 줄 때까지 기다려", "야 루미, 오른쪽 보고 손 흔들어라", "stop it", "그만두세요",
]

# ---------- voice: Lumi.answer with every handler recorded, nothing moves, no LLM ----------
got_voice = []


class LLMReached(Exception):
    pass


def rec(*item):
    got_voice.append(item)
    return True


def steps_of(rule):                                   # what the mission runner does for a keyword command
    a, t = rule
    d, _, n = t.partition(" ")
    return {"go_to": lambda: [{"do": "go", "to": t}],
            "move": lambda: [{"do": "move", "dir": d, "m": float(n or 1)}],
            "turn": lambda: [{"do": "turn", "deg": 180.0 if d == "around" else (1 if d == "left" else -1) * float(n or 90)}],
            "arm": lambda: [{"do": "arm", "pose": t}],
            "pick": lambda: [{"do": "pick", "object": t.split()[-1], "colour": t.split()[0] if " " in t else None}],
            }.get(a, lambda: None)()


def quick(text, rule=None):
    rule = rule or brain.intent(text, M)
    if not rule or rule[0] not in lumi.QUICK_RULES:
        return False
    if rule[0] == "fetch":
        return rec("fetch")
    if rule[0] in ("weather", "search") or rule[0] == "put":
        return rec("talk")                            # put with the hand empty (voice: idle here): "my hand is empty"
    s = steps_of(rule)
    return rec("steps", s) if s else rec("command", rule[0])


def hand(text):
    h = brain.hand_request(text, False, L.brain, M)
    if h and h[0] == "receive":
        return rec("steps", [{"do": "receive", "object": h[1], "from_hand": True}])
    return rec("talk")


fetch.check_hand = lambda: False
lumi.log = fetch.log = lambda *a: None
lumi.mouth = types.SimpleNamespace(say=lambda *a, **k: None, lang_of=lambda t: "ko" if brain.HANGUL.search(t) else "en",
                                recent_speech=lambda s=30.0: "")
lumi.ears = types.SimpleNamespace(heard_lang=lambda x: x, last_stt={}, understood=lambda: True, heard_clearly=lambda: True)
real_seeing = lumi.seeing.answer
lumi.seeing.answer = lambda t, lang="en", frames=None, slow_line=None: real_seeing(t, lang, frames=[])   # no camera
L = lumi.Lumi.__new__(lumi.Lumi)
L.lang, L.markers, L.current, L.patrol = "en", M, None, None
L.now_doing = lambda: ("", "")
for name in ("follow_stop", "voice_setting", "fixed_answer", "drive_words", "mission_running", "chain_busy", "fetch_voice",
             "pointed_drive"):
    setattr(L, name, lambda *a, **k: False)
L.fetch_status = lambda: None
L.keep_listening = lambda: None
L.fetch_say = lambda *a: None
L.stop_all = lambda text="": rec("stop")
L.chain_request = lambda text, plan=None: rec("chain", [[k, w] for k, w, _ in plan])
L.mission_request = lambda text, read=None: rec("talk") if read[1] else rec("steps", read[0])
L.hand_command = hand
L.quick_command = quick
L.end_conversation = lambda *a: rec("talk")
L.sing_song = lambda *a: rec("talk")


def voice(text):
    got_voice.clear()
    L.brain = brain.Brain()
    L.brain.respond_stream = lambda *a, **k: (_ for _ in ()).throw(LLMReached())
    try:
        L.answer(text)
    except LLMReached:
        rec("talk")
    return got_voice[0] if got_voice else ("talk",)


# ---------- the box ----------
from api import server
server.agv.markers = lambda: M


def box(text):
    r = server.task_parse(server.ParseBody(text=text))
    a = r["action"]
    if a == "steps":
        return ("steps", r["steps"])
    if a == "command" and r.get("talk"):
        return ("talk",)                              # answered out loud by the assistant, as by voice
    if a == "command":
        return ("chain", r["parts"]) if "parts" in r else ("stop",) if r["sentence"] == "Stop." else \
            ("command", r["rule"][0]) if "rule" in r else ("command", None)
    if a == "fetch":
        return ("fetch",)
    return ("talk",)


bad = []
for t in SENTENCES:
    v, b = voice(t), box(t)
    if "-v" in __import__("sys").argv:
        print(t, "->", v)
    if v != b:
        bad.append(t)
        print(f"DIFFERENT {t!r}\n  voice {v}\n  box   {b}")
print(f"{len(SENTENCES) - len(bad)}/{len(SENTENCES)} the same by voice and in the Command box")
assert not bad


# ---------- what the box plans: one short line per reading ----------
HELD = [False]
fetch.check_hand = lambda: HELD[0]
fetch.state = lambda: {"holding": HELD[0]}
fetch.held_name = lambda lang="en": "the white cup"


def where(p):
    if isinstance(p, dict) and "name" in p:
        return " ".join(x for x in (p.get("side"), p.get("colour"), p["name"].replace("dining table", "table")) if x)
    return p.get("marker") if isinstance(p, dict) else str(p)


def plan(text, held=False):
    """"pick cup; go exit; wait", "fetch cup here>exit place", "carry p5 hold", "place left table", "give", "empty"
    (my hand is empty), "ask: <the question>" (a place not on the map), "talk" (the LLM / the assistant answers)."""
    HELD[0] = held
    r = server.task_parse(server.ParseBody(text=text))
    a = r["action"]
    if a == "steps":
        return "; ".join(" ".join(str(where(v)) for k, v in st.items() if v not in (None, False, "") and k != "from_hand")
                         for st in r["steps"]) + (" !" + r["problems"][0] if r["problems"] else "")
    if a == "fetch":
        t = r["task"]
        return " ".join(x for x in ("fetch", t.get("prefer"), t["colour"], t["object"], f"{where(t['source'])}>{where(t['dest'])}",
                                    t["finish"]) if x)
    if a in ("place", "give"):
        return a + (" on " + where(r["task"]["on"]) if (r.get("task") or {}).get("on") else "")
    if a == "carry":
        return f"carry {where(r['task']['dest'])} {r['task'].get('then') or 'hold'}"
    if a == "command":
        return "stop" if r["sentence"] == "Stop." else "chain" if "parts" in r else \
            "rule " + " ".join(x for x in r["rule"] if x) if "rule" in r else \
            "talk:status" if r.get("talk") == "status" else "talk"
    p = r.get("problems") or []
    return "empty" if p and "hand is empty" in p[0] else "ask: " + p[0] if p else \
        "ask: " + r["sentence"] if r.get("talk") == "refuse" else "talk"


def ko_levels(v, h):
    """A request in every Korean speech level: v the 반말 verb ("놔"), h the stem of -세요 / -십시오 ("놓으")."""
    return [v, f"{v} 줘", f"{v}요", f"{v} 주세요", f"{h}세요", f"{h}십시오", f"{v} 주십시오", f"{v} 주시겠어요?",
            f"{v} 주시겠습니까?", f"{v} 줄래?", f"{v} 주실래요?", f"{v} 주게", f"{v} 주이소", f"{v} 도", f"{v} 주라",
            f"{v} 줘잉", f"{v} 주셨으면 해요", f"{v} 주시면 감사하겠습니다", f"{v} 주면 안 될까요?", f"{v} 주시면 안 될까요?",
            f"{v} 주실 수 있나요?", f"{v}줘", f"{v} 쫌 줘", f"{v} 줘 봐", f"{v} 주시지요", f"{v} 주시오"]


EN_LEVELS = ["{x}", "please {x}", "{x}, please", "can you {x}?", "could you {x}?", "would you {x}?", "will you {x}?",
             "could you please {x}?", "can u {x}", "I'd like you to {x}", "I need you to {x}", "I want you to {x}",
             "hey Lumi, {x}", "Lumi, {x} now", "go ahead and {x}", "kindly {x}", "if you don't mind, {x}",
             "would you be so kind as to {x}?", "do me a favor and {x}", "yo, {x}", "{x} pls", "{x} real quick",
             "can you {x} for me please?", "{x}, thanks", "would it be possible to {x}?", "Lumi could you {x}"]
VERB = {"wait": ("기다려", "기다리"), "put_at": ("갖다 놔", "갖다 놓으"), "put": ("놔", "놓으"), "pick": ("집어", "집으"),
        "bring": ("가져와", "가져오"), "down": ("내려놔", "내려놓으"), "go": ("가", "가"), "take": ("가져가", "가져가"),
        "hand": ("건네", "건네주")}
KO_T = [   # (words with {} for the verb, verb, holding, plan)
    ("컵 들고 exit 가서 {}", "wait", False, "pick cup; go exit; wait"),
    ("컵 챙겨서 p5 가서 {}", "wait", False, "pick cup; go p5; wait"),
    ("exit에 컵 {}", "put_at", False, "fetch cup here>exit place"),
    ("컵을 p3 테이블에 {}", "put", False, "fetch cup here>p3 place"),
    ("컵 {}", "pick", False, "pick cup"),
    ("p1에서 컵 {}", "bring", False, "fetch cup p1>here hold"),
    ("컵 {}", "down", True, "place"),
    ("왼쪽 테이블에 {}", "put", True, "place left table"),
    ("그거 나한테 {}", "hand", True, "give"),
    ("p5로 {}", "take", True, "carry p5 hold"),
    ("p5로 {}", "go", False, "go p5"),
    ("컵 {}", "put", False, "empty"),
    ("그거 {}", "put", True, "place"),
]
EN_T = [
    ("take the cup to exit and wait there", False, "pick cup; go exit; wait"),
    ("grab the cup, go to p5 and wait", False, "pick cup; go p5; wait"),
    ("put the cup at exit", False, "fetch cup here>exit place"),
    ("put the cup on the table at p3", False, "fetch cup here>p3 place"),
    ("pick up the cup", False, "pick cup"),
    ("bring me the cup from p1", False, "fetch cup p1>here hold"),
    ("put the cup down", True, "place"),
    ("put it on the table on your left", True, "place left table"),
    ("hand it to me", True, "give"),
    ("take it to p5", True, "carry p5 hold"),
    ("go to p5", False, "go p5"),
    ("put the cup down", False, "empty"),
    ("put that down", True, "place"),
]
NO_PLACE = "ask: I don't have a place called {} on this map. I know: " + ", ".join(M) + "."
READ = [   # the owner's Korean cup / delivery list (2026-10-26 18:40), then more of the same kinds
    ("컵 들고 exit 가서 건네줘", False, "pick cup; go exit; give"),
    ("컵 가지고 exit로 가서 사람한테 줘", False, "pick cup; go exit; give"),
    ("컵 집어서 exit에 갖다 줘", False, "pick cup; go exit; give"),
    ("컵 챙겨서 exit 가서 기다려", False, "pick cup; go exit; wait"),
    ("컵 들고 exit로 가 줘", False, "fetch cup here>exit hold"),
    ("컵 들고 exit 가", False, "pick cup; go exit"),
    ("exit로 컵 가져다 줘", False, "pick cup; go exit; give"),
    ("exit에 컵 갖다 놔", False, "fetch cup here>exit place"),
    ("컵을 exit 테이블에 놔 줘", False, "fetch cup here>exit place"),
    ("p1에서 컵 가져와", False, "fetch cup p1>here hold"),
    ("p1 가서 컵 가져와", False, "fetch cup p1>here hold"),
    ("p1에 있는 컵 가져다 줘", False, "fetch cup p1>here hold"),
    ("p1에서 빨간 컵 집어서 p5로 가져가", False, "fetch red cup p1>p5 hold"),
    ("빨간 컵 집어서 p5로 가져가 줘", False, "fetch red cup here>p5 hold"),
    ("컵 집어 주게", False, "pick cup"), ("컵 집어도", False, "pick cup"), ("컵 좀 집어 주이소", False, "pick cup"),
    ("컵 픽업해 줘", False, "pick cup"), ("컵 잡아", False, "pick cup"), ("컵 들어", False, "pick cup"),
    ("저 컵 가져와", False, "fetch cup here>here hold"),
    ("그 컵 좀 가져다 주세요", False, "pick cup; give"), ("컵 가져다 주실래요?", False, "pick cup; give"),
    ("컵 가져다 주시겠습니까?", False, "pick cup; give"), ("컵 갖다 주게", False, "pick cup; give"),
    ("컵 갖고 와", False, "fetch cup here>here hold"), ("물병 가져와", False, "fetch bottle here>here hold"),
    ("바나나 집어서 p3로 가져가", False, "fetch banana here>p3 hold"),
    ("사과 p2에 놔", False, "fetch apple here>p2 place"),
    ("컵 들고 p5 가서 민수한테 줘", False, "pick cup; go p5; give 민수"),
    ("컵 들고 p5 가서 기다려", False, "pick cup; go p5; wait"),
    ("컵 들고 p5까지 가서 거기 있는 사람한테 줘", False, "pick cup; go p5; give"),
    ("컵 들고 exit 가서 건네주고 돌아와", False, "pick cup; go exit; give; go here"),
    ("컵 집고 p3로 가서 테이블에 놔", False, "fetch cup here>p3 place"),
    ("p9 가서 컵 받아서 p1으로 가져와", False, "go p9; receive cup; go p1"),
    ("이 컵 받아", False, "receive cup"), ("이거 받아서 exit에 갖다 줘", False, "receive; go exit; give"),
    ("컵 내려놔", False, "empty"), ("컵 놔", False, "empty"), ("컵 내려놔", True, "place"), ("컵 놔", True, "place"),
    ("컵 줘", False, "pick cup; give"), ("컵 나한테 줘", False, "pick cup; give"), ("그거 나한테 건네줘", False, "empty"),
    ("p2 테이블에 있는 컵 가져와", False, "fetch cup p2>here hold"),
    ("exit 갔다가 p9로 가", False, "go exit; go p9"), ("p5로 가 줘", False, "go p5"),
    ("p5로 가서 30초 기다렸다가 돌아와", False, "go p5; wait 30.0; go here"),
    ("컵 들고 exit 가서 줘 그리고 집에 가", False, "pick cup; go exit; give; go home"),
    ("exit 포인트로 컵 가져가", False, "fetch cup here>exit hold"), ("엑싯으로 컵 가져가", False, "fetch cup here>exit hold"),
    ("컵 가지고 출구로 가", False, NO_PLACE.format("출구")),     # 출구 is no marker: asked, never taken for "exit"
    ("출구로 가", False, NO_PLACE.format("출구")), ("컵 들고 화장실로 가 줘", False, NO_PLACE.format("화장실")),
    ("엑시트로 가", False, "go exit"),
    # put / place words and sides, held
    ("왼쪽 테이블에 놔", True, "place left table"), ("오른쪽에 내려놔 주세요", True, "place right table"),
    ("put it on the right side", True, "place right table"), ("put it on the table on your left", True, "place left table"),
    ("테이블에 놔", True, "place on table"), ("흰 테이블에 올려놔 주세요", True, "place on white table"),
    ("put it on the white table", True, "place on white table"), ("그거 놔 줘", True, "place"),
    ("그거 놔 쫌 줘", True, "place"), ("put it down", True, "place"), ("set it down please", True, "place"),
    ("p5로 가 줘", True, "carry p5 hold"), ("그거 p5로 옮겨 줘", True, "carry p5 hold"), ("p5로 들고 가", True, "carry p5 hold"),
    ("bring it to p5", True, "carry p5 hold"), ("carry it to p5", True, "carry p5 hold"),
    ("p5에 가져다 줘", True, "carry p5 give"), ("take it to p5 and give it to them", True, "go p5; give"),
    ("p5 테이블에 놔 줘", True, "carry p5 place"), ("put it on the table at p5", True, "carry p5 place"),
    ("give it to me", True, "give"), ("나한테 줘", True, "give"), ("저한테 주세요", True, "give"),
    # English the same
    ("take the cup, go to exit and hand it over", False, "pick cup; go exit; give"),
    ("grab the cup and wait at p5", False, "pick cup; go p5; wait"),
    ("put the cup at p3", False, "fetch cup here>p3 place"), ("leave the cup at exit", False, "fetch cup here>exit place"),
    ("put the red cup on the white table at exit", False, "fetch red cup here>exit place"),
    ("take the cup to p3 and put it down", False, "fetch cup here>p3 place"),
    ("bring the cup to p3 and put it on the table", False, "fetch cup here>p3 place"),
    ("deliver the cup to p5", False, "pick cup; go p5; give"), ("take the cup to the exit", False, "fetch cup here>exit hold"),
    ("pick up the cup and give it to me", False, "pick cup; give"), ("can I have the cup?", False, "pick cup; give"),
    ("bring me the red cup from p2", False, "fetch red cup p2>here hold"), ("put the cup down", False, "empty"),
    ("put it on the table", False, "empty"), ("give it to me", False, "empty"),
    # night-4 leftovers: the same meaning at any level, EN = KO
    ("hand it to Minsu", True, "give"), ("민수한테 줘", True, "give"), ("give it to Minsu", True, "give"),
    ("민수한테 건네줘", True, "give"), ("그거 놔 줘", False, "empty"), ("그거 놔 주세요", False, "empty"),
    ("아까 그 자리로 돌아가 줄래?", False, "rule come_back"), ("허리를 왼쪽으로 돌려 주셨으면 해요", False, "rule waist left"),
    ("허리 왼쪽으로 돌려 주시면 감사하겠습니다", False, "rule waist left"), ("허리 왼쪽으로 돌려 주면 안 될까요?", False, "rule waist left"),
    ("충전하러 가 주셨으면 해요", False, "go home"), ("충전하러 가 주시면 감사하겠습니다", False, "go home"),
    ("충전하러 가 주면 안 될까요?", False, "go home"), ("차지하러 가 줘", False, "go home"), ("go charge", False, "go home"),
    ("컵 내려놔 주셨으면 해요", True, "place"), ("컵 내려놔 주시면 감사하겠습니다", True, "place"),
    ("컵 내려놔 주면 안 될까요?", True, "place"), ("put that cup down", True, "place"), ("put that cup down for me", True, "place"),
    ("go grab me a cup", False, "pick cup; give"), ("컵 하나 갖다 줘", False, "pick cup; give"),
    ("chin up, buddy", False, "talk"), ("lift your chin up", False, "rule look up"),
    ("로봇아, 이 센티미터 아래로 내려 줘", False, "rule lift down 20"), ("20cm 아래로 내려 줄래~?", False, "rule lift down 200"),
    ("아래로 내려놔", True, "place"), ("테이블 위에 내려 줘", True, "place on table"),
    # Konglish, dialect, whisper's spellings
    ("컵 픽업해서 exit 가서 웨이트 해", False, "pick cup; go exit; wait"), ("cup 들고 exit 가", False, "pick cup; go exit"),
    ("컵 테이크해서 p5로 가져가", False, "fetch cup here>p5 hold"), ("exit에 컵 드랍해 줘", False, "fetch cup here>exit place"),
    ("컵 그랩해 줘", False, "pick cup"), ("컵 픽업 플리즈", False, "pick cup"), ("pick up 컵 해 줘", False, "pick cup"),
    ("take 컵 to p5", False, "fetch cup here>p5 hold"), ("컵 들고 피파이브 가서 기다려", False, "pick cup; go p5; wait"),
    ("컵 들고 피 오 가서 기달려", False, "pick cup; go p5; wait"), ("그 컵 쫌 갖다 도", False, "pick cup; give"),
    ("exit에 컵 갖다 놓그라", False, "fetch cup here>exit place"), ("컵 좀 퍼뜩 집어 주이소", False, "pick cup"),
    ("컵 함 집어 봐라", False, "pick cup"), ("컵 집으라", False, "pick cup"), ("컵 집어 줘유", False, "pick cup"),
    ("p1에서 컵 갖고 와 주라", False, "fetch cup p1>here hold"), ("익싯에 컵 갖다 놔", False, "fetch cup here>exit place"),
    ("p1 에서 컵 가저와", False, "fetch cup p1>here hold"), ("컵집어", False, "pick cup"), ("빨간컵 집어줘", False, "pick cup red"),
    ("빨강 컵 집어", False, "pick cup red"), ("하얀 컵 집어", False, "pick cup white"),
    ("흰색 컵 p3에 놔", False, "fetch white cup here>p3 place"),
    ("drop the cup off at exit", False, "fetch cup here>exit place"), ("leave the cup at p3 for me", False, "fetch cup here>p3 place"),
    ("carry the cup over to p5 and wait there", False, "pick cup; go p5; wait"),
    ("take the cup with you to p5 and wait", False, "pick cup; go p5; wait"), ("pick up teh cup", False, "pick cup"),
    ("go to exit with the cup", False, "fetch cup here>exit hold"), ("head to p5 with the red cup", False, "fetch red cup here>p5 hold"),
    ("fetch me a cup from p1", False, "fetch cup p1>here hold"), ("take a cup to p5 and give it to Sarah", False, "pick cup; go p5; give Sarah"),
    ("can you bring a cup to the person at p5?", False, "pick cup; go p5; give"),
    ("컵 p5에 있는 사람한테 갖다 줘", False, "pick cup; go p5; give"), ("빨간 컵 p5에 계신 분께 갖다 드려", False, "pick cup red; go p5; give"),
    ("drop it off at exit", True, "carry exit place"), ("leave it at p5", True, "carry p5 place"), ("drop it at p3", True, "carry p3 place"),
    ("put it on the white table on your right", True, "place right white table"), ("set it down on your left", True, "place left table"),
    ("excuse me robot, first look me, then follow me", False, "chain"), ("야 루미, 오른쪽 보고 손 흔들어라", False, "chain"),
    ("hello robot, first turn left, then lower yourself", False, "chain"),
    ("악수하고 lower yourself 해 주세요", False, "chain"), ("오늘 날짜 알리고 look left 해 주세요", False, "chain"),
    ("wave 하고 look left 해 줘", False, "chain"), ("루미 님, 손 흔드시고 몸 내러 주시길 부탁드립니다", False, "chain"),
    ("몸내리고오른쪽으로돌아주라", False, "chain"), ("컵들고exit가서기다려", False, "pick cup; go exit; wait"),
    ("컵들고p5가서민수한테줘", False, "pick cup; go p5; give 민수"), ("컵 들구 p5 가서 기다리", False, "pick cup; go p5; wait"),
    ("wait at p5 with the cup", False, "pick cup; go p5; wait"), ("lemme see you go charge", False, "go home"),
    ("let me see you wave", False, "rule wave"), ("okay see you", False, "talk"), ("you come behind me", False, "rule follow"),
    ("here's your task: get over here", False, "talk"), ("Mina, what are you doing over there?", False, "talk"),
    ("민수야, 너 거기서 뭐 하고 있어?", False, "talk"), ("루미야 뭐 하고 있어?", False, "talk:status"),
    ("계속 들고 있어 주세요", True, "talk"), ("keep holding it", True, "talk"), ("just hold it", True, "stop"),   # safety first: "hold it" stops (the cup stays held)
    ("give it back", True, "give"), ("돌려줘", True, "give"), ("hand it back to me", True, "give"), ("그거 다시 줘", True, "give"),
    ("put it back where you found it", True, "place"), ("원래 있던 데 놔 주세요", True, "place"),
    ("할머니께 이거 전해 드려", True, "give"), ("이거 저분께 드리세요", True, "give"), ("사장님께 드려 주십시오", True, "give"),
    ("그 컵 저 주시면 돼요", True, "give"), ("저한테 주시겠어요?", True, "give"), ("내놔", True, "give"), ("그거 이리 내", True, "give"),
    ("pass it to me", True, "give"), ("could I have it please", True, "give"), ("lemme have it", True, "give"),
    ("give it to that lady", True, "give"), ("테이블에 놔 주시면 돼요", True, "place on table"), ("내려놔 주십시오", True, "place"),
    ("p5로 가 주시겠어요?", True, "carry p5 hold"),
    ("gimme the cup", False, "pick cup; give"), ("could ya grab the cup", False, "pick cup"),
    ("can ya bring the cup to p5", False, "fetch cup here>p5 hold"), ("컵 줘요 빨리", False, "pick cup; give"),
    ("would you be a dear and fetch the cup from p1", False, "fetch cup p1>here hold"),
    ("kindly deliver the cup to p5", False, "pick cup; go p5; give"),
    # which one and which side
    ("왼쪽 컵 집어", False, "pick cup left"), ("pick up the cup on the left", False, "pick cup left"),
    ("오른쪽에 있는 컵 집어 줘", False, "pick cup right"), ("grab the cup on your right", False, "pick cup right"),
    ("grab the smaller cup", False, "pick cup small"), ("작은 컵 집어 줘", False, "pick cup small"),
    ("제일 가까운 컵 집어", False, "pick cup near"),
    ("컵 p3 왼쪽 테이블에 놔", False, "pick cup; go p3; place left table"),
    ("put the cup on the left table at p3", False, "pick cup; go p3; place left table"),
    ("p3 왼쪽 테이블에 놔", True, "go p3; place left table"), ("put it on the left table at p3", True, "go p3; place left table"),
    ("오른쪽 테이블에 내려놔", True, "place right table"), ("오른쪽 테이블에 내려놔", False, "empty"),
    ("왼쪽 테이블에 있는 컵 가져와", False, "fetch left cup here>here hold"),
    ("bring me the cup from the right table", False, "fetch right cup here>here hold"),
    # holding: the box reads the hand as voice does (E1's parity run, 2026-10-27): no motion on talk about it
    ("give me a shake", True, "talk"), ("you wave hand please", True, "talk"), ("로봇아, 핸드 오픈 해 주세요", True, "talk"),
    ("컵 내려놓지 마", True, "talk"), ("제자리에 놓지 마~", True, "talk"), ("탁자 위에 놓지 마 ㅋㅋ", True, "talk"),
    ("옆 테이블에 놓지 마세요", True, "talk"), ("루미는 나한테 건네줄 수 있대", True, "talk"), ("루미가 나한테 건네주는 걸 봤나", True, "talk"),
    ("mira mira put ur phone away honey", True, "talk"), ("캘리브레이션 보게, 아까 컵 내려어놓는 거 봤어?", True, "talk"),
    ("애들 재우고 싶다, 루미, 내놔 제발", True, "talk"), ("우리 루미, 이리 내놔 봐", True, "give"),
    ("로봇 씨, 나한테 지금 주십시오", True, "give"), ("할머니께 드려 봐", True, "give"), ("Lumi, I want you pass it to me", True, "give"),
    ("저한테 주실 수 있으신가요?", True, "give"), ("선생님께 드리세요", True, "give"), ("lower it down", True, "place"),
    ("you putt dawn that", True, "place"), ("lay it on this table lay it on this table please", True, "place"),
    ("왼쪽에 내려놓고 오른편 컵 잡아 줘", True, "chain"), ("put it back", True, "place"), ("제자리에 갖다 놔", True, "place"),
    ("pick up the cup on the left table", False, "pick cup left"),
    ("pick up the cup over on your left", False, "pick cup left"), ("grab the cup sitting on your right", False, "pick cup right"),
    ("grab the cup by your side", False, "pick cup near"), ("옆에 있는 컵 집어", False, "pick cup near"),
    ("레프트 컵 집어", False, "pick cup left"), ("라이트 컵 집어 줘", False, "pick cup right"),
    ("백팩 집어 줘", False, "ask: The backpack is too big for my hand."),
    # asides: said, taken back, for later, reported or read out: no motion now
    ("Lumi buddy, shake hands with me... ah, forget I said that", False, "talk"),
    ("lumi the moment the bell rings wave goodbye to us", False, "talk"),
    ("Lumi dear, my manager wanted you to put it down gently first thing today", True, "talk"),
    ("lumi on paper it is writing shake my hand", False, "talk"), ("Rumi robot hand it to me is very funny thing", True, "talk"),
    ("루미야 come friday lets shake hands", False, "talk"), ("동생아 너도 잘 가라고 손 흔들어 봐", False, "talk"),
    ("no need for you to put it down by the coffee machine today", True, "talk"),
    ("우리 루미~ 왼쪽에 있는 사람한테 건네 ㄱㄱ~ 는 장난 ㅋㅋ", True, "talk"),
    ("로봇이 하얀 탁자 위에 올려놓는 장면이 인상 깊었습니다", True, "talk"), ("들고 있는 거 나 주쇼", True, "give"),
    ("robot, rotate right 45 degrees, is okay for you?", False, "turn -45.0"),
    ("Stretch your arm out toward me, is okay for you?", False, "arm reach"),
    ("루미 팔 원래대로 돌려놓으실 필요는 전혀 없습니다", False, "talk"), ("루미야 team everyone put your arm down now now", False, "talk"),
    ("루미야잉, 담에 오른쪽으로 직각으로 돌아 줍써", False, "talk"),
    ("are robots like you built to stretch your arm out toward me?", False, "talk"),
    ("로봇 로봇이 팔 접는 걸 보니 세상 좋아졌구먼", False, "talk"),
    ("ㅋㅋ 손 내려 저용 이거 밈이잖아", False, "talk"), ("Robot look at me is very funnny thing.", False, "talk"),
    ("루미 나한테 손 내밀 수 있대 대박.", False, "talk"), ("이따밤에허리왼쪽으로60도돌려줘ㅋㅋ", False, "talk"),
    ("now mister robot, cup go back same place, please", True, "place"), ("허리 오른쪽으로 45도 돌여", False, "rule waist right 45"),
    ("lumi buddy hold it", False, "stop"), ("루미야 under no circumstances close the gripper", False, "talk"),
    ("Lumi, no no, not scoot left 35 cm", False, "talk"), ("손 open 돼 있어?", False, "talk"), ("그리퍼 오픈돼 있어?", False, "talk"),
    ("저기 컵 살포시 내려놓지는 마세요 괜찮아요", True, "talk"), ("look 60 deg to right, is okkay for you?", False, "rule look right 60"),
    ("Face forward again for me, possible?", False, "rule look center"), ("너 팔 접을 수 있지?", False, "talk"),
    ("팔 접어 줄 수 있지?", False, "arm fold"),
    ("죄송한데요, 고개만 돌려서 뒤가 보이십니까?", False, "talk"), ("루미야, 등 좀 보이세요", False, "talk"),
    ("윤년 말씀하실 때 저 좀 봐 주시겠어요?", False, "rule look me"), ("편할 때 손 흔들어 줘", False, "rule wave"),
    ("when you get to p1, wave", False, "talk"),
    ("robot turn forty-five degrees to right ah sorry no need", False, "talk"),
    ("루미, please 루미야 turn left — scratch that, yesterday I watched a robot turn right on TV", False, "ask: Taken back: nothing to do."),
    ("cup in front you pick oops I meant on paper it is writing pickup that cup by you side", False, "ask: Taken back: nothing to do."),
    ("Lumi bring me the cup from the exit before, very good", False, "talk"),
    ("mister robot you no need twist your waist 45° to the right okay okay", False, "talk"),
    ("go to p1, no, exit", False, "go exit"), ("turn left, I mean right", False, "turn -90.0"),
    ("두 시 방향에 있는 컵 집어", False, "pick cup right"), ("열 시 방향 컵 집어 줘", False, "pick cup left"),
    ("내 얼굴 기억해", False, "talk"),
    ("루미야 under no circumstances close the gripper", False, "talk"), ("go back to where you were before", False, "rule come_back"),
    ("deliver the cup to exit and come back", False, "pick cup; go exit; give; go here"),
    ("my hands are full, so could you deliver the cup to exit and come back?", False, "pick cup; go exit; give; go here"),
    ("컵 exit에 갖다주고 돌아와", False, "pick cup; go exit; give; go here"), ("give me the cup", True, "give"),
    ("you wave hand please", True, "talk"), ("Rumi dear drop the cup off at exit then come back here much obliged", False, "pick cup; go exit; place; go here"),
    ("pick up the backpack", False, "ask: The backpack is too big for my hand."), ("오른쪽 테이블에 있는 빨간 컵 집어 줘", False, "pick cup red right"),
    ("컵이랑 같이 p5로 가", False, "fetch cup here>p5 hold"), ("컵 하고 같이 exit 가 줘", False, "fetch cup here>exit hold"),
    ("컵 가지고 p5에서 기다려", False, "pick cup; go p5; wait"), ("컵 들고 p5에 가 있어", False, "pick cup; go p5; wait"),
    ("이 컵 p5까지 좀 날라 줘", False, "fetch cup here>p5 hold"), ("컵 좀 p5로 옮겨 줘", False, "fetch cup here>p5 hold"),
    ("컵을 p5 테이블 위에 올려놔 주십시오", False, "fetch cup here>p5 place"), ("컵 하나만 가져다주시겠어요", False, "pick cup; give"),
    ("p5에 컵 좀 가져다 놓을래?", False, "fetch cup here>p5 place"), ("take this cup to p5", False, "fetch cup here>p5 hold"),
    ("could you take a cup over to exit for me", False, "fetch cup here>exit hold"),
    ("bring a cup over to p3 and leave it there", False, "fetch cup here>p3 place"),
    ("carry the cup to p5 and set it down", False, "fetch cup here>p5 place"),
    # people at places, receive, wait: EN = KO
    ("take the cup to Minsu at p5", False, "pick cup; go p5; give Minsu"), ("컵 p5에 있는 민수한테 갖다 줘", False, "pick cup; go p5; give 민수"),
    ("컵 들고 p5 가서 민수 씨께 드려", False, "pick cup; go p5; give 민수"),
    ("컵을 p5에 계신 사장님께 갖다 드리세요", False, "pick cup; go p5; give"), ("bring the cup to the boss at p5", False, "pick cup; go p5; give"),
    ("p3 가서 사라한테 컵 받아 와", False, "go p3; receive cup; go here"),
    ("go to p3, get the cup from Sarah and bring it back", False, "go p3; receive cup; go here; give"),
    ("p3에서 민수한테 컵 받아서 p5에 있는 사람한테 줘", False, "receive cup; go p5; give"),
    ("take the cup and wait for me at p5", False, "pick cup; go p5; wait"), ("컵 들고 p5에서 나 기다려", False, "pick cup; go p5; wait"),
    ("p5 가서 누가 컵 줄 때까지 기다려", False, "go p5; receive cup 300.0"),
    ("go to p5 and wait until someone gives you a cup", False, "go p5; receive cup 300.0"),
    ("wait until I say go, then go to p5", False, "talk"),
    ("컵 들고 p5 가서 10초 기다렸다가 돌아와", False, "pick cup; go p5; wait 10.0; go here"),
    ("take the cup to p5, wait 10 seconds and come back", False, "pick cup; go p5; wait 10.0; go here"),
    ("컵 가지고 p5 갔다가 p3로 가", False, "pick cup; go p5; go p3"), ("take the cup to p5 then go to p3", False, "pick cup; go p5; go p3"),
    ("컵 들고 p5 가서 테이블에 놓고 와", False, "pick cup; go p5; place table; go here"),
]
bad = []
for words, verb, held, want in KO_T:
    READ += [(words.format(f), held, want) for f in ko_levels(*VERB[verb])]
for x, held, want in EN_T:
    READ += [((f.format(x=x)[0].upper() + f.format(x=x)[1:]) if j % 3 == 0 else f.format(x=x), held, want)
             for j, f in enumerate(EN_LEVELS)]
for text, held, want in READ:
    got = plan(text, held)
    if "-v" in __import__("sys").argv:
        print(f"{text!r:50} {'holding ' if held else ''}-> {got}")
    if got != want:
        bad.append(text)
        print(f"WRONG {text!r}{' (holding)' if held else ''}\n  want {want}\n  got  {got}")
# ---------- the held thing is named in what the box reads back (never "something") ----------
HELD[0] = True
for text, want in (("put it down", "Put the white cup on the table near me."), ("컵 내려놔", "Put the white cup on the table near me."),
                   ("give it to me", "Hand the white cup to you."), ("나한테 줘", "Hand the white cup to you."),
                   ("take it to p5", "Bring the white cup to p5 and keep holding it."),
                   ("p5 테이블에 놔 줘", "Bring the white cup to p5 and put it on the table there.")):
    got = server.task_parse(server.ParseBody(text=text))["sentence"]
    if got != want:
        bad.append(text)
        print(f"WRONG {text!r} (holding the white cup)\n  want {want}\n  got  {got}")


# ---------- English marker names said in Korean (place_words: as they sound, never translated) ----------
CONF = ["home", "dock2", "Gallery_1", "Gallery_2", "Booth_12", "Gate_B7", "booth_A", "Elevator", "Registration"]
server.agv.markers = lambda: CONF
for text, want in (("갤러리 투로 가 줘", "go Gallery_2"), ("갤러리 1로 가", "go Gallery_1"), ("부스 십이로 가 줘", "go Booth_12"),
                   ("비 세븐 게이트로 가", "go Gate_B7"), ("게이트 비 세븐으로 가 줘", "go Gate_B7"), ("에이 부스로 가", "go booth_A"),
                   ("엘리베이터로 가 줘", "go Elevator"), ("레지스트레이션으로 가", "go Registration"), ("go to gate b seven", "go Gate_B7"),
                   ("홈 포지션으로 가", "go home")):
    got = plan(text)
    if got != want:
        bad.append(text)
        print(f"WRONG {text!r}\n  want {want}\n  got  {got}")
server.agv.markers = lambda: ["home", "booth_3", "p5"]
for text, want in (("drop the cup off on the table at booth 3", "carry booth_3 place"), ("drop it off at booth 3", "carry booth_3 place"),
                   ("부스 3 테이블에 놔", "carry booth_3 place")):   # holding: there, never here
    got = plan(text, True)
    if got != want:
        bad.append(text)
        print(f"WRONG {text!r} (holding)\n  want {want}\n  got  {got}")
server.agv.markers = lambda: M


# ---------- stop words (the owner, 2026-10-26 21:10): every form at every level stops, also inside a sentence ----------
STOPS = ["멈춰", "멈춰요", "멈추세요", "멈춰 주세요", "멈춰 주시겠어요?", "멈추십시오", "멈춰 줘", "멈춰라", "멈추게", "멈춰 주이소",
         "멈춰 주실래요?", "멈춰 주시면 감사하겠습니다", "멈춰 주셨으면 해요", "멈춰 주면 안 될까요?", "멈춰 주시겠습니까?", "멈춰!",
         "그만", "그만해", "그만해요", "그만하세요", "그만하십시오", "그만 해 줘", "그만둬", "그만두세요", "이제 그만", "그만그만",
         "정지", "정지해", "정지하세요", "정지!", "스톱", "스탑", "스톱해", "스탑 해 줘", "스톱 스톱", "거기 서", "서!", "서", "서라",
         "거기 서 봐", "움직이지 마", "움직이지 마세요", "움직이지 마십시오", "가지 마", "잠깐 멈춰", "당장 멈춰", "멈처", "멈쳐",
         "멈춰어", "머엄춰", "스땁", "멈춰 멈춰", "루미야 멈춰", "루미 그만", "야 멈춰", "멈추시게", "그마안",
         "stop", "stop it", "stop now", "halt", "freeze", "Stop!", "STOP", "stop, stop", "please stop", "stop please",
         "Lumi stop", "Lumi, stop!", "stop right there", "stop moving", "stop the robot", "hold it right there", "stahp",
         "stopp", "stooop", "stob", "emergency stop", "would you stop, please?", "can you stop?", "stop that", "quit it",
         "cut it out", "don't move", "stay still", "hold still", "enough!", "that's enough", "whoa whoa"]
STOPS_INSIDE = ["루미야 그거 말고 멈춰 지금", "아 잠깐만 멈춰 봐 위험해", "okay Lumi stop, there's someone in the way",
                "wait wait stop it now", "컵 내려놓지 말고 멈춰", "야야 스톱 스톱", "저기 사람 있어 멈춰요", "no no no, stop",
                "Lumi, stop, you're going to hit the table", "그만, 그만해 이제", "다 됐어 멈춰 주세요", "careful, stop!",
                "멈춰버려", "동물을 멈춰버린 거랑 안해", "루미야 지금 바로 멈춰 주세요 위험해요", "stop, where are you going?",
                "루미 님, 멈춰 주실 수 있겠습니까?", "오케이, 야 루미, 당장 얼른 서", "okay Lumi, can you go ahead and hold it right there?",
                "야 루미 스톱", "루미야 그만해 주세요", "야 서", "lumi buddy hold it", "루미 씨 정지해 주십시오", "hey robot, freeze!",
                "로봇아 움직이지 마세요", "자, 루미 님, 그만하시죠", "루미루미, 당장 멈춰 줄 수 있지?"]
for text in STOPS + STOPS_INSIDE:                     # the task's own words (lumi.fetch_voice): the same stop
    if not lumi.stop_order(text, M):
        bad.append(text)
        print(f"NO STOP during a task {text!r}")
for text in STOPS + STOPS_INSIDE:
    for held in (False, True):
        got = plan(text, held)
        if got != "stop":
            bad.append(text)
            print(f"NO STOP {text!r}{' (holding)' if held else ''}: {got}")
print(f"{len(STOPS + STOPS_INSIDE)} stop words")
assert not bad
ko = sum(1 for t, _, _ in READ if brain.HANGUL.search(t))
print(f"{len(READ) - len(bad)}/{len(READ)} read right ({ko} Korean, {len(READ) - ko} English)")
assert not bad
print("command box ok")
