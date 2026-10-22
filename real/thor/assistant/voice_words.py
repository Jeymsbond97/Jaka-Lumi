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


def read(text, last=""):
    """("volume" | "speed", +1 | -1) when the words ask Lumi to speak louder / quieter / faster / slower, else None.
    `last` is the assistant's answer just before (brain history): after "ACTION: voice volume +1" a bare "more" /
    "again" / "조금 더" asks for the same again."""
    t = text or ""
    again = re.match(r"ACTION: voice (volume|speed) ([+-]1)\b", last or "")
    if again and driving.AGAIN.search(driving.clean(t)):
        return again.group(1), int(again.group(2))
    if DRIVE.search(t) and not VOICE.search(t) or driving.move(t):
        return None                                        # "go faster", "천천히 가", "turn it up 30 degrees"
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
