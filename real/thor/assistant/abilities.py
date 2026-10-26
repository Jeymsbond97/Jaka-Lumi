""""What can you do?" / "뭐 할 수 있어?": a fixed short overview of what Lumi can do, the rest on "tell me more".

The language model left out half of it (2026-10-21: "I can chat, tell the time and weather, drive to places on my
map, and pick up and bring cups"), so these words are answered here. Keep the lines in step with
knowledge/lumi_about_en.md "What I can do now" and brain.SYSTEM "What you can do".

    python assistant/abilities.py "what can you do?"
"""
import re
import sys

ASKED = re.compile(r"\bwhat (?:else |all |things |kinds? of things )?(?:can|could) (?:you|u) do\b(?!\s+(?:with|about|if|when|to|for (?:it|that)))|"
                   r"\b(?:you|u) can do what\b(?!\s+(?:you|i|we|he|she|they|it|ever)\b)|\bwhat (?:you|u) can do(?:ing)?\b|\b(?:skills?|functions?|abilities)\s*(?:뭐|뭔|머|있|이써)|"
                   r"(?:스킬|펑션|평션)\S*\s*(?:뭐|뭔|머|있|이써|알려)|"
                   r"\bwhat (?:are|r) (?:all )?your (?:abilities|skills|capabilities|functions|features|talents)\b|"
                   r"\bwhat are you (?:able to do|capable of|good at)\b|\bwhat do you do\b(?!\s+(?:with|when|if|for fun))|"
                   r"\bwhat can you help (?:me |us )?with\b|\btell me (?:about )?(?:what you can do|your (?:abilities|skills))\b|"
                   r"\b(?:list|show me) (?:your|what you can) (?:abilities|skills|do)\b|^\W*(?:your )?(?:abilities|skills)\W*$|"
                   r"\bwhat can (?:i|we) (?:ask|get|have) you (?:to )?do\b|\bwhat (?:are your|is your) (?:special )?(?:talents?|specialty|speciality)\b|"
                   r"(?<![가-힣]로 )(?<![가-힣]으로 )(?:뭐|뭘|머|멀|무엇|무엇을|뭐를)\s*(?:또\s*)?할\s*(?:수|줄)\s*(?:있|알|아|이써|이싸)|"
                   r"(?:뭐|뭘|무엇을?)\s*시킬\s*수|특기가?\s*(?:뭐|뭔|있)|무슨\s*function|"
                   r"무슨\s*일을?\s*(?:해|하|할)|어떤\s*(?:일|것|거|걸)을?\s*(?:할\s*수|해|하)|할\s*(?:수\s*있는|줄\s*아는)\s*(?:게|것|거|일)|"
                   r"뭐\s*하는\s*로봇|무슨\s*기능|어떤\s*기능|기능\S*\s*(?:뭐|뭔|있|알려|무엇|머)|(?:능력|기능)\S*\s*(?:뭐|뭔|알려|소개|무엇)", re.I)
MORE = re.compile(r"^\W*(?:(?:yes|yeah|yep|sure|ok|okay|please|lumi|and)\W*)*(?:tell me more|more|go on|what else|and\?|"
                  r"and what else|anything else|details?|yes|yeah|yep|sure|ok|okay|please)(?:\W+(?:please|lumi))*\W*$|"
                  r"\bwhat else can you do\b|\btell me (?:more|everything|the rest)\b|"
                  r"^\W*(?:네|예|응|어|그래요?|좋아요?|좋아)?\W*(?:더|자세히|전부|다)?\s*(?:알려|말해|얘기해|들려)\s*(?:줘|주세요|줄래요?|봐)?\W*$|"
                  r"^\W*(?:네|예|응|그래요?|좋아요?|좋아|그리고요?|또요?|또\s*뭐\S*|그\s*외에는?\S*|더\s*있어요?|더요)\W*$|또\s*뭐\s*할\s*수", re.I)

SHORT_MARK = "ACTION: none abilities"   # the history line of the short overview (lumi.fixed_answer)
SHORT = {"en": "I'm a robot assistant: I can talk with you and answer your questions, also from the internet, and I can look at what's "
               "around me and understand it. I can pick things up and bring them to you, go to places, follow you, "
               "wave and even sing. Shall I tell you more?",
         "ko": "저는 로봇 어시스턴트라서 대화하면서 궁금한 걸 답해 드리고, 인터넷에서 찾아볼 수도 있어요. 주변을 보고 무엇이 있는지 이해할 수 있고, "
               "물건을 집어서 가져다드리거나, 여러 곳에 가고, 따라가고, 손을 흔들고 노래도 불러요. 더 알려 드릴까요?"}
LONG = {"en": "I talk with you in English and Korean, and when I don't know something I look it up on the internet. "
              "I can look at what's around me and understand it: objects, people, what you're wearing or holding. "
              "I can pick things up, bring them to you or take them somewhere else and put them down, or take "
              "something from your hand. I go to the places on my map, move or turn as far and as fast as you say, "
              "and follow you when you say \"follow me\". And I like to wave and sing my songs, like Fantastic Baby "
              "or Love Attack.",
        "ko": "영어와 한국어로 대화하고, 모르는 건 인터넷에서 찾아봐요. 주변을 보고 무엇이 있는지 이해할 수 있어요. 물건이나 "
              "사람, 입고 계신 옷이나 손에 든 것도요. 물건을 집어서 가져다드리거나 다른 곳에 옮겨 내려놓고, 손에 든 걸 받아 "
              "드릴 수도 있어요. 지도에 있는 장소로 가고, 말씀하시는 거리와 속도로 움직이거나 돌고, \"따라와\"라고 하시면 "
              "따라가요. 그리고 손을 흔들거나 판타스틱 베이비, 러브 어택 같은 제 노래도 불러 드려요."}


NOT_LUMI = re.compile(r"\b(?:cutshion|company|jaka)\b|쿳션|회사|자카|안전", re.I)   # "쿳션은 무슨 일 해?", "안전 기능 뭐 있어?"


def asked(text):
    """Do these words ask what Lumi can do? ("what can you do?", "what are your abilities", "넌 무슨 일을 해?")"""
    t = re.sub(r"\S+—\s*", "", text or "")              # a stutter: "기— 기능", "할 줄— 줄 아는"
    return bool(ASKED.search(t)) and not NOT_LUMI.search(t)


def more_asked(text, last=""):
    """"Tell me more", "what else?", "yes", "더 알려 줘" right after the short overview (`last` = the answer just before,
    from brain history), or "what else can you do?" at any time."""
    t = text or ""
    if re.search(r"\b(?:what else can you do)\b|또\s*뭐\s*할\s*수", t, re.I):
        return True
    return (last or "").startswith(SHORT_MARK) and bool(MORE.search(t))


def answer(text, lang="en", last=""):
    """("short" | "long", what to say) for an ability question or its follow-up, else None."""
    if more_asked(text, last):
        return "long", LONG[lang]
    if asked(text):
        return "short", SHORT[lang]
    return None


if __name__ == "__main__":
    print(answer(" ".join(sys.argv[1:])))
