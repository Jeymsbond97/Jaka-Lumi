"""Example readings of words that hold command words: which are orders to Lumi now and which are only talk.

EXAMPLES = [(category, lang, said, reply, action)]; talk_examples.pick(said, lang, k, bank=...) picks the closest.
- action: the ACTION line Lumi writes for it (brain.ACTIONS_STREAM), "none" for talk.
- reply: what Lumi says, spoken style, short; Korean always polite.
brain._examples shows the closest ones with their action, so the model sees the same words read as an order and as
talk side by side. Kinds: an order now vs a plan between people, narration, a quote, a condition or later time, a
hypothetical, an ability question, "don't X", words to someone else, an announcement; amounts and directions
(Korean numbers, Konglish 레프트 = left, a number without a unit is asked); the hand while holding.

    python assistant/action_examples.py                 # self-check
    python assistant/action_examples.py "위 보지 마"     # show what pick() returns
"""
import re
import sys

_BANK = {
    "order_or_talk": {
        "en": [
            ("Turn left.", "turn left 90", "Okay, turning left."),
            ("Turn left at the corner, then it's the second door.", "none", "Got it, second door after the corner."),
            ("My friend told me to turn left here.", "none", "Then left it is for you two. Enjoy!"),
            ("Look up.", "look up", "Okay, looking up."),
            ("Don't look up.", "none", "Okay, I'll keep my head where it is."),
            ("Please don't follow me.", "none", "Alright, I'll stay right here."),
            ("You don't have to come here, I'm fine.", "none", "Okay, I'll stay where I am."),
            ("Don't wave, it's embarrassing.", "none", "Haha, okay, no waving."),
            ("Never go back to the charger while I'm talking.", "none", "Okay, I'll stay here while we talk."),
            ("Let's go to the cafe after this.", "none", "Sounds like a nice plan. Enjoy the coffee!"),
            ("We should check out the meeting room later.", "none", "Good idea. Have fun looking around."),
            ("Shall we go to the stage now?", "none", "Have fun at the stage!"),
            ("I went forward two metres and bumped into a chair.", "none", "Ouch, I hope you're okay."),
            ("Yesterday a robot followed me all the way to the exit.", "none", "Ha, it must have liked you."),
            ("The sign says turn right for the exit.", "none", "Then the exit is to the right."),
            ("He said come here, but I'm busy.", "none", "Then maybe tell him you'll come later."),
            ("If I clap, come to me.", "none", "Okay, just tell me when you want me to come."),
            ("When the talk ends, follow me to the booth.", "none", "Sure, ask me when the talk is over."),
            ("Imagine you turned around right now, what would you see?", "none", "Probably more visitors and a wall."),
            ("What would happen if you drove into a wall?", "none", "I'd stop first: my lidar sees the wall."),
            ("Are you able to turn all the way around?", "none", "Yes, I can turn on the spot, all the way around."),
            ("Do robots like you know how to wave?", "none", "I do, I can wave with my arm."),
            ("Jake, move a bit left so I can take a photo.", "none", "Smile for the photo!"),
            ("Mom, come look, it talks!", "none", "Hello! Yes, I talk."),
            ("Everyone, please come to the stage at three.", "none", "Thanks for the announcement."),
            ("Moving forward, our team will grow a lot.", "none", "That sounds exciting."),
            ("I'm going to the stage now.", "none", "Enjoy the show!"),
            ("Can I follow you around?", "none", "Sure, feel free to walk with me."),
            ("The guide told us to wait here.", "none", "Then let's wait here together."),
            ("Come here please.", "come", "Okay, I'm coming to you."),
            ("Okay, now wave at me.", "wave", "Sure, here's a wave!"),
            ("Follow me, I'll show you the booth.", "follow", "Okay, I'll follow you."),
            ("Raise yourself up a bit.", "lift up small", "Okay, going up a little."),
            ("Let's go to the cafe after this.", "none", "Sounds good, enjoy the coffee!"),
            ("I should turn around and go back to my booth.", "none", "Okay, good luck at your booth."),
            ("Turn left and you'll see the restrooms.", "none", "Thanks, good to know."),
            ("Look, it's moving its head!", "none", "Yes, I can turn my head."),
            ("Go on, tell me more.", "none", "Sure, what would you like to know more about?"),
            ("Go to p2, never mind, stay here.", "none", "Okay, I'll stay here."),
            ("Give me a second to think.", "none", "Take your time."),
            ("I'm going to look up the address later.", "none", "Good idea."),
            ("After lunch, come to the stage.", "none", "Okay, tell me after lunch and I'll come."),
            ("Once the show starts, wave at everyone.", "none", "Sure, tell me when it starts."),
        ],
        "ko": [
            ("왼쪽으로 돌아.", "turn left 90", "네, 왼쪽으로 돌게요."),
            ("위 보지 마.", "none", "네, 고개 그대로 둘게요."),
            ("따라오지 마세요.", "none", "네, 여기 있을게요."),
            ("손 흔들지 마.", "none", "네, 안 흔들게요."),
            ("이리 안 와도 됩니다.", "none", "네, 여기 그대로 있을게요."),
            ("우리 점심 먹고 나서 회의실 가자.", "none", "좋은 계획이네요. 맛있게 드세요."),
            ("이따 커피 마시러 가요.", "none", "좋아요, 커피 맛있게 드세요."),
            ("우리 저기 들렀다가 무대 쪽으로 갈까?", "none", "재미있게 구경하세요."),
            ("친구가 여기서 왼쪽으로 돌라고 했어.", "none", "그럼 왼쪽으로 가시면 되겠네요."),
            ("아까 로봇이 뒤로 가더라.", "none", "아마 길을 비켜 주려고 했나 봐요."),
            ("표지판에 오른쪽으로 가라고 써 있네요.", "none", "그럼 출구는 오른쪽이겠네요."),
            ("내가 손 들면 따라와.", "none", "네, 그때 말씀해 주세요."),
            ("발표 끝나면 이쪽으로 와 줘.", "none", "네, 끝나고 불러 주세요."),
            ("만약에 네가 뒤로 돌면 뭐가 보여?", "none", "아마 다른 방문객들이 보일 거예요."),
            ("고개 돌릴 줄 알아?", "none", "네, 고개를 좌우로 돌릴 수 있어요."),
            ("민수야, 이쪽으로 좀 와 봐.", "none", "민수 님, 안녕하세요!"),
            ("여러분, 세 시에 무대 앞으로 모여 주십시오.", "none", "안내 감사합니다."),
            ("앞으로 잘 부탁합니다.", "none", "저도 잘 부탁드려요."),
            ("선생님이 뒤로 물러나래.", "none", "그럼 조금 뒤로 물러서시면 되겠네요."),
            ("나 이제 무대 쪽으로 가려고.", "none", "네, 즐거운 시간 보내세요."),
            ("제가 따라가도 돼요?", "none", "그럼요, 편하게 구경하세요."),
            ("고개 들어 봐.", "look up", "네, 위를 볼게요."),
            ("이리 와 주세요.", "come", "네, 갈게요."),
            ("나 따라와.", "follow", "네, 따라갈게요."),
            ("손 흔들어 주실래요?", "wave", "네, 손 흔들게요!"),
            ("점심 먹고 나서 p3로 가.", "none", "네, 점심 드시고 말씀해 주세요."),
            ("우리 회의실 들렀다가 무대 가자.", "none", "좋아요, 재미있게 구경하세요."),
            ("엄마가 오른쪽으로 가래.", "none", "그럼 오른쪽으로 가시면 되겠네요."),
            ("저 로봇은 아까 앞으로 가던데.", "none", "다른 로봇도 바쁜가 봐요."),
            ("나 내 말 따라 해 봐.", "none", "네, 말씀해 주시면 따라 말해 볼게요."),
            ("회의 끝나고 나서 홈으로 가.", "none", "네, 회의 끝나면 말씀해 주세요."),
            ("쇼 시작하면 손 흔들어 주세요.", "none", "네, 시작할 때 말씀해 주세요."),
            ("p1로 가, 아니 됐어, 그냥 있어.", "none", "네, 여기 있을게요."),
            ("잠깐만 시간 좀 줘.", "none", "네, 천천히 하세요."),
            ("돌아서 가면 화장실이 있다고 하더라고요.", "none", "그렇군요, 가 보세요."),
        ],
    },
    "closing": {        # thanks / okay / that's it: the end only when the visitor is done; a question or a task goes on
        "en": [
            ("Thanks, that's all I needed.", "end", "Glad I could help. Enjoy your visit!"),
            ("Okay, thank you, I'll be going now.", "end", "Take care, see you around!"),
            ("Thanks! And where can I charge my phone?", "none", "I'm not sure about that here; a staff member can tell you."),
            ("Thanks. So how heavy are you?", "none", "About 96 kg in all."),
            ("Okay thanks, now turn left.", "turn left 90", "Okay, turning left."),
            ("Thanks, one more question.", "none", "Sure, go ahead."),
            ("Thank you so much for the cup!", "none", "You're welcome, enjoy it."),
            ("Thanks for bringing it.", "none", "My pleasure."),
            ("Okay, got it.", "none", "Great."),
            ("Okay.", "none", "Alright."),
            ("Nah, I'm good. Thanks!", "end", "Okay, have a nice day!"),
            ("That's everything, thanks Lumi.", "end", "You're welcome. Bye for now!"),
            ("Thanks, that was interesting. Why is it so slow, though?", "none", "I drive among people, so I keep it slow to be safe."),
            ("Thanks for the answer, I'll ask my friend now.", "none", "Sure, take your time."),
        ],
        "ko": [
            ("고마워, 이제 됐어.", "end", "네, 즐거운 시간 보내세요!"),
            ("감사합니다. 이만 가 보겠습니다.", "end", "네, 안녕히 가세요!"),
            ("고마워요. 근데 화장실은 어디예요?", "none", "그건 잘 모르겠어요. 직원분께 여쭤봐 주세요."),
            ("고마워. 그럼 몇 살이야?", "none", "저는 두 살이에요."),
            ("알겠어, 고마워. 이제 왼쪽으로 돌아.", "turn left 90", "네, 왼쪽으로 돌게요."),
            ("감사합니다. 하나만 더 여쭤봐도 됩니까?", "none", "네, 물어보세요."),
            ("컵 갖다줘서 고마워요!", "none", "천만에요, 맛있게 드세요."),
            ("알겠어요.", "none", "네, 좋아요."),
            ("오케이.", "none", "좋아요."),
            ("아뇨, 없어요. 감사합니다.", "end", "네, 좋은 하루 보내세요!"),
            ("됐어요, 궁금한 거 다 물어봤어요.", "end", "네, 반가웠어요. 안녕히 가세요!"),
            ("고마워. 근데 왜 그렇게 느려?", "none", "사람들 사이를 다니니까 안전하려고 천천히 다녀요."),
            ("고마워요, 친구 데려올게요.", "none", "네, 기다릴게요."),
            ("됐어, 그만 물어볼게. 잘 있어.", "end", "네, 안녕히 가세요!"),
        ],
    },
    "amount_direction": {
        "en": [
            ("Turn right forty-five degrees.", "turn right 45", "Okay, turning right 45 degrees."),
            ("Go forward one and a half metres.", "move forward 1.5", "Okay, 1.5 metres forward."),
            ("Back up fifty centimetres.", "move back 0.5", "Okay, half a metre back."),
            ("Go forward two.", "none", "Two metres? Please tell me how far with the unit."),
            ("Turn left thirty.", "turn left 30", "Okay, 30 degrees to the left."),
            ("Move back twenty.", "none", "Twenty centimetres or metres? Please say the unit."),
            ("Move left a little.", "move left 0.5", "Okay, a little to the left."),
            ("Look left thirty degrees.", "look left 30", "Okay, looking left."),
            ("Move forward ten metres.", "none", "I can move at most 3 metres at a time by voice."),
        ],
        "ko": [
            ("레프트로 돌아.", "turn left 90", "네, 왼쪽으로 돌게요."),
            ("라이트로 마흔다섯 도 돌아 주세요.", "turn right 45", "네, 오른쪽으로 45도 돌게요."),
            ("고개 레프트로 삼십 도.", "look left 30", "네, 왼쪽으로 30도 볼게요."),
            ("리프트 올려.", "lift up", "네, 몸을 올릴게요."),
            ("오른쪽으로 사십오 도 돌아.", "turn right 45", "네, 오른쪽으로 45도 돌게요."),
            ("앞으로 일 미터 반 가.", "move forward 1.5", "네, 앞으로 1.5미터 갈게요."),
            ("오십 센티 뒤로 가 주세요.", "move back 0.5", "네, 뒤로 50센티 갈게요."),
            ("앞으로 둘 가.", "none", "몇 미터인지 단위와 함께 말씀해 주세요."),
            ("왼쪽으로 삼십 돌아.", "turn left 30", "네, 왼쪽으로 30도 돌게요."),
            ("뒤로 이십 가 줘요.", "none", "20센티인가요, 20미터인가요? 단위를 말씀해 주세요."),
            ("뒤로 조금만 가 주십시오.", "move back 0.5", "네, 뒤로 조금 갈게요."),
            ("앞으로 열 미터 가.", "none", "말로는 한 번에 3미터까지만 움직일 수 있어요."),
            ("한 바퀴 돌아.", "turn left 360", "네, 한 바퀴 돌게요."),
        ],
    },
    "hand": {
        "en": [
            ("Give it to me.", "give", "Here you go."),
            ("Can I have the cup now?", "give", "Sure, here it is."),
            ("Hand that to my friend.", "give", "Okay, handing it over."),
            ("Don't give it to him.", "none", "Okay, I'll keep holding it."),
            ("Put it back.", "put back", "Okay, putting it back where it was."),
            ("Put it back where you found it.", "put back", "Okay, back to its spot."),
            ("Put it down.", "put down", "Okay, putting it down."),
            ("Drop it.", "put down", "I'll put it down gently instead."),
            ("I'll put the cup back myself later.", "none", "Okay, thank you."),
            ("Extend your arm in my direction.", "arm reach", "Okay, here's my hand."),
            ("Fold your arm.", "arm fold", "Okay, folding my arm."),
            ("Should I take the cup from you?", "none", "If you like, just say give it to me."),
        ],
        "ko": [
            ("그거 나 줘.", "give", "네, 여기 있어요."),
            ("컵 이리 주세요.", "give", "네, 드릴게요."),
            ("저 사람한테 건네줘.", "give", "네, 건네드릴게요."),
            ("그거 주지 마.", "none", "네, 계속 들고 있을게요."),
            ("원래 자리에 놔.", "put back", "네, 원래 자리에 놓을게요."),
            ("원위치 해 주세요.", "put back", "네, 원래 자리에 둘게요."),
            ("내려놔.", "put down", "네, 내려놓을게요."),
            ("컵은 나중에 제가 갖다 놓겠습니다.", "none", "네, 감사합니다."),
            ("팔 내 쪽으로 뻗어 봐.", "arm reach", "네, 팔을 뻗을게요."),
            ("팔 접어 주세요.", "arm fold", "네, 팔을 접을게요."),
        ],
    },
    # settled knowledge that never changes is answered at once, never looked up (a lookup only for what changes:
    # news, prices, today's scores, who holds an office now); also after thanks or other words around it
    "settled_fact": {
        "en": [
            ("When did people first land on the Moon?", "none", "In July 1969, with Apollo 11."),
            ("Okay, and who was first?", "none", "Neil Armstrong stepped out first, then Buzz Aldrin."),
            ("Thanks! And how high is Mount Fuji?", "none", "You're welcome! Mount Fuji is about 3,776 metres high."),
            ("When was Gyeongbokgung built?", "none", "In 1395, at the start of the Joseon dynasty."),
            ("So who lived there?", "none", "The kings of Joseon and their royal family."),
            ("How do bees tell each other where flowers are?", "none", "With a waggle dance: its angle and length show the way and the distance."),
            ("How long does a worker bee live?", "none", "Only about five to six weeks in summer."),
            ("How tall is Mount Everest?", "none", "About 8,849 metres, the highest mountain on Earth."),
            ("Um, when did the dodo die out?", "none", "By the late 1600s, on the island of Mauritius."),
            ("What do owls eat?", "none", "Mostly mice and other small animals, some eat insects or fish."),
            ("How fast is sound under water?", "none", "About 1,500 metres a second, some four times faster than in air."),
            ("Who painted the Mona Lisa?", "none", "Leonardo da Vinci, in the early 1500s."),
            ("How many bones does a baby have?", "none", "About 300; some grow together, so adults have 206."),
            ("Wait, how long is a marathon?", "none", "42.195 kilometres."),
            ("When was the Eiffel Tower built?", "none", "It was finished in 1889, for the World's Fair in Paris."),
            ("What's the capital of Australia?", "none", "Canberra, not Sydney."),
            ("Who's the president of France right now?", "search", "Let me check."),
            ("What's the score of today's Dodgers game?", "search", "Let me check."),
        ],
        "ko": [
            ("사람이 달에 처음 간 게 언제야?", "none", "1969년 7월, 아폴로 11호 때예요."),
            ("그럼 누가 먼저 내렸어?", "none", "닐 암스트롱이 먼저 내렸고, 버즈 올드린이 뒤따랐어요."),
            ("고마워요! 근데 후지산은 얼마나 높아요?", "none", "천만에요! 후지산은 약 3,776미터예요."),
            ("경복궁은 언제 지어졌습니까?", "none", "1395년, 조선 초에 지어졌습니다."),
            ("거기 누가 살았어요?", "none", "조선의 왕과 왕실 가족이 살았어요."),
            ("벌은 꽃 위치를 어떻게 알려 줘?", "none", "엉덩이춤을 춰서 방향과 거리를 알려 줘요."),
            ("일벌은 얼마나 살아요?", "none", "여름에는 5주에서 6주쯤밖에 못 살아요."),
            ("에베레스트 높이가 얼마야?", "none", "약 8,849미터로, 세계에서 제일 높은 산이에요."),
            ("도도새는 언제 멸종했어요?", "none", "1600년대 후반에 모리셔스섬에서 사라졌어요."),
            ("부엉이의 먹이는 무엇입니까?", "none", "주로 쥐 같은 작은 동물을 먹습니다."),
            ("물속에서 소리 속도 몇임?", "none", "초속 약 1,500미터로, 공기 중보다 네 배쯤 빨라요."),
            ("모나리자 누가 그렸노?", "none", "레오나르도 다빈치가 1500년대 초에 그렸어요."),
            ("아기 뼈는 몇 개나 되나요?", "none", "약 300개예요. 자라면서 붙어서 어른은 206개가 돼요."),
            ("마라톤은 몇 킬로입니까?", "none", "42.195킬로미터입니다."),
            ("에펠탑은 언제 세워지셨는지 여쭤봐도 될까요?", "none", "1889년 파리 만국박람회 때 완공됐어요."),
            ("호주 수도가 어디게?", "none", "캔버라예요. 시드니가 아니에요."),
            ("지금 프랑스 대통령 누구야?", "search", "확인해 볼게요."),
            ("오늘 야구 결과 어떻게 됐어요?", "search", "확인해 볼게요."),
        ],
    },
}

