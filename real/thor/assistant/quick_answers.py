"""Quick answers: frequent standalone questions about Lumi (name, age, who made it, height, battery life, languages,
AI model, robot or alive, hello) answered at once, without the LLM (lumi.Lumi._answer, after the rules, seeing and
status and before the LLM).

The question is matched by meaning with the embedding server (assistant/knowledge.embed, as assistant/intent_bank.py):
close enough to one kind and far enough from every other kind and from the "no" wordings (camera questions, commands,
company facts, follow-ups) -> one of that kind's answers. Every answer is a fact of knowledge/lumi_about_en.md or
brain.SYSTEM; keep them in step. Only a question of its own: in a talk it must name Lumi ("you", "너", "루미"), and a
fragment ("why?", "really?", "and you?", "how old?") always goes to the LLM, which has the talk before.
"What can you do?" and the battery level now are assistant/abilities.py's and assistant/battery.py's; "thanks" has
two meanings (understood / goodbye) and stays with the LLM.

    .venv/bin/python assistant/quick_answers.py "who made you?"     # the kind, the answer and the closest wordings
"""
import datetime
import pathlib
import random
import re
import sys
import time

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "quick_answers.npz"
SIM_MIN = 0.86          # the closest wording must be at least this similar (bge-m3 cosine) ...
MARGIN = 0.05           # ... and this much closer than the closest wording of any other kind (the "no" kind too)
MAX_WORDS = 12          # a longer sentence is a story or several questions: the LLM
SIM_AGREE = 0.80        # or: the AGREE_K closest wordings all of one kind, the closest at least this similar ...
MARGIN_AGREE = 0.06     # ... and this much closer than any other kind ("지금 몃 시야?": every near wording is the time)
AGREE_K = 3

