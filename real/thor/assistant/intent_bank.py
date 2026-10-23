"""Example bank: the fast lane between the keyword rules and the LLM (lumi.route).

Thousands of wordings per thing Lumi can do (English, Korean in 반말 / 해요체 / 하십시오체, mixed, Konglish, whisper
slips) are matched by meaning with the embedding server (assistant/knowledge.embed, bge-m3). Close enough to one
kind and far enough from every other kind (and from the "no" wordings: talk, questions, negations, conditions)
-> the command runs at once; else the LLM reads it. The bank only routes: what a place, object, direction or amount
is comes from the words themselves (the map's marker names, brain.OBJECTS, head_target ...), never from the bank.

Guards come first: negation, a condition or a later time, an ability question, words to someone else, closing words
with two meanings, a question word. A wrong motion is the worst error, so motions need a high match and a margin.

    .venv/bin/python assistant/intent_bank.py build             # embed the bank -> data/intent_bank.npz
    .venv/bin/python assistant/intent_bank.py "say hi with your arm"   # what the bank reads, with the closest wordings
"""
import hashlib
import pathlib
import random
import re
import sys
import zlib

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "intent_bank.npz"
SIM_MIN = 0.84          # the closest wording must be at least this similar (bge-m3 cosine) ...
MARGIN = 0.04           # ... and this much closer than the closest wording of any other kind (the "no" kind too)
AGREE_K = 2             # ... and the K closest wordings all of that kind
MIN_CHARS = 4           # shorter words ("go", "가") are the rules' or the LLM's
MAX_WORDS = 16          # a longer sentence is a story or several requests: the LLM reads it
FILLS = 3               # place / object fills made of each template (the same every run)

# ---------- guards: words the bank never reads ----------
NEGATION = re.compile(r"\b(?:don'?t|do not|never|no need|not now|no more|stop \w+ing|quit \w+ing|without|forget it|"
                      r"never ?mind|scratch that|cancel that)\b|취소|아니다|됐다|"
                      r"[가-힣]지 ?마(?:세요|요|라|십시오)?(?![가-힣])|하지 ?말|말고|필요 ?없|안 ?(?:해|돼|가|와)(?:도)?\b|그만", re.I)
LATER = re.compile(r"\b(?:when|whenever|if|unless|after|before|once|until|till|as soon as|later|tomorrow|tonight|"
                   r"next time|in (?:\w+ ){0,2}(?:minute|hour|second|min|sec)s?|in a (?:while|bit)|soon)\b|분 ?(?:뒤|후|있다)|"
                   r"[가-힣](?<![정화측반전표라장내외평단그러])면(?:\s|$)|(?:하|으|오|가|되|끝나|있으|오시)면|나중에|이따|내일|"
                   r"다음에|있다가|(?:^|\s)(?:후|뒤|전)에(?![서가-힣])|때(?:에)?\s", re.I)
ABILITY = re.compile(r"\b(?:are you able|able to|know how to|how (?:do|can|could|would) you|is it possible|can you even|"
                     r"capable of|do you (?:know|have)|can robots?|could robots?)\b|"
                     r"\bcan you (?:\w+ )?(?:things|anything|objects|stuff|people|by yourself)\b|\b(?:can|could) you \w+(?: up)? (?:a|an|any)\b.*\?|"
                     r"\bshow me (?:you can|how)\b|기능|\bfunction\b|\bfeature\b|보여 ?(?:줄|주실|주세요|줘)|할 ?줄|줄 ?알|(?<!줄 )(?<!주실 )(?<!주 )(?<!줄)(?<!주실)수 ?있(?:어|어요|니|나요|습니까|을까)\s*\??$|가능해|가능한가|가능하", re.I)
WONDER = re.compile(r"\bi wonder\b|\bwonder(?:ing)? (?:if|whether|how)\b|\bi bet\b|\b(?:i )?guess (?:it|the robot)\b|"
                    r"\b(?:can|could|does|did|will|would|is|was) (?:it|this|that|the robot|this robot|that robot|he|she|this thing)\b|"
                    r"\b(?:it|the robot|this robot|this thing) (?:can|could|does|will|is able)\b|\bcan it\b|"
                    r"(?:있|하|되|가|와|오|돌|봐|올라|내려|흔들|집|따라)나(?:요)?\s*[?？.~]*\s*$|나 ?봐(?:요)?\s*[?？.~]*\s*$|"
                    r"(?:^|\s)(?:얘|쟤|걔|이 로봇|저 로봇|로봇이|로봇은|로봇도|이게|이거는)\s|궁금", re.I)
                    # "can it wave? I wonder", "does it follow people?", "이거 손 흔들 수 있나?", "얘 따라오나 봐"
NOT_TO_LUMI = re.compile(
    r"\bshall we\b|\bwe(?:'re| are) (?:heading|going|off|gonna)\b|\bwe (?:should|could|can|will|might|must|need to)\b|\bwe'll\b|"
    r"\byou and (?:i|me)\b|\bmy plan\b|\bour plan\b|우리.*(?:자|까|래|기로)\s*[?？.!~]*$|"          # plans between people
    r"\bimagine\b|\bsuppose\b|\bwhat if\b|\bwould you ever\b|\bif you were\b|\bpretend\b|\bhypothetical|"
    r"만약|[가-힣](?:라면|다면)|어떨까|겠다\s*[!.~]*$|"                                                  # hypotheticals
    r"\battention\b|\bladies and gentlemen\b|\b(?:visitors|guests|attendees|passengers)(?: are)? (?:please|should|must|may|"
    r"are asked|are requested)\b|\bare (?:kindly )?(?:asked|requested) to\b|안내 ?말씀|(?<![가-힣])여러분(?!한테|에게|께)|"
    r"관람객|방문객|승객|"                                                                               # announcements
    r"\bso (?:well|nicely|smoothly|fast|good)\b|\b(?:really|very) (?:well|nicely|smoothly)\b|\bthe way you\b|"
    r"\blove how\b|[가-힣](?:네|네요|구나|군요|더라|던데)\s*[!.~]*$|[가-힣](?<!니)다\s*[!.~]*$", re.I)
    # plans, hypotheticals, announcements, praise and remarks: nobody asked Lumi to do anything now
QUESTION = re.compile(r"^\W*(?:(?:hey|so|um+|uh+|lumi|okay|ok)\W+)*(?:what|where|why|how|when|who|whose|which|is|are|was|"
                      r"were|do(?=\s+(?:you|i|we|they|robots?)\b)|does|did|have|has|had|should|shall i|may i|can i|could i)\b(?! about\b)|"
                      r"어디|뭐|무엇|왜|언제|누구|어떻게|몇|어느|무슨|어떤|얼마|[가-힣]까\s*[?？]+\s*$|봤(?:어|니|나|냐|어요|습니까)|본 ?적|"
                      r"\bhave you (?:been|gone|ever)\b|(?:어|아|해|여)도 ?(?:돼|되|될까|괜찮)", re.I)
OTHER_SENSE = re.compile(r"instagram|insta\b|\bsns\b|\baccount\b|\bsubscribe\b|인스타|계정|채널|구독|팔로우 ?해 ?주세요|"
                         r"따라 ?(?:해|하|말|불러)|\brepeat after\b|\bcopy me\b|\bdo what i do\b|\b(?:lend|give) me a hand\b|"
                         r"\bneed a hand\b|\bhand it to\b|가는 ?길|길 ?(?:좀 )?알려|\bhow (?:do i|to) get\b|\bdirections?\b|\bthe way to\b|"
                         r"(?:^|\s)(?:다 ?같이|모두 ?(?:같이|다)|다들)\s|\beverybody\b|\beveryone,|\ball together\b|\bfollow (?:what|how|the|this|that|your)\b|법 ?알려|방법|\bhow to\b", re.I)   # follow an account, copy me, help me: no motion
REPEAT = re.compile(r"^\W*(?:(?:\w+\W+){0,2})?(?:again|one more time|once more|do it again|same again|more)\W*$|"
                    r"^\W*(?:[가-힣]+\s+)?(?:한 ?번(?:만)? 더|다시|또)\s*(?:해|해 ?줘|해 ?봐|해 ?주세요|하자)?\W*$", re.I)
                    # "again", "한 번만 더 해 줘": what again is the history's (driving.read, the LLM)
SEVERAL = re.compile(r"\b(?<!hundred )and\b(?! a half\b)|\bwait\w*|\bcorrection\b|\binstead\b|"
                     r"\b(?:look|turn|go|move|wave|come|follow|pick|take|put|lift|raise|lower|reach|grab|bring)\b[^,]*,\s*(?:look|turn|go|move|wave|come|follow|pick|take|put|lift|raise|lower|reach|grab|bring)\b|\b(?:then|after that|also|plus|while|no|not|wait|stay|sleep|sorry|i mean|actually|rather)\b|;|"
                     r"(?!갖고|고고|에서)(?<!가)[가-힣](?:서|고)(?:[\s,]|$)|하고|면서|다가|갔다|다녀|아니|기다|대기|(?:가|와) ?있어|계세요|"
                     r"계십시오", re.I)
                     # several requests or a stay ("go to p3 and wait", "가서 기다려", "p3에 가 있어"): steps.read's
HAND_WORDS = re.compile(r"\byou(?:'re| are) holding\b|\b(?:in|from) my hand\b|\bhere'?s\b|\bhanding\b|\bi'?ll give\b|"
                        r"\bhold this\b|\bfrom me\b|\bmy hand\b|\bhand ?에|\bhand it (?:over|to me)\b|\bhand over\b|내 손|제 손|손에 ?(?:줘|놔|주세요|쥐어)|\bi'?m holding\b|\bi am holding\b|들고 있는|손에 있는|받아|드릴게|줄게|가져가세요", re.I)   # the hand reader's (brain.hand_request)
NAME_CALL = re.compile(r"^\W*(?:(?:ah|oh|hey|hi|okay|ok|so|um|uh|look|and)\W+)?([A-Z][a-z]+)\s*,")      # "Jake, follow me": said to Jake
NOT_A_NAME = {"lumi", "loomi", "rumi", "okay", "ok", "please", "hey", "hi", "hello", "so", "well", "now", "alright",
              "yes", "yeah", "no", "sorry", "um", "uh", "oh", "wait", "look", "then", "first", "also", "and", "but",
              "robot", "right", "fine", "good", "great", "sure", "next", "again", "quick", "listen", "excuse", "hmm"}
SELF_TALK = re.compile(r"^\W*i'?m \w+ing\b|\b(?:myself|yesterday|last (?:time|week|night))\b|어제|지난번|었지|었어|"
                       r"^\W*(?:i'?ll|i will|i'?m going|i am going|i went|i was|we'?ll|we went|we were|i have to|i need to go|"
                       r"i want to go|my \w+ (?:will|is|went)|he |she |they )|"
                       r"(?:^|\s)(?:나는|저는|내가|제가|우리는|저희는)\s|갈게|할게|할께|갈께|했어|했어요|갔어|왔어", re.I)

