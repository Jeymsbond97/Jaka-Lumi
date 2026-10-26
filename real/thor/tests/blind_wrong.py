"""Print the wrong / motion rows of a saved blind run: python tests/blind_wrong.py logs/blind_r6_train_a5n3.json [set] [verdicts]"""
import collections
import json
import sys

d = json.load(open(sys.argv[1]))
sets = [sys.argv[2]] if len(sys.argv) > 2 and sys.argv[2] != "-" else list(d)
want = set((sys.argv[3] if len(sys.argv) > 3 else "wrong,motion").split(","))
for s in sets:
    rows = [r for r in d[s]["rows"] if r["verdict"] in want]
    print(f"== {s}: {len(rows)}", collections.Counter(r["verdict"] for r in rows))
    for r in rows:
        print(f"{r['verdict']:6} {r['show'][:260]}")
