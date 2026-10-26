"""Amounts and directions said in Korean, Konglish and mixed with English, as the readers must take them
(tests/test_korean_numbers.py). Written 2026-10-23 for the voice test of move / turn / look / lift.

ROUTE: said -> "move left 0.5" | "turn right 45" | "look left 20" | "lift up" | "ask" (a number with no unit, or a
unit that doesn't fit: never a guess). NORM: said -> what wording.norm must write. SAID: intent_bank.said_amount.
"""
import itertools

# ---------- spoken amounts ----------
METRES = {   # said -> metres
    "일 미터": 1, "이 미터": 2, "1미터": 1, "1 미터": 1, "1.5미터": 1.5, "일 점 오 미터": 1.5, "영 점 오 미터": 0.5,
    "1미터 반": 1.5, "일 미터 반": 1.5, "반 미터": 0.5, "1m 50cm": 1.5, "150센티": 1.5, "백오십 센티": 1.5,
    "오십 센티": 0.5, "오십 센치": 0.5, "50cm": 0.5, "이십 센티": 0.2, "스무 센티": 0.2, "열 센티": 0.1,
    "삼십 센치": 0.3, "서른 센티": 0.3, "사 십 센티": 0.4, "칠십오 센티": 0.75, "두 미터": 2, "1.5 meter": 1.5,
    "30 cm": 0.3, "마흔 센티": 0.4, "열다섯 센티": 0.15, "이십오 센티미터": 0.25, "일 미터 오십 센티": 1.5,
}
DEGREES = {  # said -> degrees
    "십오 도": 15, "사십오 도": 45, "사 십오 도": 45, "마흔다섯 도": 45, "서른 도": 30, "스무 도": 20, "열 도": 10,
    "삼십 도": 30, "육십 도": 60, "구십 도": 90, "45도": 45, "30 degrees": 30, "백이십 도": 120, "열다섯 도": 15,
    "십 도": 10, "이십 도": 20, "예순 도": 60, "칠십 도": 70, "삼 십 도": 30, "60도": 60,
}
ABOUT = ["", "만", "쯤"]   # "30센티만", "45도쯤": still that amount

MOVE_DIRS = {"앞으로": "forward", "뒤로": "back", "왼쪽으로": "left", "오른쪽으로": "right",
             "레프트로": "left", "라이트로": "right", "포워드로": "forward", "백으로": "back"}
MOVE_FORMS = ["{d} {a}{p} 가", "{d} {a}{p} 이동해 주세요"]
TURN_DIRS = {"왼쪽으로": "left", "오른쪽으로": "right", "레프트로": "left"}
TURN_FORMS = ["{d} {a}{p} 돌아", "{d} {a}{p} 돌아 줘", "{d} {a}{p} 회전해", "{d} {a}{p} 턴 해"]
LOOK_FORMS = ["고개 {d} {a}{p} 돌려", "고개를 {d} {a} 돌려 줘", "{d} {a}{p} 봐"]
LOOK_DIRS = {"왼쪽으로": "left", "오른쪽으로": "right"}


def _moves():
    out = {}
    for (d, dw), (a, n), p, f in itertools.product(MOVE_DIRS.items(), METRES.items(), ["", "만"], MOVE_FORMS):
        if n <= 3:
            out[f.format(d=d, a=a, p=p)] = f"move {dw} {n:g}"
    return out


def _turns():
    out = {}
    for (d, dw), (a, n), p, f in itertools.product(TURN_DIRS.items(), DEGREES.items(), ABOUT, TURN_FORMS):
        out[f.format(d=d, a=a, p=p)] = f"turn {dw} {n:g}"
    return out


def _looks():
    out = {}
    for (d, dw), (a, n), p, f in itertools.product(LOOK_DIRS.items(), DEGREES.items(), ["", "만"], LOOK_FORMS):
        if n <= 90:
            out[f.format(d=d, a=a, p=p)] = f"look {dw} {n:g}"
    return out