PAST_EN = re.compile(r"\b(?:i|we)(?:'ve| have| had)?\s+(?:just\s+|already\s+|also\s+|then\s+|never\s+)?(?:(?!need\b|feed\b|speed\b)\w+ed|went|came|"
                     r"drove|ran|took|got|left|saw|did|had|made|put|brought|gave|told|said|was|were|spun|stood|sat|found|held|"
                     r"been|gone|done|seen|taken|given)\b|\bi've\b|\bwe've\b", re.I)   # "I walked to the stage", "we went to p3"
TAG = re.compile(r",\s*(?:right|correct|huh|true)\s*[?!.]*\s*$|\b(?:isn'?t|aren'?t|wasn'?t|weren'?t|don'?t|doesn'?t|didn'?t|"
                 r"won'?t|can'?t|haven'?t|hasn'?t) (?:it|you|they|we|i|he|she|there|that)\s*[?!.]*\s*$|"
                 r"(?:지|죠|쥬|지요|잖아|잖아요|맞지|맞죠|맞아요?|그렇지|그렇죠|그쵸|그치)\s*[?？!.~]*\s*$|"
                 r"(?:^|\s)(?:맞지|맞죠|그치)\s*\?+\s*$", re.I)   # "..., right?", "the next stop is p3, isn't it?", "끝에 갔지?"


def past_ko(t):
    """A Korean past tense (a syllable ending in ㅆ: 갔, 왔, 했, 었; not 있 "is", 겠 "will"): said about what happened."""
    return any("가" <= c <= "힣" and (ord(c) - 0xAC00) % 28 == 20 and c not in "있겠" for c in t)


# ---------- the bank ----------
# kinds: what lumi.route does with them (QUICK_RULES); "no" is every wording the bank must leave to the rest
PLACE_EN = ["the stage", "booth A", "p3", "the lobby", "table front", "the coffee corner", "the exit", "point five",
            "booth two", "the entrance", "the start", "the reception desk"]
PLACE_KO = ["스테이지", "부스 A", "p3", "로비", "커피 코너", "출구", "입구", "피쓰리", "2번", "안내 데스크", "회의실", "시작점"]
OBJ_EN = ["cup", "red cup", "bottle", "apple", "banana", "white mug", "water bottle", "orange", "blue cup", "glass",
          "tumbler", "phone"]
OBJ_KO = ["컵", "빨간 컵", "병", "사과", "바나나", "물병", "오렌지", "흰 컵", "텀블러", "머그컵", "파란 컵", "핸드폰"]

