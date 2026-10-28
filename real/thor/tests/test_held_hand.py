"""With something held: give / put down / put back read by the rules in any wording (brain.held_give, held_place,
PUT_BACK), the arm words (reach / fold), and the hard negatives that must not move. No robot, no LLM.

    .venv/bin/python tests/test_held_hand.py
"""
import itertools

import no_robot                                     # noqa: F401  any connection to the robot fails the test
from assistant import brain

MARKERS = ["home", "dock2", "p1", "p3", "booth_A", "stage", "Gate_A3"]
CALLS = ["", "Lumi, ", "hey robot, ", "um, ", "루미야 ", "저기요, "]
TAILS = ["", " please", " now", ", thanks", " real quick", " 빨리"]

GIVE_EN = ["give it to me", "give me that", "hand it over", "pass it to me", "gimme", "give it", "gib me please",
           "givv it over to me", "can I have it?", "I'll take it", "hand me the cup", "give the cup to me",
           "you give me please", "give it to him", "give it to her", "give it to the lady next to me",
           "give it to my sister", "pass that to my friend", "hand it to the guy in black", "release it into my hand",
           "give 해 줘", "hand over 해 주세요", "pass 해 줘", "give me 해 줘", "would you mind handing it to me?"]
GIVE_KO = ["줘", "이리 줘", "나 줘", "그거 줘", "그거 me 줘", "나한테 주세요", "저한테 주시겠어요", "이리 주십시오", "건네 줘",
           "넘겨 줘", "그분 드려", "저 사람한테 건네줘요", "우리 손녀한테 주시오", "나한테 주이소", "그거 이리 주게", "내놔"]
PUT_DOWN = ["put it on the table", "rest it on the table", "place it down gently", "put it here", "drop it here",
            "set it down", "lower it onto the table", "테이블에 놔 줘", "여기 올려 주세요", "탁자 위에 놓아 주시겠습니까",
            "테이블에 put 해", "여기 put 해 줘", "책상 위에 올려 줘"]
PUT_BACK = ["put it back", "put it back where you found it", "return it to where you found it", "set it back down where it was",
            "put back 해 줘", "제자리에 놔 줘", "제자리에 갖다 놓으시게", "원래 자리에 놓으십시오", "원위치에 놔 줘"]
REACH = ["extend your arm toward me", "hold your hand out", "reach out", "reach for my hand", "arm forward please",
         "팔 뻗어 줘", "손 내밀어 줘", "손 쭉 내밀어 봐", "루미야 arm 뻗어 줘", "나한테 reach 해 볼래?"]
FOLD = ["fold your arm", "tuck your arm in", "arm back home", "go back to your look pose", "팔 접어", "팔 원래대로 해 줘",
        "take your hand back", "put your arm down", "arm back", "Lumi, arm back please", "back to look position",
        "go back to look position", "go back to look pose", "Your look position.", "return to the look position",
        "pull your hand back", "bring your arm back", "put your hand down", "lower your arm", "can you put your arm down?",
        "손 내려", "손 내려 줘", "손 좀 내려 주세요", "손 거둬", "팔 거둬", "팔 내려 주실래요?", "팔 원위치", "루미야 팔 접어 줘",
        "okay, 팔 내려", "take your arm back 해 줘"]
NOT_FOLD = ["don't take your hand back", "팔 내리지 마", "why did you put your arm down?", "hand back", "give it back",
            "give me your hand", "손 내밀어"]
NOT_GIVE = ["don't give it to me yet", "give it to me after the talk", "when my mom comes, give it to her", "give me a break",
            "give it a try", "give up", "she gave me that cup this morning", "I gave it to the guy at the booth",
            "can you give me directions to the subway?", "who will you give that to?", "give it to me, cancel",
            "hand it over, never mind, keep it", "아직 주지 마", "이따가 줘", "내가 달라고 하면 그때 줘", "어제 친구한테 선물 줬어",
            "잠깐만 시간 좀 줘", "엄마, 그 가방 줘 봐", "지영아 물 좀 줘", "Jake, give me your phone for a sec", "주는 척만 해",
            "give it to James at booth A", "bring it to p3", "거기 놓지 마세요", "put down 하지 마", "put the music on",
            "I put it on the table yesterday", "put it on my tab", "lay down"]


def main():
    bad = []
    for call, words, tail in itertools.product(CALLS, GIVE_EN + GIVE_KO, TAILS):
        text = f"{call}{words}{tail}"
        if brain.hand_request(text, True, None, MARKERS) != ("give", None):
            bad.append((text, "give", brain.hand_request(text, True, None, MARKERS)))
    for call, words in itertools.product(CALLS, PUT_DOWN):
        got = brain.hand_request(call + words, True, None, MARKERS)
        if not got or got[0] != "place":
            bad.append((call + words, "place", got))
    for call, words in itertools.product(CALLS, PUT_BACK):
        if brain.intent(call + words, MARKERS) != ("put", "back") or brain.hand_request(call + words, True, None, MARKERS):
            bad.append((call + words, "put back", brain.intent(call + words, MARKERS)))
    for words, want in [(w, "reach") for w in REACH] + [(w, "fold") for w in FOLD]:
        if brain.intent(words, MARKERS) != ("arm", want):
            bad.append((words, want, brain.intent(words, MARKERS)))
    for words in NOT_FOLD:
        if brain.intent(words, MARKERS) == ("arm", "fold"):
            bad.append((words, "not fold", brain.intent(words, MARKERS)))
    for words in NOT_GIVE:
        if brain.held_give(words, MARKERS) or brain.held_place(words, MARKERS):
            bad.append((words, "no hand", brain.hand_request(words, True, None, MARKERS)))
    for text in ["give it to him, he's going to Gate A3", "give it to her, she is going to the stage",
                 "그분한테 드려, 그분 p3로 가셔"]:            # where that person goes is never driven to
        if brain.hand_request(text, True, None, MARKERS) != ("give", None) or \
                any(brain._resolve(m, MARKERS) not in (None, "here")
                    for m in __import__("re").finditer(brain._place_re(MARKERS), brain._norm(brain.give_clause(text)))):
            bad.append((text, "give, no drive", brain.hand_request(text, True, None, MARKERS)))
    for words in ["고개 원위치", "머리 원위치", "head back to centre"]:
        if brain.intent(words, MARKERS) != ("look", "center"):
            bad.append((words, "look center", brain.intent(words, MARKERS)))
    assert not bad, "\n".join(f"{t!r}: want {w}, got {g}" for t, w, g in bad)
    n = len(CALLS) * len(TAILS) * len(GIVE_EN + GIVE_KO) + len(CALLS) * (len(PUT_DOWN) + len(PUT_BACK)) + \
        len(REACH) + len(FOLD) + len(NOT_FOLD) + len(NOT_GIVE) + 6
    print(f"held hand ok ({n} cases)")


if __name__ == "__main__":
    main()
