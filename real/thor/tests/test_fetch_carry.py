"""Self-check of the mission step {"do": "carry"} (tests/pick_sweep.py simulator, no robot): a pick stopped right after
the grasp leaves the cup just above the table; the step lifts it straight up and brings it to look, saying nothing:
python tests/test_fetch_carry.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests import pick_sweep as ps

ps.install()
fetch, skills, motion = ps.fetch, ps.skills, ps.motion


class Halt(Exception):
    pass


def halt_up(what, pose):                  # the pick is stopped before its straight move up: holding, 3 cm up
    if what == "up":
        raise Halt()
    REAL_LINE(what, pose)


REAL_LINE = skills._line


for name, sc in (("straight", ps.pick_at(-96, 598, -260)), ("turned", ps.pick_at(260, 722, -186))):
    ps.setup(sc, 0.0)
    skills._line = halt_up
    try:
        fetch._pick_here({"object": "cup", "colour": None}, None)
        raise AssertionError("the pick was not stopped")
    except Halt:
        pass
    skills._line = REAL_LINE
    assert ps.W["hand"]["holding"] and fetch._state["holding"], name
    z0 = ps.kin.pose(ps.W["J"])[2]
    assert not fetch._at_pose("look"), name
    said, ups = [], []
    skills._line = lambda what, pose: (ups.append(pose[2]), REAL_LINE(what, pose))
    fetch._do_step({"do": "carry"}, lambda en, ko=None: said.append(en))
    skills._line = REAL_LINE
    assert fetch._at_pose("look") and ps.W["hand"]["holding"], name
    assert ups and ups[0] >= z0 + skills.ABOVE_MM - skills.LIFT_MM - 1.0, (name, z0, ups)   # straight up first
    assert not said, said
    fetch._do_step({"do": "carry"}, lambda en, ko=None: said.append(en))   # at look already: nothing moves
    assert fetch._at_pose("look") and not said
    print(name, "lifted", round(ups[0] - z0), "mm, then to look")

fetch._state.update(holding=False)
try:
    fetch._carry_held()
    raise AssertionError("carried with an empty hand")
except fetch.FetchError:
    pass
print("fetch carry ok")