GO = [
    'scoot over to <place>', 'lead the way to <place>', 'your destination is <place>, go now', '<place>로 안내해 주세요', '<place>로 move 해', '<place>로 move', 'return to <place>', 'go back to <place>', 'off you go to <place>', '<place>로 가 주실 수 있어요?', '<place>로 이동 좀 해 줄 수 있어?', '<place>로 고고', 'can you take me to <place>',
    'i need you over at <place>', 'i need you at <place>', 'get yourself to <place>', 'can you make it to <place>', 'be at <place> please', 'go wait at the spot called <place>', 'drive yourself to <place>', 'head on over to <place>', 'please proceed to <place>', 'go to <place> right away', 'quickly go to <place>', 'go to the <place> area', '<place>로 이동하십시오', '<place>로 가 주세용', '<place>로 가 주라', '<place>로 가 볼까?', '<place>로 가 줄래요', '<place>까지 좀 가 줄래?', '<place>로 좀 이동해 줄래요?', '<place> 쪽으로 이동해 주세요', '<place>로 가시죠', '<place>로 가 보자', '<place>로 가 주실 수 있나요?', '<place>로 가 주시겠습니까?', '<place>로 이동 바랍니다', '<place>로 가 주면 좋겠어', '<place>에 좀 가 봐', '<place>으로 가', '<place> 가자', '<place>로 ㄱㄱ', '<place> 고', '<place>로 무빙', '<place>로 이동 ㄱ', 'go to <place> 해', '<place> 로 go go',
    # English
    "go to <place>", "go to <place> please", "please go to <place>", "head to <place>", "head over to <place>",
    "drive to <place>", "move to <place>", "go over to <place>", "make your way to <place>", "get to <place>",
    "take yourself to <place>", "roll over to <place>", "walk to <place>", "travel to <place>", "navigate to <place>",
    "can you go to <place>", "could you go to <place> please", "would you go to <place>", "will you go to <place>",
    "would you mind going to <place>", "mind going to <place>", "go to <place> for me", "go to <place> now",
    "go over to <place> now", "i want you to go to <place>", "i need you to go to <place>", "i'd like you to go to <place>",
    "can you head over to <place>", "your next stop is <place>",
    "next, <place>", "off to <place> you go", "let's go to <place>", "let's head to <place>", "lumi, <place>, go",
    "<place>, please", "<place>, go there", "go there, to <place>", "take me to <place>", "lead me to <place>",
    "show me the way to <place>", "guide me to <place>", "bring yourself over to <place>", "get over to <place>",
    "hurry to <place>", "go straight to <place>", "go directly to <place>", "drive over to <place> please",
    "head for <place>", "set off for <place>", "move over to <place>", "go stand by <place>", "park at <place>",
    "go park yourself at <place>", "please move to <place> now", "go to <place>, thanks", "go to <place> real quick",
    # whisper slips, non-native
    "goto <place>", "go too <place>", "go two <place>", "you go <place>", "go <place>", "going <place> please",
    "move <place>", "you go to <place> now", "robot go <place>", "please you go <place>",
    # Korean 반말
    "<place>로 가", "<place>로 가 줘", "<place>로 가 봐", "<place>로 이동해", "<place>로 이동해 줘", "<place>에 가",
    "<place>에 가 줘", "<place>까지 가", "<place>까지 가 줘", "<place> 쪽으로 가", "<place>로 가자", "<place>로 좀 가 줘",
    "<place>로 갈래?", "<place>로 가 줄래?", "<place>로 가 줄 수 있어?", "<place>로 얼른 가", "<place>로 빨리 가",
    "<place> 가", "<place> 가 줘", "<place>로 가라", "<place>로 출발",
    "<place>로 출발해", "<place>로 움직여", "<place> 앞으로 가", "<place>로 나 데려다 줘", "<place>까지 안내해 줘",
    # Korean 해요체
    "<place>로 가요", "<place>로 가 주세요", "<place>로 가 줘요", "<place>로 이동해요", "<place>로 이동해 주세요",
    "<place>에 가 주세요", "<place>까지 가 주세요", "<place>로 가 주실래요?", "<place>로 가 줄래요?",
    "<place>로 가 주실 수 있어요?", "<place>로 좀 가 주세요", "<place> 쪽으로 가 주세요", "<place>로 가 볼래요?",
    "<place>로 가 보세요", "<place>로 가세요", "<place>까지 안내해 주세요", "<place>로 데려다 주세요",
    "<place>로 가 주시면 좋겠어요", "<place>로 가 주시겠어요?", "<place>로 가 주시면 감사하겠습니다",
    # Korean 하십시오체
    "<place>로 가십시오", "<place>로 가 주십시오", "<place>로 이동하십시오", "<place>로 이동해 주십시오",
    "<place>까지 이동 바랍니다", "<place>로 이동 부탁드립니다", "<place>로 가 주시기 바랍니다",
    # mixed, Konglish
    "<place>로 go", "<place>로 go 해", "<place>로 go 해 줘", "go to <place> 해 줘", "<place> 가 please", "please <place>로 가",
    "<place>로 move 해 줘", "<place> 쪽으로 go", "lumi, <place>로 가", "루미야 go to <place>", "<place> 고고",
    "<place>로 고", "<place>로 무브", "<place>로 이동 please", "go <place>로",
    # Korean slips
    "<place>로 가조", "<place>로 가져", "<place>러 가", "<place>로 가쥬", "<place>로 이동해 져",
]
COME = [
    "come here", "come here please", "come to me", "come over here", "come closer", "come a bit closer", "get over here",
    "come this way", "over here please", "come over to me", "can you come here", "could you come over here",
    "would you come to me", "lumi, come here", "hey lumi, come over", "come on over here", "come towards me",
    "approach me", "move closer to me", "get closer to me", "drive over to me", "come to where i am", "come where i'm standing",
    "come near me", "come by me", "i need you over here", "i want you to come here", "please come here now",
    "come to my side", "come stand next to me", "roll over here", "come hither", "kum here", "come hear", "cum here pls",
    "you come here", "robot come", "come come", "come here quick", "hurry over here",
    "이리 와", "이리 와 봐", "이리 와 줘", "여기로 와", "여기로 와 줘", "나한테 와", "나한테 와 줘", "가까이 와", "가까이 와 봐",
    "좀 더 가까이 와", "이쪽으로 와", "이쪽으로 와 봐", "내 쪽으로 와", "내 옆으로 와", "여기 와", "와 봐",
    "이리 오세요", "이리 와 주세요", "여기로 와 주세요", "저한테 와 주세요", "저한테 와 주실래요?", "가까이 와 주세요",
    "이쪽으로 와 주세요", "제 옆으로 와 주세요", "여기로 좀 와 주시겠어요?", "이리로 오십시오", "이쪽으로 와 주십시오",
    "제게 와 주십시오", "come 여기로", "여기로 come", "이리 come", "루미야 come here", "come here 해 줘", "여기로 와 please",
    "이리 와조", "일루 와", "일로 와", "이루 와",
]
FOLLOW = [
    "stick with me, let's go", '나 follow 해', 'you follow, i walk', '천천히 따라와', '이 늙은이 좀 따라와',
    '나 쫓아와', '쫓아와', '쫓아와 줘', 'you follow', 'you follow me', "you're coming with me", 'come along with me now', 'go where i go', 'walk where i walk', 'stay right behind me', '따라오라고', '빨리 따라와',
    'walk beside me', 'walk next to me', 'stay by my side', 'come along', 'keep close to me', 'follow behind me', 'follow me over there', 'follow me this way', 'be my shadow', 'go with me', 'accompany me', 'escort me', '옆에서 같이 걸어', '저랑 같이 걸어요', '같이 가 줄래?', '나 따라와 봐', '저를 따라와 주시겠어요?', '따라 오세요', '따라오십시오', '저 좀 따라와 주세요', '나만 따라와', '함께 가요', 'follow 해 주세요',
    "follow me", "follow me please", "please follow me", "come with me", "come along with me", "walk with me",
    "tag along", "tag along with me", "stay with me", "keep up with me", "stick with me", "stay behind me",
    "go where i go", "come after me", "follow us", "come with us", "walk behind me", "track me", "follow my lead",
    "can you follow me", "could you follow me please", "would you follow me", "i want you to follow me",
    "let's walk together", "come on, follow me", "follow me around", "keep following me", "follow along",
    "lumi, follow me", "hey lumi, come with me", "follow mi", "fallow me", "follo me", "follow me plz", "you follow me",
    "robot follow", "me follow you go", "following me please",
    "따라와", "따라와 줘", "나 따라와", "나를 따라와", "날 따라와", "따라와 봐", "따라 와", "같이 가자", "나랑 같이 가",
    "나랑 가자", "뒤에서 따라와", "날 따라다녀", "나 따라다녀", "따라올래?", "같이 걸어가자",
    "따라오세요", "저를 따라오세요", "저 따라오세요", "따라와 주세요", "저랑 같이 가요", "저 따라와 주실래요?",
    "따라와 줄래요?", "같이 가 주세요", "저를 따라오십시오", "따라와 주십시오", "저와 함께 가시죠",
    "follow 해", "follow 해 줘", "follow me 해 줘", "나 follow 해", "루미야 follow me", "따라와 please", "팔로우 미",
    "팔로우 해 줘", "나 팔로우 해", "따라와조", "딸아와",
]
COME_BACK = [
    "come back", "come back here", "come back please", "return to where you were", "go back to where you were",
    "go back to your spot", "go back to your place", "go back to the start", "return to your starting point",
    "return to your original spot", "go back to where you started", "head back to where you were standing",
    "come back to your spot", "back to where you were", "go back where you came from", "return please",
    "can you come back", "could you go back to your old spot", "lumi, come back", "comeback", "come bak",
    "돌아와", "돌아와 줘", "다시 돌아와", "원래 자리로 돌아와", "원래 자리로 가", "원래 있던 곳으로 돌아가", "제자리로 돌아가",
    "아까 있던 자리로 가", "처음 자리로 돌아가", "돌아와 봐", "돌아오세요", "돌아와 주세요", "원래 자리로 돌아가 주세요",
    "제자리로 돌아가 주세요", "원래 위치로 돌아가십시오", "복귀해", "복귀해 주세요", "come back 해 줘", "원래 자리로 go back",
    "돌아 와", "도라와",
]
MOVE = [
    'move to the front 1 meter', 'scoot to the front 1 meter', 'go to the front 1 meter', 'slide to the front 1 meter', 'could you move to the left 1 meter', 'go backwards 1 meter',
    'move 1 meter ahead', 'drive 1 meter ahead slowly', 'go to the left 1 meter', 'drive 1 meter backwards', 'reverse 1 meter', 'roll to your left 1 meter', 'come back 1 meter', 'backwards 1 meter', 'go 1 meter to your right', 'just 1 meter forwards', 'move ahead 1 meter', 'move forward 1 meter', 'go to your right 1 meter', 'back yourself up 1 meter', 'go right by 1 meter', 'move backward 1 meter', 'roll ahead 1 meter', '앞으로 1 meter 가', '뒤로 1 meter 이동해', '왼쪽으로 1 meter 가 줘', '오른쪽으로 1 meter 이동해 주세요',
    "move forward", "move forward a bit", "go forward a little", "go ahead a bit", "drive forward", "roll forward",
    "step forward", "take a step forward", "inch forward", "scoot forward", "move ahead", "go straight a little",
    "move back", "move back a bit", "go back a little", "back up", "back up a bit", "back up a little please",
    "reverse a bit", "step back", "take a step back", "move backwards", "go backward", "scoot back", "give me some space, back up",
    "move left", "move to the left", "move to your left a bit", "slide to the left", "shift left a little", "step to the left",
    "go left a little", "scoot left", "move right", "move to the right", "move to your right a bit", "slide to the right",
    "shift right a little", "step to the right", "go right a little", "scoot right",
    "move forward one meter", "go back half a meter", "move left 50 centimeters", "move right 30 cm", "go forward 2 meters",
    "back up one meter", "move forward 1 m", "move back 0.5 m", "go 20 cm to the left", "go 1 meter to the right",
    "move forward two steps", "go back one step", "a little forward please", "a bit to the left please",
    "forward a little", "back a little", "left a bit", "right a bit", "come forward a bit", "move a little closer forward",
    "moov forward", "move forword", "go fowards", "bak up", "moove back", "move lef", "move rite",
    "앞으로 가", "앞으로 조금 가", "앞으로 가 봐", "앞으로 좀 가 줘", "앞으로 이동해", "앞으로 한 걸음", "앞으로 한 발짝 와",
    "조금 앞으로", "뒤로 가", "뒤로 조금 가", "뒤로 물러나", "뒤로 좀 빠져", "뒤로 이동해", "후진해", "후진 좀 해 줘", "뒤로 한 걸음",
    "조금 뒤로", "왼쪽으로 가", "왼쪽으로 조금 가", "왼쪽으로 이동해", "왼쪽으로 비켜", "왼쪽으로 한 걸음", "조금 왼쪽으로",
    "오른쪽으로 가", "오른쪽으로 조금 가", "오른쪽으로 이동해", "오른쪽으로 비켜", "오른쪽으로 한 걸음", "조금 오른쪽으로",
    "앞으로 1미터 가", "뒤로 50센티 가", "왼쪽으로 30센티 이동해", "오른쪽으로 1미터 가", "앞으로 2미터 이동해",
    "앞으로 가 주세요", "앞으로 조금만 가 주세요", "뒤로 가 주세요", "뒤로 조금 물러나 주세요", "왼쪽으로 가 주세요",
    "오른쪽으로 이동해 주세요", "앞으로 이동해 주십시오", "뒤로 이동해 주십시오", "왼쪽으로 이동하십시오", "오른쪽으로 이동하십시오",
    "앞으로 move", "뒤로 back", "left로 가", "right로 이동", "forward로 가", "back 해 줘", "앞으로 go", "뒤로 go",
    "앞으로 가조", "뒤로 가조", "압으로 가",
]
TURN = [
    'you turn full circle', 'do a full spin', 'turn yourself to the left', 'turn yourself to the right', '왼쪽으로 좀 돌아 주실래요', '오른쪽으로 좀 돌아 봐', '뒤돌아 주십시오', 'turn 90 degrees to the left',
    'hang a left', 'hang a right', '오른쪽으로 꺾어', '왼쪽으로 꺾어', '좌회전 해', '우회전 해', '좌회전', '우회전', 'u턴 해 줘', 'turn right by 90 degrees', 'could you turn 90 degrees to your right', 'spin 90 degrees left', 'rotate 90 degrees to the right', '제자리에서 왼쪽으로 돌아', 'tern right', '턴 레프트', '턴 라이트', 'right로 돌아',
    'turn yourself to the left', 'turn your body to your left', 'turn your body right', 'rotate your body left', 'please turn yourself to the right', 'turn to face the other way', 'face the other way', 'spin 360 degrees', 'spin all the way around', 'do a full turn', 'turn 90 degrees right', 'rotate 45 degrees left', '좌측으로 회전해', '우측으로 회전해', '좌측으로 20도 회전해 줘', '우측으로 30도 돌아', '반대쪽으로 돌아', '반대로 돌아 서', '몸 돌려', '180도 돌아', '뒤로 돌아서', '왼쪽으로 몸 돌려 줘', '오른쪽으로 방향 바꿔', '방향 바꿔 왼쪽으로',
    "turn left", "turn right", "turn around", "turn to the left", "turn to the right", "turn your body left",
    "rotate left", "rotate right", "spin around", "turn left 90 degrees", "turn right 45 degrees", "turn 30 degrees left",
    "make a left turn", "make a right turn", "do a u-turn", "turn back around", "face the other way", "rotate to your right",
    "pivot left", "pivot right", "turn yourself around", "about face", "can you turn left", "please turn right",
    "turn lefft", "tern right", "turn arond", "turn rite",
    "왼쪽으로 돌아", "오른쪽으로 돌아", "뒤로 돌아", "왼쪽으로 회전해", "오른쪽으로 회전해", "한 바퀴 돌아", "뒤돌아",
    "왼쪽으로 90도 돌아", "오른쪽으로 45도 돌아", "왼쪽으로 돌아 줘", "오른쪽으로 몸 돌려", "몸을 왼쪽으로 돌려",
    "왼쪽으로 돌아 주세요", "오른쪽으로 돌아 주세요", "뒤로 돌아 주세요", "왼쪽으로 회전해 주십시오", "오른쪽으로 회전하십시오",
    "turn 왼쪽", "오른쪽으로 turn", "left로 돌아", "right로 돌아 줘", "왼쪽으로 turn 해", "유턴해", "유턴 해 줘",
]
LOOK = [
    'eyes to the left', 'look over to the right', 'look at the left', "look here, i'm the one talking", '위를 좀 쳐다봐', '아래 좀 봐', '밑에 좀 봐', '뒤 좀 봐', 'look 아래', 'look 위로 해 줘', 'down 쪽 봐 줘', '오른쪽 look', '앞을 똑바로 봐', '여기 봐, 여기', 'you look me please', 'chin up', 'look left real fast',
    'look rightwards', 'look leftwards', 'look upward', 'look downward', 'look at the ground', 'look at your feet', 'look me in the eye', 'watch me', '나 쳐다봐', '저 보세요', '땅 봐', '왼편 봐', '오른편 봐', 'face forward', 'eyes front', 'head back to center', 'reset your head', 'center your head', 'straighten your head', 'put your head back to the middle', '고개 원위치', '고개 가운데로', '고개 원래대로 해 줘', 'front 봐', '앞에 봐', 'look away', 'avert your eyes', 'turn your eyes away', '딴 데 봐', '다른 데 봐', '시선 좀 돌려 줘', 'turn to me', 'turn your head toward me', '고개 나한테 돌려', 'chin up', 'tilt your head up a bit', 'look higher', 'look a bit to the left', '레프트 봐', '라이트 봐', 'swivel your head left', 'turn the head left 60', 'look over to the right', 'look at mee', 'luk right', 'look upp',
    'glance right', 'glance left', 'eyes up', 'eyes down', 'eyes left', 'eyes right', 'look at the ceiling', 'look at the floor', 'look to your right please', 'look 30 degrees to the left', 'look 20 degrees right', 'turn your head 45 degrees left', 'look up at me', 'look down at the floor', 'look this way please', 'look at my face', '천장 봐', '바닥 봐', '하늘 봐', '땅 봐', '고개 down 해 줘', '고개 up', 'head up 해', '여기 look', '여기 좀 봐', '앞을 보십시오', '정면을 봐요', '왼쪽 좀 봐 줄래?', '오른쪽 쳐다봐', '날 쳐다봐', '저 좀 쳐다봐 주세요', '고개 숙여 주세요', '고개를 왼쪽으로 30도 돌려', '위쪽 봐', '아래쪽 봐', '카메라 봐', '이쪽 좀 봐 주세요',
    "look at me", "look at me please", "eyes on me", "look over here", "look this way", "face me", "look my way",
    "turn your head to me", "look at us", "can you look at me", "watch me", "look straight", "look ahead",
    "look forward", "look straight ahead", "look left", "look to the left", "look right", "look to the right",
    "look up", "look down", "look up a bit", "look down a little", "turn your head left", "turn your head right",
    "raise your head", "lower your head", "head up", "head down", "tilt your head up", "tilt your head down",
    "look behind you", "look back", "look over your shoulder", "look at my son", "look at my daughter",
    "look at my friend", "lok at me", "luck at me", "look write", "look lef", "eyes over here", "look here please",
    "나 봐", "날 봐", "나를 봐", "나 좀 봐", "날 좀 봐 줘", "여기 봐", "이쪽 봐", "이쪽을 봐", "정면 봐", "앞을 봐", "왼쪽 봐",
    "오른쪽 봐", "위 봐", "위를 봐", "아래 봐", "아래를 봐", "고개 들어", "고개 숙여", "고개 왼쪽으로 돌려", "고개 오른쪽으로 돌려",
    "고개 들어 봐", "뒤 봐", "뒤를 봐", "뒤돌아 봐", "우리 애 좀 봐 줘",
    "저 봐 주세요", "저를 봐 주세요", "저 좀 봐 주세요", "여기 봐 주세요", "이쪽 봐 주세요", "정면을 봐 주세요",
    "왼쪽을 봐 주세요", "오른쪽 봐 주세요", "고개 들어 주세요", "위를 봐 주세요", "저를 봐 주십시오", "정면을 보십시오",
    "look at 나", "나 look", "left 봐", "right 봐", "up 봐", "여기 look", "look 여기", "eyes on 나",
]
LIFT = [
    'make yourself small', 'shrink a little', 'make you more tall', 'you make body high please', 'body 좀 올려 줘', 'rise up', '조금만 더 커져 봐', '위로 쭉 올라가 봐', '아래로 내려가 봐', '몸을 좀 낮추십시오',
    'shrink', 'squat down a bit', 'elevate yourself', 'drop your height', 'lower your height', 'raise your height', 'stretch up tall', 'go all the way down', 'keep going down', 'move up for a sec', 'move down', 'drop down an inch', 'raise up by 1 meter', 'go up 1 meter', 'come down 1 meter', '몸 좀 들어 올려 줄래?', '몸 위로', '높이 좀 낮춰 주실래요?', '조금 낮아져 줄래?', '높이 올려', '더 올려', '아래로 내려가 봐', '1 meter 높여 줘', '1 meter 내려가',
    'go up a bit', 'go up', 'go down', 'up a little', 'down a little', 'sink down', 'rise up', 'get up higher', 'a bit higher please', 'a bit lower please', 'lower down a little', 'raise up', 'move up', 'move down a bit', 'lift up a little', 'make yourself a bit higher', 'come up a bit', '커져 봐', '좀 더 커져 봐', '키 커져 봐', '작아져 봐', '올라가', '조금만 올라가 줄래요?', '내려가', '조금 내려가 줘', '높이 올려 줘요', '높게 올라가', '낮게 내려가', '위로 올라가 줘', '아래로 내려가 줘', '키 좀 키워 줘', '키 좀 줄여 줘', '몸 좀 높여 주세요', 'go up 해 봐', 'up 해 줘', 'down 해 줘',
    "raise yourself", "raise yourself up", "lift yourself up", "get taller", "make yourself taller", "stand up tall",
    "go higher", "lower yourself", "get shorter", "make yourself shorter", "go lower", "get a bit taller",
    "get a little lower", "raise your body", "lower your body", "lift your body up", "raise your torso",
    "lower your torso", "lift up", "stand taller", "rise up a bit", "come down a bit", "shrink down a little",
    "raise yourself 5 cm", "lower yourself 3 centimeters", "grow taller", "get smaller", "lift yourself",
    "키 높여", "키 좀 높여", "키 키워", "키 낮춰", "키 좀 낮춰", "몸 올려", "몸 내려", "몸 좀 올려 봐", "몸 좀 낮춰", "몸을 낮춰",
    "리프트 올려", "리프트 내려", "상체 올려", "상체 내려", "더 높게", "더 낮게", "키 좀 높여 주세요", "몸을 올려 주세요",
    "몸을 낮춰 주세요", "리프트 올려 주세요", "리프트를 내려 주십시오", "키를 높여 주십시오", "lift 올려 줘", "lift 내려",
    "키 up", "몸 down", "taller 해 줘", "몸 업", "리프트 업",
]
WAVE = [
    'say hello to everyone with a wave', 'say hi to them with a wave', 'wave your hand please', '손 한번 흔들어 봐', 'wave at everyone',
    'mind giving us a wave', 'give a wave', 'give them a wave', 'wave for the camera', 'wave once more', 'wave again', 'one more wave', 'do your hand wave', 'do your wave', 'show me your wave', '팔 흔들어 봐', '팔 흔들어 줘', '한 번만 더 흔들어 줘', '다시 손 흔들어', '손 한 번 흔들어 봐', '손 흔들어 인사해', '인사 손 흔들어 줘', '바이바이 손 흔들어', '손 흔들어 주실래요?', '손 좀 흔들어 줄래?', 'wave 한 번 해 줘', '손 흔들기 해 줘',
    "wave", "wave at me", "wave to me", "wave your hand", "wave hello", "wave hi", "wave at us", "give us a wave",
    "give me a wave", "wave to the people", "wave to everyone", "wave to the guests", "say hi with your arm",
    "say hi with your hand", "say hello with your hand", "greet them with your hand", "wave your arm",
    "wave goodbye to them", "wave to the kids", "can you wave", "could you wave at us", "please wave",
    "do a wave", "show us your wave", "shake your hand at me", "lift your hand and wave", "wave your arm around",
    "greet me with a wave", "a little wave please", "wave wave", "wave plz", "weave at me", "wave et me", "way of hello",
    "손 흔들어", "손 흔들어 줘", "손 흔들어 봐", "손 좀 흔들어", "손 인사 해", "손 인사 해 줘", "손으로 인사해", "손으로 인사해 봐",
    "팔 흔들어", "팔 흔들어 봐", "우리한테 손 흔들어", "애들한테 손 흔들어 줘", "손 흔들면서 인사해", "흔들어 봐",
    "손 흔들어 주세요", "손 좀 흔들어 주세요", "손 인사 해 주세요", "손으로 인사해 주세요", "저희한테 손 흔들어 주세요",
    "손을 흔들어 주십시오", "손 인사를 해 주십시오", "wave 해", "wave 해 줘", "손 wave", "웨이브 해 줘", "손 흔들어 please",
    "hi 해 봐 손으로", "손 흔드러", "손 흔들어조",
]
ARM_REACH = [
    'lemme see your hand', 'let me see your hand', 'hand out', 'reach out your hand', 'hand 좀 내밀어 줘', '팔 reach 해 줘', 'offer your hand to my grandma', 'you give me hand please', 'arm out! arm out!', '팔 쭉 뻗어 봐',
    'reach your hand to me', 'hold out you hand', 'hold it out', '나한테 손 줘', '손 이리 줘 봐', 'hand 줘 봐', '손 줘 봐', 'reach out, thanks', 'reach your arm out', 'reech out to me',
    'arm out', 'arm out please', 'put your hand out', 'reach forward', 'extend your hand', 'stretch out', 'stretch your hand forward', '손 앞으로 내밀어', '손 좀 앞으로 내밀어 주세요', '팔 extend 해 줘', '팔 앞으로', '팔 앞으로 뻗어', '팔 펴 줘', '팔 쭉 펴 주세요', '팔 내밀어 줄래?', '손 뻗어', 'reach out 해 줘',
    "reach out", "reach out your arm", "stretch your arm", "stretch out your arm", "extend your arm", "hold out your arm",
    "hold out your hand", "put your arm out", "stick your arm out", "give me your hand", "offer me your hand",
    "reach towards me", "reach out to me", "arm out please", "straighten your arm", "lift your arm up", "raise your arm",
    "show me your arm", "reach your hand out", "can you reach out your arm",
    "팔 뻗어", "팔 뻗어 봐", "팔 좀 뻗어", "팔 내밀어", "팔 좀 내밀어 봐", "팔을 쭉 뻗어 줘", "손 내밀어", "손 좀 내밀어 봐",
    "팔 쭉 펴", "팔 들어", "팔 올려", "팔 뻗어 주세요", "팔을 내밀어 주세요", "손을 내밀어 주세요", "팔을 뻗어 주십시오",
    "arm 뻗어", "팔 reach", "팔 쭉", "팔 뻐더",
]
ARM_FOLD = [
    'arm back in', 'you close arm please, put back', 'arm 접어 줘', '팔 거두십시오', '팔 접어 봐',
    'pull your arm back in', 'pull your hand back in', 'take your hand back', 'arm back home', 'bring the arm home', '손 다시 넣어', '이제 접어', '접어', '팔 다시 넣어', 'fold you arm', '넣어',
    'fold arm', 'fold it', 'you can fold your arm now', 'arm in', 'arm away', 'retract your arm', 'bring your arm in', 'tuck it in', '팔 제자리로', '팔 원위치', '팔 다시 접어', '팔 넣어 줘', 'fold arm 해 줘', '팔 fold', '팔 거둬 줘', '팔 내려 줄래?',
    "fold your arm", "fold your arm up", "put your arm down", "put your arm away", "take your arm back", "tuck your arm in",
    "arm down", "bring your arm back", "lower your arm", "pull your arm in", "rest your arm", "arm back please",
    "put your arm back", "relax your arm", "drop your arm",
    "팔 접어", "팔 접어 줘", "팔 내려", "팔 좀 내려", "팔 거둬", "팔 넣어", "팔 원래대로", "팔 접어 주세요", "팔을 내려 주세요",
    "팔을 거둬 주세요", "팔을 접어 주십시오", "arm 접어", "팔 down", "팔 내려 please",
]
ARM_OPEN = [
    "open your hand", "open your fingers", "open the gripper", "open your gripper", "open up your hand", "spread your fingers",
    "unclench your hand", "open your claw", "hand open please",
    "손 펴", "손 펴 봐", "손 좀 펴 봐", "손 벌려", "손가락 펴", "그리퍼 열어", "손 열어", "손 펴 주세요", "손을 펴 주십시오",
    "그리퍼 열어 주세요", "hand 펴", "손 open", "gripper open 해",
]
ARM_CLOSE = [
    "close your hand", "close your fingers", "close the gripper", "make a fist", "clench your hand", "squeeze your fingers",
    "close your claw", "shut your hand", "hand closed please",
    "손 쥐어", "손 꽉 쥐어", "주먹 쥐어", "손 오므려", "그리퍼 닫아", "손 닫아", "손가락 오므려", "손 쥐어 주세요",
    "주먹 쥐어 주세요", "그리퍼 닫아 주십시오", "손 close", "gripper close 해", "주먹 쥐어 봐",
]
PICK = [
    '<obj> grab 해 봐', '그 <obj> 좀 grab 해 봐', '<obj> 하나 잡아 봐', '<obj> take 해', 'pick up the <obj> please',
    'take hold of the <obj>', 'get hold of the <obj>', 'snatch the <obj>', 'snatch a <obj>', 'try picking up the <obj>', '<obj> pick 해 줘', '<obj> 픽 해 줘', '<obj> 픽업해 줘', '<obj> take 해 줘', '<obj> 좀 take 해', '<obj> 집으세요', '<obj> 한번 집어 봐요', '<obj> 쥐어 봐', '<obj> 들어 봐', 'grab 해 <obj>', '<obj> pick up 해', 'pick upp the <obj>',
    'would you mind grabbing the <obj>', 'mind grabbing the <obj>', 'grab me the <obj> off the table', 'pick the <obj> up off the table', 'take hold of that <obj>', 'can you grab that <obj>', 'lift up the <obj>', '<obj> pick up', '<obj> 좀 pick up', '<obj> 집어 줄래?', '<obj> 좀 집어 줄래요?', '<obj> 잡아 볼래?', '<obj> 들어 볼래?', '<obj> 하나 집어', '<obj> 좀 집으세요', '<obj>을 집어 주십시오', '<obj> 잡으세요',
    "pick up the <obj>", "take the <obj>", "grab the <obj>", "get the <obj>", "pick the <obj> up", "lift the <obj>",
    "take hold of the <obj>", "grab that <obj>", "snag that <obj>", "can you pick up the <obj>",
    "could you grab the <obj> please", "would you mind picking up the <obj>", "please take the <obj>",
    "pick up that <obj> on the table", "take the <obj> from the table", "grab the <obj> over there",
    "i want you to pick up the <obj>", "pick up the <obj> for me", "go ahead and grab the <obj>", "pic up the <obj>",
    "pick op the <obj>", "grap the <obj>", "take da <obj>",
    "<obj> 집어", "<obj> 집어 줘", "<obj> 좀 집어 봐", "<obj> 들어", "<obj> 들어 줘", "<obj> 잡아", "<obj> 잡아 줘", "<obj> 집어 올려",
    "<obj> 들어 올려", "<obj> 좀 잡아 봐", "저 <obj> 집어", "테이블 위에 <obj> 집어", "<obj> 집어 주세요", "<obj> 좀 들어 주세요",
    "<obj> 잡아 주세요", "<obj> 집어 주실래요?", "<obj> 들어 줄래요?", "<obj> 집어 주십시오", "<obj>을 들어 주십시오",
    "<obj> pick up 해 줘", "<obj> 좀 pick up 해", "pick up <obj>", "<obj> grab 해", "<obj> 픽업 해 줘", "<obj> 집어조",
]
PUT = [
    "put it down", "set it down", "put that down", "place it down", "put the cup down", "lay it down", "drop it here",
    "put it back", "put it back where it was", "return it to where it was", "put the cup back", "set it back down",
    "can you put it down", "please put it down now",
    "내려놔", "내려놔 줘", "내려 놓아", "그거 내려놔", "컵 내려놔", "제자리에 놔", "원래 자리에 놔", "다시 갖다 놔", "도로 놔",
    "내려놔 주세요", "내려 놓아 주세요", "제자리에 놔 주세요", "원래 자리에 놓아 주십시오", "put down 해", "내려놔 please",
    "put it back 해 줘",
]
FETCH = [
    'bring me the <obj> from <place>', 'go get the <obj> from <place>', 'get me a <obj> from <place>', 'fetch the <obj> from <place>', 'would you mind getting a <obj> from <place>', 'can you bring me the <obj> from <place>', '<place>에서 <obj> 가져와', '<place>에서 <obj> 가져다 줘', '<place>에서 <obj> 갖고 와', '<place>에서 <obj> 챙겨 와', '<place>에서 <obj> 좀 가져와 주세요', '<place>에서 <obj> 가져다 주십시오', '<place>에서 <obj> bring 해 줘', '<place>에서 <obj> fetch 해 줘', '<place>에 있는 <obj> 가져와',
    "bring me the <obj>", "bring me a <obj>", "get me the <obj>", "get me a <obj>", "fetch the <obj>", "fetch me a <obj>",
    "bring the <obj> to me", "bring the <obj> here", "go get the <obj>", "go get me a <obj>", "can you bring me the <obj>",
    "could you get me a <obj> please", "i'd like a <obj>, bring it here", "would you fetch me the <obj>",
    "bring over the <obj>", "hand me the <obj>", "pass me the <obj>", "brin me the <obj>", "bring me da <obj>",
    "<obj> 가져와", "<obj> 가져다 줘", "<obj> 갖다 줘", "<obj> 좀 가져와 봐", "<obj> 가지고 와", "<obj> 좀 갖다 줄래?",
    "나한테 <obj> 가져다 줘", "<obj> 여기로 가져와", "<obj> 가져다 주세요", "<obj> 좀 갖다 주세요", "<obj> 가져와 주실래요?",
    "저한테 <obj> 가져다 주세요", "<obj>을 가져다 주십시오", "<obj> bring 해 줘", "<obj> 가져와 please", "bring <obj> 해 줘",
    "<obj> 가저와",
]
NO = [
    'can it wave? i wonder', 'i wonder if it can follow people', 'does it pick up cups?', 'can the robot turn around?', 'this robot can go anywhere', 'it can lift itself, right', '이거 손 흔들 수 있나?', '얘 따라오나 봐', '로봇이 컵 집을 수 있나?', '이 로봇 회전하나요?', '쟤 움직이나 봐', '로봇이 어디로 가나?', '궁금하다, 팔 뻗을 수 있나', 'does this thing move?',
    '가자', '가자 이제', '이제 가자', '자 가자', "let's go now", "okay let's go", "come on, let's go", 'back to where you picked it up', 'put it back where you found it',
    # past events and tag questions are the PAST_EN / past_ko / TAG guards' (exact, before any match)
    '인스타 팔로우 해 줘', 'follow us on instagram', 'follow our account', '따라 해 봐', '내 말 따라 해', 'repeat after me', 'copy me', 'do what i do', 'can you lend me a hand?', 'give me a hand with this', '한 번만 더 해 줘', 'do it again', 'again please', 'one more time', '다시 해 줘', '또 해 봐', '한 번 더', 'over here for a sec', 'wait over there', 'the other way', '왼쪽으로', '오른쪽으로', '앞으로', '뒤로',
    'can your arm move?', 'how long is your arm?', 'how far can you reach?', '악수하자', '악수할래?', 'can you turn your head?', 'is your head turning?', 'how high can you go?', 'how low can you go?', "what's on the ceiling?", 'is the floor clean?', 'where are you looking?', 'what are you looking at?', '어디 보고 있어?', '왜 나를 봐?', '왜 따라와?', '키가 몇이야?', '팔 길이가 얼마야?', '고개 아파?', '손 차가워?', '손 따뜻해?',
    # cut-off starts
    "let's", "can you", "could you", "please", "lumi, can you", "wait", "hmm", "so", "go", "move", "turn", "look",
    "루미야 저기", "저기요", "루미야", "혹시", "그럼", "잠깐만", "있잖아", "근데",
    # talk about places, trips and the map
    "i went to the stage yesterday", "the stage is over there", "where is the stage?", "what's at booth A?",
    "how far is the lobby?", "is the coffee corner open?", "the exit is on the left", "i'm going to the lobby",
    "my friend is at booth A", "have you been to the stage?", "do you know where the exit is?", "which booth is yours?",
    "how do i get to the stage?", "can i go to the lobby?", "is it far to the entrance?", "the lobby is crowded",
    "스테이지 어디야?", "로비가 어디예요?", "출구 어디 있어요?", "부스 A에 뭐 있어?", "커피 코너 열었어요?", "저 로비로 갈게요",
    "나 스테이지 갔다 왔어", "로비 멀어요?", "화장실 어디예요?", "입구가 어디죠?", "스테이지까지 얼마나 걸려?",
    "where are you going?", "where did you go?", "어디 가?", "어디 가는 거야?", "어디 갔다 왔어?",
    # ability, how
    "can you walk?", "can you move by yourself?", "can you pick things up?", "how do you pick up a cup?",
    "are you able to follow people?", "how fast can you move?", "can you climb stairs?", "do you have arms?",
    "how heavy can you lift?", "can you see me?", "how do you know where to go?", "can robots dance?",
    "물건 집을 수 있어?", "혼자 움직일 수 있어?", "어떻게 컵을 집어?", "사람 따라갈 수 있어요?", "계단 올라갈 수 있어?",
    "얼마나 빨리 움직여?", "팔 있어?", "몇 킬로까지 들 수 있어?", "어떻게 길을 찾아?", "손 흔들 줄 알아?",
    # negation, stop
    "don't go to the stage", "don't move", "don't follow me", "don't look at me", "stop following me", "no, stay here",
    "stay where you are", "don't wave", "don't pick that up", "leave the cup", "stay put", "you don't have to come",
    "가지 마", "움직이지 마", "따라오지 마", "쳐다보지 마", "손 흔들지 마", "그거 집지 마", "거기 그대로 있어", "가만히 있어",
    "오지 마세요", "안 와도 돼", "따라오지 마세요",
    # later, conditions
    "go to the stage when the guests arrive", "after the talk, wave to them", "if someone comes, follow them",
    "later you can go to the lobby", "wave when i say so", "come here after the meeting", "tomorrow go to booth A",
    "손님 오시면 손 흔들어", "나중에 스테이지로 가", "회의 끝나면 이리 와", "내가 부르면 와", "이따가 로비로 가",
    "사람 오면 따라가",
    # to someone else
    "mom, look at the robot", "kids, wave to the robot", "honey, come here", "jake, come see this", "민수야 이리 와",
    "엄마 이거 봐", "얘들아 로봇한테 손 흔들어", "지민아 따라와", "여보 이리 와 봐",
    # closings, back-channels
    "okay", "thanks", "thank you", "okay thanks", "i see", "got it", "alright", "sounds good", "cool", "nice",
    "that's all", "that's it", "never mind", "good job", "well done", "great", "perfect",
    "알겠어", "알겠어요", "고마워", "감사합니다", "오케이", "됐어", "됐어요", "그렇구나", "좋아", "잘했어", "수고했어", "괜찮아",
    # talk, opinions, about Lumi
    "you look cute", "your arm is cool", "i like your hand", "you move so smoothly", "you turned really fast",
    "that was a nice wave", "you're tall", "your head moves", "nice to meet you", "hello", "hi lumi", "good morning",
    "what's your name?", "who made you?", "how old are you?", "tell me about yourself", "tell me a joke",
    "what can you do?", "what are you doing?", "are you busy?", "how's your battery?", "are you tired?",
    "귀엽다", "팔 멋있다", "손 신기하다", "움직임 부드럽네", "키 크다", "반가워", "안녕", "안녕하세요", "이름이 뭐야?",
    "누가 만들었어?", "몇 살이야?", "자기소개 해 줘", "농담 해 줘", "뭐 할 수 있어?", "뭐 하고 있어?", "배터리 얼마나 남았어?",
    # company / event questions
    "what does cutshion do?", "who is the ceo of your company?", "where is your company?", "how many people work there?",
    "tell me about cutshion", "what products do you make?", "is this booth yours?", "when does the event end?",
    "쿳션은 뭐 하는 회사야?", "회사 어디 있어요?", "대표가 누구예요?", "직원 몇 명이에요?", "이 행사 언제 끝나요?",
    # visitor about themselves
    "i'll follow you", "let me follow you", "i'm going to wave", "i can lift that", "i picked up the cup",
    "i'm looking at you", "i turned left at the corner", "i'll come back later", "i'll bring you a cup",
    "제가 따라갈게요", "내가 손 흔들게", "제가 컵 들게요", "저 왼쪽으로 돌았어요", "나중에 다시 올게요", "내가 가져올게",
    "my son wants to see you wave", "he went to the lobby", "she looked at you", "they picked up the cups",
    # seeing questions
    "what am i holding?", "what colour is my shirt?", "how many people do you see?", "do you see the cup?",
    "is there a bottle on the table?", "what's in front of you?", "뭐 들고 있게?", "내 옷 무슨 색이야?", "컵 보여?",
    "앞에 뭐 있어?", "사람 몇 명 보여?",
    # things that sound like commands but are not
    "look it up", "look up the weather", "look for my keys", "turn off the lights", "turn the music down",
    "pick a number", "pick one for me", "take a picture", "take a guess", "take care", "take your time",
    "go ahead, tell me", "go on", "come on", "come on, really?", "follow the rules", "follow your heart",
    "bring it on", "put it on my tab", "wave of people", "the wave was big", "raise the volume", "lower the volume",
    "lift me up with a song", "turn up the music", "give me a hint", "give me a second", "hold on",
    "날씨 찾아 봐", "검색해 봐", "불 꺼", "볼륨 줄여", "사진 찍어", "아무거나 골라", "계속해", "말해 봐", "잠깐 기다려",
]
RECEIVE = [
    "take this", "take this from me", "hold this", "hold this <obj>", "take my <obj>", "here, take it", "here you go, take it",
    "i want to give you a <obj>", "i'm handing you the <obj>", "take the <obj> from my hand", "grab this from me",
    "can you hold this for me", "keep this for me", "take it from me", "catch this", "i have a <obj> for you",
    "이거 받아", "이거 받아 줘", "이거 들고 있어", "이 <obj> 받아 줘", "제 손에 있는 <obj> 가져가세요", "<obj> 드릴게요",
    "이거 좀 들어 줘", "이거 가져가", "이거 받아 주세요", "이것 좀 들고 계세요", "<obj> 받아 줄래요?", "이거 take 해",
]
GIVE = [
    "give it to me", "give me that", "hand it over", "pass it over here", "give it back", "give me what you're holding",
    "can i have it", "let me have it", "hand it to me please", "give that to me", "i'll take it now", "pass it to me",
    "이리 줘", "그거 줘", "그거 이리 주세요", "나 줘", "저 주세요", "줘 봐", "돌려줘", "그거 저한테 주세요", "건네줘",
    "이리 넘겨", "give me 해 줘", "나한테 줘",
]
NO += [
    "face <place>", "look at <place>", "look towards <place>", "point at <place>", "<place> 쪽을 봐", "<place> 봐",
    "go upstairs", "go downstairs", "위층으로 가", "아래층으로 가", "go to sleep", "go to bed", "go home now, i'm tired",
    "the <obj>", "<obj>", "the <obj> the <obj>", "a <obj>", "<obj> <obj>", "that <obj>", "my <obj>", "your <obj>",
    "<obj> 있어", "<obj>야", "그 <obj>", "내 <obj>", "<obj> 예쁘다", "<obj> 좋아해", "<obj> 맛있어", "i like the <obj>",
    "this <obj> is mine", "the <obj> is red", "i bought a <obj>", "i need a new <obj>", "<obj> 샀어", "이 <obj> 내 거야",
    "go for it", "go away", "get lost", "come on now", "come again?", "follow up later", "look who's here",
    "lift my mood", "turn it off", "wave goodbye to your old life", "move on", "let it go", "back off from that topic",
    "저리 가", "가 버려", "꺼져", "됐어 가", "알아서 해", "마음대로 해", "좀 쉬어", "가만있어 봐",
]
KINDS = {"go_to": GO, "come": COME, "follow": FOLLOW, "come_back": COME_BACK, "move": MOVE, "turn": TURN, "look": LOOK,
         "lift": LIFT, "wave": WAVE, "arm_reach": ARM_REACH, "arm_fold": ARM_FOLD, "arm_open": ARM_OPEN,
         "arm_close": ARM_CLOSE, "pick": PICK, "put": PUT, "fetch": FETCH, "receive": RECEIVE, "give": GIVE, "no": NO}
