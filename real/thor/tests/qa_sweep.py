"""The blind train sets through quick_answers.kind_of with no history (the quick lane alone, no rules before it).

    python tests/qa_sweep.py                    # first words (commands: 'text' with no 'before'; dialogues: first turn
                                                # 'say') of train, r2-r4, r6, r8, r9, r10: the hits, for review
    python tests/qa_sweep.py r9 r10             # only these rounds' train sets
    python tests/qa_sweep.py --questions r6 r8 r9   # questions_world: want-quick answered at once, and every quick
                                                # answer that misses the case's must / says its must_not (wrong)
    python tests/qa_sweep.py --questions -v r9  # ... and the questions left to the LLM

The words are embedded in batches first (the embedding server is shared), then read from memory.
"""
import glob, importlib, re, sys
sys.path.insert(0, __file__.rsplit("/tests/", 1)[0])
from assistant import knowledge, quick_answers as qa
QUESTIONS, VERBOSE = "--questions" in sys.argv, "-v" in sys.argv
ROUNDS = [a for a in sys.argv[1:] if not a.startswith("-")] or \
    (["r6", "r8", "r9"] if QUESTIONS else ["train", "r2", "r3", "r4", "r6", "r8", "r9", "r10"])
_embed, _known = knowledge.embed, {}


def embed(texts):                                    # batches first, then from memory
    new = [t for t in dict.fromkeys(texts) if t not in _known]
    if new:
        _known.update(zip(new, _embed(new)))
    return [_known[t] for t in texts]


def pieces(t):
    """The words kind_of may embed for t: the whole, each sentence, after a connective, after the last comma."""
    t = qa._tidy(t)
    out = [t] + qa.SENTENCES.split(t)
    m = qa.CONNECT.match(t)
    rest = t[m.end():] if m else t
    out += [rest, rest.rpartition(",")[2]]
    return [qa._core(p) for p in out if p.strip()]


def sets(r, questions):
    for f in sorted(glob.glob("tests/blind/train/*.py" if r == "train" else f"tests/blind/{r}/train/*.py")):
        if f.endswith("__init__.py") or ("questions_world" in f) != questions:
            continue
        yield f, importlib.import_module(f[:-3].replace("/", "."))


def first_words():
    seen, todo = set(), []
    for r in ROUNDS:
        for f, m in sets(r, False):
            texts = [(c["text"], c.get("expect") or c.get("kind")) for c in getattr(m, "CASES", [])
                     if isinstance(c, dict) and c.get("text") and not c.get("before") and not c.get("ctx")]
            texts += [(d["turns"][0]["say"], d["turns"][0].get("expect_action")) for d in getattr(m, "DIALOGUES", [])
                      if d.get("turns") and d["turns"][0].get("say")]
            for t, e in texts:
                if t not in seen:
                    seen.add(t)
                    todo.append((t, e, f"{r}/{f.rsplit('/', 1)[1][:-3]}"))
    embed([p for t, _, _ in todo for p in pieces(t)])
    hits = 0
    for t, e, where in todo:
        k = qa.kind_of(t)
        if k:
            hits += 1
            print(f"{k:12} {where:22} {t!r} want={e}")
    print("texts", len(seen), "quick", hits)


def questions():
    from tests import company_check
    cases = [c for r in ROUNDS for _, m in sets(r, True) for c in m.CASES]
    embed([p for c in cases for p in pieces(c["text"])])
    want = hit = wrong = 0
    for c in cases:
        k = qa.kind_of(c["text"])
        quick = c["expect"] == "quick"
        want += quick
        if k is None:
            if quick and VERBOSE:
                print(f"miss  [{c['q']}] {c['text']!r}")
            continue
        hit += quick
        lang = "ko" if c["lang"] == "ko" or re.search(r"[가-힣]", c["text"]) and c["lang"] != "en" else "en"
        lines = [qa.clock_words(x, lang) for x in qa.KINDS[k][1][lang]]
        probs = sorted({p for x in lines for p in company_check.problems(c, lang, x)})
        if c["expect"].startswith("lookup:"):
            probs.append(f"want {c['expect']}")
        if probs:
            wrong += 1
            print(f"WRONG [{c['q']}, {c['expect']}] {c['text']!r} -> {k} {probs[:2]}")
    print(f"{' '.join(ROUNDS)}: cases {len(cases)}, want quick {want}, answered at once {hit}, wrong quick answers {wrong}")


knowledge.embed = embed
questions() if QUESTIONS else first_words()
