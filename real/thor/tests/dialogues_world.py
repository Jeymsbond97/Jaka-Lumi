"""Long talks (10-18 turns) on world topics with nested follow-ups on Lumi's own last answer ("why?", "when?", "and
then?", "really?", "what do you mean?", "왜?", "진짜?", "그게 무슨 말이야?", "그럼 그건?"), thanks / okay in the middle
that do not end the talk, and a real ending. English, Korean (반말 / 해요체 / 하십시오체, dialect) and mixed; Korean
replies must be polite. Format of tests/dialogues.py. Run (no file of the checkers changed):

    .venv/bin/python tests/dialogues_world.py [only]   # through tests/followup_check.main -> logs/a4/world_check.*

Written by A4 (night 2) as its own cases, not a blind set: facts in "must" are settled general knowledge.
"""
import sys

from tests.dialogues import T, D, YES, KO

NOT_HEARD = r"didn't catch|did not catch|say (it|that) again|could you repeat|what do you mean\?|무슨 말씀이신지|다시 (한 ?번 )?말씀"
OFFER = r"how can I help|무엇을 도와 ?드릴까|anything else I can"
RUDE = r"(?<![가-힣])(?:했어|있어|없어|거야|이야|맞아|그래|몰라|알았어)[.!?]?$"     # 반말 endings in a reply
FU = "answers the follow-up about its own last answer, same topic, no 'say it again', no topic change"
N = [NOT_HEARD, OFFER]
NK = [NOT_HEARD, OFFER, RUDE]

