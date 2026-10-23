"""Voice path check without a microphone: each command is spoken by Lumi's own TTS, heard by the whisper server
(the one the robot uses), and read as Lumi reads what it hears. The reading of the heard text must be the reading
of the typed text. Needs the whisper server (started by the API); nothing moves.

    .venv/bin/python tests/voice_check.py            # all mission cases, English and Korean
    .venv/bin/python tests/voice_check.py 50         # the first 50 only
    .venv/bin/python tests/voice_check.py failed     # only the ones in logs/voice_check.log
    .venv/bin/python tests/voice_check.py --port 8099   # a whisper-server of one's own (not the robot's)
    .venv/bin/python tests/voice_check.py --tag after   # failures to logs/voice_check_after.log
Units are spoken as words ("1 m" -> "1 meter"), as people say them; in Korean also the markers and numbers
("p3로" -> "피쓰리로" or "피삼으로", "1미터" -> "일 미터": the TTS reads "p3" and "1" in Korean badly); the words of a message may be spelled
differently by whisper ("canceled"), only that a message is there counts. Failures go to logs/voice_check.log."""
import re
import sys
import time
import zlib
from pathlib import Path

import numpy as np

from assistant import steps
from audio import ears, mouth
from tests.steps_cases import CASES as C1
from tests.steps_cases2 import CASES as C2
from tests.steps_cases5 import CASES as C5

ROOT = Path(__file__).resolve().parents[1]
M = ["home", "PInit", "Wp", "a", "b", "dock2", "exit", "final"] + [f"p{i}" for i in range(1, 11)]
PROMPT = None                # a whisper prompt to try instead of ears.PROMPT (VOICE_PROMPT=... in the environment)


KO_EN = ["", "원", "투", "쓰리", "포", "파이브", "식스", "세븐", "에잇", "나인", "텐"]
KO_SINO = ["영", "일", "이", "삼", "사", "오", "육", "칠", "팔", "구", "십"]


def spoken(text):
    """How a person says the command: units as words; in Korean markers and numbers in Hangul, the way people say
    them (English or Korean digits, chosen by the text, so both are heard)."""
    t = re.sub(r"(\d)\s*cm\b", r"\1 centimeters", text)
    t = re.sub(r"(\d)\s*m\b", lambda m: m.group(1) + (" meter" if m.group(1) == "1" else " meters"), t)
    t = re.sub(r"(\d)\s*m(?=[가-힣\s]|$)", r"\1미터 ", t)
    if not re.search(r"[가-힣]", t):
        return t
    en = zlib.crc32(text.encode()) % 2
    t = re.sub(r"(?<![a-z])[pP](10|[1-9])(?!\d)", lambda m: "피" + (KO_EN if en else KO_SINO)[int(m.group(1))], t)
    t = re.sub(r"dock2", "도크 투", t)
    t = re.sub(r"(\d+)\.(\d)\s*(?=미터|센티)", lambda m: f"{KO_SINO[int(m.group(1))]} 점 {KO_SINO[int(m.group(2))]} ", t)
    return re.sub(r"(?<![\d.])([1-9])\s*(?=미터|도\b)", lambda m: KO_SINO[int(m.group(1))] + " ", t)


def loose(reading):
    """A reading with the words of messages left out (whisper may spell them differently)."""
    steps_, unread = reading
    return [dict(s, text="…") if s["do"] == "say" else s for s in steps_], unread


def heard(text):
    """What whisper hears when Lumi's voice says `text`: (transcript, understood)."""
    tts = mouth._load()
    wav = mouth._synth(spoken(text), mouth.lang_of(text))
    rate = tts.sample_rate
    n = int(len(wav) * ears.RATE / rate)                       # resample to the microphone's 16 kHz
    pcm = np.interp(np.linspace(0, len(wav) - 1, n), np.arange(len(wav)), wav)
    pcm = (np.clip(pcm, -1, 1) * 32767).astype(np.int16)
    return ears.transcribe(pcm, **({"prompt": PROMPT} if PROMPT else {})), ears.understood()


LOG = ROOT / "logs" / "voice_check.log"


def main(limit=None):
    cases = [t for t, want in {**C1, **C2, **C5}.items() if want != "?"][:limit if isinstance(limit, int) else None]
    if limit == "failed":
        cases = [ln[1:-1] for ln in LOG.read_text().splitlines() if ln.startswith("'")]
    bad, t0 = [], time.time()
    for i, text in enumerate(cases, 1):
        typed = steps.read(text, M, llm=False)[:2]
        said, ok = heard(text)
        got = steps.read(said, M, llm=False)[:2]
        if loose(got) != loose(typed) or not ok:
            bad.append(f"{text!r}\n  heard {said!r} (understood {ok})\n  typed {typed}\n  heard {got}")
        if i % 25 == 0:
            print(f"{i}/{len(cases)}  wrong {len(bad)}  {time.time() - t0:.0f} s", flush=True)
    LOG.write_text("\n".join(bad) + "\n")
    print(f"{len(cases) - len(bad)}/{len(cases)} heard and read the same; failures in {LOG.relative_to(ROOT)}")


if __name__ == "__main__":
    import os
    PROMPT = os.environ.get("VOICE_PROMPT") or None
    if "--port" in sys.argv:
        ears.STT_URL = f"http://127.0.0.1:{sys.argv.pop(sys.argv.index('--port') + 1)}"
        ears.HEARD_DIR = ROOT / "logs" / "asr_check" / "heard"   # never the robot's logs/heard
        sys.argv.remove("--port")
    if "--tag" in sys.argv:
        LOG = ROOT / "logs" / f"voice_check_{sys.argv.pop(sys.argv.index('--tag') + 1)}.log"
        sys.argv.remove("--tag")
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    main(int(arg) if arg and arg.isdigit() else arg)
