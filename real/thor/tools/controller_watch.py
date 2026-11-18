#!/usr/bin/env python3
"""Watches the arm/body controller (MiniCab, 192.168.10.90) on the robot LAN.

Pings it every 10 s and writes a line to logs/controller_watch.log only when it disappears or comes back,
with the date, how long the previous state lasted, and the base state at that moment (battery, charging,
E-stop, move status), so the pattern of the drops can be found. One "alive" line per hour shows the watch runs.
Service: lumi-ctrlwatch.service (systemctl --user status lumi-ctrlwatch).
"""
import json
import subprocess
import time
import urllib.request
from datetime import datetime
from pathlib import Path

HOST = "192.168.10.90"
LOG = Path(__file__).resolve().parent.parent / "logs" / "controller_watch.log"
EVERY = 10
FAILS_FOR_DOWN = 2  # two missed pings in a row (20 s) count as gone


def ping() -> bool:
    return subprocess.run(["ping", "-c1", "-W2", HOST], stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL).returncode == 0


def base_state() -> str:
    try:
        with urllib.request.urlopen("http://127.0.0.1:8100/status", timeout=25) as r:
            b = json.load(r).get("base") or {}
        return (f"battery={b.get('power_percent')}% charging={b.get('charge_state')} "
                f"estop={b.get('estop_state')} move={b.get('move_status')} error={b.get('error_code')}")
    except Exception as e:
        return f"base state unknown ({e.__class__.__name__})"


def write(msg: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}\n")


def main() -> None:
    up = ping()
    since = time.time()
    last_alive = since
    misses = 0
    write(f"watch started: controller {'UP' if up else 'DOWN'}; {base_state()}")
    while True:
        time.sleep(EVERY)
        ok = ping()
        misses = 0 if ok else misses + 1
        now = time.time()
        if up and misses >= FAILS_FOR_DOWN:
            up = False
            write(f"controller DOWN after {(now - since) / 60:.1f} min up; {base_state()}")
            since = now
        elif not up and ok:
            up = True
            write(f"controller UP after {(now - since) / 60:.1f} min down; {base_state()}")
            since = now
        if now - last_alive >= 3600:
            write(f"alive: controller {'UP' if up else 'DOWN'} for {(now - since) / 60:.0f} min; {base_state()}")
            last_alive = now


if __name__ == "__main__":
    main()
