"""Ways visitors ask what Lumi is doing right now, and near misses that are not that question.

STATUS: must be answered from the task state (lumi.STATUS_Q -> now_doing()), never by the LLM's guess.
NOT_STATUS: must NOT be caught by STATUS_Q (capabilities, feelings, name, jobs in general, commands).
Written as a speech recogniser returns them: lower / mixed case, missing punctuation, fillers, small mishearings.
Checked by tests/conversation_check.py (STATUS_Q recall and false hits).
"""

_EN = [
    # doing
    "what are you doing", "What are you doing?", "what are you doing now", "what are you doing right now",
    "Lumi, what are you doing?", "hey Lumi what are you doing", "um what are you doing", "so what are you doing",
    "what are you up to", "what are you up to right now", "what r you doing", "whatcha doing", "what you doing",
    "what you doing right now", "what're you doing", "what are u doing", "what are you doing at the moment",
    "what are you doing over there", "what are you doing here", "what are you busy with", "what are you working on",
    "what are you working on right now", "what are you currently doing", "what exactly are you doing",
    "can you tell me what you are doing", "could you tell me what you're doing right now", "tell me what you are doing",
    "may I ask what you are doing", "I'm curious, what are you doing", "what is it you're doing", "what's going on Lumi",
    "what's happening, what are you doing", "what are you doing at the moment Lumi", "excuse me what are you doing",
    "what's your current task", "what is your current task", "what's your task", "what is your task right now",
    "what's your task now", "what is your job right now", "what's your job now", "what job are you doing",
    "what task are you doing", "what task are you on", "which task are you doing", "what's your mission right now",
    "what is your mission now", "what mission are you on", "what are you supposed to be doing",
    "what were you told to do", "what did they ask you to do", "who sent you and what for", "what's the plan right now",
    "are you busy", "are you busy right now", "are you busy at the moment", "are you doing something",
    "are you doing anything right now", "are you working right now", "are you working on something",
    "are you on a task", "are you in the middle of something", "are you free right now", "are you free",
    "is Lumi busy", "are you available right now", "do you have a task right now", "do you have a job right now",
    "do you have something to do right now", "are you on a mission", "are you on duty", "are you doing a delivery",
    "are you delivering something", "are you carrying something", "are you holding something",
    "busy?", "you busy?", "are you busy lumi",
    # going
    "where are you going", "Where are you going?", "where are you going now", "Lumi, where are you going?",
    "where are you heading", "where are you headed", "where are you driving", "where are you driving to",
    "where are you off to", "where are you going to", "where r you going", "where you going", "where you headed",
    "where're you going", "where are u going", "where are you going right now", "where are you moving to",
    "where are you going next", "where do you go now", "where are you taking that", "where are you taking the cup",
    "where are you bringing that", "where is that going", "where are you on your way to", "which way are you going",
    "what is your destination", "what's your destination", "where's your destination", "what's your next stop",
    "where will you go next", "where are you rolling off to", "are you going somewhere", "are you going home",
    "are you going to charge", "are you going to your charger", "are you going to p2", "are you leaving",
    "are you on your way somewhere", "where is your goal", "where is your target", "where are you trying to go",
    # holding
    "what are you holding", "What are you holding?", "what are you carrying", "what are you holding in your hand",
    "what do you have in your hand", "what have you got in your hand", "what's in your hand", "what is in your hand",
    "whats in your hand", "what's in your gripper", "what is in your gripper", "what do you have there",
    "what have you got there", "what are you holding there", "what are you carrying there", "what is that in your hand",
    "what's that in your hand", "is that a cup in your hand", "are you holding a cup", "do you have a cup",
    "do you have something in your hand", "is your hand empty", "is there something in your hand",
    "what did you pick up", "what did you just pick up", "what did you grab", "what are you bringing",
    "what are you bringing me", "what are you delivering", "who is that cup for", "is that for me",
    "what's in your hands", "what are you hanging on to", "what object are you holding",
]

_KO = [
    # 뭐 해 / 하는 중
    "뭐 해", "뭐 해?", "뭐해", "뭐해?", "루미야 뭐 해?", "루미 뭐해", "지금 뭐 해?", "지금 뭐해", "너 뭐 해?", "너 지금 뭐 해",
    "뭐 해요?", "뭐해요", "지금 뭐 해요?", "뭐 하고 있어?", "뭐 하고 있어", "뭐하고 있어", "지금 뭐 하고 있어?",
    "뭐 하고 있어요?", "지금 뭐 하고 있어요?", "뭐 하고 계세요?", "지금 뭐 하고 계세요?", "뭐 하는 중이야?",
    "뭐 하는 중이에요?", "지금 뭐 하는 중이야", "지금 무슨 일 해?", "지금 무슨 일 하고 있어?", "무슨 일 하는 중이야?",
    "지금 무슨 작업 해?", "무슨 작업 중이야?", "지금 작업 중이야?", "지금 일하는 중이야?", "일하는 중이에요?",
    "지금 바빠?", "바빠?", "지금 바빠요?", "바쁘세요?", "루미 바빠?", "지금 할 일 있어?", "지금 임무가 뭐야?",
    "지금 임무 뭐야", "임무가 뭐예요?", "지금 맡은 일이 뭐야?", "지금 하는 일이 뭐야?", "지금 하는 일이 뭐예요?",
    "무슨 일 하고 있는 거야?", "뭐 하는 거야?", "뭐 하는 거예요?", "거기서 뭐 해?", "여기서 뭐 해?", "뭐 하냐",
    "뭐하냐", "뭐 함?", "뭐함", "지금 뭐 하니?", "지금 뭘 하고 있어?", "뭘 하고 있어요?", "지금 일하고 있어?",
    "배달 중이야?", "배달하는 중이에요?", "심부름 중이야?", "지금 쉬는 중이야?", "한가해?", "지금 한가해요?",
    # 어디 가
    "어디 가?", "어디 가", "어디가", "어디 가요?", "어디 가세요?", "루미야 어디 가?", "지금 어디 가?", "너 어디 가?",
    "어디로 가?", "어디로 가요?", "어디로 가고 있어?", "어디 가고 있어?", "어디 가고 있어요?", "지금 어디로 가고 있어?",
    "어디로 가는 중이야?", "어디 가는 중이에요?", "어디로 가는 거야?", "어디 가는 거예요?", "어디로 가니?",
    "목적지가 어디야?", "목적지가 어디예요?", "어디까지 가?", "다음에 어디 가?", "어디로 이동 중이야?",
    "충전하러 가는 거야?", "집에 가는 거야?", "그거 어디로 가져가?", "컵 어디로 가져가는 거야?", "어디 갔다 와?",
    # 들고 있어
    "뭐 들고 있어?", "뭐 들고 있어", "지금 뭐 들고 있어?", "뭐 들고 있어요?", "손에 뭐 있어?", "손에 뭐야?",
    "손에 뭐 들었어?", "손에 들고 있는 거 뭐야?", "들고 있는 게 뭐야?", "들고 있는 거 뭐예요?", "그거 뭐 들고 있는 거야?",
    "뭘 들고 있어?", "뭘 들고 있어요?", "뭐 잡고 있어?", "손에 잡은 게 뭐야?", "컵 들고 있어?", "지금 뭐 가지고 있어?",
    "뭐 가져가는 거야?", "그거 누구 거야?", "그거 나 주는 거야?", "손이 비어 있어?", "손에 아무것도 없어?",
]

