"""Speech-to-text check: spoken cases (tests/asr_cases.py) made with the TTS, made to sound like the robot's
microphones, sent through ears.transcribe() exactly as Lumi does, then through Lumi's routing.

    .venv/bin/python tests/asr_check.py                  # all cases, both rooms
    .venv/bin/python tests/asr_check.py --room far       # one room: near (clip mic) | far (head array, echo, people)
    .venv/bin/python tests/asr_check.py --prompt "..."   # another whisper prompt than ears.PROMPT
    .venv/bin/python tests/asr_check.py --heard          # also the real clips in logs/heard/ (text only, no judgement)
    .venv/bin/python tests/asr_check.py --set LANG_RETRY=False --tag before   # an ears constant; -> logs/asr_check_before.md

Needs a whisper-server; the check starts its own on STT_PORT (never the live one on 8096, which Lumi uses).
A case is right when the text routes as the written text does (tests/command_check.rules: the same motion, or both
for the LLM and the words nearly the same), whisper's language is the spoken one, and ears.understood() takes it
(else Lumi says "say it again"). -> logs/asr_check.md / .json; audio cached in logs/asr_check/.
"""
import collections
import difflib
import hashlib
import json
import pathlib
import re
import subprocess
import sys
import time
import urllib.request
import wave

import numpy as np

from assistant import brain, lumi
from audio import ears
from tests.asr_cases import CASES
from tests.command_check import rules

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "logs" / "asr_check"
STT_PORT = 8097
MARKERS = ['home', 'PInit', 'Wp', 'a', 'b', 'dock2', 'exit', 'final', 'p1', 'p10', 'p2', 'p3', 'p4', 'p5', 'p6', 'p7',
           'p8', 'p9', 'aisle_a', 'aisle_b']                        # the map of 2026-10-21 and a few more
VOICES = ["F1", "F2", "F3", "F4", "F5", "M1", "M2", "M3", "M4", "M5"]
ROOMS = {   # how the sound reaches whisper: echo time (s), signal to noise (dB), level (peak of full scale), babble
    "near": dict(rt60=0.15, snr=28, peak=0.4, babble=False),     # clip mic at the chest
    "far": dict(rt60=0.5, snr=12, peak=0.04, babble=True),       # head array 1.5-3 m away, people talking around
}
TEXT_CLOSE = 0.8            # difflib ratio of the normalised texts for a question / short answer to count as heard


def start_server():
    url = f"http://127.0.0.1:{STT_PORT}"
    try:
        urllib.request.urlopen(url + "/", timeout=1)
    except OSError:
        log = open(OUT / "whisper.log", "a")
        subprocess.Popen([str(ears.WHISPER_SERVER), "-m", str(ears.WHISPER_MODEL), "--host", "127.0.0.1",
                          "--port", str(STT_PORT), "-l", "auto", "-nt"], stdout=log, stderr=log, start_new_session=True)
        for _ in range(120):
            time.sleep(0.5)
            try:
                urllib.request.urlopen(url + "/", timeout=1)
                break
            except OSError:
                pass
    ears.STT_URL = url
    ears.HEARD_DIR = OUT / "heard"           # never the robot's logs/heard


_tts = {}


def synth(pieces, voice, speed):
    """[(lang, words)] -> float32 mono 16 kHz, cached."""
    key = hashlib.md5(json.dumps([pieces, voice, speed]).encode()).hexdigest()[:16]
    f = OUT / "audio" / f"{key}.npy"
    if f.exists():
        return np.load(f)
    if not _tts:
        from supertonic import TTS
        _tts["tts"] = TTS(model="supertonic-3", model_dir=ROOT / "models/supertonic3", auto_download=False,
                          intra_op_num_threads=4)
    tts = _tts["tts"]
    style = tts.get_voice_style(voice)
    parts = []
    for lang, words in pieces:
        wav, _ = tts.synthesize(words, voice_style=style, lang=lang, total_steps=4, speed=speed, silence_duration=0.1)
        parts.append(np.asarray(wav, np.float32).reshape(-1))
    x = np.concatenate(parts)
    x = np.interp(np.arange(0, len(x), tts.sample_rate / ears.RATE), np.arange(len(x)), x).astype(np.float32)
    f.parent.mkdir(parents=True, exist_ok=True)
    np.save(f, x)
    return x


