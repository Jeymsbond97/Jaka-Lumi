"""Quick answers about Cutshion Company (assistant/quick_answers.py): what a visitor asks first about the company that
developed Lumi, answered at once. Every answer is a fact of knowledge/cutshion_en.md; keep them in step. What the notes
do not know (prices, employees, revenue, hiring, the next exhibition) is answered "not known" with the way to ask.
The talk after it ("tell me more", "and the price?") goes to the LLM with the company notes (brain.COMPANY_TALK).

Wordings are made from each kind's English frames and Korean stems with every way of naming the company and every
Korean speech level (반말, 해요체, 하십시오체, honorific, dialect), plus Konglish and whisper slips.
"""

EN_CO = ["cutshion", "cutshion company", "your company", "cushion", "cutsion"]
KO_CO = ["쿳션", "쿳션은", "쿳션이", "쿠션", "커션", "컷션", "너희 회사", "니네 회사", "루미 만든 회사", "회사"]
ASK = ["야", "예요", "에요", "니", "입니까", "인가요", "이에요", "고", "여", "죠", "임", "이야", "이세요"]     # after a noun
HOW = ["어떻게 돼", "어떻게 돼요", "어떻게 되니", "어떻게 되나요", "어떻게 되세요", "어떻게 되십니까", "어떻게 됩니까", "어떻게 되노", "우째 되노"]
TELL = ["알려 줘", "알려 주세요", "알려 줄래", "알려 주실래요", "알려 주시겠어요", "말해 줘", "말해 주세요", "가르쳐 줘", "좀 알려 줘",
        "좀 알려 주세요", "궁금해요", "궁금합니다", "알려 주십시오"]


def _en(frames):
    return [f.format(c=c) for f in frames for c in EN_CO]


def _ko(stems, ends=None):
    """stems with "{c}" (the company) and optional endings."""
    out = []
    for s in stems:
        for c in KO_CO:
            t = s.format(c=c)
            out.extend([t + e for e in ends] if ends else [t])
    return out