# kind: (wordings, {"en": [answers], "ko": [answers]})
KINDS = {
    "name": ([
        "what's your name", "what is your name", "your name?", "what are you called", "what do they call you",
        "do you have a name", "tell me your name", "may i know your name", "what should i call you", "whats ur name",
        "wat is your name", "what's your name, robot", "name please", "what is the robot's name",
        "이름이 뭐야", "이름이 뭐예요", "이름이 어떻게 돼요", "너 이름 뭐야", "성함이 어떻게 되세요", "이름 알려 줘", "이름이 뭡니까",
        "넌 이름이 뭐니", "이름 있어요", "뭐라고 부르면 돼요", "니 이름 머야", "너 이름이 뭐꼬", "이름이 뭐당가", "네임이 뭐야",
        "your name 뭐야", "이 로봇 이름이 뭐예요",
    ], {"en": ["I'm Lumi.", "My name is Lumi.", "Lumi. Nice to meet you."],
        "ko": ["저는 루미예요.", "제 이름은 루미예요.", "루미라고 해요. 반가워요."]}),
    "name_meaning": ([
        "what does your name mean", "why are you called lumi", "where does the name lumi come from", "what does lumi mean",
        "meaning of your name", "why lumi", "who named you lumi", "루미가 무슨 뜻이야", "이름이 무슨 뜻이에요", "왜 이름이 루미예요",
        "루미라는 이름은 어디서 왔어요", "루미 뜻이 뭐야", "이름 의미가 뭐예요",
    ], {"en": ["My name comes from Lux, Latin for light, and mini, small and agile.",
               "Lumi is Lux, the Latin word for light, plus mini, for small and agile."],
        "ko": ["빛을 뜻하는 라틴어 룩스와, 작고 날렵하다는 미니에서 온 이름이에요.",
               "제 이름은 라틴어로 빛이라는 룩스와 작고 날렵하다는 미니를 합친 거예요."]}),
    "who": ([
        "who are you", "who are you?", "what are you", "what are you exactly", "introduce yourself", "tell me about yourself",
        "what kind of robot are you", "what is this robot", "what's this robot", "who is this robot", "what are you for",
        "what is your job", "what do you do here", "who r u", "hoo are you", "what is lumi", "who is lumi",
        "누구야", "넌 누구니", "누구세요", "당신은 누구예요", "너 뭐야", "자기소개 해 줘", "자기소개 좀 해 주세요", "소개해 주세요",
        "어떤 로봇이에요", "이 로봇은 뭐예요", "이건 무슨 로봇이야", "루미가 뭐야", "니 누고", "누구당가", "넌 뭐 하는 애야",
        "여기서 뭐 하는 로봇이에요", "who are you 너", "넌 who야",
    ], {"en": ["I'm Lumi, a mobile robot assistant developed by Cutshion Company.",
               "I'm Lumi, a robot assistant made by Cutshion Company. I can talk, see, drive around and use my arm.",
               "My name is Lumi. I'm a mobile robot assistant from Cutshion Company."],
        "ko": ["저는 루미예요. 쿳션이 개발한 모바일 로봇 어시스턴트예요.",
               "저는 쿳션이 만든 로봇 어시스턴트 루미예요. 대화하고, 보고, 움직이고, 팔도 쓸 수 있어요.",
               "루미라고 해요. 쿳션에서 개발한 모바일 로봇이에요."]}),
    "age": ([
        "how old are you", "what is your age", "what's your age", "how old r u", "how old is lumi", "when were you born",
        "when were you made", "when were you built", "how old is this robot", "are you old", "are you new", "your age?",
        "how many years old are you", "hau old are you",
        "몇 살이야", "몇 살이에요", "나이가 어떻게 돼요", "너 몇 살", "나이가 몇이야", "연세가 어떻게 되세요", "언제 태어났어",
        "언제 만들어졌어요", "이 로봇 몇 살이에요", "몇 살인교", "멫 살이여", "몇살", "나이 몇 살이야", "니 몇 살이고",
        "how old 너", "너 age가 몇이야",
    ], {"en": ["I'm 2 years old.", "I'm two years old.", "Two years old!"],
        "ko": ["저는 두 살이에요.", "두 살이에요.", "올해 두 살이에요."]}),
    "maker": ([
        "who made you", "who built you", "who created you", "who developed you", "who designed you", "who is your maker",
        "who programmed you", "which company made you", "what company made you", "what company are you from",
        "where are you from", "where do you come from", "who owns you", "who do you belong to", "who's your creator",
        "who mad you", "whoo made you", "made by who", "which company built this robot", "who makes this robot",
        "누가 만들었어", "누가 만들었어요", "누가 개발했어요", "누가 널 만들었어", "어느 회사에서 만들었어요", "어디서 만들었어요",
        "어느 회사 로봇이에요", "어디 회사 로봇이야", "만든 사람이 누구예요", "제작사가 어디예요", "어디서 왔어", "어디서 왔어요",
        "너 어디 소속이야", "누가 맹글었노", "누가 만들었당가", "who made 너", "누가 made 했어",
    ], {"en": ["I was developed by Cutshion Company.",
               "Cutshion Company made me. It's a robot company in Seoul.",
               "I'm from Cutshion Company, a Korean robot company in Seoul."],
        "ko": ["쿳션이 저를 개발했어요.", "주식회사 쿳션에서 만들었어요. 서울에 있는 로봇 회사예요.",
               "저는 쿳션이라는 한국 로봇 회사에서 왔어요."]}),
    "height": ([
        "how tall are you", "what's your height", "what is your height", "how tall is lumi", "how tall is this robot",
        "how high are you", "your height?", "hau tall are you", "how tall r u", "how tall can you get",
        "how tall are you in centimeters",
        "키가 몇이야", "키가 몇이에요", "키 얼마야", "키가 얼마나 돼요", "너 키 몇이야", "키 몇 센티예요", "이 로봇 키가 얼마예요",
        "키가 몇 센치고", "키 얼마나 크노", "얼마나 커요", "키 몇이에요", "your 키 몇이야",
    ], {"en": ["I'm 146 cm tall, and with my lift I can go up to 186 cm.",
               "146 centimetres. My lifting column can raise me by 40 cm, to 186 cm.",
               "I'm 146 cm tall; I can stretch up to 186 cm with my lift."],
        "ko": ["키는 146cm이고, 리프트로 186cm까지 올라가요.", "146센티미터예요. 리프트로 40cm 더 올라가서 186cm까지 돼요.",
               "저는 146cm예요. 리프트를 올리면 186cm까지 커져요."]}),
    "weight": ([
        "how heavy are you", "how much do you weigh", "what's your weight", "what is your weight", "how heavy is lumi",
        "how heavy is this robot", "are you heavy",
        "몸무게가 몇이야", "몸무게 얼마예요", "무게가 얼마나 돼요", "너 몇 킬로야", "몇 키로예요", "얼마나 무거워요", "이 로봇 무게가 얼마예요",
    ], {"en": ["I weigh about 96 kg.", "About 96 kilograms; my wheeled base alone is 50 kg."],
        "ko": ["저는 약 96kg이에요.", "무게는 약 96킬로그램이에요. 베이스만 50kg이에요."]}),
    "battery_life": ([
        "how long does your battery last", "how long can you run", "how long can you work on one charge",
        "how many hours does your battery last", "what's your battery life", "how long do you last on a charge",
        "how long can you go without charging", "battery life?", "how long can you work",
        "배터리 얼마나 가요", "배터리 몇 시간 가", "한 번 충전하면 얼마나 써요", "배터리 수명이 얼마나 돼요", "몇 시간 일할 수 있어요",
        "충전 한 번에 몇 시간 가요", "배터리 오래 가요", "배터리 얼마나 버텨",
    ], {"en": ["My battery lasts about 10 hours.", "About 10 hours on one charge.",
               "Around 10 hours: I have a 24-volt, 45 Ah lithium-ion battery."],
        "ko": ["배터리는 약 10시간 가요.", "한 번 충전하면 약 10시간 일할 수 있어요.", "약 10시간이에요. 24볼트 45Ah 리튬이온 배터리예요."]}),
    "languages": ([
        "what languages do you speak", "what languages can you speak", "which languages do you understand",
        "do you speak english", "do you speak korean", "can you speak korean", "can you speak english",
        "can you speak chinese", "do you speak japanese", "can you speak other languages", "what language do you speak",
        "how many languages do you speak", "do you understand english",
        "무슨 언어 할 수 있어", "어떤 언어 해요", "영어 할 줄 알아", "한국어 할 수 있어요", "몇 개 국어 해요", "중국어 할 줄 알아요",
        "일본어 할 수 있어", "영어도 돼요", "한국말 알아들어요", "외국어 할 줄 알아", "english 할 줄 알아", "korean 할 수 있어",
    ], {"en": ["I understand and speak English and Korean.", "English and Korean. I answer in the language you use.",
               "I speak English and Korean; other languages I don't understand yet."],
        "ko": ["영어와 한국어를 이해하고 말할 수 있어요.", "영어와 한국어요. 말씀하시는 언어로 대답해요.",
               "영어랑 한국어를 해요. 다른 언어는 아직 이해하지 못해요."]}),
    "chatgpt": ([
        "are you chatgpt", "do you use chatgpt", "are you connected to the cloud", "do you use the internet to think",
        "is this chatgpt", "are you using gpt", "you are chatgpt?", "챗gpt 써요", "챗지피티야", "gpt 쓰는 거야", "너 챗GPT 써",
        "클라우드에 연결돼 있어요", "챗gpt랑 연결돼 있어",
    ], {"en": ["No, I don't use ChatGPT or the cloud. I answer with Gemma 4, made by Google, on my own NVIDIA Jetson Thor.",
               "No. My language model is Gemma 4 by Google, and it runs on my own computer, not in the cloud."],
        "ko": ["아니요, 챗GPT나 클라우드는 쓰지 않아요. 구글이 만든 젬마 4로 제 젯슨 토르에서 직접 대답해요.",
               "아니요. 제 언어 모델은 구글의 젬마 4이고, 클라우드가 아니라 제 컴퓨터에서 돌아가요."]}),
    "model": ([
        "what ai do you use", "what model do you use", "which language model are you",
        "what is your ai model", "what's your brain", "what ai are you", "what llm do you run",
        "무슨 ai 써요", "어떤 모델 써요", "언어 모델이 뭐예요", "인공지능 뭐 써", "ai 모델이 뭐야",
    ], {"en": ["I answer with Gemma 4, a language model made by Google, served by Ollama on my own NVIDIA Jetson Thor.",
               "My language model is Gemma 4 by Google, served by Ollama, and I understand speech with Whisper; both run on my own NVIDIA Jetson Thor, without the cloud."],
        "ko": ["구글이 만든 언어 모델 젬마 4로 대답해요. 제 안의 엔비디아 젯슨 토르에서 올라마로 돌아가요.",
               "제 언어 모델은 구글의 젬마 4이고 올라마로 돌려요. 음성 인식은 위스퍼예요. 둘 다 클라우드 없이 제 젯슨 토르에서 돌아가요."]}),
    "robot": ([
        "are you a robot", "are you human", "are you alive", "are you real", "are you an ai", "are you a person",
        "is there a person inside", "is someone controlling you", "do you have feelings", "do you have emotions",
        "are you conscious", "is this a real robot", "are you a machine",
        "너 로봇이야", "로봇이에요", "사람이야", "살아 있어", "진짜 로봇이에요", "안에 사람 있어요", "누가 조종해요", "감정 있어",
        "감정이 있어요", "인공지능이야", "ai야", "기계예요", "의식 있어요",
    ], {"en": ["I'm a robot, not a living being: I understand speech and answer with AI running on my own computer.",
               "I'm a robot, not alive. I have no feelings or consciousness; my friendliness is how I was made to talk."],
        "ko": ["저는 로봇이에요. 살아 있는 건 아니고, 제 컴퓨터에서 돌아가는 AI로 말을 알아듣고 대답해요.",
               "저는 로봇이에요. 감정이나 의식은 없고, 친절하게 말하도록 만들어졌어요."]}),
    "speed": ([
        "how fast can you go", "how fast do you move", "what's your speed", "what is your top speed", "how fast are you",
        "how quick can you drive", "what's your max speed",
        "얼마나 빨라요", "속도가 얼마예요", "얼마나 빨리 가요", "최고 속도가 몇이야", "몇 키로로 달려요", "속도 얼마나 나와",
    ], {"en": ["I normally drive at 0.6 metres per second, at most 1.2.",
               "0.6 m per second normally, up to 1.2 m per second."],
        "ko": ["보통 초속 0.6m로 가고, 최대 초속 1.2m예요.", "평소엔 초속 0.6미터, 가장 빠르면 초속 1.2미터예요."]}),
    "hello": ([
        "hello", "hi", "hi there", "hello lumi", "hi lumi", "hey there", "good morning", "good afternoon", "good evening",
        "nice to meet you", "hello robot", "howdy", "yo", "hiya", "helo", "hallo",
        "안녕", "안녕하세요", "루미 안녕하세요", "반가워", "반가워요", "만나서 반가워요", "처음 뵙겠습니다", "좋은 아침이에요", "하이",
        "헬로", "안뇽", "안녕하십니까", "하이 루미",
    ], {"en": ["Hello! Nice to meet you.", "Hi there!", "Hello! I'm Lumi."],
        "ko": ["안녕하세요! 반가워요.", "안녕하세요!", "안녕하세요, 저는 루미예요."]}),
    "how_are_you": ([
        "how are you", "how are you doing", "how's it going", "how are you today", "are you okay", "how do you feel",
        "what's up", "how have you been",
        "잘 지내", "잘 지냈어요", "기분 어때", "오늘 기분 어때요", "괜찮아요", "요즘 어때", "어떻게 지내요",
    ], {"en": ["I'm a robot, so I have no feelings, but everything is running fine. Thanks for asking!",
               "All good here: as a robot I don't feel things, but my systems are running well."],
        "ko": ["저는 로봇이라 감정은 없지만, 다 잘 돌아가고 있어요. 물어봐 주셔서 고마워요!",
               "로봇이라 기분은 없지만, 아주 잘 돌아가고 있어요."]}),
    # the clock: {time} / {date} / {day} are filled in when said (answer)
    "time_now": ([
        "what time is it", "what's the time", "what is the time now", "do you know the time", "what time is it now",
        "could you tell me the time", "have you got the time", "time please", "what time've we got", "wat time is it",
        "what's the time right now", "tell me the time", "the time?", "what o'clock is it", "is it noon yet",
        "몇 시야", "지금 몇 시야", "몇 시예요", "지금 몇 시예요", "지금 몇 시입니까", "몇 시인지 알려 줘", "시간 좀 알려 줘",
        "지금 시간 몇 시야", "현재 시각이 어떻게 돼요", "몇 시고", "지금 몇 시고", "몇 시여", "멫 시야", "몃 시야", "시간이 몇 시예요",
        "타임 좀 알려 줘", "what time 이야", "지금 몇 시쯤 됐어", "벌써 몇 시야",
    ], {"en": ["It's {time}.", "It's {time} now."], "ko": ["지금 {time}이에요.", "{time}이에요."]}),
    "date_today": ([
        "what's the date today", "what is today's date", "what's the date", "what date is it", "what date is it today",
        "which date is today", "today's date please", "do you know the date", "what's today's date", "what day of the month is it",
        "what's the date today robot", "date please",
        "오늘 며칠이야", "오늘 며칠이에요", "오늘 날짜가 뭐야", "오늘 날짜 알려 줘", "오늘이 며칠입니까", "오늘 날짜가 어떻게 돼요",
        "며칠이야 오늘", "오늘 몇 월 며칠이야", "오늘 몇 월 며칠이에요", "날짜 좀 알려 주세요", "오늘 며칠이고", "오늘 메칠이여",
        "today 며칠이야", "오늘 date가 뭐야", "날짜 알려 줘", "오늘이 며칠이죠",
        "what month is it", "which month is it", "what month are we in", "몇 월이야", "지금 몇 월이에요", "이번 달이 몇 월이야",
        # the day of the week: the same answer (the date says the day)
        "what day is it", "what day is it today", "which day of the week is it", "what day of the week is it",
        "what's today", "is it friday today", "what weekday is it", "do you know what day it is", "today is what day",
        "오늘 무슨 요일이야", "오늘 무슨 요일이에요", "무슨 요일이야", "오늘 요일이 뭐야", "오늘이 무슨 요일입니까", "요일 알려 줘",
        "오늘 뭔 요일이고", "오늘 무슨 요일이여", "today 무슨 요일이야", "오늘 금요일 맞아",
    ], {"en": ["Today is {date}.", "It's {date} today."], "ko": ["오늘은 {date}이에요.", "{date}이에요."]}),
    "days_to_christmas": ([
        "how many days until christmas", "how many days are left before christmas", "how long until christmas",
        "days left to christmas", "when is christmas from now", "is christmas soon", "christmas how many days left",
        "how many sleeps till christmas", "크리스마스까지 며칠 남았어", "크리스마스까지 며칠 남았어요", "크리스마스 얼마나 남았어",
        "크리스마스 언제 와", "성탄절까지 며칠이야", "크리스마스 디데이 알려 줘", "크리스마스까지 몇 일 남았어요", "산타 언제 와",
    ], {"en": ["Christmas is in {xmas} days.", "{xmas} days until Christmas."],
        "ko": ["크리스마스까지 {xmas}일 남았어요.", "{xmas}일 뒤가 크리스마스예요."]}),
}
KO_DAYS = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]


