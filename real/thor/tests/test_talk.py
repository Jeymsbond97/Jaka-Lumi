"""Self-check of the talk prompt (T1), no LLM, no embeddings: the model and the note search are faked.
- The date and time the model is given come from the clock (web.now_text), never from the model: every LLM path that
  can be asked the time puts "Now it is ..." with today's date in its prompt: respond_stream (talk), respond_from (a
  lookup's answer).
- The subject of a world question (Brain.world_talk): an adverb with 는 is none ("공식적으로는"), "X 그거" names X,
  "X는 뭐예요?" is X alone; world questions are shown world-knowledge examples only.

    python tests/test_talk.py
"""
import time

from assistant import brain, knowledge, memory, talk_examples, web

FAKE_NOW = "Friday, 13 March 2026, 10:05"      # a date the model could never have guessed
sent = []


def fake_stream(messages):
    sent.append(messages)
    return iter(["ACTION: none -\nIt is 10:05 am.\n"])


brain._stream = fake_stream
knowledge.search = lambda text, k=4: []
talk_examples.pick = lambda *a, **kw: []
memory.turn_lines = lambda b, text: ""
web.now_text = lambda: FAKE_NOW


def last_message():
    return sent[-1][-1]["content"]


def main():
    line = brain.now_line()
    assert line.startswith(FAKE_NOW), line
    assert time.strftime("%Y년 %-m월 %-d일") in line and ("오전" in line or "오후" in line), line         # the Korean form, from the same clock

    for q in ("What is the time?", "What's the date today?", "지금 몇 시예요?", "오늘 며칠이야?", "지금 몇..."):
        b = brain.Brain()
        list(b.respond_stream(q, ["home"], now="I'm not doing any task right now."))
        assert f"Now it is {FAKE_NOW}" in last_message(), (q, last_message())
        assert FAKE_NOW not in sent[-1][0]["content"], "the time must stay out of the cached system prompt"

    b = brain.Brain()
    list(b.respond_from("What day is it in New York?", "New York: Thursday evening."))
    assert f"Now it is {FAKE_NOW}" in last_message(), last_message()

    for before, q, want in [
            ("저기 2월 29일에 태어나면 생일은 어떻게 해요?", "공식적으로는 언제로 쳐요?", ["생일"]),
            ("공식적으로는 언제로 쳐요?", "윤초는 뭐예요?", ["윤초"]),
            ("생일은 어떻게 해요?", "윤초는 뭐예요?", ["윤초"]),
            ("경복궁 그거 언제 지었노?", "이름은 와 그래 지었노?", ["경복궁"]),
            ("", "부엉이 그거 목 을매나 돌아가노?", ["부엉이"]),
            ("", "너 그거 할 수 있어?", []),
            ("", "루미 그거 뭐야?", []),
            ("", "블루투스 이름은 왜 그렇게 지었나?", ["블루투스"]),
            ("", "에펠탑의 높이는 얼마예요?", ["에펠탑"]),
            ("", "너 이름은 뭐야?", []),
            ("", "루미 이름은 누가 지었어?", []),
            ("문어는 피가 무슨 색이야?", "심장은 몇 개고?", ["문어", "심장"])]:
        b = brain.Brain()
        b.history = [(before, "ACTION: none -\n네.")] if before else []
        assert b.world_talk(q) == want, (before, q, b.world_talk(q))

    b = brain.Brain()                                  # a lookup in the checks / live: its follow-ups are looked up,
    b.history, b.last_lookup = [("공식적으로는 언제로 쳐요?", "")], "공식적으로는 언제로 쳐요?"   # a new subject is not
    none = {"action": "none", "target": ""}
    assert b._after(none, "윤초는 뭐예요?") == none
    assert b._after(none, "몇 살이야?")["action"] == "search"
    assert b._after(none, "그게 뭐예요?")["action"] == "search"

    picked = []
    talk_examples.pick = lambda said, lang, k=4, bank=None: picked.append(bank) or []
    brain._examples("윤초는 뭐예요?", world=True)
    assert picked[-1] and all(e[0] in brain.WORLD_EXAMPLES for e in picked[-1]), "world: world examples only"
    brain._examples("이름이 뭐예요?")
    assert any(e[0] == "name" for e in picked[-1])
    import io
    import json
    from assistant import llm_direct                    # the model's own empty thought block is never said
    def sse(pieces):
        return io.BytesIO(b"".join(b"data: " + json.dumps({"content": p}).encode() + b"\n" for p in pieces))
    assert list(llm_direct._pieces(sse(["<|channel>", "thought", "\n", "<channel|>", "No, ", "she didn't."]))) == \
        ["No, ", "she didn't."]
    assert list(llm_direct._pieces(sse(["<|channel>thought\n<channel|>Yes."]))) == ["Yes."]
    assert list(llm_direct._pieces(sse(["ACTION: none -\n", "Hi."]))) == ["ACTION: none -\n", "Hi."]
    print("talk: ok")


if __name__ == "__main__":
    main()
