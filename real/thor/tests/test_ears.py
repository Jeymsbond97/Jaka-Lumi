"""ears.transcribe() choices without whisper: a fake _infer answers per language.

    .venv/bin/python tests/test_ears.py
"""
import numpy as np

from audio import ears

ears.ensure_stt_server = lambda: None
ears.HEARD_DIR = ears.ROOT / "logs" / "asr_check" / "heard_test"
AUDIO = np.zeros(16000, np.int16)
real_speech_seconds = ears.speech_seconds
ears.speech_seconds = lambda audio: 1.0          # the cases below are speech; the detector is checked at the end


def fake(answers):
    """answers: {None | 'en' | 'ko': (text, lang, prob, logprob)}; records the languages asked."""
    asked = []

    def infer(wav, prompt, language=None):
        key = "no prompt" if not prompt and "no prompt" in answers else language
        asked.append(key)
        return answers[key]
    ears._infer = infer
    return asked


# Korean written in Latin letters ("Natarawa." is no English word): asked in Korean too, the Hangul one kept
asked = fake({None: ("Natarawa.", "english", 0.55, -0.4),
              "ko": ("나 따라와.", "korean", None, -0.5)})
assert ears.transcribe(AUDIO) == "나 따라와." and ears.heard_lang() == "ko" and asked == [None, "ko"], asked
# sure English in dictionary words: one call only
asked = fake({None: ("Go to p3.", "english", 0.97, -0.1)})
assert ears.transcribe(AUDIO) == "Go to p3." and asked == [None], asked
# Hangul in a text tagged English: Korean
asked = fake({None: ("Red cup. 집어줘.", "english", 0.6, -0.15)})
assert ears.transcribe(AUDIO) == "Red cup. 집어줘." and ears.heard_lang() == "ko" and asked == [None], asked
# whisper's spelling of the company
asked = fake({None: ("What does Kutchen make?", "english", 0.9, -0.2)})
assert ears.transcribe(AUDIO) == "What does Cutshion make?", ears.last_stt
# another language (Japanese) named: both asked
asked = fake({None: ("Lumi.", "japanese", 0.5, -0.01),       # Korean translated when forced to English
              "ko": ("컵 좀 주세요.", "korean", None, -0.3), "en": ("Give me a cup.", "english", None, -0.1)})
assert ears.transcribe(AUDIO) == "컵 좀 주세요." and asked == [None, "ko", "en"], asked
# only the name from 2 s of audio: asked in both, the one with more than the name kept although less sure
asked = fake({None: ("Lumi.", "english", 0.9, -0.05),
              "ko": ("Lumi야, 이리 와.", "korean", None, -0.4), "en": ("Lumi.", "english", None, -0.05)})
assert ears.transcribe(np.zeros(32000, np.int16)) == "루미야, 이리 와." and asked == [None, "ko", "en"], asked
# the prompt's name written for a clap: checked without the prompt, dropped
asked = fake({None: ("Lumi.", "english", 0.9, -0.05), "no prompt": ("*clap*", "english", 0.9, -0.3)})
assert ears.transcribe(AUDIO) == "" and asked == [None, "no prompt"], asked
# the name really said: kept
asked = fake({None: ("Hey Lumi.", "english", 0.9, -0.05), "no prompt": ("Hey, Liumu!", "english", 0.9, -0.8)})
assert ears.transcribe(AUDIO) == "Hey Lumi." and asked == [None, "no prompt"], asked
# tagged Korean but written in Latin letters (understood() would refuse it): asked in English, the same words kept
asked = fake({None: ("Wait.", "korean", 0.6, -0.01), "en": ("Wait.", "english", None, -0.02)})
assert ears.transcribe(AUDIO) == "Wait." and ears.understood() and asked == [None, "en"], asked
asked = fake({None: ("Tifa.", "korean", 0.5, -0.84), "en": ("To the bar.", "english", None, -0.5)})   # 뒤 봐, far
assert ears.transcribe(AUDIO) == "Tifa." and not ears.understood(), ears.last_stt   # other words: "say it again"
# a sound taken for Japanese, made Korean: whisper's "감사합니다." and "Hey." are dropped, not a turn or a wake word
asked = fake({None: ("Okay.", "japanese", 0.4, -0.03),
              "ko": ("감사합니다.", "korean", None, -0.15), "en": ("Hey.", "english", None, -0.09)})
