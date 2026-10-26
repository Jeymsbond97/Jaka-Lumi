"""More quick-answer kinds about Lumi's body, sensors and limits (assistant/quick_answers.py), each with its answers.
Every answer is a fact of knowledge/lumi_about_en.md; keep them in step. Wordings in English, Korean (반말, 해요체,
하십시오체, honorific, dialect, Konglish, slips) and mixed; "no" wordings are commands and other things' facts that
sound alike.

Questions the quick lane's guards leave to the LLM on purpose are not listed here: the cameras ("camera", "see"),
faces ("recognise", "remember"), what it can lift or hold ("lift", "hold", "things"), the price.
"""
import re


def _ko(stems, ends):
    """Every stem with every ending: _ko(["라이다 있"], ["어", "어요"]) -> ["라이다 있어", "라이다 있어요"]."""
    return [s + e for s in stems for e in ends]


HAVE = ["어", "어요", "니", "나요", "습니까", "으세요", "으십니까", "나", "노", "어유", "음"]     # 있-
CAN = ["어", "어요", "니", "나요", "습니까", "으세요", "나", "노", "어유"]                        # 수 있-
WHAT = ["야", "예요", "에요", "니", "입니까", "인가요", "고", "여", "임"]                         # 뭐-

QUICK_KINDS = {
    "size": ([
        "how wide are you", "how wide is your base", "how wide is the robot", "what's your footprint", "what are your dimensions",
        "what is your size in centimeters", "how much floor space do you take", "how much room do you need",
        "how big is your base", "how deep are you", "what's your width", "how narrow a gap can you pass", "how narrow can a corridor be",
        "can you fit through a door", "how wide does the path need to be", "what are your measurements", "how wide r u",
        "dimensions?", "your dimensions please", "what size are you exactly",
        "폭이 얼마나 돼요", "폭이 몇 센티예요", "너비가 얼마예요", "가로 세로 몇이에요", "가로세로 크기가 어떻게 돼요", "크기가 어떻게 돼요",
        "크기가 어떻게 되세요", "크기가 어떻게 됩니까", "사이즈가 어떻게 돼", "사이즈 몇이야", "몸 크기가 얼마나 돼", "덩치가 얼마나 돼요",
        "베이스 크기가 몇이에요", "바닥 면적이 얼마나 돼요", "자리 얼마나 차지해요", "공간 얼마나 필요해요", "통로 폭이 얼마나 돼야 돼요",
        "좁은 데도 지나갈 수 있어요", "문 통과할 수 있어요", "몇 센티 통로까지 지나가요", "폭 몇이고", "크기가 우째 되노", "크기가 어찌 되유",
        "너 size 얼마야", "사이즈가 어떻게 되세요", "dimension이 어떻게 돼요", "가로 몇 cm야", "너비 몇 cm예요", "치수가 어떻게 돼요",
    ], {"en": ["I'm 51 cm wide, 51 cm deep and 146 cm tall. I need a passage at least 70 cm wide.",
               "My base is 51 by 51 cm and I'm 146 cm tall, up to 186 cm with my lift. A way 70 cm wide is enough for me."],
        "ko": ["저는 가로 51cm, 세로 51cm, 키 146cm예요. 지나가려면 폭이 70cm 이상인 길이 필요해요.",
               "베이스가 51cm에 51cm이고, 키는 146cm, 리프트를 올리면 186cm까지 돼요. 폭 70cm 길이면 지나갈 수 있어요."]}),
    "payload": ([
        "what's your payload", "what is your payload", "what's your max payload", "payload?", "what payload can you handle",
        "how many kilograms can your gripper take", "what is the arm's payload", "maximum payload please",
        "how heavy an object can you pick up", "how heavy can a cup be for you", "what's the heaviest you can pick up",
        "가반하중이 몇이에요", "가반하중 몇 키로예요", "가반하중이 어떻게 돼요", "가반하중 몇이야", "가반 하중이 어떻게 되십니까",
        "최대 하중이 몇 킬로예요", "하중이 몇 키로야", "몇 킬로까지 집을 수 있어요", "몇 키로까지 집어", "얼마나 무거운 걸 집을 수 있어요",
        "제일 무거운 거 몇 키로까지 돼요", "팔이 몇 kg까지 돼요", "팔 하중이 얼마나 돼", "payload 몇이야", "페이로드가 몇이에요",
        "몇 키로까지 잡아", "몇 kg까지 잡을 수 있어요", "무게 몇까지 집을 수 있노", "가반하중 우째 되노",
    ], {"en": ["My arm carries 2 kg including the gripper. The gripper weighs about 1 kg, an estimate, so I can hold roughly 1 kg in my hand.",
               "About 1 kg in my hand: the arm takes 2 kg in total, and the gripper is about 1 kg of that (an estimate). So far I've been tested with cups."],
        "ko": ["팔은 그리퍼를 포함해 2kg까지 들 수 있어요. 그리퍼가 약 1kg(추정치)이라서 손에는 약 1kg까지 들 수 있어요.",
               "손에는 약 1kg까지예요. 팔이 모두 2kg까지 드는데 그리퍼가 그중 약 1kg(추정치)이에요. 지금까지는 컵으로 시험해 봤어요."]}),
    "arm": ([
        "what arm do you have", "what kind of arm do you have", "what robot arm is that", "which arm do you use", "what is your arm",
        "how long is the robot arm", "how far can you reach", "what's your reach", "how far does your hand reach",
        "how many arms do you have", "do you have arms", "do you have two arms", "why only one arm", "is that a cobot arm",
        "what model is the arm", 
        "팔은 뭐 써요", "무슨 팔이에요", "어떤 팔이야", "팔이 어떤 거예요", "팔 모델이 뭐예요", "로봇 팔이 뭐예요", "팔이 몇 개야",
        "팔이 몇 개예요", "팔이 하나예요", "왜 팔이 하나야", "팔 두 개 있어", "팔 길이가 얼마나 돼요", "팔이 얼마나 길어", "팔이 얼마나 길어요",
        "팔 길이 몇이에요", "팔이 어디까지 닿아요", "얼마나 멀리 손이 닿아", "팔 닿는 거리가 얼마예요", "팔 리치가 몇이에요",
        "협동 로봇 팔이에요", "코봇이에요 그 팔", "팔이 몇 개고", "팔이 우째 생겼노",
        "팔 길이가 어떻게 되십니까", "arm 뭐 써요", "arm 길이 몇이야", "팔 reach가 얼마야", "로봇 arm 모델 뭐야", "팔 몇 축이에요",
    ], {"en": ["I have one arm, a Mini 2 collaborative arm with six joints. It reaches 58 cm and is precise to 0.1 mm.",
               "One Mini 2 collaborative arm: six joints, 58 cm reach, 2 kg payload including the gripper. It stops when it bumps into something."],
        "ko": ["팔은 하나예요. 관절이 6개인 Mini 2 협동 로봇 팔이고, 58cm까지 닿고 정밀도는 0.1mm예요.",
               "Mini 2 협동 로봇 팔 하나예요. 관절 6개, 길이 58cm, 그리퍼 포함 2kg까지 들고, 뭔가에 부딪히면 멈춰요."]}),
    "gripper": ([
        "what gripper do you have", "what gripper is that", "what's on the end of your arm", "what kind of hand do you have",
        "do you have a hand", "do you have fingers", "how many fingers do you have", "what's that gripper", "who makes your gripper",
        "how wide can your gripper open", "how wide can you grip", "how big a cup can you grab",
        "how fast does the gripper close",
        "그리퍼 뭐 써요", "그리퍼가 뭐예요", "무슨 그리퍼야", "어떤 그리퍼예요", "손이 어떻게 생겼어", "손가락 몇 개야", "손가락이 몇 개예요",
        "손 있어요", "손가락 있어", "집게가 뭐예요", "집게 어디 거예요", "그리퍼 어디 제품이에요", "얼마나 넓게 벌어져요", "몇 센티까지 잡아요",
        "몇 센티까지 집을 수 있어요", "손가락이 몇 개고", "그리퍼 뭐 쓰노", "그리퍼 머여",
        "gripper 뭐 써요", "그리퍼 brand가 뭐야", "finger 몇 개야", "손 모양이 어때요", "어떤 손이 달려 있으세요",
    ], {"en": ["I wear a Zimmer electric gripper with two long steel fingers, made for cups and glasses. I can grip firm things from about 6 to 9 cm wide.",
               "A Zimmer electric gripper with two steel fingers. It opens and closes in about a second and holds firm things 6 to 9 cm wide; a paper cup is too soft, it gets squeezed flat."],
        "ko": ["팔 끝에 짐머(Zimmer) 전동 그리퍼가 있어요. 긴 강철 손가락 두 개로 약 6cm에서 9cm 폭의 단단한 물건을 잡아요.",
               "짐머 전동 그리퍼이고 손가락은 두 개예요. 1초쯤에 열고 닫고, 6에서 9cm 폭의 단단한 걸 잡아요. 종이컵은 너무 물러서 눌려 버려요."]}),
    "lidar": ([
        "do you have a lidar", "do you have lidar", "what lidar do you use", "where is your lidar", "how far does your lidar go",
        "what's the range of your lidar", "do you have a laser scanner", "do you use a laser", "what is the laser for",
        "is that a lidar at the bottom", "how does your lidar work",
        "라이다 있어요", "라이다 있어", "라이다 있니", "라이다 있습니까", "라이다 있으세요", "라이다 달려 있어요", "라이다 뭐 써요", "라이다 어디 있어요",
        "라이다는 몇 미터까지 봐요", "라이다 범위가 어떻게 돼요", "레이저 스캐너 있어요", "레이저 센서 있어", "레이저 쏘는 거예요",
        "아래 있는 게 라이다예요", "밑에 빨간 불은 뭐예요", "라이다 있나", "라이다 있노", "라이더 있어요", "리다 있어", "lidar 있어요",
        "lidar 몇 미터야", "라이다 range 얼마야",
    ], {"en": ["Yes, a 2D laser scanner, a lidar, at the bottom of my base. It measures from 2 cm to 10 metres over 240 degrees, 30 times a second.",
               "My lidar sits low in my base. I use it to make a map and to know where I am, and it sees obstacles up to 10 metres away."],
        "ko": ["네, 베이스 아래쪽에 2D 라이다(레이저 스캐너)가 있어요. 2cm부터 10m까지, 240도를 1초에 30번 재요.",
               "라이다는 베이스 아래쪽에 있어요. 지도를 만들고 제 위치를 알 때 쓰고, 10m 앞의 장애물까지 봐요."]}),
    "sensors": ([
        "what sensors do you have", "which sensors do you have", "what sensors are on you", "how many sensors do you have",
        "list your sensors", "what kind of sensors do you use", "do you have ultrasonic sensors", "how many ultrasonic sensors",
        "do you have a bumper", "do you have an imu", "what are your sensors", "sensors?",
        "센서 뭐 있어요", "센서 뭐 있어", "센서가 뭐 있니", "센서는 뭐가 있습니까", "센서 몇 개예요", "센서 몇 개야", "센서 어떤 거 써요",
        "무슨 센서 달려 있어요", "어떤 센서가 있으세요", "초음파 센서 있어요", "초음파 센서 몇 개야", "범퍼 있어요", "센서 종류가 뭐예요",
        "센서 뭐 있노", "센서 머 있어", "센서 뭐 달렸슈", "sensor 뭐 있어요", "너 sensor 몇 개야", "센서 list 알려 줘",
    ], {"en": ["I have a 2D lidar, three depth cameras, five ultrasonic sensors, an infrared sensor, an inertial sensor and a bumper, and six microphones.",
               "A lidar for the map, three 3D cameras, five ultrasonic sensors, an inertial sensor and a bumper that stops me when it's pressed."],
        "ko": ["2D 라이다, 깊이 카메라 세 대, 초음파 센서 5개, 적외선 센서, 관성 센서, 범퍼가 있고, 마이크도 6개 있어요.",
               "지도용 라이다, 3D 카메라 세 대, 초음파 센서 5개, 관성 센서, 그리고 눌리면 저를 멈추는 범퍼가 있어요."]}),
    "stairs": ([
        "can you climb stairs", "can you go up stairs", "can you go upstairs", "can you take the stairs", "can you use stairs",
        "can you climb steps", "can you go over a step", "can you drive up a ramp", "can you go up a slope", "can you go over bumps",
        "how high a step can you climb", "can you drive on a slope", "can you use the escalator", "can you take the elevator",
        "계단 올라갈 수 있어", "계단 올라갈 수 있어요", "계단 올라갈 수 있니", "계단 오를 수 있습니까", "계단 오르실 수 있으세요",
        "계단 갈 수 있어", "계단 돼요", "계단도 가요", "2층 올라갈 수 있어요", "문턱 넘을 수 있어요", "턱 넘을 수 있어", "경사로 올라가요",
        "비탈길 갈 수 있어요", "오르막 갈 수 있어", "에스컬레이터 탈 수 있어요", "엘리베이터 탈 수 있어", "계단 올라갈 수 있나",
        "계단 올라가나", "계단 오를 수 있노", "계단 올라가유", "stairs 올라갈 수 있어", "계단 climb 돼요", "slope 올라가요",
    ], {"en": ["No, I can't climb stairs: I drive on wheels. I can go over a step of at most 1.5 cm and up a slope of at most 8 degrees.",
               "Stairs, no. Small bumps up to 1.5 cm and slopes up to 8 degrees are fine, and I need a way at least 70 cm wide."],
        "ko": ["아니요, 계단은 못 올라가요. 바퀴로 다녀서 1.5cm 이하의 턱과 8도 이하의 경사만 갈 수 있어요.",
               "계단은 못 가요. 1.5cm까지의 턱과 8도까지의 경사는 괜찮고, 폭 70cm 이상인 길이 필요해요."]}),
    "turn_range": ([
        "how far can your head turn", "how far does your head turn", "can your head turn all the way around",
        "how many degrees can your head turn", "can you turn your head 360 degrees", "how far can you tilt your head",
        "how far can your waist turn", "how far does your waist rotate", "can your waist spin all the way",
        "can you rotate your waist", "can your body turn", "what's the range of your head",
        "고개 몇 도까지 돌아가", "고개 몇 도까지 돌아가요", "고개가 얼마나 돌아가요", "머리 몇 도까지 돌아가요", "머리가 360도 돌아가요",
        "고개가 끝까지 돌아가", "머리 얼마나 돌릴 수 있어요", "고개 위아래로 얼마나 움직여요", "허리 몇 도까지 돌아가요", "허리가 얼마나 돌아가",
        "허리 돌릴 수 있어요", "허리 회전 몇 도예요", "몸통 얼마나 돌아가요", "머리 회전 범위가 어떻게 됩니까", "고개 몇 도까지 돌아가노",
        "모가지 얼마나 돌아가", "head 몇 도까지 돌아가", "waist 회전 몇 도야", "고개 rotation 범위가 어떻게 돼요",
    ], {"en": ["My head turns up to 180 degrees left or right and tilts up and down within 40 degrees. My waist turns up to 160 degrees each way.",
               "Head: 180 degrees to each side, and a 40-degree tilt. Waist: 160 degrees to each side."],
        "ko": ["머리는 좌우로 180도까지 돌고, 위아래로 40도 범위에서 움직여요. 허리는 좌우로 160도까지 돌아가요.",
               "고개는 양쪽으로 180도, 위아래로 40도 범위예요. 허리는 양쪽으로 160도까지 돌아요."]}),
    "grow": ([
        "can you grow taller", "can you get taller", "can you change your height", "can you make yourself taller",
        "how tall can you get", "what's your maximum height", "how high can you go up", "how far can you rise",
        "can you go up and down", "what does the lift do", "what's the column for", "how high can you stretch",
        "키 커질 수 있어", "키 커질 수 있어요", "키가 커질 수 있니", "키를 바꿀 수 있어요", "키 조절돼요", "키 조절할 수 있어", "키 높일 수 있어요",
        "최대 키가 몇이에요", "제일 크면 몇 센티예요", "얼마나 높이 올라가요", "몸이 위아래로 움직여요", "리프트가 뭐예요", "리프트 몇 센티 올라가요",
        "키가 늘어나요", "키 늘어나나", "키 크게 할 수 있노", "키 높낮이 조절됩니까", "키 조절 되세요", "height 조절 돼요", "lift 몇 cm 올라가",
    ], {"en": ["Yes, a little: my lifting column raises my upper body by up to 40 cm, from 146 cm to 186 cm.",
               "My lift takes me from 146 cm up to 186 cm, 40 cm higher."],
        "ko": ["네, 조금요. 리프트로 상체를 40cm까지 올려서 146cm에서 186cm까지 돼요.",
               "리프트로 40cm 올라가서 146cm에서 최대 186cm까지 돼요."]}),
    "charging": ([
        "how do you charge", "how do you get charged", "how do you recharge", "can you charge yourself", "do you charge by yourself",
        "where do you charge", "do you have a charging station", "do you plug in", "do you need to be plugged in",
        "what happens when your battery is low", "what do you do when your battery runs low", "do you go charge on your own",
        "충전 어떻게 해요", "충전은 어떻게 해", "충전 어떻게 하니", "충전은 어떻게 하십니까", "어떻게 충전하세요", "혼자 충전할 수 있어요",
        "스스로 충전해요", "혼자 충전하러 가", "충전기 어디 있어요", "충전소 있어요", "충전 스테이션 있어", "플러그 꽂아야 돼요", "선 꽂아서 충전해요",
        "배터리 없으면 어떻게 해요", "배터리 떨어지면 어떡해", "배터리 다 되면 어떻게 돼요", "충전 우째 하노", "충전 어떻게 해유",
        "charging 어떻게 해요", "혼자 charge 돼요", "auto charging 돼요", "자동 충전 돼요",
    ], {"en": ["I charge on a charging dock, through contacts under my base, and I can drive onto it by myself.",
               "I drive onto my charging dock on my own. When I patrol and my battery falls below 5 percent I go home to charge, and I go on at 60 percent."],
        "ko": ["충전 도크에서 베이스 아래 접점으로 충전해요. 도크에는 제가 혼자 올라갈 수 있어요.",
               "충전 도크로 혼자 가서 충전해요. 순찰하다가 배터리가 5% 아래로 떨어지면 충전하러 가고, 60%가 되면 다시 일해요."]}),
    "battery_spec": ([
        "what battery do you have", "what kind of battery do you use", "what type of battery is it", "is it a lithium battery",
        "how many volts is your battery", "what's your battery voltage", "what's your battery capacity", "how big is your battery",
        "how many amp hours", "where is your battery",
        "배터리 뭐 써요", "무슨 배터리예요", "어떤 배터리야", "배터리 종류가 뭐예요", "리튬 배터리예요", "배터리 몇 볼트예요", "배터리 전압이 얼마예요",
        "배터리 용량이 얼마나 돼요", "배터리 용량 몇이야", "배터리 몇 암페어예요", "배터리 어디 있어요", "배터리 뭐 쓰노", "배터리 용량이 어떻게 되십니까",
        "battery 용량 얼마야", "battery spec 알려 줘", "배터리 capacity 몇이에요",
    ], {"en": ["A 24-volt lithium-ion battery of 45 Ah in my base. It lasts about 10 hours."],
        "ko": ["베이스에 24볼트, 45Ah 리튬이온 배터리가 있어요. 약 10시간 가요."]}),
    "navigation": ([
        "how do you navigate", "how do you find your way", "how do you know where you are", "how do you know where to go",
        "how do you drive by yourself", "do you drive on your own", "are you autonomous", "can you drive autonomously",
        "how does your navigation work", "do you have a map", "do you use a map", "how accurate is your navigation",
        "do you use gps", "how do you know the way",
        "자율주행 어떻게 해요", "자율주행 돼요", "자율주행 하니", "혼자 다닐 수 있어요", "길은 어떻게 찾아요", "길 어떻게 찾아", "위치는 어떻게 알아요",
        "어디 있는지 어떻게 알아", "지도 있어요", "지도 써요", "지도를 어떻게 만들어요", "GPS 써요", "내비게이션 어떻게 해요", "자율 주행입니까",
        "길 우째 찾노", "길 어떻게 찾아유", "혼자 길 찾아가세요", "navigation 어떻게 해요", "자율주행 how", "map 있어요", "SLAM 써요",
    ], {"en": ["I drive with a map of the room made with my lidar. I compare what the lidar sees with the map to know where I am, to within about 5 cm, and plan a path around people and obstacles.",
               "With a lidar map: I know where I am on it to about 5 cm, and I drive to named places on my own, around people and obstacles."],
        "ko": ["라이다로 만든 지도에서 제 위치를 약 5cm 정확도로 알고, 지도 위의 장소까지 사람과 장애물을 피해 경로를 짜서 가요.",
               "라이다 지도로 다녀요. 지도에서 제 위치를 5cm 정도로 알고, 이름 붙은 장소까지 혼자 장애물을 피해서 가요."]}),
    "obstacles": ([
        "how do you avoid obstacles", "how do you avoid people", "do you avoid obstacles", "will you bump into people",
        "do you crash into things", "what if someone is in your way", "what happens if someone stands in front of you",
        "can you avoid collisions", "are you safe to be around", "will you run me over", "do you stop for people",
        "장애물 어떻게 피해요", "장애물 피할 수 있어요", "장애물 피해", "사람 피할 수 있어", "사람 피해요", "부딪히지 않아요", "사람한테 부딪혀요",
        "앞에 사람 있으면 어떻게 돼요", "길 막히면 어떻게 해요", "충돌하면 어떻게 돼요", "안 부딪혀", "장애물 피하나", "장애물 우째 피하노",
        "obstacle 피할 수 있어요", "장애물 avoid 돼요",
    ], {"en": ["My lidar, my 3D camera and five ultrasonic sensors see obstacles, and I drive around them. I drive slowly and stop for people in my way, and my bumper stops me if it's pressed.",
               "I see obstacles with my lidar, my cameras and my ultrasonic sensors, plan my way around them, and stop when someone is in my way. My arm stops when it bumps into something."],
        "ko": ["라이다, 3D 카메라, 초음파 센서 5개로 장애물을 보고 피해서 가요. 앞에 사람이 있으면 천천히 가거나 멈추고, 범퍼가 눌리면 바로 멈춰요.",
               "라이다와 카메라, 초음파 센서로 사람과 장애물을 보고 피해서 경로를 짜요. 길에 사람이 있으면 멈추고, 팔도 뭔가에 부딪히면 멈춰요."]}),
    "dance": ([
        "can you dance", "do you dance", "do you know how to dance", "are you able to dance", "can robots dance",
        "can you walk", "do you walk", "do you have legs", "can you run", "can you jump", "can you fly", "can you swim",
        "춤출 수 있어", "춤출 수 있어요", "춤 출 줄 알아", "춤출 줄 아니", "춤추실 수 있으세요", "춤 출 수 있습니까", "춤 잘 춰", "춤춰요",
        "걸을 수 있어", "걸을 수 있어요", "걸어 다녀요", "다리 있어요", "다리 있어", "뛸 수 있어", "점프할 수 있어요", "날 수 있어", "수영할 수 있어",
        "춤 출 줄 아나", "춤 출 수 있노", "춤 출 줄 알아유", "dance 할 수 있어", "댄스 돼요",
        "walk 할 수 있어",
    ], {"en": ["No, I can't dance, walk, jump or fly: I drive on two wheels. But I can wave, and move my head when I sing.",
               "I have no legs, I drive on two wheels, so no dancing or jumping. I can wave and sing a song for you, though."],
        "ko": ["아니요, 저는 춤추거나 걷거나 뛰지 못해요. 바퀴 두 개로 다녀요. 대신 손을 흔들 수 있고, 노래할 때 고개를 움직여요.",
               "다리가 없고 바퀴로 다녀서 춤이나 점프는 못 해요. 대신 손을 흔들거나 노래를 불러 드릴 수 있어요."]}),
    "doors": ([
        "can you open doors", "can you open a door", "can you open the door by yourself", "do you open doors",
        "can you press elevator buttons", "can you push buttons", "can you go through doors",
        "문 열 수 있어", "문 열 수 있어요", "문 열 줄 알아", "문 열 수 있니", "문 여실 수 있으세요", "문 열 수 있습니까", "문 열 수 있나",
        "문 열 수 있노", "혼자 문 열어요", "엘리베이터 버튼 누를 수 있어요", "버튼 누를 수 있어", "문 open 할 수 있어",
    ], {"en": ["No, I can't open doors. I drive through open ones that are at least 70 cm wide.",
               "Doors, no: I can't open them or climb stairs. An open passage 70 cm wide is fine."],
        "ko": ["아니요, 문은 못 열어요. 폭 70cm 이상으로 열려 있는 문은 지나갈 수 있어요.",
               "문 열기는 못 해요. 열려 있고 폭이 70cm 이상이면 지나갈 수 있어요."]}),
    "software": ([
        "what software do you run", "what programming language are you written in", "what are you programmed in",
        "are you written in python", "what language is your code", "what is your software", "do you use ros",
        "what operating system do you use", "who wrote your software", "what's your code written in",
        "무슨 소프트웨어로 돌아가요", "프로그래밍 언어 뭐 써요", "무슨 언어로 만들었어요", "파이썬으로 만들었어요", "코드는 뭘로 짰어요",
        "소프트웨어 뭐 써", "프로그램 뭘로 짰어", "어떤 언어로 프로그래밍했어요", "ROS 써요", "운영체제 뭐예요", "코딩 뭘로 했노",
        "software 뭐 써요", "python으로 짰어요", "코드 언어가 뭐야",
    ], {"en": ["My software, which lets me talk, see, drive and pick things up, is written in Python and runs on my NVIDIA computer.",
               "Python, running on my NVIDIA Jetson Thor. Cutshion wrote it."],
        "ko": ["말하고, 보고, 다니고, 물건을 집는 제 소프트웨어는 파이썬으로 짜여 있고 엔비디아 컴퓨터에서 돌아가요.",
               "파이썬으로 짜여 있고, 엔비디아 젯슨 토르에서 돌아가요. 쿳션이 만들었어요."]}),
    "detector": ([
        "how do you detect people", "how do you detect objects", "what object detection do you use", "what detector do you use",
        "do you use yolo", "what vision model do you use", "what neural network do you use for vision", "how fast is your detection",
        "how do you find people", "how do you find objects",
        "사람을 어떻게 찾아요", "사람 어떻게 인식해", "물체 인식은 뭘로 해요", "물체 인식 뭐 써요", "객체 인식 모델이 뭐예요", "욜로 써요",
        "YOLO 써요", "비전 모델 뭐 써", "인식 모델 뭐예요", "사람 인식은 뭘로 하십니까", "물건 어떻게 찾아요", "object detection 뭐 써요",
        "vision AI 뭐 써", "사람 detect 어떻게 해",
    ], {"en": ["I find people and objects with a neural network called YOLOv8 on my graphics processor; it looks at one camera picture in about 4 to 13 milliseconds."],
        "ko": ["사람과 물건은 그래픽 프로세서에서 돌아가는 욜로(YOLOv8) 신경망으로 찾아요. 카메라 사진 한 장을 약 4에서 13밀리초 만에 봐요."]}),
    "teach": ([
        "can you learn", "can you learn new tasks", "how do you learn", "how can you be taught", "can people teach you",
        "can you be programmed", "can you learn from demonstrations", "can you be controlled with vr", "do you learn by yourself",
        "can someone teach you a new skill", "can you be trained",
        "배울 수 있어", "배울 수 있어요", "새로운 거 배울 수 있니", "학습할 수 있어요", "학습 돼요", "어떻게 배워요", "가르칠 수 있어요",
        "가르치면 배워", "새 작업 가르칠 수 있습니까", "VR로 조종돼요", "원격 조종 돼요", "티칭 돼요", "배울 수 있나", "배울 수 있노",
        "learning 돼요", "새 skill 배울 수 있어", "teaching 가능해요",
    ], {"en": ["People can teach me new tasks by moving my arm by hand, by writing programs, or by remote control with a VR headset, and I can learn skills from demonstrations."],
        "ko": ["제 팔을 손으로 움직여서 가르치거나, 프로그램을 짜거나, VR 헤드셋으로 원격 조종해서 새 일을 가르칠 수 있어요. 시범을 보고 기술을 배울 수도 있어요."]}),
    "touch": ([
        "is it ok to touch you", "is it safe to touch you", "can people touch you", "may we touch you", "can kids touch you",
        "can you be pushed", "is it okay to push you", "are you dangerous", "is it safe near you", "are you safe for kids",
        "만져도 돼", "만져도 돼요", "만져도 되니", "만져도 됩니까", "만져도 되나요", "만져 봐도 되세요", "만져도 괜찮아요", "만지면 안 돼요",
        "밀어도 돼요", "밀어도 되나", "애들이 만져도 돼요", "아이들 옆에 있어도 안전해요", "만져도 되나", "만지도 되나",
        "만져도 되노", "만져도 돼유", "touch 해도 돼요", "만져도 OK예요",
    ], {"en": ["You may touch me, but please keep your hands away from my gripper fingers when they close, and please don't push me: I'm heavy.",
               "Yes, gently. Keep your hands away from my gripper fingers when they close, and don't push my base while I'm switched on."],
        "ko": ["만지셔도 돼요. 다만 그리퍼 손가락이 닫힐 때는 손을 가까이 대지 마시고, 저는 무거우니까 밀지 말아 주세요.",
               "살살 만지셔도 돼요. 그리퍼 손가락이 닫힐 때는 손을 떼 주시고, 켜져 있을 때는 베이스를 밀지 말아 주세요."]}),
    "accuracy": ([
        "how accurate is your position", "how precise is your map position", "how accurate is your arm", "what's your repeatability",
        "how precise are you", "how accurate are you", "what's your precision", "how exact is your arm",
        "몇 센티 오차예요", "오차가 몇 센티야", "위치 오차가 얼마예요", "팔 정확도가 얼마예요", "반복 정밀도가 얼마예요", "정밀도가 어떻게 돼요",
        "얼마나 정확해요", "얼마나 정밀해", "정확도가 몇이에요", "오차 얼마나 나요", "오차가 어떻게 됩니까", "정밀도 몇이고", "precision 얼마예요",
        "accuracy 몇이야", "repeatability 얼마예요",
    ], {"en": ["My arm repeats a position to 0.1 mm, and on my map I know where I am to within about 5 cm."],
        "ko": ["팔의 반복 정밀도는 0.1mm이고, 지도에서 제 위치는 약 5cm 정확도로 알아요."]}),
    "pick_what": ([
        "what can you pick up", "what objects can you pick up", "what can you grab", "what can you grip", "what objects do you know",
        "which objects can you pick", "can you pick from the floor", "can you pick up from the floor", "can you reach the floor",
        "뭐 집을 수 있어", "뭐 집을 수 있어요", "뭘 집을 수 있니", "무엇을 집을 수 있습니까", "어떤 걸 집을 수 있어요", "뭐 잡을 수 있어",
        "병도 집을 수 있어요", "사과 집을 수 있어", "과일 집을 수 있어요", "바닥에 있는 거 주울 수 있어요", "바닥에서 주울 수 있어",
        "어떤 거 집을 수 있으세요", "뭐 집을 수 있노", "뭐 집을 수 있나", "뭐 pick 할 수 있어", "pick up 뭐 돼요",
    ], {"en": ["I can pick up cups, mugs and glasses, bottles, apples, oranges and bananas, from a table or a box near table height. I can't pick from the floor. So far I've picked up cups live.",
               "Cups, glasses, bottles and fruit like apples, oranges and bananas, from about table height. Not from the floor: I can't reach that low."],
        "ko": ["컵, 머그, 유리잔, 병, 사과, 오렌지, 바나나를 탁자 높이에서 집을 수 있어요. 바닥에 있는 건 못 집어요. 실제로 집어 본 건 컵이에요.",
               "탁자 높이에 있는 컵, 유리잔, 병, 그리고 사과, 오렌지, 바나나 같은 과일을 집어요. 바닥은 팔이 안 닿아서 못 집어요."]}),
    "operator": ([
        "who operates you", "who's in charge of you", "who takes care of you", "who looks after you",
        "who is responsible for you", "who runs you here", "is there a staff member",
        "누가 관리해요", "관리자가 누구예요", "누가 운영해요", "담당자가 누구예요",
        "책임자가 누구야", "관리는 누가 하십니까", "누가 관리하노", "manager 누구예요", "담당 staff 누구예요",
    ], {"en": ["Cutshion Company operates me here. If you need help with something I can't do, please ask a staff member."],
        "ko": ["여기서는 쿳션이 저를 운영해요. 제가 못 하는 일은 직원에게 물어봐 주세요."]}),
}

