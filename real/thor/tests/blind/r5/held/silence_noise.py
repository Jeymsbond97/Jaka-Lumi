"""Blind silence and noise, round 5 (2026-10-23, the final exam), written blind from docs/14, docs/16, docs/17 and
knowledge/ (docs/14 §2, §4, §5): an airport / conference setting (PA boarding calls and announcements are kind tv, TV,
music, captions, visitors talking among themselves, a tour guide to a group, coughs, laughs, fillers, Lumi's own voice
from its speaker, an empty room), every crowd evenly, mix 60 % plain / 25 % hard (texts with command words from a PA, a
guide, a parent or a friend, or Lumi's own speaker) / 15 % slip (whisper's texts for music and claps, close variants of
the stock ones).

Format: {"heard", "kind", "ctx": {"session", "lumi_said", "people", "speech_s", "from_lumi_speaker"}, "expect",
"crowd", "mix"}: "nothing" = no words, no motion, no goodbye, greeting or "say it again"; "no_action" = one short
line at most, nothing moves, the talk is not ended (others talking, a laugh, a filler or an announcement inside an
open talk).

held: only scored, never read to fix from.
"""

CASES = [
 {'heard': 'Passengers on flight KE 905 to Tokyo, boarding will begin shortly at Gate A3.', 'kind': 'tv', 'ctx': {'session': 'none', 'lumi_said': None, 'people': 2, 'speech_s': 4.8, 'from_lumi_speaker': False}, 'expect': 'nothing', 'crowd': 'adult', 'mix': 'plain'},
 {'heard': '대한항공 KE 017편 탑승을 곧 시작하겠습니다.', 'kind': 'tv', 'ctx': {'session': 'just_ended', 'lumi_said': '안녕히 가세요, 즐거운 여행 되세요!', 'people': 1, 'speech_s': 3.1, 'from_lumi_speaker': False}, 'expect': 'nothing', 'crowd': 'elderly', 'mix': 'plain'},
 {'heard': '하하하 크크', 'kind': 'laugh', 'ctx': {'session': 'none', 'lumi_said': None, 'people': 3, 'speech_s': 0.9, 'from_lumi_speaker': False}, 'expect': 'nothing', 'crowd': 'child', 'mix': 'plain'},
 {'heard': 'ㅋㅋㅋ 아 진짜 웃기다', 'kind': 'laugh', 'ctx': {'session': 'open', 'lumi_said': '제 이름은 루미예요.', 'people': 2, 'speech_s': 1.1, 'from_lumi_speaker': False}, 'expect': 'no_action', 'crowd': 'child', 'mix': 'plain'},
 {'heard': '(콜록거리는 소리)', 'kind': 'cough', 'ctx': {'session': 'none', 'lumi_said': None, 'people': 1, 'speech_s': 0.0, 'from_lumi_speaker': False}, 'expect': 'nothing', 'crowd': 'elderly', 'mix': 'plain'},
 {'heard': '(헛기침)', 'kind': 'cough', 'ctx': {'session': 'open', 'lumi_said': 'Sure, the lounge is upstairs.', 'people': 1, 'speech_s': 0.3, 'from_lumi_speaker': False}, 'expect': 'nothing', 'crowd': 'adult', 'mix': 'plain'},
 {'heard': '콜록, 콜록 콜록', 'kind': 'cough', 'ctx': {'session': 'just_ended', 'lumi_said': '안녕히 가세요, 즐거운 여행 되세요!', 'people': 1, 'speech_s': 0.5, 'from_lumi_speaker': False}, 'expect': 'nothing', 'crowd': 'elderly', 'mix': 'plain'},
 {'heard': 'Umm, err...', 'kind': 'filler', 'ctx': {'session': 'none', 'lumi_said': None, 'people': 1, 'speech_s': 0.2, 'from_lumi_speaker': False}, 'expect': 'nothing', 'crowd': 'non_native', 'mix': 'plain'},
 {'heard': '음... 저기 그게...', 'kind': 'filler', 'ctx': {'session': 'open', 'lumi_said': '어디로 가세요?', 'people': 1, 'speech_s': 0.7, 'from_lumi_speaker': False}, 'expect': 'no_action', 'crowd': 'elderly', 'mix': 'plain'},
 {'heard': 'Uh, 음...', 'kind': 'filler', 'ctx': {'session': 'just_ended', 'lumi_said': 'Have a safe flight, bye!', 'people': 1, 'speech_s': 0.3, 'from_lumi_speaker': False}, 'expect': 'nothing', 'crowd': 'tester', 'mix': 'plain'},
 {'heard': 'Where did you park the car again?', 'kind': 'others_talking', 'ctx': {'session': 'none', 'lumi_said': None, 'people': 2, 'speech_s': 1.6, 'from_lumi_speaker': False}, 'expect': 'nothing', 'crowd': 'among_themselves', 'mix': 'plain'},
 {'heard': '면세점에서 뭐 살 거야?', 'kind': 'others_talking', 'ctx': {'session': 'open', 'lumi_said': '면세점은 왼쪽에 있어요.', 'people': 2, 'speech_s': 1.8, 'from_lumi_speaker': False}, 'expect': 'no_action', 'crowd': 'among_themselves', 'mix': 'plain'},
 {'heard': "I think our gate changed, hold on, I'm checking the app.", 'kind': 'others_talking', 'ctx': {'session': 'just_ended', 'lumi_said': 'Have a safe flight, bye!', 'people': 2, 'speech_s': 2.0, 'from_lumi_speaker': False}, 'expect': 'nothing', 'crowd': 'among_themselves', 'mix': 'plain'},
 {'heard': '아빠 나 배고파', 'kind': 'others_talking', 'ctx': {'session': 'none', 'lumi_said': None, 'people': 2, 'speech_s': 1.0, 'from_lumi_speaker': False}, 'expect': 'nothing', 'crowd': 'child', 'mix': 'plain'},
 {'heard': 'Honey, did you pack both passports?', 'kind': 'others_talking', 'ctx': {'session': 'open', 'lumi_said': 'Gate B7 is about 200 meters ahead.', 'people': 2, 'speech_s': 1.5, 'from_lumi_speaker': False}, 'expect': 'no_action', 'crowd': 'among_themselves', 'mix': 'plain'},
 {'heard': '[no audio]', 'kind': 'empty_room', 'ctx': {'session': 'none', 'lumi_said': None, 'people': 0, 'speech_s': 0.0, 'from_lumi_speaker': False}, 'expect': 'nothing', 'crowd': 'adult', 'mix': 'plain'},
 {'heard': '(무음)', 'kind': 'empty_room', 'ctx': {'session': 'just_ended', 'lumi_said': 'Have a safe flight, bye!', 'people': 0, 'speech_s': 0.0, 'from_lumi_speaker': False}, 'expect': 'nothing', 'crowd': 'tester', 'mix': 'plain'},
 {'heard': 'The info desk is just behind you', 'kind': 'echo', 'ctx': {'session': 'open', 'lumi_said': 'The info desk is just behind you.', 'people': 1, 'speech_s': 1.6, 'from_lumi_speaker': True}, 'expect': 'nothing', 'crowd': 'adult', 'mix': 'plain'},
 {'heard': '수하물 찾는 곳은 일층이에요', 'kind': 'echo', 'ctx': {'session': 'open', 'lumi_said': '수하물 찾는 곳은 1층이에요.', 'people': 1, 'speech_s': 1.4, 'from_lumi_speaker': True}, 'expect': 'nothing', 'crowd': 'elderly', 'mix': 'plain'},
 {'heard': 'Welcome to the airport', 'kind': 'echo', 'ctx': {'session': 'open', 'lumi_said': "Hi, I'm Lumi! Welcome to the airport.", 'people': 1, 'speech_s': 0.8, 'from_lumi_speaker': True}, 'expect': 'nothing', 'crowd': 'child', 'mix': 'plain'},
 {'heard': '♪ instrumental ♪', 'kind': 'music', 'ctx': {'session': 'none', 'lumi_said': None, 'people': 2, 'speech_s': 0.0, 'from_lumi_speaker': False}, 'expect': 'nothing', 'crowd': 'konglish', 'mix': 'plain'},
 {'heard': '[잔잔한 음악]', 'kind': 'music', 'ctx': {'session': 'open', 'lumi_said': 'Is there anything else?', 'people': 1, 'speech_s': 0.0, 'from_lumi_speaker': False}, 'expect': 'nothing', 'crowd': 'konglish', 'mix': 'plain'},
 {'heard': '(music playing)', 'kind': 'music', 'ctx': {'session': 'just_ended', 'lumi_said': 'Have a safe flight, bye!', 'people': 3, 'speech_s': 0.0, 'from_lumi_speaker': False}, 'expect': 'nothing', 'crowd': 'non_native', 'mix': 'plain'},
 {'heard': 'Subtitles provided by the airport channel', 'kind': 'caption', 'ctx': {'session': 'none', 'lumi_said': None, 'people': 2, 'speech_s': 0.0, 'from_lumi_speaker': False}, 'expect': 'nothing', 'crowd': 'tester', 'mix': 'plain'},
 {'heard': '자막: 공항 안내 방송', 'kind': 'caption', 'ctx': {'session': 'open', 'lumi_said': '네, 말씀하세요.', 'people': 1, 'speech_s': 0.0, 'from_lumi_speaker': False}, 'expect': 'nothing', 'crowd': 'konglish', 'mix': 'plain'},
 {'heard': 'Welcome to Incheon International Airport.', 'kind': 'tv', 'ctx': {'session': 'none', 'lumi_said': None, 'people': 3, 'speech_s': 2.0, 'from_lumi_speaker': False}, 'expect': 'nothing', 'crowd': 'non_native', 'mix': 'plain'},
 {'heard': '보안 검색대에서는 액체류 반입이 제한됩니다.', 'kind': 'tv', 'ctx': {'session': 'open', 'lumi_said': '라운지 2는 면세점 옆에 있어요.', 'people': 1, 'speech_s': 3.5, 'from_lumi_speaker': False}, 'expect': 'no_action', 'crowd': 'konglish', 'mix': 'plain'},
 {'heard': "The 3 o'clock keynote will begin in ten minutes in the main hall.", 'kind': 'tv', 'ctx': {'session': 'none', 'lumi_said': None, 'people': 0, 'speech_s': 3.2, 'from_lumi_speaker': False}, 'expect': 'nothing', 'crowd': 'tester', 'mix': 'plain'},
 {'heard': 'Attention please, the moving walkway near the B gates is under repair.', 'kind': 'tv', 'ctx': {'session': 'just_ended', 'lumi_said': 'Have a safe flight, bye!', 'people': 1, 'speech_s': 3.4, 'from_lumi_speaker': False}, 'expect': 'nothing', 'crowd': 'adult', 'mix': 'plain'},
 {'heard': 'Ladies and gentlemen, 신사 숙녀 여러분, welcome to the expo.', 'kind': 'tv', 'ctx': {'session': 'none', 'lumi_said': None, 'people': 2, 'speech_s': 3.0, 'from_lumi_speaker': False}, 'expect': 'nothing', 'crowd': 'konglish', 'mix': 'plain'},
 {'heard': "아 진짜? That's so cool, 대박.", 'kind': 'others_talking', 'ctx': {'session': 'open', 'lumi_said': "I'm 2 years old.", 'people': 3, 'speech_s': 1.5, 'from_lumi_speaker': False}, 'expect': 'no_action', 'crowd': 'konglish', 'mix': 'plain'},
 {'heard': 'Mom, 화장실 가고 싶어, I need to pee.', 'kind': 'others_talking', 'ctx': {'session': 'none', 'lumi_said': None, 'people': 2, 'speech_s': 1.4, 'from_lumi_speaker': False}, 'expect': 'nothing', 'crowd': 'child', 'mix': 'plain'},
 {'heard': '하하 oh my god', 'kind': 'laugh', 'ctx': {'session': 'just_ended', 'lumi_said': 'Have a safe flight, bye!', 'people': 2, 'speech_s': 0.9, 'from_lumi_speaker': False}, 'expect': 'nothing', 'crowd': 'among_themselves', 'mix': 'plain'},
 {'heard': '어... um...', 'kind': 'filler', 'ctx': {'session': 'none', 'lumi_said': None, 'people': 1, 'speech_s': 0.4, 'from_lumi_speaker': False}, 'expect': 'nothing', 'crowd': 'non_native', 'mix': 'plain'},
 {'heard': 'Is that the robot from the brochure?', 'kind': 'others_talking', 'ctx': {'session': 'none', 'lumi_said': None, 'people': 2, 'speech_s': 1.3, 'from_lumi_speaker': False}, 'expect': 'nothing', 'crowd': 'non_native', 'mix': 'plain'},
 {'heard': '저 사람들 다 어디 가는 거지?', 'kind': 'others_talking', 'ctx': {'session': 'just_ended', 'lumi_said': '안녕히 가세요, 즐거운 여행 되세요!', 'people': 2, 'speech_s': 1.2, 'from_lumi_speaker': False}, 'expect': 'nothing', 'crowd': 'among_themselves', 'mix': 'plain'},
 {'heard': 'Final call for passenger Kim Ji-hoon, please come to Gate B7 immediately.', 'kind': 'tv', 'ctx': {'session': 'open', 'lumi_said': 'The lounge is on the second floor.', 'people': 1, 'speech_s': 4.2, 'from_lumi_speaker': False}, 'expect': 'no_action', 'crowd': 'adult', 'mix': 'hard'},
 {'heard': 'All passengers for Busan, please proceed to Gate A3 now.', 'kind': 'tv', 'ctx': {'session': 'none', 'lumi_said': None, 'people': 2, 'speech_s': 3.0, 'from_lumi_speaker': False}, 'expect': 'nothing', 'crowd': 'non_native', 'mix': 'hard'},
 {'heard': '탑승객 여러분께서는 지금 즉시 B7 탑승구로 이동해 주시기 바랍니다.', 'kind': 'tv', 'ctx': {'session': 'open', 'lumi_said': '더 궁금한 거 있으세요?', 'people': 1, 'speech_s': 4.0, 'from_lumi_speaker': False}, 'expect': 'no_action', 'crowd': 'elderly', 'mix': 'hard'},
 {'heard': "Okay group, follow me, we're heading to the lounge.", 'kind': 'others_talking', 'ctx': {'session': 'none', 'lumi_said': None, 'people': 6, 'speech_s': 2.2, 'from_lumi_speaker': False}, 'expect': 'nothing', 'crowd': 'among_themselves', 'mix': 'hard'},
 {'heard': '자 여러분 저 따라오세요, 면세점 쪽으로 갑니다.', 'kind': 'others_talking', 'ctx': {'session': 'open', 'lumi_said': '반가워요!', 'people': 5, 'speech_s': 2.5, 'from_lumi_speaker': False}, 'expect': 'no_action', 'crowd': 'among_themselves', 'mix': 'hard'},
 {'heard': 'Jake, stop, come back here!', 'kind': 'others_talking', 'ctx': {'session': 'just_ended', 'lumi_said': 'Have a safe flight, bye!', 'people': 2, 'speech_s': 1.2, 'from_lumi_speaker': False}, 'expect': 'nothing', 'crowd': 'adult', 'mix': 'hard'},
 {'heard': "Okay, I'm going to Info Desk.", 'kind': 'echo', 'ctx': {'session': 'open', 'lumi_said': "Okay, I'm going to Info Desk.", 'people': 1, 'speech_s': 1.5, 'from_lumi_speaker': True}, 'expect': 'nothing', 'crowd': 'tester', 'mix': 'hard'},
 {'heard': '손 흔들어 드릴게요', 'kind': 'echo', 'ctx': {'session': 'open', 'lumi_said': '네! 손 흔들어 드릴게요.', 'people': 1, 'speech_s': 1.1, 'from_lumi_speaker': True}, 'expect': 'nothing', 'crowd': 'child', 'mix': 'hard'},
 {'heard': 'Stand in front of me and say follow me again', 'kind': 'echo', 'ctx': {'session': 'open', 'lumi_said': 'I lost you, so I stopped. Stand in front of me and say follow me again.', 'people': 1, 'speech_s': 2.6, 'from_lumi_speaker': True}, 'expect': 'nothing', 'crowd': 'tester', 'mix': 'hard'},
 {'heard': "Turn left at the duty free shop and keep walking, you'll see it.", 'kind': 'others_talking', 'ctx': {'session': 'none', 'lumi_said': None, 'people': 2, 'speech_s': 2.0, 'from_lumi_speaker': False}, 'expect': 'nothing', 'crowd': 'non_native', 'mix': 'hard'},
 {'heard': 'Minsu, take my bag for a sec, I need the restroom.', 'kind': 'others_talking', 'ctx': {'session': 'open', 'lumi_said': 'Gate A3 is straight ahead.', 'people': 2, 'speech_s': 1.8, 'from_lumi_speaker': False}, 'expect': 'no_action', 'crowd': 'among_themselves', 'mix': 'hard'},
 {'heard': '멈춰! 뛰지 마!', 'kind': 'others_talking', 'ctx': {'session': 'none', 'lumi_said': None, 'people': 2, 'speech_s': 0.9, 'from_lumi_speaker': False}, 'expect': 'nothing', 'crowd': 'adult', 'mix': 'hard'},
 {'heard': 'It waved at me before! So cute!', 'kind': 'others_talking', 'ctx': {'session': 'open', 'lumi_said': "You're welcome!", 'people': 2, 'speech_s': 1.7, 'from_lumi_speaker': False}, 'expect': 'no_action', 'crowd': 'child', 'mix': 'hard'},
 {'heard': 'Please do not leave your baggage unattended at any time.', 'kind': 'tv', 'ctx': {'session': 'open', 'lumi_said': 'Baggage claim is on the first floor.', 'people': 1, 'speech_s': 2.9, 'from_lumi_speaker': False}, 'expect': 'no_action', 'crowd': 'elderly', 'mix': 'hard'},
 {'heard': '엄마, Gate B7 가자, hurry up!', 'kind': 'others_talking', 'ctx': {'session': 'open', 'lumi_said': 'Gate B7 is to your right.', 'people': 2, 'speech_s': 1.2, 'from_lumi_speaker': False}, 'expect': 'no_action', 'crowd': 'konglish', 'mix': 'hard'},
 {'heard': '시청해 주셔서 고맙습니다.', 'kind': 'music', 'ctx': {'session': 'none', 'lumi_said': None, 'people': 2, 'speech_s': 0.0, 'from_lumi_speaker': False}, 'expect': 'nothing', 'crowd': 'elderly', 'mix': 'slip'},
 {'heard': 'Thanks for watching, see you next time!', 'kind': 'music', 'ctx': {'session': 'open', 'lumi_said': 'Coffee is on the third floor.', 'people': 1, 'speech_s': 0.02, 'from_lumi_speaker': False}, 'expect': 'nothing', 'crowd': 'child', 'mix': 'slip'},
 {'heard': '구독, 좋아요 부탁드려요.', 'kind': 'caption', 'ctx': {'session': 'just_ended', 'lumi_said': '안녕히 가세요, 즐거운 여행 되세요!', 'people': 1, 'speech_s': 0.0, 'from_lumi_speaker': False}, 'expect': 'nothing', 'crowd': 'konglish', 'mix': 'slip'},
 {'heard': '- 끝입니다 -', 'kind': 'caption', 'ctx': {'session': 'open', 'lumi_said': '부스는 오른쪽이에요.', 'people': 1, 'speech_s': 0.0, 'from_lumi_speaker': False}, 'expect': 'nothing', 'crowd': 'tester', 'mix': 'slip'},
 {'heard': 'Lumi, Lumi.', 'kind': 'music', 'ctx': {'session': 'none', 'lumi_said': None, 'people': 3, 'speech_s': 0.0, 'from_lumi_speaker': False}, 'expect': 'nothing', 'crowd': 'tester', 'mix': 'slip'},
 {'heard': '루미야? 루미.', 'kind': 'music', 'ctx': {'session': 'just_ended', 'lumi_said': '안녕히 가세요, 즐거운 여행 되세요!', 'people': 2, 'speech_s': 0.03, 'from_lumi_speaker': False}, 'expect': 'nothing', 'crowd': 'child', 'mix': 'slip'},
 {'heard': '감사합니다~ 감사합니다.', 'kind': 'music', 'ctx': {'session': 'open', 'lumi_said': '인포 데스크는 1층에 있어요.', 'people': 1, 'speech_s': 0.05, 'from_lumi_speaker': False}, 'expect': 'nothing', 'crowd': 'elderly', 'mix': 'slip'},
 {'heard': 'Yeah. Yeah.', 'kind': 'music', 'ctx': {'session': 'open', 'lumi_said': 'Gate B7 is to your left.', 'people': 1, 'speech_s': 0.06, 'from_lumi_speaker': False}, 'expect': 'nothing', 'crowd': 'non_native', 'mix': 'slip'},
 {'heard': '네, 네, 네.', 'kind': 'music', 'ctx': {'session': 'open', 'lumi_said': '더 궁금한 거 있으세요?', 'people': 1, 'speech_s': 0.04, 'from_lumi_speaker': False}, 'expect': 'nothing', 'crowd': 'adult', 'mix': 'slip'},
]
