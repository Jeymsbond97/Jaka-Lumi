"""Voice confirmation of a fetch task (docs/16 §4): read the task back, listen, start / correct / cancel.

The robot parts are passed in, so this runs the same in lumi.py and in tests/test_fetch_intents.py:
    listen(seconds) -> (text or None on silence, understood)
    say(en, ko)     -> speaks one of them in the current language
    describe(task, lang) -> the read-back sentence (tasks/fetch.py)
    start(task)     -> starts the task (lumi.py turns "here" into the robot's pose first)
"""
from assistant import brain

CONFIRM_S = 5.0                    # s to wait for the answer to a question
MAX_ROUNDS = 3                     # questions asked before Lumi gives up


def _question(task, markers):
    """(en, ko) asking for the first missing field, or None when the task is complete."""
    places = ", ".join(markers)
    if task.get("object") is None:
        return ("Which object? I know cup, bottle, apple, orange and banana.",
                "어떤 물건이요? 컵, 병, 사과, 오렌지, 바나나를 알아요.")
    if task.get("source") is None:
        return (f"Where should I take it from? I know {places}.", f"어디에서 가져올까요? {places}를 알아요.")
    if task.get("dest") is None:
        return (f"Where should I bring it? I know {places}, or here.", f"어디로 가져갈까요? {places} 또는 여기요.")
    return None


def _field(task):
    """The field a bare answer ("p2") is about: the first missing place."""
    return next((f for f in ("source", "dest") if task.get(f) is None), None)


def run(task, markers, listen, say, describe, start):
    """Ask until the task is complete and confirmed. Returns 'started', 'cancelled' or 'gave_up'."""
    prompt = True                                       # False: just listen again (after "sorry" / "what to change")
    readback = False                                    # the last thing asked was "Is that right?"
    for _ in range(MAX_ROUNDS):
        if prompt:
            q = _question(task, markers)
            readback = q is None
            if readback:
                q = (describe(task, "en") + " Is that right?", describe(task, "ko") + " 맞아요?")
            say(*q)
        prompt = True
        text, understood = listen(CONFIRM_S)
        if not text:
            if readback:                                # silence after the read-back = yes
                start(task)
                return "started"
            say("Okay, cancelled.", "네, 취소할게요.")
            return "cancelled"
        if not understood:
            say("Sorry, I didn't catch that.", "죄송해요, 잘 못 들었어요.")
            prompt = False
            continue
        answer = brain.confirm_answer(text)
        if answer == "cancel":
            say("Okay, cancelled.", "네, 취소할게요.")
            return "cancelled"
        if readback and answer == "yes":
            start(task)
            return "started"
        task, changed = brain.parse_correction(text, task, markers, field=_field(task))
        if not changed and readback:                    # "no" alone, or words that change nothing
            say("What should I change?", "무엇을 바꿀까요?")
            prompt = readback = False
        # not readback and nothing changed: the same question is asked again
    say("Sorry, let's try again later.", "죄송해요, 나중에 다시 해요.")
    return "gave_up"