# the same meanings at every Korean speech level (반말, 해요체, 하십시오체, honorific, dialect)
for _kind, _stems, _ends in [
    ("lidar", ["라이다 ", "레이저 센서 "], [s + e for s in ["있"] for e in HAVE]),
    ("stairs", ["계단 올라갈 ", "계단 오를 "], ["수 " + s + e for s in ["있"] for e in CAN]),
    ("dance", ["춤출 ", "걸을 "], ["수 " + s + e for s in ["있"] for e in CAN]),
    ("doors", ["문 열 "], ["수 " + s + e for s in ["있"] for e in CAN]),
    ("teach", ["새로운 일 배울 ", "배울 "], ["수 " + s + e for s in ["있"] for e in CAN]),
    ("gripper", ["그리퍼 ", "그리퍼는 "], ["뭐" + e for e in WHAT]),
    ("sensors", ["센서는 ", "무슨 센서 "], ["있" + e for e in HAVE]),
]:
    QUICK_KINDS[_kind][0].extend(_ko(_stems, _ends))

QUICK = {
    "no": [
        # commands that sound like these questions: the rules
        "turn your head 180 degrees", "turn your head all the way", "tilt your head up", "turn your waist", "rotate your waist left",
        "고개 180도 돌려", "고개 끝까지 돌려", "허리 돌려", "허리 왼쪽으로 돌려", "머리 위로 들어", "grow taller now", "get taller", "lift up",
        "키 커져 봐", "키 높여", "리프트 올려", "go charge", "go to your charger", "go charge yourself", "charge now", "충전하러 가",
        "충전하러 가 줘", "충전기로 가", "dance for me", "dance", "do a dance", "춤 춰", "춤춰 봐", "춤 좀 춰 줘", "open the door",
        "문 열어", "문 좀 열어 줘", "pick up the cup", "pick up the bottle", "pick up that apple", "컵 집어", "병 집어 줘", "사과 집어 줘",
        "climb the stairs", "go upstairs", "계단 올라가 봐", "2층으로 가", "reach out", "reach out your arm", "팔 뻗어", "팔 내밀어",
        "show me your gripper", "open your gripper", "close your gripper", "그리퍼 열어", "그리퍼 닫아", "손 펴", "손 쥐어",
        "avoid the chair", "go around the table", "의자 피해서 가", "turn on the lidar", "라이다 켜", "teach me something", "나 좀 가르쳐 줘",
        "touch my hand", "내 손 만져", "push the cart", "밀어", "navigate to p1", "p1으로 가", "find the way to the door", "길 안내해 줘",
        # other things' facts
        "how wide is the door", "how wide is this room", "how big is this room", "문 폭이 얼마예요", "이 방 크기가 얼마예요",
        "how far can a car go", "how many stairs are there", "계단 몇 개야", "where are the stairs", "계단 어디 있어요", "where's the elevator",
        "엘리베이터 어디예요", "where's the door", "문 어디예요", "how heavy is the cup", "컵 무게가 얼마예요", "what's in the cup", "컵에 뭐 있어",
        "how accurate is the weather forecast", "일기예보 정확해요", "who is the staff here", "how do i charge my phone", "핸드폰 충전 어디서 해요",
        "where can i charge my phone", "do you have a phone charger", "충전기 있어요 핸드폰", "what sensors does a car have",
        "what language do people speak here", "what software does cutshion make", "쿳션은 무슨 소프트웨어 만들어요",
        "can my kid dance with you", "do you like dancing", "춤 좋아해", "do you like stairs", "what's your favorite dance",
        "can the ice cream robot dance", "아이스크림 로봇 춤춰요", "barista robot arm 몇 축이에요", "바리스타 로봇 팔 뭐 써요",
        "how fast is the barista robot arm", "does the barista robot have a lidar", "does the ice cream robot have sensors", "does the drawing robot have a camera", "바리스타 로봇도 라이다 있어요", "아이스크림 로봇 센서 뭐 써요", "does your car have a lidar", "does a tesla have lidar", "jaka arm payload", "자카 로봇 가반하중", "what's the payload of the zu 7",
        # the battery now, the charging time: assistant/battery.py
        "are you charging", "are you charging now", "충전 중이야", "충전 중이에요", "how long to charge", "충전 얼마나 걸려",
        "how much battery is left", "배터리 몇 퍼센트야",
    ],
}

