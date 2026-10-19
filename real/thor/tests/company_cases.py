"""What visitors ask Lumi about Cutshion Company, and what the answer must (not) contain.

CASES = [{"text", "lang", "must", "must_not"}]: case-insensitive regexes on the spoken reply; every must has to
match, no must_not may. Facts come only from knowledge/cutshion_en.md (taken from cutshion.com); where the website
says nothing, must is a "not sure"-like phrase and must_not a made-up value. Checked by tests/company_check.py.
"""
NOT_SURE = (r"not sure|don'?t know|do not know|not known|no information|don'?t have|do not have|isn'?t (on|listed)|"
            r"not (on|listed)|not something i (have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|"
            r"없어서|가지고 있지 않|나와 있지 않|직원|문의|연락")
PRICE = r"\$\s*\d|\d[\d,.]*\s*(?:won|원|dollars?|달러|만|억|million|thousand|천)"
COUNT = r"\d+\s*(?:people|persons?|employees|staff|workers|명)"
JAKA = r"jaka|자카|제이카"
CO = r"cutshion|쿳션"            # the site writes 쿳션 ((주)쿳션); 컷션 / 커션 are wrong
OFFER = r"more|like to (know|hear)|anything|which|what else|궁금|알려 드릴|소개해 드릴|더 알고"
LONG = r"(?s)^.{350,}"            # the short company answer is short

ROBOT = r"robot|로봇"
APP = r"app|application|solution|애플리케이션|앱|솔루션"
SEOUL = r"seoul|서울"
FOUNDED = r"2022"
CEO = r"lee min|min-?seok|이민석"
BARISTA = r"barista|바리스타"
DRAW = r"draw|드로잉|그림|그려"
COFFEE = r"espresso|coffee|에스프레소|커피"
PHOTO = r"photo|picture|camera|selfie|사진|카메라|촬영"
COOK = r"cook|조리|요리"
ICE = r"ice ?cream|아이스크림"
CANDY = r"candy|캔디"
WELD = r"weld|용접"
PALLET = r"pallet|팔레"
EDU = r"educat|school|kit|교육|키트|학교"
PHONE = r"070.?8959.?2960"
EMAIL = r"cutshion@cutshion\.com|cutshion at cutshion"

CASES = []


def add(lang, rows):
    """rows: (text, must[, must_not]); must / must_not: a regex or a list of them."""
    for r in rows:
        text, must, must_not = (list(r) + [[]])[:3]
        CASES.append({"text": text, "lang": lang,
                      "must": [must] if isinstance(must, str) else list(must),
                      "must_not": [must_not] if isinstance(must_not, str) else list(must_not)})


