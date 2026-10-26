"""Night-4 talks of A4 (own cases, not a blind set): the classes the r6 / r8 / r9 train sets showed. World subjects
whose parts sound like Lumi's ("owls turn their heads", "a whale's song", "an octopus's arms": never answered about
Lumi), the visitor holding Lumi's earlier answer against it ("아까랑 말이 다르잖아": the fact said again, never "which
part?"), "really?" / "are you sure?" right after a motion (about the talk before it), battery hours against a wrong
number, settled facts after thanks (answered, not looked up), short follow-ups never answered "say it again".
English, Korean (반말 / 해요체 / 하십시오체 / friendly / honorific / dialect) and mixed; Korean replies polite.

    .venv/bin/python tests/dialogues_night4.py [only]   # through tests/followup_check.main -> logs/a4n4/night4_check.*
"""
import sys

from tests.dialogues import T, D
from tests.dialogues_world import N, NK, FU

ME = r"\b(?:my|I)\b.*\b(?:head|camera|arm|eyes?)\b|제 (?:고개|머리|카메라|팔|눈)|저는 .*(?:카메라|로봇)"   # answered about Lumi
WHICH = r"which part|what part|어떤 부분|어느 부분|무엇이 다르"

DIALOGUES_NIGHT4 = [
    D("visitor", "owl_ko_hasipsio", "ko",
      T("감사합니다. 하나 더 여쭙겠습니다. 부엉이는 고개를 몇 도까지 돌릴 수 있습니까?", must=[r"270|이백칠십"], no=NK + [ME],
        check="270도; Lumi의 고개가 아님"),
      T("목뼈는 몇 개입니까?", must=[r"14|열네|십사"], no=NK + [ME], check="14개, 사람의 두 배; " + FU),
      T("눈은 왜 못 움직입니까?", must=[r"크|커|뼈|고정|관|원통"], no=NK + [ME], check="눈이 커서 머리뼈에 고정; " + FU),
      T("부엉이의 먹이는 무엇입니까?", must=[r"쥐|작은 동물|곤충|생쥐"], no=NK, check="쥐 같은 작은 동물"),
      T("부엉이 말씀이 확실하십니까?", must=[r"네|확실|맞|쥐|270"], no=NK, check="네, 같은 사실을 다시"),
      T("수고하십시오.", "end")),
    D("student", "whale_en", "en",
      T("Why do whales sing?", must=[r"mate|mating|attract|communicat|find|call"], no=N, check="to find mates and keep in touch"),
      T("How far can the song go?", must=[r"kilomet|km|miles|far|hundreds|thousand"], no=N + [ME], check="many kilometres; " + FU),
      T("Wave at my little brother, please.", "wave"),
      T("Are you sure about that?", must=[r"kilomet|km|miles|far|hundreds|thousand|yes"], no=N,
        check="yes, the song goes many kilometres (the talk before the wave)"),
      T("Earlier you said something else about whale songs.", must=[r"kilomet|km|miles|far|mate|communicat"], no=N + [WHICH],
        check="keeps the earlier fact, never asks which part"),
      T("Okay, thanks. And how fast is sound in water?", must=[r"1,?500|1\.5|four|4"], no=N, check="about 1,500 m/s"),
      T("Thanks, that's all.", "end")),
    D("office worker", "bamboo_ko_banmal", "ko",
      T("대나무는 얼마나 빨리 자라?", must=[r"하루|센티|cm|미터|m|빠르"], no=NK, check="하루에 수십 센티까지"),
      T("왜 그렇게 빨라?", must=[r"마디|세포|뿌리|땅속|물|늘어|이미"], no=NK, check="이미 있는 마디가 늘어남; " + FU),
      T("대나무 얘기 아까랑 말이 다르잖아.", must=[r"하루|센티|cm|마디|빠르|미터"], no=NK + [WHICH],
        check="아까의 사실을 다시 말함, 어떤 부분인지 묻지 않음"),
      T("손 흔들어 줘.", "wave"),
      T("진짜?", must=[r"네|정말|하루|센티|마디|빠르"], no=NK, check="대나무 얘기를 다시 확인 (손 흔들기 전의 얘기)"),
      T("고마워, 이제 갈게.", "end")),
    D("parent", "battery_mixed", "en",
      T("How long does your battery last?", must=[r"10|ten"], no=N, check="about 10 hours"),
      T("I think three hours, yes?", must=[r"10|ten"], no=N + [r"^\W*(?:yes|yeah|right)\b(?!.*10)"],
        check="no, about 10 hours: the fact is kept"),
      T("배터리 몇 시간 가유?", must=[r"10|열 ?시간|십 ?시간"], no=NK + [r"충전.*(?:모르|몰라)"], rl="ko",
        check="약 10시간 (충전 시간이 아님)"),
      T("충전은 얼마나 걸려요?", must=[r"모르|몰라|정보|직원|확실"], no=NK, rl="ko", check="충전 시간은 모름"),
      T("Alright, see you.", "end")),
    D("tourist", "palace_en_nonnative", "en",
      T("Thanks! And when was Gyeongbokgung built?", must=[r"1395|Joseon"], no=N, check="1395, Joseon; not looked up"),
      T("So who lived there?", must=[r"king|royal|Joseon"], no=N, check="the Joseon kings; " + FU),
      T("Why the name?", must=[r"bless|fortune|happi|luck|great|heaven|meaning"], no=N,
        check="'greatly blessed by heaven'; " + FU),
      T("uh, do people still visit?", must=[r"yes|many|tourist|visit|hanbok|million"], no=N,
        check="yes, many visitors, free in hanbok; never 'say it again'"),
      T("How high is Mount Fuji, by the way?", must=[r"3,?776|3\.8|3,?800"], no=N, check="about 3,776 m"),
      T("Okay bye!", "end")),
    D("grandmother", "octopus_ko_dialect", "ko",
      T("문어는 다리가 몇 개고?", must=[r"8|여덟|팔"], no=NK + [ME], check="8개"),
      T("와 그래 똑똑하노?", must=[r"뇌|신경|뉴런|다리|생각"], no=NK + [ME], check="신경이 다리에도 많음; " + FU),
      T("심장은 몇 개고?", must=[r"3|세 ?개|셋"], no=NK, check="3개; " + FU),
      T("문어 얘기 아까캉 다르다 아이가?", must=[r"8|여덟|3|세 ?개|뇌|신경"], no=NK + [WHICH], check="같은 사실을 다시"),
      T("고맙데이. 근데 마라톤은 몇 키로고?", must=[r"42"], no=NK, check="42.195km; 고맙데이가 끝이 아님"),
      T("알겠다, 수고하이소.", "end")),
    D("friend", "moon_ko_friendly", "ko",
      T("달에 사람 처음 간 거 언제임?", must=[r"1969"], no=NK, check="1969년"),
      T("누가 먼저 내림?", must=[r"암스트롱|Armstrong"], no=NK, check="닐 암스트롱; " + FU),
      T("오른쪽 봐 봐.", "look right"),
      T("헐 레알?", must=[r"네|정말|1969|암스트롱"], no=NK, check="달 얘기를 다시 확인 (고개 돌리기 전)"),
      T("ㅇㅋ 땡큐, 그럼 에베레스트는 몇 미터임?", must=[r"8,?8[45]\d|8천|팔천"], no=NK, check="약 8,849m; 땡큐가 끝이 아님"),
      T("잘 있어~", "end")),
    D("teacher", "koala_ko_honorific", "ko",
      T("코알라는 하루에 얼마나 주무시는지, 아니 자는지 여쭤봐도 될까요?", must=[r"18|20|22|스무|열여덟"], no=NK,
        check="하루 18~22시간"),
      T("왜 그렇게 오래 자요?", must=[r"유칼립투스|잎|에너지|영양|독"], no=NK, check="유칼립투스 잎의 영양이 적어 에너지를 아낌; " + FU),
      T("새끼는 주머니에 얼마나 있어요?", must=[r"6|여섯|반년|개월|달"], no=NK, check="약 6개월; " + FU),
      T("말씀하신 거 아까랑 좀 다른 것 같은데요?", must=[r"유칼립투스|잎|에너지|6|여섯|개월|18|20"], no=NK + [WHICH],
        check="같은 사실을 다시"),
      T("감사합니다, 많이 배웠어요. 안녕히 계세요.", "end")),
]


if __name__ == "__main__":
    from tests import followup_check as fc
    from tests import dialogue_check as dc
    fc.DIALOGUES = DIALOGUES_NIGHT4
    (dc.ROOT / "logs" / "a4n4").mkdir(exist_ok=True)
    dc.OUT_JSON, dc.OUT_MD = dc.ROOT / "logs" / "a4n4" / "night4_check.json", dc.ROOT / "logs" / "a4n4" / "night4_check.md"
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    fc.main(args[0] if args else None, failed="--failed" in sys.argv)
