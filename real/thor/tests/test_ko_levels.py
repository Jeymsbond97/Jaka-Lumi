"""Korean speech levels read as the English request (a fixed part of tests/ko_levels_check.py): every level of a few
capabilities gives the same action, and the same phrase said as a past, a negation, a later time or a condition
gives no motion. No robot; the embedding server answers the bank.

    .venv/bin/python tests/test_ko_levels.py
"""
from tests import ko_levels_check

CAPS = {"wave", "turn45", "head_up", "follow", "fetch", "go_to"}

rows = ko_levels_check.check(CAPS)
bad = [r for r in rows if r[-1] != "right"]
for name, level, text, got, want, v in bad:
    print(f"FAIL {name} [{level}] {text!r} -> {got} (want {want}, {v})")
assert not bad, f"{len(bad)} of {len(rows)} not right"
assert len(rows) > 400, len(rows)
print(f"ok: {len(rows)} forms")