ACTS = set(KINDS) - {"put", "receive", "give", "no"}   # the kinds the bank acts on; the hand's (put down, take, hand
                                                       # over) are brain.hand_request's or the LLM's


def _fill(t, slot, en, ko):
    if slot not in t:
        return [t]
    pool = ko if re.search(r"[가-힣]", t.replace(slot, "")) else en
    r = random.Random(zlib.crc32(t.encode()))    # the same fills for a wording whatever is added around it
    if slot == "<place>":                        # a named marker is embedded as CANON_PLACE (core): always one fill
        return [t.replace(slot, f) for f in [CANON_PLACE] + r.sample([f for f in pool if f != CANON_PLACE], FILLS - 1)]
    canon = "컵" if pool is ko else "cup"       # an object is embedded as this one (core): always one fill
    return [t.replace(slot, f) for f in [canon] + r.sample([f for f in pool if f != canon], FILLS - 1)]


def examples():
    """[(text, kind)]: the bank with its <place> / <obj> slots filled (FILLS each, a fixed seed)."""
    out = []
    for kind, texts in KINDS.items():
        for t in texts:
            for a in _fill(t, "<place>", PLACE_EN, PLACE_KO):
                out += [(b, kind) for b in _fill(a, "<obj>", OBJ_EN, OBJ_KO)]
    return out