SPEC = {
    "co_what": (
        ["what is {c}", "what's {c}", "tell me about {c}", "about {c}", "{c}", "what kind of company is {c}", "what does {c} do", "who is {c}",
         "what does {c} make", "can you tell me about {c}", "what's {c} about", "introduce {c}", "{c} what is it",
         "what business is {c} in", "give me the short version of {c}"],
        _ko(["{c} 뭐", "{c} 무슨 회사", "{c} 어떤 회사"], ASK) + _ko(["{c} 뭐 하는 회사", "{c} 뭐 하는 곳"], ASK) +
        _ko(["{c} 소개 ", "{c}에 대해 "], TELL) + _ko(["{c} 뭐 만들어", "{c} 뭐 만들어요", "{c} 뭐 만드니", "{c} 뭐 만듭니까",
                                                     "{c} 뭐 만드세요", "{c} 뭐 하는데", "{c} 뭐 하노", "{c} 뭐 해요"]),
        {"en": ["Cutshion is a Korean robot company, founded in 2022, that makes robot applications, such as barista, AI drawing, "
                "cooking and ice cream robots. Its head office is in Seoul. What would you like to know more about?",
                "Cutshion Company developed me. It's a young robot company from Seoul, founded in 2022, that builds robot apps like "
                "barista, drawing, cooking and ice cream robots. What else would you like to know?"],
         "ko": ["쿳션은 2022년에 설립된 한국 로봇 회사로, 바리스타 로봇, AI 드로잉 로봇, 조리 로봇, 아이스크림 로봇 같은 로봇 "
                "애플리케이션을 만들어요. 본사는 서울에 있어요. 더 궁금하신 점이 있으세요?",
                "쿳션은 저를 개발한 서울의 로봇 회사예요. 2022년에 설립됐고, 바리스타, 드로잉, 조리, 아이스크림 로봇 같은 로봇 앱을 "
                "만들어요. 또 궁금하신 게 있으세요?"]}),
    "co_founded": (
        ["when was {c} founded", "when was {c} started", "when did {c} start", "how old is {c}", "what year was {c} founded",
         "when was {c} established", "since when does {c} exist", "how long has {c} been around", "{c} founded when",
         "how old is the company", "when was the company founded"],
        _ko(["{c} 언제 생겼어", "{c} 언제 생겼어요", "{c} 언제 생겼니", "{c} 언제 설립됐어요", "{c} 언제 설립됐습니까", "{c} 언제 세워졌어",
             "{c} 언제 만들어졌어요", "{c} 몇 년 됐어", "{c} 몇 년 됐어요", "{c} 몇 년 되셨어요", "{c} 몇 년 됐노", "{c} 생긴 지 얼마나 됐어요",
             "{c} 몇 년도에 생겼어", "{c} 창립이 언제예요", "{c} 설립 연도가 언제예요", "{c} 설립일이 언제입니까", "{c} 언제 창업했어요",
             "{c} 언제 시작했어", "{c} 몇 살이야", "{c} 나이가 어떻게 돼요"]) + ["회사 몇 년 됐어요", "회사 언제 생겼어요"],
        {"en": ["Cutshion was founded in July 2022, so it's a young startup.",
                "In July 2022. Cutshion is a young robot startup, a certified venture business."],
         "ko": ["쿳션은 2022년 7월에 설립됐어요. 젊은 스타트업이에요.",
                "2022년 7월에 법인을 설립했어요. 벤처기업 인증을 받은 젊은 로봇 스타트업이에요."]}),
    "co_ceo": (
        ["who is the ceo of {c}", "who's {c}'s ceo", "who runs {c}", "who is the boss of {c}", "who founded {c}",
         "who is the founder of {c}", "who leads {c}", "who is the president of {c}", "what's the name of {c}'s ceo",
         "who is the ceo", "who's the ceo", "who's your ceo", "who is your boss", "what is the name of the ceo"],
        _ko(["{c} 대표가 누구", "{c} 대표님이 누구", "{c} 사장이 누구", "{c} 사장님이 누구", "{c} 대표이사가 누구", "{c} 창업자가 누구",
             "{c} 대표 이름이 뭐", "{c} 대표님 성함이 뭐"], ASK) +
        _ko(["{c} 대표님 성함이 어떻게 되세요", "{c} 대표님 성함이 어떻게 되십니까", "{c} 누가 세웠어", "{c} 누가 세웠어요", "{c} 누가 창업했어요", "{c} 누가 운영해요", "{c} 대표님은 누구신가요", "{c} 대표 누고",
             "{c} 대표 누구여", "{c} 대표 누군데", "{c} 대표 알려 줘", "{c} ceo가 누구야", "{c} ceo 누구예요"]) +
        ["대표가 누구예요", "대표 이름이 뭐예요", "대표님 이름이 뭐예요", "대표님 성함이 어떻게 되세요", "사장님이 누구예요"],
        {"en": ["Cutshion's CEO is Lee Min-seok. Cutshion is his third company.",
                "Lee Min-seok is the CEO of Cutshion; it's the third company he has founded."],
         "ko": ["쿳션의 대표이사는 이민석 대표님이에요. 쿳션은 대표님의 세 번째 회사예요.",
                "이민석 대표님이 쿳션의 대표이사예요. 대표님이 세 번째로 세운 회사예요."]}),
    "co_hq": (
        ["where is {c}", "where's {c}", "where is {c} located", "where is {c}'s office", "where is {c}'s head office",
         "what's {c}'s address", "where is {c} based", "is {c} in seoul", "which city is {c} in", "where are you from company",
         "where is the company", "where is the head office", "what's the company's address", "where is your company"],
        _ko(["{c} 어디 있어", "{c} 어디 있어요", "{c} 어디 있니", "{c} 어디 있습니까", "{c} 어디 있으세요", "{c} 어디예요", "{c} 어디야",
             "{c} 어디에 있나요", "{c} 어디 있노", "{c} 어딨어", "{c} 어딨어요", "{c} 본사가 어디예요", "{c} 본사 어디야", "{c} 본사 위치가 어디입니까",
             "{c} 주소가 어떻게 돼요", "{c} 주소 알려 줘", "{c} 주소가 어디예요", "{c} 사무실 어디예요", "{c} 사무실이 어디 있어요",
             "{c} 위치가 어디예요", "{c} 서울에 있어요", "{c} 어느 동네에 있어요", "{c} 어데 있노", "{c} 어디 있슈"]) +
        ["회사 어디 있어요", "본사가 어디예요", "회사 위치가 어디예요"],
        {"en": ["Cutshion's head office is in Seoul: room 709, Mullae SK V1 Center, 10 Seonyu-ro 9-gil, Yeongdeungpo-gu.",
                "In Seoul, Korea. The head office is at the Mullae SK V1 Center in Yeongdeungpo-gu, room 709."],
         "ko": ["쿳션 본사는 서울시 영등포구 선유로 9길 10, 문래 SK V1 Center 709호예요.",
                "서울 영등포구에 있어요. 본사는 문래 SK V1 Center 709호예요."]}),
    "co_offices": (
        ["does {c} have other offices", "where are {c}'s offices", "does {c} have a factory", "where is {c}'s factory",
         "does {c} have a branch in daegu", "does {c} have an office in america", "does {c} have a us office",
         "where is {c}'s research lab", "does {c} have a lab", "how many offices does {c} have", "is {c} in the us"],
        _ko(["{c} 지사 있어요", "{c} 지사 어디 있어요", "{c} 지사가 어디야", "{c} 공장 있어요", "{c} 공장 어디예요", "{c} 공장이 어디 있습니까",
             "{c} 연구소 어디예요", "{c} 연구소 있어", "{c} 대구 지사 있어요", "{c} 미국 법인 있어요", "{c} 미국에도 있어요", "{c} 미국 지사 어디야",
             "{c} 강남 사무소 어디예요", "{c} 사무실 몇 개예요", "{c} 지점 어디 있노", "{c} 해외 지사 있어요"]) +
        ["where is the factory", "공장이 어디예요", "쿳션 공장 어디 있어요"],
        {"en": ["Besides the head office in Seoul, Cutshion has the Mullae Factory in the same building, a Gangnam office, a research "
                "lab in Gangseo-gu, a Daegu branch and a US company in McLean, Virginia.",
                "Cutshion's places: the Seoul head office and Mullae Factory, a Gangnam office, a research lab in Magok, a branch in "
                "Daegu, and a US company in McLean, Virginia."],
         "ko": ["서울 본사 말고도, 같은 건물에 쿳션 문래 팩토리가 있고, 강남사무소, 강서구 마곡 연구소, 대구지사, 미국 버지니아주 "
                "맥린의 미국법인이 있어요.",
                "본사와 문래 팩토리는 서울 영등포구에 있고, 강남사무소, 마곡 연구소, 대구지사, 미국 맥린에 미국법인이 있어요."]}),
    "co_contact": (
        ["how do i contact {c}", "how can i contact {c}", "what's {c}'s phone number", "{c} phone number", "{c} email",
         "what's {c}'s email", "what is {c}'s website", "{c} website", "how can i reach {c}", "contact {c} how",
         "how do i get in touch with {c}", "what's the company's phone number", "{c} contact info"],
        _ko(["{c} 연락처", "{c} 전화번호", "{c} 이메일", "{c} 메일 주소", "{c} 홈페이지", "{c} 웹사이트"], ["", " 알려 줘", " 알려 주세요",
                                                                                                  "가 뭐예요", " 뭐야", "가 어떻게 돼요",
                                                                                                  "가 어떻게 되십니까", " 있어요", " 좀"]) +
        _ko(["{c}에 어떻게 연락해요", "{c}에 연락하려면 어떻게 해요", "{c}에 문의하려면 어떻게 해", "{c} 연락 어떻게 하노",
             "{c}에 어떻게 연락드려요", "{c} 문의는 어디로 해요"]),
        {"en": ["You can reach Cutshion at 070-8959-2960 or cutshion@cutshion.com, or through the contact form on cutshion.com.",
                "Phone 070-8959-2960, email cutshion@cutshion.com, and the website is cutshion.com."],
         "ko": ["쿳션 연락처는 전화 070-8959-2960, 이메일 cutshion@cutshion.com이에요. 홈페이지 cutshion.com의 문의하기도 있어요.",
                "전화는 070-8959-2960, 이메일은 cutshion@cutshion.com, 홈페이지는 cutshion.com이에요."]}),
    "co_slogan": (
        ["what is {c}'s slogan", "{c} slogan", "what's {c}'s motto", "what is {c}'s mission", "what's {c}'s goal",
         "what is {c}'s vision", "what does {c} want to become"],
        _ko(["{c} 슬로건이 뭐", "{c} 슬로건", "{c} 모토가 뭐", "{c} 목표가 뭐", "{c} 비전이 뭐", "{c} 미션이 뭐", "{c} 캐치프레이즈가 뭐"], ASK),
        {"en": ["Cutshion's slogan is \"Soft & Flexible Idea\", and its mission is to be \"The Best Robot Application Provider\": "
                "not only building robots, but robot apps and an ecosystem for them."],
         "ko": ["쿳션의 슬로건은 'Soft & Flexible Idea'예요. 로봇을 만들고 파는 것을 넘어 로봇 애플리케이션 생태계를 만드는 "
                "'The Best Robot Application Provider'가 목표예요."]}),
    "co_products": (
        ["what robots does {c} make", "what products does {c} have", "what does {c} sell", "which robots does {c} build",
         "list {c}'s robots", "what are {c}'s products", "{c} products", "what robot apps does {c} make",
         "what robots does the company make", "what does your company make", "what other robots do you have"],
        _ko(["{c} 제품 뭐 있어", "{c} 제품 뭐 있어요", "{c} 제품이 뭐예요", "{c} 무슨 로봇 만들어", "{c} 무슨 로봇 만들어요", "{c} 어떤 로봇 만들어요",
             "{c} 어떤 로봇 만듭니까", "{c} 로봇 종류가 뭐 있어요", "{c} 로봇 뭐 있어", "{c} 제품 알려 줘", "{c} 제품 소개해 주세요", "{c} 뭐 팔아요",
             "{c} 무슨 제품 팔아", "{c} 로봇 뭐 만드노", "{c} 로봇 라인업이 어떻게 돼요", "{c} 어떤 로봇 있으세요", "{c} 다른 로봇도 있어요"]) +
        ["회사는 어떤 로봇 만들어", "회사에서 무슨 로봇 만들어요", "쿳션은 뭐 만들어요"],
        {"en": ["Cutshion's robot apps are a barista robot, an AI drawing robot, a welding robot, a palletizing robot, a cooking "
                "robot, an ice cream robot, a candy ball robot and an educational robot kit. Its own technology is CUVision, "
                "Pionoid and GOMCOOK. Ask me about any of them."],
         "ko": ["쿳션의 로봇 앱은 바리스타 로봇, AI 드로잉 로봇, 용접 로봇, 팔레타이징 로봇, 조리 로봇, 아이스크림 로봇, 캔디볼 로봇, "
                "교육용 로봇이에요. 자체 기술로 큐비전, 피오노이드, 곰쿡이 있어요. 궁금한 로봇이 있으면 물어보세요."]}),
    "co_awards": (
        ["has {c} won any awards", "did {c} win any awards", "what awards has {c} won", "{c} awards", "any awards for {c}",
         "what prizes did {c} get", "has {c} won anything"],
        _ko(["{c} 상 받은 거 있어", "{c} 상 받은 거 있어요", "{c} 수상 경력 있어요", "{c} 수상 내역이 어떻게 돼요", "{c} 무슨 상 받았어요",
             "{c} 어떤 상 받았어", "{c} 상 탔어요", "{c} 수상 경력이 있습니까", "{c} 상 받은 적 있노", "{c} 어워드 받았어요"]),
        {"en": ["Cutshion won the RoboWorld Award 2023 for GOMCOOK, the RoboWorld Award 2024 for its mobile welding robot, the "
                "Excellence Award at the Venturium Demo Day in 2026, and the VivaTech Tech for Change Award in Paris in 2026."],
         "ko": ["쿳션은 로보월드 어워드 2023(곰쿡), 로보월드 어워드 2024(모바일 용접 로봇), 2026 벤처리움 데모데이 우수상, "
                "2026 비바테크 Tech for Change Award를 받았어요."]}),
    "co_exhibitions": (
        ["which exhibitions has {c} been to", "what shows did {c} attend", "was {c} at ces", "has {c} been to ces",
         "where has {c} exhibited", "{c} exhibitions", "which trade fairs did {c} join"],
        _ko(["{c} 전시회 어디 나갔어요", "{c} 어느 전시회 갔어요", "{c} 전시회 참가했어요", "{c} CES 나갔어요", "{c} 시이에스 갔어",
             "{c} 전시 이력이 어떻게 돼요", "{c} 박람회 나간 적 있어요", "{c} 어떤 전시회 나갔습니까", "{c} 전시회 어데 갔노"]),
        {"en": ["Cutshion has shown its robots at RoboWorld, IFA Berlin, the Gangnam Robot Plus Festival, Smart Life Week, the Korea "
                "ICT Expo in Japan, CES in Las Vegas in 2025 and 2026, the NRA Show in Chicago and VivaTech in Paris."],
         "ko": ["쿳션은 로보월드, 베를린 IFA, 강남 로봇 플러스 페스티벌, 스마트 라이프 위크, 일본 코리아 ICT 엑스포, 라스베이거스 "
                "CES 2025와 2026, 시카고 NRA 쇼, 파리 비바테크에 참가했어요."]}),
    "co_investment": (
        ["has {c} got investors", "who invested in {c}", "did {c} get investment", "how much funding does {c} have",
         "is {c} funded", "{c} investment", "has {c} raised money"],
        _ko(["{c} 투자 받았어요", "{c} 투자 받은 적 있어", "{c} 투자자가 누구예요", "{c} 누가 투자했어요", "{c} 투자 얼마 받았어요",
             "{c} 투자 유치했어요", "{c} 팁스 선정됐어요", "{c} 벤처기업이에요", "{c} 투자 받았노"]),
        {"en": ["In August 2025 Cutshion got a seed investment of 500 million won from CNT Tech and Evergreen Investment Partners, "
                "and in December 2025 it was selected for the TIPS Global Track program."],
         "ko": ["쿳션은 2025년 8월 씨엔티테크와 에버그린투자파트너스에서 5억 원 시드 투자를 받았고, 2025년 12월 팁스 글로벌 트랙에 "
                "선정됐어요."]}),
    "co_partners": (
        ["who are {c}'s partners", "{c} partners", "which companies does {c} work with", "does {c} work with omron",
         "who does {c} partner with"],
        _ko(["{c} 파트너사가 어디예요", "{c} 협력사가 어디야", "{c} 파트너 회사 알려 줘", "{c} 어느 회사랑 일해요", "{c} 협력 업체가 어디입니까"]),
        {"en": ["Cutshion's website lists partners such as OMRON, Zimmer Group Korea, Screen HD Korea, BorgWarner and THIRA Robotics, "
                "and in 2026 it signed a partnership with PEITIAN Robotics."],
         "ko": ["쿳션 홈페이지에는 오므론, 짐머 그룹 코리아, 스크린 HD 코리아, 보그워너, 티라로보틱스 같은 파트너사가 있고, 2026년에 "
                "PEITIAN 로보틱스와 파트너십을 맺었어요."]}),
    "co_unknown": (
        ["how many employees does {c} have", "how many people work at {c}", "how big is {c}", "what is {c}'s revenue",
         "how much money does {c} make", "is {c} hiring", "can i work at {c}", "how do i get a job at {c}", "is {c} on the stock market",
         "is {c} listed", "what are {c}'s opening hours", "how many robots has {c} sold", "what's {c}'s sales",
         "what is {c}'s next exhibition", "where will {c} exhibit next", "which show is {c} going to next",
         "how many employees does the company have", "how many people work there", "is the company hiring"],
        _ko(["{c} 직원 몇 명이에요", "{c} 직원이 몇 명이야", "{c} 직원 수가 어떻게 돼요", "{c} 직원 몇 명 있어", "{c} 사람 몇 명 일해요",
             "{c} 매출이 얼마예요", "{c} 매출 얼마야", "{c} 돈 얼마 벌어요", "{c} 채용해요", "{c} 채용 중이에요", "{c} 입사하려면 어떻게 해요",
             "{c} 상장했어요", "{c} 상장 회사예요", "{c} 영업시간이 어떻게 돼요", "{c} 몇 시에 문 열어요", "{c} 로봇 몇 대 팔았어요",
             "{c} 판매 대수가 어떻게 돼요", "{c} 직원 몇 명이고", "{c} 다음 전시회 어디예요", "{c} 다음 전시회 언제 나가요",
             "{c} 다음에 어느 전시회 가요", "{c} 다음 전시 일정이 어떻게 됩니까", "{c} 직원 수가 어떻게 되십니까", "{c} 규모가 어떻게 돼요"]) +
        ["직원이 몇 명이에요", "직원 몇 명이에요"],
        {"en": ["I don't have that information. Please ask a staff member, or contact Cutshion at 070-8959-2960 or "
                "cutshion@cutshion.com."],
         "ko": ["그건 제가 가진 정보가 없어요. 직원에게 물어보시거나 쿳션(070-8959-2960, cutshion@cutshion.com)에 문의해 주세요."]}),
    "price": (
        ["how much is this robot", "what's the price of this robot", "how much does lumi cost", "how much does a robot like you cost",
         "can i buy you", "are you for sale", "can i rent you", "how much to rent you", "is lumi for sale",
         "how much is the barista robot", "how much does the ice cream robot cost", "what do cutshion's robots cost",
         "how much does {c} charge for a robot", "{c} robot prices", "how expensive are you"],
        ["가격이 어떻게 돼요", "가격이 어떻게 되세요", "가격이 어떻게 됩니까", "가격 알려 줘", "가격 알려 주세요", "가격이 궁금해요", "로봇 가격이 어떻게 돼요",
         "루미 가격이 어떻게 돼요", "너 가격 알려 줘", "너 살 수 있어요", "너 팔아요", "너 판매해요", "루미 판매해요", "렌탈 돼요", "대여 돼요",
         "렌탈 가격 알려 주세요", "바리스타 로봇 가격 알려 주세요", "아이스크림 로봇 가격이 어떻게 돼요", "로봇 사고 싶어요", "이 로봇 사려면 어떻게 해요",
         "구매하려면 어떻게 해요", "가격 좀 알려 주실래요", "가격 우째 되노", "값이 어떻게 돼요", "price 알려 줘", "가격 how much"] +
        _ko(["{c} 로봇 가격 알려 주세요", "{c} 로봇 가격이 어떻게 돼요", "{c} 로봇 사려면 어떻게 해요"]) +
        [w + n + e for w in ["", "이 로봇 ", "로봇 ", "루미 ", "너 "] for n in ["가격 ", "값 "]   # every speech level
         for e in ["알려 줘", "좀 알려 줘", "알려 주세요", "좀 알려 주세요", "알려 주십시오", "말해 주세요", "얼마야", "얼마예요", "얼마입니까",
                   "얼마세요", "얼마고", "얼만교", "어떻게 되나요"]],
        {"en": ["I don't know the prices: they aren't on Cutshion's website. Please ask a staff member, or contact Cutshion at "
                "070-8959-2960 or cutshion@cutshion.com."],
         "ko": ["가격은 홈페이지에 없어서 저도 몰라요. 직원에게 물어보시거나 쿳션(070-8959-2960, cutshion@cutshion.com)에 문의해 주세요."]}),
}

