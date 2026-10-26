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
        return {"do": "receive", "object": w[1]}
    if w[0] == "wait":
        if w[1:2] == ["order"]:
            return {"do": "wait", "s": steps.WAIT_ORDER_S, "until": "instruction"}
        return {"do": "wait", "s": float(w[1]) if len(w) > 1 else None}
    if w[0] == "turn":
        return {"do": "turn", "deg": float(w[1])}
    if w[0] == "place":
        return {"do": "place", "on": None}
    if w[0] == "give" and len(w) > 1:
        return {"do": "give", "person": w[1]}
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

print("\n".join(bad))
print(f"{len(FETCH) + len(STEPS) + 4 - len(bad)}/{len(FETCH) + len(STEPS) + 4} right")
assert not bad
print("fetch words ok")
