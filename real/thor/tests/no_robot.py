"""Import first in a test: any connection to the robot (arm / body controller, AGV base) is refused and the test fails
at exit with where it came from, even when the code under test catches the error. `import tests.no_robot` or
`from tests import no_robot`."""
import atexit
import os
import socket
import sys
import traceback

ROBOT_HOSTS = {"192.168.10.90", "192.168.10.10"}     # arm / body controller, AGV base (CLAUDE.md "Addresses")
hits = []                                            # (host, port, the caller's frame)


def _guard(real):
    def connect(sock, address, *a):
        if isinstance(address, tuple) and address[0] in ROBOT_HOSTS:
            frames = [f for f in traceback.extract_stack()[:-1] if "/tests/no_robot.py" not in f.filename]
            ours = [f"{f.filename.rsplit('/', 1)[-1]}:{f.name}:{f.lineno}" for f in frames
                    if "lumi-wave" in f.filename and "site-packages" not in f.filename]
            caller = " < ".join(ours[::-1][:4]) or "?"           # innermost first
            hits.append((address[0], address[1], caller))
            raise ConnectionRefusedError(f"a test reached the robot: {address[0]}:{address[1]} from {caller}")
        return real(sock, address, *a)
    return connect


socket.socket.connect = _guard(socket.socket.connect)
socket.socket.connect_ex = _guard(socket.socket.connect_ex)

# the running assistant's blocked-drive state (/dev/shm): a test must not read it (after a live STUCK, "look at that"
# became "go around" and the intents test failed, 2026-10-28)
from assistant import detour as _detour                  # noqa: E402
import tempfile as _tempfile                             # noqa: E402
from pathlib import Path as _Path                        # noqa: E402
_detour.STATE_FILE = _Path(_tempfile.mkdtemp()) / "lumi_stuck.json"


@atexit.register
def _report():
    if hits:
        for host, port, caller in dict.fromkeys(hits):
            print(f"REACHED THE ROBOT: {host}:{port} from {caller}", file=sys.stderr)
        sys.stderr.flush()
        os._exit(1)
