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
if real_speech_seconds(AUDIO) is not None:
    from tests.asr_cases4 import synth
    assert real_speech_seconds(AUDIO) == 0.0
    assert real_speech_seconds((synth(0, 3.0) * 8000).astype(np.int16)) < ears.MIN_SPEECH_S
print("ears ok")