_bank = None


def _load():
    """(vectors, kinds) of the bank: from data/intent_bank.npz when it holds these very wordings, else embedded now."""
    global _bank
    if _bank is None:
        from assistant import knowledge
        ex = examples()
        texts = [t for t, _ in ex]
        key = hashlib.sha1("\n".join(f"{t}\t{k}" for t, k in ex).encode()).hexdigest()
        if CACHE.exists():
            z = np.load(CACHE)
            if str(z["key"]) == key:
                _bank = (z["vecs"], z["kinds"])
                return _bank
        vecs = knowledge.embed(texts)
        kinds = np.array([k for _, k in ex])
        np.savez(CACHE, vecs=vecs, kinds=kinds, key=key)
        _bank = (vecs, kinds)
    return _bank


POLITE = re.compile(r"\bif you don'?t mind\b|\b(?:it'?d|it would|that would|that'?d) be (?:great|nice|good|lovely|awesome|"
                    r"cool|helpful) if you(?: could)?\b|^\W*go ahead and\b|\bfor a (?:sec|second|moment|bit)\b|\bif you please\b", re.I)
SLANG = [(re.compile(rf"(?<![\w가-힣]){a}(?![\w가-힣])", re.I), b) for a, b in (
    ("wav", "wave"), ("reech", "reach"), ("ur", "your"), ("u", "you"), ("lemme", "let me"), ("luk", "look"),
    ("pickup", "pick up"), ("plz|pls", "please"), ("mister robot|hey robot|yo robot|bro|buddy|lol|beep boop", ""),
    ("^\\W*robot", ""), (",?\\s*robot(?=\\s*[,.!?]|\\s*$)", ""),
    ("보이소|보시오|보시게|보십시오", "봐"), ("주이소|주시게", "주세요"), ("따라온나|따라오시게|따라오이소", "따라와"),
    ("왼짝", "왼쪽"), ("오른짝", "오른쪽"), ("오른쪽바", "오른쪽 봐"), ("왼쪽바", "왼쪽 봐"),
    ("얘(?= ?,? ?(?:로봇|루미))", ""), ("로봇아|로봇 양반|로봇씨", ""), ("어이|ㅋ+", ""))]
    # slang, whisper's spellings, dialect endings and calls: read as the plain word (the bank and the slots)
