"""Singing: play a pre-rendered song (data/songs/<id>.wav, made by audio/sing_render.py, or data/songs/mine/<id>.wav,
made by audio/sing_mine.py from the owner's own files) and move the head with it.

    python audio/sing.py                  # list the songs
    python audio/sing.py twinkle          # sing one (plays on the speaker and moves the head)

Each <id>.json holds the title, the names it is asked by and the lyrics; the public domain songs also the melody
and chords, the owner's songs (local only, never copied off the robot) their head moves timed to the beat. The song is played through mouth._play (the microphone is muted the same way as for speech,
and abort() stops it within 50 ms). The head turns to yaw 0 / pitch 0 and dances around it in a thread, following the
music: small diagonal bobs landing on the beats in energetic parts, a quick sweep with a dip on a bar's accent or a
phrase start, slower sways in calm parts, each move called early enough (the owner's measured head timing) to land
on its beat, one call at a time; it goes back to yaw 0 / pitch 0 when the song ends or is stopped. Never the lift, the waist or the arm.
"""
import json
import pathlib
import random
import re
import sys
import threading
import time

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
SONGS = ROOT / "data" / "songs"
MINE = SONGS / "mine"           # the owner's songs: local only
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

SING = re.compile(r"\bsing\b|\bsay (?:a |some )?songs?\b|"                    # whisper writes "let's say song"
                  r"\b(?:play|put on|turn on|start)(?: me| us)? (?:a |some |any |another |the |your )?(?:songs?|music|tunes?)\b|"
                  r"\b(?:another|different|next|new|other) (?:song|tune)\b|\b(?:want|like|love) to hear (?:a |some )?(?:song|music)\b|"
                  r"^\W*(?:lumi\W*)?(?:a |some )?(?:song|music)(?:\W+(?:please|lumi))*\W*$|"
                  r"(?:노래|음악|(?<![가-힣])곡)\s*(?:를|을|좀|하나|한\s*곡|한\s*번|한번|도|이나|나|이든|든|라도|\s)*"
                  r"(?:불러|부르|들려|해|틀어|틀|뽑아|부탁|재생|플레이|(?:할|부를)\s*(?:수|줄)\s*(?:있|알))|"
                  r"노래\s*(?:좀|하나)?\s*(?:듣고\s*싶|들을래|듣자)|(?:다른|딴|다음)\s*(?:노래|곡)|(?:다른|딴)\s*(?:거|걸|걸로)\s*(?:불러|들려|틀어)|^\W*(?:노래|음악)\s*(?:좀|하나)?\W*$", re.I)
SING_TITLE = re.compile(r"(불러|들려|틀어) ?(줘|주세요|줄래|봐|볼래)|\b(?:sing|play)\b")    # "아리랑 불러 줘": a title said with it
SONG_LIST = re.compile(r"\b(?:what|which) (?:kinds? of |sort of |other )?(?:songs?|music|tunes)\b|\bwhat can you sing\b|"
                       r"\bsongs? (?:do |can |could )?you (?:know|sing|have)\b|\b(?:know|have) any (?:other )?songs\b|"
                       r"\b(?:list|names?) of (?:your |the )?songs\b|"
                       r"(?:무슨|어떤|뭔|어느)\s*(?:노래|곡)(?!\s*(?:이든|든|이나|나|라도))|노래\s*(?:는|를|은)?\s*(?:뭐|뭘|몇)|"
                       r"아는\s*노래|부를\s*(?:수\s*있는|줄\s*아는)\s*노래|노래\s*목록", re.I)
NOT_REQUEST = re.compile(r"\b(?:do|did) you (?:really )?(?:like|love|enjoy)\b|"
                         r"\bwho sings?\b|\bfavou?rite\b|좋아하는|좋아해|잘\s*(?:해|하|불러)", re.I)
