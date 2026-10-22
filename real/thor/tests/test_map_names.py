"""Self-check of marker names as people say them on any map (assistant/wording.py map_names, brain, steps, the
assistant's live list), with fake marker lists for the office and a conference map, no robot, no LLM:
python tests/test_map_names.py"""
import types

from assistant import brain, lumi, steps, wording
from robot import agv

lumi.LOG_FILE = "/dev/null"
OFFICE = ["home", "dock2", "exit", "final"] + [f"p{i}" for i in range(1, 13)]
CONF = ["home", "start", "end", "init", "final", "middle", "table_front", "stage", "booth_2"]

# ---------- said -> written, with the conference map's names ----------
NORM = {
    "go to table front": "go to table_front", "go to the Table-Front": "go to the table_front",
    "go to tablefront": "go to table_front", "테이블 프론트로 가": "table_front로 가", "테이블 프런트로": "table_front로",
    "go to booth two": "go to booth_2", "go to Booth 2": "go to booth_2", "go to booth-2": "go to booth_2",
    "부스 투로 가": "booth_2로 가", "스타트로 가": "start로 가", "엔드에서 컵 가져와": "end에서 컵 가져와",
    "미들로 가": "middle로 가", "스테이지로 가": "stage로 가", "이닛으로 가": "init으로 가", "홈으로 가": "home으로 가",
    "go to the stagee": "go to the stage", "go to the middel": "go to the middle",       # whisper slips, one name
    "go to the table fronts": "go to the table_front", "from the stagee to end": "from the stage to end",
    # not a marker: unchanged
    "테이블에 놔": "테이블에 놔", "restart the song": "restart the song", "스타트업": "스타트업", "go to point": "go to point",
    "go to booth 3": "go to booth 3", "go to the left": "go to the left",
}
bad = {t: (wording.norm(t, CONF), w) for t, w in NORM.items() if wording.norm(t, CONF) != w}
assert not bad, bad

# ---------- go to / come back to: the quick rules ----------
GO = {"go to table front": "table_front", "테이블 프론트로 가": "table_front", "go to booth two": "booth_2",
      "부스 투로 가 줘": "booth_2", "루미야 스타트로 가": "start", "go to the end": "end", "엔드로 가": "end",
      "go back to start": "start", "come back to the stage": "stage", "drive to Middle": "middle", "이닛으로 가": "init",
      "파이널로 가": "final", "go to the stagee": "stage", "go home": "home"}
wrong = {t: brain.intent(t, CONF) for t, w in GO.items() if brain.intent(t, CONF) != ("go_to", w)}
assert not wrong, wrong
for t, w in {"go to p3": "p3", "피쓰리로 가": "p3", "go to final": "final", "도크 투로 가": "dock2", "go to 10p point": "p10",
             "엑시트로 가": "exit"}.items():                 # the office map's names keep working
    assert brain.intent(t, OFFICE) == ("go_to", w), (t, brain.intent(t, OFFICE))
for t in ("go to p3", "go to the kitchen", "go to start"):   # not on that map: never driven
    assert brain.intent(t, OFFICE if t == "go to start" else CONF) is None, t

# ---------- unknown, ambiguous: what Lumi says ----------
en, ko = brain.place_problem("go to p12", CONF)
assert en.startswith("I don't have a place called p12 on this map. I know: ") and "table front" in en, en
assert "p12라는 곳이 없어요" in ko, ko
TWO = CONF + ["booth_1"]
en, ko = brain.place_problem("go to booth", TWO)
assert en.startswith("Did you mean booth ") and "booth 1" in en and "booth 2" in en, en
assert brain.intent("go to booth", TWO) is None and brain.intent("go to booth two", TWO) == ("go_to", "booth_2")
for t in ("go to stage", "go to sleep", "go to the left", "go to the kitchen"):   # the LLM answers the others
    assert brain.place_problem(t, CONF) is None, t
said = brain.Brain._action("ACTION: go_to kitchen", "go to the kitchen", CONF)
assert said["action"] == "none" and said["say"].startswith("I don't have a place called kitchen"), said
assert brain.Brain._action("ACTION: go_to table_front", "go to the table front", CONF)["target"] == "table_front"