ROBOTS = {   # one robot app or technology of Cutshion: (English names, Korean names, answers)
    "co_barista": (["barista robot", "coffee robot", "robot barista"], ["바리스타 로봇", "커피 로봇", "로봇 바리스타", "바리스타 로봇은"],
                   {"en": ["Cutshion's barista robot makes espresso fully automatically: it runs a real espresso machine and grinds, doses, "
                           "tamps and extracts by itself, with the same taste every time. Mega Coffee signed a yearly supply agreement for it."],
                    "ko": ["쿳션의 바리스타 로봇은 에스프레소 머신을 직접 제어해서 원두 분쇄, 도징, 탬핑, 추출까지 완전히 자동으로 해요. "
                           "언제나 같은 맛을 내고, 메가커피와 연간 공급 계약을 맺었어요."]}),
    "co_drawing": (["drawing robot", "ai drawing robot", "portrait robot", "painting robot"], ["드로잉 로봇", "그림 그리는 로봇", "AI 드로잉 로봇", "초상화 로봇"],
                   {"en": ["Cutshion's AI drawing robot takes your photo, AI turns it into a line drawing, and the robot arm draws it on a "
                           "canvas. One button starts it, and it's popular at events and in education."],
                    "ko": ["쿳션의 AI 드로잉 로봇은 사진을 찍으면 AI가 라인 드로잉으로 바꾸고, 로봇 팔이 캔버스에 그려 줘요. 버튼 하나로 "
                           "시작하고, 행사와 교육에서 인기가 많아요."]}),
    "co_cooking": (["cooking robot", "chicken robot", "kitchen robot", "chimaek robot"], ["조리 로봇", "요리 로봇", "치킨 로봇", "치맥 로봇"],
                   {"en": ["Cutshion's cooking robot is an AI cooking robot for personalised cooking, with Cutshion's own vision and the "
                           "GOMCOOK platform. It keeps the taste the same and lowers staff and ingredient costs."],
                    "ko": ["쿳션의 조리 로봇은 개인 맞춤 조리를 하는 AI 조리 로봇이고, 곰쿡 플랫폼과 함께 써요. 같은 맛을 지키고 인건비와 "
                           "식재료 비용을 줄여 줘요."]}),
    "co_icecream": (["ice cream robot", "icecream robot", "soft ice cream robot"], ["아이스크림 로봇", "아이스크림 기계", "소프트아이스크림 로봇"],
                    {"en": ["Cutshion's ice cream robot serves soft ice cream with no staff: you order on a kiosk and it makes and hands "
                            "over the ice cream in about 30 seconds. It holds 40 cones and weighs 500 kg."],
                     "ko": ["쿳션의 아이스크림 로봇은 키오스크 주문부터 아이스크림 추출, 전달까지 무인으로 해요. 한 개에 약 30초가 걸리고 "
                            "콘을 40개 넣을 수 있어요. 무게는 500kg이에요."]}),
    "co_candyball": (["candy ball robot", "candy robot", "candyball robot"], ["캔디볼 로봇", "사탕 로봇", "캔디 로봇"],
                     {"en": ["Cutshion's candy ball robot is a fun event robot: you choose a colour on the touch screen, and it picks a "
                             "candy ball of that colour and gives it to you, in about 20 seconds."],
                      "ko": ["쿳션의 캔디볼 로봇은 터치스크린에서 고른 색의 캔디볼을 로봇이 뽑아서 주는 체험형 로봇이에요. 한 번에 약 "
                             "20초가 걸려요."]}),
    "co_welding": (["welding robot", "welder robot", "mobile welding robot"], ["용접 로봇", "웰딩 로봇", "모바일 용접 로봇"],
                   {"en": ["Cutshion's welding robot is a light collaborative welding robot: multi-pass arc welding, automatic seam "
                           "tracking, taught by dragging the arm. The mobile welding robot won the RoboWorld Award 2024."],
                    "ko": ["쿳션의 용접 로봇은 가벼운 협동 용접 로봇이에요. 다층 아크 용접과 용접선 자동 추적을 하고, 모바일 용접 로봇으로 "
                           "로보월드 어워드 2024를 받았어요."]}),
    "co_palletizing": (["palletizing robot", "palletising robot", "palletizer", "stacking robot"], ["팔레타이징 로봇", "적재 로봇", "팔레트 로봇"],
                       {"en": ["Cutshion's palletizing robot stacks finished products on pallets and can run 24 hours. Made with Screen, "
                               "it's Korea's first palletizing robot for book publishing: up to 20 kg, about 15 seconds a cycle."],
                        "ko": ["쿳션의 팔레타이징 로봇은 완성품을 팔레트에 자동으로 쌓고 24시간 돌릴 수 있어요. 스크린사와 함께 만든 "
                               "국내 최초 출판 전용 팔레타이징 로봇이고, 20kg까지, 한 번에 약 15초예요."]}),
    "co_edukit": (["educational robot", "education kit", "robot training kit", "edu kit"], ["교육용 로봇", "교육 로봇", "교육 키트", "실습 키트"],
                  {"en": ["Cutshion's educational robot is an all-in-one training kit in one flight case: a small cobot arm, practice "
                          "modules, digital twin software and course materials, for schools, universities and companies."],
                   "ko": ["쿳션의 교육용 로봇은 협동로봇, 실습 모듈, 디지털 트윈 소프트웨어, 교육 자료를 휴대용 케이스 하나에 담은 올인원 "
                          "키트예요. 학교, 대학, 연구소, 기업 교육에 써요."]}),
    "co_cuvision": (["cuvision", "cu vision", "cutshion's ai vision"], ["큐비전", "쿠비전", "AI 비전"],
                    {"en": ["CUVision is Cutshion's AI vision technology: it understands camera images, checks work piece surfaces and "
                            "tracks 3D movement, for example for quality checks in smart factories."],
                     "ko": ["큐비전은 카메라 영상을 AI로 이해하는 쿳션의 AI 비전 기술이에요. 공정물 표면을 분석하고 3D 움직임을 추적해서 "
                            "스마트 팩토리 품질 검사 같은 데 써요."]}),
    "co_pionoid": (["pionoid", "pionoid platform"], ["피오노이드", "파이오노이드"],
                   {"en": ["Pionoid is Cutshion's robot development platform: one robot API for robots of any maker, so the same robot "
                           "app runs on different robots. It works like an app store, with Pionoid Factory and Pionoid Store."],
                    "ko": ["피오노이드는 쿳션의 로봇 개발 플랫폼이에요. 제조사와 상관없이 하나의 통합 로봇 API로 같은 로봇 앱을 여러 "
                           "로봇에서 돌릴 수 있고, 앱스토어처럼 앱을 공유해요."]}),
    "co_gomcook": (["gomcook", "gom cook"], ["곰쿡", "곰 쿡"],
                   {"en": ["GOMCOOK is Cutshion's cooking robot platform for personalised cooking. It connects to delivery and ordering "
                           "apps, covering order, payment, cooking and delivery, and won the RoboWorld Award 2023."],
                    "ko": ["곰쿡은 쿳션의 조리 로봇 플랫폼이에요. 배달·주문 앱과 연동해서 주문, 결제, 조리, 배달을 하나로 하고, "
                           "로보월드 어워드 2023을 받았어요."]}),
}
EN_ROBOT = ["what is the {r}", "what's the {r}", "tell me about the {r}", "what does the {r} do", "how does the {r} work",
            "explain the {r}", "what is cutshion's {r}", "tell me about cutshion's {r}", "{r}?", "what can the {r} do",
            "what's {r}", "what is {r}", "does cutshion make a {r}", "how fast is the {r}", "how heavy is the {r}", "how big is the {r}"]