# The same questions said by everyone: each kind's nouns and abilities with every Korean speech level and the usual
# English frames, with or without a subject ("너", "루미", "이 로봇", "this robot").
KO_WHO = ["", "너 ", "루미 ", "이 로봇 ", "로봇 ", "니 "]
HOW = ["어떻게 돼", "어떻게 돼요", "어떻게 되니", "어떻게 되나요", "어떻게 되세요", "어떻게 되십니까", "어떻게 됩니까", "어떻게 되노",
       "어떻게 되유", "어떻게 됨", "우째 되노", "얼마나 돼", "얼마나 돼요", "얼마나 되니", "얼마나 되세요", "몇이야", "몇이에요", "몇이니",
       "몇입니까", "몇이고", "몇이여", "몇이세요"]
USE = ["뭐 써", "뭐 써요", "뭐 쓰니", "뭐 쓰세요", "뭐 쓰십니까", "뭐 씁니까", "뭐 쓰노", "뭐 써유", "뭐야", "뭐예요", "뭐니", "뭡니까",
       "뭐고", "뭐여", "뭔가요", "무슨 거야", "어떤 거예요", "어떤 걸 쓰세요"]
ABLE = ["수 있어", "수 있어요", "수 있니", "수 있나요", "수 있으세요", "수 있으십니까", "수 있습니까", "수 있나", "수 있노", "수 있어유",
        "수 있음", "줄 알아", "줄 알아요", "줄 아니", "줄 아세요", "줄 압니까", "줄 아나", "줄 아노", "수 있겠어", "수 있겠어요"]
