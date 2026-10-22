"""Self-check: battery questions answered from the base's live status (assistant/battery.py), EN + KO; how long it
lasts is left to the LLM (10 hours), how long charging takes is not known. Fake base: python tests/test_battery.py"""
from assistant import battery

NOW = ["And charging?", "charging?", "battery?", "Battery", "what's your battery level?", "How much battery do you have?",
       "how much battery is left", "what's your battery at", "battery percentage", "are you charging?",
       "are you charging right now", "is your battery charging", "are you on the charger?", "is your battery low?",
       "배터리 몇 프로야?", "충전 중이야?", "배터리 얼마나 남았어?", "배터리 상태 어때?", "지금 충전하고 있어?", "배터리는?",
       "배터리 충분해?", "충전 중이에요?", "그럼 충전은?", "충전은요?", "배터리 몇 퍼센트예요?"]
HOW_LONG = ["how long does charging take?", "How long does it take to charge?", "how long to recharge",
            "what's the charging time", "충전 시간 얼마나 걸려?", "충전하는 데 얼마나 걸려요?", "충전 몇 시간 걸려?"]
OTHER = ["How long does your battery last?", "how long on a charge?", "How long does the battery last on a full charge?",
         "what kind of battery do you have", "배터리 얼마나 가요?", "한 번 충전하면 몇 시간 가요?", "배터리 용량이 얼마야?",
         "go charge", "충전하러 가", "How long until you need a charge?", "at what battery level do you go back to charge",
         "배터리 몇 퍼센트에서 충전하러 가요?", "go to the charger", "Do you get tired?", "what time is it?", "배고파?"]
for t in NOW:
    assert battery.asked(t) == "now", t
for t in HOW_LONG:
    assert battery.asked(t) == "how long", t
for t in OTHER:
    assert battery.asked(t) is None, t

battery.agv.status = lambda: {"power_percent": 53, "charge_state": False}
assert battery.answer("battery?", "en") == "My battery is at 53 percent, and I'm not charging."
assert battery.answer("충전 중이야?", "ko") == "배터리는 53퍼센트예요. 지금은 충전 중이 아니에요."
battery.agv.status = lambda: {"power_percent": 87.0, "charge_state": True}
assert battery.answer("are you charging?", "en") == "My battery is at 87 percent, and I'm charging now."
assert battery.answer("배터리 몇 프로야?", "ko") == "배터리는 87퍼센트예요. 지금 충전 중이에요."
battery.agv.status = lambda: (_ for _ in ()).throw(ConnectionError())
assert "can't read" in battery.answer("battery?", "en")
assert "몰라요" in battery.answer("충전 시간 얼마나 걸려?", "ko")
battery.agv.status = lambda: {"power_percent": 53, "charge_state": False}
assert battery.fact_for("is the battery good for tonight's event?") == " Battery now: 53 %, not charging."
assert battery.fact_for("what time is it?") == ""
print(f"battery ok ({len(NOW)} now, {len(HOW_LONG)} charging time, {len(OTHER)} other)")
