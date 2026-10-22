"""Short words that may close the talk or only say "understood", read in their context (tests/closing_check.py).
Written blind (2026-10-22), the way visitors really talk, without looking at the rules: the same words end the talk
in one place and go on in another.

CASES = [(lang, turns before [(visitor, Lumi)], said, want)]
- want: "end" (the visitor is done and leaving), "on" (understood / reacting / asking on: the talk stays open, no
  goodbye), "either" (could be both: a goodbye, or waiting for the next words, are both fine).
"""
ANS = [("How fast can you drive?", "Normally 0.6 metres a second, at most 1.2.")]
ANS_KO = [("얼마나 빨리 움직여요?", "보통 초속 0.6미터, 최대 1.2미터예요.")]
ASKED = [("What can you do?", "I can answer questions, bring things and guide you. Anything else you'd like to know?")]
ASKED_KO = [("뭐 할 수 있어요?", "질문에 답하고, 물건을 가져다드리고, 안내도 해요. 더 궁금한 거 있으세요?")]
LONG = [("Who made you?", "Cutshion Company in Seoul developed me."),
        ("How tall are you?", "I'm 146 cm, up to 186 cm with the lift."),
        ("Can you pick things up?", "Yes, cups and small things up to about 1 kg.")]
LONG_KO = [("누가 만들었어요?", "서울의 쿳션에서 만들었어요."), ("키가 몇이에요?", "146센티미터예요. 리프트를 올리면 186센티까지 돼요."),
           ("물건도 들 수 있어요?", "네, 1킬로그램쯤까지 컵 같은 걸 들 수 있어요.")]
OFFER = [("Can you sing?", "Yes! Shall I sing one for you?")]
OFFER_KO = [("노래할 수 있어요?", "네! 한 곡 불러 드릴까요?")]

CASES = [
    # ---------- English: after a plain answer ----------
    ("en", ANS, "Okay thanks.", "either"),
    ("en", ANS, "Oh I see.", "on"),
    ("en", ANS, "Gotcha.", "on"),
    ("en", ANS, "Ah okay, makes sense. And how long does the battery last?", "on"),
    ("en", ANS, "Okay cool, thanks. Can you also turn around?", "on"),
    ("en", ANS, "Cool cool.", "on"),
    ("en", ANS, "Right, thanks, that's all I wanted to know.", "end"),
    ("en", ANS, "Great, thanks a lot. I'll let you get back to work.", "end"),
    ("en", ANS, "Okay, I gotta run. Thanks!", "end"),
    ("en", ANS, "Thanks, I think I'm good.", "end"),
    ("en", ANS, "Alright. Hmm, what else... oh, do you have a name?", "on"),
    ("en", ANS, "Not bad for a robot.", "on"),
    ("en", ANS, "I got you.", "on"),
    ("en", ANS, "Okay, noted.", "either"),
    ("en", ANS, "Perfect, thank you so much, have a good one!", "end"),
    ("en", ANS, "Thanks. Wait, one more thing.", "on"),
    ("en", ANS, "Sweet. That's pretty quick.", "on"),
    ("en", ANS, "Okay, nice talking to you!", "end"),
    # ---------- English: after Lumi asked something ----------
    ("en", ASKED, "No, that's it, thanks.", "end"),
    ("en", ASKED, "Nah, I'm good.", "end"),
    ("en", ASKED, "Hmm, not right now.", "either"),
    ("en", ASKED, "Yeah actually, how much do you weigh?", "on"),
    ("en", ASKED, "Okay.", "either"),
    ("en", ASKED, "Nope, all good. See you around.", "end"),
    ("en", OFFER, "Okay!", "on"),
    ("en", OFFER, "Sure, go ahead.", "on"),
    ("en", OFFER, "Maybe later, thanks.", "either"),
    ("en", OFFER, "No thanks, I have to go.", "end"),
    # ---------- English: after several turns ----------
    ("en", LONG, "Okay, I think that's everything.", "end"),
    ("en", LONG, "Thanks Lumi, you've been very helpful.", "either"),
    ("en", LONG, "Awesome. Alright, I'm off.", "end"),
    ("en", LONG, "Got it. So what do you do here all day?", "on"),
    ("en", LONG, "Wow okay.", "on"),
    ("en", LONG, "That's enough for now, thank you.", "end"),
    ("en", LONG, "Understood, thanks.", "either"),
    ("en", LONG, "Fine.", "either"),
    # ---------- Korean: after a plain answer ----------
    ("ko", ANS_KO, "오케이 됐어.", "either"),
    ("ko", ANS_KO, "아 그렇구나.", "on"),
    ("ko", ANS_KO, "알겠어요, 고마워요.", "either"),
    ("ko", ANS_KO, "오 빠르네요.", "on"),
    ("ko", ANS_KO, "알겠어. 그럼 배터리는 얼마나 가?", "on"),
    ("ko", ANS_KO, "네네 감사합니다, 이제 가 볼게요.", "end"),
    ("ko", ANS_KO, "됐어요, 궁금한 거 다 물어봤어요.", "end"),
    ("ko", ANS_KO, "아하 오케이.", "on"),
    ("ko", ANS_KO, "고마워~ 다음에 또 올게!", "end"),
    ("ko", ANS_KO, "응 알겠어.", "either"),
    ("ko", ANS_KO, "그렇군요. 근데 이름이 뭐예요?", "on"),
    ("ko", ANS_KO, "생각보다 느리네.", "on"),
    ("ko", ANS_KO, "감사합니다. 수고하세요!", "end"),
    ("ko", ANS_KO, "아 진짜? 대박.", "on"),
    ("ko", ANS_KO, "오케이 오케이. 하나만 더 물어봐도 돼요?", "on"),
    # ---------- Korean: after Lumi asked something ----------
    ("ko", ASKED_KO, "아뇨, 됐어요. 고마워요.", "end"),
    ("ko", ASKED_KO, "없어요~", "end"),
    ("ko", ASKED_KO, "음 지금은 괜찮아요.", "either"),
    ("ko", ASKED_KO, "네, 몇 살이에요?", "on"),
    ("ko", ASKED_KO, "아니 괜찮아, 나 이제 가야 돼.", "end"),
    ("ko", ASKED_KO, "네.", "either"),
    ("ko", OFFER_KO, "응 불러 줘!", "on"),
    ("ko", OFFER_KO, "좋아요!", "on"),
    ("ko", OFFER_KO, "다음에 들을게요, 고마워요.", "either"),
    # ---------- Korean: after several turns ----------
    ("ko", LONG_KO, "오케이, 이 정도면 됐어.", "end"),
    ("ko", LONG_KO, "알겠습니다. 그럼 여기서 뭐 하는 로봇이에요?", "on"),
    ("ko", LONG_KO, "와 신기하다.", "on"),
    ("ko", LONG_KO, "고마워요 루미, 덕분에 많이 알았어요.", "either"),
    ("ko", LONG_KO, "그만 물어볼게요. 잘 있어요.", "end"),
    ("ko", LONG_KO, "이해했어요.", "either"),
    ("ko", LONG_KO, "ㅇㅋ 땡큐", "either"),
    # ---------- mixed ----------
    ("ko", ANS_KO, "오케이 thank you!", "either"),
    ("en", ANS, "Okay 감사합니다.", "either"),
]