TELL = ["알려 줘", "좀 알려 줘", "알려 줘요", "알려 주세요", "좀 알려 주세요", "알려 주십시오", "알려 주시겠어요", "말해 줘", "말해 주세요",
        "알려 주이소", "알려 도"]   # "<noun> 알려 줘": the same question asked as a request
EN_NOUN = ["what's your {}", "what is your {}", "tell me your {}", "what {} do you have", "what's the robot's {}", "your {}?",
           "what is lumi's {}", "what's this robot's {}", "{} of this robot", "what {} does this robot have"]
EN_ABLE = ["can you {}", "are you able to {}", "can lumi {}", "is this robot able to {}", "do you know how to {}", "can this robot {}",
           "is lumi able to {}", "you can {}?"]
EN_HAVE = ["do you have {}", "have you got {}", "does this robot have {}", "does lumi have {}", "is there {} on you", "any {}?"]

NOUNS = {   # kind: ([Korean nouns with 은/는/이/가 or none], [English nouns])
    "size": (["크기가 ", "크기 ", "사이즈가 ", "사이즈 ", "폭이 ", "폭 ", "너비가 ", "치수가 ", "가로세로 크기가 "],
             ["size", "dimensions", "width", "footprint", "measurements"]),
    "arm": (["팔 길이가 ", "팔 길이 ", "팔 리치가 ", "팔 닿는 거리가 "], ["arm model", "reach", "robot arm"]),
    "payload": (["가반하중이 ", "가반하중 ", "최대 하중이 ", "하중이 ", "팔 하중이 "], ["payload", "maximum payload", "payload capacity"]),
    "battery_spec": (["배터리 용량이 ", "배터리 전압이 ", "배터리 사양이 ", "배터리 스펙이 "],
                     ["battery type", "battery capacity", "battery voltage", "battery spec"]),
    "accuracy": (["정밀도가 ", "정확도가 ", "오차가 ", "반복 정밀도가 ", "위치 정확도가 "], ["precision", "accuracy", "repeatability"]),
    "turn_range": (["고개 회전 범위가 ", "머리 회전 범위가 ", "허리 회전 범위가 ", "고개 돌아가는 각도가 ", "허리 돌아가는 각도가 "],
                   ["head rotation range", "waist rotation range", "head turning range"]),
}
TOOLS = {   # kind: ([Korean nouns], [English nouns]) asked "뭐 써?"
    "arm": (["팔은 ", "팔 ", "로봇 팔은 ", "로봇 팔 "], ["arm", "robot arm"]),
    "gripper": (["그리퍼는 ", "그리퍼 ", "집게는 ", "집게 ", "손은 ", "로봇 손은 "], ["gripper", "robot hand", "end effector"]),
    "sensors": (["센서는 ", "센서 ", "무슨 센서 "], ["sensors"]),
    "lidar": (["라이다는 ", "라이다 ", "레이저 스캐너는 "], ["lidar", "laser scanner"]),
    "battery_spec": (["배터리는 ", "배터리 종류는 "], ["battery"]),
    "software": (["소프트웨어는 ", "소프트웨어 ", "프로그래밍 언어는 ", "프로그래밍 언어 ", "코드는 ", "프로그램은 "],
                 ["software", "programming language", "code language"]),
    "detector": (["물체 인식은 ", "물체 인식 모델은 ", "사람 인식은 ", "비전 모델은 ", "객체 인식 모델 ", "인식 모델 "],
                 ["object detector", "vision model", "detection model", "person detector"]),
}
ABILITIES = {   # kind: ([Korean verbs before 수 / 줄], [English verbs])
    "stairs": (["계단 올라갈 ", "계단 오를 ", "계단 갈 ", "턱 넘을 ", "경사로 올라갈 ", "오르막 갈 "],
               ["climb stairs", "go up stairs", "take the stairs", "climb steps", "go up a ramp", "go over a step"]),
    "dance": (["춤출 ", "춤 출 ", "걸을 ", "걸어 다닐 ", "뛸 ", "점프할 ", "날 "], ["dance", "walk", "run", "jump", "fly"]),
    "doors": (["문 열 ", "문을 열 ", "혼자 문 열 "], ["open doors", "open a door", "open the door by yourself"]),
    "teach": (["배울 ", "새로운 걸 배울 ", "새 일 배울 ", "학습할 "], ["learn", "learn new tasks", "learn new skills", "be taught"]),
    "charging": (["혼자 충전할 ", "스스로 충전할 ", "충전하러 혼자 갈 "], ["charge yourself", "charge by yourself", "dock by yourself"]),
    "navigation": (["혼자 다닐 ", "혼자 길 찾을 ", "자율주행 할 ", "스스로 운전할 "],
                   ["drive by yourself", "drive on your own", "find your way", "drive autonomously", "navigate on your own"]),
    "obstacles": (["장애물 피할 ", "장애물을 피할 ", "사람 피할 ", "사람을 피해 갈 "], ["avoid obstacles", "avoid people", "avoid collisions"]),
    "grow": (["키 키울 ", "키 늘릴 ", "키를 높일 ", "키 조절할 "], ["grow taller", "get taller", "change your height", "raise yourself"]),
    "pick_what": (["바닥에서 주울 ", "바닥에 있는 걸 주울 "], ["pick things from the floor", "reach the floor", "pick from the floor"]),
}
HAVES = {   # kind: ([Korean nouns before 있-], [English "a ..."])
    "lidar": (["라이다 ", "라이다가 ", "레이저 스캐너 ", "레이저 센서 "], ["a lidar", "lidar", "a laser scanner"]),
    "sensors": (["초음파 센서 ", "범퍼 ", "관성 센서 ", "센서 "], ["ultrasonic sensors", "a bumper", "an imu", "sensors"]),
    "gripper": (["손가락 ", "손 ", "그리퍼 ", "집게 "], ["fingers", "a hand", "a gripper"]),
    "navigation": (["지도 ", "지도가 ", "내비게이션 "], ["a map", "navigation", "gps"]),
    "charging": (["충전기 ", "충전 스테이션 ", "충전 도크 "], ["a charging station", "a charging dock", "a charger"]),
    "dance": (["다리 ", "다리가 "], ["legs"]),
}
for _kind, (_ko_n, _en_n) in NOUNS.items():
    QUICK_KINDS[_kind][0].extend(w + n + e for w in ["", "너 ", "이 로봇 "] for n in _ko_n for e in HOW)
    QUICK_KINDS[_kind][0].extend(w + n + e for w in ["", "로봇 ", "이 로봇 ", "루미 "]
                                 for n in dict.fromkeys(re.sub(r"[이가] $", " ", n) for n in _ko_n) for e in TELL)
    QUICK_KINDS[_kind][0].extend(f.format(n) for f in EN_NOUN for n in _en_n)
