"""Knowledge base for the assistant: documents -> chunks -> bge-m3 vectors -> search (RAG).

    python assistant/knowledge.py build                    # (re)build knowledge/index.npz from knowledge/**/*.md|txt
    python assistant/knowledge.py search "how much can your arm lift?"

Embeddings come from llama.cpp's llama-server running bge-m3 (multilingual: English, Korean, Chinese),
started on 127.0.0.1:8095 when needed. Ollama is not touched.
"""
import json
import pathlib
import re
import subprocess
import sys
import time
import urllib.request

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]      # the project folder
DOCS = ROOT / "knowledge"
INDEX = DOCS / "index.npz"
EMBED_URL = "http://127.0.0.1:8095"
LLAMA_SERVER = pathlib.Path.home() / "llama.cpp/build/bin/llama-server"
BGE_M3 = pathlib.Path.home() / "models/bge-m3-Q8_0.gguf"
CHUNK = 320            # characters per chunk (about 2 sentences): one topic per vector
LEAD_CHARS = 60        # start of a long paragraph repeated in front of its later pieces
WORD_BONUS = 0.08      # added to the similarity per rare question word found in a chunk (names, numbers, terms)
RARE_SHARE = 0.08      # a word in fewer than this share of all chunks counts as rare
KO_PARTICLES = ("에서", "으로", "한테", "에게", "이랑", "은", "는", "이", "가", "을", "를", "에", "의", "도", "로", "랑",
                "와", "과", "요")


def _post(url, body, timeout=60):
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def ensure_embed_server():
    """Start llama-server with bge-m3 in the background if it is not running yet."""
    try:
        urllib.request.urlopen(f"{EMBED_URL}/health", timeout=1)
        return
    except OSError:
        pass
    log = open(ROOT / "logs" / "embed_server.log", "a")
    subprocess.Popen([str(LLAMA_SERVER), "-m", str(BGE_M3), "--embedding", "--pooling", "cls",
                      "--host", "127.0.0.1", "--port", "8095", "-ngl", "99", "-c", "8192", "-ub", "8192"],
                     stdout=log, stderr=log, start_new_session=True)
    for _ in range(120):
        time.sleep(0.5)
        try:
            urllib.request.urlopen(f"{EMBED_URL}/health", timeout=1)
            return
        except OSError:
            pass
    raise RuntimeError("embedding server did not start, see embed_server.log")


def embed(texts):
    """Unit-length vectors for a list of texts."""
    ensure_embed_server()
    out = []
    for i in range(0, len(texts), 16):
        data = _post(f"{EMBED_URL}/v1/embeddings", {"input": texts[i:i + 16]})["data"]
        out += [d["embedding"] for d in sorted(data, key=lambda d: d["index"])]
    v = np.array(out, dtype=np.float32)
    return v / np.linalg.norm(v, axis=1, keepdims=True)


def chunks(text):
    """One chunk per paragraph (blank lines / headings); a paragraph longer than CHUNK is cut at sentence or line
    ends into pieces of about CHUNK, each after the first starting with LEAD_CHARS of the paragraph's first
    sentence, so "It handles up to 20 kg" still says which robot. Small chunks keep one topic per vector."""
    out, head = [], ""
    for para in (p.strip() for p in re.split(r"\n\s*\n|\n(?=#)", text)):
        if para.startswith("#"):                    # a heading goes in front of every chunk of its section
            head, _, para = para.partition("\n")
            head = head.lstrip("# ").strip()
            para = para.strip()
        if not para:
            continue
        lead0 = f"{head}: " if head else ""
        if len(para) <= CHUNK:
            out.append(lead0 + para)
            continue
        lead = lead0 + re.split(r"(?<=[.!?。])\s+|\n", para, maxsplit=1)[0][:LEAD_CHARS]
        cur = lead0
        for sent in re.split(r"(?<=[.!?。요다])\s+|\n", para):
            if cur and len(cur) + len(sent) > CHUNK:
                out.append(cur)
                cur = f"{lead} …"
            cur = f"{cur} {sent}".strip()
            while len(cur) > CHUNK * 2:             # very long text without sentence ends
                out.append(cur[:CHUNK])
                cur = cur[CHUNK - 50:]
        if cur:
            out.append(cur)
    return out


def build():
    texts, sources = [], []
    for f in sorted(DOCS.rglob("*")):
        if f.suffix in (".md", ".txt") and f.is_file() and "jaka_zh" not in f.parts:   # vendor manuals: not Lumi's
            for c in chunks(f.read_text(encoding="utf-8", errors="ignore")):
                texts.append(c)
                sources.append(str(f.relative_to(DOCS)))
    t = time.time()
    vecs = embed(texts)
    tmp = INDEX.with_name("index.tmp.npz")       # written aside, then swapped in: a running search never reads half a file
    np.savez(tmp, vectors=vecs, texts=np.array(texts, dtype=object), sources=np.array(sources, dtype=object))
    tmp.replace(INDEX)
    print(f"{len(texts)} chunks from {len(set(sources))} files, embedded in {time.time() - t:.1f} s -> {INDEX}")


_index = None


def _words(text):
    """Question words that can be matched literally: Latin words of 3+ letters, numbers, Korean words of 2+
    syllables without a trailing particle ("소노빅터스에" -> "소노빅터스")."""
    out = set()
    for w in re.findall(r"[a-z0-9]{3,}|\d+|[가-힣]{2,}", text.lower()):
        for pa in KO_PARTICLES:
            if re.match("[가-힣]", w) and w.endswith(pa) and len(w) - len(pa) >= 2:
                w = w[:-len(pa)]
                break
        out.add(w)
    return out


def search(question, k=4):
    """[(score, source, text)] best matching chunks: embedding similarity plus WORD_BONUS for each rare word of
    the question the chunk contains (bge-m3 alone missed "Sonovictus" and "20 kg" in long mixed chunks)."""
    global _index
    if _index is None:
        _index = dict(np.load(INDEX, allow_pickle=True))     # all in memory: the file may be rebuilt meanwhile
    if "lower" not in _index:
        _index["lower"] = [str(t).lower() for t in _index["texts"]]
    q = embed([question])[0]
    scores = _index["vectors"] @ q
    n = len(_index["lower"])
    for w in _words(question):
        has = np.array([w in t for t in _index["lower"]])
        if 0 < has.sum() < RARE_SHARE * n:
            scores = scores + WORD_BONUS * has
    best = np.argsort(-scores)[:k]
    return [(float(scores[i]), str(_index["sources"][i]), str(_index["texts"][i])) for i in best]


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "build":
        build()
    elif len(sys.argv) > 2 and sys.argv[1] == "search":
        for score, src, text in search(" ".join(sys.argv[2:])):
            print(f"[{score:.2f}] {src}: {text[:160].replace(chr(10), ' ')}")
    else:
        print(__doc__)