KO_ROBOT = [s + e for s in ["{r} 뭐", "{r} 뭐 하는 거", "{r} 어떤 거", "쿳션 {r} 뭐", "{r}이 뭐", "{r}는 뭐"] for e in ["야", "예요", "니", "입니까", "고", "여", "죠"]] + \
           [s + e for s in ["{r} 설명해", "{r} 소개해", "{r} 알려"] for e in [" 줘", " 주세요", " 주실래요", " 주십시오"]] + \
           ["{r} 어떻게 작동해요", "{r} 어떻게 돼요", "{r} 뭐 해요", "{r} 뭐 해", "{r} 무게가 몇이에요", "{r} 얼마나 빨라요", "{r} 크기가 어떻게 돼요",
            "{r} 궁금해요", "{r} 뭐 할 수 있어", "{r} 어떻게 써요", "{r} 있어요"]

QUICK_KINDS = {}
for _k, (_en, _ko_, _a) in SPEC.items():
    QUICK_KINDS[_k] = ([w for f in _en for w in ([f] if "{c}" not in f else [f.format(c=c) for c in EN_CO])] + _ko_, _a)
for _k, (_en, _ko_, _a) in ROBOTS.items():
    QUICK_KINDS[_k] = ([f.format(r=r) for f in EN_ROBOT for r in _en] + [f.format(r=r) for f in KO_ROBOT for r in _ko_], _a)

