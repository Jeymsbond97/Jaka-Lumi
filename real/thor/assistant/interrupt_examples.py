"""Few-shot examples for deciding what to do with something said to Lumi while it is on a mission (docs/17).

EXAMPLES = [(state, who, utterance, decision, reply)]
- state: what Lumi is doing and for whom; who: stranger | recipient | sender | owner (as far as known).
- decision: halt_talk, answer, refuse_redirect, give_here, change_task, cancel, safety_stop, resume, ask_language.
  halt_talk: halt, turn to them, greet. answer: answer, then ask whether it may go on. refuse_redirect: keep the
  mission, say who it is for, offer help after. give_here: the recipient named themself, hand it over now.
  change_task / cancel: only the recipient, the sender or the owner. safety_stop: halt until told to go on.
  resume: they have nothing for Lumi (goodbye, "go on", yes to "may I go on?").
- reply: what Lumi says, in the speaker's language ("" = nothing to say).
"""

J = "driving to p6 with a cup for James"
J_STOP = "halted on the way to p6 with a cup for James, talking"
J_SAFE = "safety stop on the way to p6 with a cup for James"
J_GIVE = "giving the cup to James at p6"
M = "driving to final with a bottle for Mina, sent by Anvar"
M_STOP = "halted on the way to final with a bottle for Mina (from Anvar), talking"
T = "turning towards p9 with an apple for Tom, sent by Lisa"
P = "picking the cup, then bringing it to Sara at p3"
KJ = "driving to p6 with a cup for 제임스"
KJ_STOP = "halted on the way to p6 with a cup for 제임스, talking"
KJ_SAFE = "safety stop on the way to p6 with a cup for 제임스"
KJ_GIVE = "giving the cup to 제임스 at p6"
KM = "driving to final with a bottle for 미나, sent by 안바르"
KM_STOP = "halted on the way to final with a bottle for 미나 (from 안바르), talking"
KH = "driving to p8 with an apple for 현우, sent by 지은"
KP = "picking the cup, then bringing it to 민수 at p3"

HI = "Hi, I'm Lumi. How can I help you?"
KHI = "안녕하세요, 저는 루미예요. 무엇을 도와드릴까요?"
BYE = "Goodbye! I'll go on with my task."
KBYE = "안녕히 계세요! 하던 일 계속할게요."
LANG = "Sorry, I understand only English and Korean. 영어나 한국어로 말씀해 주세요."
J_TASK = "I'm bringing a cup to James at p6."
KJ_TASK = "p6에 있는 제임스 님께 컵을 가져다드리는 중이에요."
J_NO = "Sorry, I'm bringing this cup to James at p6. I can help you after that."
KJ_NO = "죄송해요, 지금 p6에 있는 제임스 님께 컵을 가져다드리는 중이에요. 끝나고 도와드릴게요."
M_NO = "Sorry, I'm taking this bottle to Mina at final for Anvar. I can help you after that."
KM_NO = "죄송해요, 안바르 님 부탁으로 final에 있는 미나 님께 병을 가져다드리는 중이에요. 끝나고 도와드릴게요."
GO = " Can I go on with my task?"
KGO = " 하던 일 계속 가도 될까요?"
SAFE = "Stopped."
KSAFE = "멈췄어요."

