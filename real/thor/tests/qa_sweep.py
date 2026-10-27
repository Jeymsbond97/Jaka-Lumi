"""Every first utterance (commands: 'text' with no 'before'; dialogues: first turn 'say') of the blind train sets
through quick_answers.kind_of with no history: list the hits for review.

    python tests/qa_sweep.py                 # train, r2-r4, r6, r8, r9, r10 train
    python tests/qa_sweep.py r9 r10          # only these rounds' train sets
"""
import glob, importlib, sys
sys.path.insert(0, __file__.rsplit("/tests/", 1)[0])
from assistant import quick_answers as qa
ROUNDS = sys.argv[1:] or ["train", "r2", "r3", "r4", "r6", "r8", "r9", "r10"]
from assistant import knowledge
_embed, _known = knowledge.embed, {}


def embed(texts):                                    # one batch for all the first words first, then from memory
    new = [t for t in dict.fromkeys(texts) if t not in _known]
    if new:
        _known.update(zip(new, _embed(new)))
    return [_known[t] for t in texts]


knowledge.embed = embed
seen = set()
hits = 0
todo = []
for r in ROUNDS:
    for f in sorted(glob.glob("tests/blind/train/*.py" if r == "train" else f"tests/blind/{r}/train/*.py")):
        mod = f[:-3].replace("/", ".")
        if mod.endswith("__init__") or "questions_world" in mod:     # those are scored by blind_check
            continue
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
            if t not in seen:
                seen.add(t)
                todo.append((t, e, f"{r}/{mod.split('.')[-1]}"))
embed([qa._core(qa._tidy(t)) for t, _, _ in todo])
for t, e, where in todo:
    k = qa.kind_of(t)
    if k:
        hits += 1
        print(f"{k:12} {where:22} {t!r} want={e}")
print("texts", len(seen), "quick", hits)