QUICK = {
    "no": [
        # the company's robots asked to act, or the visitor's own: not a fact of the notes
        "make me a coffee", "커피 한 잔 만들어 줘", "draw me", "내 그림 그려 줘", "give me an ice cream", "아이스크림 줘", "can i have a candy",
        "사탕 하나 줘", "where can i get a coffee", "커피 어디서 마셔요", "where is the barista robot", "바리스타 로봇 어디 있어요",
        "where is the ice cream robot", "아이스크림 로봇 어디 있어요", "take me to the drawing robot", "드로잉 로봇한테 데려가 줘",
        "i like coffee", "커피 좋아해요", "is the coffee good", "커피 맛있어요", "my company makes robots too", "우리 회사도 로봇 만들어요",
        "i work at samsung", "저 삼성 다녀요", "what is a cushion", "쿠션 어디서 사요", "this cushion is soft", "쿠션 좋다",
        "what's jaka", "who is jaka", "자카가 뭐야", "jaka 로봇 뭐 있어", "what is samsung", "삼성은 뭐 하는 회사야", "what does google make",
        "who is the ceo of samsung", "삼성 대표가 누구야", "who is the ceo of openai", "where is google's office", "애플 본사 어디야",
        "how much is a coffee", "커피 얼마예요", "how much is the ice cream", "아이스크림 얼마예요", "얼마예요", "이거 얼마예요",
        "how much is this cup", "where can i buy a cushion", "price of bitcoin", "비트코인 가격 알려 줘", "삼성전자 주가 얼마야",
        "what time does the event start", "행사 몇 시에 끝나요", "who is the president", "대통령이 누구야",
    ],
}