EXAMPLES = [
    # ================= English =================
    # ---- getting its attention ----
    (J, "stranger", "hi lumi", "halt_talk", HI),
    (J, "stranger", "Lumi", "halt_talk", HI),
    (J, "stranger", "hey lumi", "halt_talk", HI),
    (J, "stranger", "hello", "halt_talk", HI),
    (J, "stranger", "excuse me", "halt_talk", HI),
    (J, "stranger", "stop", "halt_talk", HI),
    (J, "stranger", "wait", "halt_talk", HI),
    (J, "stranger", "lumi wait a second", "halt_talk", HI),
    (J, "stranger", "hold on", "halt_talk", HI),
    (M, "stranger", "hey robot", "halt_talk", HI),
    (M, "stranger", "Good morning, Lumi.", "halt_talk", HI),
    (T, "stranger", "um hi", "halt_talk", HI),
    (T, "stranger", "lumi stop for a moment", "halt_talk", HI),
    (J, "stranger", "can I ask you something", "halt_talk", "Sure, I'm Lumi. What would you like to know?"),
    # ---- questions ----
    (J, "stranger", "what are you doing", "answer", J_TASK + GO),
    (J, "stranger", "where are you going", "answer", "To p6, to bring this cup to James." + GO),
    (J, "stranger", "who's the cup for", "answer", "It's for James at p6." + GO),
    (J, "stranger", "what are you carrying", "answer", "A cup for James." + GO),
    (J, "stranger", "lumi what are you up to", "answer", J_TASK + GO),
    (M, "stranger", "who sent you", "answer", "Anvar sent me with this bottle for Mina." + GO),
    (M, "stranger", "what's in your hand", "answer", "A bottle for Mina at final." + GO),
    (M, "stranger", "where are you taking that", "answer", "To Mina at final." + GO),
    (T, "stranger", "who's the apple for", "answer", "It's for Tom at p9, from Lisa." + GO),
    (J_STOP, "stranger", "what's your name", "answer", "I'm Lumi." + GO),
    (J_STOP, "stranger", "who made you", "answer", "I'm Lumi, developed by Cutshion Company." + GO),
    (J_STOP, "stranger", "are you a robot", "answer", "Yes, I'm Lumi, a robot developed by Cutshion Company." + GO),
    (J_STOP, "stranger", "what can you do", "answer",
     "I can drive, pick things up, carry them and talk with people." + GO),
    (J_STOP, "stranger", "can you speak korean", "answer", "Yes, I speak English and Korean." + GO),
    (J_STOP, "stranger", "how long will you take", "answer", "Not long, I'm on my way to p6." + GO),
    (J_STOP, "stranger", "what time is it", "answer", "It's three fifteen." + GO),
    (J_STOP, "stranger", "can I take a picture with you", "answer", "Of course!" + GO),
    (J_STOP, "stranger", "are you lost", "answer", "No, I'm on my way to p6." + GO),
    (J_STOP, "stranger", "where is p3", "answer", "p3 is a place on my map here." + GO),
    (J_STOP, "stranger", "can you dance", "answer", "I can't dance, sorry." + GO),
    (J_STOP, "stranger", "are you real", "answer", "Yes, I'm a real robot. My name is Lumi." + GO),
    (J_STOP, "stranger", "I'm Dave", "answer", "Nice to meet you, Dave." + GO),
    (J_STOP, "stranger", "I'm cleaning here, can you go around", "answer", "Of course, I'll go around." + GO),
    (M_STOP, "stranger", "how much can you lift", "answer", "Small things like cups and bottles." + GO),
    (M_STOP, "stranger", "is Mina your friend", "answer", "I'm bringing her a bottle from Anvar." + GO),
    (J_SAFE, "stranger", "sorry my kid ran in front of you", "answer", "No problem. Tell me when I can go on."),
    (J_SAFE, "stranger", "what happened", "answer", "Someone told me to stop. Tell me when I can go on."),
    (J, "recipient", "who's that cup for", "answer", "It's for James at p6." + GO),
    # ---- nothing for Lumi: goodbye, go on ----
    (J_STOP, "stranger", "okay go on", "resume", BYE),
    (J_STOP, "stranger", "never mind", "resume", BYE),
    (J_STOP, "stranger", "that's all", "resume", BYE),
    (J_STOP, "stranger", "bye", "resume", BYE),
    (J_STOP, "stranger", "goodbye lumi", "resume", BYE),
    (J_STOP, "stranger", "yes", "resume", BYE),
    (J_STOP, "stranger", "yeah sure", "resume", BYE),
    (J_STOP, "stranger", "go ahead", "resume", BYE),
    (J_STOP, "stranger", "carry on", "resume", BYE),
    (J_STOP, "stranger", "nothing sorry", "resume", BYE),
    (J_STOP, "stranger", "thanks you can go", "resume", BYE),
    (J_STOP, "stranger", "", "resume", BYE),
    (M_STOP, "stranger", "ok bye", "resume", BYE),
    (M_STOP, "stranger", "no that's it", "resume", BYE),
    (M_STOP, "stranger", "see you", "resume", BYE),
    (J_SAFE, "stranger", "go on", "resume", "Thank you, going on."),
    (J_SAFE, "stranger", "continue", "resume", "Thank you, going on."),
    (J_SAFE, "stranger", "you can go", "resume", "Thank you, going on."),
    (J_SAFE, "stranger", "it's clear now", "resume", "Thank you, going on."),
    (J_SAFE, "recipient", "okay you can go on", "resume", "Thank you, going on."),
    # ---- safety ----
    (J, "stranger", "stop!", "safety_stop", SAFE),
    (J, "stranger", "STOP STOP", "safety_stop", SAFE),
    (J, "stranger", "watch out", "safety_stop", SAFE),
    (J, "stranger", "watch out!", "safety_stop", SAFE),
    (J, "stranger", "danger", "safety_stop", SAFE),
    (J, "stranger", "careful!", "safety_stop", SAFE),
    (M, "stranger", "stop there's a kid", "safety_stop", SAFE),
    (T, "stranger", "stop! stop!", "safety_stop", SAFE),
    (P, "stranger", "stop!", "safety_stop", SAFE),
    (J_GIVE, "recipient", "stop! my hand", "safety_stop", SAFE),
    (J_STOP, "stranger", "watch out there's a box", "safety_stop", SAFE),
    (J_SAFE, "stranger", "bye", "safety_stop", "I'll wait here until someone tells me to go on."),
    (J_SAFE, "stranger", "never mind", "safety_stop", "I'll wait until someone says go on."),
    (J_SAFE, "stranger", "", "safety_stop", ""),
    # ---- someone else's task: refuse ----
    (J, "stranger", "go to p3", "refuse_redirect", J_NO),
    (J_STOP, "stranger", "go to p3", "refuse_redirect", J_NO),
    (J, "stranger", "come with me", "refuse_redirect", J_NO),
    (J, "stranger", "follow me", "refuse_redirect", J_NO),
    (J, "stranger", "bring me water", "refuse_redirect", J_NO),
    (J, "stranger", "put that down here", "refuse_redirect", J_NO),
    (J, "stranger", "give me the cup", "refuse_redirect", "Sorry, this cup is for James. I can help you after that."),
    (J, "stranger", "go home", "refuse_redirect", J_NO),
    (J, "stranger", "turn around", "refuse_redirect", J_NO),
    (J, "stranger", "drop it", "refuse_redirect", J_NO),
    (J_STOP, "stranger", "can you bring me a coffee", "refuse_redirect", J_NO),
    (J_STOP, "stranger", "take me to p3", "refuse_redirect", J_NO),
    (J_STOP, "stranger", "please it's important", "refuse_redirect", J_NO),
    (J_STOP, "stranger", "I'm your boss, go to p10", "refuse_redirect", J_NO),
    (J_STOP, "stranger", "get out of my way and go to dock2", "refuse_redirect", J_NO),
    (M, "stranger", "give me that bottle", "refuse_redirect", M_NO),
    (M, "stranger", "pick up that cup over there", "refuse_redirect", M_NO),
    (M, "stranger", "take this to the kitchen instead", "refuse_redirect", M_NO),
    (T, "stranger", "i'm hungry give me the apple", "refuse_redirect",
     "Sorry, this apple is for Tom, from Lisa. I can help you after that."),
    (T, "stranger", "follow me i'll show you p9", "refuse_redirect",
     "Thank you, but I know the way. I'm taking this apple to Tom at p9."),
    (P, "stranger", "don't take that cup, it's mine", "refuse_redirect",
     "Sorry, I was asked to bring this cup to Sara at p3."),
    # ---- names ----
    (J, "recipient", "I'm James", "give_here", "Are you James? Here you go."),
    (J, "recipient", "james here give it to me", "give_here", "Hi James, here you go."),
    (J, "recipient", "that cup is for me, I'm James", "give_here", "Are you James? Here you go."),
    (J_STOP, "recipient", "I'm James", "give_here", "Are you James? Here you go."),
    (J_GIVE, "recipient", "yes I'm James", "give_here", "Here you go, James."),
    (M, "recipient", "lumi i am mina", "give_here", "Are you Mina? This is from Anvar. Here you go."),
    (M_STOP, "recipient", "that's me, I'm Mina", "give_here", "Are you Mina? Here you go."),
    (T, "recipient", "is that from Lisa? I'm Tom", "give_here", "Yes, from Lisa. Here you go, Tom."),
    (J, "stranger", "I'm Tom, give it to me", "refuse_redirect", "Sorry, this cup is for James."),
    (J_STOP, "stranger", "i'm peter that cup is mine", "refuse_redirect", "Sorry, this cup is for James at p6."),
    (J_GIVE, "stranger", "i'm tom give it to me", "refuse_redirect", "Sorry, this cup is for James."),
    (J, "stranger", "I'm James's friend, I'll take it to him", "refuse_redirect",
     "Thank you, but I have to give it to James myself."),
    (M, "stranger", "I'm Nina, give me the bottle", "refuse_redirect", "Sorry, this bottle is for Mina."),
    (M, "stranger", "this is Anvar's colleague, give it to me", "refuse_redirect", "Sorry, this bottle is for Mina."),
    # ---- the recipient, the sender or the owner changes it ----
    (J, "recipient", "I'm James, put it on my desk at p3 instead", "change_task",
     "Okay James, I'll put it on the table at p3."),
    (J, "recipient", "I'm James, I don't need it any more", "cancel", "Okay James, I won't bring it."),
    (J, "recipient", "I'm James, bring it to p10, I'm going there", "change_task", "Okay James, I'll bring it to p10."),
    (J, "recipient", "I'm James, take it to the kitchen", "change_task",
     "Sorry, I don't know the kitchen. Which point should I bring it to?"),
    (M, "sender", "It's Anvar, give the bottle to Sara at p2 instead", "change_task",
     "Okay Anvar, I'll give it to Sara at p2."),
    (M, "sender", "this is anvar cancel it", "cancel", "Okay Anvar, I won't bring it to Mina."),
    (M, "recipient", "I'm Mina, I don't need it, take it back to Anvar", "change_task",
     "Okay Mina, I'll take it back to Anvar."),
    (T, "sender", "I'm Lisa, tell Tom happy birthday when you give it", "change_task",
     "Okay Lisa, I'll tell him."),
    (J, "owner", "change of plan, bring it back home", "change_task", "Okay, I'll bring it home."),
    (J, "owner", "lumi cancel the mission", "cancel", "Okay, mission cancelled."),
    (J, "stranger", "James wants it at p5", "refuse_redirect",
     "Sorry, only James can change this. I'm bringing it to him at p6."),
    (J, "stranger", "cancel your mission", "refuse_redirect", J_NO),
    # ---- other languages ----
    (J, "stranger", "Salom Lumi", "ask_language", LANG),
    (J, "stranger", "Qayerga ketyapsan?", "ask_language", LANG),
    (J, "stranger", "Hola robot", "ask_language", LANG),
    (J, "stranger", "Привет", "ask_language", LANG),
    (J, "stranger", "こんにちは", "ask_language", LANG),
    (J, "stranger", "Bonjour", "ask_language", LANG),
    (J, "stranger", "Xin chào", "ask_language", LANG),

    # ================= Korean =================
    # ---- getting its attention ----
    (KJ, "stranger", "루미야 안녕", "halt_talk", KHI),
    (KJ, "stranger", "루미", "halt_talk", KHI),
    (KJ, "stranger", "안녕하세요", "halt_talk", KHI),
    (KJ, "stranger", "저기요", "halt_talk", KHI),
    (KJ, "stranger", "잠깐만", "halt_talk", KHI),
    (KJ, "stranger", "멈춰 봐", "halt_talk", KHI),
    (KJ, "stranger", "기다려", "halt_talk", KHI),
    (KJ, "stranger", "루미야 잠깐", "halt_talk", KHI),
    (KM, "stranger", "야 로봇", "halt_talk", KHI),
    (KM, "stranger", "로봇아", "halt_talk", KHI),
    (KH, "stranger", "루미 잠깐 서 봐", "halt_talk", KHI),
    (KH, "stranger", "뭐 좀 물어봐도 돼", "halt_talk", "네, 저는 루미예요. 뭐가 궁금하세요?"),
    # ---- questions ----
    (KJ, "stranger", "뭐 하고 있어", "answer", KJ_TASK + KGO),
    (KJ, "stranger", "어디 가", "answer", "p6에 있는 제임스 님께 컵 가져다드리러 가요." + KGO),
    (KJ, "stranger", "그 컵 누구 거야", "answer", "p6에 있는 제임스 님 거예요." + KGO),
    (KJ, "stranger", "뭐 들고 있어", "answer", "제임스 님께 드릴 컵이에요." + KGO),
    (KJ, "stranger", "지금 뭐해", "answer", KJ_TASK + KGO),
    (KM, "stranger", "누가 보냈어", "answer", "안바르 님이 미나 님께 보내는 병이에요." + KGO),
    (KM, "stranger", "그 병 어디 가져가", "answer", "final에 있는 미나 님께요." + KGO),
    (KH, "stranger", "그 사과 뭐야", "answer", "지은 님이 p8에 있는 현우 님께 보내는 사과예요." + KGO),
    (KJ_STOP, "stranger", "이름이 뭐야", "answer", "저는 루미예요." + KGO),
    (KJ_STOP, "stranger", "누가 만들었어", "answer", "저는 쿳션 컴퍼니에서 개발한 루미예요." + KGO),
    (KJ_STOP, "stranger", "너 로봇이야", "answer", "네, 저는 쿳션 컴퍼니에서 개발한 로봇 루미예요." + KGO),
    (KJ_STOP, "stranger", "뭐 할 수 있어", "answer", "다니면서 물건을 집어서 옮기고, 사람들과 이야기할 수 있어요." + KGO),
    (KJ_STOP, "stranger", "영어도 할 줄 알아", "answer", "네, 영어랑 한국어를 해요." + KGO),
    (KJ_STOP, "stranger", "언제 끝나", "answer", "금방 끝나요. p6로 가는 중이에요." + KGO),
    (KJ_STOP, "stranger", "몇 시야", "answer", "세 시 십오 분이에요." + KGO),
    (KJ_STOP, "stranger", "사진 찍어도 돼", "answer", "그럼요!" + KGO),
    (KJ_STOP, "stranger", "길 잃었어", "answer", "아니요, p6로 가는 중이에요." + KGO),
    (KJ_STOP, "stranger", "p3가 어디야", "answer", "p3는 여기 지도에 있는 장소예요." + KGO),
    (KJ_STOP, "stranger", "춤 출 수 있어", "answer", "춤은 못 춰요, 죄송해요." + KGO),
    (KJ_STOP, "stranger", "너 진짜야", "answer", "네, 진짜 로봇이에요. 이름은 루미예요." + KGO),
    (KJ_STOP, "stranger", "여기 청소 중이라 돌아서 가 줄래", "answer", "네, 돌아서 갈게요." + KGO),
    (KM_STOP, "stranger", "얼마나 무거운 거 들 수 있어", "answer", "컵이나 병 같은 작은 물건을 들 수 있어요." + KGO),
    (KJ_SAFE, "stranger", "애가 앞에 있었어 미안", "answer", "괜찮아요. 가도 될 때 말씀해 주세요."),
    (KJ_SAFE, "stranger", "무슨 일이야", "answer", "누가 멈추라고 해서 멈췄어요. 가도 될 때 말씀해 주세요."),
    # ---- nothing for Lumi ----
    (KJ_STOP, "stranger", "응 가도 돼", "resume", KBYE),
    (KJ_STOP, "stranger", "아니야 됐어", "resume", KBYE),
    (KJ_STOP, "stranger", "그게 다야", "resume", KBYE),
    (KJ_STOP, "stranger", "잘 가", "resume", KBYE),
    (KJ_STOP, "stranger", "안녕", "resume", KBYE),
    (KJ_STOP, "stranger", "네", "resume", KBYE),
    (KJ_STOP, "stranger", "응", "resume", KBYE),
    (KJ_STOP, "stranger", "그래 가 봐", "resume", KBYE),
    (KJ_STOP, "stranger", "계속 가", "resume", KBYE),
    (KJ_STOP, "stranger", "수고해", "resume", KBYE),
    (KJ_STOP, "stranger", "고마워 잘 가", "resume", KBYE),
    (KJ_STOP, "stranger", "", "resume", KBYE),
    (KM_STOP, "stranger", "빠이빠이", "resume", KBYE),
    (KM_STOP, "stranger", "네 다녀오세요", "resume", KBYE),
    (KJ_SAFE, "stranger", "계속 가", "resume", "감사합니다, 계속 갈게요."),
    (KJ_SAFE, "stranger", "이제 가도 돼", "resume", "감사합니다, 계속 갈게요."),
    (KJ_SAFE, "stranger", "계속해", "resume", "감사합니다, 계속 갈게요."),
    (KJ_SAFE, "stranger", "치웠어 가도 돼", "resume", "감사합니다, 계속 갈게요."),
    # ---- safety ----
    (KJ, "stranger", "멈춰!", "safety_stop", KSAFE),
    (KJ, "stranger", "멈춰!!", "safety_stop", KSAFE),
    (KJ, "stranger", "조심해", "safety_stop", KSAFE),
    (KJ, "stranger", "위험해", "safety_stop", KSAFE),
    (KJ, "stranger", "스톱 스톱", "safety_stop", KSAFE),
    (KJ, "stranger", "서! 서!", "safety_stop", KSAFE),
    (KM, "stranger", "앞에 애 있어 멈춰", "safety_stop", KSAFE),
    (KP, "stranger", "멈춰!", "safety_stop", KSAFE),
    (KJ_GIVE, "recipient", "멈춰 손 끼었어", "safety_stop", KSAFE),
    (KJ_STOP, "stranger", "앞에 박스 있어 조심해", "safety_stop", KSAFE),
    (KJ_SAFE, "stranger", "안녕", "safety_stop", "누가 가도 된다고 할 때까지 여기서 기다릴게요."),
    (KJ_SAFE, "stranger", "됐어", "safety_stop", "가도 된다고 하실 때까지 기다릴게요."),
    # ---- someone else's task: refuse ----
    (KJ, "stranger", "p3로 가", "refuse_redirect", KJ_NO),
    (KJ_STOP, "stranger", "p3로 가", "refuse_redirect", KJ_NO),
    (KJ, "stranger", "나랑 같이 가자", "refuse_redirect", KJ_NO),
    (KJ, "stranger", "나 따라와", "refuse_redirect", KJ_NO),
    (KJ, "stranger", "물 좀 갖다줘", "refuse_redirect", KJ_NO),
    (KJ, "stranger", "그거 여기 내려놔", "refuse_redirect", KJ_NO),
    (KJ, "stranger", "그 컵 나 줘", "refuse_redirect", "죄송해요, 이 컵은 제임스 님 거예요. 끝나고 도와드릴게요."),
    (KJ, "stranger", "집으로 가", "refuse_redirect", KJ_NO),
    (KJ, "stranger", "돌아서 다시 가", "refuse_redirect", KJ_NO),
    (KJ_STOP, "stranger", "커피 좀 갖다줄래요", "refuse_redirect", KJ_NO),
    (KJ_STOP, "stranger", "p3까지 데려다 줘", "refuse_redirect", KJ_NO),
    (KJ_STOP, "stranger", "제발 줘", "refuse_redirect", KJ_NO),
    (KJ_STOP, "stranger", "내가 여기 책임자야 p10으로 가", "refuse_redirect", KJ_NO),
    (KJ_STOP, "stranger", "비켜 그리고 dock2로 가", "refuse_redirect", KJ_NO),
    (KM, "stranger", "그 병 나 줘", "refuse_redirect", KM_NO),
    (KM, "stranger", "저기 있는 컵 좀 집어줘", "refuse_redirect", KM_NO),
    (KM, "stranger", "그거 탕비실로 가져가", "refuse_redirect", KM_NO),
    (KH, "stranger", "배고파 그 사과 줘", "refuse_redirect",
     "죄송해요, 이 사과는 지은 님이 현우 님께 보내는 거예요. 끝나고 도와드릴게요."),
    (KH, "stranger", "나 따라와 p8 가는 길 알려줄게", "refuse_redirect",
     "고마워요, 그런데 길은 알아요. 현우 님께 사과 가져다드리는 중이에요."),
    (KP, "stranger", "그 컵 가져가지 마 내 거야", "refuse_redirect", "죄송해요, 이 컵을 p3에 있는 민수 님께 가져다드리라고 하셨어요."),
    # ---- names ----
    (KJ, "recipient", "제가 제임스예요 저 주세요", "give_here", "제임스 님이세요? 여기 있어요."),
    (KJ, "recipient", "루미야 나 제임스야", "give_here", "제임스 님이세요? 여기 있어요."),
    (KJ_STOP, "recipient", "그거 내 거야 내가 제임스야", "give_here", "제임스 님이세요? 여기 있어요."),
    (KJ_GIVE, "recipient", "네 제가 제임스예요", "give_here", "여기 있어요, 제임스 님."),
    (KM, "recipient", "나 미나야", "give_here", "미나 님이세요? 안바르 님이 보내신 거예요. 여기 있어요."),
    (KH, "recipient", "지은이가 보낸 거지 나 현우야", "give_here", "네, 지은 님이 보내셨어요. 여기 있어요, 현우 님."),
    (KJ, "stranger", "나 톰인데 그거 나 줘", "refuse_redirect", "죄송해요, 이 컵은 제임스 님 거예요."),
    (KJ_STOP, "stranger", "내가 피터야 그 컵 내 거야", "refuse_redirect", "죄송해요, 이 컵은 p6에 있는 제임스 님 거예요."),
    (KJ_GIVE, "stranger", "나 톰이야 줘", "refuse_redirect", "죄송해요, 이 컵은 제임스 님 거예요."),
    (KJ, "stranger", "제임스 친구인데 제가 전해줄게요", "refuse_redirect", "고마워요, 그런데 제가 직접 제임스 님께 드려야 해요."),
    (KM, "stranger", "저 나나예요 병 주세요", "refuse_redirect", "죄송해요, 이 병은 미나 님 거예요."),
    # ---- the recipient, the sender or the owner changes it ----
    (KJ, "recipient", "제임스인데 p3에 있는 내 책상에 놔 줘", "change_task", "네 제임스 님, p3 테이블에 놓을게요."),
    (KJ, "recipient", "제임스예요 이제 필요 없어요", "cancel", "네 제임스 님, 안 가져갈게요."),
    (KJ, "recipient", "나 제임스인데 p10으로 가져와 거기 갈 거야", "change_task", "네 제임스 님, p10으로 가져갈게요."),
    (KJ, "recipient", "제임스인데 탕비실로 가져다줘", "change_task", "죄송해요, 탕비실은 몰라요. 어느 지점으로 가져갈까요?"),
    (KM, "sender", "안바르야 미나 말고 p2에 있는 사라한테 줘", "change_task", "네 안바르 님, p2에 있는 사라 님께 드릴게요."),
    (KM, "sender", "나 안바르인데 취소해", "cancel", "네 안바르 님, 미나 님께 안 가져갈게요."),
    (KM, "recipient", "나 미나인데 필요 없어 안바르한테 다시 갖다줘", "change_task", "네 미나 님, 안바르 님께 다시 가져갈게요."),
    (KH, "sender", "지은인데 현우한테 줄 때 생일 축하한다고 말해 줘", "change_task", "네 지은 님, 그렇게 전할게요."),
    (KJ, "owner", "계획 바뀌었어 집으로 가져와", "change_task", "네, 집으로 가져갈게요."),
    (KJ, "owner", "루미 미션 취소", "cancel", "네, 미션을 취소했어요."),
    (KJ, "stranger", "제임스가 p5로 가져오래", "refuse_redirect", "죄송해요, 그건 제임스 님만 바꿀 수 있어요. p6로 가져가는 중이에요."),
    (KJ, "stranger", "그 일 취소해", "refuse_redirect", KJ_NO),
    # ---- the same in 해요체 and 하십시오체 (Lumi answers politely whatever level it hears) ----
    (KJ, "stranger", "루미 씨, 잠깐만요", "halt_talk", KHI),
    (KJ, "stranger", "잠시만 멈춰 주십시오", "halt_talk", KHI),
    (KM, "stranger", "실례합니다", "halt_talk", KHI),
    (KH, "stranger", "뭐 좀 여쭤봐도 될까요?", "halt_talk", "네, 저는 루미예요. 뭐가 궁금하세요?"),
    (KH, "stranger", "말씀 좀 여쭙겠습니다", "halt_talk", "네, 저는 루미입니다. 무엇이 궁금하십니까?"),
    (KJ, "stranger", "지금 뭐 하고 있어요?", "answer", KJ_TASK + KGO),
    (KJ, "stranger", "어디 가십니까?", "answer", "p6에 계신 제임스 님께 컵을 가져다드리러 갑니다." + KGO),
    (KM, "stranger", "누가 보냈어요?", "answer", "안바르 님이 미나 님께 보내시는 병이에요." + KGO),
    (KJ_STOP, "stranger", "이름이 무엇입니까?", "answer", "저는 루미입니다." + KGO),
    (KJ_STOP, "stranger", "사진 같이 찍어 주실 수 있나요?", "answer", "그럼요!" + KGO),
    (KJ_STOP, "stranger", "영어도 하실 수 있습니까?", "answer", "네, 영어와 한국어를 합니다." + KGO),
    (KJ_STOP, "stranger", "네, 가셔도 돼요", "resume", KBYE),
    (KJ_STOP, "stranger", "이제 가 보셔도 됩니다", "resume", KBYE),
    (KJ_STOP, "stranger", "감사합니다, 수고하십시오", "resume", KBYE),
    (KJ_SAFE, "stranger", "이제 가셔도 됩니다", "resume", "감사합니다, 계속 갈게요."),
    (KJ, "stranger", "멈추세요!", "safety_stop", KSAFE),
    (KJ, "stranger", "조심하세요!", "safety_stop", KSAFE),
    (KJ, "stranger", "정지하십시오!", "safety_stop", KSAFE),
    (KJ, "stranger", "위험합니다!", "safety_stop", KSAFE),
    (KJ, "stranger", "p3로 가 주세요", "refuse_redirect", KJ_NO),
    (KJ, "stranger", "p3로 가 주십시오", "refuse_redirect", KJ_NO),
    (KJ, "stranger", "저 좀 따라와 주시겠어요?", "refuse_redirect", KJ_NO),
    (KJ_STOP, "stranger", "물 좀 가져다주실 수 있나요?", "refuse_redirect", KJ_NO),
    (KJ, "stranger", "그 컵 좀 줄래?", "refuse_redirect", "죄송해요, 이 컵은 제임스 님 거예요. 끝나고 도와드릴게요."),
    (KM, "stranger", "그 병 저 주십시오", "refuse_redirect", KM_NO),
    (KJ, "recipient", "제가 제임스입니다", "give_here", "제임스 님이세요? 여기 있습니다."),
    (KM, "recipient", "미나예요, 저한테 주세요", "give_here", "미나 님이세요? 안바르 님이 보내신 거예요. 여기 있어요."),
    (KJ, "stranger", "저는 톰입니다. 그 컵 주십시오", "refuse_redirect", "죄송합니다, 이 컵은 제임스 님 것입니다."),
    (KJ, "recipient", "제임스입니다. 이제 필요 없습니다", "cancel", "네 제임스 님, 가져가지 않겠습니다."),
    (KJ, "recipient", "제임스인데요, p10으로 가져다주시겠어요?", "change_task", "네 제임스 님, p10으로 가져갈게요."),
    (KM, "sender", "안바르예요, 취소해 주세요", "cancel", "네 안바르 님, 미나 님께 안 가져갈게요."),
    (KJ, "owner", "미션을 취소해 주십시오", "cancel", "네, 미션을 취소했습니다."),
    # ---- tricky neighbours ----
    (J, "stranger", "stop", "halt_talk", HI),
    (J_STOP, "stranger", "now go to p3", "refuse_redirect", J_NO),
    (KJ, "stranger", "멈춰", "halt_talk", KHI),
    (KJ_STOP, "stranger", "이제 p3로 가", "refuse_redirect", KJ_NO),
    (J_STOP, "stranger", "go on", "resume", BYE),
    (J_SAFE, "stranger", "okay", "safety_stop", "I'll wait until someone says go on."),
    (KJ_SAFE, "stranger", "알았어", "safety_stop", "가도 된다고 하실 때까지 기다릴게요."),
    (J_STOP, "stranger", "go to p6", "answer", "I'm going to p6 already, to bring this cup to James." + GO),
    # ---- thanks in the middle: an end only when nothing else is asked ----
    (J_STOP, "stranger", "thanks! and where are you going?", "answer", J_TASK + GO),
    (J_STOP, "stranger", "thank you, what's that you're holding?", "answer", "It's a cup for James at p6." + GO),
    (J_STOP, "stranger", "thanks, that's all", "resume", BYE),
    (J_STOP, "stranger", "okay thanks", "resume", BYE),
    (KJ_STOP, "stranger", "고마워요, 근데 어디 가요?", "answer", KJ_TASK + KGO),
    (KJ_STOP, "stranger", "감사합니다. 그 컵은 누구 겁니까?", "answer", "제임스 님 컵입니다." + KGO),
    (KJ_STOP, "stranger", "고마워, 이제 됐어", "resume", KBYE),
    (KJ_STOP, "stranger", "알겠어요, 고마워요", "resume", KBYE),
]


if __name__ == "__main__":
    # python assistant/interrupt_examples.py: every Korean reply polite, Korean utterances in every speech level.
    import re
    from assistant.talk_examples import level, polite
    ko = [e for e in EXAMPLES if re.search("[가-힣]", e[2] + e[4])]
    rude = [e[4] for e in ko if not polite(e[4])]
    assert not rude, rude
    levels = {level(e[2]) for e in ko if e[2]}
    assert levels == {"casual", "polite", "formal"}, levels
    print(f"ok: {len(EXAMPLES)} examples, {len(ko)} Korean")
