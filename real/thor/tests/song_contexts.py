"""The turn before a song case (brain history: what was said, Lumi's action line and answer), for
tests/song_cases_train.py / song_cases_held.py."""
OFFER = ("Can you make music?", "ACTION: none -\nI can sing a few songs for you, like Fantastic Baby or Love Attack. "
         "Want one?")
OFFER_KO = ("음악 할 수 있어?", "ACTION: none -\n판타스틱 베이비나 러브 어택 같은 노래를 불러 드릴 수 있어요. 한 곡 불러 드릴까요?")
LISTED = ("What songs do you know?", "ACTION: none songs\nI can sing BAD, Fantastic Baby, Did I Become the Adult I "
          "Dreamed Of and Love Attack. Which one would you like?")
LISTED_KO = ("무슨 노래 알아?", "ACTION: none songs\n배드, 판타스틱 베이비, 꿈꾸던 어른이 되었나요, 러브 어택을 부를 수 있어요. "
             "어떤 노래 불러 드릴까요?")
SANG = ("Sing a song.", "ACTION: sing RESCENE_LOVE_ATTACK")
SANG_SONG = "RESCENE_LOVE_ATTACK"
UNKNOWN_SAID = ("Sing Yesterday.", "ACTION: none songs\nSorry, I can't sing that one. I only know my own songs: BAD, "
                "Fantastic Baby, Did I Become the Adult I Dreamed Of and Love Attack. Want one of them?")