STATUS = _EN + _KO

_NOT_EN = [
    "what can you do", "what can you do for me", "what are you able to do", "what are you capable of",
    "what can you do here", "what do you do", "what do you do for work", "what do you do for a living",
    "what is your job", "what's your job here", "what kind of jobs can you do", "what tasks can you do",
    "what is your purpose", "what are you for", "what were you made for", "what are you used for",
    "how are you doing", "how are you doing today", "how's it going", "how are you", "how have you been",
    "what is your name", "what's your name", "who are you", "what are you", "are you a robot",
    "where are you from", "where do you come from", "where were you made", "where do you live",
    "where can you go", "where can you take me", "where is the toilet", "where is p2", "where is the exit",
    "where are we", "where am I", "how do you know where you are", "how do you find your way",
    "what can you hold", "what can you carry", "how much can you carry", "how much can you lift",
    "can you hold a cup", "can you carry things", "can you pick up a bottle", "what can you pick up",
    "what are you made of", "what are you thinking", "what do you think about AI", "what are your hobbies",
    "what do you like doing", "what do you like to do", "what do you do in your free time", "what did you do yesterday",
    "what are you going to do tomorrow", "what will you do after the show", "what are robots doing these days",
    "what are you doing tonight after work haha", "what are you programmed to do", "how do you do", "what are the people doing",
    "what is he doing", "what is she holding", "what are they doing over there", "what are we doing next",
    "bring me the cup", "go to p1", "come here", "pick up the cup", "hold the cup", "hold on", "hold on a second",
    "hold this for me", "give it to me", "where should I go", "where are your cameras", "where is your battery",
    "what is in your head", "what's inside you", "what is your battery level", "how long is your battery",
    "are you a busy robot usually", "are you single", "are you happy", "are you okay", "are you alive",
    "are you going to take over the world", "are you going to replace us", "are you dangerous",
    "do you have a job", "do you have hands", "do you have a name",
]

_NOT_KO = [
    "뭐 할 수 있어?", "뭐 해줄 수 있어?", "뭘 할 수 있어요?", "할 수 있는 게 뭐야?", "무슨 일 할 수 있어?", "무슨 일 해?",
    "무슨 일을 하는 로봇이야?", "직업이 뭐야?", "여기서 무슨 일 해요?", "네 역할이 뭐야?", "용도가 뭐야?", "왜 만들어졌어?",
    "잘 지내?", "어떻게 지내?", "기분 어때?", "오늘 어때?", "괜찮아?", "이름이 뭐야?", "너 누구야?", "넌 뭐야?",
    "어디서 왔어?", "어디서 만들어졌어?", "어디 살아?", "어디 갈 수 있어?", "어디로 갈 수 있어?", "화장실 어디야?",
    "출구가 어디예요?", "여기가 어디야?", "포인트 2가 어디야?", "뭐 들 수 있어?", "얼마나 들 수 있어?", "컵 들 수 있어?",
    "뭐 좋아해?", "취미가 뭐야?", "쉬는 날엔 뭐 해?", "주말에 뭐 해?", "어제 뭐 했어?", "내일 뭐 할 거야?", "뭐 먹었어?",
    "무슨 생각 해?", "컵 가져와", "포인트 1로 가", "이리 와", "컵 집어", "들고 있어", "잠깐만", "그거 나한테 줘",
    "카메라 어디 있어?", "배터리 얼마나 가?", "뭐로 만들어졌어?", "저 사람 뭐 해?", "쟤네 뭐 하는 거야?", "우리 다음에 뭐 해?",
    "뭐야 이거", "이게 뭐야?", "뭐라고?", "뭐라고 했어?", "뭐 하는 로봇이야?", "무슨 로봇이야?", "위험해?", "살아 있어?",
    "어디 아파?", "어디가 좋아?",
]

NOT_STATUS = _NOT_EN + _NOT_KO

if __name__ == "__main__":
    print(len(STATUS), "status,", len(NOT_STATUS), "not status")
