"""English questions about Lumi said in many ways (plain, polite, casual / slang, kids, non-native) against the quick
answers: the same question must get the same kind. Written apart from the bank's wordings.

    .venv/bin/python tests/en_questions_check.py      # -> logs/en_questions.md
"""
import collections
import pathlib

from assistant import quick_answers as qa

ROOT = pathlib.Path(__file__).resolve().parents[1]

Q = {
    "name": {"plain": ["what's your name?", "do you have a name?"], "polite": ["may I ask your name?", "could you tell me your name?"],
             "casual": ["yo what's ur name", "what do they call you?"], "kid": ["robot what is you name?"],
             "nonnative": ["you name what?", "what is name of you?"]},
    "age": {"plain": ["how old are you?", "when were you made?"], "polite": ["may I ask how old you are?"],
            "casual": ["how old r u", "you old or new?"], "kid": ["are you a baby robot? how old?"],
            "nonnative": ["how many year you have?", "you are how old?"]},
    "maker": {"plain": ["who made you?", "which company built you?"], "polite": ["could you tell me who developed you?"],
              "casual": ["who built ya?", "who put you together?"], "kid": ["who made you robot?"],
              "nonnative": ["who is make you?", "what company make this robot?"]},
    "height": {"plain": ["how tall are you?", "what's your height?"], "polite": ["may I ask how tall you are?"],
               "casual": ["how tall r u", "you're pretty tall huh, how tall?"], "kid": ["how big are you?"],
               "nonnative": ["how much tall you are?", "you height is how much?"]},
    "weight": {"plain": ["how much do you weigh?", "how heavy are you?"], "polite": ["could you tell me your weight?"],
               "casual": ["how heavy r u", "you heavy?"], "nonnative": ["how many kilo you are?"]},
    "battery_life": {"plain": ["how long does your battery last?", "how many hours can you work?"],
                     "polite": ["could you tell me your battery life?"], "casual": ["how long u last on a charge?"],
                     "nonnative": ["battery how many hour?"]},
    "speed": {"plain": ["how fast can you go?", "what's your top speed?"], "polite": ["may I ask how fast you move?"],
              "casual": ["how quick r u", "you fast?"], "nonnative": ["your speed how much?"]},
    "languages": {"plain": ["what languages do you speak?", "do you speak korean?"], "polite": ["which languages can you understand?"],
                  "casual": ["u speak english?", "what languages u got?"], "nonnative": ["you speak which language?"]},
    "who": {"plain": ["who are you?", "what are you?"], "polite": ["could you introduce yourself?"],
            "casual": ["so what are you exactly?", "what's your deal?"], "kid": ["what kind of robot are you?"],
            "nonnative": ["you are what?"]},
    "time_now": {"plain": ["what time is it?", "do you know the time?"], "polite": ["could you tell me the time?"],
                 "casual": ["what time's it?", "got the time?"], "nonnative": ["now what time?"]},
    "date_today": {"plain": ["what's the date today?", "what day is it today?"], "polite": ["could you tell me today's date?"],
                   "casual": ["what's today's date?"], "nonnative": ["today is what date?"]},
    "how_are_you": {"plain": ["how are you?", "how's it going?"], "polite": ["how are you doing today?"],
                    "casual": ["sup lumi", "how ya doin?"], "nonnative": ["you are fine?"]},
    "can_sing": {"plain": ["can you sing?", "do you sing?"], "polite": ["are you able to sing?"],
                 "casual": ["u sing?", "can u sing tho?"], "nonnative": ["you can singing?"]},
    "cameras": {"plain": ["how many cameras do you have?", "where are your cameras?"], "polite": ["what cameras do you use?"],
                "casual": ["where ur eyes at?"], "nonnative": ["camera how many you have?"]},
    "safety": {"plain": ["are you safe?", "is it safe to stand next to you?"], "polite": ["is it safe for children to be near you?"],
               "casual": ["u gonna hurt me?"], "nonnative": ["you are dangerous?"]},
    "stairs": {"plain": ["can you climb stairs?", "can you go up steps?"], "polite": ["are you able to use stairs?"],
               "casual": ["u do stairs?"], "nonnative": ["you can go stair?"]},
    "estop": {"plain": ["where is your emergency stop?", "how do I stop you in an emergency?"],
              "polite": ["could you show me the emergency stop button?"], "casual": ["where's ur kill switch?"]},
}


def check():
    rows = []
    for kind, levels in Q.items():
        for level, texts in levels.items():
            for t in texts:
                got = qa.kind_of(t)
                rows.append((kind, level, t, got, "right" if got == kind else "missed" if got is None else "wrong"))
    return rows


if __name__ == "__main__":
    rows = check()
    by = collections.defaultdict(collections.Counter)
    for kind, level, t, got, v in rows:
        by[level][v] += 1
    lines = ["# English questions in many ways (tests/en_questions_check.py)", "",
             "| way | right | missed | wrong | total |", "|---|---|---|---|---|"]
    for level, c in by.items():
        lines.append(f"| {level} | {c['right']} | {c['missed']} | {c['wrong']} | {sum(c.values())} |")
    tot = collections.Counter(v for *_, v in rows)
    lines += [f"| all | {tot['right']} | {tot['missed']} | {tot['wrong']} | {len(rows)} |", "", "## Not right", ""]
    lines += [f"- {k} [{lv}] {t!r} -> {got}" for k, lv, t, got, v in rows if v != "right"]
    out = "\n".join(lines) + "\n"
    (ROOT / "logs" / "en_questions.md").write_text(out)
    print(out)