# right after a song (or the list of songs): a short word switches or repeats it
AFTER_SONG = re.compile(r"^\W*(?:(?:lumi|ok|okay|no|nah|um|please|then|now|and)\W+)*(?:sing |play )?"
                        r"(?:another(?: one)?|(?:the )?next(?: one)?|a different one|something (?:else|different)|"
                        r"not (?:this|that)(?: one)?|(?:it |that )?again|one more(?: time)?|once more|more)"
                        r"(?:\W+(?:please|lumi))*\W*$|"
                        r"^\W*(?:루미야?\W*)?(?:아니\W*)?(?:(?:그거|그\s*노래|이거|이\s*노래)\s*말고(?:\s*(?:다른|딴)\s*(?:거|걸로|노래))?|"
                        r"(?:다른|딴)\s*(?:거|걸|걸로|것)|다음\s*(?:거|곡|노래)?|한\s*번\s*더|하나\s*더|다시|또)"
                        r"\s*(?:요|줘|해\s*줘|불러\s*줘|들려\s*줘|부탁해요?|해요|주세요)?\W*$", re.I)
AGAIN = re.compile(r"\bagain\b|\bone more time\b|\bonce more\b|한 ?번 ?더|다시", re.I)
ANOTHER = re.compile(r"\b(another|different|next|other)\b|\bsomething else\b|\bnot (this|that)\b|다른|딴|다음|말고", re.I)
STOP = re.compile(r"\b(stop|enough|halt|quiet|shh+)\b|멈춰|그만|스톱|정지|조용", re.I)
KOREAN = re.compile(r"\bkorean\b|한국", re.I)
ENGLISH = re.compile(r"\benglish\b|영어", re.I)
FILLER = {"sing", "a", "an", "the", "song", "songs", "me", "us", "for", "please", "lumi", "some", "something", "now", "again",
          "one", "another", "different", "other", "next", "little", "short", "can", "you", "could", "would", "will", "to",
          "it", "that", "this", "together", "with", "and", "your", "nice", "hey", "hi", "ok", "okay", "play", "music",
          "in", "korean", "english", "else", "let's", "lets", "let", "go", "now", "pretty", "beautiful", "my", "kids",
          "children", "children's", "cute", "fun", "favorite", "favourite", "of", "yours", "so", "just", "maybe", "then"}
UNKNOWN = {"en": "Sorry, I don't know that song yet. I can sing {}.", "ko": "그 노래는 아직 몰라요. {} 부를 수 있어요."}
LIST = {"en": "I can sing {}. Which one would you like?", "ko": "{} 부를 수 있어요. 어떤 노래 불러 드릴까요?"}

_head_thread = None


def songs():
    """{id: song} for every song with a rendered file; song["wav"] is its path."""
    out = {}
    for p in sorted(SONGS.glob("*.json")) + sorted(MINE.glob("*.json")):
        if p.with_suffix(".wav").exists():
            out[p.stem] = {**json.loads(p.read_text()), "wav": p.with_suffix(".wav")}
    return out


def asked(text, last=""):
    """Do these words ask Lumi to sing ("sing a song", "노래 불러 줘", "sing Arirang", "다른 노래", "can you sing?")?
    `last` is the assistant's answer just before (brain history): right after a song a short "another one" /
    "again" / "그거 말고" is a song too, right after the list of songs also a title alone ("Arirang")."""
    t = text or ""
    if NOT_REQUEST.search(t) or SONG_LIST.search(t):
        return False
    if re.match(r"ACTION: (?:sing|none songs)\b", last or "") and AFTER_SONG.search(t):
        return True
    if (last or "").startswith("ACTION: none songs") and _title(t, songs()):
        return True
    return bool(SING.search(t)) or bool(SING_TITLE.search(t) and _title(t, songs()))


def list_asked(text):
    """"What songs can you sing?", "무슨 노래 알아?": the titles are said."""
    return bool(SONG_LIST.search(text or "")) and not NOT_REQUEST.search(text or "")