ROUTE = {**_moves(), **_turns(), **_looks(), **{
    # Konglish and mixed
    "레프트로 반 미터 가 줘요": "move left 0.5", "라이트 턴 해": "turn right 90", "레프트 턴": "turn left 90",
    "라이트로 턴": "turn right 90", "레프트 턴 해 줘": "turn left 90", "라이트로 1미터 무브": "move right 1",
    "포워드 1미터 고": "move forward 1", "백 1미터": "move back 1", "앞으로 1미터 고": "move forward 1",
    "turn left 45도": "turn left 45", "왼쪽으로 30 degrees 돌아": "turn left 30", "앞으로 1.5 meter 가": "move forward 1.5",
    "왼쪽으로 turn 해": "turn left 90", "라이트로 45도 턴": "turn right 45", "레프트로 마흔다섯 도 턴 해": "turn left 45",
    "move left 반 미터": "move left 0.5", "go forward 일 미터": "move forward 1", "turn right 서른 도": "turn right 30",
    "고개 업": "look up", "고개 다운": "look down", "머리 업": "look up", "헤드 다운": "look down",
    "고개 레프트로 돌려": "look left", "레프트 봐": "look left", "리프트 업": "lift up", "리프트 다운": "lift down",
    "백으로 50센티 가": "move back 0.5", "포워드로 1미터 가": "move forward 1",
    # whole turns, English
    "백팔십 도 돌아": "turn around 180", "turn right 90 degrees": "turn right 90",
    "turn left forty five degrees": "turn left 45", "move forward 1.5 meters": "move forward 1.5",
    "앞으로 다섯 걸음 가": "move forward 2.5", "뒤로 한 걸음": "move back 0.5",
    # no unit, or a unit that doesn't fit: asked
    "앞으로 다섯만 가": "ask", "앞으로 다섯 가": "ask", "뒤로 셋 가": "ask", "앞으로 30 가": "ask",
    "왼쪽으로 서른만 가": "ask", "앞으로 삼십만 가": "ask", "앞으로 30도 가": "ask", "뒤로 45도만 가": "ask",
    "왼쪽으로 1미터 돌아": "ask", "오른쪽으로 50센티 돌아": "ask", "왼쪽으로 서른만 돌아": "ask",
    "왼쪽으로 30 돌아": "ask", "오른쪽으로 30만 돌아": "ask", "왼쪽으로 삼십만 돌아": "ask", "오른쪽으로 열만 돌아": "ask",
    "레프트로 다섯 가": "ask", "라이트로 30만 턴": "ask",
}}

NORM = {
    "사 십오 도": "45도", "삼백 육십 도": "360도", "마흔다섯 도": "45 도", "스무 센티": "0.2 m", "일 점 오 미터": "1.5 m",
    "1미터 반": "1.5 m", "1m 50cm": "1.5 m", "150센티": "1.5 m", "반 미터": "0.5 m", "열 센티": "0.1 m",
    "레프트로 반 미터": "왼쪽으로 0.5 m", "라이트 턴 해": "오른쪽으로 돌아", "포워드 1미터 고": "앞으로 1 m 이동해",
    "백 미터 달리기": "100 m 달리기", "백팔십 도": "180도", "라이트 켜 줘": "라이트 켜 줘", "고개 업": "고개 들어",
    "백 1미터": "뒤로 1 m", "이번에": "이번에", "한 번 더": "한 번 더",
}

SAID = {   # intent_bank.said_amount: (metres, degrees)
    "왼쪽으로 사 십오 도": (None, 45), "마흔다섯 도": (None, 45), "일 점 오 미터": (1.5, None), "1미터 반": (1.5, None),
    "150센티": (1.5, None), "1m 50cm": (1.5, None), "반 미터": (0.5, None), "스무 센티": (0.2, None),
    "a quarter of a meter": (0.25, None), "a hundred and eighty degrees": (None, 180), "삼십 도": (None, 30),
}

STEPS = {   # assistant/steps.rules: the steps read whole
    "앞으로 사 십 센티 가고 왼쪽으로 마흔다섯 도 돌아": [{"do": "move", "dir": "forward", "m": 0.4}, {"do": "turn", "deg": 45.0}],
    "레프트로 반 미터 가고 라이트로 서른 도 돌아": [{"do": "move", "dir": "left", "m": 0.5}, {"do": "turn", "deg": -30.0}],
    "p3로 가서 오른쪽으로 사 십오 도 돌아": [{"do": "go", "to": "p3"}, {"do": "turn", "deg": -45.0}],
    "뒤로 일 미터 반 가고 오른쪽으로 스무 도 돌아": [{"do": "move", "dir": "back", "m": 1.5}, {"do": "turn", "deg": -20.0}],
}
