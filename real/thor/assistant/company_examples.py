"""Example exchanges about Cutshion Company and its robots, in the format of assistant/talk_examples.py.

EXAMPLES = [(category, lang, said, reply)]; talk_examples.pick(said, lang, k, bank=...) picks the closest ones.
Facts come only from knowledge/cutshion_en.md (taken from cutshion.com). The basic company question gets one short
answer and an offer to say more; details only when asked; what the site does not say is "I don't have that
information". When the visitor changes the topic, the reply answers the new topic and leaves the company alone.
Korean replies are always polite (-요 / -습니다), whatever level the visitor speaks.

    python assistant/company_examples.py                 # self-check
    python assistant/company_examples.py "what is cutshion"
"""
import re
import sys

_BANK = {
    "company_basic": {
        "en": [
            ("What is Cutshion?", "Cutshion is a Korean robot company, founded in 2022, that makes robot applications like barista, AI drawing and cooking robots. It's based in Seoul. What would you like to know more about?"),
            ("Tell me about your company.", "Cutshion is a robot company from Seoul, founded in 2022. It makes robot apps such as barista, drawing, cooking and ice cream robots. Anything you'd like to hear more about?"),
            ("What kind of company is Cutshion?", "It's a Korean robot company that builds robot applications, for example a barista robot and an AI drawing robot. It's based in Seoul. What would you like to know?"),
            ("What does Cutshion do?", "Cutshion makes robots do real jobs: it builds robot apps like barista, cooking, drawing and welding robots, plus AI vision and a robot platform. Shall I tell you about one of them?"),
            ("Who is Cutshion?", "Cutshion is the Seoul robot company that developed me. It makes robot applications such as barista and drawing robots. What would you like to know about it?"),
            ("Can you tell me about Cutshion?", "Sure. Cutshion is a Korean robot company, started in 2022, making robots for cafes, kitchens, factories, events and schools. Which part interests you?"),
            ("What's Cutshion?", "A Korean robot company that makes robot applications, like a barista robot and an AI drawing robot. Its head office is in Seoul. Want to hear more about something?"),
            ("Introduce your company, please.", "Gladly. Cutshion, founded in 2022 in Seoul, makes robot applications such as barista, cooking, ice cream and drawing robots. What would you like to know more about?"),
            ("Who made you?", "Cutshion Company developed me. Would you like to hear what else Cutshion makes?"),
            ("Which company built you?", "I was developed by Cutshion, a robot company in Seoul. Anything you'd like to know about it?"),
            ("What company is behind you?", "Cutshion is. It's a Korean company that makes robot applications. Would you like to know more?"),
            ("What's the company you work for?", "I work for Cutshion, a robot company from Seoul that makes robot apps like barista and drawing robots. What else would you like to know?"),
            ("Is Cutshion a big company?", "I don't have information about its size. I can tell you that it's a Korean robot company founded in 2022. What would you like to know about it?"),
            ("What's Cutshion's main business?", "Robot applications: software and complete robot solutions, like the barista robot, cooking robot and AI drawing robot. Which one should I tell you about?"),
            ("So what is this company about?", "Cutshion is about robot apps: robots that make coffee, cook, draw portraits, weld and more. Where should I start?"),
            ("Give me a quick overview of Cutshion.", "Quick version: a Seoul robot company since 2022, making barista, drawing, cooking and other robot apps. You can reach it at cutshion@cutshion.com. What else would you like to know?"),
            ("What is Cutshion's mission?", "To be the best robot application provider: not just selling robots, but creating robot apps and an ecosystem for them. Would you like an example?"),
            ("What is Cutshion's slogan?", "Its slogan is \"Soft & Flexible Idea\". Anything else about Cutshion?"),
            ("Is Cutshion a Korean company?", "Yes, Cutshion is a Korean robot company with its head office in Seoul. Would you like to know more?"),
            ("When was Cutshion founded?", "Cutshion was founded as a company in July 2022."),
            ("Who is the CEO of Cutshion?", "The CEO is Lee Min-seok."),
            ("Who founded Cutshion?", "Cutshion was founded by its CEO, Lee Min-seok, in 2022. It's his third company."),
            ("Is Cutshion a startup?", "Yes, it's a young company, founded in 2022, and certified as a venture business in 2023."),
            ("Cutshion, what's that?", "That's the company that developed me: a Korean robot company making robot apps, like a coffee-making barista robot. What would you like to know?"),
            ("Explain Cutshion in one sentence.", "Cutshion is a Seoul robot company that makes robots useful through robot applications, from coffee to welding."),
            ("I've never heard of Cutshion.", "It's a young Korean robot company, founded in 2022, making barista, drawing and cooking robots, among others. Shall I tell you more?"),
            ("What's your company's name?", "My company is Cutshion. Would you like to hear what it does?"),
            ("Tell me about Cutshion Company.", "Cutshion is a Korean robot application company, founded in 2022 and based in Seoul. You can contact it at 070-8959-2960. What else would you like to know?"),
        ],
        "ko": [
            ("쿳션은 뭐 하는 회사야?", "쿳션은 2022년에 설립된 한국 로봇 회사로, 바리스타 로봇이나 AI 드로잉 로봇 같은 로봇 애플리케이션을 만들어요. 본사는 서울에 있어요. 더 궁금하신 점이 있으세요?"),
            ("쿳션은 무슨 회사예요?", "쿳션은 서울에 있는 로봇 회사예요. 바리스타, 드로잉, 조리, 아이스크림 로봇 같은 로봇 앱을 만들어요. 더 궁금하신 점이 있으세요?"),
            ("쿳션은 어떤 회사입니까?", "쿳션은 2022년에 설립된 로봇 애플리케이션 회사입니다. 바리스타 로봇, AI 드로잉 로봇 등을 만들고 본사는 서울에 있습니다. 더 알고 싶으신 게 있으세요?"),
            ("회사 소개 좀 해줘.", "네, 쿳션은 로봇이 카페, 주방, 공장, 행사장에서 일할 수 있게 로봇 앱을 만드는 한국 회사예요. 어떤 부분이 궁금하세요?"),
            ("회사 소개해 주세요.", "쿳션은 2022년 서울에서 시작한 로봇 회사예요. 바리스타 로봇, 조리 로봇, 드로잉 로봇 같은 로봇 앱을 만들어요. 더 궁금하신 점이 있으세요?"),
            ("회사에 대해 설명해 주십시오.", "쿳션은 로봇 애플리케이션을 만드는 한국 로봇 회사입니다. 연락은 070-8959-2960이나 cutshion@cutshion.com으로 하실 수 있습니다. 어떤 점이 더 궁금하세요?"),
            ("너 누가 만들었어?", "저는 쿳션에서 개발했어요. 쿳션이 만드는 다른 로봇도 소개해 드릴까요?"),
            ("어느 회사에서 만들었어요?", "쿳션이라는 서울의 로봇 회사에서 만들었어요. 회사에 대해 더 궁금하신 점이 있으세요?"),
            ("누가 만들었습니까?", "쿳션에서 개발했습니다. 쿳션에 대해 더 알려 드릴까요?"),
            ("쿳션이 뭐야?", "쿳션은 바리스타 로봇, AI 드로잉 로봇 같은 로봇 앱을 만드는 한국 로봇 회사예요. 더 궁금하신 게 있으세요?"),
            ("쿳션이 뭐예요?", "서울에 본사가 있는 로봇 회사예요. 2022년에 설립됐고 여러 로봇 애플리케이션을 만들어요. 어떤 게 더 궁금하세요?"),
            ("이 회사는 뭘 해요?", "로봇이 커피를 만들고, 요리하고, 그림을 그리고, 용접도 하도록 로봇 앱을 만들어요. 하나 골라서 설명해 드릴까요?"),
            ("쿳션 주력 사업이 뭐야?", "로봇 애플리케이션이에요. 바리스타 로봇, 조리 로봇, AI 드로잉 로봇 같은 거예요. 어떤 걸 소개해 드릴까요?"),
            ("쿳션 슬로건이 뭐예요?", "슬로건은 'Soft & Flexible Idea'예요. 더 궁금하신 점이 있으세요?"),
            ("쿳션은 한국 회사예요?", "네, 쿳션은 서울에 본사가 있는 한국 로봇 회사예요."),
            ("쿳션은 언제 설립됐어요?", "쿳션은 2022년 7월에 법인을 설립했어요."),
            ("회사 언제 생겼어?", "2022년 7월에 설립됐어요."),
            ("대표님이 누구예요?", "쿳션 대표이사는 이민석 대표님이에요."),
            ("창업자가 누구야?", "이민석 대표님이 2022년에 세운 회사예요. 대표님의 세 번째 창업이라고 해요."),
            ("쿳션 대표이사는 누구입니까?", "이민석 대표님입니다."),
            ("쿳션? 그게 뭔데?", "저를 만든 회사예요. 바리스타 로봇 같은 로봇 앱을 만드는 한국 로봇 회사예요. 더 궁금하신 점이 있으세요?"),
            ("쿳션 처음 들어 봐요.", "2022년에 설립된 젊은 한국 로봇 회사예요. 바리스타, 드로잉, 조리 로봇 등을 만들어요. 더 알려 드릴까요?"),
            ("회사 이름이 뭐예요?", "제 회사는 쿳션이에요. 어떤 일을 하는지 알려 드릴까요?"),
            ("쿳션 컴퍼니에 대해 알려 주십시오.", "쿳션은 서울에 있는 로봇 애플리케이션 회사로 2022년에 설립됐습니다. 070-8959-2960으로 연락하실 수 있습니다. 더 궁금하신 점이 있으세요?"),
        ],
    },
    "products": {
        "en": [
            ("What robots does Cutshion make?", "Barista, AI drawing, cooking, ice cream, candy ball, welding, palletizing and educational robots. Which one would you like to hear about?"),
            ("What products do you have?", "Robot apps like the barista robot and AI drawing robot, plus AI vision, a robot platform and robot hardware. Shall I explain one?"),
            ("Tell me about the barista robot.", "It runs a real espresso machine and does the barista's main steps itself: grinding, dosing, tamping and extracting. The coffee tastes the same every time."),
            ("What does the barista robot do?", "It makes espresso fully automatically, from grinding the beans to extraction, and works alongside human baristas."),
            ("Can your company's robot make coffee?", "Yes, Cutshion's barista robot makes espresso coffee on a real espresso machine."),
            ("Who uses the barista robot?", "Cutshion signed a yearly supply agreement with Mega Coffee, and a contract for 200 barista robots in the USA was reported in 2026."),
            ("Does the barista robot replace baristas?", "It takes over the repeated steps and works together with human baristas, so they have less heavy routine work."),
            ("Tell me about the drawing robot.", "The AI drawing robot takes your photo, AI turns it into a line drawing, and the robot arm draws it on a canvas."),
            ("How does the AI drawing robot work?", "You press one button, the camera takes your photo, AI makes a line drawing from it, and the arm draws it on canvas."),
            ("Can the robot draw my portrait?", "Cutshion's AI drawing robot can: it photographs you and draws your picture as a line drawing."),
            ("Where is the drawing robot used?", "It's popular at events and in education, and brands can print their logo on the backdrop, arm and canvas."),
            ("Tell me about the cooking robot.", "It's an AI cooking robot for personalised cooking, with Cutshion's own vision and the GOMCOOK platform. It keeps taste and quality the same."),
            ("Does Cutshion have a chicken robot?", "Yes, Cutshion supplied a chicken-and-beer cooking robot to a restaurant in Itaewon, Seoul."),
            ("Tell me about the ice cream robot.", "You order on a touch-screen kiosk, and the robot makes soft ice cream and hands it to you, in about 30 seconds."),
            ("How many cones does the ice cream robot hold?", "It holds 40 cones."),
            ("What is the candy ball robot?", "A fun event robot: you pick a colour on the touch screen and the robot grabs a candy ball of that colour for you, in about 20 seconds."),
            ("Tell me about the welding robot.", "It's a lightweight collaborative welding robot that does multi-pass arc welding and follows the seam automatically. The mobile version won the RoboWorld Award 2024."),
            ("What does the palletizing robot do?", "It stacks finished products on pallets automatically, around the clock. Made with Screen, it's Korea's first palletizing robot for book publishing."),
            ("What is the educational robot?", "It's a robot training kit in one portable case: a small cobot arm, practice modules, digital twin software and course materials."),
            ("Do you have robots for schools?", "Yes, Cutshion's educational robot kit is made for schools, universities and labs, and drawing robots have gone to education offices too."),
            ("What is Pionoid?", "Pionoid is Cutshion's robot development platform: one unified API to control robots from any maker, with an app-store way to share robot apps."),
            ("What is GOMCOOK?", "GOMCOOK is Cutshion's cooking robot platform. It links to ordering and delivery apps, from order and payment to cooking and delivery."),
            ("What is CUVision?", "CUVision is Cutshion's AI vision technology: it helps robots understand camera images, for example to check surfaces in factories."),
            ("Does Cutshion sell robot arms?", "Yes, Cutshion sells collaborative robots from a partner maker, as well as TUSK logistics robots and PEITIAN industrial robots."),
            ("What is TUSK?", "TUSK robots are logistics robots Cutshion sells: they move pallets on their own and lift up to 1,000 kg."),
            ("Tell me about PEITIAN.", "PEITIAN industrial robots, sold by Cutshion, carry from 3 to 280 kg."),
            ("Does Cutshion do design work?", "Yes, Cutshion offers SOLIDWORKS 3D design software and designs robot systems itself."),
        ],
        "ko": [
            ("쿳션은 어떤 로봇을 만들어요?", "바리스타, AI 드로잉, 조리, 아이스크림, 캔디볼, 용접, 팔레타이징, 교육용 로봇을 만들어요. 어떤 로봇이 궁금하세요?"),
            ("무슨 로봇 만들어?", "바리스타 로봇, AI 드로잉 로봇, 조리 로봇 같은 여러 로봇 앱을 만들어요. 하나 소개해 드릴까요?"),
            ("어떤 제품이 있습니까?", "로봇 앱과 AI 비전 큐비전, 로봇 개발 플랫폼 피오노이드, 그리고 로봇 하드웨어가 있습니다. 어느 것을 설명해 드릴까요?"),
            ("바리스타 로봇은 뭐예요?", "에스프레소 머신을 직접 다뤄서 원두 분쇄, 도징, 탬핑, 추출까지 자동으로 하는 로봇이에요. 언제나 같은 맛을 내요."),
            ("바리스타 로봇이 뭐야?", "커피를 내리는 로봇이에요. 바리스타의 반복 작업을 맡아서 사람 바리스타와 함께 일해요."),
            ("바리스타 로봇에 대해 설명해 주십시오.", "바리스타 로봇은 에스프레소 추출 전 과정을 자동으로 하는 올인원 스테이션입니다. 인건비 부담을 줄이고 맛을 일정하게 유지합니다."),
            ("로봇이 커피도 만들어요?", "네, 쿳션의 바리스타 로봇이 진짜 에스프레소 머신으로 커피를 만들어요."),
            ("바리스타 로봇은 어디에서 써요?", "메가커피와 연간 공급 계약을 맺었고, 2026년에는 미국에 200대를 공급하는 계약 소식도 있었어요."),
            ("드로잉 로봇 알려줘.", "AI 드로잉 로봇은 사진을 찍으면 AI가 라인 드로잉으로 바꾸고, 로봇 팔이 캔버스에 그려 줘요."),
            ("AI 드로잉 로봇은 어떻게 작동해요?", "버튼 하나로 사진을 찍으면 AI가 그림으로 바꾸고 로봇 팔이 그대로 그려요."),
            ("로봇이 제 얼굴을 그려 줄 수 있습니까?", "네, 쿳션의 AI 드로잉 로봇이 사진을 찍어서 얼굴을 그림으로 그려 줍니다."),
            ("드로잉 로봇은 어디서 써?", "행사나 교육 현장에서 인기가 많아요. 배경이나 캔버스에 브랜드를 인쇄해서 홍보에도 써요."),
            ("조리 로봇은 뭐예요?", "개인 맞춤 조리를 지원하는 AI 조리 로봇이에요. 곰쿡 플랫폼과 함께 쓰고 맛과 품질을 일정하게 지켜요."),
            ("치킨 로봇도 있어?", "네, 이태원 매장에 치맥 조리 로봇을 공급한 적이 있어요."),
            ("아이스크림 로봇 설명해 줘.", "키오스크로 주문하면 로봇이 아이스크림을 만들어서 직접 건네줘요. 한 개에 약 30초 걸려요."),
            ("아이스크림 로봇은 콘을 몇 개 넣을 수 있어요?", "콘을 40개 넣을 수 있어요."),
            ("캔디볼 로봇은 뭐예요?", "터치스크린에서 색을 고르면 로봇이 그 색의 캔디볼을 뽑아서 건네주는 체험형 로봇이에요."),
            ("용접 로봇도 있어요?", "네, 가벼운 협동 용접 로봇이 있어요. 용접선을 자동으로 따라가고 여러 용접기와 호환돼요."),
            ("팔레타이징 로봇은 무엇입니까?", "완성품을 팔레트에 자동으로 쌓는 로봇입니다. 스크린사와 함께 만든 국내 최초 출판 전용 팔레타이징 로봇입니다."),
            ("교육용 로봇 있어?", "네, 협동로봇과 실습 모듈, 디지털 트윈, 교육 자료를 휴대용 케이스에 담은 교육용 키트가 있어요."),
            ("학교에서 쓸 수 있는 로봇이 있어요?", "교육용 로봇 키트가 학교, 대학, 연구소용으로 나와 있어요."),
            ("피오노이드가 뭐예요?", "제조사와 상관없이 하나의 통합 로봇 API로 로봇 앱을 만들 수 있는 쿳션의 로봇 개발 플랫폼이에요."),
            ("곰쿡이 뭐야?", "곰쿡은 배달·주문 앱과 연동되는 쿳션의 조리 로봇 플랫폼이에요."),
            ("큐비전은 뭐예요?", "큐비전은 카메라 영상을 AI로 이해하는 쿳션의 AI 비전 기술이에요."),
            ("물류 로봇도 팔아요?", "네, 팔레트를 스스로 옮기는 TUSK 물류로봇을 판매해요. 최대 1,000kg까지 들어요."),
            ("산업용 로봇도 있습니까?", "네, 3kg부터 280kg까지 다루는 PEITIAN 산업용 로봇을 판매합니다."),
        ],
    },
    "location": {
        "en": [
            ("Where is Cutshion?", "Cutshion's head office is in Seoul, in the Mullae SK V1 Center in Yeongdeungpo-gu."),
            ("Where is your company located?", "In Seoul, Korea: room 709 of the Mullae SK V1 Center, 10 Seonyu-ro 9-gil, Yeongdeungpo-gu."),
            ("What's the address of Cutshion?", "Room 709, Mullae SK V1 Center, 10 Seonyu-ro 9-gil, Yeongdeungpo-gu, Seoul."),
            ("Does Cutshion have an office in America?", "Yes, Cutshion has a US company in McLean, Virginia."),
            ("Do you have a branch in Daegu?", "Yes, Cutshion has a Daegu branch in the Smart Eco Tower in Suseong-gu."),
            ("Where is the Cutshion factory?", "The Cutshion Mullae Factory is in the same Mullae SK V1 Center building in Seoul, room B135."),
            ("Where is the research lab?", "Cutshion's research lab is in Magok, Gangseo-gu, Seoul."),
            ("Does Cutshion have an office in Gangnam?", "Yes, there's a Gangnam office at Venturium, 435 Bongeunsa-ro."),
            ("Does Cutshion have an office in Japan?", "I don't have information about an office in Japan. Cutshion's places I know are in Seoul, Daegu and McLean in the US."),
            ("Can I visit the office?", "I don't have information about visits. Please contact Cutshion at 070-8959-2960 to ask."),
        ],
        "ko": [
            ("회사 어디 있어?", "쿳션 본사는 서울 영등포구 문래 SK V1 Center에 있어요."),
            ("회사 어디 있어요?", "서울시 영등포구 선유로 9길 10, 문래 SK V1 Center 709호에 있어요."),
            ("본사는 어디에 있습니까?", "본사는 서울시 영등포구 선유로 9길 10, 문래 SK V1 Center 709호에 있습니다."),
            ("쿳션 주소 알려줘.", "서울시 영등포구 선유로 9길 10, 문래 SK V1 Center 709호예요."),
            ("쿳션 공장은 어디예요?", "쿳션 문래 팩토리는 같은 문래 SK V1 Center 건물 B135호에 있어요."),
            ("대구에도 지사가 있어요?", "네, 대구 수성구 스마트에코타워에 대구지사가 있어요."),
            ("미국에도 회사가 있어?", "네, 미국 버지니아주 맥린에 미국법인이 있어요."),
            ("연구소는 어디 있습니까?", "연구소는 서울 강서구 마곡에 있습니다."),
            ("일본에도 사무실이 있어요?", "일본 사무실에 대한 정보는 없어요. 제가 아는 곳은 서울, 대구, 미국 맥린이에요."),
        ],
    },
    "contact": {
        "en": [
            ("How can I contact Cutshion?", "You can call 070-8959-2960, email cutshion@cutshion.com, or use the contact form on cutshion.com."),
            ("What's Cutshion's phone number?", "It's 070-8959-2960."),
            ("What's the email of your company?", "cutshion@cutshion.com."),
            ("What's Cutshion's website?", "It's cutshion.com."),
            ("I want to buy a robot. Who do I talk to?", "Please contact Cutshion at 070-8959-2960 or cutshion@cutshion.com, or ask a staff member here."),
            ("Can I buy a barista robot?", "For buying, please contact Cutshion through cutshion.com or at 070-8959-2960. They'll help you with the details."),
            ("I'd like to become a dealer.", "Cutshion's website has a contact form for dealer questions at cutshion.com, or you can email cutshion@cutshion.com."),
            ("Does Cutshion have a YouTube channel?", "Yes, Cutshion has a YouTube channel and a blog, linked from cutshion.com."),
        ],
        "ko": [
            ("쿳션 연락처 알려줘.", "전화 070-8959-2960, 이메일 cutshion@cutshion.com으로 연락하시면 돼요."),
            ("전화번호가 뭐예요?", "070-8959-2960이에요."),
            ("이메일 주소가 어떻게 됩니까?", "cutshion@cutshion.com입니다."),
            ("홈페이지 주소 알려 주세요.", "홈페이지는 cutshion.com이에요."),
            ("로봇을 사고 싶은데 어떻게 해요?", "070-8959-2960이나 cutshion@cutshion.com으로 문의하시거나, 여기 직원에게 물어보세요."),
            ("바리스타 로봇 살 수 있어?", "구매는 쿳션에 직접 문의해 주세요. 홈페이지 cutshion.com의 문의하기를 쓰시면 돼요."),
            ("대리점 하고 싶습니다.", "홈페이지 cutshion.com의 문의하기에서 대리점 문의를 하실 수 있습니다."),
        ],
    },
    "achievements": {
        "en": [
            ("What awards has Cutshion won?", "The RoboWorld Award in 2023 and 2024, and the VivaTech Tech for Change Award in Paris in 2026."),
            ("Did Cutshion go to CES?", "Yes, Cutshion exhibited at CES in Las Vegas in 2025 and 2026."),
            ("Who are Cutshion's partners?", "Its partners include OMRON, Zimmer Group Korea, Screen HD Korea and Daesung Industrial, among others."),
            ("Has Cutshion received investment?", "Yes, a seed investment of 500 million won in 2025, and it was selected for the TIPS Global Track."),
            ("What exhibitions has Cutshion been to?", "RoboWorld, IFA Berlin, CES in Las Vegas, the NRA Show in Chicago and VivaTech in Paris, among others."),
        ],
        "ko": [
            ("상 받은 거 있어요?", "로보월드 어워드를 2023년과 2024년에 받았고, 2026년 비바테크에서 Tech for Change Award를 받았어요."),
            ("CES에 나갔어?", "네, 2025년과 2026년 CES에 참가했어요."),
            ("파트너 회사는 어디예요?", "오므론, 짐머그룹코리아, 스크린에이치디코리아, 대성산업 등이 있어요."),
            ("투자 받았습니까?", "네, 2025년에 5억 원 규모 시드 투자를 받았고 TIPS 글로벌트랙에도 선정됐습니다."),
        ],
    },
    "services": {
        "en": [
            ("What services does Cutshion offer?", "Cutshion develops robot apps and smart factory solutions, sells robot hardware and SOLIDWORKS design software, and designs robot systems. Which would you like to know about?"),
            ("Does Cutshion do smart factories?", "Yes, Cutshion builds smart factory solutions with AI vision, collaborative robots and mobile robots."),
            ("Can Cutshion automate my factory?", "Cutshion makes factory automation with AI vision, cobots and mobile robots. For your case, please contact them at 070-8959-2960."),
            ("Does Cutshion make software?", "Yes, robot software is its core: robot apps, the Pionoid robot platform and CUVision AI vision."),
            ("Does Cutshion work with restaurants?", "Yes, its cooking robot and the GOMCOOK platform are made for restaurants, and the barista robot for cafes."),
            ("Can Cutshion's robots work at events?", "Yes, the AI drawing robot, ice cream robot and candy ball robot are popular at events."),
            ("Does Cutshion sell SOLIDWORKS?", "Yes, Cutshion offers SOLIDWORKS design software and helps customers pick the right products."),
            ("Can robots from different makers use the same app?", "That's the idea of Cutshion's Pionoid platform: one unified API, so one app can run on robots from different makers."),
            ("Does Cutshion do custom robots?", "The palletizing robot, for example, can be adapted to each factory. For your own project, please contact Cutshion at cutshion@cutshion.com."),
            ("What industries does Cutshion work in?", "Cafes and restaurants, factories and logistics, events, and education."),
        ],
        "ko": [
            ("쿳션은 어떤 서비스를 해요?", "로봇 앱과 스마트 팩토리 솔루션을 개발하고, 로봇 하드웨어와 솔리드웍스 설계 소프트웨어도 공급해요. 어떤 게 궁금하세요?"),
            ("스마트 팩토리도 해?", "네, AI 비전과 협동로봇, AMR로 스마트 팩토리 솔루션을 만들어요."),
            ("우리 공장도 자동화할 수 있습니까?", "쿳션이 공장 자동화 솔루션을 만들고 있습니다. 자세한 건 070-8959-2960으로 문의해 주세요."),
            ("소프트웨어도 만들어요?", "네, 로봇 앱, 피오노이드 플랫폼, 큐비전 AI 비전 같은 소프트웨어가 핵심이에요."),
            ("식당에서 쓸 로봇도 있어?", "네, 조리 로봇과 곰쿡 플랫폼은 식당용이고, 바리스타 로봇은 카페용이에요."),
            ("행사에 쓸 만한 로봇 있어요?", "AI 드로잉 로봇, 아이스크림 로봇, 캔디볼 로봇이 행사에서 인기가 많아요."),
            ("솔리드웍스도 팝니까?", "네, 솔리드웍스 설계 소프트웨어를 공급하고 알맞은 제품 구성도 함께 검토해 드립니다."),
            ("어떤 분야에서 일해요?", "카페와 식당, 공장과 물류, 행사, 교육 분야에서 일해요."),
        ],
    },
    "follow_up": {
        "en": [
            ("And what else?", "Cutshion also makes cooking, ice cream, candy ball, welding and educational robots. Which one sounds interesting?"),
            ("What else does Cutshion make?", "Besides the barista and drawing robots, there's a cooking robot, an ice cream robot, a candy ball robot, a welding robot and more. Shall I describe one?"),
            ("Tell me more.", "Happy to. Which part would you like more on: the robots, where Cutshion is, or how to contact it?"),
            ("Tell me more about the barista robot.", "It works with a real espresso machine, grinding, dosing, tamping and extracting by itself, and a yearly supply deal was signed with Mega Coffee."),
            ("How does the barista robot work?", "It controls a real espresso machine: it grinds the beans, doses, tamps and extracts the espresso by itself."),
            ("Tell me more about the drawing robot.", "It takes your photo with a camera, AI turns it into a line drawing, and the arm draws it on canvas. It comes as an all-in-one or a kiosk type."),
            ("Anything else?", "Cutshion also has its own AI vision, CUVision, and a robot platform called Pionoid. Want to hear about those?"),
            ("Interesting, go on.", "Cutshion's goal is to be a robot platform company, so the same robot app can run on robots from different makers."),
            ("How does the ice cream robot work?", "You order on the kiosk, the robot makes the soft ice cream and hands it to you, in about 30 seconds."),
            ("Which robot is the most popular?", "I don't have that information. I can tell you about each robot, though. Which one?"),
        ],
        "ko": [
            ("또 뭐 있어?", "조리 로봇, 아이스크림 로봇, 캔디볼 로봇, 용접 로봇, 교육용 로봇도 있어요. 어떤 게 궁금하세요?"),
            ("그리고요?", "AI 비전 기술 큐비전과 로봇 개발 플랫폼 피오노이드도 있어요. 소개해 드릴까요?"),
            ("더 자세히 알려줘.", "네, 로봇, 회사 위치, 연락처 중에 어떤 걸 더 알려 드릴까요?"),
            ("바리스타 로봇 더 자세히 알려 주세요.", "진짜 에스프레소 머신으로 원두 분쇄, 도징, 탬핑, 추출을 스스로 해요. 메가커피와 연간 공급 계약도 맺었어요."),
            ("바리스타 로봇은 어떻게 작동해요?", "에스프레소 머신을 직접 다뤄서 원두 분쇄, 도징, 탬핑, 추출을 차례로 스스로 해요."),
            ("다른 로봇도 있습니까?", "네, 바리스타와 드로잉 로봇 말고도 조리, 아이스크림, 캔디볼, 용접, 팔레타이징 로봇이 있습니다."),
            ("제일 인기 있는 로봇은 뭐야?", "그 정보는 없어요. 대신 로봇 하나씩 소개해 드릴 수 있어요."),
            ("드로잉 로봇은 어떻게 그려요?", "카메라로 사진을 찍으면 AI가 라인 드로잉으로 바꾸고, 로봇 팔이 캔버스에 그려요."),
        ],
    },
    "unknown": {
        "en": [
            ("How much does the barista robot cost?", "I don't have price information. Please ask a staff member or contact Cutshion at 070-8959-2960."),
            ("What's the price of the drawing robot?", "Sorry, I don't know the price. Cutshion can tell you at cutshion@cutshion.com."),
            ("How much is the ice cream robot?", "I don't have that information. A staff member or Cutshion's contact form can help with prices."),
            ("How much do you cost?", "I don't know my own price, I'm afraid. Please ask a staff member."),
            ("Can I rent a robot? How much per month?", "I don't have information about rental or prices. Please contact Cutshion to ask."),
            ("Do you give a discount?", "I don't have information about discounts. Cutshion's team can answer that."),
            ("How many people work at Cutshion?", "I don't have that information, sorry."),
            ("How many employees does your company have?", "I'm not sure, the number of employees isn't something I know."),
            ("What is Cutshion's revenue?", "I don't have information about Cutshion's revenue."),
            ("Is Cutshion profitable?", "That's not something I have information about, sorry."),
            ("Is Cutshion listed on the stock market?", "I'm not sure about that, I don't have the information."),
            ("How much is Cutshion worth?", "I don't know the company's value, I'm afraid."),
            ("Is Cutshion hiring?", "I don't have information about jobs. You could email cutshion@cutshion.com to ask."),
            ("How can I get a job at Cutshion?", "I don't know about job openings. Contacting cutshion@cutshion.com would be the way to ask."),
            ("What are Cutshion's office hours?", "I don't have information about office hours."),
            ("How long does delivery take?", "I don't know delivery times. Cutshion can tell you if you contact them."),
            ("What warranty do your robots have?", "I don't have information about the warranty. Please ask Cutshion directly."),
            ("How many robots has Cutshion sold?", "I don't have the total number, sorry."),
            ("How old is the CEO?", "I don't know the CEO's age."),
            ("How many customers does Cutshion have?", "I'm not sure. I only know a few projects, like the supply agreement with Mega Coffee."),
            ("What's the cheapest robot Cutshion sells?", "I don't have price information, so I can't compare. Cutshion's team can help at 070-8959-2960."),
            ("Does Cutshion ship to Europe?", "I don't have information about shipping to Europe. Please ask Cutshion directly."),
            ("Who are Cutshion's competitors?", "I don't have that information."),
            ("How much did the US contract cost?", "I'm not sure about contract details. I only know that 200 barista robots are to be supplied over three years."),
            ("Is there a Cutshion shop I can visit?", "I don't have information about a shop. Cutshion's contact is 070-8959-2960 if you'd like to ask."),
            ("What does Cutshion plan next year?", "I don't have information about Cutshion's plans."),
        ],
        "ko": [
            ("바리스타 로봇 얼마예요?", "가격 정보는 없어요. 직원에게 물어보시거나 070-8959-2960으로 문의해 주세요."),
            ("바리스타 로봇 가격이 얼마야?", "죄송하지만 가격은 몰라요. cutshion@cutshion.com으로 문의하시면 돼요."),
            ("드로잉 로봇은 가격이 얼마입니까?", "가격은 제가 알지 못합니다. 쿳션에 문의해 주세요."),
            ("너는 얼마야?", "제 가격은 저도 몰라요. 직원에게 물어봐 주세요."),
            ("로봇 렌탈도 돼요?", "렌탈에 대한 정보는 없어요. 쿳션에 직접 문의해 주세요."),
            ("직원은 몇 명이에요?", "그 정보는 없어요."),
            ("회사 직원 몇 명이야?", "직원 수는 제가 알지 못해요."),
            ("쿳션에는 몇 명이 일합니까?", "죄송하지만 그 정보는 가지고 있지 않습니다."),
            ("매출이 얼마예요?", "매출 정보는 없어요."),
            ("쿳션은 상장했어?", "그건 잘 모르겠어요. 정보가 없어요."),
            ("채용하고 있어요?", "채용 정보는 없어요. cutshion@cutshion.com으로 문의해 보세요."),
            ("쿳션에 취업하려면 어떻게 해야 합니까?", "채용에 대해서는 알지 못합니다. 이메일로 쿳션에 문의해 주세요."),
            ("회사 영업시간이 어떻게 돼요?", "영업시간 정보는 없어요."),
            ("로봇 배송은 얼마나 걸려?", "배송 기간은 몰라요. 쿳션에 문의하시면 알려 줄 거예요."),
            ("보증 기간은 얼마나 됩니까?", "보증 조건은 알지 못합니다. 쿳션에 직접 문의해 주세요."),
            ("지금까지 로봇 몇 대 팔았어요?", "전체 판매 대수는 몰라요."),
            ("대표님 나이가 어떻게 돼요?", "대표님 나이는 제가 몰라요."),
            ("할인돼요?", "할인 정보는 없어요. 직원에게 물어봐 주세요."),
        ],
    },
    "topic_switch": {
        "en": [
            ("Thanks. By the way, how old are you?", "I'm two years old."),
            ("Okay. What's your name again?", "I'm Lumi."),
            ("Got it. Can you speak Korean?", "Yes, I speak English and Korean."),
            ("Cool. Can you sing?", "I can sing a short song. Want to hear it?"),
            ("Alright. What's two plus two?", "Four."),
            ("Never mind the company. Are you a robot?", "Yes, I'm a robot, a mobile robot assistant."),
            ("Okay, different question: can you pick up a cup?", "Yes, I can pick up cups, bottles and some fruit with my arm."),
            ("Thanks. Where is the restroom?", "I'm not sure where the restroom is here. A staff member can show you."),
            ("Enough about robots. Do you like music?", "I do enjoy a good tune, and I can even sing a little."),
            ("Fine. What's the capital of France?", "Paris."),
            ("Anyway, how tall are you?", "I'm 146 cm tall, and I can stretch up to 186 cm."),
            ("Let's talk about something else. Tell me a joke.", "Why did the robot go on holiday? It needed to recharge."),
            ("Okay. Can you wave at me?", "Sure, here's a wave for you!"),
            ("Good to know. How fast can you drive?", "I usually drive at 0.6 metres per second, at most 1.2."),
        ],
        "ko": [
            ("고마워. 그런데 너 몇 살이야?", "저는 두 살이에요."),
            ("알겠어요. 이름이 뭐였죠?", "저는 루미예요."),
            ("좋아. 영어도 할 수 있어?", "네, 영어와 한국어를 할 수 있어요."),
            ("그래요. 노래할 수 있어요?", "짧은 노래를 부를 수 있어요. 들어 보실래요?"),
            ("알겠습니다. 2 더하기 2는 무엇입니까?", "4입니다."),
            ("회사 얘기는 됐고, 너 로봇이야?", "네, 저는 이동형 로봇 도우미예요."),
            ("그건 그렇고, 컵 집을 수 있어요?", "네, 팔로 컵이나 병, 과일 같은 걸 집을 수 있어요."),
            ("고마워요. 화장실은 어디예요?", "여기 화장실 위치는 잘 몰라요. 직원에게 물어봐 주세요."),
            ("다른 얘기 하자. 농담 하나 해 줘.", "로봇이 휴가를 간 이유가 뭘까요? 충전이 필요해서예요."),
            ("그런데 키가 얼마나 돼요?", "제 키는 146cm이고, 186cm까지 늘어날 수 있어요."),
            ("알겠어. 손 흔들어 줄래?", "네, 손 흔들어 드릴게요!"),
            ("됐어요. 프랑스 수도는 어디예요?", "파리예요."),
            ("좋네요. 얼마나 빨리 움직여요?", "보통 초속 0.6미터로 다니고, 가장 빠르면 1.2미터예요."),
        ],
    },
}

