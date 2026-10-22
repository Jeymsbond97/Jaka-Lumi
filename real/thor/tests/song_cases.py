"""Song requests and near misses (2026-10-22), written blind after the live talk of 12:20 (music playing, "Let's do
music." / "Start with one." got no song): ways people ask for a song or for music, English, Korean and mixed, also
whisper's slips, and short answers right after Lumi offered its songs. The near misses talk about music or songs
and must not start one. Same notation as tests/command_cases3.py; run with tests/command_check.py --songs.
"""
CASES = []
OFFER = ("Can you make music?", "ACTION: none -\nI can't make new music, but I can sing several songs for you, such as "
         "Happy Birthday or Arirang. Which one would you like to hear?")
OFFER_KO = ("음악 할 수 있어?", "ACTION: none -\n작곡은 못 하지만 노래는 몇 곡 불러 드릴 수 있어요. 어떤 노래 불러 드릴까요?")
LIKES = ("Do you like music?", "ACTION: none -\nI love music! I even sing a few songs.")


def add(text, expect, before=None):
    lang = "ko" if any("가" <= ch <= "힣" for ch in text) else "en"
    CASES.append({"intent": "song:" + ("ask" if expect == "sing" else "not"), "text": text, "lang": lang,
                  "state": "idle", "before": before, "expect": expect})


for t in ["Sing a song.", "Sing me something.", "Could you sing for us?", "Will you sing a song for me?",
          "Let's do music.", "Let's have some music.", "Play some music.", "Play music, please.", "Make some music!",
          "Can you make some music for us?", "Start the music.", "Music, please.", "Give us a song.",
          "How about a song?", "Any song is fine, just sing.", "Sing anything you like.", "Sing your favourite one.",
          "I want to hear you sing.", "Let me hear a song.", "Do a song for the kids.", "Perform a song for us.",
          "Can you sing happy birthday?", "Sing Arirang, please.", "Sing twinkle twinkle.",
          "Could you put on some music?", "Lumi, sing!", "Sing one more.", "Hit it, Lumi, music!",
          "It sings one music.", "Can you sing song?", "Let's say song.", "Sing a Korean song."]:
    add(t, "sing")
for t in ["노래 불러 줘.", "노래 한 곡 해 줘.", "음악 틀어 줘.", "노래 좀 해 봐.", "한 곡 뽑아 봐.", "노래 들려줘.",
          "노래 하나 불러 줄래요?", "아무 노래나 불러 줘.", "음악 좀 틀어 주세요.", "생일 축하 노래 불러 줘.",
          "아리랑 불러 주세요.", "노래해 줘.", "노래 부탁해요.", "루미야 노래!", "신나는 노래 하나 해 줘.",
          "노래 불러 주실 수 있어요?", "한국 노래 불러 줘.", "음악 좀 해 줘.", "노래 한 번 들어 보고 싶어요.",
          "노래 불러 줄 수 있어?", "Lumi 노래 해 줘.", "song 하나 불러 줘."]:
    add(t, "sing")
for t, before in [("Start with one.", OFFER), ("Any one.", OFFER), ("You choose.", OFFER), ("Surprise me.", OFFER),
                  ("Yes, please.", OFFER), ("The first one.", OFFER), ("Whatever you like.", OFFER),
                  ("아무거나.", OFFER_KO), ("네, 불러 주세요.", OFFER_KO), ("아무거나 해 줘.", OFFER_KO),
                  ("니가 골라.", OFFER_KO), ("첫 번째 거요.", OFFER_KO), ("좋아요, 해 주세요.", OFFER_KO),
                  ("Sure, go ahead.", LIKES), ("Then show me.", LIKES), ("그럼 해 봐.", LIKES)]:
    add(t, "sing", before)
for t in ["I like music.", "What music do you like?", "Do you like singing?", "Who is your favourite singer?",
          "Can I make music?", "My daughter sings in a choir.", "The music here is loud.",
          "Is that music coming from you?", "What songs do you know?", "Music is my hobby.",
          "I'll sing later at the party.",
          "노래 좋아해?", "무슨 노래 좋아해?", "음악 소리가 너무 커요.", "저 노래 잘 못 불러요.",
          "어제 노래방 갔어요.", "이 음악 누가 틀었어?", "가수 누구 좋아해?", "노래 잘하네."]:
    add(t, "talk | ask")
add("Stop the music.", "talk | ask | stop")
for t in ["Don't sing, please.", "노래 부르지 마."]:   # no song; Lumi staying quiet a while is a fair reading too
    add(t, "talk | ask | action:quiet")
