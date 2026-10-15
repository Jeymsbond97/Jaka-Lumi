"""The Zimmer electric gripper on the arm's tool connector (TIO), driven by two digital outputs.

Wiring found 2026-10-13 (Cobo π → I/O → Tool(S), outputs set to PNP):
    DO_1 on  -> the gripper closes, DO_2 on -> it opens (a stroke takes ~1 s)
    AI_1     -> finger position: ~160 open, ~4100-4200 closed on nothing, ~3500 closed on a cup (cup test
                11:39:12); in between while moving. The fingers stay where they are when both outputs go off.
                A soft plastic cup squeezed flat reads like "empty" (3 of 4 cup closes reached ~4150).
    DI_1     -> optical sensor on a finger: 1 while something is in front of it (inputs set to PNP)
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
EMPTY_AI = 3900              # closed above this = nothing between the fingers (empty reads 4100-4200, noise +-50)
MOVE_S = 1.5                 # s a full stroke takes (measured ~1 s)
SENSOR_DI = 0                # DI_1


def state():
    d = arm.cmd("get_data")
    ai = d["tio_ain"][0]
    return {"closed": ai > CLOSED_AI, "holding": CLOSED_AI < ai < EMPTY_AI, "object_in_front": bool(d["tio_din"][SENSOR_DI]),
            "ai": d["tio_ain"], "do": d["tio_dout"], "di": d["tio_din"]}


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
