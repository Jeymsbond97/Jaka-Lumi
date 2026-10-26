"""Lumi's speaking volume and speed as people ask for them, in English, Korean and mixed.

    louder: "speak louder", "a bit louder", "I can't hear you", "speak up", "더 크게 말해", "안 들려", "소리 좀 키워"
    quieter: "speak quieter", "too loud", "lower your voice", "소리 좀 줄여", "너무 시끄러워", "작게 말해"
    slower / faster: "speak slower", "you talk too fast", "talk faster", "천천히 말해", "말이 너무 빨라", "빨리 말해"
    right after one of them: "a bit more", "again", "even more", "조금 더", "한 번 더" repeat it

The drive speed is assistant/driving.py: a speed word counts here only with a voice word (speak / talk / say /
voice / 말 / 목소리) and never with a drive word ("go faster", "천천히 가"). The volume is the speaker's mixer
(audio/mouth.py set_volume, data/volume.txt, also set from the dashboard), the speed Supertonic's speed (mouth.speed).

    python assistant/voice_words.py "speak a bit louder"
"""
import re
import sys

from assistant import driving
from audio import mouth

VOLUME_STEP = 10             # % of the speaker mixer per "louder" / "quieter"
VOLUME_MIN, VOLUME_MAX = 30, 90   # %; voice commands stay inside (100 % disturbed people in the office)
SPEED_STEP = 0.1             # Supertonic speed per "slower" / "faster" (mouth.SPEED_MIN / SPEED_MAX clamp it)

LOUDER = re.compile(r"\blouder\b|\bspeak up\b|\b(?:can'?t|cannot|can not|couldn'?t|could not|don'?t) (?:really )?hear "
                    r"(?:you|that|it|anything|what you)|\bhard to hear\b|\btoo (?:quiet|soft|low)\b|"
                    r"\b(?:volume|sound) up\b|\bturn (?:it |the volume |the sound |your voice |yourself )?up\b|"
                    r"\b(?:raise|increase) (?:your |the )?(?:voice|volume)\b|\bmore loudly\b|"
                    r"크게|안\s*들려|잘\s*안\s*들|안\s*들리|들리지\s*않|(?:소리|볼륨|목소리)\s*(?:를|을|좀|\s)*(?:키워|올려|높여)|"
                    r"(?:소리|목소리)\S*\s*너무\s*작", re.I)
QUIETER = re.compile(r"\bquieter\b|\bsofter\b|\btoo loud\b|\bnot so loud\b|\bless loud\b|\bso loud\b|"
                     r"\b(?:lower|turn down|drop) (?:your |the )?(?:voice|volume|sound)\b|\b(?:volume|sound) down\b|"
                     r"\bturn (?:it |yourself )?down\b|\b(?:speak|talk) (?:more )?(?:quietly|softly)\b|"
                     r"작게|시끄러|(?:소리|볼륨|목소리)\s*(?:를|을|좀|\s)*(?:줄여|낮춰|내려)|(?:소리|목소리)\S*\s*너무\s*커", re.I)
VOICE = re.compile(r"\b(?:speak|speaking|talk|talking|say|saying|said|voice|speech|words)\b|말|얘기|이야기|목소리", re.I)
SLOW = re.compile(r"\b(?:slower|slowly|slow down)\b|천천히|느리게|느릿", re.I)
FAST = re.compile(r"\b(?:faster|quicker|quickly|speed up)\b|빨리|빠르게", re.I)
TOO_FAST = re.compile(r"\b(?:too|so) fast\b|(?:너무|넘)\s*빨라|빠르네|빨라요", re.I)
TOO_SLOW = re.compile(r"\b(?:too|so) slow(?:ly)?\b|(?:너무|넘)\s*느려|느리네|느려요", re.I)
DRIVE = re.compile(r"\b(?:go|going|drive|driving|move|moving|walk|come|run|follow|forward)\b|"
                   r"달려|돌아|움직|이동|따라|가\s*줘|가요|가라|가세요|와\s*줘|(?:^|\s)가(?:\s|$)", re.I)

SAY = {("volume", 1): ("Is this better?", "이제 잘 들리세요?"),
       ("volume", -1): ("Okay. Is this better?", "네, 이 정도면 괜찮으세요?"),
       ("speed", -1): ("Okay, I'll speak more slowly. Is this better?", "네, 천천히 말할게요. 이 정도면 괜찮으세요?"),
       ("speed", 1): ("Okay, I'll speak a little faster.", "네, 조금 빨리 말할게요.")}
AT_LIMIT = {("volume", 1): ("This is as loud as I can speak.", "이게 제일 큰 목소리예요."),
            ("volume", -1): ("This is as quiet as I can speak.", "이게 제일 작은 목소리예요."),
            ("speed", -1): ("I can't speak any slower than this.", "이보다 더 천천히는 말할 수 없어요."),
            ("speed", 1): ("I can't speak any faster than this.", "이보다 더 빨리는 말할 수 없어요.")}