# a second set, written after the change and run once without tuning (the change's generalisation)
DONE = [("Where are you from?", "I was made in Seoul by Cutshion Company. Is there anything else I can tell you?")]
DONE_KO = [("어디서 왔어요?", "서울의 쿳션에서 만들어졌어요. 또 궁금한 거 있으세요?")]
FACT = [("Can you see in the dark?", "I'm not sure about that, a staff member can tell you.")]
FACT_KO = [("어두운 데서도 보여요?", "그건 저도 잘 몰라요. 직원분께 여쭤봐 주세요.")]
HOLDOUT = [
    ("en", DONE, "No no, that's plenty. Cheers!", "end"),
    ("en", DONE, "Hm, nope.", "either"),
    ("en", DONE, "Yeah, what's your battery like?", "on"),
    ("en", DONE, "I'm all set, thanks robot.", "end"),
    ("en", DONE, "Ok ok, catch you later.", "end"),
    ("en", FACT, "Ah, alright.", "either"),
    ("en", FACT, "No worries.", "either"),
    ("en", FACT, "Hmm okay. What about stairs then?", "on"),
    ("en", FACT, "Fair. Thanks anyway.", "either"),
    ("en", FACT, "Huh, interesting.", "on"),
    ("en", FACT, "Okay okay, I'll ask someone. Bye for now.", "end"),
    ("en", ANS, "Right on.", "on"),
    ("en", ANS, "Okay, that answers my question. Thanks, I'm heading out.", "end"),
    ("en", ANS, "Thanks! So what's your name again?", "on"),
    ("en", ANS, "Okay great. Let me get my friend over here.", "on"),
    ("ko", DONE_KO, "아뇨 이제 충분해요. 고마워요~", "end"),
    ("ko", DONE_KO, "음… 없는 것 같아요.", "either"),
    ("ko", DONE_KO, "네, 배터리는 얼마나 가요?", "on"),
    ("ko", DONE_KO, "됐어 됐어, 나 간다~", "end"),
    ("ko", DONE_KO, "아 괜찮아요 괜찮아요.", "either"),
    ("ko", FACT_KO, "아 그래요? 알겠어요.", "on"),
    ("ko", FACT_KO, "넵.", "either"),
    ("ko", FACT_KO, "그렇구나. 그럼 계단은 올라가요?", "on"),
    ("ko", FACT_KO, "오키 고마워!", "either"),
    ("ko", FACT_KO, "흠 신기하네.", "on"),
    ("ko", ANS_KO, "알겠습니다. 이제 볼일 보러 가야겠네요.", "end"),
    ("ko", ANS_KO, "오 감사요. 근데 혹시 춤도 춰요?", "on"),
    ("ko", ANS_KO, "그래 고마워, 담에 봐!", "end"),
    ("ko", ANS_KO, "오케바리~", "either"),
    ("ko", ANS_KO, "친구 불러올게요, 잠깐만요.", "on"),
]
