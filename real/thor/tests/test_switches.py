"""Self-check of the dashboard switches and the arm's state: with Greeter only Lumi works in place (head, lift, arm,
gripper, wave) and refuses the base and the waist with one line; Patrol on allows them; "stop" works either way; an
arm action with the arm switched off asks to enable it, nothing else asks. Fake state, no robot:
python tests/test_switches.py"""
import types

import no_robot                                     # noqa: F401  any connection to the robot fails the test
from assistant import lumi
from tasks import fetch, follow

M = ["home", "p3", "p8"]
moved, said = [], []


def forbid(*a, **k):
    raise AssertionError("a test reached the robot")


for mod in (lumi.agv, lumi.head, lumi.arm, lumi.gripper, lumi.motion, lumi.skills):   # nothing may reach the robot
    for name in dir(mod):
        if not name.startswith("_") and callable(getattr(mod, name)) and not isinstance(getattr(mod, name), type):
            setattr(mod, name, forbid)
lumi.wave_mod.wave = forbid
lumi.log = fetch.log = lambda *a: None
lumi.mouth = types.SimpleNamespace(say=lambda text, **k: said.append(text))
arm_state = {"power": 1, "enable": 1}
lumi.arm.cmd = lambda name, **a: dict(arm_state) if name == "get_robot_state" else forbid()

L = lumi.Lumi.__new__(lumi.Lumi)
L.lang, L.markers, L.current, L.patrol, L.vision, L.voice_angle = "en", M, None, None, None, 0.0
L.turn_head = lambda *a, **k: moved.append("head")
L.brain = types.SimpleNamespace(history=[])
L.keep_listening = lambda: None
L.mission_running = lambda: False
L.fetch_status = lambda: None
L.skill_busy = lambda: False
FAKED = ("start_trip", "move_by", "come_to", "follow_me", "fetch_request", "object_task", "arm_pose", "lift", "look",
         "come_back", "receive_from_hand")
for name in FAKED:
    setattr(L, name, lambda *a, _n=name, **k: moved.append(_n) or _n not in ("look", "lift"))   # look / lift: a LIMIT_SAY key
L.wave = lambda *a, **k: None                          # quick_command starts it in a thread

BASE = {"go to p3": "go_to", "p3로 가": "go_to", "follow me": "follow", "따라와": "follow", "come here": "come",
        "이리 와": "come", "move forward 1 meter": "move", "1미터 앞으로 가": "move", "turn left": "turn",
        "come back": "come_back"}
IN_PLACE = {"look left": "look", "고개 들어": "look", "look behind you": "look", "lift up": "lift", "키 좀 낮춰": "lift",
            "pick up the cup": "pick", "open your hand": "arm", "reach out your hand": "arm", "wave": "wave",
            "bring me the cup": "fetch"}
for text, action in {**BASE, **IN_PLACE}.items():
    got = lumi.brain_mod.intent(text, M)
    assert got and got[0] == action, (text, got)
DOES = {"go_to": "start_trip", "follow": "follow_me", "come": "come_to", "move": "move_by", "turn": "move_by",
        "arm": "arm_pose", "pick": "object_task", "fetch": "fetch_request", "come_back": "come_back",
        "look": "look", "lift": "lift"}

# ---------- Greeter only: the base refused aloud (no "Okay" first), everything in place done ----------
L.modes = types.SimpleNamespace(greeter=True, patrol=False, drive=True, wave=True)
for text in BASE:
    moved.clear()
    said.clear()
    assert L.quick_command(text) and moved == [] and said == [lumi.BASE_OFF_SAY[0]], (text, moved, said)
L.lang = "ko"
said.clear()
assert L.quick_command("p3로 가") and said == [lumi.BASE_OFF_SAY[1]]
L.lang = "en"
for text, action in IN_PLACE.items():
    moved.clear()
    said.clear()
    L.quick_command(text)
    assert lumi.BASE_OFF_SAY[0] not in said, (text, said)
    assert action == "wave" or moved == [DOES[action]], (text, moved)
for action, target in (("go_to", "p3"), ("follow", ""), ("move", "forward 1"), ("turn", "left 90"), ("come", "")):
    moved.clear()
    L.act(action, target)                              # the LLM's action: answer() has said the line
    assert moved == [] and L.base_off(action, target, say=False), action