# --- facts on the website, English
add("en", [
    ("What does Cutshion do?", [ROBOT, APP]),
    ("What kind of company is Cutshion?", [ROBOT, OFFER], LONG),
    ("Tell me about your company.", [ROBOT, OFFER], LONG),
    ("What is Cutshion?", [ROBOT, OFFER], LONG),
    ("What's Cutshion's main business?", [ROBOT]),
    ("Who made you?", CO, JAKA),
    ("Which company built you?", CO, JAKA),
    ("Where is Cutshion?", SEOUL),
    ("Where is your company located?", SEOUL),
    ("Where is the head office?", [SEOUL, r"yeongdeungpo|mullae|seonyu"]),
    ("What's the address of Cutshion?", r"seonyu|mullae|yeongdeungpo"),
    ("Is Cutshion a Korean company?", r"yes|korea"),
    ("Which country is Cutshion from?", r"korea"),
    ("Does Cutshion have an office in America?", r"mclean|virginia|yes"),
    ("Do you have a branch in Daegu?", r"yes|daegu"),
    ("Where is the Cutshion factory?", r"mullae|seoul"),
    ("Where is the research lab?", r"magok|gangseo|seoul"),
    ("When was Cutshion founded?", FOUNDED),
    ("How old is Cutshion?", FOUNDED + r"|four|4|three|3"),
    ("Who is the CEO of Cutshion?", CEO),
    ("Who founded Cutshion?", CEO),
    ("Who is the boss of your company?", CEO),
    ("What robots does Cutshion make?", [BARISTA, DRAW]),
    ("What products do you have?", [ROBOT]),
    ("What robot apps does Cutshion have?", [BARISTA]),
    ("Tell me about the barista robot.", COFFEE),
    ("What does the barista robot do?", COFFEE),
    ("Can your company's robot make coffee?", [r"yes|barista", COFFEE]),
    ("Does the barista robot replace baristas?", r"barista|repeat|together|help"),
    ("Who uses the barista robot?", r"mega|sonovictus|cafe|coffee"),
    ("Did Cutshion sell barista robots to America?", [r"200|sonovictus|yes"]),
    ("Tell me about the drawing robot.", [DRAW, PHOTO]),
    ("How does the AI drawing robot work?", [PHOTO, DRAW]),
    ("Can the robot draw my portrait?", DRAW),
    ("Where is the drawing robot used?", r"event|school|educat|promot"),
    ("What types of drawing robot are there?", r"kiosk|all-in-one"),
    ("Tell me about the cooking robot.", COOK),
    ("What is GOMCOOK?", COOK),
    ("Does Cutshion have a chicken robot?", r"chicken|chimaek|yes|cook"),
    ("Tell me about the ice cream robot.", [ICE, r"kiosk|order|touch"]),
    ("How long does the ice cream robot take?", r"30|thirty"),
    ("How many cones does the ice cream robot hold?", r"40|forty"),
    ("What is the candy ball robot?", [CANDY, r"colou?r|pick"]),
    ("How fast is the candy ball robot?", r"20|twenty"),
    ("Tell me about the welding robot.", WELD, JAKA),
    ("What does the palletizing robot do?", PALLET),
    ("Who did Cutshion make the palletizing robot with?", r"screen"),
    ("What is the educational robot?", EDU),
    ("Do you have robots for schools?", EDU),
    ("What is Pionoid?", r"platform|api"),
    ("What is CUVision?", r"vision"),
    ("Does Cutshion do AI vision?", r"vision"),
    ("Does Cutshion sell robot arms?", r"yes|collaborative|cobot|hardware", JAKA),
    ("Does Cutshion sell logistics robots?", r"tusk|yes|logistic"),
    ("Does Cutshion sell industrial robots?", r"peitian|yes|industrial"),
    ("What design software does Cutshion offer?", r"solidworks"),
    ("What is Cutshion's slogan?", r"soft.{0,5}flexible"),
    ("What is Cutshion's mission?", r"application|app"),
    ("What awards has Cutshion won?", r"roboworld|robo world|vivatech|viva ?tech"),
    ("Did Cutshion go to CES?", r"yes|ces"),
    ("Who are Cutshion's partners?", r"omron|zimmer|screen|daesung|borgwarner"),
    ("Has Cutshion received investment?", r"seed|500|cnt|evergreen|yes"),
    ("How can I contact Cutshion?", [r"phone|email|website|070|cutshion\.com|cutshion@"]),
    ("What's Cutshion's phone number?", PHONE),
    ("What's the email of your company?", EMAIL),
    ("What's Cutshion's website?", r"cutshion\.com|cutshion dot com"),
    ("I want to buy a robot. Who do I talk to?", r"contact|staff|070|email|cutshion\.com|website", PRICE),
    ("Can I buy a barista robot?", r"contact|staff|070|email|website|yes|cutshion", PRICE),
    ("Does Cutshion have a YouTube channel?", r"yes|youtube"),
    ("Is Cutshion a startup?", r"2022|yes|venture|startup|young"),
])

