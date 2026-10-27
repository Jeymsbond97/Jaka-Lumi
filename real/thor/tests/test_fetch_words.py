"""Self-check of cup-task wordings (night 4, F1), no robot, no LLM: python tests/test_fetch_words.py

1. brain.parse_fetch: where the thing is (source), where it goes (dest), which one (prefer), at every speech level.
2. steps.rules: cup tasks of several parts (fetch then more, deliver and come back, put it at a place, wait until
   someone takes it, Korean calls / endings of every level, Korean written without spaces).
Notation of tests/test_steps.py."""
from assistant import brain, steps


def short(s):
    """The notation of tests/test_steps.py, the kinds used here."""
    w = s.split()
    if w[0] == "go":
        return {"do": "go", "to": w[1]}
    if w[0] == "pick":
        return {"do": "pick", "object": w[-1], "colour": w[1] if len(w) == 3 else None}
    if w[0] == "receive":
        return {"do": "receive", "object": w[1], **({"wait_s": steps.WAIT_GIVE_S} if w[-1] == "wait" else {})}
    if w[0] == "wait":
        if w[1:2] == ["order"]:
            return {"do": "wait", "s": steps.WAIT_ORDER_S, "until": "instruction"}
        return {"do": "wait", "s": float(w[1]) if len(w) > 1 else None}
    if w[0] == "turn":
        return {"do": "turn", "deg": float(w[1])}
    if w[0] == "place":
        return {"do": "place", "on": {"name": "dining table", "colour": None, "side": None} if len(w) > 1 else None}
    if w[0] == "give" and len(w) > 1:
        return {"do": "give", "person": s[5:]}
    return {"do": w[0]}

M = ["home", "p1", "p2", "p3", "p4", "p5", "Registration", "Main_Stage", "Coffee_Bar"]
P = lambda n: {"marker": n}

# ---- 1. one fetch: (object, colour, source, dest, finish[, prefer]); None = asked ----
FETCH = {
    "bring me the red cup from p3": ("cup", "red", P("p3"), "here", "hold"),
    "could you grab me the cup that's on p2?": ("cup", None, P("p2"), "here", "hold"),
    "get me the cup on the left from p1": ("cup", None, P("p1"), "here", "hold", "left"),
    "fetch the white cup from the coffee bar": ("cup", "white", P("Coffee_Bar"), "here", "hold"),
    "would you mind bringing the cup over from p5": ("cup", None, P("p5"), "here", "hold"),
    "p1 red cup bring me please": ("cup", "red", P("p1"), "here", "hold"),
    "bring the cup on p1 to p4": ("cup", None, P("p1"), P("p4"), "hold"),
    "take the cup from p1 to p4": ("cup", None, P("p1"), P("p4"), "hold"),
    "bring the cup to p1": ("cup", None, "here", P("p1"), "hold"),
    "p3에서 빨간 컵 가져와": ("cup", "red", P("p3"), "here", "hold"),
    "피삼에 있는 컵 좀 가져다줄래?": ("cup", None, P("p3"), "here", "hold"),
    "피투에 있는 왼쪽 컵 가져와 줘": ("cup", None, P("p2"), "here", "hold", "left"),
    "피원 컵 가져와": ("cup", None, P("p1"), "here", "hold"),
    "p1의 컵 가져와": ("cup", None, P("p1"), "here", "hold"),
    "커피 바에서 하얀 컵 갖다 주시겠어요?": ("cup", "white", P("Coffee_Bar"), "here", "hold"),
    "피오에서 작은 컵 좀 가져다 주십시오": ("cup", None, P("p5"), "here", "hold", "small"),
    "일 번 포인트에 있는 컵 좀 갖다 줘": ("cup", None, P("p1"), "here", "hold"),
    "피원에서 컵 가져다가 피사에 있는 테이블에 놔": ("cup", None, P("p1"), P("p4"), "place"),
    "컵을 p1에 갖다 놔": ("cup", None, "here", P("p1"), "place"),
    # a person, not a place: asked
    "bring the cup from p2 to Minsu": ("cup", None, P("p2"), None, "hold"),
    "p2에서 컵 가져다가 민수한테 줘": ("cup", None, P("p2"), None, "hold"),
    "빨간 옷 입은 여자분께 컵 갖다 드려": ("cup", None, "here", None, "hold"),
    # the place said without "to" / 로 (the dashboard, 2026-10-26): a drive there with it, or the way to the thing
    "take the cup and go p5": ("cup", None, "here", P("p5"), "hold"),
    "take the cup from p1 and go p5": ("cup", None, P("p1"), P("p5"), "hold"),
    "컵 들고 p5 가서 기다려": ("cup", None, "here", P("p5"), "hold"),
    "p2 가서 컵 가져와": ("cup", None, P("p2"), "here", "hold"),
}
bad = []
for text, want in FETCH.items():
    task, _ = brain.parse_fetch(text, M)
    got = (task["object"], task["colour"], task["source"], task["dest"], task["finish"]) + \
        ((task["prefer"],) if task.get("prefer") else ())
    if got != want:
        bad.append(f"FAIL fetch {text!r}\n  want {want}\n  got  {got}")