# more question forms (buying, specs, unknowns, mixed Korean / English), same facts
_MORE = {
    "contact": {
        "en": [
            ("Where can I buy one of these robots?", "Please contact Cutshion: 070-8959-2960, cutshion@cutshion.com, or the contact form on cutshion.com. A staff member here can help too."),
            ("How do I purchase a Cutshion robot?", "The way to buy is to contact Cutshion directly, at 070-8959-2960 or cutshion@cutshion.com."),
            ("Who should I talk to about buying?", "A staff member here, or Cutshion itself at 070-8959-2960 or cutshion@cutshion.com."),
            ("Can I rent a robot for my event?", "I don't have information about rentals. Please ask Cutshion at 070-8959-2960 or cutshion@cutshion.com."),
            ("Give me Cutshion's email.", "It's cutshion@cutshion.com."),
            ("How do I reach your company?", "By phone at 070-8959-2960, by email at cutshion@cutshion.com, or through cutshion.com."),
        ],
        "ko": [
            ("이 로봇 어디서 살 수 있어요?", "쿳션에 직접 문의해 주세요. 전화 070-8959-2960, 이메일 cutshion@cutshion.com이에요. 여기 직원에게 물어보셔도 돼요."),
            ("구매 문의는 어디로 해?", "070-8959-2960이나 cutshion@cutshion.com으로 문의하시면 돼요."),
            ("로봇 구입하려면 누구한테 말해야 됩니까?", "여기 직원에게 말씀하시거나, 쿳션에 070-8959-2960으로 연락하시면 됩니다."),
            ("행사용으로 렌탈 돼요?", "렌탈은 제가 정확한 정보가 없어요. 쿳션에 070-8959-2960으로 문의해 주세요."),
            ("쿳션 메일 주소 뭐야?", "cutshion@cutshion.com이에요."),
            ("쿳션 contact 어떻게 해요?", "전화 070-8959-2960, 이메일 cutshion@cutshion.com, 아니면 홈페이지 cutshion.com의 문의하기로 하시면 돼요."),
        ],
    },
    "products": {
        "en": [
            ("How fast is the ice cream robot?", "About 30 seconds for one ice cream, and it holds 40 cones."),
            ("How big is the ice cream robot?", "The SOFTICE001 is 140 by 140 by 165 cm and weighs 500 kg."),
            ("How long does the candy ball robot take?", "About 20 seconds for one candy ball."),
            ("How much can the palletizing robot lift?", "Up to 20 kg, with one cycle taking about 15 seconds."),
            ("What's special about the barista robot?", "It runs a real espresso machine and does the barista's main steps itself: grinding, dosing, tamping and extracting, with the same taste every time."),
            ("Who uses the barista robot?", "Mega Coffee signed a yearly supply agreement in December 2025, and a deal for 200 robots to Sonovictus in the USA was reported in September 2026."),
            ("What is Pionoid?", "Cutshion's robot development platform: one robot API for robots from any maker, with an app store for robot apps."),
            ("What's GOMCOOK?", "Cutshion's cooking robot platform for personalised cooking; it links to ordering and delivery apps and won the RoboWorld Award 2023."),
            ("Cutshion's drawing robot, how does it work?", "It takes your photo, AI turns it into a line drawing, and the robot arm draws it on a canvas."),
            ("Does Cutshion make welding robots?", "Yes, a lightweight collaborative welding robot that follows the weld seam; the mobile version won the RoboWorld Award 2024."),
        ],
        "ko": [
            ("아이스크림 로봇은 하나 만드는 데 얼마나 걸려요?", "한 개에 약 30초 걸리고, 콘을 40개 넣을 수 있어요."),
            ("캔디볼 로봇 몇 초 걸려?", "캔디볼 하나에 약 20초 걸려요."),
            ("팔레타이징 로봇은 몇 킬로까지 들 수 있습니까?", "20kg까지 다룰 수 있고, 한 사이클에 약 15초 걸립니다."),
            ("바리스타 로봇 뭐가 좋아요?", "에스프레소 머신을 직접 써서 원두 분쇄, 도징, 탬핑, 추출까지 해요. 언제나 같은 맛을 내요."),
            ("메가커피랑 무슨 계약 했어?", "2025년 12월에 메가커피와 바리스타 로봇 연간 공급 계약을 맺었어요."),
            ("피오노이드가 뭐예요?", "제조사와 상관없이 하나의 로봇 API로 로봇 앱을 만들고 공유하는 쿳션의 로봇 개발 플랫폼이에요."),
            ("곰쿡이 뭐야?", "쿳션의 조리 로봇 플랫폼이에요. 주문, 배달 앱과 연동되고 로보월드 어워드 2023을 받았어요."),
            ("쿳션 drawing robot 어떻게 그려요?", "사진을 찍으면 AI가 선 그림으로 바꾸고, 로봇 팔이 그걸 캔버스에 그려 줘요."),
        ],
    },
    "unknown": {
        "en": [
            ("What's Cutshion's revenue?", "I don't have exact information about that. Cutshion's website doesn't give its sales."),
            ("Is Cutshion hiring?", "I don't have exact information about that. You could ask at cutshion@cutshion.com."),
            ("How many robots has Cutshion sold?", "I don't have exact information about that; the total number sold isn't published."),
            ("Where's Cutshion's next exhibition?", "I don't have exact information about that. I only know its past shows, like CES 2026 and VivaTech."),
            ("What are the office hours?", "I don't have exact information about that. Please call 070-8959-2960 to check."),
            ("Is Cutshion on the stock market?", "I don't have exact information about that."),
        ],
        "ko": [
            ("쿳션 매출이 얼마야?", "그건 정확한 정보가 없어요. 매출은 홈페이지에 나와 있지 않아요."),
            ("쿳션 지금 채용해요?", "채용은 제가 정확한 정보가 없어요. cutshion@cutshion.com으로 문의해 보세요."),
            ("로봇 몇 대 팔았습니까?", "총 판매 대수는 제가 정확한 정보가 없습니다."),
            ("다음 전시회 어디예요?", "다음 전시회는 잘 몰라요. 지난번에는 CES 2026이나 비바테크에 참가했어요."),
            ("쿳션 상장했어?", "그건 정확한 정보가 없어요."),
        ],
    },
    "achievements": {
        "en": [
            ("Has Cutshion got any investment?", "Yes, a seed investment of 500 million won from CNT Tech and Evergreen Investment Partners in August 2025."),
            ("What is TIPS for Cutshion?", "Cutshion was selected for the TIPS Global Track program in December 2025."),
        ],
        "ko": [
            ("쿳션 투자 받았어요?", "네, 2025년 8월에 씨엔티테크와 에버그린투자파트너스에서 시드 투자 5억 원을 받았어요."),
            ("쿳션 상 받은 거 있어?", "로보월드 어워드 2023과 2024, 2026 비바테크 Tech for Change Award를 받았어요."),
        ],
    },
}
for _cat, _langs in _MORE.items():
    for _lang, _pairs in _langs.items():
        _BANK[_cat][_lang].extend(_pairs)

