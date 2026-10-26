"""Singing: play one of the owner's songs (data/songs/mine/<id>.wav, made by audio/sing_mine.py from the owner's own
files, local only, never copied off the robot) and move the head with it. Lumi sings only these.

    python audio/sing.py                  # list the songs
    python audio/sing.py <id>             # sing one (plays on the speaker and moves the head)

Each <id>.json holds the title, the names it is asked by, the lyrics and the head moves timed to the beat. The song
is played through mouth._play (the microphone is muted the same way as for speech,
and abort() stops it within 50 ms). The head turns to yaw 0 / pitch 0 and dances around it in a thread, following the
music: small diagonal bobs landing on the beats in energetic parts, a quick sweep with a dip on a bar's accent or a
phrase start, slower sways in calm parts, each move called early enough (the owner's measured head timing) to land
on its beat, one call at a time; it goes back to yaw 0 / pitch 0 when the song ends or is stopped. Never the lift, the waist or the arm.
"""
import difflib
import json
import pathlib
import random
import re
import sys
import threading
import time

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
MINE = ROOT / "data" / "songs" / "mine"   # the owner's songs: local only
YAW_SWAY = 40.0                 # deg; head yaw stays within +- this while singing (owner: wider, 2026-10-21)
PITCH_RANGE = (0.0, 28.0)       # deg, absolute head pitch while singing (0 = level, + = up; owner: higher)
# head timing measured by the owner (2026-10-20, body API, vel = acc = 100, head.status polled every 20 ms): the head
# starts 0.2 s after the call and turns ~40 deg/s after that (15 / 6 deg diagonal reached at 0.87 s, 25 / 10 deg at
# 1.12 s); the call returns ~0.1 s after it arrives. Speed is no higher above vel 50. Overlapping moveto calls hang
# the body API: a move is sent only after the last one returned.
REACH_S = 0.5                   # s from the call until a small move arrives (start delay + speeding up)
RETURN_S = 0.6                  # s from the call until it returns, for a small move
HEAD_DEG_S = 40.0               # deg/s of the larger axis at vel >= VEL_FULL
VEL_FULL = 50                   # speed ratio % from which the head is at its full speed
VEL_LIVELY, VEL_CALM, VEL_CALMEST = 100, 100, 80   # speed ratio %: energetic / calm / the calmest parts
ENERGETIC = 0.4                 # music energy (0..1) from which the head bobs on the beat
CALMEST = 0.15                  # below this energy the head sways slowly
BOB_DEG = (7.0, 12.0)           # deg, a beat's bob (diagonal nod / tilt), alternating sides
ACCENT_DEG = (25.0, 38.0)       # deg, a bar's or phrase's accent: a quick sweep with a dip
SWAY_DEG = (12.0, 20.0)         # deg, a calm sway
ACCENT_EVERY_S = 1.2            # s, at least this between two accents
CENTRE_PITCH = 12.0             # deg; the dance moves around yaw 0, this pitch
GAP_S = 0.02                    # s between a call returning and the next one
MIN_CHANGE = (1.5, 0.8)         # deg; every move changes yaw and pitch at least this much
MIN_TURN_DEG = 20.0             # two moves in a row differ in direction by at least this (never one line)
HEAD_VEL = 70                   # speed ratio % for turning to yaw 0 / pitch 0 before and after the song
LATE_S = 0.4                    # s; a move this late is skipped (the previous one took longer)
RETURN_WAIT_S = 3.0             # s a new song waits for the head to get back from the last one
BANK_SIM = 0.80                 # song bank (assistant/song_bank.py): the closest wording at least this similar ...
BANK_MARGIN = 0.05              # ... and this much closer than the closest wording of another kind
BANK_MIN_WORDS = 3              # the bank reads only words with a song or music word in them and at least this many
                                # words ("Let's", cut off from "Let's follow me", sang once, 2026-10-22)
SONG_WORD = re.compile(r"\bsing|\bsong|\bmusic|\btunes?\b|\bplaylist|k-?pop|노래|노레|노랠|음악|곡|불러|부르|틀어|들려|케이팝", re.I)

SING = re.compile(r"\bsing\b|\bsay (?:a |some )?songs?\b|"                    # whisper writes "let's say song"
                  r"\b(?:play|put on|turn on|start)(?: me| us)? (?:a |some |any |another |the |your )?(?:songs?|music|tunes?)\b|"
                  r"\b(?:another|different|next|new|other) (?:song|tune)\b|\b(?:change|switch)(?: the| this| that)? (?:songs?|music|tunes?)\b|"
                  r"(?:노래|음악|곡)\s*(?:좀\s*)?바꿔|\b(?:(?:want|like|love) to|(?:can|could|may) (?:we|i)) hear (?:a |some |one of your )?(?:songs?|music)\b|\bgive (?:us|me) (?:a |some )?(?:song|tune|music)\b|"
                  r"^\W*(?:lumi\W*)?(?:a |some )?(?:song|music)(?:\W+(?:please|lumi))*\W*$|"
                  r"(?:노래|음악|(?<![가-힣])곡|(?<![가-힣])송)\s*(?:를|을|좀|쫌|쪼까|쪼끔|하나|한\s*곡조?|한\s*번|한번|함|한\s*자락|자락|도|이나|나|이든|든|라도|\s)*"
                  r"(?:불러|부르|들려|해|틀어|틀|뽑아|땡겨|부탁|재생|플레이|싱\s*(?:해|하)|(?:할|부를)\s*수\s*있)|(?<![가-힣])싱\s*(?:좀\s*)?해\s*(?:줘|주|봐)|"
                  r"노래\s*(?:좀|하나)?\s*(?:듣고\s*싶|들을래|듣자)|\b(?:songs?|music)\s*(?:좀\s*|하나\s*|한\s*곡\s*)?(?:불러|해|틀어|들려)|"
                  r"(?<![가-힣])(?:거|것)\s*(?:로\s*)?한\s*곡|(?:다른|딴|다음)\s*(?:노래|곡)|(?:다른|딴)\s*(?:거|걸|걸로)\s*(?:불러|들려|틀어)|^\W*(?:노래|음악)\s*(?:좀|하나)?\W*$", re.I)
