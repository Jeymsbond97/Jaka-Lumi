"""Run a Cobo π program on the arm over the controller's TCP command port 10001 (no SDK).

    python robot/arm.py                    # state
    python robot/arm.py run                # play hand_shaking.jks once and wait
    python robot/arm.py stop
"""
import json
import socket
import sys
import time

CONTROLLER = ("192.168.10.90", 10001)
WAVE = "hand_shaking.jks"
# The controller now and then closes the connection without a reply (seen on get_data, get_program_state,
# kine_inverse, stop_program). Commands that only read are asked again; motion commands are never repeated here.
READ_ONLY = {"get_data", "get_joint_pos", "get_tcp_pos", "get_robot_state", "get_program_state", "get_loaded_program",
             "kine_inverse", "kine_forward"}
RETRIES, RETRY_S = 3, 0.2


def cmd(name, **args):
    tries = RETRIES if name in READ_ONLY else 1
    for i in range(tries):
        try:
            return _send(name, args)
        except (ConnectionError, OSError):
            if i == tries - 1:
                raise
            time.sleep(RETRY_S)


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


def start(program=WAVE):
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
    if what == "run":
        if not ready():
            sys.exit("arm not ready (power/enable off, or a program is running)")
        start()
        time.sleep(0.5)
        while program_state() != "idle":
            time.sleep(0.3)
        print("done")
    elif what == "stop":
        print(stop())
    else:
        print(cmd("get_robot_state"), program_state(), cmd("get_loaded_program").get("programName"))