for action, target in (("look", "left"), ("lift", "up"), ("arm", "reach")):
    moved.clear()
    L.act(action, target)
    assert moved == [DOES[action]], (action, moved)
said.clear()
assert L.mission_request("go to p3, wait 10 seconds and come back") and said == [lumi.BASE_OFF_SAY[0]]
said.clear()
L.heard = "그럼 가 보세요"
L.go_offered("p3")
assert said == [lumi.BASE_OFF_SAY[0]]

# a fetch from or to a place drives: refused; one here runs in place (fetch.stay_put)
started = []
real_start = fetch.start
fetch.start = lambda task, say=None: started.append((task, fetch.stay_put))
lumi.agv.pose = lambda: (1.0, 2.0, 0.0)
said.clear()
L.fetch_start({"object": "cup", "source": {"marker": "p3"}, "dest": "here", "finish": "hold"})
assert started == [] and said == [lumi.BASE_OFF_SAY[0]]
L.fetch_start({"object": "cup", "source": "here", "dest": "here", "finish": "hold"})
assert started and started[-1][1] is True                # in place: head and lift only

# fetch.stay_put: no base, no waist; the search is the head and the lift
fetch.stay_put = True
fetch.head.status = lambda: [50.0, 30.0, 0.0, 0.0]       # the waist turned 30 deg (jogged before)
fetch._waist_turn = lambda: 30.0
fetch.head.moveto = forbid
fetch.agv.turn_by = fetch.agv.go_point = fetch.agv.go = fetch.agv.request = forbid
assert fetch._waist_to(0.0) is False and fetch._turn(90.0) is False
for fn, args in ((fetch._waist_front, ()), (fetch._straight, (0.5,)), (fetch._approach, ({"x": 0, "y": 900}, 0.0, set())),
                 (fetch._drive_to, ({"marker": "p3"}, None))):
    try:
        fn(*args)
        raise AssertionError(f"{fn.__name__} moved with Patrol off")
    except fetch.FetchError as e:
        assert e.args == fetch.NEED_PATROL, (fn.__name__, e.args)
fetch.stay_put = False
fetch.start = real_start

# ---------- the arm switched off: arm actions ask to enable it, the rest runs ----------
arm_state.update(enable=0)
for text in ("pick up the cup", "reach out your hand", "wave", "bring me the cup"):
    moved.clear()
    said.clear()
    assert L.quick_command(text) and moved == [] and said == [lumi.ARM_OFF_SAY[0]], (text, moved, said)
for text in ("look left", "lift up", "open your hand"):        # the gripper alone does not ask
    moved.clear()
    said.clear()
    L.quick_command(text)
    assert lumi.ARM_OFF_SAY[0] not in said and moved, (text, said)
said.clear()
L.lang = "ko"
lumi.Lumi.receive_from_hand(L, "cup")
assert said == [lumi.ARM_OFF_SAY[1]]
L.lang = "en"
assert lumi.wave_mod.OFF == fetch.arm_route.OFF == lumi.ARM_OFF_SAY

# follow: an enabled arm never refuses; a disabled one follows where it is; powered off (joints 0) asks
follow.fetch._charging = lambda: False
at_look = [True]
follow.fetch._at_pose = lambda name: at_look[0]
follow.fetch._look = lambda: "look"
follow.motion._ready = lambda: None if arm_state["enable"] else (_ for _ in ()).throw(follow.motion.MotionError("off"))
arm_state.update(enable=1)
assert follow.ready() is None
at_look[0] = False
assert follow.ready() is None                            # enabled: it may go to look
arm_state.update(enable=0)
real_joints, follow.fetch.skills._joints = follow.fetch.skills._joints, lambda: [5.0] * 6
assert follow.ready() is None                            # off and not at look: follows, the arm stays
follow.fetch.skills._joints = lambda: [0.0] * 6
assert follow.ready() == follow.fetch.ARM_UNSEEN         # powered off: where the arm is is not known
follow.fetch.skills._joints = real_joints
at_look[0] = True
assert follow.ready() is None                            # off but already at look: follows

