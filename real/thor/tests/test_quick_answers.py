"""Self-check of the quick answers (assistant/quick_answers.py): python tests/test_quick_answers.py

Needs the embedding server (assistant/knowledge.embed starts it); nothing moves. Standalone questions get their kind,
in other words than the bank's too; follow-ups, camera questions, commands and company facts never do."""
import re

from assistant import quick_answers as qa

TALK = [("what does cutshion make?", "Cutshion makes robot applications, such as barista and cooking robots.")]

KIND = {   # words (no talk before) -> kind
    "how many employees does Cutshion have?": "co_unknown", "직원이 몇 명이에요?": "co_unknown",
    "how old is Cutshion?": "co_founded", "대표가 누구예요?": "co_ceo",                  # company kinds: bank_words/company.py
    "who made you?": "maker", "Lumi, who built you?": "maker", "누가 만들었어요?": "maker", "어느 회사 로봇이에요?": "maker",
    "what's your name?": "name", "이름이 뭐예요?": "name", "니 이름 머야": "name",
    "how old are you?": "age", "몇 살이에요?": "age", "너 몇 살이야?": "age",
    "who are you?": "who", "넌 누구니?": "who", "introduce yourself please": "who",
    "how tall are you?": "height", "키가 몇이에요?": "height",
    "how long does your battery last?": "battery_life", "배터리 몇 시간 가요?": "battery_life",
    "what languages do you speak?": "languages", "영어 할 줄 알아?": "languages",
    "are you chatgpt?": "chatgpt", "너 챗GPT 써?": "chatgpt", "무슨 AI 써요?": "model",
    "are you a robot?": "robot", "감정 있어요?": "robot",
    "hello": "hello", "안녕하세요": "hello", "hi lumi": "hello",
    "how much do you weigh?": "weight", "how fast can you go?": "speed",
    "what time is it?": "time_now", "지금 몇 시야?": "time_now", "오늘 며칠이에요?": "date_today",
    "what day is it today?": "date_today", "오늘 무슨 요일이야?": "date_today",
    "are you a Korean robot?": "country", "어느 나라 로봇이에요?": "country", "what computer do you use?": "computer",
    "관절이 몇 개예요?": "dof", "음성 인식 뭐 써요?": "stt", "how fast do you answer?": "reply_time",
    "where are you used?": "used_where", "인터넷 써요?": "internet",
    # openers, asides, remarks, connectives, stutters, run-together words (night 5)
    "hello robot, you name is?": "name", "루미 님, 배터리 수명 얼마나 됩니까?": "battery_life", "누미야 너 몇 살이야": "age",
    "실례합니다. 몇 살입니까?": "age", "하나 여쭤봐도 될까요? 너 이름 어떻게 되세요?": "name", "너 살아 있어? ㅎㅎ": "robot",
    "Christmas 얼마나 남았어요? 알고 싶어요.": "days_to_christmas", "얘 몇 살일까? 너 몇 살이야?": "age",
    "형 비켜 봐, 키가 몇이에요?": "height", "My new friend Lumi, how heavy are you?": "weight", "아 그리고 몇 개 국어 해?": "languages",
    "그러면 키가 몇이에요?": "height", "키가 얼— 얼마예요?": "height", "너 너 몇 살이야": "age", "이보게 루미, 지금 몇 시인가?": "time_now",
    "누가너를만들었습니까?": "maker", "루미군,오늘무슨요일인가?": "date_today", "키가 얼마인지 알려 주시겠어요?": "height",
    "You're Siri, aren't you?": "name", "너 2미터지?": "height", "Samsung made you, right?": "maker", "이번 달 알려 줘.": "date_today",
    "에이지가 몇이야?": "age", "스피드가 얼마야?": "speed", "메이커가 어디야?": "maker", "do you have the time?": "time_now",
    "아이들 옆에 있어도 안전해?": "safety", "what cameras do you have?": "cameras", "얼굴 인식 돼요?": "faces",
    "컴퍼니 오픈 언제예요?": "co_founded", "참, 로봇 양반, 이름이 무슨 뜻이야?": "name_meaning", "Your voice, what program?": "tts", "들어 있는 인공지능 무엇인지 알려 주십시오": "model",
    "실례합니다. 네 이름 무엇인지 알려 주십시오": "name", "바퀴 몇 개야?": "wheels", "do you have eyes?": "cameras",
    "스피커 어디 있어요?": "tts", "배터리 타임 얼마나 돼요?": "battery_life", "랭귀지 뭐 할 수 있어?": "languages",
    "Is it safe to stand next to you?": "safety", "Is it safe for kids to be near you?": "safety",
}
IN_TALK = {   # words after TALK -> kind or None
    "how old are you?": "age", "who made you?": "maker", "what's your name?": "name",
    "how old?": None, "몇 살이에요?": None, "hello": None, "why?": None, "really?": None, "and you?": None,
    "who runs it?": None, "how many people work there?": None, "진짜?": None, "왜요?": None, "너는?": None, "무겁습니까?": None, "어떤 로봇이요?": None,
    "그럼 몇 살이에요?": None, "and how old?": None, "근데 너 몇 살이야?": "age",
}
NEVER = [   # no talk before: never a quick answer
    "can you see me?", "what am I holding?", "what colour is my shirt?", "how old do I look?", "how tall am I?",
    "나 보여?", "내 옷 무슨 색이야?", "카메라로 뭐 보여요?",
    "come here", "follow me", "wave at me", "sing a song", "이리 와", "손 흔들어 줘", "노래 불러 줘",
    "how much do you cost?", "가격이 얼마예요?",
    "how long does charging take?", "충전 얼마나 걸려요?", "who is the CEO?",
    "what's the weather?", "what time does the show start?", "몇 시에 끝나요?", "thanks", "고마워요", "okay", "bye",
    "goodbye", "May I ask you something?",
    "what's your name and how old are you?", "who made you? and why?", "how much can you lift?",
    "what can you do?", "how much battery is left?", "who made your arm?", "너 얼마야?", "얼마나 무거운 거 들 수 있어?",
    "로봇 미국 회사 맞아요?",
    "when is your birthday?", "생일이 언제예요?", "완충까지 몇 시간이에요?", "how slow can you drive?", "what are you doing?",
    "너 자카 로봇이야?", "can you hear me?", "키 줄여 줘", "Price of the ice cream robot?",
    # night 5: other things' facts, commands among sentences or before a comma, fragments
    "몇씨야? 아니 몇 살로 보여?", "Is it Samsung? Who made you?", "What's your name? Where's the toilet?", "fold it fold it! your arm!",
    "손! 손 내밀어!", "go the souvenir shop, ehh, tell me time", "Turn your head toward me, young robot.", "배터리, 아 아니, 지금 뭐 해?",
    "오픈AI 대표 누군가?", "1달러에 원화로 얼만가?", "롯데타워 하이트 얼마야?", "K1 정밀도 어때요?", "PEITIAN 로봇의 가반하중은 얼마입니까?",
    "배터리 수명이 몇 년이에요?", "배터리 얼만가?", "do you have time?", "언제?", "How do you know?",
    "위험해", "손에 뭐 있어?", "what can your camera see?", "do you recognize me?", "저기 평가 항목, 루미, 오늘 무슨 요일이야?", "홀로 가십시오", "근데 너 몇 살이야? 아 됐고, 검정 머그컵 잡으시지요",
    "Lumi, could you turn your head ten degrees down?", "이 로봇 마 저한테 손 쫌 주실래요? 알겄제", "내일 며칠이야?", "오늘 미세먼지 어때?",
    "충전하는 데 얼마나 걸려?", "이거 몇 살짜리 장난감이야?",
]
FACT = {"chatgpt": r"\bno\b|아니", "name": r"lumi|루미", "who": r"lumi|루미", "age": r"\b2\b|two|두 살", "maker": r"cutshion|쿳션",
        "height": r"146", "battery_life": r"10", "languages": r"english|영어", "model": r"gemma|젬마",
        "robot": r"robot|로봇", "weight": r"96", "speed": r"0\.6"}