def clock_words(line, lang, now=None):
    """The answer line with {time} / {date} / {day} filled from the clock (this machine's local time)."""
    lt = time.localtime(now)
    h, m = lt.tm_hour, lt.tm_min
    if lang == "ko":
        words = {"time": f"{'오전' if h < 12 else '오후'} {h % 12 or 12}시" + (f" {m}분" if m else ""),
                 "date": f"{lt.tm_mon}월 {lt.tm_mday}일 {KO_DAYS[lt.tm_wday]}", "day": KO_DAYS[lt.tm_wday]}
    else:
        words = {"time": f"{h % 12 or 12}:{m:02d} {'am' if h < 12 else 'pm'}",
                 "date": time.strftime("%A, %B ", lt) + str(lt.tm_mday), "day": time.strftime("%A", lt)}
    y = lt.tm_year + (1 if (lt.tm_mon, lt.tm_mday) > (12, 25) else 0)
    words["xmas"] = (datetime.date(y, 12, 25) - datetime.date(lt.tm_year, lt.tm_mon, lt.tm_mday)).days
    return line.format(**words) if "{" in line else line

NO = [
    # the cameras: assistant/seeing.py's or the LLM's
    "can you see me", "do you see me", "what do you see", "what am i holding", "what am i wearing", "how many people do you see",
    "what colour is my shirt", "how old do i look", "how tall am i", "who am i", "do you know me", "do you remember me",
    "what's in front of you", "can you see the cup", "is there someone behind me", "how old am i",
    "나 보여", "내가 보여요", "뭐 보여", "내 옷 무슨 색이야", "나 몇 살 같아", "내 키 몇이야", "나 누군지 알아", "앞에 뭐 있어",
    "사람 몇 명 보여", "카메라로 뭐 보여요",
    # commands and requests
    "come here", "follow me", "wave", "wave at me", "go to the stage", "sing a song", "dance for me", "turn around",
    "look at me", "tell me a joke", "say hello to my son", "introduce me to cutshion", "take a picture",
    "이리 와", "따라와", "손 흔들어 줘", "노래 불러 줘", "춤 춰 봐", "농담 해 줘", "우리 애한테 인사해 줘",
    # abilities: the LLM (or abilities.py)
    "what can you do", "can you dance", "can you fly", "can you climb stairs", "can you lift 5 kg", "how much can you lift",
    "how far can you reach", "can you open doors", "can you pick up a cup", "how long is your arm", "can you grow taller",
    "뭐 할 수 있어", "춤 출 수 있어", "계단 올라갈 수 있어", "몇 킬로까지 들 수 있어", "팔 길이가 얼마야", "문 열 수 있어",
    # the company and other things, not Lumi
    "what is cutshion", "tell me about cutshion", "how old is cutshion", "when was cutshion founded", "how old is the company",
    "how many people work at cutshion", "how many employees does the company have", "who is the ceo", "where is the company",
    "how much do you cost", "what's your price", "how long does charging take", "how much battery is left",
    "who made the barista robot", "who made your arm", "who made your gripper", "how tall is your arm",
    "how heavy is your arm", "how heavy can the items be", "how heavy a thing can you hold", "how heavy can things be",
    "얼마나 무거운 거 들 수 있어", "물건 무게는 얼마까지 돼요", "what's the name of the ceo", "what's the company's name", "what's this event called",
    "what's the name of this place", "what is this booth", "who made this booth",
    "쿳션은 뭐 하는 회사야", "회사 몇 년 됐어요", "직원이 몇 명이에요", "대표가 누구예요", "회사 어디 있어요", "얼마예요", "가격이 얼마예요",
    "충전 얼마나 걸려요", "배터리 몇 퍼센트 남았어", "팔은 누가 만들었어요", "그리퍼 무게가 얼마예요", "이 행사 이름이 뭐예요",
    "여기가 어디예요", "대표 이름이 뭐예요", "너 얼마야", "how much are you", "is cutshion an american company",
    "로봇 미국 회사 맞아요", "중국 회사예요", "is your company chinese",
    # follow-ups and fragments: the LLM with the talk before
    "why", "really", "and you", "how come", "are you sure", "what about you", "and the arm", "who", "what do you mean", "tell me more", "which one", "why lumi?", "seriously?",
    "왜", "진짜", "너는", "그럼 너는", "확실해", "팔은요", "누가", "무슨 뜻이야", "더 알려 줘",
    # praise and remarks: the LLM
    "you're cool", "you look cute", "you're so tall", "nice robot", "what a cool robot", "you're amazing", "i like you",
    "로봇 정말 멋있어요", "귀엽다", "멋있다", "키 크다", "로봇 신기하네요", "너 좋아", "대단하다",
    # the weather, the time, closings
    "what's the weather", "thanks", "thank you", "bye", "okay", "i see",
    "날씨 어때", "고마워", "감사합니다", "잘 가", "알겠어요", "그렇구나",
]

