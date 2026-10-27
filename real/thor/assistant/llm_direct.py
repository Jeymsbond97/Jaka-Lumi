"""Chat with a model straight on the llama-server that Ollama runs for it, without Ollama's ~0.9 s per request.

    python assistant/llm_direct.py "What is your name?"     # one reply, with the time it took

Ollama 0.31 starts one llama-server per loaded model (`--model <blob> --port N`) and spends about 0.9 s in its own
scheduler on every request (its load_duration, with the model loaded; measured 2026-10-21), while the runner answers
a cached prompt in ~0.1 s. Here the messages are rendered the way Ollama's gemma4 renderer does it (checked against
Ollama: the same token count and a full prompt-cache hit, so both share the runner's cache) and sent to the runner's
/completion with Ollama's sampling values. When anything is off (model not loaded, runner gone, a model that is not
gemma4) stream() returns None and the caller asks Ollama, which also loads the model again.
"""
import json
import pathlib
import re
import sys
import threading
import time
import urllib.request

OLLAMA = "http://127.0.0.1:11434"
# Ollama's values for gemma4 (its Modelfile and defaults): the runner's own defaults differ (min_p 0.05, no repeat penalty)
SAMPLING = {"top_k": 64, "top_p": 0.95, "min_p": 0.0, "repeat_penalty": 1.1, "repeat_last_n": 64}
NO_THINKING = "<|channel>thought\n<channel|>"      # what Ollama adds to the model's turn for "think": false

KEEP_EVERY_S = 60.0                                # s; Ollama is told this often to keep the model loaded (see _keep)

_ports = {}                                        # model -> the runner's port, found once
_kept = {}                                         # model -> when Ollama was last told to keep it
_filled = {}                                       # model -> (prompt, the runner's task id) of the last prefill


def render(messages, reply=True):
    """Ollama's gemma4 prompt (the runner adds <bos>); reply=False: the turns only, the start of a longer prompt."""
    turns = "".join(f"<|turn>{'model' if m['role'] == 'assistant' else m['role']}\n{m['content']}<turn|>\n"
                    for m in messages)
    return f"{turns}<|turn>model\n{NO_THINKING}" if reply else turns


def _find_port(model):
    """The port of the llama-server Ollama runs for this model, or None (not loaded)."""
    req = urllib.request.Request(f"{OLLAMA}/api/show", json.dumps({"model": model}).encode())
    with urllib.request.urlopen(req, timeout=2) as r:
        blob = re.search(r"^FROM (\S+)", json.loads(r.read())["modelfile"], re.M).group(1)
    for cmdline in pathlib.Path("/proc").glob("[0-9]*/cmdline"):
        try:
            args = cmdline.read_bytes().split(b"\0")
        except OSError:
            continue
        if args and args[0].endswith(b"llama-server") and blob.encode() in args and b"--port" in args:
            return int(args[args.index(b"--port") + 1])
    return None


def _keep(model):
    """Ollama never sees these requests, so it would unload the model when someone loaded it with a timeout:
    now and then, in the background, an empty request (it only loads, nothing runs) sets keep_alive -1 again."""
    if time.time() - _kept.get(model, 0.0) < KEEP_EVERY_S:
        return
    _kept[model] = time.time()

    def run():
        try:
            req = urllib.request.Request(f"{OLLAMA}/api/generate", json.dumps({"model": model, "keep_alive": -1}).encode())
            urllib.request.urlopen(req, timeout=60).read()
        except OSError:
            pass
    threading.Thread(target=run, daemon=True).start()


def stream(messages, model, temperature=0.3, num_predict=200):
    """An iterator over the reply's text pieces, or None when the runner can't be reached (then use Ollama).
    The request is sent here, so a dead runner shows now and not half way through the reply."""
    if not model.startswith("gemma4"):             # render() is gemma4's prompt only
        return None
    body = json.dumps({"prompt": render(messages), "n_predict": num_predict, "temperature": temperature,
                       "stream": True, "cache_prompt": True, **SAMPLING}).encode()
    for fresh in (False, True):                    # the cached port, then once more after looking it up again
        try:
            if fresh or model not in _ports:
                _ports[model] = _find_port(model)
            if _ports[model] is None:
                return None
            r = urllib.request.urlopen(urllib.request.Request(
                f"http://127.0.0.1:{_ports[model]}/completion", body, {"Content-Type": "application/json"}), timeout=120)
            _keep(model)
            return _pieces(r)
        except (OSError, ValueError, KeyError, AttributeError):
            _ports.pop(model, None)
    return None


def prefill(messages, model):
    """In the background, have the runner process these messages (the start of the next prompt) now, so the next
    request only processes its own last message. The runner has one slot: any other prompt in between (a lookup, a
    farewell, a mission read-back, a picture) leaves only ~1000 tokens of ours cached and the next answer ~3.5 s
    slower. Nothing is sent when the runner has done nothing since the same prefill (its /slots task id)."""
    if not model.startswith("gemma4"):
        return
    prompt = render(messages, reply=False)

    def run():
        try:
            if model not in _ports:
                _ports[model] = _find_port(model)
            base = f"http://127.0.0.1:{_ports[model]}"
            if _filled.get(model, (None,))[0] == prompt and _filled[model][1] == _task(base):
                return
            body = json.dumps({"prompt": prompt, "n_predict": 0, "cache_prompt": True}).encode()
            urllib.request.urlopen(urllib.request.Request(f"{base}/completion", body,
                                                          {"Content-Type": "application/json"}), timeout=60).read()
            _filled[model] = (prompt, _task(base))
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            _ports.pop(model, None)
    threading.Thread(target=run, daemon=True).start()


def _task(base):
    """The id of the last task the runner's slot ran."""
    with urllib.request.urlopen(f"{base}/slots", timeout=2) as r:
        return json.loads(r.read())[0]["id_task"]


def _pieces(r):
    """The reply's text pieces. An empty thought block the model writes itself ("<|channel>thought\n<channel|>",
    the turn's NO_THINKING once more) is dropped: it was said as the whole reply once (r13 check, 2026-10-27)."""
    thinking = False
    with r:
        for line in r:
            if not line.startswith(b"data: "):
                continue
            d = json.loads(line[6:])
            piece, out = d.get("content") or "", ""
            while piece:
                if thinking:
                    _, end, piece = piece.partition("<channel|>")
                    thinking = not end
                else:
                    said, start, piece = piece.partition("<|channel>")
                    out, thinking = out + said, bool(start)
            piece = out
            if piece:
                yield piece
            if d.get("stop"):
                return


if __name__ == "__main__":
    from assistant import brain
    t = time.time()
    pieces = stream([{"role": "user", "content": " ".join(sys.argv[1:]) or "Hi"}], brain.MODEL)
    print("runner not found, Ollama would be used" if pieces is None else "".join(pieces), f"({time.time() - t:.2f} s)")
