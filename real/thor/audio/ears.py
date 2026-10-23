"""Listening: one utterance from the head microphone array (via mic.py) turned into text.

    python audio/ears.py            # listen once, print what was said (English or Korean)

Recording, speech detection and "do not listen while Lumi talks" are in mic.py (one always-on recording that
lumi.py also uses for the wake word). Speech-to-text: whisper.cpp (GPU) server with large-v3-turbo on
127.0.0.1:8096, started when needed.
"""
import difflib
import io
import json
import re
import pathlib
import subprocess
import threading
import time
import urllib.request
import uuid
import wave

import numpy as np

from audio import mic

ROOT = pathlib.Path(__file__).resolve().parents[1]      # the project folder
RATE = mic.RATE
STT_URL = "http://127.0.0.1:8096"
WHISPER_SERVER = ROOT / "whisper.cpp/build/bin/whisper-server"
WHISPER_MODEL = ROOT / "models/ggml-large-v3-turbo.bin"   # f16: more right than q5_0 (tests/asr_check.py
                                 # 443 / 431 of 644, 196 / 185 of 254) and ~0.35 s faster with the GPU busy
PROMPT = "Hi Lumi. Hey Lumi. 루미야."   # helps whisper spell the robot's name
LANG_PROMPT = {"en": "Hi Lumi. Hey Lumi.", "ko": "안녕하세요, 루미야."}   # when asked again in one language: the
                                 # mixed prompt made whisper write Korean in Latin letters ("Natarawa" for 나 따라와)
last = {}                        # levels of the last listen() call, for the log: noise, threshold, peak


def ensure_stt_server():
    try:
        urllib.request.urlopen(f"{STT_URL}/", timeout=1)
        return
    except OSError:
        pass
    log = open(ROOT / "logs" / "whisper_server.log", "a")
    subprocess.Popen([str(WHISPER_SERVER), "-m", str(WHISPER_MODEL), "--host", "127.0.0.1", "--port", "8096",
                      "-l", "auto", "-nt"], stdout=log, stderr=log, start_new_session=True)
    for _ in range(120):
        time.sleep(0.5)
        try:
            urllib.request.urlopen(f"{STT_URL}/", timeout=1)
            return
        except OSError:
            pass
    raise RuntimeError("whisper-server did not start, see whisper_server.log")


def record(wait_s=8.0, on_start=None, abort=None, since=None):
    """Wait up to wait_s for speech to start, then until it ends. Returns a mic.Utterance or None.
    abort: optional function checked every 30 ms; when it returns True, stop and return None.
    since: take speech that ended after this time, also one already heard (the rest of a sentence)."""
    m = mic.get()
    if since is None:
        m.clear()                                # only speech that starts from now on
    t0, started = since or time.time(), False
    try:
        while True:
            if abort and abort():
                return None
            u = m.next(0.03)
            if u is not None and u.t_end > t0:
                return u
            if m.in_speech and not started:
                started = True
                if on_start:
                    on_start()
            if not m.in_speech and not started and time.time() - t0 > wait_s:
                return None
    finally:
        last.update(noise=round(m.noise), threshold=round(m.threshold))


def louder(audio, target=0.7):
    """Quiet speech from far away: raise the peak to `target` of full scale (at most 12x) for speech-to-text."""
    import numpy as np
    peak = float(np.abs(audio).max()) if len(audio) else 0.0
    if peak < 1:
        return audio
    gain = min(12.0, target * 32767 / peak)
    return np.clip(audio.astype(np.float32) * gain, -32767, 32767).astype(np.int16) if gain > 1.05 else audio


