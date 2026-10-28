"""The arm controller's TCP command port 10001 (JSON, no SDK): commands, Cobo π programs.
Programs are started through manipulation/arm_route.py (only from `look`).

    python robot/arm.py                    # state
    python robot/arm.py stop
"""
import json
import socket
import sys
import time

CONTROLLER = ("192.168.10.90", 10001)
# The controller now and then closes the connection without a reply (seen on get_data, get_program_state,
# kine_inverse, stop_program, moveL, set_digital_output). Commands that only read are asked again, and so are those
# that set an absolute value: moves to an absolute target (relFlag 0) and setting an output; sent twice they do the
# same. Relative moves are never repeated here.
READ_ONLY = {"get_data", "get_joint_pos", "get_tcp_pos", "get_robot_state", "get_program_state", "get_loaded_program",
             "kine_inverse", "kine_forward"}
ABSOLUTE_MOVES = {"moveL", "joint_move"}
SET_VALUE = {"set_digital_output", "stop_program"}
RETRIES, RETRY_S = 5, 0.2    # tries; s before the 2nd, doubled each time (0.2 ... 1.6, 3 s in all): the controller
                             # closes every connection for ~0.5 s every few seconds, whatever the request rate


def cmd(name, **args):
    again = name in READ_ONLY or name in SET_VALUE or (name in ABSOLUTE_MOVES and args.get("relFlag") == 0)
    tries = RETRIES if again else 1
    for i in range(tries):
        try:
            r = _send(name, args)
            if name in READ_ONLY and r.get("cmdName", name) != name and i < tries - 1:
                time.sleep(RETRY_S)      # another command's reply (get_data to get_joint_pos, seen): ask again
                continue
            return r
        except (ConnectionError, OSError):
            if i == tries - 1:
                raise
            time.sleep(RETRY_S * 2 ** i)


def _send(name, args):
    with socket.create_connection(CONTROLLER, timeout=10) as s:
        s.sendall(json.dumps({"cmdName": name, **args}).encode())
        buf = ""
        while True:
            chunk = s.recv(65536)
            if not chunk:                            # the controller closed the connection: never loop forever
                raise ConnectionError(f"arm controller closed the connection ({name})")
            buf += chunk.decode()
            try:
                return json.loads(buf)
            except json.JSONDecodeError:
                continue


def ready():
    """True when the arm is powered, enabled and no program is running."""
    r = cmd("get_robot_state")
    return bool(r.get("power")) and bool(r.get("enable")) and cmd("get_program_state").get("programState") == "idle"


def program_state():
    return cmd("get_program_state").get("programState")


def start(program):
    """Load (if needed) and start a program; returns at once."""
    if (cmd("get_loaded_program").get("programName") or "").lower() != program.lower():
        if cmd("load_program", programName=program).get("errorCode") != "0":
            raise RuntimeError(f"cannot load {program}")
    if cmd("play_program").get("errorCode") != "0":
        raise RuntimeError("play_program failed")


def stop():
    return cmd("stop_program")


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "state"
    if what == "stop":
        print(stop())
    else:
        print(cmd("get_robot_state"), program_state(), cmd("get_loaded_program").get("programName"))
