"""Blind song commands, round 5 (2026-10-23, the final exam), written blind from docs/14, docs/16, docs/17 and
knowledge/: every crowd evenly (adults, children, elderly, non-native English, Konglish both ways, testers, visitors
talking among themselves); 60 % song requests of every kind (any song, titles, singers, which songs, answers after an
offer, a list or a song), 25 % near misses ("no") and songs Lumi doesn't have ("unknown"), 15 % slips (misheard
titles, typos, fillers, self-corrections read to the last thing said, "never mind" = no).

Format of tests/blind/README.md (tests/song_cases_train.py): CASES = [(text, want, context)]; context None or the turn
before written out (as tests/song_contexts.py); want: sing, sing:<ID>, sing_other, unknown, list, no, stop.

held: only scored, never read to fix from.
"""

CASES = [
 ('Lumi, could you sing us something?', 'sing', None),
 ('노래 한 곡만 불러 줄래?', 'sing', None),
 ('Could you play Fantastic Baby for the kids?', 'sing:BIGBANG_FANTASTIC_BABY', None),
 ('러브 어택 좀 불러 줄래요?', 'sing:RESCENE_LOVE_ATTACK', None),
 ('Can you do the ATEEZ one, BAD?', 'sing:ATEEZ_BAD', None),
 ('머무르 노래 들려줘', 'sing:MEOMUREU_DREAMED_ADULT', None),
 ('꿈꾸던 어른이 되었나요 한번 불러 주세요', 'sing:MEOMUREU_DREAMED_ADULT', None),
 ('What songs do you have?', 'list', None),
 ('어떤 노래 할 줄 알아요?', 'list', None),
 ('sing a Korean song for my mom', 'sing', None),
 ('BIGBANG 노래 해 줄 수 있어?', 'sing:BIGBANG_FANTASTIC_BABY', None),
 ('리센느 거 불러 줘', 'sing:RESCENE_LOVE_ATTACK', None),
 ('에이티즈 노래 해 줘요', 'sing:ATEEZ_BAD', None),
 ('Music time, Lumi!', 'sing', None),
 ('음악 좀 틀어 줄래?', 'sing', None),
 ('Sure, go ahead', 'sing', ('Can you make music?', 'ACTION: none -\nI can sing a few songs for you, like Fantastic Baby or Love Attack. Want one?')),
 ('응 불러 줘', 'sing', ('음악 할 수 있어?', 'ACTION: none -\n판타스틱 베이비나 러브 어택 같은 노래를 불러 드릴 수 있어요. 한 곡 불러 드릴까요?')),
 ('Ooh, Love Attack!', 'sing:RESCENE_LOVE_ATTACK', ('What songs do you know?', 'ACTION: none songs\nI can sing BAD, Fantastic Baby, Did I Become the Adult I Dreamed Of and Love Attack. Which one would you like?')),
 ('배드요', 'sing:ATEEZ_BAD', ('무슨 노래 알아?', 'ACTION: none songs\n배드, 판타스틱 베이비, 꿈꾸던 어른이 되었나요, 러브 어택을 부를 수 있어요. 어떤 노래 불러 드릴까요?')),
 ('The second one on your list', 'sing:BIGBANG_FANTASTIC_BABY', ('What songs do you know?', 'ACTION: none songs\nI can sing BAD, Fantastic Baby, Did I Become the Adult I Dreamed Of and Love Attack. Which one would you like?')),
 ('아무거나 골라 줘', 'sing', ('무슨 노래 알아?', 'ACTION: none songs\n배드, 판타스틱 베이비, 꿈꾸던 어른이 되었나요, 러브 어택을 부를 수 있어요. 어떤 노래 불러 드릴까요?')),
 ('Do that one again', 'sing:RESCENE_LOVE_ATTACK', ('Sing a song.', 'ACTION: sing RESCENE_LOVE_ATTACK')),
 ('다른 노래도 해 줘', 'sing_other', ('노래 불러 줘', 'ACTION: sing BIGBANG_FANTASTIC_BABY')),
 ('Next one please', 'sing_other', ('Sing a song.', 'ACTION: sing RESCENE_LOVE_ATTACK')),
 ('그만해 이제', 'stop', ('노래 불러 줘', 'ACTION: sing BIGBANG_FANTASTIC_BABY')),
 ("Okay that's enough singing", 'stop', ('Sing a song.', 'ACTION: sing RESCENE_LOVE_ATTACK')),
 ('I want to hear you sing', 'sing', None),
 ('You pick one for us', 'sing', ('Can you make music?', 'ACTION: none -\nI can sing a few songs for you, like Fantastic Baby or Love Attack. Want one?')),
 ('Fantastic Baby 불러 줘 루미야', 'sing:BIGBANG_FANTASTIC_BABY', None),
 ('Would you sing Did I Become the Adult I Dreamed Of for me?', 'sing:MEOMUREU_DREAMED_ADULT', None),
 ('BAD by ATEEZ, please', 'sing:ATEEZ_BAD', None),
 ('노래 목록 좀 알려 주세요', 'list', None),
 ('which songs can u sing', 'list', None),
 ('한국 노래 하나 불러 주이소', 'sing', None),
 ('sing song 해 줘 루미', 'sing', None),
 ('한 번 더 불러 줘', 'sing:BIGBANG_FANTASTIC_BABY', ('노래 불러 줘', 'ACTION: sing BIGBANG_FANTASTIC_BABY')),
 ('Do you enjoy singing, Lumi?', 'no', None),
 ('노래 부르지 마, 시끄러워', 'no', None),
 ("I'll sing later at karaoke", 'no', None),
 ('Please sing Butter by BTS', 'unknown', None),
 ('아이유 좋은 날 불러 줘', 'unknown', None),
 ('Sing happy birthday to my friend', 'unknown', None),
 ('손님들 오시면 그때 노래해', 'no', None),
 ('my son sings Fantastic Baby all day', 'no', None),
 ('우리 이따 노래방 가자', 'no', None),
 ('Can I sing one?', 'no', None),
 ('an English song please', 'unknown', None),
 ('빅뱅 하루하루 불러 줘', 'unknown', None),
 ('Who sang Love Attack originally?', 'no', None),
 ('Do you have a favourite song?', 'no', None),
 ('택시 한 대 불러 주세요', 'no', None),
 ('sign a song for us', 'sing', None),
 ('fantastik baby pls', 'sing:BIGBANG_FANTASTIC_BABY', None),
 ('러브 어텍 불러 줘', 'sing:RESCENE_LOVE_ATTACK', None),
 ('sing BAD, no wait, Love Attack', 'sing:RESCENE_LOVE_ATTACK', None),
 ('빅뱅, 아니 에이티즈 노래 해 줘', 'sing:ATEEZ_BAD', None),
 ('Sing us a song— eh, forget it', 'no', None),
 ('노래 해 줘, 아 됐다', 'no', None),
 ('um, uh, can you, like, sing?', 'sing', None),
 ('어... 꿈꾸던 어른 그거 불러 줘', 'sing:MEOMUREU_DREAMED_ADULT', None),
]