# ---- 2. several parts ----
STEPS = {
    "deliver the cup to p5 and come back": "pick cup | go p5 | give | go here",
    "take the cup to p5, leave it there and come back": "pick cup | go p5 | place | go here",
    "컵을 p5에 갖다 주고 돌아와": "pick cup | go p5 | give | go here",
    "컵 피오에 갖다 놓고 돌아와 주세요": "pick cup | go p5 | place | go here",
    "컵을 피오에 갖다 드리고 돌아오십시오": "pick cup | go p5 | give | go here",
    "bring me the cup from p2 and then go back home": "go p2 | pick cup | go here | give | go home",
    "p2에서 컵 가져다 주고 충전기로 가": "go p2 | pick cup | go here | give | go home",
    "p1에서 병 가져다 p2에 놔 주고 여기로 돌아와": "go p1 | pick bottle | go p2 | place | go here",
    "p1에 있는 컵을 p4로 가져다 놔": "go p1 | pick cup | go p4 | place",
    "go to p3 and wait until someone takes the cup": "go p3 | give",
    "피삼에 가서 누가 가져갈 때까지 기다려": "go p3 | give",
    "피삼에 가서 누가 받을 때까지 기다려 주세요": "go p3 | give",
    "p3에 가서 민수한테 컵 받아서 가져와": "go p3 | receive cup | go here",
    "go to p3, take the cup from Minsu and bring it to me": "go p3 | receive cup | go here | give",
    "컵 들고 p2로 가서 거기 있는 사람한테 줘": "pick cup | go p2 | give",
    "빨간 컵을 p4에 있는 민수한테 갖다 줘": "pick red cup | go p4 | give 민수",
    "fetch the cup from p1, then wait here": "go p1 | pick cup | go here | wait",
    "피원에서 빨간 컵 가져다가 피삼에 놔 줘": "go p1 | pick red cup | go p3 | place",
    "피일에서 컵 가져다 주시고 홈으로 가십시오": "go p1 | pick cup | go here | give | go home",
    "take the bottle to p2 and wait there until someone takes it, then come back": "pick bottle | go p2 | give | go here",
    "병 들고 피투로 가서 누가 가져갈 때까지 기다렸다가 돌아와": "pick bottle | go p2 | give | go here",
    "컵 피삼에 갖다 주고 10초 기다렸다가 홈으로 가": "pick cup | go p3 | give | wait 10 | go home",
    "빨간 컵을 피사에 갖다 놓으시고 돌아오세요": "pick red cup | go p4 | place | go here",
    "take the cup to the main stage and hand it to whoever is there": "pick cup | go Main_Stage | give",
    "find the red cup and bring it to me": "pick red cup | go here | give",
    "빨간 컵 찾아서 나한테 가져다 줘": "pick red cup | go here | give",
    "point one에서 빨간 컵 가져와서 P5에 있는 사람한테 줘": "go p1 | pick red cup | go p5 | give",
    "take the banana to the main stage and give it too Mr. Kim": "pick banana | go Main_Stage | give Mr. Kim",
    "에구 하얀 컵 집어서 p4로 가져가서 테이블에 놔, 응": "pick white cup | go p4 | place dining table",
    "p4에 가서 누가 빨간 컵 주면 받아 가지고 와": "go p4 | receive cup wait | go here",
    "p4 가서 십 초 wait 하고 와": "go p4 | wait 10 | go here",
    # a new order on the way (lumi.mission_talk reads it with steps.read)
    "no, bring it to p4 instead": "go p4",
    "아니야 피사로 가져가 줘": "go p4",
    "change of plan, go to p4 and put it down": "go p4 | place",
    "그거 저 사람한테 줘": "give",
    # calls and endings of every level, Konglish, no spaces
    "이보게 루미, 피삼에 가서 30초 기다렸다가 돌아오게나": "go p3 | wait 30 | go here",
    "루미 님께서 피삼으로 가서 30초 기다렸다가 돌아와 주시길 부탁드립니다": "go p3 | wait 30 | go here",
    "아야 루미, 피투로 가서 1분 기다렸다가 돌아와 주시겄슈": "go p2 | wait 60 | go here",
    "우리 루미, 피투로 가서 한 바퀴 돌고 돌아와 주라~": "go p2 | turn 360 | go here",
    "자네, 피투로 가서 오더 받고 컴백해 주게나": "go p2 | wait order | go here",
    "피사에가서5분있다가다시오세요": "go p4 | wait 300 | go here",
    "홈 포지션에 들렀다가 피투로 가게나": "go home | go p2",
}
for text, want in STEPS.items():
    got, unread = steps.rules(text, M)
    if unread or got != [short(s.strip()) for s in want.split(" | ")]:
        bad.append(f"FAIL steps {text!r}\n  want {want}\n  got  {got}\n  unread {unread}")

