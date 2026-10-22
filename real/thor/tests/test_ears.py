"""ears.transcribe() choices without whisper: a fake _infer answers per language.

    .venv/bin/python tests/test_ears.py
"""
import numpy as np

from audio import ears

ears.ensure_stt_server = lambda: None
ears.HEARD_DIR = ears.ROOT / "logs" / "asr_check" / "heard_test"
AUDIO = np.zeros(16000, np.int16)


def fake(answers):
    """answers: {None | 'en' | 'ko': (text, lang, prob, logprob, probs)}; records the languages asked."""
    asked = []

    def infer(wav, prompt, language=None):
        asked.append(language)
        return answers[language]
    ears._infer = infer
    return asked


# Korean heard as English with Korean nearly as likely: asked in Korean too, the surer one kept
asked = fake({None: ("Iriwa.", "english", 0.55, -0.6, {"en": 0.55, "ko": 0.40}),
              "ko": ("이리 와.", "korean", None, -0.2, {})})
assert ears.transcribe(AUDIO) == "이리 와." and ears.heard_lang() == "ko" and asked == [None, "ko"], asked
# sure English: one call only
asked = fake({None: ("Go to p3.", "english", 0.97, -0.1, {"en": 0.97, "ko": 0.01})})
assert ears.transcribe(AUDIO) == "Go to p3." and asked == [None], asked
# the other language asked but less sure: the first kept
asked = fake({None: ("Come here.", "english", 0.6, -0.15, {"en": 0.6, "ko": 0.3}),
              "ko": ("컴히어.", "korean", None, -0.7, {})})
assert ears.transcribe(AUDIO) == "Come here." and ears.heard_lang() == "en" and asked == [None, "ko"], asked
# another language (Japanese) named: both asked
asked = fake({None: ("Lumi.", "japanese", 0.5, -0.01, {"ja": 0.5}),
              "ko": ("컵 좀 주세요.", "korean", None, -0.3, {}), "en": ("Cup.", "english", None, -0.9, {})})
assert ears.transcribe(AUDIO) == "컵 좀 주세요." and asked == [None, "ko", "en"], asked
# only the name from 2 s of audio: asked in both, the one with more than the name kept although less sure
asked = fake({None: ("Lumi.", "english", 0.9, -0.05, {"en": 0.9, "ko": 0.05}),
              "ko": ("Lumi야, 이리 와.", "korean", None, -0.4, {}), "en": ("Lumi.", "english", None, -0.05, {})})
assert ears.transcribe(np.zeros(32000, np.int16)) == "루미야, 이리 와." and asked == [None, "ko", "en"], asked
print("ears ok")