assert ears.transcribe(AUDIO) == "", ears.last_stt
# whisper's loop on a sound it can't read: dropped
asked = fake({None: ("Look right. Look right. Look right.", "english", 0.6, -0.3)})
assert ears.transcribe(AUDIO) == "" and "repeating" in ears.last_stt["dropped"], ears.last_stt
# the owner's "How old are you?" written in Hangul: English
asked = fake({None: ("호월달요.", "korean", 0.6, -0.3)})
assert ears.transcribe(AUDIO) == "How old are you?" and ears.understood() and ears.heard_lang() == "en", ears.last_stt
# an early run (started in the pause at the end) is taken when only the quiet came after it, else asked again
fake({None: ("Look at the left side.", "english", 0.9, -0.05)})
speech = (np.sin(np.arange(16000) / 3) * 3000).astype(np.int16)
ears.early(speech)
ears._early["job"]["done"].wait(5)
asked = fake({None: ("Look at the.", "english", 0.9, -0.05)})
assert ears.transcribe(np.concatenate([speech, np.zeros(4800, np.int16)])) == "Look at the left side." and \
    asked == [] and ears.last_stt["early"], asked
assert ears.transcribe(np.concatenate([speech, np.zeros(4800, np.int16), speech])) == "Look at the." and \
    asked == [None], asked                       # more was said after the pause
asked = fake({None: ("Look at the.", "english", 0.9, -0.05)})
assert ears.transcribe(speech[:8000]) == "Look at the." and asked == [None], asked   # another utterance
ears._early.clear()
# the segmenter's pause signal: once, EARLY_QUIET_S into the quiet of an utterance still going on
from audio import mic
seg, fired = mic.Segmenter(100), []
for i in range(80):                                      # quiet, 0.6 s speech, 0.45 s pause, 0.15 s speech, quiet
    loud = 20 <= i < 40 or 55 <= i < 60
    if seg.feed(np.zeros(480, np.int16), 1000.0 if loud else 10.0, i * 0.03) is None and seg.quiet_now():
        fired.append(i)
assert fired == [49, 69] and not seg.in_speech, fired
# music or noise (no speech frames): whisper is not asked
ears.speech_seconds = lambda audio: 0.03
asked = fake({None: ("-끝-", "korean", 0.9, -0.01)})
assert ears.transcribe(AUDIO) == "" and asked == [] and "no speech" in ears.last_stt["dropped"], asked
# whisper's subtitle texts for music, with some speech frames: dropped
ears.speech_seconds = lambda audio: 0.4
for text in ["-끝.", "- 네.", "-", "...", "자막 제공 및 광고를 포함하고 있습니다.", "Thanks for watching!"]:
    fake({None: (text, "korean", 0.9, -0.01)})
    assert ears.transcribe(AUDIO) == "", text
fake({None: ("네.", "korean", 0.9, -0.1)})
assert ears.transcribe(AUDIO) == "네."
# more words than the speech held: "감사합니다." from 0.2 s of speech frames is music; from 0.4 s it was said
ears.speech_seconds = lambda audio: 0.2
fake({None: ("감사합니다.", "korean", 0.9, -0.01)})
assert ears.transcribe(AUDIO) == "" and "from 0.20 s" in ears.last_stt["dropped"]
ears.speech_seconds = lambda audio: 0.4
assert ears.transcribe(AUDIO) == "감사합니다."
# the detector itself: silence and piano-like music have no speech (the model file is local, models/)
# a sentence cut by a pause ("Let's" ... "follow me"): the rest is recorded and heard with the first part
import types
real_record, real_transcribe = ears.record, ears.transcribe
first = types.SimpleNamespace(mono=np.ones(8000, np.int16), t_end=10.0, peak=900.0, seconds=0.5)
rest = types.SimpleNamespace(mono=np.ones(12000, np.int16), t_end=11.5, peak=900.0, seconds=0.75)
calls = []
ears.record = lambda wait_s=8.0, on_start=None, abort=None, since=None: calls.append(since) or (first if since is None else rest)
ears.transcribe = lambda audio: "Let's" if len(audio) == 8000 else "Let's follow me."
assert ears.listen() == "Let's follow me." and calls == [None, 10.0], calls
for cut in ["What is the color of the...", "Well, if I get a little bit,", "You're the address of", "Can you find…"]:
    ears.transcribe = lambda audio, cut=cut: cut if len(audio) == 8000 else "x"
    calls.clear()
    first.mono, first.t_end = np.ones(8000, np.int16), 10.0   # listen() kept the joined audio in it
    assert ears.listen() == "x" and calls == [None, 10.0], cut
ears.transcribe = lambda audio: "Can you see me?"                 # a whole sentence: nothing waited for
calls.clear()
assert ears.listen() == "Can you see me?" and calls == [None], calls
ears.record = lambda wait_s=8.0, on_start=None, abort=None, since=None: first if since is None else None
ears.transcribe = lambda audio: "Let's"                           # nothing more said: the part as heard
assert ears.listen() == "Let's"
ears.record, ears.transcribe = real_record, real_transcribe

if real_speech_seconds(AUDIO) is not None:
    from tests.asr_cases4 import synth
    assert real_speech_seconds(AUDIO) == 0.0
    assert real_speech_seconds((synth(0, 3.0) * 8000).astype(np.int16)) < ears.MIN_SPEECH_S
print("ears ok")