SING_TITLE = re.compile(r"(불러|들려|틀어) ?(줘|주세요|줄래|봐|볼래)|\b(?:sing|play)\b")    # "러브 어택 불러 줘": a title said with it
TITLE_ASKED = re.compile(r"불러|들려|틀어|불르|부르[시세십실게자]|부를\s*수|플레이|(?<![가-힣])송(?![가-힣])|(?<![가-힣])싱(?![가-힣])|"
                         r"\bplease\b|플리즈|\bhear\b|한\s*번만|\byou sing\b|\bcan (?:we|i) get\b", re.I)
    # with one of our titles: "배드 불러 주라", "Love Attack 부르시게", "I'd love to hear Love Attack", "Fantastic Baby 플레이 해 줘"
SONG_LIST = re.compile(r"\b(?:what|which) (?:kinds? of |sort of |other )?(?:songs?|music|tunes)\b|\b(?:what|hwat|wat|whta) (?:can|do|would|will) you sing\b|"
                       r"(?<!sing a )(?<!sing one )(?<!sing me a )(?<!sing us a )\bsongs? (?:do |can |could )?you (?:know|sing|have)\b|\b(?:know|have) any (?:other )?songs\b|"
                       r"\b(?:list|names?) of (?:your |the )?songs\b|"
                       r"(?:무슨|어떤|뭔|어느)\s*(?:노래|곡)(?!\s*(?:이든|든|이나|나|라도))|노래\s*(?:는|를|은)?\s*(?:뭐|뭘|몇)|"
                       r"아는\s*노래|부를\s*(?:수\s*있는|줄\s*아는)\s*노래|노래\s*목록|(?:송|노래|곡|song)\s*리스트|\bsong\s*list\b|플레이\s*리스트|\bplaylist\b|what\s*songs", re.I)
NOT_REQUEST = re.compile(r"\b(?:do|did) you (?:really )?(?:like|love|enjoy)\b|"
                         r"\bwho sings?\b|\bfavou?rite\b|좋아하는|좋아해|잘\s*(?:해|하|불러)|"
                         r"^\W*(?:is|are|was|were|does|did|has|have)\b(?!\s+you\s+(?:able|willing)\s+to\s+sing\s+(?:a|some|me|us|for|something|one|another)\b)|\b(?:can|do|could) robots? (?:really |even )?sing\b|"
                         r"(?:노래|음악)\s*(?:하는|부르는)\s*로봇", re.I)   # "is Love Attack a new song?", "노래 부르는 로봇 신기하다"
NOT_ASKED = re.compile(r"\b(?:don'?t|do not|never)\s+(?:\w+\s+)?(?:sing|play)\b|\b(?:i|we)(?:'ll| will|'m going to)? sing\b|"
                       r"\b(?:i|we) (?:can'?t|cannot|can|could|used to) sing\b|\b(?:can|may|could|should) (?:i|we) sing\b|"
                       r"\b(?:later|tomorrow|tonight|next time|after (?:lunch|dinner|the|this|that|we|i)|"
                       r"when (?:the|they|i|we|guests?|everyone|people)|at the end)\b|"
                       r"\bif (?:the|they|i|we|you|he|she|guests?|kids?|someone|people|it)\b|"
                       r"\b(?:once|as soon as|whenever|until) (?:the|they|i|we|you|he|she|guests?|kids?|someone|people|it)\b|"
                       r"(?:손|박수|손뼉|신호)\s*(?:을|를)?\s*\S*\s*(?:면|때)\s|"   # "제가 손 들면 노래 불러 주세요": later, on a sign
                       r"(?:부를|할|하실|부르실)\s*줄\s*(?:알아|알아요|아세요|아시|아십|아니|아냐|아나|알지|알죠|압니까|알아유)"
                       r"(?!.*(?:불러|들려|틀어)\s*(?:줘|주))|\bdo you know how to sing\b|\b(?:are|r) you able to sing\W*$|"   # "노래 부를 줄 알아요?": an ability (quick answers)
                       r"\b(?:never ?mind|forget it|cancel that|actually,? no|on second thought)\b|아니다\s*(?:됐|그만|말자)|됐(?:어|다|습니다)\W*$|"
                       r"(?:끝나|오|되|돌아오|도착하|시작하)면\s|(?:제가|내가|우리가|저희가|애들이|아이들이|손님이|사람들이)\s+(?:\S+\s+){0,2}\S*[^안않]면\s|(?:부르는|하는|불렀던|부른) ?거 ?(?:봤|들었)|"
                       r"(?:부르|하|틀|불르)지\s*(?:마|말)|노래방|나중에|이따가?|있다가|끝나고|면\s*그때|(?:내가|제가)\s*(?:노래\s*)?"
                       r"(?:불러|부를|부르|할|노래\s*(?:해|하))|(?:불러|노래\s*해|노래해|틀어)도\s*(?:돼|되|괜찮)|"
                       r"^\W*(?:\w+\W+){0,3}?(?:why|how come|how (?:do|does|did|can|could) you)\b|왜|어째서|어떻게", re.I)
                       # "don't sing", "I'll sing later", "노래 부르지 마", "why can you sing?", "왜 손은 안 되고 노래는 돼?":
                                                                        # no song, also when the LLM says sing
