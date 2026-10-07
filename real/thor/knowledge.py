"""Knowledge base for the assistant: documents -> chunks -> bge-m3 vectors -> search (RAG).

    python knowledge.py build                    # (re)build knowledge/index.npz from knowledge/**/*.md|txt
    python knowledge.py search "how much can your arm lift?"

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

HERE = pathlib.Path(__file__).resolve().parent
DOCS = HERE / "knowledge"
INDEX = DOCS / "index.npz"
EMBED_URL = "http://127.0.0.1:8095"
LLAMA_SERVER = pathlib.Path.home() / "llama.cpp/build/bin/llama-server"
BGE_M3 = pathlib.Path.home() / "models/bge-m3-Q8_0.gguf"
CHUNK = 500            # characters per chunk (about 2-4 sentences)


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
    log = open(HERE / "embed_server.log", "a")
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
    """Split on blank lines / headings, then pack paragraphs into ~CHUNK-character pieces."""
    paras = [p.strip() for p in re.split(r"\n\s*\n|\n(?=#)", text) if p.strip()]
    out, cur = [], ""
    for p in paras:
        if cur and len(cur) + len(p) > CHUNK:
            out.append(cur)
            cur = ""
        cur = f"{cur}\n{p}".strip()
        while len(cur) > CHUNK * 2:                 # very long paragraph (e.g. Chinese text without breaks)
            out.append(cur[:CHUNK])
            cur = cur[CHUNK - 50:]
    if cur:
        out.append(cur)
    return out


def build():
    texts, sources = [], []
    for f in sorted(DOCS.rglob("*")):
        if f.suffix in (".md", ".txt") and f.is_file():
            for c in chunks(f.read_text(encoding="utf-8", errors="ignore")):
                texts.append(c)
                sources.append(str(f.relative_to(DOCS)))
    t = time.time()
    vecs = embed(texts)
    np.savez(INDEX, vectors=vecs, texts=np.array(texts, dtype=object), sources=np.array(sources, dtype=object))
    print(f"{len(texts)} chunks from {len(set(sources))} files, embedded in {time.time() - t:.1f} s -> {INDEX}")


_index = None


def search(question, k=4):
    """[(score, source, text)] best matching chunks."""
    global _index
    if _index is None:
        _index = np.load(INDEX, allow_pickle=True)
    q = embed([question])[0]
    scores = _index["vectors"] @ q
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
