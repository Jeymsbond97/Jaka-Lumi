"""Play a sound through the robot's USB speaker (on the Thor).

    python speak.py                  # sounds/hello.wav
    python speak.py sounds/x.wav
"""
import pathlib
import subprocess
import sys
import threading

import mic

DEVICE = "plughw:CARD=Device,DEV=0"     # "USB Audio Device" in `aplay -l`
HERE = pathlib.Path(__file__).resolve().parent


def mouth_volume():
    from mouth import volume                    # one volume setting for every sound (mouth.py)
    return volume()


def play(wav="sounds/hello.wav", wait=False):
    """Start playing a WAV file; returns the process (wait=True blocks until it ends)."""
    subprocess.run(["amixer", "-q", "-c", "Device", "sset", "Speaker", f"{mouth_volume()}%"], check=False)
    mic.speaking(True)                          # the microphone must not hear Lumi itself
    proc = subprocess.Popen(["aplay", "-q", "-D", DEVICE, str(HERE / wav)])

    def unmute():
        proc.wait()
        mic.speaking(False)
    if wait:
        unmute()
    else:
        threading.Thread(target=unmute, daemon=True).start()
    return proc


if __name__ == "__main__":
    play(sys.argv[1] if len(sys.argv) > 1 else "sounds/hello.wav", wait=True)
