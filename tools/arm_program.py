"""Run a Cobo π program on the Lumi arm over the controller's TCP command port (10001).

No JAKA SDK needed; works from any computer on the robot network. A program starts only with the arm at `look`
(data/arm_poses.json, every joint within AT_LOOK_DEG), as on the robot (manipulation/arm_route.py); hand_shaking
never (it hit the head, 2026-10-21).

    python3 tools/arm_program.py state                  # power/enable, loaded program, program state
    python3 tools/arm_program.py run arm_reach          # load the program and play it once, wait until done
    python3 tools/arm_program.py stop                   # stop the running program

Ctrl+C while a program runs stops it.
"""
import json
import socket
import sys
import time
from pathlib import Path

CONTROLLER = ("192.168.10.90", 10001)
POSES_FILE = Path(__file__).resolve().parents[1] / "data" / "arm_poses.json"
AT_LOOK_DEG = 3.0                    # deg; every joint this close to `look` (J1 / J4 / J6 also ± 360)
NEVER_RUN = ("hand_shaking.jks",)


def cmd(name, **args):
    """Send one command, return the reply as a dict."""
    with socket.create_connection(CONTROLLER, timeout=5) as s:
        s.sendall(json.dumps({"cmdName": name, **args}).encode())
        buf = ""
        while True:
            buf += s.recv(65536).decode()
            try:
                return json.loads(buf)
            except json.JSONDecodeError:
                continue


def state():
    r = cmd("get_robot_state")
    return {"power": r.get("power"), "enable": r.get("enable"), "errcode": r.get("errcode"),
            "loaded": cmd("get_loaded_program").get("programName"),
            "program": cmd("get_program_state").get("programState")}


def run(program):
    st = state()
    if not (st["power"] and st["enable"]):
        sys.exit(f"Arm is not powered and enabled: {st}. Turn on Power and Enable in Cobo π first.")
    if st["program"] != "idle":
        sys.exit(f"A program is {st['program']}; stop it first (python3 tools/arm_program.py stop).")

    name = program if program.endswith(".jks") else program + ".jks"
    if name.lower() in NEVER_RUN:
        sys.exit(f"{name} is not used any more (it hit the head); the wave is manipulation/wave.py.")
    look = json.loads(POSES_FILE.read_text())["look"]
    now = cmd("get_joint_pos")["joint_pos"]
    off = max(min(abs(n - l - k) for k in ((-360, 0, 360) if i in (0, 3, 5) else (0,)))
              for i, (n, l) in enumerate(zip(now, look)))
    if off > AT_LOOK_DEG:
        sys.exit(f"The arm is {off:.0f} deg from look: programs start only from look.")
    if (st["loaded"] or "").lower() != name.lower():
        r = cmd("load_program", programName=name)
        print("load_program:", r.get("errorCode"), r.get("errorMsg"))
        if r.get("errorCode") != "0":
            sys.exit("Load failed. Check the program name in Cobo π → Program → File.")

    r = cmd("play_program")
    print("play_program:", r.get("errorCode"), r.get("errorMsg"))
    if r.get("errorCode") != "0":
        sys.exit("Play failed.")
    try:
        time.sleep(0.5)
        while (s := cmd("get_program_state").get("programState")) != "idle":
            print(f"\r  {s} ", end="", flush=True)
            time.sleep(0.3)
        print("\r  done ")
    except KeyboardInterrupt:
        print("\nStopping:", cmd("stop_program").get("errorCode"))


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("state", "run", "stop") or sys.argv[1] == "run" and len(sys.argv) < 3:
        sys.exit(__doc__)
    if sys.argv[1] == "state":
        print(state())
    elif sys.argv[1] == "stop":
        print("stop_program:", cmd("stop_program"))
    else:
        run(sys.argv[2])


if __name__ == "__main__":
    main()