NOT_NOW = re.compile(r"(?:^|\s)(?:쟤|걔|저 사람|그 사람|저분|그분)(?:는|가|도|은)?\s|\b(?:he|she|they|his|her|their)\b|"
                     r"(?:할|될|볼)걸\W*$|겠지\W*$|\bwhenever\b|끝나(?:고|면)|고 ?나서|(?:다음|후|뒤)에\s", re.I)
    # someone else ("쟤 좀 작게 얘기하는 거 못 할걸"), a guess, a rule for later ("whenever I whistle, speed up")


def _not_now(t):
    """Words that name a voice change but ask none now: a later time / condition, someone else, a take-back."""
    from assistant import brain, intent_bank
    if NOT_NOW.search(t) or intent_bank.told_ko(t) or brain.held_back(t) or re.search(r"[\"“”]|라고|래서|하래", t):
        return True                                        # a quote: "게임에서 자꾸 말 천천히 하라고 나와"
    if intent_bank.NEGATION.search(t) and not re.search(r"\bso (?:fast|loud|quiet|slow)|\btoo\b|너무", t, re.I):
        return True                                        # "don't talk louder" (not "don't speak so fast")
    if re.search(r"\b(?:are you able|able to|know how to|how (?:do|can|could) you|is it possible|can you even|capable of|"
                 r"built to|made to|designed to)\b|할 ?줄|줄 ?알|가능(?:해|한|하)|어떻게", t, re.I) or \
            intent_bank.SELF_TALK.search(t) or intent_bank.PAST_EN.search(t) or intent_bank.past_ko(t):
        return True                                        # "were you built to ...", "you were too loud yesterday"
    name = intent_bank.NAME_CALL.match(t)
    if name and name.group(1).lower() not in intent_bank.NOT_A_NAME or brain.to_someone_else(t):
        return True                                        # "Jake, talk quieter"
    if intent_bank.LATER.search(t) and not re.search(r"\bif you (?:can|could|don'?t mind|please|would)\b|\bso i can\b", t, re.I):
        return True                                        # "쉬는 시간 끝나고 목소리 좀 크게 해"
    return brain.self_correct(t) == ""                     # "볼륨 up 해 줄 수 있어, 아 cancel"


def read(text, last=""):
    """("volume" | "speed", +1 | -1) when the words ask Lumi to speak louder / quieter / faster / slower, else None.
    `last` is the assistant's answer just before (brain history): after "ACTION: voice volume +1" a bare "more" /
    "again" / "조금 더" asks for the same again."""
    t = text or ""
    again = re.match(r"ACTION: voice (volume|speed) ([+-]1)\b", last or "")
    if again and driving.AGAIN.search(driving.clean(t)):
        return again.group(1), int(again.group(2))
    if re.search(r"(?:^|\s)(?:키|몸|리프트)(?:를|좀|\s)*(?:크게|작게|높게|낮게)", t):
        return None                                        # "키 크게 해 줘": the lift, not the voice
    if DRIVE.search(t) and not VOICE.search(t) or driving.move(t):
        return None                                        # "go faster", "천천히 가", "turn it up 30 degrees"
    if (LOUDER.search(t) or QUIETER.search(t) or SLOW.search(t) or FAST.search(t)) and _not_now(t):
        return None
    up, down = bool(LOUDER.search(t)), bool(QUIETER.search(t))
    if up != down:
        return "volume", 1 if up else -1
    if not VOICE.search(t) or DRIVE.search(t):
        return None
    if TOO_FAST.search(t) or TOO_SLOW.search(t):
        return "speed", -1 if TOO_FAST.search(t) else 1
    slow, fast = bool(SLOW.search(t)), bool(FAST.search(t))
    return ("speed", -1 if slow else 1) if slow != fast else None


def apply(kind, sign, lang="en"):
    """Change the volume or the speed one step (inside the limits) and return what Lumi says about it, said at the
    new setting."""
    if kind == "volume":
        old = mouth.volume()
        new = min(max(old + sign * VOLUME_STEP, VOLUME_MIN), VOLUME_MAX)
        changed = (new - old) * sign > 0
        if changed:
            mouth.set_volume(new)
    else:
        old = mouth.speed()
        new = round(min(max(old + sign * SPEED_STEP, mouth.SPEED_MIN), mouth.SPEED_MAX), 2)
        changed = (new - old) * sign > 1e-6
        if changed:
            mouth.set_speed(new)
    en, ko = (SAY if changed else AT_LIMIT)[(kind, sign)]
    return en if lang == "en" else ko


if __name__ == "__main__":
    print(read(" ".join(sys.argv[1:])))