class _ToLLM(Exception):
    pass


def through_answer():
    """lumi.Lumi.answer(): the quick answer is said and kept in the talk; "why?" next goes to the LLM."""
    import types
    from assistant import lumi
    from audio import mouth
    from tasks import fetch
    said = []
    lumi.LOG_FILE = "/dev/null"
    mouth.say = lambda text, lang=None, abort=None: said.append(text)
    lumi.ears.understood = lambda *a: True
    lumi.ears.last_stt = {"language": "english", "logprob": -0.1}
    fetch.check_hand = lambda: False
    L = lumi.Lumi.__new__(lumi.Lumi)
    L.lang, L.current, L.closing_pending, L.markers = "en", None, None, ["home", "stage"]

    def llm(*a, **k):
        raise _ToLLM()
    L.brain = types.SimpleNamespace(history=[], topic=llm, is_lookup_follow_up=lambda t: False)
    for name in ("follow_stop", "drive_words", "fetch_voice", "quick_command"):
        setattr(L, name, lambda *a: False)
    L.voice_setting = lambda text, last: False
    L.mission_running = L.chain_busy = lambda: False
    L.fetch_status = lambda: None
    L.keep_listening = lambda: None
    L.speak_abort = lambda: False
    bad = 0
    L.answer("who made you?")
    if not said or not re.search(r"cutshion", said[-1], re.I) or L.brain.history[-1][0] != "who made you?":
        bad += 1
        print(f"FAIL through answer: {said} {L.brain.history}")
    try:
        L.answer("why?")
        bad += 1
        print("FAIL: why? after a quick answer did not go to the LLM")
    except _ToLLM:
        pass
    return bad


def main():
    bad = 0
    for words, want in KIND.items():
        got = qa.kind_of(words)
        if got != want:
            bad += 1
            print(f"FAIL kind {words!r}: {got} (want {want})")
    for words, want in IN_TALK.items():
        got = qa.kind_of(words, TALK)
        if got != want:
            bad += 1
            print(f"FAIL in talk {words!r}: {got} (want {want})")
    for words in NEVER:
        got = qa.kind_of(words)
        if got:
            bad += 1
            print(f"FAIL never {words!r}: {got}")
    for kind, (_, lines) in qa.KINDS.items():           # every answer says its fact; Korean polite, the right name
        for lang, says in lines.items():
            for s in says:
                if kind in FACT and not re.search(FACT[kind], s, re.I) or lang == "ko" and \
                        (not re.search(r"(?:요|다)[.!?]?$", s) or re.search(r"컷션|커션", s)):
                    bad += 1
                    print(f"FAIL answer {kind}/{lang}: {s}")
    a, b = qa.answer("how old are you?", "en"), qa.answer("how old are you?", "en")
    if not a or a == b:
        bad += 1
        print(f"FAIL variety: {a!r} then {b!r}")
    if not re.search(r"[가-힣]", qa.answer("몇 살이에요?", "ko") or ""):
        bad += 1
        print("FAIL Korean answer")
    bad += through_answer()
    print("quick answers:", "all passed" if not bad else f"{bad} failed")
    return bad


if __name__ == "__main__":
    raise SystemExit(1 if main() else 0)