# right after a song (or the list of songs): a short word switches or repeats it
AFTER_SONG = re.compile(r"^\W*(?:(?:lumi|ok|okay|no|nah|um|please|then|now|and)\W+)*(?:sing |play )?"
                        r"(?:another(?: one)?|(?:the )?next(?: (?:one|song|sog|son|tune))?|a different one|something (?:else|different)|"
                        r"not (?:this|that)(?: one)?|(?:it |that )?again|one more(?: time)?|once more|more|encore)"
                        r"(?:\W+(?:please|lumi))*\W*$|"
                        r"^\W*(?:(?:야야?|어이|자네|보소|저기요?|저기유|실례지만|실례합니다|죄송한데요|이보게|우리)\W*)*"
                        r"(?:(?:루미(?:루미)?|로봇)\s*(?:야|아|씨|님\s*(?:께서)?|군|양)?\W+)?(?:아니\W*)?(?:(?:그거|그\s*노래|이거|이\s*노래)\s*말고(?:\s*(?:다른|딴)\s*(?:거|걸로|노래))?|"
                        r"(?:다른|딴)\s*(?:거|걸|걸로|것)|다음\s*(?:거|곡|노래)?|넥스트(?:\s*송)?|앵콜|앙코르|한\s*번만?\s*더|하나\s*더|다시|또)"
                        r"\s*(?:요|줘|해\s*줘|해\s*봐|해|불러\s*줘|들려\s*줘|부탁해요?|해요|주세요)?\W*$", re.I)
SONG_OFFER = re.compile(r"\bshall i sing\b|\bwant to hear one\b|불러 드릴까요|들어 보실래요", re.I)   # Lumi's offer of a song
OFFER_YES = re.compile(r"^\W*(?:(?:야야?|어이|자네|보소|저기요?|저기유|실례지만|실례합니다|죄송한데요|이보게|우리)\W*)*"
                       r"(?:(?:루미(?:루미)?|로봇)\s*(?:야|아|씨|님\s*(?:께서)?|군|양)?\W+)?(?:(?:yes|yeah|yep|sure|ok(?:ay)?|please|of course|go ahead|why not|응|웅|어|네|예|좋아요?|좋습니다|좋제|좋지|그래요?|"
                       r"오케이|플리즈|아무거나|any(?:\s*one|thing)?(?: is fine)?|whatever|fine|"
                       r"불러\s*(?:줘|주세요|봐|보게|주라|주실래요)|해\s*봐|ㅋ+|ㅎ+|듣고\s*싶어요?|부탁해요?|해\s*(?:줘|주세요)|sing(?: it| one)?)(?:\W+|$))+$", re.I)
AGAIN = re.compile(r"\bagain\b|\bone more time\b|\bonce more\b|\bencore\b|한 ?번만? ?더|다시|앵콜|앙코르", re.I)
ANOTHER = re.compile(r"\b(another|different|next|other|change|switch)\b|바꿔|\bsomething else\b|\bnot (this|that)\b|다른|딴|다음|말고", re.I)
STOP = re.compile(r"\b(stop|enough|halt|quiet|shh+)\b|멈춰|그만|스톱|정지|조용", re.I)
KOREAN = re.compile(r"\bkorean\b|한국", re.I)
ENGLISH = re.compile(r"\benglish\b|영어", re.I)
FILLER = {"sing", "a", "an", "the", "song", "songs", "me", "us", "for", "please", "lumi", "some", "something", "now", "again",
          "one", "another", "different", "other", "next", "little", "short", "can", "you", "could", "would", "will", "to",
          "it", "that", "this", "together", "with", "and", "your", "nice", "hey", "hi", "ok", "okay", "play", "music",
          "in", "korean", "english", "else", "let's", "lets", "let", "now", "pretty", "beautiful", "my", "kids",
          "children", "children's", "cute", "fun", "favorite", "favourite", "of", "yours", "so", "just", "maybe", "then",
          "anything", "whatever", "any", "pls", "plz", "fun", "happy", "sad", "nice", "good", "new", "cool", "upbeat",
          "dance", "party", "slow", "fast", "quick", "famous", "popular", "love", "real", "first", "second", "third",
          "last", "same", "own", "k-pop", "kpop", "pop", "lively", "energetic", "cheerful", "exciting", "catchy", "best",
          "us", "them", "everyone", "everybody", "all", "guys", "people", "friends", "here", "today", "more", "ones",
          "our", "oh", "um", "uh", "hmm", "well", "loomi", "yo", "do", "does", "give", "hear", "want", "wanna", "need",
          "tune", "tunes", "number", "track", "by", "from", "bit", "on", "put", "start", "perform", "sing", "singing",
          "really", "very", "quiet", "loud", "soft", "calm", "short", "whole", "full", "yeah", "yes", "sure", "great",
          "awesome", "lovely", "sweet", "funny", "silly", "piece", "tell", "show", "make", "is", "are", "be", "i", "we",
          "sung", "lumie", "random", "pick", "choose", "and", "like", "say", "wish", "how", "about", "have", "time",
          "cheer", "up", "sin", "sink", "sum", "here", "kids", "listen", "listening", "would", "mind", "surprise",
          "change", "switch", "son", "sonf", "sog", "sogn", "snog", "sonng", "songg", "bro", "dude", "buddy", "robot", "grandma",
          "grandpa", "granny", "mom", "mum", "dad", "she", "he", "him", "her", "likes", "loves", "daughter", "sister",
          "brother", "friend", "wife", "husband", "kid", "guest", "guests", "na", "bestie", "dear"}   # slips of "song", the people sung to