# never by meaning: the cameras, the visitor about themselves, a doubt or a fragment of the talk before

from assistant import bank_words                                   # more wordings / kinds: assistant/bank_words/*.py
for _m in bank_words.modules():
    for _k, (_t, _a) in getattr(_m, "QUICK_KINDS", {}).items():
        KINDS.setdefault(_k, ([], _a))[0].extend(_t)
for _k, _t in bank_words.merged("QUICK").items():
    (NO if _k == "no" else KINDS[_k][0]).extend(_t)
_said = {t for texts, _ in KINDS.values() for t in texts}
NO = [t for t in NO if t not in _said]                              # a wording listed for a kind is that kind's

CAMERA = re.compile(r"\b(?:see|seeing|saw|look(?:s|ing)?|watch|camera|wearing|holding|in front of|behind|colou?r|"
                    r"recogni[sz]e|remember)\b|보여|보이|보니|(?<!해 )(?<!해)(?<!쭤 )(?<!쭤)(?<!여쭈어 )봐(?!도 ?(?:돼|되|될|괜찮))|봤|입었|들고|색|카메라|앞에|뒤에|알아봐|기억", re.I)
ABOUT_ME = re.compile(r"\b(?:(?<!can )(?<!could )(?<!may )i(?! (?:call|address) you\b)(?! (?:talk|speak|chat) (?:to|with) you\b)|i'm|am i|my|"
                      r"(?<!tell )(?<!give )(?<!let )(?<!show )me|mine)\b|(?:^|\s)(?:나|내|제|저|난|전)(?:는|가|를|의)?\s", re.I)