def room(x, how, rng, others=()):
    """Echo (exponential noise tail), people talking (other cases' audio), noise, a quiet level; -> int16."""
    n = int(how["rt60"] * ears.RATE)
    ir = rng.standard_normal(n) * np.exp(-6.9 * np.arange(n) / n)
    ir[0] = 1.0 / 0.3
    ir *= 0.3
    y = np.convolve(x, ir)[:len(x) + n // 2]
    y = np.concatenate([np.zeros(int(0.3 * ears.RATE)), y, np.zeros(int(0.4 * ears.RATE))])   # pre-roll, end silence
    p = float(np.mean(y ** 2)) + 1e-12
    noise = np.cumsum(rng.standard_normal(len(y)))                  # brown-ish room rumble + hiss
    noise = noise - np.convolve(noise, np.ones(400) / 400, "same") + 0.5 * rng.standard_normal(len(y))
    if how["babble"] and others:
        b = np.zeros(len(y))
        for o in others:
            start = rng.integers(0, max(1, len(y) - len(o))) if len(o) < len(y) else 0
            seg = o[:len(y) - start]
            b[start:start + len(seg)] += seg
        noise = noise / np.sqrt(np.mean(noise ** 2)) + 2.0 * b / (np.sqrt(np.mean(b ** 2)) + 1e-9)
    noise *= np.sqrt(p / 10 ** (how["snr"] / 10) / (np.mean(noise ** 2) + 1e-12))
    y = y + noise
    y *= how["peak"] / (np.abs(y).max() + 1e-9)
    return np.clip(y * 32767, -32767, 32767).astype(np.int16)


def plain(t):
    return re.sub(r"[^\w가-힣 ]", "", (t or "").lower()).split()


def route(text, b):
    try:
        r = rules(text, "idle", MARKERS, b) or "llm"
        if r.startswith("action:fetch"):                         # its target is the whole text: what it asks for
            task = brain.fetch_from_text(text, MARKERS)[0]
            r = "action:fetch " + " ".join(f"{k}={task[k]}" for k in sorted(task) if task[k] and k != "said")
        return r
    except Exception as e:                                       # noqa: BLE001 - a crash is a failure of that case
        return f"error {e!r}"


def judge(c, heard, stt):
    """(verdict, why): right | slip (text heard wrong) | lang (wrong language tag) | unclear (asked again) | lost."""
    if not heard:
        return "lost", "nothing"
    want_lang = {"en": "english", "ko": "korean"}.get(c["lang"])
    if c["kind"] == "wake":
        ok = bool(lumi.WAKE.search(heard) or lumi.HELLO_ONLY.match(heard))
        return ("right", "") if ok else ("slip", "no wake word")
    clear = ears.understood() or (ears.heard_clearly() and lumi.own_command(heard, ""))
    if not clear:
        return "unclear", f"{stt.get('language')} {stt.get('logprob')}"
    if want_lang and stt.get("language") != want_lang:
        return "lang", stt.get("language")
    want, got = route(c["text"], brain.Brain()), route(heard, brain.Brain())
    if want != got:
        return "slip", f"{got} (want {want})"
    if want == "llm" or c["kind"] in ("short", "question"):
        r = difflib.SequenceMatcher(None, " ".join(plain(c["text"])), " ".join(plain(heard))).ratio()
        if r < TEXT_CLOSE:
            return "slip", f"text {r:.2f}"
    return "right", ""


def main(args):
    OUT.mkdir(parents=True, exist_ok=True)
    rooms = [args[args.index("--room") + 1]] if "--room" in args else list(ROOMS)
    if "--prompt" in args:
        ears.PROMPT = args[args.index("--prompt") + 1]
    for i, a in enumerate(args):                                # --set LANG_RETRY=False: an ears constant
        if a == "--set":
            k, v = args[i + 1].split("=", 1)
            setattr(ears, k, type(getattr(ears, k))(eval(v)))
    only = args[args.index("--only") + 1] if "--only" in args else None
    tag = args[args.index("--tag") + 1] if "--tag" in args else ""
    start_server()
    rng = np.random.default_rng(5)
    rows, t0 = [], time.time()
    cases = [c for c in CASES if not only or re.search(only, c["text"])]
    for i, c in enumerate(cases):
        voice, speed = VOICES[i % len(VOICES)], [0.85, 0.95, 1.05, 1.15][(i // len(VOICES)) % 4]
        x = synth(c["say"], voice, speed)
        for rname in rooms:
            others = [synth(CASES[(i * 7 + k * 13) % len(CASES)]["say"], VOICES[(i + k + 3) % 10], 1.0) * 0.5
                      for k in range(3)] if ROOMS[rname]["babble"] else ()
            audio = room(x, ROOMS[rname], rng, others)
            heard = ears.transcribe(audio, ears.PROMPT)
            stt = dict(ears.last_stt)
            verdict, why = judge(c, heard, stt)
            rows.append({**c, "room": rname, "voice": voice, "speed": speed, "heard": heard, "stt": stt,
                         "verdict": verdict, "why": why})
            if verdict != "right" and "-v" in args:
                print(f"{verdict:7} [{c['lang']}/{rname}] {c['text']!r} -> {heard!r} {why}", flush=True)
    if "--heard" in args:
        heard_clips(rows)
    name = "asr_check" + (f"_{tag}" if tag else "")
    (ROOT / "logs" / f"{name}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=0))
    report(rows, time.time() - t0, ROOT / "logs" / f"{name}.md")


def heard_clips(rows):
    """The real utterances kept in logs/heard (local only): the text with this prompt, no judgement."""
    for f in sorted((ROOT / "logs" / "heard").glob("*.wav")):
        with wave.open(str(f)) as w:
            audio = np.frombuffer(w.readframes(w.getnframes()), np.int16)
        heard = ears.transcribe(audio, ears.PROMPT)
        rows.append({"kind": "real", "lang": "?", "text": f.name, "room": "real", "heard": heard,
                     "stt": dict(ears.last_stt), "verdict": "real", "why": ""})


def report(rows, secs, path):
    judged = [r for r in rows if r["verdict"] != "real"]
    by = collections.defaultdict(collections.Counter)
    for r in judged:
        for k in (f"{r['lang']} {r['room']}", f"{r['kind']} {r['room']}", "ALL"):
            by[k][r["verdict"]] += 1
    kinds = ["right", "slip", "lang", "unclear", "lost"]
    lines = [f"# Speech-to-text check ({time.strftime('%Y-%m-%d %H:%M')}, prompt {ears.PROMPT!r}, {secs:.0f} s)", "",
             f"{len(judged)} spoken cases. " + ", ".join(kinds) + ".", "",
             "| group | cases | " + " | ".join(kinds) + " |", "|---|---|" + "---|" * len(kinds)]
    for k in sorted(by, key=lambda k: (k == "ALL", k)):
        c = by[k]
        lines.append(f"| {k} | {sum(c.values())} | " + " | ".join(str(c[v]) for v in kinds) + " |")
    for v in kinds[1:]:
        lines += ["", f"## {v}", ""] + [f"- [{r['lang']}/{r['room']} {r['voice']} {r['speed']}] {r['text']!r} -> "
                                        f"{r['heard']!r} [{r['stt'].get('language')} {r['stt'].get('logprob')}] {r['why']}"
                                        for r in judged if r["verdict"] == v]
    real = [r for r in rows if r["verdict"] == "real"]
    if real:
        lines += ["", "## Real clips", ""] + [f"- {r['text']}: {r['heard']!r} [{r['stt'].get('language')} "
                                              f"{r['stt'].get('logprob')}]" for r in real]
    path.write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:len(by) + 6]))


if __name__ == "__main__":
    main(sys.argv[1:])