UNKNOWN = {"en": ["Sorry, I can't sing that one. I only know my own songs: {}. Want one of them?",
                   "I don't know that song yet. I'd love to learn it someday! I can sing {}. Shall I sing one?",
                   "That one isn't in my songbook, sorry. My songs are {}. Would you like one of those?",
                   "Oh, I wish I could sing that one! For now I only know {}. Want to hear one?"],
           "ko": ["죄송해요, 그 노래는 아직 못 불러요. 제가 부를 수 있는 노래는 {}, 이렇게 {n}곡이에요. 하나 들어 보실래요?",
                  "아, 그 노래는 제가 몰라요. 언젠가 꼭 배워 보고 싶네요! 대신 {} 중에 하나 어떠세요?",
                  "그 노래는 아직 안 배웠어요. 저는 {}만 부를 수 있어요. 들어 보실래요?",
                  "아쉽지만 그 노래는 못 불러요. {} 중에서 고르시면 불러 드려요."]}
COUNT_KO = {1: "한 ", 2: "두 ", 3: "세 ", 4: "네 ", 5: "다섯 ", 6: "여섯 "}
LIST = {"en": "I can sing {}. Which one would you like?", "ko": "{} 부를 수 있어요. 어떤 노래 불러 드릴까요?"}

_head_thread = None


def songs():
    """{id: song} for every song with a rendered file; song["wav"] is its path."""
    out = {}
    for p in sorted(MINE.glob("*.json")):
        if p.with_suffix(".wav").exists():
            out[p.stem] = {**json.loads(p.read_text()), "wav": p.with_suffix(".wav")}
    return out


def asked(text, last=""):
    """Do these words ask Lumi to sing ("sing a song", "노래 불러 줘", "sing Love Attack", "다른 노래", "can you sing?")?
    `last` is the assistant's answer just before (brain history): right after a song a short "another one" /
    "again" / "그거 말고" is a song too, right after the list of songs (or "I can't sing that one") also a title alone ("Love Attack")."""
    t = text or ""
    if NOT_REQUEST.search(t) or NOT_ASKED.search(t) or SONG_LIST.search(t):
        return False
    if re.match(r"ACTION: (?:sing|none songs)\b", last or "") and AFTER_SONG.search(t):
        return True
    if SONG_OFFER.search(last or "") and OFFER_YES.match(t):
        return True                                    # "Shall I sing one for you?" (quick answers' can_sing) -> "yes"
    if picked(t, last):
        return True
    return bool(SING.search(t)) or bool(SING_TITLE.search(t) and (_title(t, songs()) or re.search(
        r"[a-z]{2}.*(?:불러|들려|틀어)", t, re.I) and _other_song(t, songs()))) or \
        bool(TITLE_ASKED.search(t) and _title(t, songs(), plain=bool(re.search(r"불러|들려|틀어|불르|부르|부를", t))))   # "Let it go 불러 줘": not ours


_bank = None


# right after the list of songs: which one ("the first one", "두 번째 거", "the last", "아무거나")
ORDINAL = [re.compile(r"\b(?:first|1st|number one)\b|첫\s*(?:번째|곡|거|노래)|첫번째|1번", re.I),
           re.compile(r"\b(?:second|2nd|number two)\b|두\s*번째|둘째|2번", re.I),
           re.compile(r"\b(?:third|3rd|number three)\b|세\s*번째|셋째|3번", re.I),
           re.compile(r"\b(?:fourth|4th|number four)\b|네\s*번째|넷째|4번", re.I)]
LAST_ONE = re.compile(r"\b(?:the )?last(?: one)?\b|마지막", re.I)
ANY_ONE = re.compile(r"\b(?:any(?:thing|one)?|whatever|you (?:choose|pick|decide)|random|surprise me|doesn'?t matter|"
                     r"up to you)\b|아무\s*거나|아무\s*노래|아무\s*곡|알아서|(?:네가|니가|루미가)\s*(?:골라|정해)|상관\s*없", re.I)


def picked(text, last=""):
    """Right after Lumi said its songs ("ACTION: none songs": the list, or "I can't sing that one"): the song these
    words choose, a title ("Fantastic Baby", "판타스틱", "BAD") or its place in the list ("the first one", "두 번째",
    "the last one"), or any one ("아무거나", "you choose"); else None."""
    if not (last or "").startswith("ACTION: none songs") or NOT_ASKED.search(text or ""):
        return None
    all_songs = songs()
    ids = list(all_songs)                             # the order the list says them in (_titles)
    named = _title(text, all_songs)
    if named:
        return named
    for i, r in enumerate(ORDINAL):
        if r.search(text or "") and i < len(ids):
            return ids[i]
    if ids and LAST_ONE.search(text or ""):
        return ids[-1]
    if ids and ANY_ONE.search(text or ""):
        return random.choice(ids)
    return None