LANGS = {"english": "en", "korean": "ko"}
MIN_LOGPROB = -1.0               # below this average token log-probability whisper was guessing
NAME_ONLY = re.compile(r"\W*(lumi|루미야?)\W*", re.I)
# whisper writes the prompt's "Lumi." / "Hey Lumi." for sounds that are no speech: 13 of 15 "Lumi." in logs/heard
# (2026-10-21 12:00-13:50) were a clap, a thud, music or "はい" without the prompt. Such a text is checked once more
# without the prompt and dropped when no word there sounds like the name.
CALL_ONLY = re.compile(r"\W*(?:(?:hi|hey|hello|안녕)\W*)?(lumi|루미야?)\W*", re.I)
KO_BONUS = 0.3                   # another language named: asked in Korean and in English, a Hangul answer's average
                                 # log-probability counts this much more (tests/asr_check.py: +3 of 898 cases)
ODD_KO_BONUS = 0.3               # English text with a word no dictionary has: Korean asked too, taken when written in
                                 # Hangul and its log-probability + this beats the English one (tests/asr_check.py)
WORDS_FILE = pathlib.Path("/usr/share/dict/words")
OUR_WORDS = {"lumi", "cutshion", "okay", "ok", "hmm", "um", "uh"}
SLIPS = [   # whisper's slips seen in tests/asr_check.py and logs/lumi.log (our names first) -> as said
    (r"\b(?:[kc]ut(?:s|t)?ch[aei]n|katchen|kutch and|kutsche(?: and(?= company))?)(?= company|\b)", "Cutshion"),
    (r"\b(?:coaching|cushion|kitchen|kuching|kuchung|kuchun) (?=company)", "Cutshion "),
    (r"\bcushion(?=[은는이가을를의에])|커션|컷션", "쿳션"),
    (r"난시(?=가?\s*어때)", "날씨"),                   # "오늘 난시가 어때요?" (lumi.log 2026-10-20)
    # "How old are you?" in the owner's voice, tagged Korean or Turkish: "호월달요.", "호화 다리.", "Powa tari.",
    # "호valde arıyor.", "Hovalt arıyor." (8 times in lumi.log 2026-10-21 / 22, never heard right)
    (r"^\W*lumi,? stopped\W*$", "Lumi, stop."),       # the owner's English, live 2026-10-21 / 22 (lumi.log)
    (r"\bwhat(?:'s| is) (?:it|that|the hand of)\W+(?=my (?:left |right )?hand\b)",
     lambda m: m.group(0)[0] + "hat is in "),   # "What is it
                                                     # my hand?", "What is it? My hand." for "what is in my hand"
    (r"^\W*(?:호|ho|po)\s?(?:월|화|wa|val[dt]?e?)\s?(?:달|다리|대|tari|arıyor|도)[^.?!]{0,8}[.?!]?\s*$", "How old are you?"),
]
_words = set()
last_stt = {}                    # language / confidence of the last transcription (see understood())


VAD_MODEL = ROOT / "models/silero_vad.onnx"   # Silero VAD v5.1.2 (MIT), 2.3 MB, from github.com/snakers4/silero-vad
                                 # /raw/v5.1.2/src/silero_vad/data/silero_vad.onnx; missing: every sound goes to whisper
VAD_P = 0.3                      # a 32 ms frame is speech when Silero's probability is above this
MIN_SPEECH_S = 0.1               # s of speech frames an utterance needs, else it is music or noise and whisper is not
                                 # asked: soft music passes mic.py's level check and whisper writes "-", "-끝-", "감사합니다."
                                 # for it. logs/heard 2026-10-22 12:17-12:29: the 27 clips of music only had 0-0.13 s
                                 # (those above 0.1 s came back as "-" / "Lumi." and are dropped anyway), the 23 of
                                 # speech 0.45 s and more; tests/asr_check.py --cases 4
SPEECH_PER_SYLLABLE = 0.05       # s of speech frames a text needs per syllable: whisper's "감사합니다." for music came
                                 # with 0.13-0.29 s (0.03-0.06 s per syllable); spoken cases (tests/asr_check.py, 898)
                                 # have 0.08 s and more, 1 % below 0.11 s