FRAGMENT = re.compile(r"^\W*(?:and|so|but|then|or|also|why|really|seriously|wait|what about|how about|how come|are you sure)\b|"
                      r"^\W*(?:그럼|그러면|그리고|근데|그런데|그래서|아니|왜|진짜|정말|확실|설마|또)|"
                      r"\b(?:that|(?<!is )(?<!was )(?<!is it )(?<!how's )(?<!how is )it(?! is (?:now|today))|they|them|"
                      r"(?<!hello )(?<!hi )(?<!hey )(?<!is )(?<!are )there(?! (?:is|are)\b)|this one)\b|"
                      r"그거|그건|거기|그분|그 회사|걔", re.I)   # not the clock's "it": "what day is it?"
OTHER = re.compile(r"\b(?:lift|carry|hold|items?|(?<!this )things?|stuff|price|cost)\b|들 ?수|(?<!만)(?<!알아)(?<!뭐 )들어|물건|"
                   r"^(?!.*(?:키|무게|체중|신장|속도|시간|나이|높이|길이|크기)).*얼마(?:야|예요)|"
                   r"맞(?:아|지|죠|나|습니까)|아니(?:야|에요|죠)", re.I)   # what it can hold, the price, a check: the LLM
SEVERAL = re.compile(r"\band\b(?!\s+(?:built|made|\w+ed)\s+(?:you|lumi|this robot)\b)|\bthen\b|그리고|[?？].+\S|하고\s|랑\s|"
                     r"[가-힣](?<![최광참사창공경재원라])(?<!그리)고\s+(?!싶|있|계)", re.I)   # "고개 숙이고 몇 시야?", "보고 시간 알려 줘"