for _kind, (_ko_n, _en_n) in TOOLS.items():
    QUICK_KINDS[_kind][0].extend(w + n + e for w in KO_WHO[:4] for n in _ko_n for e in USE)
    QUICK_KINDS[_kind][0].extend(f.format(n) for f in ["what {} do you use", "what {} do you have", "which {} do you use", "what {} is that",
                                                       "what kind of {} do you have", "what's your {}", "what {} does this robot use"]
                                 for n in _en_n)
for _kind, (_ko_v, _en_v) in ABILITIES.items():
    QUICK_KINDS[_kind][0].extend(w + v + e for w in KO_WHO[:4] for v in _ko_v for e in ABLE)
    QUICK_KINDS[_kind][0].extend(f.format(v) for f in EN_ABLE for v in _en_v)
for _kind, (_ko_n, _en_n) in HAVES.items():
    QUICK_KINDS[_kind][0].extend(w + n + e for w in KO_WHO[:4] for n in _ko_n for e in ["있" + h for h in HAVE] + ["달려 있어", "달려 있어요", "달려 있나요"])
    QUICK_KINDS[_kind][0].extend(f.format(n) for f in EN_HAVE for n in _en_n)
QUICK_KINDS["dance"][0].append("춤 출 수 있어")      # quick_answers.NO lists it for the LLM; it is this kind's now
QUICK_KINDS["arm"][0].extend(["팔 길이가 얼마야", "how long is your arm"])

