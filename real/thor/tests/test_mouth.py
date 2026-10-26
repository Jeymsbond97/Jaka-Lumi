"""Self-check of how speech and the LLM prompt are cut for a fast first word, no audio, no LLM.

    python tests/test_mouth.py
"""
from assistant import llm_direct
from audio import mouth

CUTS = [("I am 146 cm tall, but I can raise my upper body up to 186 cm.",
         ["I am 146 cm tall,", "but I can raise my upper body up to 186 cm."]),
        ("Yes, I can see you about 80 centimetres away.", None),          # comma too early
        ("Oh no, you look sad.", None),                                   # short
        ("It costs about 1,330 won today and a bit more tomorrow.", None),  # a number's comma
        ("오늘은 날씨가 맑고 따뜻해요, 그래서 산책하기 좋은 날이에요 정말로요.",
         ["오늘은 날씨가 맑고 따뜻해요,", "그래서 산책하기 좋은 날이에요 정말로요."])]

for text, want in CUTS:
    got = mouth.first_parts(text)
    assert got == (want or [text]), (text, got)

# Ollama's gemma4 prompt, as checked token for token against Ollama on 2026-10-21
assert llm_direct.render([{"role": "system", "content": "S"}, {"role": "user", "content": "Q"},
                          {"role": "assistant", "content": "A"}, {"role": "user", "content": "Q2"}]) == \
    ("<|turn>system\nS<turn|>\n<|turn>user\nQ<turn|>\n<|turn>model\nA<turn|>\n<|turn>user\nQ2<turn|>\n"
     "<|turn>model\n<|channel>thought\n<channel|>")
# a prefill (system + turns) is the start of the next prompt, so the runner's cache holds it
start = [{"role": "system", "content": "S"}, {"role": "user", "content": "Q"}, {"role": "assistant", "content": "A"}]
assert llm_direct.render(start + [{"role": "user", "content": "Q2"}]).startswith(llm_direct.render(start, reply=False))

# Lumi's own voice in the clip mic (mouth.echo): what the speaker played 0.4 s earlier, quieter, with noise -> high; a
# visitor's sound over it -> low; a sound after Lumi stopped -> no judgement. Speech-like test sounds: noise with a
# syllable-rate envelope in each of four bands (tests/echo_check.py uses real TTS)
import numpy as np                                                       # noqa: E402
rng = np.random.default_rng(0)


def voice(seconds):
    n = int(seconds * 16000)
    out = np.zeros(n, np.float32)
    for lo, hi in [(200, 600), (600, 1200), (1200, 2400), (2400, 4000)]:
        spec = np.fft.rfft(rng.standard_normal(n))
        f = np.fft.rfftfreq(n, 1 / 16000)
        spec[(f < lo) | (f > hi)] = 0
        env = np.repeat(rng.uniform(0, 1, n // 1600 + 1) ** 2, 1600)[:n]   # a new level every 0.1 s
        out += np.fft.irfft(spec, n).astype(np.float32) * env
    return out / np.abs(out).max() * 0.5


played, other = voice(3.0), voice(2.0)
mouth._played.clear()
mouth._played.append([100.0, 103.0, played])                             # played from t = 100 s to 103 s
heard = played[8000:40000] * 0.3 + rng.standard_normal(32000).astype(np.float32) * 0.005   # 0.5-2.5 s of it, 0.4 s late
assert mouth.echo((heard * 32767).astype(np.int16), 102.9) >= mouth.ECHO_MIN
visitor = other * 0.5 + played[8000:40000] * 0.05                       # a visitor close to the mic, Lumi 20 dB lower
assert mouth.echo((visitor * 32767).astype(np.int16), 102.9) < mouth.ECHO_MIN
assert mouth.echo((heard * 32767).astype(np.int16), 106.0) is None       # said 1 s after Lumi stopped

# one voice: every sentence (English, Korean, short, long) is synthesised with the same style, steps and speed, and
# starts from the same noise, so the same sentence always sounds the same and sentences don't change pitch
calls = []


class FakeTTS:
    def synthesize(self, text, **kw):
        calls.append(kw)
        return np.zeros((1, 10), np.float32), None


mouth._tts, mouth._style = FakeTTS(), object()
for s in ["Hello.", "I can talk with you in English and Korean, answer questions, and guide you.", "네, 갈게요.",
          "오늘은 날씨가 맑고 따뜻해요, 그래서 산책하기 좋은 날이에요."]:
    mouth._synth(s, mouth.lang_of(s))
assert all({k: v for k, v in c.items() if k != "lang"} == {k: v for k, v in calls[0].items() if k != "lang"}
           for c in calls), calls
assert all(c["voice_style"] is mouth._style for c in calls)


class FakeModel:
    ldim, chunk_compress_factor, base_chunk_size, sample_rate = 4, 2, 512, 44100


m = FakeModel()
mouth._fixed_noise(m)
a, _ = m.sample_noisy_latent(np.array([1.0]))
b, _ = m.sample_noisy_latent(np.array([1.0]))
c, _ = m.sample_noisy_latent(np.array([2.5]))
assert np.array_equal(a, b) and np.array_equal(a, c[:, :, :a.shape[2]])   # same noise, a longer one goes on from it
print(f"ok: {len(CUTS)} cuts, the prompt, the prefill, own voice, one voice")
