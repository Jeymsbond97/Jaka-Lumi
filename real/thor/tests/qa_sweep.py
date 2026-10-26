"""Every first utterance (commands: 'text' with no 'before'; dialogues: first turn 'say') of the blind train sets
through quick_answers.kind_of with no history: list the hits for review."""
import glob, importlib, sys
sys.path.insert(0, __file__.rsplit("/tests/", 1)[0])
from assistant import quick_answers as qa
seen = set()
for f in sorted(glob.glob("tests/blind/train/*.py") + glob.glob("tests/blind/r[234]/train/*.py") + glob.glob("tests/blind/r6/train/*.py")):
    mod = f[:-3].replace("/", ".")
    if mod.endswith("__init__"): continue
    m = importlib.import_module(mod)
    texts = []
    for c in getattr(m, "CASES", []):
        if isinstance(c, dict) and c.get("text") and not c.get("before") and not c.get("ctx"):
            texts.append((c["text"], c.get("expect") or c.get("kind")))
    for d in getattr(m, "DIALOGUES", []):
        t = d.get("turns") or []
        if t and t[0].get("say"):
            texts.append((t[0]["say"], t[0].get("expect_action")))
    for t, e in texts:
        if t in seen: continue
        seen.add(t)
        k = qa.kind_of(t)
        if k: print(f"{k:12} {mod.split('.')[-2]}/{mod.split('.')[-1]:20} {t!r} want={e}")
print("texts", len(seen))