REPEAT = re.compile(r"(\b\w+(?:\W+\w+)+?)(?:\W+\1\b){2,}", re.I)   # a phrase of 2+ words three times over:
                                 # whisper's loop on a sound it can't read ("Look right. Look right. Look right." for
                                 # "dock2로 가서 충전해" far away, "이 마가의 피지않아." x3 in lumi.log 2026-10-21)
SAME_WORDS = 0.8                 # difflib ratio of two readings' letters to count as the same words
STOCK = re.compile(r"\W*(?:감사합니다|고맙습니다|thank you|thanks|hey|hi|bye|mm+)\W*", re.I)
                                 # whisper's stock words when made to write a language for a sound it took for another
                                 # one (logs/heard 18:39: "はい" -> "감사합니다." / "Hey."): dropped there. Not "네" /
                                 # "yes": answers to Lumi (a real "네" tagged Japanese was lost, blind short set)
NOT_SAID = re.compile(r"^\W*$|^\s*-|자막|시청해\s*주셔서|thanks? (?:you )?for watching|subtitles? by", re.I)
                                 # whisper's subtitle habits on music: no word at all, a dialogue dash ("-끝-", "- 네."),
                                 # a caption credit ("자막 제공 및 광고를 포함하고 있습니다.")
_vad = {}
_early = {}                      # the last early() run: its audio, done (Event), out (text, stt)
EARLY_REST = mic.END_SILENCE - mic.EARLY_QUIET_S + 0.05   # s an utterance may be longer than its early run's audio
                                 # for that run to be taken: only the quiet that ended it, no new speech
CUT_OFF = re.compile(r"(?:\b(?:let'?s|can you|could you|would you|will you|can i|and|but|or|the|a|an|to|of|with|"
                     r"my|your|i want|i'd like|i need)|(?<![가-힣])(?:저기|그리고|근데|혹시|그래서|그러니까|있잖아))\W*$|"
                     r"\b(?:our|at|about|from|for)[.,…]*$|(?:\.\.\.|…|,)\s*$", re.I)
                                 # a sentence cut off by a pause longer than mic.END_SILENCE ("Let's" of "Let's ...
                                 # follow me", 2026-10-22 14:36; today's clips: the longest pause inside an utterance
                                 # 0.39 s at the 90th percentile, 0.51 s at most, so one cut in 140 turns); also
                                 # whisper's own trailing "..." / "," ("Can you look at...", "Well, if I get a little
                                 # bit,": 17 such turns in lumi.log 2026-10-21 / 22, none a whole sentence)
MERGE_WAIT_S = 1.5               # s waited for the rest of a cut-off sentence; it is heard with the first part

BEAM_SIZE = 0                    # whisper beam search width (0: the server's greedy decoding)
HEARD_DIR = ROOT / "logs" / "heard"   # the last HEARD_KEEP utterances as wav, to check what Lumi really heard
HEARD_KEEP = 50