def bank_read(text, last=""):
    """'sing' / 'list' when these words mean the same as the bank's wordings of that kind (bge-m3 through
    assistant/knowledge.embed, ~20 ms), else None (the LLM decides; also when the closest are the bank's
    near misses, and for a 'sing' with any word that might be a title: "jingle bells please"). Only words with a song
    or music word and BANK_MIN_WORDS words are read: a cut-off start ("Let's", "can you", "루미야 저기") never sings. Negation, a condition or a later time, the
    person singing, a question about liking music or "is / does ...?", and any words with a turn before them (the
    talk decides what "yes" means) are never read here."""
    global _bank
    t = text or ""
    if not SONG_WORD.search(t) or len(re.findall(r"\w+", t)) < BANK_MIN_WORDS or NOT_REQUEST.search(t) or \
            NOT_ASKED.search(t) or re.match(r"\W*(?:is|are|was|were|does|did|has|have)\b", t, re.I) or \
            re.search(r"\b(?:like|love|enjoy|favou?rite)\b|좋아|싫어", t, re.I) and re.search(r"\?|까요?\W*$|니\W*$", t) or last:
        return None
    from assistant import knowledge, song_bank
    try:
        q = knowledge.embed([t])[0]
    except OSError as e:                              # no embedding server: the LLM decides
        print(f"song bank: {e}")
        return None
    if _bank is None:
        texts = song_bank.SING + song_bank.LIST + song_bank.NO
        labels = ["sing"] * len(song_bank.SING) + ["list"] * len(song_bank.LIST) + ["no"] * len(song_bank.NO)
        _bank = (knowledge.embed(texts), np.array(labels))
    vecs, labels = _bank
    sims = vecs @ q
    best = int(sims.argmax())
    other = sims[labels != labels[best]].max()
    if sims[best] < BANK_SIM or sims[best] - other < BANK_MARGIN or labels[best] == "no":
        return None
    return "sing" if labels[best] == "sing" and choose(t, whole=True) else "list" if labels[best] == "list" else None


def list_asked(text):
    """"What songs can you sing?", "무슨 노래 알아?": the titles are said."""
    return bool(SONG_LIST.search(text or "")) and not NOT_REQUEST.search(text or "")


def stop_words(text):
    return bool(STOP.search(text or ""))


def _name_re(name):
    """A song's name in any spacing ("big bang", "러브어택", "a teez"); Latin names as whole words ("bad" is not in
    "badminton")."""
    body = r"\s*".join(re.escape(c) for c in name.replace(" ", ""))
    return rf"(?<![a-z]){body}(?![a-z])" if re.search(r"[a-z]", name) else body


def _title(text, all_songs, plain=True):
    """The song whose longest name is said ("I feel bad, sing Love Attack" is Love Attack), or None. plain=False:
    not by a name that is also a plain word ("bad": "I feel bad, please")."""
    low = (text or "").lower()
    found = [(len(n), sid) for sid, s in all_songs.items() for n in s["names"] if re.search(_name_re(n), low) and
             (plain or n not in ("bad", "배드"))]
    return max(found)[1] if found else None


def _title_at(text, all_songs):
    """Where the longest of our titles said starts (0 when none)."""
    low = (text or "").lower()
    found = [(len(n), m.start()) for s in all_songs.values() for n in s["names"] for m in [re.search(_name_re(n), low)] if m]
    return max(found)[1] if found else 0


def _without_ours(text, all_songs):
    low = (text or "").lower()
    for n in sorted((n for s in all_songs.values() for n in s["names"]), key=len, reverse=True):
        low = re.sub(_name_re(n), " , ", low)          # a comma: the words said before our title are not a title
    return low


# the words around a request that may hold a title: after "sing" / "play", before "song" / "노래", after "by" / "from",
# before "불러" / "들려" / "틀어"; what is left there after FILLER / FILLER_KO and our own names is another song
EN_SLOTS = [re.compile(r"\b(?:sing|play|perform|put on)\s+(.+?)\s*(?:\b(?:songs?|tunes?|music|for|please|now|again|lumi|to|with|"
                       r"together|today|right|ok|okay)\b|[,.!?~]|$)"),
            re.compile(r"((?:[\w'-]+\s+){0,2}[\w'-]+?)(?:'s)?\s+(?:songs?|tunes?|music)\b"),
            re.compile(r"\b(?:songs?|something|anything|one|tunes?|music)\s+(?:by|from|of|about)\s+(.+?)\s*(?:[,.!?]|\bplease\b|$)"),
            re.compile(r"\b(?:you know|do you know|know)\s+(.+?)\s*\?\s*(?:then |so |just |please |now )?(?:sing|play) (?:it|that|this)\b")]
KO_SLOTS = [re.compile(r"((?:\S+\s+){0,2}\S+?)\s*(?:의\s*)?(?:노래|곡|음악|(?<![가-힣])송)"),
            re.compile(r"((?:\S+\s+){0,2}\S+?)\s*(?:을|를)?\s*(?:좀\s*)?(?:불러|들려|틀어|부르)")]