# --- not on the website, English
add("en", [
    ("How much does the barista robot cost?", NOT_SURE, PRICE),
    ("What's the price of the drawing robot?", NOT_SURE, PRICE),
    ("How much is the ice cream robot?", NOT_SURE, PRICE),
    ("How much do you cost?", NOT_SURE, PRICE),
    ("Can I rent a robot from Cutshion? How much per month?", NOT_SURE, PRICE),
    ("Do you give a discount?", NOT_SURE, PRICE),
    ("How many people work at Cutshion?", NOT_SURE, COUNT),
    ("How many employees does your company have?", NOT_SURE, COUNT),
    ("How big is Cutshion?", NOT_SURE, COUNT),
    ("What is Cutshion's revenue?", NOT_SURE, PRICE),
    ("Is Cutshion profitable?", NOT_SURE, PRICE),
    ("Is Cutshion listed on the stock market?", NOT_SURE),
    ("How much is Cutshion worth?", NOT_SURE, PRICE),
    ("Is Cutshion hiring?", NOT_SURE),
    ("How can I get a job at Cutshion?", NOT_SURE),
    ("What are Cutshion's office hours?", NOT_SURE, r"\d\s*(am|pm|시)|\d:\d\d"),
    ("How long does delivery of a robot take?", NOT_SURE, r"\d+\s*(days?|weeks?|months?|일|주|개월)"),
    ("What warranty do your robots have?", NOT_SURE, r"\d+\s*(years?|months?|년|개월)"),
    ("How many robots has Cutshion sold?", NOT_SURE, r"\d{3,}|\bthousands?\b"),
    ("How many customers does Cutshion have?", NOT_SURE, r"\d+\s*(customers|clients|고객)"),
    ("How old is the CEO?", NOT_SURE, r"\d+\s*(years? old|살|세)"),
    ("Is the CEO married?", NOT_SURE),
    ("What is the CEO's email?", NOT_SURE + "|" + EMAIL),
    ("Does Cutshion have an office in Japan?", NOT_SURE + r"|\bno\b|seoul|mclean|daegu"),
    ("How much does the candy ball robot cost to run per day?", NOT_SURE, PRICE),
    ("What is the price of the educational robot kit?", NOT_SURE, PRICE),
])

# --- facts on the website, Korean (반말, -요, -습니다)
add("ko", [
    ("쿳션은 뭐 하는 회사야?", ROBOT),
    ("쿳션은 무슨 회사예요?", [ROBOT, OFFER], LONG),
    ("쿳션은 어떤 회사입니까?", [ROBOT, OFFER], LONG),
    ("회사 소개 좀 해줘.", [ROBOT, OFFER], LONG),
    ("너 누가 만들었어?", CO, JAKA),
    ("어느 회사에서 만들었어요?", CO, JAKA),
    ("회사 어디 있어?", SEOUL),
    ("회사 어디 있어요?", SEOUL),
    ("본사는 어디에 있습니까?", [SEOUL, r"영등포|문래|선유"]),
    ("쿳션 주소 알려줘.", r"영등포|문래|선유"),
    ("쿳션 공장은 어디예요?", r"문래|서울"),
    ("대구에도 지사가 있어요?", r"대구|네|있"),
    ("미국에도 회사가 있어?", r"맥린|버지니아|미국"),
    ("쿳션은 언제 설립됐어요?", FOUNDED),
    ("회사 언제 만들어졌어?", FOUNDED),
    ("대표님이 누구예요?", CEO),
    ("쿳션 대표이사는 누구입니까?", CEO),
    ("창업자가 누구야?", CEO),
    ("쿳션은 어떤 로봇을 만들어요?", [BARISTA, DRAW]),
    ("무슨 로봇 만들어?", BARISTA),
    ("바리스타 로봇은 뭐예요?", COFFEE),
    ("바리스타 로봇이 뭐야?", COFFEE),
    ("바리스타 로봇에 대해 설명해 주십시오.", COFFEE),
    ("로봇이 커피도 만들어요?", COFFEE),
    ("바리스타 로봇은 어디에서 써요?", r"메가|소노빅터스|미국|카페|커피"),
    ("드로잉 로봇 알려줘.", [DRAW, PHOTO]),
    ("AI 드로잉 로봇은 어떻게 작동해요?", [PHOTO, DRAW]),
    ("로봇이 제 얼굴을 그려 줄 수 있습니까?", DRAW),
    ("조리 로봇은 뭐예요?", COOK),
    ("곰쿡이 뭐야?", COOK),
    ("아이스크림 로봇 설명해 줘.", [ICE, r"키오스크|주문|터치"]),
    ("아이스크림 하나 만드는 데 얼마나 걸려요?", r"30|삼십"),
    ("캔디볼 로봇은 뭐예요?", [CANDY, r"색|뽑"]),
    ("용접 로봇도 있어요?", WELD, JAKA),
    ("팔레타이징 로봇은 무엇입니까?", PALLET),
    ("교육용 로봇 있어?", EDU),
    ("학교에서 쓸 수 있는 로봇이 있어요?", EDU),
    ("피오노이드가 뭐예요?", r"플랫폼|api|API"),
    ("큐비전은 뭐야?", r"비전"),
    ("쿳션 슬로건이 뭐예요?", r"soft.{0,5}flexible"),
    ("상 받은 거 있어요?", r"로보월드|비바테크|vivatech|roboworld"),
    ("CES에 나갔어?", r"CES|네|나갔|참가"),
    ("파트너 회사는 어디예요?", r"오므론|omron|짐머|zimmer|스크린|대성"),
    ("투자 받았어요?", r"시드|5억|씨엔티|에버그린|네"),
    ("쿳션 연락처 알려줘.", [r"070|전화|이메일|홈페이지|cutshion"]),
    ("전화번호가 뭐예요?", PHONE),
    ("이메일 주소가 어떻게 됩니까?", EMAIL),
    ("홈페이지 주소 알려 주세요.", r"cutshion\.com|cutshion 닷컴|쿳션 닷컴"),
    ("로봇을 사고 싶은데 어떻게 해요?", r"문의|연락|직원|070|이메일|홈페이지", PRICE),
    ("물류 로봇도 팔아요?", r"TUSK|터스크|tusk|네|물류"),
    ("쿳션은 스타트업이에요?", r"2022|네|벤처|스타트업"),
])