# night 4: wordings the dev eval missed, at every level
for _kind, _texts in {
    "size": ["how wide is lumi", "how wide is the robot", "how wide is this robot", "how big is lumi", "루미 폭이 얼마예요", "로봇 폭이 몇이야"],
    "stairs": [s + e for s in ["계단도 올라가", "계단 올라가", "계단도 올라가실 수 있"] for e in ["니", "나요", "요", "", "노", "습니까", "세요"]],
    "grow": ["최대 몇 센티까지 커져", "최대 몇 센티까지 커져요", "제일 높이 몇 센티까지 올라가", "얼마나 높아질 수 있어요", "how tall can you get",
             "what's your tallest height", "몇 센티까지 늘어나요", "최대 높이가 몇이에요"],
    "navigation": ["are you self-driving", "are you autonomous", "is this robot autonomous", "do you drive yourself", "자율주행 로봇이에요",
                   "혼자 다닐 수 있어", "혼자 다니세요", "스스로 운전해요"],
    "software": ["is your code python", "are you programmed in python", "is lumi written in python", "파이썬으로 만들었어요", "코드 파이썬이야"],
    "detector": ["do you run yolo", "is it yolo", "do you use yolo for detection", "욜로 써요", "YOLO 돌려요", "물체 인식 YOLO야"],
    "touch": ["is it ok to touch the robot", "is it okay to touch lumi", "may people touch the robot", "are visitors allowed to touch you",
              "로봇 만져도 돼요", "루미 만져도 되나요", "이 로봇 만져도 됩니까"],
    "operator": ["who operates this robot", "who runs this robot", "who is in charge of this robot", "이 로봇 누가 운영해요", "이 로봇 관리자 누구예요"],
}.items():
    QUICK_KINDS[_kind][0].extend(_texts)

