"""Marker names said in other ways than wording.py reads them: as they sound in the other language ("인포 데스크"
for info_desk, "레지스트레이션" for Registration; never a translation: 출구 is no "exit"), the words of a two-word
name the other way round ("에이 부스" for booth_A, "삼 번 부스" for 부스3), letters and numbers as said ("booth bee",
"부스 십이", "gate won"), and whisper's spellings ("hole A", "카패").

apply(t, markers) writes them as the marker's written name (wording.written) in text already normalised by
wording.norm, so every reader after it (brain.named_place, the go rules, the intent bank) sees the marker.
Every word of the name must be said: "booth" alone is no booth_A.

    python assistant/place_words.py conference "레지스트레이션으로 가 줘"
"""
import functools
import re
import sys

from assistant import wording

EN_KO = {   # an English word of a name -> how it sounds in Korean, and other spellings. Never a translation: "출구" is
    # not "exit" (the owner, 2026-10-26: a word that only means the place is asked about, never mapped to a marker)
    "registration": ["레지스트레이션", "레지스트레이숀"], "gallery": ["갤러리", "겔러리", "갤러리이"],
    "information": ["인포메이션"], "info": ["인포", "information", "인포메이션"],
    "desk": ["데스크", "대스크", "데스끄"], "cafe": ["카페", "카패", "까페", "café"], "coffee": ["커피", "코피"],
    "corner": ["코너"], "elevator": ["엘리베이터", "엘레베이터", "엘베"], "lift": ["리프트"], "entrance": ["엔트런스"],
    "exit": ["엑시트", "엑싯", "엑짓", "이그짓", "익싯", "익시트", "에그짓"], "stage": ["스테이지"], "main": ["메인"], "booth": ["부스", "boot", "bootH"],
    "hall": ["홀", "hole", "hol"], "gate": ["게이트", "gait"], "photo": ["포토", "foto"], "zone": ["존", "zon"],
    "lounge": ["라운지"], "lobby": ["로비"], "bar": ["바"], "table": ["테이블", "table"], "front": ["프론트", "프런트"],
    "restroom": ["레스트룸"], "toilet": ["토일렛"], "meeting": ["미팅"], "room": ["룸"], "shop": ["샵", "숍"],
    "gift": ["기프트"], "dock": ["도크", "독"], "demo": ["데모"], "lab": ["랩"], "office": ["오피스"],
}
KO_EN = {   # a Korean word of a name -> how it sounds in English (and its spellings); never a translation
    "인포": ["info"], "인포메이션": ["information"], "데스크": ["desk", "대스크"], "커피": ["coffee"], "코너": ["corner"],
    "포토": ["photo", "foto"], "존": ["zone"], "엔트런스": ["entrance"], "스테이지": ["stage"], "라운지": ["lounge"],
    "부스": ["booth"], "로비": ["lobby"], "카페": ["cafe", "café", "카패"], "갤러리": ["gallery"], "홀": ["hall"],
}
LETTER = {"a": ["a", "에이", "ay", "에이에"], "b": ["b", "bee", "be", "비", "삐"], "c": ["c", "see", "sea", "씨"],
          "d": ["d", "dee", "디"], "e": ["e", "이"]}
NUM = {1: ["one", "won", "원", "일"], 2: ["two", "투", "이"], 3: ["three", "쓰리", "스리", "삼"],
       4: ["four", "포", "사"], 5: ["five", "파이브", "오"], 6: ["six", "식스", "육"], 7: ["seven", "세븐", "칠"],
       8: ["eight", "에잇", "팔"], 9: ["nine", "나인", "구"], 10: ["ten", "텐", "십"], 11: ["eleven", "십일"],
       12: ["twelve", "트웰브", "십이"], 13: ["thirteen", "십삼"], 14: ["fourteen", "십사"], 15: ["fifteen", "십오"]}
SEP = r"[\s_.-]*(?:(?:번|number|no\.?|넘버)\s*)?"          # between the words: "booth 3", "booth_3", "삼 번 부스"


def _segments(tok):
    """A Korean word cut into the known words of KO_EN ("커피코너" -> 커피, 코너), else the word whole."""
    out, rest = [], tok
    while rest:
        w = next((k for k in sorted(KO_EN, key=len, reverse=True) if rest.startswith(k)), None)
        if not w:
            return [tok]
        out.append(w)
        rest = rest[len(w):]
    return out


def _alts(tok, alone):
    if tok.isdigit():
        return [tok] + NUM.get(int(tok), [])
    if tok in LETTER:
        return LETTER[tok] if not alone else [tok]
    return [tok] + EN_KO.get(tok, []) + KO_EN.get(tok, [])


@functools.lru_cache(maxsize=64)
def _patterns(markers):
    out = []
    for m in markers:
        if re.fullmatch(r"p\d+|home", m.lower()):
            continue
        toks = []
        for tok in re.findall(r"[a-z]+|\d+|[가-힣]+", m.lower()):
            toks += _segments(tok) if re.fullmatch(r"[가-힣]+", tok) else [tok]
        if not toks:
            continue
        parts = ["(?:" + "|".join(sorted({re.escape(a).replace(r"\ ", r"\s?") for a in _alts(t, len(toks) == 1)},
                                         key=len, reverse=True)) + ")" for t in toks]
        orders = [parts] + ([parts[::-1]] if len(parts) == 2 else [parts[1:] + parts[:1]] if len(parts) > 2 else [])
        # ^ "에이 부스" for booth_A, "비 세븐 게이트" for Gate_B7: the first word said last
        body = "|".join(SEP.join(p) for p in orders)
        out.append((m, re.compile(rf"(?<![a-z0-9_가-힣])(?:the )?(?:{body})(?![a-z0-9_])(?:(?<=[a-z0-9])|{wording._KO_END})")))
    return out


def apply(t, markers=()):
    """Normalised text with the markers said in other ways written as their names."""
    if not markers or not t:
        return t
    for m, rx in _patterns(tuple(markers)):
        name = wording.written(m)
        t = rx.sub(lambda x: x.group(0) if x.group(0).strip() == name else name, t)
    return t


if __name__ == "__main__":
    from tests.blind.maps import MAPS
    print(apply(wording.norm(" ".join(sys.argv[2:]), MAPS[sys.argv[1]]), MAPS[sys.argv[1]]))