# ---------- stop works either way ----------
stopped = []
real_follow_stop, real_fetch_stop = follow.stop, fetch.stop
follow.stop = lambda: stopped.append("follow")
fetch.stop = lambda: stopped.append("fetch")
lumi.agv.cancel = lambda: stopped.append("base")
lumi.skills.cancel = lambda: stopped.append("skill")
lumi.motion.stop = lambda: stopped.append("arm")
said.clear()
L.stop_all()
assert stopped == ["fetch", "follow", "base", "skill", "arm"] and said == ["Okay, I stopped."], (stopped, said)
assert lumi.stop_order("stop", M) and lumi.stop_order("멈춰", M)

# ---------- Patrol on: the base moves too ----------
arm_state.update(enable=1)
L.modes.patrol = True
for text, action in {**BASE, **IN_PLACE}.items():
    moved.clear()
    said.clear()
    L.quick_command(text)
    assert lumi.BASE_OFF_SAY[0] not in said, (text, said)
    assert action == "wave" or moved == [DOES[action]], (text, moved)
moved.clear()
L.act("go_to", "p3")
assert moved == ["start_trip"]
follow.stop, fetch.stop = real_follow_stop, real_fetch_stop

# ---------- "reach out to me": toward the person; the waist turns to them with Greeter only too (the base stays) ----
assert lumi.reach_turn(None) is None and lumi.reach_turn(8.0) == 0.0
assert lumi.reach_turn(-35.0) == -35.0 and lumi.reach_turn(35.0) == 35.0
# the hand held out 21 deg right of the waist's front (give): the waist turns until the hand, not its front, points
# at the person (live 2026-10-28: turned straight at them, the hand went out beside them)
assert lumi.reach_turn(36.0, -21.0) == 57.0 and lumi.reach_turn(-15.0, -21.0) == 0.0 and lumi.reach_turn(0.0, -21.0) == 21.0
reached, looked = [], []
real_reach, real_bearing = fetch.reach, fetch.give_bearing
fetch.reach = lambda angle=0.0, say=None, look=None: reached.append(angle) or looked.append(look)
fetch.give_bearing = lambda: 0.0
L.fetch_finish = lambda how, **k: moved.append(how)
L.skill_thread, L.voice_trusted = None, False
person = types.SimpleNamespace(angle=35.0, distance=1.0, id=8)
L.vision = types.SimpleNamespace(present=lambda t: False, near_angle=lambda a, d=25: None, only_person=lambda: person)
L.turn_head = lambda yaw=None, pitch=None, force=False: moved.append(("head", yaw))
for patrol, angle, want in ((False, 35.0, [35.0]), (True, 35.0, [35.0]), (False, -40.0, [-40.0]), (False, -8.0, [0.0]),
                           (True, -8.0, [0.0])):
    L.modes.patrol, person.angle = patrol, angle
    reached.clear(), said.clear(), moved.clear()
    got = L.reach_out(False)
    # a waist turn takes the head onto them (fetch._waist_to look); a head turn here raced it (looked away live)
    head_cmds = [] if want[0] else [("head", lumi.HEAD_SIGN * angle)]
    assert got and reached == want and moved == head_cmds and not said, (patrol, angle, reached, moved, said)
fetch.give_bearing = lambda: -21.0                       # the hand right of the front: turned further, the head on them
person.angle = 36.0
reached.clear(), looked.clear()
assert L.reach_out(False) and reached == [57.0] and looked == [36.0], (reached, looked)
person.angle, person.distance = 0.0, 3.0                 # far away: come to them first, then reach
came = []
L.vision.present = lambda t: True
L.come_to = lambda t: came.append(t.id) or setattr(t, "distance", 1.1)
reached.clear(), said.clear()
assert L.reach_out(False) and came == [8] and reached == [21.0], (came, reached)
person.distance, L.modes.drive = 3.0, False              # far and driving switched off: asked to come, no reach
reached.clear(), said.clear(), came.clear()
assert L.reach_out(False) is None and not reached and not came and said == [lumi.COME_CLOSER_SAY[0]], (said, reached)
L.modes.drive, person.distance = True, 1.0
fetch.give_bearing = lambda: 0.0
L.turn_head = lambda *a, **k: moved.append("head")
L.vision = None                                          # nobody seen, the voice's direction not trusted: ask
reached.clear(), said.clear()
assert L.reach_out(False) is None and not reached and said == [lumi.STAND_IN_FRONT_SAY[0]]
L.voice_trusted, L.voice_angle, L.modes.patrol = True, -50.0, True   # heard from the right: turn to the voice
assert L.reach_out(False) and reached == [-50.0]
moved.clear(), reached.clear(), said.clear()
L.fetch_status = lambda: "holding"
real_check, fetch.check_hand = fetch.check_hand, lambda: True     # the hand checked: something is in it
assert lumi.Lumi.arm_pose(L, "reach") is None and moved == ["give"] and not reached   # holding: hand it over
assert lumi.Lumi.arm_pose(L, "open") is None and said == [lumi.brain_mod.REFUSE_OPEN[0]]   # never dropped
fetch.check_hand = lambda: False                         # a stale "holding", the hand empty: it opens
real_open, lumi.gripper.open_ = lumi.gripper.open_, lambda: moved.append("open") or {}
said.clear(), moved.clear()
assert lumi.Lumi.arm_pose(L, "open") and moved == ["open"] and not said, (moved, said)
lumi.gripper.open_, fetch.check_hand = real_open, real_check
L.fetch_status = lambda: None
fetch.reach, fetch.give_bearing = real_reach, real_bearing