EVENT_TIME = re.compile(r"\b(?:what time|what day|which day|what date) (?:does|do|did|will|is|are|was|were|should|can)\b"
                        r"(?!\s+(?:it|today)\b)|몇 ?시(?:에|부터|까지|쯤에)|며칠(?:에|까지|부터)|무슨 요일(?:에|까지|부터)|"
                        r"\b(?:open|close)\b(?!\s+(?:a|the|my|your|this|that|doors?)\b)|\b(?:start|end|begin|finish)\b|열어요|닫아요|시작|끝나", re.I)   # an event's time: the LLM
NAMES_LUMI = re.compile(r"\b(?:you|your|yourself|u|ur|lumi)\b|(?:^|\s)(?:너|넌|니|네|당신|루미|본인|자기)", re.I)

_bank = None
_named = None        # (kind names, int code per bank row) for intent_bank._top


def examples():
    """[(text, kind)] of every wording."""
    return [(t, k) for k, (texts, _) in KINDS.items() for t in texts] + [(t, "no") for t in NO]


def _load():
    """(vectors, kinds) of the bank; embeddings kept per wording in the cache (bank_words.vectors)."""
    global _bank
    if _bank is None:
        from assistant import bank_words
        ex = examples()
        _bank = (bank_words.vectors([t for t, _ in ex], CACHE), np.array([k for _, k in ex]))
    return _bank


