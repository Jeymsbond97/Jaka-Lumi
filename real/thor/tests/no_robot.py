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


@atexit.register
def _report():
    if hits:
        for host, port, caller in dict.fromkeys(hits):
            print(f"REACHED THE ROBOT: {host}:{port} from {caller}", file=sys.stderr)
        sys.stderr.flush()
        os._exit(1)
