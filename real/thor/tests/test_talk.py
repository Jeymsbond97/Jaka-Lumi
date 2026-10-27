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
            ("emoji 얘기 좀 해 줘요", "Hey, 실례지만 처음 만든 해 언제인지 알려 주시겠습니까", ["emoji"]),
            ("", "tell me about mirrors", ["mirrors"]),
            ("", "아까 그 얘기 다시 해 줘", []),
            ("", "네 얘기 좀 해 봐", []),
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

    b = brain.Brain()                                  # back to an earlier topic: that turn's answer as a hint
    b.history = [("페트라가 뭐야?", "ACTION: none -\n요르단에 있는 바위를 깎아 만든 도시예요."),
                 ("물곰은 얼마나 작아?", "ACTION: none -\n0.5mm 정도예요."), ("그거 사실이야?", "ACTION: none -\n네.")]
    assert "요르단" in b._back_to("다시 페트라 얘기로 돌아가서, 뭐라고 했지?")
    assert "요르단" in b._fragment_hint("다시 페트라 얘기로 돌아가서, 뭐라고 했지?")
    assert b._back_to("물곰은 왜 안 죽어?") == ""
    b.history = [("Tell me about hydrogen", "ACTION: none -\nHydrogen is the most common element."),
                 ("What is salt for?", "ACTION: none -\nSeasoning."), ("ok", "ACTION: none -\nSure.")]
    assert "most common" in b._back_to("again about hydrogen, what did you say?")

    h = [("남극은 얼마나 추워?", "ACTION: none -\n영하 89도까지 내려가요."),     # "really?" after a refused order:
         ("춤 좀 춰 봐", "ACTION: none -\n저는 바퀴로 움직여서 춤은 못 춰요.")]   # the talk before it; "why not?": the refusal
    assert brain.topic_turn(h, "어이, 진짜?")[0] == "남극은 얼마나 추워?"
    assert brain.topic_turn(h, "저기 루미 왜 안 돼?")[0] == "춤 좀 춰 봐"
    assert brain.topic_turn(h)[0] == "춤 좀 춰 봐"

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
