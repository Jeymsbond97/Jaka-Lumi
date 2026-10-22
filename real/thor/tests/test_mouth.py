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
print(f"ok: {len(CUTS)} cuts, the prompt, the prefill")