def stop_words(text):
    return bool(STOP.search(text or ""))


def _title(text, all_songs):
    low = (text or "").lower()                      # Latin names are whole words ("bad" is not in "badminton")
    return next((sid for sid, s in all_songs.items()
                 if any(re.search(rf"(?<![a-z]){re.escape(n)}(?![a-z])", low) for n in s["names"])), None)


def _unknown_title(text):
    """A title was named that is not one of ours: 'sing Yesterday', '애국가 불러 줘'."""
    words = re.findall(r"[a-z']+", (text or "").lower())
    if "sing" in words:
        after = [w for w in words[words.index("sing") + 1:] if w not in ("me", "us", "please", "lumi")]
        if after and after[0] not in FILLER:          # "sing yesterday"; "sing for everyone" is no title
            return True
    m = re.search(r"(\S+?)\s*(?:을|를)?\s*(?:좀\s*)?(?:불러|들려)", text or "")
    return bool(m) and not re.search(r"노래|좀|곡|하나|루미|아무|뭐|뭔가|^(한|또|더|다시|거|걸|것)$", m.group(1))


def choose(text, lang="en", last=None):
    """The song to sing for these words, or None when they name a song we don't have. A named song first; the
    last one again when asked; else any song (one in the language asked for: "a Korean song"), not the last."""
    all_songs = songs()
    named = _title(text, all_songs)
    if named and not ANOTHER.search(text or ""):
        return named
    if not named and _unknown_title(text):
        return None
    if last in all_songs and AGAIN.search(text or "") and not ANOTHER.search(text or ""):
        return last                                  # "sing it again", "한 번 더"
    want = "ko" if KOREAN.search(text or "") else "en" if ENGLISH.search(text or "") else None
    pool = [sid for sid, s in all_songs.items() if want in (None, s["lang"]) and sid != last] or \
        [sid for sid in all_songs if sid != last] or list(all_songs)
    return random.choice(pool) if pool else None


def unknown_reply(lang, lines=UNKNOWN):
    names = [s["title_ko" if lang == "ko" else "title"] for s in songs().values()]
    joined = ", ".join(names[:-1]) + (" and " if lang == "en" else ", ") + names[-1] if len(names) > 1 else "".join(names)
    return lines[lang].format(joined + ("" if lang == "en" else "를" if _no_final(names[-1]) else "을"))


def list_reply(lang):
    """Every title: "I can sing Arirang, ... and Love Attack. Which one would you like?"."""
    return unknown_reply(lang, LIST)


def _no_final(word):
    """Korean: the last syllable has no final consonant (를 rather than 을)."""
    c = ord(word[-1]) - 0xAC00
    return not (0 <= c < 11172) or c % 28 == 0


def song_beats(song):
    """[(seconds, energy 0..1, accent 0..1, a sung phrase starts)] per beat. The owner's songs carry them from the
    instrumental (loudness, onsets) and the vocal (phrases); for the others they come from the tempo and the melody:
    the bar's first beat is the accent, a phrase starts after a rest or a long note, the intro is calm."""
    if "beats" in song:
        return [tuple(b) if len(b) == 4 else (b[0], b[1], 0.5, False) for b in song["beats"]]
    spb = 60.0 / song["bpm"]
    meter = song["meter"]
    intro = song.get("intro_bars", 1) * meter
    tokens = [t.split(":") for t in song["melody"].split() if t != "|"] * song.get("repeat", 1)
    starts, beat, after_break = set(), 0.0, True
    for syl, note, b in tokens:
        if note != "r" and syl != "~" and after_break:
            starts.add(int(round(intro + beat)))
        after_break = note == "r" or float(b) >= 2
        beat += float(b)
    total = intro + int(beat)
    return [(i * spb, 0.3 if i < intro else 0.65, 1.0 if i % meter == 0 else 0.3, i in starts) for i in range(total)]


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
