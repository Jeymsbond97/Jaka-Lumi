"""English requests said in other words: each capability's sentences of the same meaning (the owner's example: "shake
your hand", "shake hand", "can you shake your hand", "wave your hand", "wave hand", "do you shake your hand" = wave)
in every frame people use (bare, please, could you, would you mind, I need you to, go ahead and, slang, non-native)
must give the reading of the capability's plain request. The same words as talk (past, negation, later, about
someone else) must not move Lumi.

    .venv/bin/python tests/en_paraphrase_check.py        # -> logs/en_paraphrase.md
"""
import collections
import pathlib
import sys

from tests import ko_levels_check as kl

ROOT = pathlib.Path(__file__).resolve().parents[1]

# name: (plain request, [other sentences of the same meaning, verb first]); "spin left" / "spin around" / "turn all the
# way around" are a full spin, "hold it" a hand-over: not listed
CAPS = {
    "wave":     ("wave", ["shake your hand", "shake hand", "wave your hand", "wave hand", "give us a wave", "wave hello",
                          "do a little wave", "shake hands with me", "let's shake hands", "wave at me", "wave to the kids",
                          "say hi with your hand", "wave bye"]),
    "reach":    ("give me your hand", ["hold out your hand", "stretch your arm out", "reach out your hand", "put your hand out",
                                       "lend me your hand", "extend your arm"]),
    "fold":     ("fold your arm", ["put your arm away", "tuck your arm in", "bring your arm back", "lower your arm",
                                   "put your arm down"]),
    "open":     ("open your hand", ["open the gripper", "open your fingers", "spread your fingers", "release the gripper"]),
    "close":    ("close your hand", ["close the gripper", "close your fingers", "make a fist", "shut your hand"]),
    "pick":     ("pick up the cup", ["grab the cup", "take the cup", "get the cup", "lift the cup", "pick the cup up",
                                     "grab that cup", "take hold of the cup"]),
    "fetch":    ("bring me the cup", ["get me the cup", "fetch the cup", "bring the cup over here", "hand me the cup",
                                      "bring that cup to me", "go get the cup for me"]),
    "go_to":    ("go to p3", ["head to p3", "drive to p3", "move to p3", "go over to p3", "make your way to p3",
                              "get yourself to p3", "go to point p3"]),
    "home":     ("go home", ["go back home", "head home", "return home", "go to your home spot"]),
    "come":     ("come here", ["come over here", "come to me", "come closer", "get over here", "come this way",
                               "come over", "approach me"]),
    "follow":   ("follow me", ["come with me", "follow along", "walk with me", "stay behind me", "keep following me",
                               "tag along", "stick with me"]),
    "forward":  ("move forward one meter", ["go forward one meter", "drive forward a meter", "move ahead one meter",
                                            "roll forward one meter", "go one meter forward"]),
    "back":     ("move back half a meter", ["back up half a meter", "go back fifty centimeters", "reverse half a meter",
                                            "back off half a meter", "move backward fifty centimeters"]),
    "turn":     ("turn left", ["turn to the left", "rotate left", "turn your body left", "face left",
                               "make a left turn", "turn left ninety degrees"]),
    "around":   ("turn around", ["do a u-turn", "turn the other way",
                                 "face the other way", "rotate one eighty"]),
    "look_up":  ("look up", ["look upward", "lift your head", "raise your head", "tilt your head up", "look at the ceiling",
                             "head up"]),
    "look_dn":  ("look down", ["look downward", "lower your head", "tilt your head down", "look at the floor",
                               "head down", "bow your head"]),
    "look_me":  ("look at me", ["look over here", "eyes on me", "face me", "turn to me", "look this way",
                                "look at my face"]),
    "stop":     ("stop", ["stop it", "stop right there", "stop moving", "freeze", "halt", "stop now", "cut it out"]),
    "sing":     ("sing a song", ["sing something", "sing for us", "give us a song", "play a song", "sing me a song",
                                 "can we hear a song", "sing one of your songs"]),
    "come_back": ("come back", ["come back to where you were", "go back to your spot", "return to where you started"]),
    "body_up":  ("raise your body", ["make yourself taller", "lift your body", "go up higher", "stand taller"]),
    "charge":   ("go charge", ["go charge yourself", "go to the charger", "go recharge", "go charge your battery"]),
}
FRAMES = {
    "bare": ["{}", "{} now", "okay, {}", "lumi, {}", "hey lumi, {}"],
    "polite": ["please {}", "{}, please", "could you {}?", "would you {}, please?", "can you {} for me?",
               "would you be so kind as to {}?", "{}, if you don't mind", "I'd like you to {}", "I need you to {}",
               "would you please {}?", "could you please {}?"],
    "casual": ["yo, {}", "{} real quick", "go ahead and {}", "c'mon, {}", "just {}", "{}, buddy", "{} already",
               "hey, {} would ya", "{} pls", "can u {}"],
    "nonnative": ["you {} please", "please you {}", "lumi you {}", "now you {}", "{} ok?", "you can {}?"],
}
NOT_NOW = ["I {}ed yesterday", "don't {}", "please don't {}", "later you can {}", "if I clap, {}", "my son wants to {}",
           "he told me to {}", "do you know how to {}?"]


def check(names=None):
    rows = []
    for name, (plain, others) in CAPS.items():
        if names and name not in names:
            continue
        want = kl.read(plain)
        for frame, forms in FRAMES.items():
            for phrase in [plain] + others:
                for f in forms:
                    t = f.format(phrase)
                    got = kl.read(t)
                    rows.append((name, frame, t, got, want, "right" if kl.same(want, got) else
                                 "missed" if got is None or got.split()[0] in kl.command_check.NO_MOTION else "wrong"))
        for f in NOT_NOW[1:3] + NOT_NOW[3:]:
            t = f.format(plain)
            got = kl.read(t)
            moves = got is not None and got.split()[0] not in kl.command_check.NO_MOTION
            rows.append((name, "not_now", t, got, "no motion", "right" if not moves else
                         "wrong" if got in ("stop", "sing") else "motion"))
    return rows


if __name__ == "__main__":
    rows = check(set(sys.argv[1:]) or None)
    out = kl.report(rows).replace("# Korean speech levels against English (tests/ko_levels_check.py)",
                                  "# English sentences of the same meaning (tests/en_paraphrase_check.py)")
    (ROOT / "logs" / "en_paraphrase.md").write_text(out)
    print(out[:out.index("## Not right")])