LEAD = re.compile(r"^\W*(?:(?:excuse me|okay so|ok so|so|uh+|um+|yo|hi|hey|hello|alright|all right|okay|ok|well|listen|"
                  r"ah+|oh+|wow|hmm+|buddy|lumi|robot|hey robot|루미 ?군|루미 ?선생|루미 ?씨|루미야|루미씨|루미|저기요|저기|자|야(?=\s*,?\s*(?:루미|로봇))|음|어|좋아|이제|그럼|근데|그런데|아|like)\b[\s,.!~]*)+", re.I)
AMOUNT = [(re.compile(r"\b\d+(?:\.\d+)?\s*(?:degrees?|도)(?![a-z])|\b\d+(?:\.\d+)?도", re.I), "90 degrees"),
          (re.compile(r"\b\d+(?:\.\d+)?\s*(?:m|meters?|metres?|cm|centimet(?:er|re)s?|mm|millimet(?:er|re)s?|"
                      r"미터|센티(?:미터)?|센치|밀리)(?![a-z])", re.I), "1 meter")]   # embedded as one amount


def plain(text):
    """The words without polite frames ("if you don't mind", "it'd be great if you could") and calls before."""
    t = POLITE.sub(" ", text or "")
    for rx, word in SLANG:
        t = rx.sub(word, t)
    t = re.sub(r"\s+([,.!?])", r"\1", re.sub(r"^[\s,.!?~]+", "", t))
    t = LEAD.sub("", t).strip()
    return re.sub(r"\s{2,}", " ", t) or (text or "").strip()


def guarded(text):
    """Why the bank does not read these words, or None."""
    from assistant import brain
    t = text.strip()
    if len(t) < MIN_CHARS or len(t.split()) > MAX_WORDS:
        return "length"
    for name, rx in (("negation", NEGATION), ("later", LATER), ("ability", ABILITY), ("question", QUESTION),
                     ("self", SELF_TALK), ("several", SEVERAL), ("hand", HAND_WORDS), ("other sense", OTHER_SENSE),
                     ("repeat", REPEAT), ("past", PAST_EN), ("tag", TAG), ("wonder", WONDER), ("not to lumi", NOT_TO_LUMI)):
        if rx.search(t):
            return name
    if brain.LATER.search(t):
        return "later"
    if past_ko(t):
        return "past"
    if re.match(r"^\W*야\s", t):
        return "someone else"                          # "야 커피코너에서 컵 좀 가져와": a friend called (야 루미 is cut before)
    name = NAME_CALL.match(t)
    if brain.to_someone_else(t) or brain.to_someone_else(brain.CALLING.sub("", t)) or name and name.group(1).lower() not in NOT_A_NAME:
        return "someone else"
    if brain.is_closing(t) or brain.BACKCHANNEL.match(t):
        return "closing"
    return None


def nearest(text, k=5):
    """[(similarity, kind, wording)] of the k closest bank wordings (one embed call)."""
    from assistant import knowledge
    vecs, kinds = _load()
    q = knowledge.embed([text])[0]
    sims = vecs @ q
    top = np.argsort(-sims)[:k]
    texts = [t for t, _ in examples()] if k else []
    return [(float(sims[i]), str(kinds[i]), texts[i]) for i in top], sims, kinds


TAIL = re.compile(r"(?:[\s,.!?~]+(?:please|thanks|thank you|for me|now|right now|real quick|real fast|if you can|lumi|okay|"
                  r"yo|my friend|you|thank|"
                  r"고마워|고마워요|감사합니다|감사해요|부탁해|부탁해요|부탁합니다|루미야|제발))+[\s,.!?~]*$", re.I)
CANON_PLACE = "p3"      # a named marker is embedded as this one: the bank's wordings know it, any map's names work


def core(text, markers=()):
    """The words the bank compares: calls and fillers before ("hey Lumi, um"), politeness after ("please",
    "감사합니다") cut, and the one marker named written as CANON_PLACE ("go to the coffee corner" -> "go to p3")."""
    from assistant import brain
    t = TAIL.sub("", brain.CALLING.sub("", plain(text))).strip(" ,.!?~") or text
    named = [m for m in markers if brain.named_place(t, m, markers)]
    if len(named) == 1:
        low = brain._norm(t, markers)
        swapped = re.sub(rf"(?<![a-z0-9])(?:the )?{re.escape(named[0].lower())}(?![a-z0-9])", CANON_PLACE, low)
        if swapped != low:
            t = swapped
    obj = re.compile(rf"(?:(?:{brain._COL})\s*)?(?<![a-z])(?:{brain._OBJ})s?(?![a-z])", re.I)
    t = obj.sub(lambda m: "컵" if re.search(r"[가-힣]", m.group(0)) else "cup", t)   # any object as "cup": the verb decides
    t = re.sub(r"컵를", "컵을", re.sub(r"컵가(?![가-힣])", "컵이", re.sub(r"컵는", "컵은", t)))
    for rx, canon in AMOUNT:
        t = rx.sub(canon, t)
    t = SAID.sub(lambda m: " 90 degrees" if re.search(r"(?:degrees?|도|°)$", m.group(0)) else " 1 meter", t)
    return re.sub(r"\s+", " ", t).strip()