# --- not on the website, Korean
add("ko", [
    ("바리스타 로봇 얼마예요?", NOT_SURE, PRICE),
    ("바리스타 로봇 가격이 얼마야?", NOT_SURE, PRICE),
    ("드로잉 로봇은 가격이 얼마입니까?", NOT_SURE, PRICE),
    ("아이스크림 로봇 얼마예요?", NOT_SURE, PRICE),
    ("너는 얼마야?", NOT_SURE, PRICE),
    ("로봇 렌탈도 돼요? 한 달에 얼마예요?", NOT_SURE, PRICE),
    ("직원은 몇 명이에요?", NOT_SURE, COUNT),
    ("회사 직원 몇 명이야?", NOT_SURE, COUNT),
    ("쿳션에는 몇 명이 일합니까?", NOT_SURE, COUNT),
    ("매출이 얼마예요?", NOT_SURE, PRICE),
    ("쿳션은 상장했어?", NOT_SURE),
    ("채용하고 있어요?", NOT_SURE),
    ("쿳션에 취업하려면 어떻게 해야 합니까?", NOT_SURE),
    ("회사 영업시간이 어떻게 돼요?", NOT_SURE, r"\d\s*시|\d:\d\d"),
    ("로봇 배송은 얼마나 걸려?", NOT_SURE, r"\d+\s*(일|주|개월)"),
    ("보증 기간은 얼마나 됩니까?", NOT_SURE, r"\d+\s*(년|개월)"),
    ("지금까지 로봇 몇 대 팔았어요?", NOT_SURE, r"\d{3,}\s*대"),
    ("대표님 나이가 어떻게 돼요?", NOT_SURE, r"\d+\s*(살|세)"),
    ("일본에도 사무실이 있어요?", NOT_SURE + r"|아니|없|서울|대구|미국"),
    ("교육용 로봇 키트 가격 알려줘.", NOT_SURE, PRICE),
])

# --- dialogues: follow-ups and topic switches, one Brain per dialogue (history kept).
# DIALOGUES = [{"lang", "turns": [{"text", "must", "must_not"}]}]
DIALOGUES = []