for _en, _ko_, _a in ROBOTS.values():     # where it stands, or asked to work: the LLM / the rules
    QUICK["no"] += [f.format(r=r) for f in ["where is the {r}", "where's the {r}", "take me to the {r}", "is there a {r} here",
                                           "i want to see the {r}", "show me the {r}"] for r in _en]
    QUICK["no"] += [f.format(r=r) for f in ["{r} 어디 있어", "{r} 어디 있어요", "{r} 어디예요", "{r}한테 데려가 줘", "{r} 보여 줘", "{r} 여기 있어요"]
                    for r in _ko_]

# night 5: Konglish / 하게체 / non-native ways of asking the founding year and the office ("컴퍼니 오픈 언제예요?",
# "company made which year?", "회사 사무실 어딘가?"); in quick_answers.KINDS by the loop above's kinds
QUICK["co_founded"] = [
    "company made which year", "company founded which year", "company start when", "your company open when", "company since when",
    "which year company start", "when company made", "cutshion made which year", "cutshion start what year", "company birthday when",
    "company how many years", "company how old"] + _ko(
    ["컴퍼니 오픈 언제", "회사 오픈 언제", "쿳션 오픈 언제", "회사 설립 언제", "쿳션 설립 언제", "회사 창립 언제", "회사 창업 언제",
     "회사 생긴 게 언제", "회사 세운 게 언제", "쿳션 생긴 게 언제", "컴퍼니 설립 언제", "회사 몇 년도 설립"],
    ["예요", "야", "니", "입니까", "인가요", "인가", "고", "여", "임", "이에요", "일까요"]) + _ko(
    ["회사 몇 년 됐", "회사 생긴 지 몇 년 됐", "쿳션 생긴 지 얼마나 됐", "회사 차린 지 얼마나 됐"],
    ["어", "어요", "니", "습니까", "나요", "노", "어유", "는가"])