def kind_of(text, markers=()):
    """The bank's kind for these words (a QUICK kind or "arm_*"), or None when it is not sure or it is "no"."""
    from assistant import knowledge
    vecs, kinds = _load()
    try:
        q = knowledge.embed([core(text, markers)])[0]
    except OSError as e:                               # no embedding server: the LLM decides
        print(f"intent bank: {e}")
        return None
    sims = vecs @ q
    kinds = np.where(kinds == "fetch", "pick", kinds)   # pick or fetch: one kind here, the words decide (_slot)
    order = np.argsort(-sims)[:AGREE_K]
    best = kinds[order[0]]
    if best not in ACTS or sims[order[0]] < SIM_MIN or any(kinds[i] != best for i in order):
        return None
    if sims[order[0]] - sims[kinds != best].max() < MARGIN:
        return None
    return str(best)


# ---------- slots: what the words themselves say ----------
DIR = {"forward": r"\b(?:forward|forwards|forword|ahead|straight)\b|\bto the front\b|앞으로|앞쪽|^\s*앞|forward로",
       "back": r"\b(?:back|backward|backwards|reverse|bak)\b|뒤로|후진|뒤쪽|물러",
       "left": r"\bleft|\blef\b|왼쪽|왼편|좌측", "right": r"\bright\b|\brite\b|오른쪽|오른편|우측"}


CARRY = (r"\b(?:bring(?! yourself)|fetch|deliver|carry)\b|\bget me\b|\b(?:to|for) me\b(?=.*\b(?:bring|get|fetch|hand|pass)\b)|"
         r"\bget(?:ting)?\b.*\bfrom\b|\bgo get\b|가져|갖다|가지고 ?와|가져다|챙겨 ?(?:와|다)|갖고 ?와")    # words that bring a thing to someone
COME_VERB = (r"\bcome\b|\bcum\b|\bkum\b|\bget over\b|\bapproach|\bcloser\b|\bhither\b|\bnear me\b|"
             r"\bget closer\b|\broll over\b|\bdrive over\b|\bmy side\b|\bnext to me\b|\bto me\b|와|오세요|오십시오|오시|올래")
LIFT_SAID_MAX_M = 0.3   # m; a longer lift amount said is no lift request ("grow to three meters tall")
LIFT_BODY = (r"\b(?:yourself|your (?:body|torso|upper body)|body|make you|taller|shorter|smaller|small|tall|high|lift|rise|grow|"
             r"shrink|come down|go up|go down|move up|move down|raise up|lower down|come up|sink down|elevate|squat|height|"
             r"stretch up|drop down|going down|going up)\b|위로|아래로|낮아|높아|"
             r"키|몸|리프트|상체|높게|낮게|높이|커져|작아져|올라|내려가|업\b|다운")


MOVE_VERB = (r"\b(?:move|go|step|back up|backup|scoot|slide|shift|drive|roll|reverse|inch|come|forward|backward|ahead|"
             r"moov|moove|bak)|가|이동|물러|비켜|후진|와|빠져|걸음|발짝|move|back|go")   # a bare "왼쪽으로" may be a look


LOOK_DIR = {"left": r"\bleft|왼|레프트", "right": r"\bright|\brite\b|오른|라이트",
            "up": r"\bup|\bupward|\bceiling|\bsky\b|\bhigher\b|천장|하늘|(?<!원)위", "down": r"\bdown|\bfloor|\bground|\bfeet\b|바닥|땅|아래|밑"}
LOOK_ME = (r"\b(?:at|on|to|toward|towards) (?:me|us|나)\b|\bthis way\b|\bover here\b|\bmy way\b|\bhere\b|\bwatch me\b|"
           r"\bme in the eye|\bmy face\b|나한테|저한테|쳐다봐|(?:^|\s)(?:여기|이쪽|저|나|날)(?:를|을)?\s*(?:좀\s*)?(?:봐|보세요|look)")


EN_NUM = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen "
                                    "fourteen fifteen sixteen seventeen eighteen nineteen".split())}
EN_NUM.update({w: 10 * i for i, w in enumerate("twenty thirty forty fifty sixty seventy eighty ninety".split(), 2)})
KO_DIGIT = dict(zip("일이삼사오육칠팔구", range(1, 10)))
UNIT = [(r"m|meters?|metres?|미터", 1.0), (r"cm|centimet(?:er|re)s?|센티(?:미터)?|센치", 0.01),
        (r"mm|millimet(?:er|re)s?|밀리(?:미터)?", 0.001)]   # feet / inches: asked (driving.read refuses them)
_EN_WORDS = "|".join(sorted(EN_NUM, key=len, reverse=True)) + "|hundred|and|a|point"
SAID = re.compile(rf"((?:\d+(?:\.\d+)?|(?:(?:{_EN_WORDS})[\s-]*)+|[일이삼사오육칠팔구십백]+))\s*"
                  rf"(?:{'|'.join(u for u, _ in UNIT)}|degrees?|도|°)(?=만|[^a-z가-힣]|$)", re.I)


def _number(words):
    """'eight' / 'a hundred and eighty' / '삼십' / '12.5' -> the number, or None."""
    w = words.strip().lower()
    if re.fullmatch(r"\d+(?:\.\d+)?", w):
        return float(w)
    if re.fullmatch(r"[일이삼사오육칠팔구십백]+", w):
        total, digit = 0, 0
        for c in w:
            if c in KO_DIGIT:
                digit = KO_DIGIT[c]
            else:
                total += (digit or 1) * (10 if c == "십" else 100)
                digit = 0
        return float(total + digit)
    if re.search(r"\bpoint\b", w):                   # "point five", "one point five"
        whole, _, frac = w.partition("point")
        a = _number(whole) if whole.strip() else 0.0
        b = [_number(x) for x in frac.split()]
        if a is None or not b or None in b or any(x > 9 for x in b):
            return None
        return a + float("0." + "".join(f"{x:g}" for x in b))
    total, cur = 0, 0
    for x in re.split(r"[\s-]+", w):
        if x in EN_NUM:
            cur += EN_NUM[x]
        elif x == "hundred":
            cur = (cur or 1) * 100
        elif x not in ("and", "a", ""):
            return None
    total += cur
    return float(total) if total or re.search(r"\bzero\b", w) else None


def said_amount(text):
    """(metres, degrees) said with a unit, numbers in digits or words ("a quarter of a meter", "eight centimetres",
    "오십 센티", "a hundred and eighty degrees", "삼십 도"); each None when not said."""
    t = (text or "").lower()
    metres = degrees = None
    if re.search(r"\bquarter of an? (?:meter|metre)\b", t):
        metres = 0.25
    elif re.search(r"\bhalf an? (?:meter|metre)\b|(?:^|\s)반 ?미터", t):
        metres = 0.5
    parts = []                                       # (metres, unit factor) in the order said
    for m in SAID.finditer(t):
        n = _number(re.sub(r"^(?:a|and)\s+", "", m.group(1).strip()) or m.group(1))
        unit = t[m.end(1):m.end()].strip()
        if n is None:
            continue
        if re.fullmatch(r"degrees?|도|°", unit):
            degrees = n
        else:
            f = next(f for u, f in UNIT if re.fullmatch(u, unit))
            parts.append((n * f, f))
    if parts:                                        # "1미터 50센티": 1.5; "30 cm, sorry, 20 cm": not read (nan)
        ok = all(a[1] > b[1] for a, b in zip(parts, parts[1:]))
        metres = sum(x for x, _ in parts) if ok else float("nan")
    if metres is not None and re.search(r"\band a half\b|미터 ?반", t):
        metres += 0.5
    return metres, degrees


FOLLOW_WORD = (r"\bfollow|\bfallow|\bfollo\b|\bwith (?:me|us)\b|\balong\b|\bbehind me\b|\bafter me\b|\bbeside me\b|\bmy side\b|"
               r"\bwhere i go\b|\bwhere i walk\b|\bshadow\b|\bescort|\baccompany|\btrack me|\bkeep (?:up|close)|\bstick with|"
               r"\bstay (?:with|behind|right behind)|\bnext to me\b|\bcoming with\b|\bgo with\b|따라|딸아|쫓아|같이|함께|팔로우|"
               r"\bwalk together\b")


LETTER = {"a": "a", "ay": "a", "에이": "a", "b": "b", "be": "b", "bee": "b", "비": "b", "c": "c", "see": "c", "sea": "c",
          "씨": "c", "d": "d", "dee": "d", "디": "d", "e": "e", "이": "e", "f": "f", "에프": "f"}


def _other_suffix(text, marker):
    """The words name the marker's base with a different letter or number after it ("exit a" for Exit_B, "booth 13"
    for Booth_12, "부스 13" for 부스12): a place that is not on the map, never the near marker."""
    m = re.fullmatch(r"(.+?)[\s_-]*([a-z]|\d+)", marker.lower())
    if not m:
        return False
    base, suffix = m.groups()
    for x in re.finditer(rf"{re.escape(base)}[\s_-]*(?:number\s+|no\.?\s*|넘버\s*)?([a-z0-9가-힣]+)", text.lower()):
        tok = x.group(1)
        if re.match(r"\d", tok):
            said = re.match(r"\d+", tok).group(0)
        elif tok in LETTER and len(suffix) == 1 and not suffix.isdigit():
            said = LETTER[tok]
        elif _number(tok) is not None and suffix.isdigit():
            said = f"{_number(tok):g}"
        else:
            continue
        if said != suffix:
            return True
    return False


def _to_person(text):
    """Someone other than the speaker named as who gets it or where they are: "안나한테 갖다줘", "사라는 부스 투에 있어",
    "John is at p4, bring him a cup" (a mission: the rules / LLM)."""
    from assistant import brain
    for m in re.finditer(r"([가-힣]+)(?:한테|에게|께)(?![가-힣])", text):
        if m.group(1) not in ("나", "저", "내", "제", "우리", "저희"):
            return True
    m = re.search(r"([가-힣]+)(?:은|는)\s.*에\s*있", text)
    if m and m.group(1) not in brain.OBJECTS and not any(m.group(1).startswith(o) for o in brain.OBJECTS):
        return True
    if re.search(r"님(?![가-힣])|님(?:은|이|께|한테)|계셔|계시|계세요|드려|드리", text):
        return True                                    # "김 부장님 라운지에 계셔, 사과 좀 갖다 드려": to someone honoured
    return bool(re.search(r"\b[A-Z][a-z]+(?: is|'s) (?:at|in|by|over)\b", text))


def _dirs(t):
    return [d for d, rx in DIR.items() if re.search(rx, t)]