# night 4, round 2: kinds the train sets asked for (knowledge/lumi_about_en.md: the arm, the gripper, short moves)
QUICK_KINDS["paper_cup"] = (
    _ko(["종이컵 집을 수 있", "종이컵 잡을 수 있", "종이컵도 잡을 수 있", "종이컵도 집을 수 있", "종이컵 들 수 있", "종이컵 잡으실 수 있",
         "paper cup 잡을 수 있", "종이컵 잡을수있", "종이컵 집을수있"], CAN) +
    ["종이컵도 잡아", "종이컵 잡아요", "종이컵은 못 잡아", "종이컵은 안 돼요", "종이컵도 돼요", "종이컵 되나", "종이컵 잡을 줄 알아",
     "종이컵 집으면 찌그러져요", "종이컵 같은 거 잡을 수 있습니까", "종이컵은 어떻게 돼요", "종이컵 잡을 수 있는교",
     "can you grab a paper cup", "can you pick up a paper cup", "can you hold a paper cup", "are you able to hold paper cups",
     "can your gripper hold a paper cup", "what about paper cups", "do paper cups work", "can you take paper cups",
     "will a paper cup get crushed", "can u grab paper cups", "paper cup 잡을 수 있어요", "can you pick up paper cups too"],
    {"en": ["Not well: a paper cup is too soft, my fingers squeeze it flat. Firm cups and glasses about 6 to 9 cm wide are fine.",
            "A paper cup is too soft for my steel fingers, they squeeze it flat. I hold firm cups and glasses 6 to 9 cm wide."],
     "ko": ["종이컵은 너무 물러서 제 손가락이 눌러 찌그러뜨려요. 6에서 9cm 폭의 단단한 컵이나 유리잔은 잡을 수 있어요.",
            "종이컵은 부드러워서 눌려 버려요. 단단한 컵이나 유리잔은 6에서 9cm 폭까지 잡아요."]})