# ---------- missions, fetch to / from, place at a marker ----------
STEPS = {
    "go to start, then come back": [{"do": "go", "to": "start"}, {"do": "go", "to": "here"}],
    "스타트로 갔다가 돌아와": [{"do": "go", "to": "start"}, {"do": "go", "to": "here"}],
    "go to middle and wait 10 seconds then go to end":
        [{"do": "go", "to": "middle"}, {"do": "wait", "s": 10.0}, {"do": "go", "to": "end"}],
    "미들로 가서 10초 기다렸다가 엔드로 가": [{"do": "go", "to": "middle"}, {"do": "wait", "s": 10.0}, {"do": "go", "to": "end"}],
    "go to Table-Front then 홈으로 가": [{"do": "go", "to": "table_front"}, {"do": "go", "to": "home"}],
    "go to the stagee and come back": [{"do": "go", "to": "stage"}, {"do": "go", "to": "here"}],
    "go stage": [{"do": "go", "to": "stage"}],
    "take the white cup to booth two and put it on the table": [
        {"do": "pick", "object": "cup", "colour": "white"}, {"do": "go", "to": "booth_2"},
        {"do": "place", "on": {"name": "dining table", "colour": None, "side": None}}],
    "부스 투 테이블에 놔": [{"do": "go", "to": "booth_2"},
                     {"do": "place", "on": {"name": "dining table", "colour": None, "side": None}}],
    "컵 들고 테이블 프론트로 가서 놔": [{"do": "pick", "object": "cup", "colour": None}, {"do": "go", "to": "table_front"},
                           {"do": "place", "on": None}],
}
for t, want in STEPS.items():
    got, unread, _ = steps.read(t, CONF, llm=False)
    assert got == want and not unread, (t, got, unread)
assert steps.read("go to booth and come back", TWO, llm=False)[1] == ["go to booth"]   # ambiguous: not guessed
assert lumi.read_mission("go to start, then come back", CONF)[0][0] == {"do": "go", "to": "start"}
FETCH = {"bring the cup from start to table front": ({"marker": "start"}, {"marker": "table_front"}),
         "스타트에서 컵 가져와서 부스 투에 놔": ({"marker": "start"}, {"marker": "booth_2"}),
         "bring me the cup from the stagee": ({"marker": "stage"}, "here")}
for t, (src, dest) in FETCH.items():
    task, _ = brain.parse_fetch(t, CONF)
    assert (task["source"], task["dest"]) == (src, dest), (t, task)
assert brain.parse_fetch("bring the cup from the kitchen", CONF)[0]["source"] is None

# ---------- the assistant's list follows the map ----------
maps = {"now": OFFICE}
agv.markers = lambda: list(maps["now"])
assert agv.known_markers(fresh=True) == OFFICE
maps["now"] = CONF                                           # the owner switched the map
assert agv.known_markers() == OFFICE                         # read again only after MARKERS_FRESH_S ...
agv._known["t"] -= agv.MARKERS_FRESH_S + 1
assert agv.known_markers() == CONF                           # ... or on a miss (fresh=True)


def offline():
    raise ConnectionError("AGV closed the connection")


agv.markers = offline
assert agv.known_markers(fresh=True) == CONF                 # the base not answering: the last list
agv.markers = lambda: list(maps["now"])

L = lumi.Lumi.__new__(lumi.Lumi)
assert L.markers == CONF
spoken, trips = [], []
lumi.mouth.say = lambda text, **k: spoken.append(text)
L.lang, L.keep_listening, L.mission_running = "en", lambda: None, lambda: False
L.base_off, L.arm_off, L.start_trip = lambda *a: False, lambda: False, trips.append
L.modes, L.brain, L.current, L.voice_until = types.SimpleNamespace(drive=True), types.SimpleNamespace(history=[]), None, 0
assert L.quick_command("go to p12") and spoken[-1].startswith("I don't have a place called p12") and not trips
maps["now"] = OFFICE                                          # a miss reads the list again: p12 is on this map
assert L.quick_command("go to p12") and trips == ["p12"]
maps["now"] = CONF
agv.known_markers(fresh=True)
assert L.quick_command("go to table front") and trips[-1] == "table_front" and spoken[-1] == "Okay, I'm going to table front."
print("map names ok")