FILLER_KO = {"루미야", "루미", "루미씨", "좀", "하나", "하나만", "한", "곡", "한곡", "노래", "음악", "아무", "아무거나", "다른", "딴",
             "다음", "새", "네", "니", "너", "너의", "네가", "니가", "당신", "우리", "저한테", "나한테", "우리한테", "저", "나", "제",
             "내", "그", "이", "저기", "한국", "한국어", "영어", "외국", "무슨", "어떤", "아는", "지금", "빨리", "한번", "번", "같이",
             "다시", "또", "진짜", "그냥", "케이팝", "제일", "가장", "최신", "음", "어", "자", "그럼", "혹시", "먼저", "거", "걸",
             "것", "뭐", "뭔가", "아무노래", "노래나", "곡만", "더", "요", "예", "응", "네네", "어서", "얼른", "한곡만", "하나쯤",
             "신곡", "의", "뭐든", "아무거나요", "노레", "노랠", "야", "래", "노", "신나게", "재밌게", "멋지게", "크게", "작게", "잠깐", "이번엔", "이번에는", "오늘", "여기서", "다들", "모두",
             "로봇", "로봇아", "말고", "그거", "이거", "얘", "애들", "할머니", "할아버지", "엄마", "아빠", "손님", "손님들",
             "씨", "짱", "님", "오빠", "언니", "누나", "형", "선배", "선배님", "양반", "형제님", "친구", "기사님", "선생님",
             "로봇님", "루미아", "저기요", "이봐", "이보게", "어이", "대박", "그래", "곡뽑아", "부를", "줄", "알면", "할줄",
             "부를줄", "쫌", "쪼까", "쪼끔", "함", "퍼뜩", "후딱", "얼릉", "싱", "송", "자락", "한자락", "땡겨", "아", "불", "웅", "넥스트", "플리즈", "오케이", "바", "앵콜"}   # addresses and the words of "부를 줄 알면 한 곡 해 봐"
VERB_KO = re.compile(r"^(?:불러|부르|불러줘|들려|틀어|틀|켜|해|줘|주|봐|부탁|시작|제발|할|하자|합시다|뽑아|바꿔|바꾸)")   # the request's own words
_PARTICLE = re.compile(r"(?<=.)(?:을|를|은|는|이|가|도|만|요|나|이나|라도|이라도|으로|로)$")
_ADNOMINAL = tuple("는은운한픈른쁜던된난진")    # "신나는", "조용한", "슬픈": a kind of song, no title


def _other_song(text, all_songs, whole=False):
    """A song not ours was named: 'sing Yesterday', 'Bad Guy by Billie Eilish', 'ATEEZ Wonderland', '아이유 노래',
    '빅뱅 거짓말 불러 줘', 'a Christmas song'. Words are read from the song word back: a describing word ("신나는",
    "좋으니까") or one said to someone ("아이한테") ends the title part."""
    low = re.sub(r"(?<=[가-힣])(?=노래|음악|(?<!한)곡|불러|들려|틀어)|(?<=노래)(?=[가-힣])", " ", _without_ours(text, all_songs))
    #                                              "노래하나불러줘요", "다음곡불러": the request's words written together
    whole_text = [re.match(r"(.*)", low, re.S)] if whole else []   # read by the bank: every word may hold a title
    for slots, word in ((EN_SLOTS, r"[a-z][a-z'-]*|[가-힣]+"), (KO_SLOTS, r"[a-z][a-z'-]*|[가-힣]+")):
        for m in whole_text + [m for slot in slots for m in slot.finditer(low)]:
            part = re.split(r"[,.!?~]", m.group(1))[-1]   # "루미 씨, 러브 어택 불러 줘": the address is no title
            for w in reversed(re.findall(word, part)):
                if re.match(r"[a-z]", w):
                    w = w.strip("'-").removesuffix("'s")
                    if w not in FILLER and not (len(w) > 4 and difflib.get_close_matches(w, FILLER, 1, 0.8)):
                        return True                     # "pleaase", "anothre": slips of filler words
                    continue
                if w in FILLER_KO or VERB_KO.match(w):
                    continue
                if len(w) > 1 and w.endswith(_ADNOMINAL) or re.search(r"(?:한테|에게|께|께서|니까|는데|데요|지만|해서|면|합니다)$", w):
                    break
                if _PARTICLE.sub("", w) not in FILLER_KO:
                    return True
    return False


def choose(text, lang="en", last=None, whole=False):
    """The song to sing for these words, or None when they ask for a song we don't have (another title or singer,
    or a language none of ours is in; with `whole` any word that is no filler is a title: "jingle bells please").
    A named song first; the last one again when asked; else any of ours, not
    the last."""
    all_songs = songs()
    if _other_song(text, all_songs, whole):
        return None
    named = _title(text, all_songs)
    other = [m.start() for m in ANOTHER.finditer(text or "")]
    if named and (not other or other[-1] < _title_at(text, all_songs)):
        return named                                 # "다음은 러브 어택", "그거 말고 BAD": that one; "BAD 말고 다른 거": another
    if last in all_songs and AGAIN.search(text or "") and not ANOTHER.search(text or ""):
        return last                                  # "sing it again", "한 번 더"
    want = "ko" if KOREAN.search(text or "") else "en" if ENGLISH.search(text or "") else None
    if want and not any(s["lang"] == want for s in all_songs.values()):
        return None                                  # "an English song": all of ours are Korean
    pool = [sid for sid, s in all_songs.items() if want in (None, s["lang"]) and sid != last] or list(all_songs)
    return random.choice(pool) if pool else None