QUICK_KINDS["arm_weight"] = (
    _ko(["팔 무게가 얼마", "팔 무게 얼마", "팔은 무게가 얼마", "팔 자체 무게가 얼마", "팔 하나 무게가 얼마", "로봇 팔 무게가 얼마"],
        ["야", "예요", "에요", "니", "입니까", "인가요", "고", "여", "임", "나 돼요", "나 됩니까", "나 나가요"]) +
    ["팔 하나 몇 키로임", "팔 몇 킬로예요", "팔이 몇 킬로예요", "팔 몇 kg이야", "팔은 몇 kg입니까", "팔은 몇 킬로야", "팔 무게 몇 키로", "팔이 몇 킬로나 나가요", "팔 무게는요", "팔 얼마나 무거워요",
     "팔 무거워요", "팔 무게 아세요", "팔 무게가 어떻게 되십니까", "arm 무게 얼마야",
     "how heavy is your arm", "how much does your arm weigh", "what does the arm weigh", "what's the weight of your arm",
     "how heavy is the robot arm", "is your arm heavy", "arm weight?", "how many kilos is your arm"],
    {"en": ["My arm itself weighs 9.9 kg. It can lift up to 2 kg, the gripper included.",
            "The arm alone is 9.9 kg; with the gripper on it, it lifts up to 2 kg."],
     "ko": ["팔 자체 무게는 9.9kg이에요. 그리퍼를 포함해 2kg까지 들 수 있어요.",
            "팔만 9.9kg이에요. 그리퍼까지 합쳐 2kg까지 들어요."]})
QUICK_KINDS["short_move"] = (
    ["앞으로 가라 하면 최대 몇 미터 가", "앞으로 최대 몇 미터 갈 수 있어", "앞으로 최대 몇 미터 가요", "한 번에 몇 미터까지 가요",
     "한 번에 최대 몇 미터 움직여요", "앞으로 가라고 하면 얼마나 가", "직진은 최대 몇 미터예요", "최대 몇 미터까지 직진해요",
     "한 번에 얼마나 멀리 가세요", "앞으로 몇 미터까지 갈 수 있습니까", "앞뒤로 최대 몇 미터 가노", "forward 최대 몇 meter 가요",
     "앞으로 10미터 가라 하면 감", "앞으로 10미터 가라고 하면 가요", "뒤로 최대 몇 미터 가요",
     "how far can you move forward in one go", "what's the longest straight move you make", "how far will you go if i say move forward",
     "what's the farthest you drive straight", "how many meters can you move forward at once", "is there a limit to how far you move forward",
     "if i say go forward 10 meters, will you", "max distance for a forward move?"],
    {"en": ["A straight move forward or back is at most 3 metres at a time. For anything farther, name a place on my map and I drive there.",
            "At most 3 metres per straight move. Farther than that, I go to a named place on my map."],
     "ko": ["앞뒤로 곧장 가는 건 한 번에 최대 3미터예요. 더 먼 곳은 지도에 있는 장소 이름으로 말해 주시면 거기까지 가요.",
            "한 번에 곧장 가는 건 3미터까지예요. 그보다 멀면 지도의 장소로 가요."]})
QUICK_KINDS["llm_runtime"] = (
    ["what serves your language model", "what software serves your llm", "what software runs your llm", "do you use ollama",
     "how is your model served", "what program runs gemma", "is it ollama", "what runs gemma on you", "what serves gemma",
     "is gemma served with ollama", "do you run ollama",
     "언어 모델은 어떤 프로그램으로 돌려요", "언어 모델은 어떤 프로그램으로 돌리시나요", "언어 모델은 어떤 프로그램으로 구동합니까",
     "언어 모델 뭘로 돌려", "모델 돌리는 프로그램 뭐야", "언어 모델 돌리는 소프트웨어가 뭐예요", "젬마 돌리는 프로그램이 뭐야", "올라마 써요", "올라마 쓰니", "모델 서버 뭐 써요", "LLM 뭘로 돌려요", "젬마는 뭘로 돌려요", "모델 서빙 뭐로 해요"],
    {"en": ["Ollama serves my language model, Gemma 4, on my own NVIDIA Jetson Thor, without the cloud."],
     "ko": ["언어 모델 젬마 4는 올라마로 제 엔비디아 젯슨 토르에서 돌려요. 클라우드는 안 써요."]})
QUICK["dof"] = QUICK.get("dof", []) + [
    "너 몇 군데 움직여", "몇 군데 움직일 수 있어요", "몇 군데가 움직여요", "움직이는 데가 몇 군데예요", "몇 군데 움직이십니까", "어디 어디 움직여요",
    "how many parts of you move", "how many moving parts do you have", "how many joints do you have in total", "which parts of you can move"]
QUICK["battery_spec"] = QUICK.get("battery_spec", []) + [
    "배터리 뭐 들어 있어", "배터리 뭐 들었어요", "무슨 배터리 들어 있어요", "배터리 종류가 뭐예요", "어떤 배터리 써요", "배터리 뭐 쓰세요",
    "무슨 배터리 쓰노", "what battery is inside you", "what kind of battery is in you", "what battery do you use", "what battery powers you"]
QUICK["no"] += [
    "앞으로 3미터 가", "앞으로 10미터 가 줘", "앞으로 2미터 가 주세요", "뒤로 1미터 가", "move forward 5 meters", "go forward 2 meters",
    "drive 3 meters ahead", "종이컵 집어 줘", "종이컵 잡아 줘", "pick up the paper cup", "grab my paper cup", "종이컵 가져와",
    "팔 들어", "팔 내려", "raise your arm", "대통령 연세가 어떻게 됩니까", "대통령 몇 살이에요", "엄마 연세가 어떻게 되세요", "how old is the president",
    "오픈AI는 누가 이끌고 있습니까", "오픈AI CEO가 누구야", "who runs openai", "who leads openai"]