# ---------- the waist back to the front (waist_home): in place, Greeter only too; never with the arm out or a task ----
real = {n: getattr(fetch, n) for n in ("_waist_turn", "state", "_at_pose", "_waist_to")}
calls = []
fetch._waist_to = lambda rel, in_place=False: calls.append((rel, in_place)) or True
fetch.state = lambda: {"status": "idle"}
fetch._at_pose = lambda name: True
fetch._waist_turn = lambda: 0.4                          # at the front already: nothing moves
assert lumi.waist_home("test") and calls == []
fetch._waist_turn = lambda: 35.0                         # turned for a person
fetch.state = lambda: {"status": "running"}              # a task turns the waist itself
assert lumi.waist_home("test") is False and calls == []
fetch.state = lambda: {"status": "done"}
fetch._at_pose = lambda name: False                      # the hand held out (a reach): it stays turned
assert lumi.waist_home("test") is False and calls == []
fetch._at_pose = lambda name: True
assert lumi.waist_home("test") and calls == [(0.0, True)]   # in place: also with Patrol off (stay_put)
fetch._waist_to = lambda rel, in_place=False: False      # the arm's sweep is not clear
assert lumi.waist_home("test") is False
for n, f in real.items():
    setattr(fetch, n, f)

# ---------- every drive and base turn starts with the waist at the front ----------
order = []
real_home = lumi.waist_home
lumi.waist_home = lambda why: order.append("waist") or True
lumi.agv.status = lambda: {"move_status": "idle", "power_percent": 90}
lumi.agv.go = lambda m: order.append(("go", m)) or (True, "OK")
lumi.agv.go_point = lambda x, y, th: order.append(("go", (x, y, th))) or (True, "OK")
lumi.agv.turn_by = lambda a: order.append(("turn", round(lumi.math.degrees(a)))) or (True, "OK")
P = lumi.Patrol(["p3"], once=True)
P.tick(force=True)
assert order == ["waist", ("go", "p3")] and P.moving, order
lumi.agv.status = lambda: {"move_status": "idle", "power_percent": 2}    # low battery: home, the waist first
order.clear()
P = lumi.Patrol(["p3"])
P.tick(force=True)
assert order == ["waist", ("go", "home")] and P.mode == "going_home", order
lumi.agv.status = lambda: {"move_status": "idle", "power_percent": 90}
L.modes.patrol, L.modes.drive = True, True
real_turned, lumi.waist_turned = lumi.waist_turned, lambda: 30.0   # turned 30 left for someone
order.clear()
L.look_toward(150.0)                                     # a voice behind: the base turns to it from the base's front
assert order == ["waist", ("turn", 180)], order
lumi.waist_home = lambda why: order.append("waist") or False   # it can't come back: no drive, no turn, said why
order.clear()
P = lumi.Patrol(["p3"], once=True)
P.tick(force=True)
assert order == ["waist"] and P.stuck == "p3" and P.stuck_why == lumi.WAIST_BACK_SAY and P.mode == "done"
order.clear()
L.look_toward(150.0)
assert order == ["waist"], order
lumi.waist_home, lumi.waist_turned = real_home, real_turned
for name in ("status", "go", "go_point", "turn_by"):
    setattr(lumi.agv, name, forbid)
print(f"switches ok: {len(BASE)} base phrases refused with Greeter only, {len(IN_PLACE)} in place done; "
      "arm off asks; Patrol allows all; stop always")