ASKING = re.compile(r"^\W*(?:(?:hang on|wait|okay|ok|so|um+|uh+|hey|excuse me|sorry|just out of curiosity|out of curiosity|"
                    r"i(?:'m| am) curious|quick question|one question|let me ask(?: (?:it|you|him|her))?|i bet (?:it'?s|you'?re) \w+|"
                    r"(?:may|can|could|might) i (?:ask|know)(?: you)?|i(?:'d| would) like to know|i want(?:ed)? to (?:ask|know)|"
                    r"i wonder|do you mind (?:telling me|if i ask)|(?:(?:can|could|would|will) you )?tell me|might i trouble you for|could i trouble you for|잠깐(?:만)?|저기(?:요|유|예)?|이보게|자네|보소|"
                    r"야야|궁금한 ?게 있는데(?:요)?|하나 여쭤봐도 될까요\??|여쭤봐도 될까요\??|궁금한데(?:요)?|궁금해서(?:요)?|"
                    r"하나 물어봐도 (?:돼|될까)요?|여쭤봐도 될까요|물어볼게(?:요)?|질문(?: 하나)?(?: 있어요| 있는데요?)?)"
                    r"\b[\s,.!?~:-]*)+", re.I)
    # "May I ask your age?", "Hang on, let me ask it. What's your name?", "궁금한데, 몇 살이에요?": the question after