QUICK["co_hq"] = _ko(
    ["회사 사무실 어디", "회사 사무실 어딘", "쿳션 사무실 어디", "회사 위치 어디", "회사 주소 어디", "본사 어디",
     "회사는 어디", "쿳션 본사 어디", "컴퍼니 어디", "회사 오피스 어디"],
    ["야", "예요", "에요", "니", "입니까", "인가요", "인가", "고", "여", "임"]) + _ko(
    ["회사 어디 있", "쿳션 어디 있", "회사 사무실 어디 있"], ["어", "어요", "니", "나요", "습니까", "노", "는가", "으세요"]) + [
    "where is company", "company where", "company office where", "where your company", "company location please",
    "office where", "where is the office of cutshion", "where's your company's office", "company address"]
QUICK["no"] += [
    "오픈AI 대표 누구야", "오픈AI 대표 누군가", "오픈AI 대표 누구임", "오픈AI 대표 어떤 분이세요", "구글 대표 누구예요", "애플 CEO 누구야",
    "엔비디아 대표 누구야", "테슬라 대표 누구예요", "삼성 회장 누구야", "who's the boss of openai", "who runs google",
    "1달러에 원화로 얼마야", "1달러 원화로 얼만가", "환율 얼마예요", "달러 환율 알려 줘", "엔화 얼마야", "how much is a dollar in won",
    "what's the exchange rate", "배터리 얼만가", "배터리 얼마예요", "배터리 얼마야", "배터리 얼마 남았는가"]
