"""The Zimmer electric gripper on the arm's tool connector (TIO), driven by two digital outputs.

Wiring found 2026-10-13 (Cobo π → I/O → Tool(S), outputs set to PNP):
    DO_1 on  -> the gripper closes, DO_2 on -> it opens (a stroke takes ~1 s)
    AI_1     -> finger position: ~160 open, ~4100-4200 closed on nothing, ~3500 closed on a cup (cup test
                11:39:12); in between while moving. A close runs to the end once started: DO_1 off half way
                (AI_1 2730) still ended at 4190 (2026-10-19), so the fingers can't be stopped on a soft cup.
                A soft plastic cup squeezed flat reads like "empty" (3 of 4 cup closes reached ~4150).
    DI_1     -> optical sensor under the gripper: 1 while something is below it, not between the fingers (PNP);
                a held object shows only in AI_1 (gap_mm)
Only one output may be on at a time: both on = close and open at once.

    python robot/gripper.py            # state
    python robot/gripper.py open
    python robot/gripper.py close
"""
import sys
import time

from robot import arm

TOOL = 1                     # set_digital_output type: 0 cabinet, 1 tool (TIO), 2 extended
CLOSE_DO, OPEN_DO = 0, 1     # DO_1, DO_2 (0-based)
CLOSED_AI = 400              # AI_1 above this = closed on something (open reads 130-165; an 82 mm metal cup
                             # held in the cup fingers reads ~2200-2300, 2026-10-13)
EMPTY_AI = 4000              # closed above this = nothing between the fingers (these fingers empty: 4084-4158; an 84 mm
                             # rim cup held ~4 cm down read 3902, 2026-10-29)
AI_OPEN, AI_SHUT = 140.0, 4160.0   # AI_1 fully open / closed on nothing (2026-10-19)
# inner gap (mm) between the fingers, (open, closed), measured by the owner (docs/gripper/README.md; the neck and the
# straight part "shank" not measured again, the earlier ones kept); the gap is taken as linear in AI_1
GAP_MM = {"tips": (100.0, 73.0), "belly": (102.0, 77.0), "neck": (57.0, 30.0), "shank": (66.0, 39.0)}
MOVE_S = 1.5                 # s a full stroke takes (measured ~1 s)
SENSOR_DI = 0                # DI_1
READ_TRIES, READ_GAP_S = 5, 0.1   # get_data now and then answers without the tool I/O: ask again


def state():
    for _ in range(READ_TRIES):
        d = arm.cmd("get_data")
        if all(k in d for k in ("tio_ain", "tio_din", "tio_dout")):
            break
        time.sleep(READ_GAP_S)
    else:
        raise ConnectionError("the arm controller sends no tool I/O")
    ai = d["tio_ain"][0]
    return {"closed": ai > CLOSED_AI, "holding": CLOSED_AI < ai < EMPTY_AI, "object_in_front": bool(d["tio_din"][SENSOR_DI]),
            "ai": d["tio_ain"], "do": d["tio_dout"], "di": d["tio_din"], "gap_mm": round(gap_mm(ai))}


def gap_mm(ai, where="belly"):
    """Inner gap (mm) between the fingers at `where` (GAP_MM) for an AI_1 reading: the held object's width there."""
    opened, closed = GAP_MM[where]
    f = min(1.0, max(0.0, (ai - AI_OPEN) / (AI_SHUT - AI_OPEN)))
    return opened + f * (closed - opened)


def _out(index, value):
    r = arm.cmd("set_digital_output", type=TOOL, index=index, value=int(value))
    if r.get("errorCode") != "0":
        raise RuntimeError(f"set_digital_output failed: {r}")


def close(wait=True):
    _out(OPEN_DO, 0)                         # never both on
    _out(CLOSE_DO, 1)
    if wait:
        time.sleep(MOVE_S)
    return state()


def open_(wait=True):
    _out(CLOSE_DO, 0)
    _out(OPEN_DO, 1)
    if wait:
        time.sleep(MOVE_S)
    return state()


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "state"
    print({"open": open_, "close": close}.get(what, state)())