# ---- 3. holding: put it at a place = a drive there and a put-down ----
for text in ("put it on p3", "p3에 갖다 놔", "피삼에 놔 줘", "leave it at the registration"):
    got, unread = steps.rules(text, M)
    if unread or [s["do"] for s in got] != ["go", "place"]:
        bad.append(f"FAIL put at {text!r}: {got} {unread}")

# ---- near misses: nothing is read as a task part ----
NEAR = ["did you bring the cup from p1 and go home?", "don't bring the cup from p1, go home", "I'll bring the cup from p1 myself",
        "tomorrow bring me the cup from p1 and go to p2", "my friend brought the cup from p1 and went home",
        "p1에서 컵 가져오지 마", "내가 p1에서 컵 가져올게", "어제 p1에서 컵 가져왔지?", "컵을 p5에 갖다 줬어?",
        "p3에 갖다 놓지 마", "did you deliver the cup to p5?"]
for text in NEAR:
    got, unread = steps.rules(text, M)
    if not unread and got:
        bad.append(f"FAIL near miss {text!r}: {got}")

# ---- 4. a correction after the read-back (fetch_dialog): what changes ----
T = {"object": "cup", "colour": "red", "source": P("p1"), "dest": "here", "finish": "hold"}
FIX = {"no, the blue one": {"colour": "blue"}, "아니 파란 거": {"colour": "blue"}, "not p1, p2": {"source": P("p2")},
       "피원 말고 피투": {"source": P("p2")}, "the one on the left": {"prefer": "left"}, "왼쪽 거": {"prefer": "left"},
       "the smaller one": {"prefer": "small"}, "아니 작은 거": {"prefer": "small"}, "no, from p2": {"source": P("p2")},
       "아니 피사로": {"dest": P("p4")}, "no, the bottle": {"object": "bottle", "colour": None},
       "the other one": {}, "아니 다른 거": {}}       # not said which: nothing changes, Lumi asks what to change
for text, want in FIX.items():
    task, changed = brain.parse_correction(text, T, M)
    if {k: task.get(k) for k in changed} != want:
        bad.append(f"FAIL correction {text!r}: want {want}, got {({k: task.get(k) for k in changed})}")

print("\n".join(bad))
print(f"{len(FETCH) + len(STEPS) + len(FIX) + len(NEAR) + 4 - len(bad)}/{len(FETCH) + len(STEPS) + len(FIX) + len(NEAR) + 4} right")
assert not bad
print("fetch words ok")
