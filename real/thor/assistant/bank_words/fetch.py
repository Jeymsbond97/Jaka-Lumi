"""Cup-task wordings for the intent bank (F1, night 4): fetch from a place said in every way ("the cup on p2",
"p2에 있는 컵", "피원 컵을", "move the cup from A to B", "옮겨"), at every Korean level; and "no": the same words
reported, asked about, put off or taken back (nothing moves). The words decide the fields (brain.parse_fetch)."""

_KO_FETCH = ["<place>에 있는 <obj> 가져와", "<place>에 있는 <obj> 좀 갖다 줘", "<place>에 놓인 <obj> 가져와",
             "<place> <obj> 가져와", "<place>의 <obj> 가져다 줘", "<place> 위에 있는 <obj> 가져와",
             "<place>에서 <obj> 집어서 가져와", "<place>에서 <obj> 들고 와", "<place>에 있는 <obj>을 여기로 가져와",
             "<place>에서 <obj> 좀 챙겨 와", "<place>에 있는 <obj> 옮겨 와"]
_KO_END = [("가져와", ["가져와", "가져와요", "가져오세요", "가져오십시오", "가져와 주세요", "가져와 주시겠어요?",
                     "가져와 주시겠습니까?", "가져와 줄래?", "가져오게", "가져와 주게나", "가져온나", "가져와유",
                     "가져와 주이소", "가져와 주실 수 있으신가요?", "가져와 주시면 감사하겠습니다"]),
           ("갖다 줘", ["갖다 줘", "갖다 주세요", "갖다 주십시오", "갖다 주실래요?", "갖다 주게", "갖다 줘유",
                      "갖다 주이소", "갖다 주시겠어요?", "갖다 드려 주세요"]),
           ("가져다 줘", ["가져다 줘", "가져다 주세요", "가져다 주십시오", "가져다 주시겠습니까?", "가져다 주게나"]),
           ("들고 와", ["들고 와", "들고 와요", "들고 오세요", "들고 오십시오"]),
           ("챙겨 와", ["챙겨 와", "챙겨 와요", "챙겨 오세요"]),
           ("옮겨 와", ["옮겨 와", "옮겨 와 주세요", "옮겨 오십시오"])]

_EN_FETCH = ["bring me the <obj> on <place>", "get me the <obj> that's on <place>", "fetch the <obj> sitting at <place>",
             "grab the <obj> at <place> and bring it here", "bring the <obj> over from <place>",
             "<place> <obj>, bring it to me", "go to <place>, get the <obj> and bring it back to me",
             "pick up the <obj> at <place> and bring it to me", "the <obj> on <place>, could you fetch it",
             "move the <obj> from <place> over here", "carry the <obj> from <place> to me"]
_EN_FRAME = ["{}", "please {}", "could you {}", "would you mind, {}", "can you {} for me", "{} please", "lumi, {}",
             "hey robot, {}", "excuse me, {}", "i need you to {}", "{} real quick", "do me a favour and {}"]

_NO = ["did you bring the <obj> from <place>?", "you brought the <obj> from <place> yesterday", "can you bring cups at all?",
       "don't bring the <obj> from <place>", "i'll bring the <obj> from <place> myself", "tomorrow bring the <obj>",
       "maybe later you can bring the <obj> from <place>", "my friend brought the <obj> from <place>",
       "she asked whether you can fetch things", "bring me the <obj> from <place>, no wait, never mind",
       "<place>에서 <obj> 가져왔어?", "어제 <obj> 가져왔지?", "<place>에서 <obj> 가져오지 마", "내가 <obj> 가져올게",
       "나중에 <obj> 가져와 줘", "<obj> 가져올 수 있어?", "친구가 <place>에서 <obj> 가져왔대", "<obj> 가져오는 거 봤어",
       "<place>에서 <obj> 가져와, 아 아니다 됐어", "<obj> 가져오시면 안 됩니다", "<obj> 가져다 주실 필요 없어요",
       "할머니가 <obj> 가져오라고 하셨는데 괜찮아", "<obj> 가져오는 건 내일 해", "<place>에서 <obj> 가져다 줄 수 있나 궁금하네"]


def _ko():
    out = []
    for base in _KO_FETCH:
        for verb, ends in _KO_END:
            stem = base.rsplit(" ", 1)[0] if base.endswith(("가져와", "갖다 줘", "가져다 줘", "들고 와", "챙겨 와", "옮겨 와")) else base
            if base.endswith(verb):
                stem = base[: -len(verb)].rstrip()
                out += [f"{stem} {e}" for e in ends]
    return out


INTENT = {"fetch": sorted(set(_ko() + [f.format(c) for c in _EN_FETCH for f in _EN_FRAME])), "no": _NO}