def _infer(wav, prompt, language=None):
    """One whisper-server call: (text, language, language probability, average token log-probability)."""
    boundary = uuid.uuid4().hex
    fields = {"response_format": "verbose_json", "prompt": prompt, **({"language": language} if language else {}),
              **({"beam_size": BEAM_SIZE} if BEAM_SIZE else {})}
    body = "".join(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n"
                   for k, v in fields.items()).encode()
    body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"a.wav\"\r\n"
             f"Content-Type: audio/wav\r\n\r\n").encode() + wav + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(f"{STT_URL}/inference", body,
                                 {"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        out = json.loads(r.read())
    segs = out.get("segments") or []
    logprob = sum(s.get("avg_logprob", 0.0) for s in segs) / len(segs) if segs else 0.0
    lang = out.get("language") or out.get("detected_language")
    return out.get("text", "").strip(), lang, out.get("detected_language_probability"), logprob


def speech_seconds(audio):
    """Seconds of speech in int16 mono 16 kHz audio by Silero VAD (music, hum and knocks give ~0), or None when the
    model file is missing."""
    import numpy as np
    if "s" not in _vad:
        if not VAD_MODEL.exists():
            return None
        import onnxruntime
        opt = onnxruntime.SessionOptions()
        opt.intra_op_num_threads = 1
        _vad["s"] = onnxruntime.InferenceSession(str(VAD_MODEL), opt, providers=["CPUExecutionProvider"])
    x = audio.astype(np.float32) / 32768
    state, ctx, n = np.zeros((2, 1, 128), np.float32), np.zeros(64, np.float32), 0
    for i in range(0, len(x) - 511, 512):                # 32 ms frames, each with the 64 samples before it
        c = np.concatenate([ctx, x[i:i + 512]])
        p, state = _vad["s"].run(None, {"input": c[None], "state": state, "sr": np.array(RATE, np.int64)})
        ctx, n = c[-64:], n + (p[0, 0] > VAD_P)
    return n * 512 / RATE


def syllables(text):
    """Hangul syllables plus English vowel groups: how long the text takes to say, roughly."""
    return len(re.findall(r"[가-힣]", text)) + len(re.findall(r"[aeiouy]+", re.sub(r"[^a-z]", " ", text.lower())))


def names(text):
    """Whisper's slips (SLIPS, our names) -> as said; "Lumi야" -> 루미야."""
    text = re.sub(r"\blumi(?=[야아])", "루미", text, flags=re.I)
    for slip, said in SLIPS:
        text = re.sub(slip, said, text, flags=re.I)
    return text


def _letters(text):
    return re.sub(r"[^a-z가-힣]", "", text.lower())


def lumi_like(text):
    """A word that may be the name as whisper writes it without the prompt ("Louie", "Lumen", "Remia", "루미")."""
    if re.search(r"루미|루(?![가-힣])|ルミ|미야|민희|^\W*이미|\b[lr]e?mi|\bb?l[ou]{1,2}m|\bl[ou]{1,2}n(?:e?y|i|e)\b", text,
                 re.I):                                  # "안녕 민희야", "Bloomy", "Looney" (logs/heard 18:35:10)
        return True
    return any(difflib.SequenceMatcher(None, w, "lumi").ratio() >= 0.5 for w in re.findall(r"[a-z]+", text.lower()))


def not_english(text):
    """A word in English text that no dictionary has (our names, p-numbers and contractions aside)."""
    if not _words and WORDS_FILE.exists():
        _words.update(w.strip().lower() for w in WORDS_FILE.open() if w.strip().isalpha())
    words = [re.sub(r"'.*", "", w) for w in re.findall(r"[a-z']+", text.lower())]
    return bool(_words) and any(w and w not in _words and w not in OUR_WORDS and not re.fullmatch(r"p\d*", w)
                                for w in words)


def set_names(markers):
    """The map's marker names for whisper. Nothing: in the prompt they were no better (tests/asr_check.py, blind train
    set: +2 of 82 fake-map cases, -5 of 394 others, 4 more far wake words lost); kept for tests/blind_check.py."""


def _wav(audio):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(audio.tobytes())
    return buf.getvalue()


def transcribe(audio, prompt=None):
    """int16 mono 16 kHz -> text (empty string if nothing understood). Also fills last_stt.
    When whisper already heard this utterance up to a pause (early(), started mic.EARLY_QUIET_S into the quiet at its
    end) and nothing was said after it, that result is taken: the reply starts that much sooner."""
    ensure_stt_server()
    try:
        HEARD_DIR.mkdir(parents=True, exist_ok=True)
        (HEARD_DIR / time.strftime("%H%M%S.wav")).write_bytes(_wav(louder(audio)))
        for old in sorted(HEARD_DIR.glob("*.wav"), key=lambda p: p.stat().st_mtime)[:-HEARD_KEEP]:   # by time: names wrap at midnight
            old.unlink()
    except OSError:
        pass
    job = _early.get("job")
    out = None
    if prompt is None and job is not None and 0 <= len(audio) - len(job["audio"]) <= EARLY_REST * RATE and \
            np.array_equal(audio[:len(job["audio"])], job["audio"]):
        job["done"].wait(30)
        out = job.get("out")
    elif job is not None and _early.get("job") is job:
        _early.pop("job", None)                  # speech went on after that pause: a run not started is skipped
    text, stt = out or _hear(audio, prompt)
    last_stt.clear()
    last_stt.update(stt, early=out is not None)
    return text


def early(audio):
    """mic.py, in a pause of an utterance still going on: whisper starts on what was said so far, in the background
    (one run at a time: a newer one waits for the older)."""
    before = _early.get("job")
    job = {"audio": audio, "done": threading.Event()}

    def run():
        if before is not None:
            before["done"].wait(30)
        try:
            if _early.get("job") is job:             # not yet replaced by a newer pause or passed over by transcribe()
                job["out"] = _hear(audio, None)
        except Exception:                        # noqa: BLE001 - transcribe() asks again itself
            pass
        job["done"].set()
    _early["job"] = job
    threading.Thread(target=run, daemon=True).start()


mic.on_quiet = early


def _hear(audio, prompt):
    """int16 mono 16 kHz -> (text, what is known about it for last_stt); text "" if nothing understood.
    Whisper sometimes names another language (Japanese) for Korean said from afar and writes only the prompt's
    "Lumi." (2026-10-20: "컵 좀 주세요" came back as "Lumi." [japanese] four times): then it is asked again with
    Korean and with English fixed, and the surer of the two is kept."""
    ensure_stt_server()
    audio = louder(audio)
    wav = _wav(audio)
    speech = speech_seconds(audio)
    if speech is not None and speech < MIN_SPEECH_S:
        return "", dict(text="", dropped=f"no speech ({speech:.2f} s): music or noise")
    prompt = prompt or PROMPT
    text, lang, prob, logprob = _infer(wav, prompt)
    if names(text) != text and lang == "korean" and not re.search(r"[가-힣]", names(text)):
        lang = "english"                         # "호월달요." -> "How old are you?"
    text = names(text)
    asked = {}

    def ask(code):                               # transcribed with the language fixed, once per language
        if code not in asked:
            t2, _, _, lp2 = _infer(wav, LANG_PROMPT.get(code, prompt), code)
            asked[code] = (names(t2), {"en": "english", "ko": "korean"}[code], None, lp2)
        return asked[code]
    only_name = NAME_ONLY.fullmatch(text) and len(audio) > 1.5 * RATE
    # tagged Korean but written in Latin letters ("Wait.", "What is it?", "Can you sing song?" live 2026-10-21 / 22):
    # understood() refuses it. Asked in English: the same words again are English. (Asked in Korean too, far Korean
    # came back as other Korean words more often than right: tests/asr_check.py blind sets, 6 right of 37.)
    if lang == "korean" and re.search(r"[a-z]", text, re.I) and not re.search(r"[가-힣]", text) and \
            not NOT_SAID.search(text) and not only_name:
        t2 = ask("en")
        if difflib.SequenceMatcher(None, _letters(t2[0]), _letters(text)).ratio() >= SAME_WORDS:
            text, lang, prob, logprob = t2
    if lang not in LANGS or only_name:
        tries = [(text, lang, prob, logprob)] if lang in LANGS and not only_name else []
        tries += [ask("ko"), ask("en")]
        if lang not in LANGS:                    # forced on a sound whisper took for another language, Korean is
            tries = [r for r in tries if not STOCK.fullmatch(r[0])] or [("", lang, prob, logprob)]   # "감사합니다."
        more = [r for r in tries if not NAME_ONLY.fullmatch(r[0])]   # "Lumi, 이리 와" came back "Lumi." in English
        # forced to English, Korean speech comes back translated and sure of itself: Hangul gets KO_BONUS
        text, lang, prob, logprob = max(more if only_name and more else tries,
                                        key=lambda r: r[3] + (KO_BONUS if re.search(r"[가-힣]", r[0]) else 0.0))
    if lang == "english" and not_english(text):  # "Natarawa", "Lumi. Iriwa.": Korean written in Latin letters
        t2 = ask("ko")
        if re.search(r"[가-힣]", t2[0]) and t2[3] + ODD_KO_BONUS > logprob:
            text, lang, prob, logprob = t2
    if CALL_ONLY.fullmatch(text) and not lumi_like(_infer(wav, "")[0]):
        text = ""                                # the prompt's name written for a clap, a cough, "はい" (see CALL_ONLY)
    if lang == "english" and re.search(r"[가-힣]", text):
        lang = "korean"                          # "Red cup. 집어줘." tagged English: the Korean is real
    if text and NOT_SAID.search(text):
        return "", dict(text="", language=lang, dropped=f"{text!r}: whisper's subtitle text, nothing said")
    if REPEAT.search(text):
        return "", dict(text="", language=lang, dropped=f"{text!r}: whisper repeating itself")
    if speech is not None and speech < SPEECH_PER_SYLLABLE * syllables(text):
        return "", dict(text="", language=lang, dropped=f"{text!r} from {speech:.2f} s of speech: music or noise")
    stt = dict(text=text, language=lang, lang_prob=prob, logprob=round(logprob, 2), speech_s=speech)
    # whisper writes things like "[BLANK_AUDIO]" or "(music)" for non-speech
    return ("" if text.startswith(("[", "(", "*")) else text), stt


def understood(min_logprob=MIN_LOGPROB):
    """Was the last transcription clear English or Korean? (else Lumi asks the visitor to say it again)
    The text must also be written in that language: Whisper turns noise or Lumi's own Korean voice into
    English sentences tagged 'korean' ("I'll see you next time.", 2026-10-13)."""
    lang, text = last_stt.get("language"), last_stt.get("text", "")
    if lang not in LANGS or last_stt.get("logprob", 0.0) < min_logprob:
        return False
    return bool(re.search(r"[가-힣]", text)) == (lang == "korean")


def heard_clearly(min_logprob=MIN_LOGPROB):
    """English or Korean said clearly, whatever script whisper wrote it in ("Can you sing song?" came tagged
    'korean', 2026-10-21): lumi.py takes it only for its own fixed commands."""
    return last_stt.get("language") in LANGS and last_stt.get("logprob", 0.0) >= min_logprob


def heard_lang(default="en"):
    """'en' or 'ko': the language of the last transcription."""
    return LANGS.get(last_stt.get("language"), default)


def listen(wait_s=8.0, on_start=None, abort=None, full=False):
    """Record one utterance and transcribe it. Returns text or None (nobody spoke, or aborted).
    full=True: returns (text, mic.Utterance) instead, for the sound direction."""
    last_stt.pop("dropped", None)                # why the last sound was not taken (for the log), this call only
    u = record(wait_s, on_start, abort)
    if u is not None:
        last["peak"] = round(u.peak)
    if u is None or u.seconds < 0.4:
        return (None, u) if full else None
    text = transcribe(u.mono) or None
    if text and CUT_OFF.search(text):            # "Let's" ... "follow me": the rest after a pause, heard as one
        rest = record(MERGE_WAIT_S, abort=abort, since=u.t_end)
        if rest is not None and rest.seconds >= 0.3:
            import numpy as np
            joined = np.concatenate([u.mono, np.zeros(int(0.3 * RATE), np.int16), rest.mono])
            text2 = transcribe(joined)
            if text2:
                text, u.mono, u.t_end = text2, joined, rest.t_end
    return (text, u) if full else text


if __name__ == "__main__":
    ensure_stt_server()
    print("Say something (English or Korean)...")
    u = record(10, on_start=lambda: print("  (hearing you)"))
    if u is None:
        print("nothing heard")
    else:
        t = time.time()
        print(f"you said: {transcribe(u.mono)!r}   ({u.seconds:.1f} s audio, STT {time.time() - t:.2f} s)")