DIALOGUES_WORLD = [
    D("student", "world_space", "en",
      T("Why is the sky blue?", must=[r"scatter|blue|light|wavelength"], no=N, check="explains light scattering"),
      T("Why does blue scatter more?", must=[r"short|wavelength|wave|small"], no=N, check="shorter wavelengths scatter more; " + FU),
      T("Then why are sunsets red?", must=[r"red|longer|more air|farther|through"], no=N, check="light travels through more air at sunset; " + FU),
      T("Oh I see.", no=N, check="a short acknowledgement, the talk goes on"),
      T("How far is the Moon?", must=[r"384|380|thousand"], no=N, check="about 384,000 km"),
      T("Really?", must=[r"384|380|yes"], no=N, check="confirms the same distance"),
      T("Does it change?", must=[r"orbit|oval|elliptic|varies|363|405|yes"], no=N, check="the orbit is an ellipse, the distance varies; " + FU),
      T("Why?", must=[r"orbit|oval|ellip|circle"], no=N, check="the orbit is not a perfect circle; " + FU),
      T("Thanks. And what's the biggest planet?", must=[r"Jupiter"], no=N, check="Jupiter; the thanks does not end the talk"),
      T("How big?", must=[r"eleven|11|thousand|1,?300|times"], no=N, check="about 11 times Earth's width; " + FU),
      T("What do you mean?", must=[r"wide|diameter|across|Earth|times|fit"], no=N, check="explains the comparison with Earth; " + FU),
      T("Cool, thanks, that's all!", "end")),
    D("office worker", "world_history_ko", "ko",
      T("세종대왕이 누구예요?", must=[r"조선|왕|한글"], no=NK, check="조선의 왕, 한글을 만든 분"),
      T("왜 한글을 만들었어?", must=[r"백성|어려|한자|쉽"], no=NK, check="한자가 어려워 백성이 쉽게 쓰도록; " + FU),
      T("진짜?", must=[r"네|맞|정말|백성|한자"], no=NK, check="같은 이유를 다시 확인"),
      T("언제?", must=[r"1443|1446|15세기|1400"], no=NK, check="1443년에 만들고 1446년에 반포; " + FU),
      T("그게 무슨 말이야?", must=[r"만들|반포|알리|발표|공포|3년"], no=NK, check="만든 해와 널리 알린 해의 차이를 설명; " + FU),
      T("아 그렇구나.", no=NK, check="짧게 받고 대화가 이어짐"),
      T("그럼 그 다음 왕은?", must=[r"문종"], no=NK, check="문종; " + FU),
      T("고마워요. 근데 한국전쟁은 언제였어요?", must=[r"1950|1953"], no=NK, check="1950–1953; 고마워요가 대화를 끝내지 않음"),
      T("끝난 거야?", must=[r"정전|휴전|평화|조약|공식"], no=NK, check="정전(휴전)으로 멈췄고 평화협정은 없음; " + FU),
      T("그게 무슨 뜻이에요?", must=[r"멈췄|멈춘|끝나지|조약|협정|공식"], no=NK, check="싸움은 멈췄지만 전쟁을 공식적으로 끝내는 조약은 없다는 뜻; " + FU),
      T("알겠습니다. 감사합니다, 이만 가 보겠습니다.", "end")),
    D("traveller", "world_places_mixed", "en",
      T("What's the capital of Australia?", must=[r"Canberra"], no=N, check="Canberra"),
      T("Not Sydney?", must=[r"Sydney|Canberra|no|compromise|Melbourne"], no=N, check="no, Sydney is the biggest city; Canberra was chosen as a compromise; " + FU),
      T("Why?", must=[r"Sydney|Melbourne|compromise|rival|between"], no=N, check="compromise between Sydney and Melbourne; " + FU),
      T("When did that happen?", must=[r"19\d\d|1908|1913|1927|early 20"], no=N, check="early 20th century (chosen 1908, parliament 1927); " + FU),
      T("And the capital of Japan?", must=[r"Tokyo|도쿄"], no=N, check="Tokyo"),
      T("언제부터요?", must=[r"1868|메이지|19세기|교토"], no=NK, rl="ko", check="1868년부터, 그 전엔 교토; " + FU),
      T("그 전에는?", must=[r"교토|Kyoto"], no=NK, rl="ko", check="교토; " + FU),
      T("Okay.", no=N, check="a short acknowledgement; no goodbye"),
      T("How high is Mount Everest?", must=[r"8,?8[48]\d|8848|8849"], no=N, check="8,849 m"),
      T("Is it still growing?", must=[r"yes|millimet|mm|India|plate|grow"], no=N, check="yes, a few mm a year, plates pushing; " + FU),
      T("How come?", must=[r"India|plate|push|collid|tecton"], no=N, check="the Indian plate pushes into Asia; " + FU),
      T("Thanks a lot, bye!", "end")),
    D("parent", "world_animals_ko_casual", "ko",
      T("고양이는 왜 그르렁거려?", must=[r"기분|편안|진정|좋을|아플"], no=NK, check="기분이 좋을 때, 또는 스스로 진정하려고"),
      T("아플 때도?", must=[r"네|진정|회복|아플|편하"], no=NK, check="네, 아프거나 무서울 때도 진정하려고; " + FU),
      T("왜?", must=[r"진정|회복|편|안정|진동|통증"], no=NK, check="스스로 안정하고 회복을 도울 수 있어서; " + FU),
      T("헐 대박", no=NK, check="짧고 자연스러운 반응"),
      T("치타는 얼마나 빨라?", must=[r"100|110|120|시속"], no=NK, check="시속 100km 넘게"),
      T("얼마나 오래?", must=[r"짧|몇백|수백|초|미터|잠깐"], no=NK, check="짧게만, 몇백 미터; " + FU),
      T("그럼 그 다음엔?", must=[r"쉬|숨|지쳐|휴식|체온|열"], no=NK, check="달린 뒤엔 쉬어야 함; " + FU),
      T("진짜?", must=[r"네|맞|정말|쉬|열|체온"], no=NK, check="같은 점을 다시 확인"),
      T("고마워", no=NK, check="짧게 천만에요; 대화를 끝내라는 말 아님"),
      T("판다는 뭐 먹어?", must=[r"대나무"], no=NK, check="대나무"),
      T("그것만?", must=[r"거의|대부분|대나무|가끔|조금"], no=NK, check="거의 대나무만; " + FU),
      T("알겠어, 이제 됐어. 잘 있어!", "end")),
    D("engineer", "world_tech", "en",
      T("What is a black hole?", must=[r"gravity|light|escape"], no=N, check="gravity so strong light can't escape"),
      T("Then how do we see them?", must=[r"gas|stars?|orbit|around|picture|image|shadow|2019"], no=N, check="by gas and stars around them, the 2019 picture; " + FU),
      T("When was that picture?", must=[r"2019"], no=N, check="2019; " + FU),
      T("Who took it?", must=[r"Event Horizon|telescope|EHT|astronomers"], no=N, check="the Event Horizon Telescope team; " + FU),
      T("fr?", must=[r"yes|really|2019|Event Horizon|telescope"], no=N, check="confirms the same fact"),
      T("Nice. What's the speed of light?", must=[r"300|299|thousand"], no=N, check="about 300,000 km/s"),
      T("Can anything go faster?", must=[r"no|nothing|not"], no=N, check="no, nothing with mass; " + FU),
      T("Why not?", must=[r"mass|energy|infinite|relativity|Einstein"], no=N, check="it would take infinite energy / relativity; " + FU),
      T("Says who?", must=[r"Einstein|relativity|experiment|physic"], no=N, check="Einstein's relativity, tested by experiments; " + FU),
      T("Okay, got it, thanks. One more: what is AI?", must=[r"learn|data|software|computer|intelligen"], no=N, check="what AI is; the thanks does not end the talk"),
      T("Like you?", must=[r"yes|I |my "], no=N, check="yes, it uses AI itself; " + FU),
      T("That's everything, thanks.", "end")),
    D("grandfather", "world_food_formal", "ko",
      T("김치는 왜 발효시킵니까?", must=[r"보관|겨울|오래|맛|유산균"], no=NK, check="겨울 동안 오래 보관하고 맛이 생겨서"),
      T("얼마나 오래 갑니까?", must=[r"몇 ?달|개월|오래|냉장"], no=NK, check="냉장고에서 몇 달; " + FU),
      T("그럼 그건 어떻게 됩니까?", must=[r"시|신맛|찌개|익"], no=NK, check="오래되면 시어지고 찌개에 좋음; " + FU),
      T("그렇군요.", no=NK, check="짧게 받음"),
      T("커피는 몸에 나쁩니까?", must=[r"적당|네 ?잔|4 ?잔|괜찮"], no=NK, check="적당히는 괜찮음, 하루 네 잔쯤"),
      T("왜 네 잔입니까?", must=[r"카페인|400"], no=NK, check="카페인 400mg 한도; " + FU),
      T("확실합니까?", must=[r"네|400|카페인|보건|권장"], no=NK, check="같은 근거로 확인"),
      T("감사합니다. 그런데 하루에 물은 얼마나 마셔야 합니까?", must=[r"1\.5|2 ?리터|두 ?리터|리터"], no=NK, check="1.5–2리터; 감사합니다가 대화를 끝내지 않음"),
      T("커피도 칩니까?", must=[r"네|대부분|수분|포함|쳐"], no=NK, check="대부분 수분으로 침; " + FU),
      T("잘 알겠습니다. 수고하세요.", "end")),
    D("teenager", "world_sports_slang", "en",
      T("how long is a marathon", must=[r"42"], no=N, check="42.195 km"),
      T("why such a weird number", must=[r"1908|London|Windsor|royal|Olympic"], no=N, check="the 1908 London course; " + FU),
      T("no way", must=[r"yes|really|true|1908|London"], no=N, check="confirms the same fact"),
      T("who has won the most world cups", must=[r"Brazil"], no=N, check="Brazil"),
      T("how many", must=[r"five|5"], no=N, check="five; " + FU),
      T("when was the last one", must=[r"2002"], no=N, check="2002; " + FU),
      T("against who", must=[r"Germany"], no=N, check="Germany; " + FU),
      T("lol ok", no=N, check="a short natural reply; no goodbye"),
      T("is taekwondo in the olympics", must=[r"yes|2000|Sydney"], no=N, check="yes, since 2000"),
      T("and before that?", must=[r"demonstrat|1988|1992|Seoul"], no=N, check="demonstration sport 1988 and 1992; " + FU),
      T("ok cool, gotta run, bye", "end")),
    D("student", "world_science_ko_mixed", "ko",
      T("바다는 왜 짜요?", must=[r"강|소금|광물|증발|바위"], no=NK, check="강이 소금기를 실어 오고 물만 증발"),
      T("그럼 강은 왜 안 짜?", must=[r"흘러|바뀌|쌓이|조금|흐르"], no=NK, check="강물은 계속 흘러 소금이 쌓이지 않음; " + FU),
      T("why 그래요?", must=[r"흘러|바다|쌓|증발|빠져|흐르"], no=NK, rl="ko", check="같은 이유를 이어서 설명; " + FU),
      T("오 신기하네요", no=NK, check="짧은 반응"),
      T("사람 뼈는 몇 개예요?", must=[r"206"], no=NK, check="206개"),
      T("아기는?", must=[r"300|270|더 많|많아"], no=NK, check="300개 가까이; " + FU),
      T("왜 줄어?", must=[r"붙|합쳐|자라"], no=NK, check="자라면서 뼈가 붙어서; " + FU),
      T("진짜요?", must=[r"네|정말|붙|맞"], no=NK, check="같은 점 확인"),
      T("단풍은 왜 들어요?", must=[r"엽록소|초록|색소|분해"], no=NK, check="엽록소가 분해되어 다른 색이 보임"),
      T("왜 분해돼요?", must=[r"짧|추워|겨울|낮|에너지"], no=NK, check="날이 짧고 추워지면 나무가 겨울 준비; " + FU),
      T("오케이 땡큐, 다음에 또 올게요!", "end")),
    D("visitor", "world_economy_dialect", "ko",
      T("인플레이션이 뭐꼬?", must=[r"물가|오르|돈"], no=NK, check="물가가 계속 올라 돈의 가치가 떨어지는 것"),
      T("와 생기노?", must=[r"수요|사려는|비용|에너지|돈|많아"], no=NK, check="수요가 많거나 비용이 오를 때; " + FU),
      T("그기 나쁜 기가?", must=[r"조금|적당|2 ?%|2퍼|높으면|저축|월급"], no=NK, check="조금은 정상, 높으면 저축과 월급에 나쁨; " + FU),
      T("부산 인구 얼마나 되노?", must=[r"330|340|만"], no=NK, check="약 330만"),
      T("와 그래 많노?", must=[r"두 ?번째|2번째|서울 다음|큰 도시|항구"], no=NK, check="서울 다음으로 큰 도시; " + FU),
      T("고맙데이. 근데 서울은?", must=[r"9\d\d ?만|천만|1,?000만|940|950"], no=NK, check="약 940만; 고맙데이가 끝이 아님"),
      T("많은 기가?", must=[r"네|많|다섯|5분의|5명|절반"], no=NK, check="네, 다섯 명 중 한 명쯤; " + FU),
      T("알겠다, 수고하이소.", "end")),
    D("researcher", "world_people_en", "en",
      T("Who was the first person on the Moon?", must=[r"Armstrong"], no=N, check="Neil Armstrong"),
      T("When?", must=[r"1969"], no=N, check="20 July 1969; " + FU),
      T("Who was with him?", must=[r"Aldrin|Collins"], no=N, check="Buzz Aldrin, Michael Collins in orbit; " + FU),
      T("And then?", must=[r"return|back|Earth|splash|Pacific|came home|walk|flag|samples"], no=N, check="what came next in that story; " + FU),
      T("Interesting.", no=N, check="short reply; talk goes on"),
      T("Who painted the Mona Lisa?", must=[r"Leonardo|da Vinci"], no=N, check="Leonardo da Vinci"),
      T("Where is it now?", must=[r"Louvre|Paris"], no=N, check="the Louvre; " + FU),
      T("Why is it so famous?", must=[r"smile|style|stolen|theft|1911|technique|mystery"], no=N, check="its style and smile, the 1911 theft; " + FU),
      T("Stolen?", must=[r"1911|stolen|theft|Peruggia|yes"], no=N, check="yes, stolen in 1911 and found two years later; " + FU),
      T("By whom?", must=[r"Peruggia|worker|Italian|handyman|employee"], no=N, check="Vincenzo Peruggia, a museum worker; " + FU),
      T("Thanks, I think I'm good.", "end")),
]


if __name__ == "__main__":
    from tests import followup_check as fc
    from tests import dialogue_check as dc
    fc.DIALOGUES = DIALOGUES_WORLD
    (dc.ROOT / "logs" / "a4").mkdir(exist_ok=True)
    dc.OUT_JSON, dc.OUT_MD = dc.ROOT / "logs" / "a4" / "world_check.json", dc.ROOT / "logs" / "a4" / "world_check.md"
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    fc.main(args[0] if args else None, failed="--failed" in sys.argv)