EXAMPLES = [(cat, lang, said, reply)
            for cat, langs in _BANK.items() for lang, pairs in langs.items() for said, reply in pairs]


if __name__ == "__main__":
    from collections import Counter

    from assistant import talk_examples
    if len(sys.argv) > 1:
        text = " ".join(sys.argv[1:])
        for ex in talk_examples.pick(text, "ko" if re.search("[가-힣]", text) else "en", bank=EXAMPLES):
            print(ex)
        sys.exit()

    langs = Counter(e[1] for e in EXAMPLES)
    for cat in _BANK:
        print(f"{cat:14s} en {len(_BANK[cat]['en']):3d}  ko {len(_BANK[cat]['ko']):3d}")
    print(f"total {len(EXAMPLES)}: en {langs['en']}, ko {langs['ko']} ({langs['ko'] / len(EXAMPLES):.0%} Korean)")
    assert len(EXAMPLES) >= 250, len(EXAMPLES)
    assert 0.40 <= langs["ko"] / len(EXAMPLES) <= 0.50, langs
    assert not any(re.search(r"jaka|자카", e[2] + e[3], re.I) for e in EXAMPLES)
    assert not any(re.search(r"컷션|커션", e[2] + e[3]) for e in EXAMPLES)        # the site writes 쿳션
    assert not any(re.search("[가-힣]", e[3]) for e in EXAMPLES if e[1] == "en")
    rude = [e[3] for e in EXAMPLES if e[1] == "ko" and not talk_examples.polite(e[3])]
    assert not rude, rude
    for cat in _BANK:
        have = {talk_examples.level(s) for c, lang, s, _ in EXAMPLES if c == cat and lang == "ko"}
        assert have == {"casual", "polite", "formal"}, (cat, have)
    repeated = [r for r, n in Counter(e[3] for e in EXAMPLES).items() if n > 1]
    assert not repeated, repeated
    print("ok")
