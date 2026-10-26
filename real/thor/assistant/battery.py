"""The battery asked about: its level now and whether Lumi is charging, from the base's live status
(/api/robot_status power_percent, charge_state), never guessed; how long charging takes is not known.
answer(text, lang) -> what to say, or None for anything else ("how long does the battery last?" is the LLM's, 10 hours).
python assistant/battery.py "배터리 몇 프로야?" """
import re

from robot import agv

HOW_LONG_CHARGE = re.compile(
    r"\bhow (long|much time)\b.*\b(charg\w*|recharg\w*)\b|\bcharg(e|ing) time\b|\bhow fast\b.*\bcharg|"
    r"\bhow long\b.*\bfull(?:y)? charg|\bto (?:fully )?charge (?:fully|completely|all the way)\b|"
    r"(?:충전|완충)(?:하는 ?데|에|하는데|하려면|이 다 되려면|까지|되려면|시간)?.{0,6}(?:얼마나|몇 ?시간|시간이 ?얼마).{0,4}(?:걸려|걸리|걸릴|돼|되|이야|예요|이에요|인가)|"
    r"충전 ?시간|완충 ?시간", re.I)
ON_CHARGE = re.compile(r"\b(on|per|with) (a |one |the )?(full |single )?charge\b|\ba full charge last|\bneed (a |to )?(re)?charg|"
                       r"\bgo (back )?(to )?(re)?charg|한 ?번 충전(?:으로|하면)|완충(?:으로|하면|되면)|충전하면 ?(?:얼마나|몇)|"
                       r"충전하러", re.I)   # how long it lasts (10 hours), when it goes to charge: the LLM
LASTS = re.compile(r"\b(last|life|lifetime|capacity|volt|amp|ah|kind|type|made|hours?)\b|얼마나 ?가|몇 ?시간|오래 ?가|"
                   r"지속|용량|종류|볼트|수명|뭐\s*들어|무슨\s*배터리|어떤\s*배터리|\bwhat (?:kind of |type of )?battery\b|사용 ?시간|쓸 ?수 ?있는 ?시간|런타임|\bruntime\b|\bhow long\b", re.I)    # how long it lasts, what it is: the reference notes
LEVEL = re.compile(
    r"\bbattery\b.*\b(level|percent(age)?|left|status|charged|full|low|now|remaining|state|at|much|look)\b|"
    r"\b(level|percent(age)?|how much)\b.*\bbattery\b|^\W*(and |so |what about |how about )?(your |the )?battery\W*$|"
    r"배터리.{0,8}(?:몇|남|상태|퍼센트|프로|충분|얼마|어때|괜찮|있어|많|부족|없어)|^\W*(?:그럼 |그리고 )?배터리[는은요]?\W*$", re.I)
CHARGING = re.compile(
    r"\bare you (still |now |currently )?(charging|on (the |your )?charger|plugged in)\b|"
    r"\bis (it|the battery|your battery) (still |now )?charging\b|^\W*(and |so |what about |how about )?charging\W*$|"
    r"충전 ?중|충전하고 ?있|충전되고 ?있|충전 ?(?:돼|되고|되는) ?(?:있|중)|충전 ?상태|^\W*(?:그럼 |그리고 )?충전[은는]?요?\W*$", re.I)


def asked(text):
    """"now" (level / charging now), "how long" (charging time), or None."""
    text = re.sub(r"\S+—\s*", "", text or "")          # a stutter: "몇 시— 시간"
    if ON_CHARGE.search(text):
        return None
    if HOW_LONG_CHARGE.search(text):
        return "how long"
    if CHARGING.search(text) or LEVEL.search(text) and not LASTS.search(text):
        return "now"
    return None


def say_now(st, lang):
    """The sentence for a base status (None: it could not be read)."""
    pct = st.get("power_percent") if isinstance(st, dict) else None
    if pct is None:
        return "I can't read my battery right now." if lang == "en" else "지금은 배터리를 확인할 수 없어요."
    on = bool(st.get("charge_state"))
    if lang == "en":
        return f"My battery is at {pct:.0f} percent, and I'm {'charging now' if on else 'not charging'}."
    return f"배터리는 {pct:.0f}퍼센트예요. " + ("지금 충전 중이에요." if on else "지금은 충전 중이 아니에요.")


ABOUT = re.compile(r"\b(battery|charg\w*|power)\b|배터리|충전|전원", re.I)


def fact_for(text):
    """" Battery now: 53 %, not charging." for battery words answer() did not take (the LLM then never guesses it)."""
    if not ABOUT.search(text):
        return ""
    try:
        st = agv.status()
    except Exception:
        return ""
    pct = st.get("power_percent") if isinstance(st, dict) else None
    return "" if pct is None else f" Battery now: {pct:.0f} %, {'charging' if st.get('charge_state') else 'not charging'}."


def answer(text, lang="en"):
    kind = asked(text)
    if kind == "how long":
        return "How long charging takes, I don't know." if lang == "en" else "충전에 얼마나 걸리는지는 저도 잘 몰라요."
    if kind == "now":
        try:
            st = agv.status()
        except Exception:                      # the base not answering: say so, never a guess
            st = None
        return say_now(st, lang)
    return None


if __name__ == "__main__":
    import sys
    print(asked(sys.argv[1]), answer(sys.argv[1], "ko" if re.search(r"[가-힣]", sys.argv[1]) else "en"))