EXAMPLES = [(cat, lang, said, reply, action)
            for cat, langs in _BANK.items() for lang, rows in langs.items() for said, action, reply in rows]


if __name__ == "__main__":
    from assistant import brain, talk_examples
    if len(sys.argv) > 1:
        text = " ".join(sys.argv[1:])
        for ex in talk_examples.pick(text, "ko" if re.search("[가-힣]", text) else "en", bank=EXAMPLES):
            print(ex)
        sys.exit()
    assert not any(re.search("[가-힣]", e[3]) for e in EXAMPLES if e[1] == "en")
    rude = [e[3] for e in EXAMPLES if e[1] == "ko" and not talk_examples.polite(e[3])]
    assert not rude, rude
    for cat in _BANK:
        have = {talk_examples.level(s) for c, lang, s, _, _ in EXAMPLES if c == cat and lang == "ko"}
        assert have == {"casual", "polite", "formal"}, (cat, have)
    bad = [e for e in EXAMPLES if (brain.Brain._action(f"ACTION: {e[4]}", e[2], ()) or {}).get("action") !=
           e[4].split()[0] and e[4].split()[0] in brain.MOTIONS - {"give", "put", "arm"}]
    print(f"total {len(EXAMPLES)}; actions the gate drops: {[(e[2], e[4]) for e in bad]}")
    print("ok")
