"""Self-check: amounts and directions in Korean, Konglish and mixed (tests/korean_numbers_cases.py) read exactly by
wording.norm, the route lumi.answer() takes before the LLM and intent_bank.said_amount; a number
without a fitting unit is asked. No robot: python tests/test_korean_numbers.py"""
import math

import no_robot                                     # noqa: F401  any connection to the robot fails the test
from assistant import brain, intent_bank, steps, wording
from tests import command_check
from tests.korean_numbers_cases import NORM, ROUTE, SAID, STEPS

M = ["home", "p3", "dock2"]
B = brain.Brain()


def route(text):
    """lumi.answer()'s route before the LLM (tests/command_check.rules): 'move left 0.5' | 'turn right 45' |
    'look left 20' | 'lift up' | 'ask' | None (left to the LLM)."""
    got = command_check.rules(text, "idle", M, B)
    return got[len("action:"):] if got and got.startswith("action:") else got


def main():
    bad = []
    for said, want in NORM.items():
        got = wording.norm(said)
        if want not in got:
            bad.append(f"norm {said!r}: {got!r}, want {want!r}")
    for said, want in SAID.items():
        got = intent_bank.said_amount(said)
        if not all(a == b or (a is not None and b is not None and math.isclose(a, b)) for a, b in zip(got, want)):
            bad.append(f"said_amount {said!r}: {got}, want {want}")
    for said, want in ROUTE.items():
        got = route(said)
        if got != want:
            bad.append(f"route {said!r}: {got}, want {want}")
    for said, want in STEPS.items():
        got = steps.rules(said, M)
        if got != (want, []):
            bad.append(f"steps {said!r}: {got}, want {want}")
    for b in bad:
        print(b)
    n = len(NORM) + len(SAID) + len(ROUTE) + len(STEPS)
    print(f"{n - len(bad)}/{n} right")
    assert not bad


if __name__ == "__main__":
    main()
