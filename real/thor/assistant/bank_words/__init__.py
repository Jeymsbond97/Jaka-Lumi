"""Wordings for the fast lane, one module per field (arm, motion, korean, questions ...), so each can grow apart.

A module here may hold:
    INTENT = {"look": [...], "no": [...]}                        # added to assistant/intent_bank.KINDS (same kinds,
                                                                 # same <place> / <obj> slots)
    QUICK = {"name": [...], "no": [...]}                         # more wordings for assistant/quick_answers kinds
    QUICK_KINDS = {"kind": ([wordings], {"en": [...], "ko": [...]})}   # new quick-answer kinds with their answers
"""
import importlib
import pkgutil


def modules():
    return [importlib.import_module(f"{__name__}.{m.name}") for m in sorted(pkgutil.iter_modules(__path__), key=lambda m: m.name)]


def merged(attr):
    """{kind: [wordings]} of every module's `attr`, in module order."""
    out = {}
    for m in modules():
        for kind, texts in getattr(m, attr, {}).items():
            out.setdefault(kind, []).extend(texts)
    return out


def vectors(texts, cache):
    """Embeddings of `texts` (assistant/knowledge.embed); kept per text in `cache` (.npz), so only new wordings are
    embedded when a bank grows. Written atomically: several processes may build at once."""
    import os
    import numpy as np
    from assistant import knowledge
    known = {}
    try:
        z = np.load(cache)
        if "texts" in z:
            known = dict(zip(z["texts"].tolist(), z["vecs"]))
    except (OSError, ValueError, KeyError):
        pass
    new = sorted({t for t in texts if t not in known})
    if new:
        known.update(zip(new, knowledge.embed(new)))
        keep = sorted(set(texts) | set(new))
        tmp = f"{cache}.{os.getpid()}.npz"
        np.savez(tmp, texts=np.array(keep), vecs=np.array([known[t] for t in keep]))
        os.replace(tmp, cache)
    return np.array([known[t] for t in texts])
