"""More English sentences of the same meaning: other verbs and idioms for the same order ("face left", "do a u-turn",
"bow your head", "eyes on me", "lend me your hand", "tag along", "stick with me", "go get the cup for me"), each with
the frames people put around it (please, could you, would you mind, I need you to, slang, non-native)."""

FRAMES = ["{}", "please {}", "{}, please", "could you {}?", "can you {}?", "would you {}?", "can you {} for me?",
          "I need you to {}", "I'd like you to {}", "go ahead and {}", "{} now", "yo, {}", "just {}", "lumi, {}",
          "you {} please", "{} pls", "can u {}", "would you please {}?", "hey, {} would ya"]


def _with(phrases):
    return list(dict.fromkeys(f.format(p) for p in phrases for f in FRAMES))


INTENT = {
    "turn": _with(["face left", "face right", "face the other way", "turn the other way", "do a u-turn", "make a u-turn",
                   "rotate one eighty", "turn one eighty", "pivot left", "pivot right", "swing left", "swing right",
                   "turn your body to the left", "turn your body to the right", "about face", "flip around"]),
    "look": _with(["bow your head", "nod your head down", "look at the ceiling", "look at the floor", "eyes on me",
                   "turn to me", "turn your head to me", "look my way", "look in my direction", "eyes up",
                   "eyes down", "glance up", "glance down", "peek left", "peek right", "check out the ceiling"]),
    "come_back": _with(["go back to your spot", "return to where you started", "come back to where you were",
                        "go back where you came from", "back to your starting point", "return to your spot",
                        "head back to where you were"]),
    "arm_reach": _with(["lend me your hand", "let me hold your hand", "give me a hand to hold", "stick your hand out",
                        "put your arm out", "offer me your hand"]),
    "arm_open": _with(["release the gripper", "let go with your gripper", "loosen your grip", "unclench your hand",
                       "open up your fingers", "relax your fingers"]),
    "arm_close": _with(["clench your hand", "tighten your grip", "grip tight", "squeeze your fingers shut"]),
    "fetch": _with(["go get the <obj> for me", "go get me the <obj>", "fetch me the <obj>", "grab me the <obj>",
                    "bring the <obj> my way", "get the <obj> and bring it here", "could you bring over the <obj>",
                    "pass me the <obj>"]),
    "lift": _with(["get taller", "raise yourself up", "make yourself shorter", "lower yourself", "make yourself taller"]),
    # not "go up / down a bit": "move up a smidge" is a drive forward
    "follow": _with(["tag along", "stick with me", "come along with me", "walk behind me", "stay on my heels",
                     "keep up with me", "come with me, buddy"]),
    "come": _with(["get over here", "come over to me", "come on over", "come closer to me", "scoot over here",
                   "roll over here", "make your way over here"]),
    "wave": _with(["do you shake your hand", "do you wave", "shake my hand", "give me a handshake", "high five me",
                   "wave goodbye", "give a little wave", "wave your hand at me"]),
}

# "mind folding your arm?", "how about turning around?", "care to follow me?": the -ing and "care to" frames
GERUND = ["mind {g}?", "would you mind {g}?", "how about {g}?", "what about {g}?", "care to {v}?", "how about you {v}?",
          "any chance of {g}?", "fancy {g}?"]
_PAIRS = {
    "arm_fold": [("fold your arm", "folding your arm"), ("put your arm away", "putting your arm away")],
    "arm_reach": [("hold out your hand", "holding out your hand"), ("reach out your arm", "reaching out your arm")],
    "turn": [("turn around", "turning around"), ("turn left", "turning left"), ("turn right", "turning right")],
    "follow": [("follow me", "following me"), ("come with me", "coming with me")],
    "come": [("come here", "coming here"), ("come over", "coming over")],
    "look": [("look at me", "looking at me"), ("look up", "looking up"), ("look down", "looking down")],
    "wave": [("wave", "waving"), ("shake my hand", "shaking my hand")],
    "pick": [("pick up the <obj>", "picking up the <obj>"), ("grab the <obj>", "grabbing the <obj>")],
    "arm_open": [("open your hand", "opening your hand")],
    "arm_close": [("close your hand", "closing your hand")],
}
for _k, _ps in _PAIRS.items():
    INTENT[_k] = INTENT.get(_k, []) + [f.format(v=v, g=g) for v, g in _ps for f in GERUND]