def dialogue(lang, *turns):
    """turns: (text, must[, must_not])."""
    rows = []
    for r in turns:
        text, must, must_not = (list(r) + [[]])[:3]
        rows.append({"text": text, "must": [must] if isinstance(must, str) else list(must),
                     "must_not": [must_not] if isinstance(must_not, str) else list(must_not)})
    DIALOGUES.append({"lang": lang, "turns": rows})


dialogue("en", ("What is Cutshion?", [ROBOT, OFFER], LONG), ("Tell me about the barista robot.", COFFEE),
         ("How much does it cost?", NOT_SURE, PRICE))
dialogue("en", ("Tell me about your company.", [ROBOT, OFFER], LONG), ("And what else does it make?", r"cook|ice|candy|weld|pallet|educat|draw"))
dialogue("en", ("What robots does Cutshion make?", BARISTA), ("Tell me more about the drawing robot.", [DRAW, PHOTO]))
dialogue("en", ("Tell me about the drawing robot.", DRAW), ("How does it work?", [PHOTO]))
dialogue("en", ("Where is Cutshion?", SEOUL), ("And how can I contact them?", PHONE + "|" + EMAIL))
dialogue("en", ("What is Cutshion?", ROBOT), ("How many people work there?", NOT_SURE, COUNT))
dialogue("en", ("Tell me about the ice cream robot.", ICE), ("How long does it take?", r"30|thirty"))
dialogue("en", ("What is Cutshion?", ROBOT), ("Thanks. By the way, how old are you?", r"two|2", CO))
dialogue("en", ("Tell me about the barista robot.", COFFEE), ("Okay. What's the capital of France?", r"paris", [CO, BARISTA]))
dialogue("en", ("Who made you?", CO), ("Can you speak Korean?", r"yes|korean", BARISTA))
dialogue("en", ("What does Cutshion do?", ROBOT), ("Enough about that. Tell me a joke.", r"\w", [CO, BARISTA, DRAW]))
dialogue("en", ("Where is the head office?", SEOUL), ("Can you pick up a cup?", r"yes|cup|can", CO))
dialogue("ko", ("쿳션은 무슨 회사예요?", [ROBOT, OFFER], LONG), ("바리스타 로봇은 뭐예요?", COFFEE),
         ("그거 얼마예요?", NOT_SURE, PRICE))
dialogue("ko", ("회사 소개 좀 해줘.", [ROBOT, OFFER], LONG), ("또 뭐 있어?", r"조리|아이스크림|캔디|용접|팔레|교육|드로잉"))
dialogue("ko", ("드로잉 로봇 알려줘.", DRAW), ("그거 어떻게 작동해요?", PHOTO))
dialogue("ko", ("회사 어디 있어요?", SEOUL), ("연락처는요?", PHONE + "|" + EMAIL))
dialogue("ko", ("쿳션은 어떤 회사입니까?", ROBOT), ("직원은 몇 명입니까?", NOT_SURE, COUNT))
dialogue("ko", ("쿳션이 뭐야?", ROBOT), ("고마워. 그런데 너 몇 살이야?", r"두 살|2살|2 살", CO))
dialogue("ko", ("바리스타 로봇이 뭐야?", COFFEE), ("알겠어요. 프랑스 수도는 어디예요?", r"파리", [CO, BARISTA]))
dialogue("ko", ("누가 만들었어요?", CO), ("영어도 할 수 있어요?", r"네|영어|할 수 있", BARISTA))
dialogue("ko", ("쿳션은 뭐 하는 회사야?", ROBOT), ("다른 얘기 하자. 농담 하나 해 줘.", r"[가-힣]", [CO, BARISTA, DRAW]))

from tests.company_cases_more import MORE, MORE_DIALOGUES     # written blind in a later round (2026-10-19)
for _lang, _rows in MORE:
    add(_lang, _rows)
for _lang, _turns in MORE_DIALOGUES:
    dialogue(_lang, *_turns)

if __name__ == "__main__":
    import collections
    print(len(CASES), collections.Counter(c["lang"] for c in CASES), len(DIALOGUES), "dialogues")