def _titles(lang):
    names = [s["title_ko" if lang == "ko" else "title"] for s in songs().values()]
    if lang == "ko" or len(names) < 2:
        return ", ".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def unknown_reply(lang):
    """A song we don't have was asked for: said kindly, our songs offered (one of several wordings)."""
    n = len(songs())
    return random.choice(UNKNOWN[lang]).format(_titles(lang), n=COUNT_KO.get(n, f"{n} "))


def list_reply(lang):
    """Every title: "I can sing BAD, ... and Love Attack. Which one would you like?"."""
    names = _titles(lang)
    if lang == "ko":
        names += "를" if _no_final(names[-1]) else "을"
    return LIST[lang].format(names)


def _no_final(word):
    """Korean: the last syllable has no final consonant (를 rather than 을)."""
    c = ord(word[-1]) - 0xAC00
    return not (0 <= c < 11172) or c % 28 == 0


def song_beats(song):
    """[(seconds, energy 0..1, accent 0..1, a sung phrase starts)] per beat, from the instrumental (loudness,
    onsets) and the vocal (phrases), written by audio/sing_mine.py."""
    return [tuple(b) if len(b) == 4 else (b[0], b[1], 0.5, False) for b in song["beats"]]


def _speed(vel):
    return HEAD_DEG_S * min(1.0, vel / VEL_FULL)


def reach_time(dy, dp, vel):
    """s from the call until the head arrives (the owner's measurements)."""
    return REACH_S + max(abs(dy), abs(dp)) / _speed(vel)


def move_time(dy, dp, vel):
    """s from the call until moveto returns."""
    return RETURN_S + max(abs(dy), abs(dp)) / _speed(vel)


def _turn(a, b):
    """deg between two move directions (0 = same line forward, 180 = straight back)."""
    na, nb = np.hypot(*a), np.hypot(*b)
    return float(np.degrees(np.arccos(np.clip(np.dot(a, b) / (na * nb + 1e-9), -1, 1))))


def _fit(v, d, lo, hi, least):
    """A step d from v of at least `least`, ending inside lo..hi (turned toward the middle when it would not)."""
    d = d if abs(d) >= least else least * (1 if d >= 0 else -1)
    if lo <= v + d <= hi:
        return d
    if lo <= v - d <= hi:
        return -d
    toward = 1 if v < (lo + hi) / 2 else -1
    return toward * max(least, min(abs(d), hi - v if toward > 0 else v - lo))


def p_room(pp):
    """+1 when the pitch has more room upward, -1 when downward."""
    lo, hi = PITCH_RANGE
    return 1 if hi - pp >= pp - lo else -1


def _bend(py, pp, dy, dp, last):
    """The move (dy, dp) from (py, pp) made to change both axes (MIN_CHANGE), to turn away from the last move's
    line (MIN_TURN_DEG) and to end inside the limits: as planned, with the pitch the other way, else bent to either
    side."""
    lo, hi = PITCH_RANGE
    for side in (0, "flip", 1, -1, 2, -2):
        if side == "flip":                            # a sweep back: rise where the last one fell, and the other way
            dy2, dp2 = dy, -dp if abs(dp) >= 2 else (2.5 if p_room(pp) > 0 else -2.5)
        elif side and last is not None:               # add a part across the last move's direction
            n = np.hypot(*last) + 1e-9
            size = max(np.hypot(dy, dp), 3.0) * 0.6 * abs(side)
            dy2, dp2 = dy - last[1] / n * size * np.sign(side), dp + last[0] / n * size * np.sign(side)
        else:
            dy2, dp2 = dy, dp
        dy2, dp2 = _fit(py, dy2, -YAW_SWAY, YAW_SWAY, MIN_CHANGE[0]), _fit(pp, dp2, lo, hi, MIN_CHANGE[1])
        if last is None or MIN_TURN_DEG <= _turn(last, (dy2, dp2)) <= 180 - MIN_TURN_DEG:
            break
    return dy2, dp2


