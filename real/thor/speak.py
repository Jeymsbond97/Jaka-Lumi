"""Play a sound through the robot's USB speaker (on the Thor).

    python speak.py                  # sounds/hello.wav
    python speak.py sounds/x.wav
"""
import pathlib
import subprocess
import sys

DEVICE = "plughw:CARD=Device,DEV=0"     # "USB Audio Device" in `aplay -l`
HERE = pathlib.Path(__file__).resolve().parent


def play(wav="sounds/hello.wav", wait=False):
    """Start playing a WAV file; returns the process (wait=True blocks until it ends)."""
    proc = subprocess.Popen(["aplay", "-q", "-D", DEVICE, str(HERE / wav)])
    if wait:
        proc.wait()
    return proc


if __name__ == "__main__":
    play(sys.argv[1] if len(sys.argv) > 1 else "sounds/hello.wav", wait=True)