def _slot(kind, text, markers, holding):
    """The (action, target) lumi.quick_command takes, or None when the words don't say it plainly."""
    from assistant import brain, driving
    t = brain._norm(text, markers)
    if kind == "go_to":
        if brain._mentions(text, markers).get("object") or re.search(r"\bfrom\b|에서|에 있는|\bface\b|\blook|\bpoint|봐|"
                                                                     r"\bwith (?:me|us)\b|같이|함께|따라|"
                                                                     + CARRY + r"|\btake (?:it|this|that|them)\b", t):
            return None                                # "get the bottle from booth two": a fetch, the rules' / LLM's
        named = [m for m in markers if brain.named_place(text, m, markers)]
        said = re.sub(r"\bp\s+(?=\d)", "p", text.lower())
        if len(named) != 1 or _other_suffix(text, named[0]) or re.search(r"\bp\d+", said) and \
                not re.search(rf"(?<![a-z0-9]){re.escape(named[0].lower())}(?![0-9])", said):
            return None                                # "exit a" with only Exit_B, "booth 13" with Booth_12: asked
        return ("go_to", named[0])
    if kind == "come" and (re.search(CARRY + r"|따라", t) or not re.search(COME_VERB, t)):
        return None                                    # "나한테 가져와", "이리 줘": not a trip to the person
    if kind == "come" and re.search(r"\bwith (?:me|us)\b|함께|같이", t):
        return ("follow", "")                          # "just come with me": walk along
    if kind == "come_back" and (re.search(r"\bpose\b|\barm\b|\bhead\b|팔|고개|\bpick|\bput\b|\bit\b|그거|놓|놔", t) or
                                any(brain.named_place(text, m, markers) for m in markers)):
        return None                                    # "go back to your dock", "go back to your look pose": not here
    if kind == "come_back" and re.search(r"\bhere\b|\bto me\b|이리|여기|나한테|저한테", t):
        return ("come", "")                            # "come back here": to the person, not to the old spot
    if kind == "follow" and (re.search(r"\bfollow (?:you|him|her|them|it|that)\b", t) or not re.search(FOLLOW_WORD, t)):
        return None                                    # "follow you": not "follow me"; "가자 이제": let's go, where?
    if kind == "wave" and re.search(r"\bto you\b|너한테|너에게", t):
        return None                                # "wave to you": Lumi's own words back, or about Lumi
    if kind == "wave" and (holding() if callable(holding) else holding):
        return None                                    # a wave with a cup in the hand: the LLM says why not
    if kind in ("come", "follow", "come_back", "wave"):
        return (kind, "")
    if kind == "move":
        if re.search(r"\bturn|\brotat|\bspin|\bpivot|\bswivel|\bface\b|돌|회전|도세요|도십시오|(?:^|\s)돌?아(?:\s|$)", t) or \
                not re.search(MOVE_VERB, t):
            return None                                # "turn left a bit", "왼쪽으로 도세요": a turn, not a drive
        if re.search(r"\b(?:some|more than|less than|few|several|couple)\b|\b(?:to|too) (?:meters?|metres?|m)\b", t):
            return None                                # "move back some", "forward to meters": how far? asked
        d = _dirs(t)
        n = said_amount(text)[0]
        n = driving.amount(re.sub(r"(?:^|\s)좀(?=\s)", " ", t))[0] if n is None else n   # "뒤로 좀 가": 좀 is "please"
        if re.search(r"\b(?:third|fourth)\b", t) or n is None and re.search(r"\b(?:half|meters?|metres?|cm|centimet\w*|inch\w*|feet|foot|yards?)\b|미터|"
                                   r"센티|\d", t):
            return None                                # an amount the words say but driving.amount does not read
        n = driving.DEFAULT_M if n is None else n
        if len(d) != 1 or n == "?" or not driving.MOVE_MIN_M <= n <= brain.MOVE_MAX_M:
            return None
        return ("move", f"{d[0]} {n:g}")
    if kind == "turn":
        if re.search(r"\blook|봐|\bhead\b|고개|\beyes\b", t):
            return None                                # "look the other way": the head, not the base
        if re.search(r"\bspin\b|\ball the way (?:a)?round\b|\b360\b|한 ?바퀴", t) and \
                not re.search(r"\bface\b|\bother (?:side|way)\b|\d+\s*(?:degrees?|도)", t.replace("360", "")) and \
                said_amount(text)[1] in (None, 360):
            return ("turn", ("right" if re.search(r"\bright\b|오른쪽", t) else "left") + " 360")
        if re.search(r"\baround\b|\bu-?turn\b|유턴|뒤로 돌|뒤돌|\bother way\b|\babout face\b|한 바퀴", t):
            return None if re.search(r"\bleft|\bright\b|왼|오른", t) else ("turn", "around 180")
        d = [x for x in _dirs(t) if x in ("left", "right")]
        if not d and said_amount(text)[1] == 180:
            return ("turn", "around 180")                # "rotate a hundred and eighty degrees"
        if len(d) != 1:
            return None
        deg = re.search(r"(\d+)\s*(?:degrees?|도|°)", t)
        words_deg = said_amount(text)[1]
        if not deg and words_deg:
            return ("turn", f"{d[0]} {words_deg:g}")
        if not deg and re.search(r"\bdegrees?\b|[가-힣]\s*도(?:만)?\s", t + " ") and not re.search(r"(?:^|\s)(?:한|좀)\s", t):
            return None                                # "삼십 도": a number the words don't give as digits
        if not deg and re.search(r"\d", t):
            return None                                # "turn left 30.": a number with no unit, asked
        return ("turn", f"{d[0]} {deg.group(1) if deg else 90}")
    if kind == "look":
        if re.search(r"\byour back\b|\bback to me\b|등 ?돌", t):
            return None                                # "turn your back to me": the base turns away
        target = "center" if re.search(r"원위치|원래대로|\breset\b", t) else brain.head_target(t)
        if target is None:
            dirs = [d for d, rx in LOOK_DIR.items() if re.search(rx, t)]
            if re.search(r"\baway\b|\bavert|딴 ?데|다른 ?데|시선", t):
                target = "away"
            elif re.search(r"\b(?:front|forward|center|centre|middle|reset|straighten)\b|원위치|원래대로|가운데|정면|앞에", t):
                target = "center"
            elif len(dirs) == 1:
                target = dirs[0] + (" small" if brain.SMALL.search(t) else "")
            elif not dirs and re.search(LOOK_ME, t):
                target = "me"
        return ("look", target) if target else None
    if kind == "lift":
        if not re.search(LIFT_BODY, t):
            return None                                # "go upstairs": no word about Lumi's own height
        down = re.search(r"\b(?:down|lower|shorter|smaller|small|sink|shrink|squat)\b|낮|줄여|작게|작아|내려|아래|다운", t)
        up = re.search(r"\b(?:up|higher|taller|tall|high|bigger|raise|rise|grow|elevate|stretch)\b|높(?:여|게|아|혀)|키워|올려|"
                       r"커|올라|업", t)
        if bool(down) == bool(up):
            return None                                # no direction, or both: asked
        metres = said_amount(text)[0]
        if metres is not None:
            if not metres <= LIFT_SAID_MAX_M:            # also nan: two amounts said
                return None                            # "grow to three meters tall": not a lift amount, the LLM answers
            return ("lift", f"{'down' if down else 'up'} {metres * 1000:g}")
        target = brain.lift_target(t).split(" ", 1)
        return ("lift", " ".join(["down" if down else "up"] + target[1:]))
    if kind.startswith("arm_"):
        pose = kind[4:]
        if pose == "reach" and re.search(r"줘|주세요|주십시오|\bgive\b|\bhand\b|\bover\b|\bpass\b", t) and \
                (holding() if callable(holding) else holding):
            return None                                # "손 줘" with a cup held: hand it over, the hand reader's
        if pose in ("open", "close"):
            held = holding() if callable(holding) else holding
            if held:
                return None                            # an open hand drops what it holds: brain.hand_request's
        return ("arm", pose)
    if kind in ("pick", "fetch"):
        got = brain._mentions(text, markers)
        if not got.get("object") or re.search(r"\b(?:a|one|two) (?:cup|glass|bottle) of\b|한 ?잔|두 ?잔|아메리카노|라떼|"
                                              r"\b(?:americano|latte|coffee|tea|juice)\b|주스|음료|먹|마셔|마시|"
                                              r"\b(?:throw|toss|kick|break|eat|drink|wash|clean|buy|sell|"
                                              r"put|place|set|drop|leave|this|hold (?:this|my|it|on)|my)\b|놔|놓|내려", t) or \
                not re.search(CARRY, t) and re.search(r"\bfrom\b|\bgo get\b|에서", t) or \
                (holding() if callable(holding) else holding):
            return None                                # "put the banana on the table", "hold this apple": the hand's
        if re.search(r"\b(?:give|hand|pass)\b|건네", t) or \
                re.search(r"줘|주세요|주실|줄래", t) and not re.search(r"집|잡|들어|쥐|픽|pick|grab|take|" + CARRY, t):
            return None                                # "컵 좀 줘": bring it to me, a mission (pick, then give)
        if re.search(CARRY, t):                        # "bring me the cup", "컵 가져와": a fetch
            if re.search(r"\b(?:him|her|them)\b", t) or _to_person(text) or \
                    "source" in got and got["source"] is None or "dest" in got and got["dest"] is None or \
                    re.search(r"\bgo\b|가서|\bwhere\b", t):
                return None                            # "from the cafeteria" (not on the map), "go home, bring it": asked
            return ("fetch", text)
        if got.get("source") or got.get("dest") or any(brain.named_place(text, m, markers) for m in markers) or \
                re.search(r"\b(?:to|at|ask|tell|say|pass\w*|want|need|is on|are on)\b|있는|옮겨|에게|한테|께", t):
            return None                                # "take the cup to p4", "I want the mug, the one at the entrance"
        return ("pick", f"{got['colour']} {got['object']}" if got.get("colour") else got["object"])
    if kind == "put":
        if not (holding() if callable(holding) else holding):
            return None                                # nothing held: lumi says the hand is empty (rules / LLM)
        if brain.place_on(t) or re.search(r"\b(?:on|onto|in|into) (?:the|a|my)\b|위에|에다", t):
            return None                                # "put it on the table": a place, the hand reader's
        return ("put", "back" if re.search(r"\bback\b|제자리|원래|다시|도로", t) else "down")
    return None


def read(text, markers=(), holding=False):
    """(action, target) as brain.intent gives it, when the bank is sure; else None (the LLM reads it)."""
    said, text = text, plain(text)
    if guarded(text):
        return None
    kind = kind_of(text, markers)
    got = _slot(kind, text, markers, holding) if kind else None
    return ("fetch", said) if got and got[0] == "fetch" else got


if __name__ == "__main__":
    if sys.argv[1:] == ["build"]:
        CACHE.unlink(missing_ok=True)
        n = len(_load()[1])
        print(f"{n} wordings -> {CACHE}")
    else:
        from tests.conversation_check import markers as _markers
        for said in sys.argv[1:]:
            print(said, "| guard:", guarded(said), "| kind:", kind_of(said), "| read:", read(said, _markers()))
            for s, k, w in nearest(said)[0]:
                print(f"   {s:.3f} {k:10} {w}")