def head_targets(song, seed=0):
    """[(call s, yaw deg, pitch deg, speed %)] around yaw 0 / pitch CENTRE_PITCH, each move timed to land ON a beat
    (called reach_time before it) and never before the last call returned. Energetic parts: a small diagonal bob on
    every beat that leaves time (alternating sides, vel 100), and on a bar's accent or a phrase start a quick 15-25
    deg sweep with a dip. Calm parts: slower sways. Every move changes both axes and turns away from the last move's
    line (_bend)."""
    rng = random.Random(seed)
    beats = song_beats(song)
    lo, hi = PITCH_RANGE
    y, p, free = 0.0, 0.0, 0.0                       # the pose and when the last call returns (starts at 0 / 0)
    side, last, last_accent, out, pending = rng.choice((-1, 1)), None, -9.0, [], False
    for k, (t, e, accent, phrase) in enumerate(beats):
        if t < 0.8:                                   # the head is still turning to 0 / 0
            continue
        pending = pending or ((accent >= 0.7 or phrase) and t - last_accent >= ACCENT_EVERY_S and e >= 0.3)
        if pending:                                   # an accent waits for the first beat it fits on
            kind, vel = "accent", VEL_LIVELY
        elif e >= ENERGETIC:
            kind, vel = "bob", VEL_LIVELY
        else:
            kind, vel = "sway", VEL_CALM if e >= CALMEST else VEL_CALMEST
        if kind != "bob" or rng.random() < 0.85:
            side = -side
        if kind == "accent":                          # a sweep across to the other side, dipping
            side = -1 if y > 0 else 1
            ty = side * rng.uniform(*ACCENT_DEG) * 0.7 + 0.3 * y
            tp = rng.choice((max(lo, min(p, CENTRE_PITCH + 2) - rng.uniform(6, 10)), min(hi, CENTRE_PITCH + rng.uniform(8, 14))))   # dip or lift
        elif kind == "bob":
            size = rng.uniform(*BOB_DEG)
            ty = y + side * size * rng.uniform(0.7, 1.0)
            tp = (p - size * 0.8 if p > CENTRE_PITCH else p + size * 0.8) + rng.uniform(-1, 1)   # diagonal
        else:
            ty = side * rng.uniform(*SWAY_DEG)
            tp = CENTRE_PITCH + rng.uniform(-8, 8)
        ty -= 0.15 * y if kind == "bob" else 0.0       # bobs drift back toward the middle
        dy, dp = _bend(y, p, ty - y, tp - p, last)
        call = t - reach_time(dy, dp, vel)            # lands on the beat
        for _ in range(8):                            # too little time: a smaller move (an accent stays big)
            if call >= free + GAP_S or max(abs(dy), abs(dp)) <= (ACCENT_DEG[0] if kind == "accent" else 3.0):
                break
            dy, dp = _bend(y, p, dy * 0.8, dp * 0.8, last)
            call = t - reach_time(dy, dp, vel)
        if last is not None and not MIN_TURN_DEG <= _turn(last, (dy, dp)) <= 180 - MIN_TURN_DEG:
            n = np.hypot(*last) + 1e-9                # still on the last line: a small step across it instead
            for size in (4.0, -4.0, 6.0, -6.0, 2.5, -2.5):
                dy = _fit(y, -last[1] / n * size, -YAW_SWAY, YAW_SWAY, MIN_CHANGE[0] + 0.2)
                dp = _fit(p, last[0] / n * size, lo, hi, MIN_CHANGE[1] + 0.2)
                if MIN_TURN_DEG <= _turn(last, (dy, dp)) <= 180 - MIN_TURN_DEG:
                    break
            call = t - reach_time(dy, dp, vel)
        if call < free + GAP_S or last is not None and not MIN_TURN_DEG <= _turn(last, (dy, dp)) <= 180 - MIN_TURN_DEG:
            continue                                  # no time or no fitting move for this beat: a later one
        out.append((round(float(call), 3), round(float(y + dy), 2), round(float(p + dp), 2), int(vel)))
        free = call + move_time(dy, dp, vel)
        last, y, p = (dy, dp), y + dy, p + dp
        if kind == "accent":
            last_accent, pending = t, False
    return out


def _move_head(song, seed, stop, head_api):
    """Turn the head to yaw 0 / pitch 0, follow the head targets until the song ends or stop is set, then go back
    to yaw 0 / pitch 0. One call at a time (each blocks until the head arrives)."""
    try:
        lift, waist, _, _ = head_api.status()
    except Exception as e:
        print(f"sing: head status failed: {e}")
        return
    t0 = time.time()
    try:
        head_api.moveto([lift, waist, 0.0, 0.0], VEL_LIVELY, VEL_LIVELY)
        for t, yaw, pitch, vel in head_targets(song, seed):
            while not stop.is_set() and time.time() - t0 < t:
                stop.wait(0.02)
            if stop.is_set():
                break
            if time.time() - t0 - t > LATE_S:
                continue
            head_api.moveto([lift, waist, yaw, pitch], vel, vel)
    except Exception as e:
        print(f"sing: head move failed: {e}")
    finally:
        try:
            head_api.moveto([lift, waist, 0.0, 0.0], HEAD_VEL, HEAD_VEL)
        except Exception as e:
            print(f"sing: head return failed: {e}")


def sing(song_id, abort=None, play=None, head_api=None, load=None):
    """Sing one song; blocks until it ends (True) or abort() becomes True (False). The head returns in its own
    thread, so a stop is at once. play / head_api / load are for tests (default: the speaker and the real head)."""
    global _head_thread
    from audio import mouth
    if play is None:
        mouth._set_volume()
        play = mouth._play
    if head_api is None:
        from robot import head as head_api
    if load is None:
        import soundfile as sf
        def load(path):
            return sf.read(path, dtype="float32")
    song = songs()[song_id]
    wav, rate = load(song["wav"])
    wav = np.asarray(wav)
    if wav.ndim == 2:                                  # the owner's songs are stereo; the speaker is one channel
        wav = wav.mean(1)
    if _head_thread is not None:
        _head_thread.join(RETURN_WAIT_S)               # the head is still going back from the last song
    # the clip mic hears the song: its words are Lumi's own voice until 30 s after its end (mouth.recent_speech)
    mouth._recent.append((time.time() + len(wav) / rate, song["lyrics"]))
    stop = threading.Event()
    _head_thread = threading.Thread(target=_move_head, args=(song, time.time(), stop, head_api), daemon=True)
    _head_thread.start()
    try:
        return bool(play(wav, rate, abort))
    finally:
        stop.set()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        for sid, s in songs().items():
            print(f"{sid:24} {s['lang']}  {s['title']}")
    else:
        print("finished" if sing(sys.argv[1]) else "stopped")
        if _head_thread:
            _head_thread.join()