def _core(text):
    from assistant import brain
    t = ASKING.sub("", brain.CALLING.sub("", brain.unfill(text or "")).strip()).strip() or text or ""
    if not re.search(r"\b(?:is|was|name|named|called)\s+lumi\W*$", t, re.I):   # the subject: "How wide is Lumi?"
        t = re.sub(r"[\s,]*(?:lumi|루미야|루미)?[\s,.!?~]*$", "", t, flags=re.I).strip()
    if re.fullmatch(r"(?:무슨|뭔|무엇의?) ?뜻\S*", t) and "루미" in (text or ""):
        t = "루미 " + t                                 # "루미 무슨 뜻이에요?": what the name means
    t = re.sub(r"얼만가$", "얼마예요", re.sub(r"(?<=[가-힣])는가$", "나요", re.sub(r"(?<=[가-힣])인가$", "인가요", t)))
    return t or (text or "").strip(" ,.!?~")                # 하게체 questions ("키 얼만가", "얼마나 되는가") as 해요체


def guarded(text, history=()):
    """Why these words are not a quick answer's (the LLM's or another reader's), or None."""
    from assistant import brain
    t = ASKING.sub("", brain.unfill((text or "").strip())).strip() or (text or "").strip()   # "what time is, uh, it?"
    if not t or len(t.split()) > MAX_WORDS:
        return "length"
    if re.search(r"\b(?:good ?bye|bye|see you|farewell)\b|잘 ?가|안녕히|다음에 봐", t, re.I):
        return "closing"                               # "goodbye" is never a hello
    if CAMERA.search(t):
        return "camera"
    if ABOUT_ME.search(t):
        return "about the visitor"
    lead = re.match(r"^\W*(?:and|so|but|okay so|then)\W+", t, re.I)
    if lead and len(t[lead.end():].split()) >= 3 and NAMES_LUMI.search(t[lead.end():]):
        t = t[lead.end():]                             # "and your name is?", "so who are you?": a whole question
    why = re.match(r"^\W*(?:why|왜)\s+", t, re.I)       # "why is your name Lumi?", "왜 루미라고 불러?": a whole question
    whole_why = why and len(t[why.end():].split()) >= 2 and NAMES_LUMI.search(t[why.end():]) and \
        not FRAGMENT.search(t[why.end():])
    if FRAGMENT.search(t) and not whole_why:
        return "fragment"
    if SEVERAL.search(t):
        return "several"
    if OTHER.search(t):
        return "other"
    if EVENT_TIME.search(t) and not re.search(r"\bwhen did\b", t, re.I):   # "when did Cutshion start?": a founding
        return "event time"
    if history and not NAMES_LUMI.search(t):
        return "in a talk, not naming Lumi"            # "how old?" / "몇 살이에요?" after the company: about that
    return None


def kind_of(text, history=()):
    """The kind of question, when sure; else None."""
    if guarded(text, history):
        return None
    from assistant import knowledge
    vecs, kinds = _load()
    try:
        q = knowledge.embed([_core(text)])[0]
    except OSError as e:                               # no embedding server: the LLM answers
        print(f"quick answers: {e}")
        return None
    from assistant import intent_bank
    global _named
    if _named is None:
        names, codes = np.unique(kinds, return_inverse=True)
        _named = ([str(n) for n in names], codes)
    best, top, margin, agree, _ = intent_bank._top(vecs @ q, _named, k=AGREE_K)
    sure = top >= SIM_MIN and margin >= MARGIN or agree and top >= SIM_AGREE and margin >= MARGIN_AGREE
    if best == "no" or not sure:
        return None
    if best == "hello" and history:
        return None                                    # hello in the middle of a talk: the LLM
    return best


_last = {}


def answer(text, lang="en", history=()):
    """The spoken answer when `text` is a standalone question this module answers, else None. Never the same line
    twice in a row for a kind."""
    kind = kind_of(text, history)
    if kind is None:
        return None
    lines = KINDS[kind][1]["ko" if lang == "ko" else "en"]
    choices = [x for x in lines if x != _last.get(kind)] or lines
    _last[kind] = random.choice(choices)
    return clock_words(_last[kind], lang)


if __name__ == "__main__":
    import time
    for said in sys.argv[1:]:
        t0 = time.time()
        got = answer(said, "ko" if re.search(r"[가-힣]", said) else "en")
        print(f"{said} | guard: {guarded(said)} | kind: {kind_of(said)} | {got} ({time.time() - t0:.3f} s)")
        from assistant import knowledge
        vecs, kinds = _load()
        sims = vecs @ knowledge.embed([_core(said)])[0]
        texts = [t for t, _ in examples()]
        for i in np.argsort(-sims)[:4]:
            print(f"   {sims[i]:.3f} {kinds[i]:12} {texts[i]}")
