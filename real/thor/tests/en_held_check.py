"""A held-out English check (written apart from en_paraphrase_check.py and bank_words/en_more.py): orders said in
sentences of their own (plain, polite, casual, non-native), each with the plain request it means; and talk that must
not move. Run on two trees to compare (PYTHONPATH=<tree> from inside it).

    .venv/bin/python tests/en_held_check.py      # -> logs/en_held.md
"""
import pathlib

from tests import ko_levels_check as kl

ROOT = pathlib.Path(__file__).resolve().parents[1]

CASES = [
    ("mind taking me to p5?", "go to p5", "polite"), ("p5, let's go", "go to p5", "casual"), ("off you go to p5", "go to p5", "casual"),
    ("you go p5 now please", "go to p5", "nonnative"), ("would you kindly make your way over to p5", "go to p5", "polite"),
    ("scoot forward a meter", "move forward one meter", "casual"), ("one meter ahead please", "move forward one meter", "polite"),
    ("you go front one meter", "move forward one meter", "nonnative"), ("back it up half a meter", "move back half a meter", "casual"),
    ("could you reverse fifty centimeters?", "move back half a meter", "polite"),
    ("hang a left", "turn left", "casual"), ("turn yourself to the left please", "turn left", "polite"), ("you turn left side", "turn left", "nonnative"),
    ("swing around the other way", "turn around", "casual"), ("would you mind turning around?", "turn around", "polite"),
    ("tip your head up", "look up", "casual"), ("could you look up at the ceiling for me?", "look up", "polite"), ("you look up please", "look up", "nonnative"),
    ("look down at your feet", "look down", "plain"), ("eyes on me buddy", "look at me", "casual"), ("would you look over at me?", "look at me", "polite"),
    ("come on over here", "come here", "casual"), ("could you come a bit closer to me?", "come here", "polite"), ("you come here please", "come here", "nonnative"),
    ("keep close behind me", "follow me", "plain"), ("come along, follow me", "follow me", "casual"), ("would you mind following me?", "follow me", "polite"),
    ("you follow me please", "follow me", "nonnative"),
    ("give the kids a wave", "wave", "plain"), ("shake my hand, robot", "wave", "casual"), ("could you wave at us?", "wave", "polite"),
    ("you shake hand with me", "wave", "nonnative"), ("let's do a handshake", "wave", "casual"),
    ("hold your hand out for me", "give me your hand", "plain"), ("could you reach your arm out?", "give me your hand", "polite"),
    ("put the arm away now", "fold your arm", "plain"), ("could you fold that arm back in?", "fold your arm", "polite"),
    ("open up your hand", "open your hand", "plain"), ("would you open the gripper please?", "open your hand", "polite"),
    ("snag the cup", "pick up the cup", "casual"), ("could you pick that cup up for me?", "pick up the cup", "polite"),
    ("you take cup please", "pick up the cup", "nonnative"),
    ("bring that cup over to me", "bring me the cup", "plain"), ("would you fetch me the cup?", "bring me the cup", "polite"),
    ("whoa whoa stop", "stop", "casual"), ("please stop right now", "stop", "polite"), ("you stop please", "stop", "nonnative"),
    ("knock it off", "stop", "casual"),
    ("sing us something", "sing a song", "casual"), ("would you sing a song for us?", "sing a song", "polite"),
    ("you sing song please", "sing a song", "nonnative"),
    ("time to charge, go", "go charge", "casual"), ("could you go to your charger?", "go charge", "polite"),
    ("speak up a bit", "speak louder", "casual"), ("could you talk a little louder?", "speak louder", "polite"),
]
NOT_NOW = [
    "I waved at a robot yesterday", "don't follow me please", "my kid wants to shake your hand later", "can you even turn left?",
    "if I raise my hand, come here", "he told me to go to p5", "the robot at the mall followed me around",
    "do you know how to sing?", "please don't pick up my cup", "we turned left at the corner",
]


def check():
    rows = []
    for t, en, level in CASES:
        want, got = kl.read(en), kl.read(t)
        rows.append(("en", level, t, got, want, "right" if kl.same(want, got) else
                     "missed" if got is None or got.split()[0] in kl.command_check.NO_MOTION else "wrong"))
    for t in NOT_NOW:
        got = kl.read(t)
        moves = got is not None and got.split()[0] not in kl.command_check.NO_MOTION
        rows.append(("en", "not_now", t, got, "no motion", "motion" if moves and got not in ("stop", "sing") else "right"))
    return rows


if __name__ == "__main__":
    out = kl.report(check()).replace("# Korean speech levels against English (tests/ko_levels_check.py)",
                                     "# English held-out orders (tests/en_held_check.py)")
    (ROOT / "logs" / "en_held.md").write_text(out)
    print(out)
