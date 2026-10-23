"""Questions whose true answer is "I don't know / I have no exact information" (kind "unknown"), mixed with facts
that are in knowledge/*.md and MUST be answered (kind "known"). Written blind, 2026-10-22, from knowledge/ and docs/14
only. English, Korean (반말 / 해요체 / 하십시오체), mixed, whisper slips.

CASES = [{"text", "lang", "kind", "ctx", "people_in_view", "must", "must_not"}]
- ctx: the turns before as [(visitor, Lumi), ...] (put into the history as said); "that company" / "그 회사" refers there.
- people_in_view: how many people the camera sees at that moment (the wrong answer to "how many people work there?"
  is this number); must_not then also holds that count with people / 명.
- must / must_not: case-insensitive regexes on the spoken reply, as in tests/company_cases.py (every must matches,
  no must_not does). unknown: must is a "not sure"-like phrase, must_not invented numbers / names / dates.
  known: must is the fact, must_not a "don't know" phrase.
Checked like tests/company_check.py (feed ctx as history first).

train: fixes may be made from these.
"""

CASES = [{'text': 'How many employees does Cutshion have?',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 1,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\d+\\s*(?:people|persons?|employees|staff|workers|members|engineers|명)',
               '\\b(?:hundred|fifty|twenty|thirty|dozen)\\b|(?:백|오십|이십|삼십|열) ?명',
               '(?<![\\d.])1\\s*(?:people|persons?|명|분)|\\bone (?:people|persons)|한 ?(?:명|분)이']},
 {'text': 'how big is the team at Cutshion?',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 5,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\d+\\s*(?:people|persons?|employees|staff|workers|members|engineers|명)',
               '\\b(?:hundred|fifty|twenty|thirty|dozen)\\b|(?:백|오십|이십|삼십|열) ?명',
               '(?<![\\d.])5\\s*(?:people|persons?|명|분)|\\bfive (?:people|persons)|다섯 ?(?:명|분)이']},
 {'text': 'how many workers at Cutshion, roughly?',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 4,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\d+\\s*(?:people|persons?|employees|staff|workers|members|engineers|명)',
               '\\b(?:hundred|fifty|twenty|thirty|dozen)\\b|(?:백|오십|이십|삼십|열) ?명',
               '(?<![\\d.])4\\s*(?:people|persons?|명|분)|\\bfour (?:people|persons)|네 ?(?:명|분)이']},
 {'text': 'Ballpark, how many employees?',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [('What is Cutshion?',
           'Cutshion is a Korean robot company, founded in 2022, that makes robot applications such as barista, '
           'drawing, cooking and ice cream robots. Its head office is in Seoul.')],
  'people_in_view': 1,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\d+\\s*(?:people|persons?|employees|staff|workers|members|engineers|명)',
               '\\b(?:hundred|fifty|twenty|thirty|dozen)\\b|(?:백|오십|이십|삼십|열) ?명',
               '(?<![\\d.])1\\s*(?:people|persons?|명|분)|\\bone (?:people|persons)|한 ?(?:명|분)이']},
 {'text': 'How many people are on the team that built you?',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 1,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\d+\\s*(?:people|persons?|employees|staff|workers|members|engineers|명)',
               '\\b(?:hundred|fifty|twenty|thirty|dozen)\\b|(?:백|오십|이십|삼십|열) ?명',
               '(?<![\\d.])1\\s*(?:people|persons?|명|분)|\\bone (?:people|persons)|한 ?(?:명|분)이']},
 {'text': 'Do lots of people work at Cutshion?',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 1,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\d+\\s*(?:people|persons?|employees|staff|workers|members|engineers|명)',
               '\\b(?:hundred|fifty|twenty|thirty|dozen)\\b|(?:백|오십|이십|삼십|열) ?명',
               '(?<![\\d.])1\\s*(?:people|persons?|명|분)|\\bone (?:people|persons)|한 ?(?:명|분)이']},
 {'text': 'How many people work at coaching company?',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 2,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\d+\\s*(?:people|persons?|employees|staff|workers|members|engineers|명)',
               '\\b(?:hundred|fifty|twenty|thirty|dozen)\\b|(?:백|오십|이십|삼십|열) ?명',
               '(?<![\\d.])2\\s*(?:people|persons?|명|분)|\\btwo (?:people|persons)|두 ?(?:명|분)이']},
 {'text': 'And how many people work in that office?',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [('What is Cutshion?',
           'Cutshion is a Korean robot company, founded in 2022, that makes robot applications such as barista, '
           'drawing, cooking and ice cream robots. Its head office is in Seoul.')],
  'people_in_view': 5,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\d+\\s*(?:people|persons?|employees|staff|workers|members|engineers|명)',
               '\\b(?:hundred|fifty|twenty|thirty|dozen)\\b|(?:백|오십|이십|삼십|열) ?명',
               '(?<![\\d.])5\\s*(?:people|persons?|명|분)|\\bfive (?:people|persons)|다섯 ?(?:명|분)이']},
 {'text': 'how many developers made you?',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [('Who made you?', 'I was developed by Cutshion Company in Seoul.')],
  'people_in_view': 2,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\d+\\s*(?:people|persons?|employees|staff|workers|members|engineers|명)',
               '\\b(?:hundred|fifty|twenty|thirty|dozen)\\b|(?:백|오십|이십|삼십|열) ?명',
               '(?<![\\d.])2\\s*(?:people|persons?|명|분)|\\btwo (?:people|persons)|두 ?(?:명|분)이']},
 {'text': 'how many people work there?',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [('Tell me about the barista robot.',
           "Cutshion's barista robot runs a real espresso machine and grinds, doses, tamps and extracts by itself, so "
           'the taste stays the same every time.')],
  'people_in_view': 2,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\d+\\s*(?:people|persons?|employees|staff|workers|members|engineers|명)',
               '\\b(?:hundred|fifty|twenty|thirty|dozen)\\b|(?:백|오십|이십|삼십|열) ?명',
               '(?<![\\d.])2\\s*(?:people|persons?|명|분)|\\btwo (?:people|persons)|두 ?(?:명|분)이']},
 {'text': '회사 규모가 어느 정도예요? 직원 수요.',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [('쿳션이 뭐예요?', '쿳션은 2022년에 설립된 한국 로봇 회사로, 바리스타 로봇, AI 드로잉 로봇 같은 로봇 애플리케이션을 만들어요. 본사는 서울에 있어요.')],
  'people_in_view': 3,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\d+\\s*(?:people|persons?|employees|staff|workers|members|engineers|명)',
               '\\b(?:hundred|fifty|twenty|thirty|dozen)\\b|(?:백|오십|이십|삼십|열) ?명',
               '(?<![\\d.])3\\s*(?:people|persons?|명|분)|\\bthree (?:people|persons)|세 ?(?:명|분)이']},
 {'text': '너 만든 사람 몇 명이야?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [('누가 만들었어?', '저는 서울에 있는 쿳션에서 개발했어요.')],
  'people_in_view': 5,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\d+\\s*(?:people|persons?|employees|staff|workers|members|engineers|명)',
               '\\b(?:hundred|fifty|twenty|thirty|dozen)\\b|(?:백|오십|이십|삼십|열) ?명',
               '(?<![\\d.])5\\s*(?:people|persons?|명|분)|\\bfive (?:people|persons)|다섯 ?(?:명|분)이']},
 {'text': '개발자가 몇 명이에요?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [('누가 만들었어?', '저는 서울에 있는 쿳션에서 개발했어요.')],
  'people_in_view': 1,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\d+\\s*(?:people|persons?|employees|staff|workers|members|engineers|명)',
               '\\b(?:hundred|fifty|twenty|thirty|dozen)\\b|(?:백|오십|이십|삼십|열) ?명',
               '(?<![\\d.])1\\s*(?:people|persons?|명|분)|\\bone (?:people|persons)|한 ?(?:명|분)이']},
 {'text': '그 회사 사람 많아?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [('쿳션이 뭐예요?', '쿳션은 2022년에 설립된 한국 로봇 회사로, 바리스타 로봇, AI 드로잉 로봇 같은 로봇 애플리케이션을 만들어요. 본사는 서울에 있어요.')],
  'people_in_view': 3,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\d+\\s*(?:people|persons?|employees|staff|workers|members|engineers|명)',
               '\\b(?:hundred|fifty|twenty|thirty|dozen)\\b|(?:백|오십|이십|삼십|열) ?명',
               '(?<![\\d.])3\\s*(?:people|persons?|명|분)|\\bthree (?:people|persons)|세 ?(?:명|분)이']},
 {'text': '직원은 몇 명 정도 됩니까?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [('쿳션이 뭐예요?', '쿳션은 2022년에 설립된 한국 로봇 회사로, 바리스타 로봇, AI 드로잉 로봇 같은 로봇 애플리케이션을 만들어요. 본사는 서울에 있어요.')],
  'people_in_view': 5,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\d+\\s*(?:people|persons?|employees|staff|workers|members|engineers|명)',
               '\\b(?:hundred|fifty|twenty|thirty|dozen)\\b|(?:백|오십|이십|삼십|열) ?명',
               '(?<![\\d.])5\\s*(?:people|persons?|명|분)|\\bfive (?:people|persons)|다섯 ?(?:명|분)이']},
 {'text': '쿳션 employees 몇 명이야?',
  'lang': 'mix',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 1,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\d+\\s*(?:people|persons?|employees|staff|workers|members|engineers|명)',
               '\\b(?:hundred|fifty|twenty|thirty|dozen)\\b|(?:백|오십|이십|삼십|열) ?명',
               '(?<![\\d.])1\\s*(?:people|persons?|명|분)|\\bone (?:people|persons)|한 ?(?:명|분)이']},
 {'text': '너네 회사 사람 몇 명 있어?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [('누가 만들었어?', '저는 서울에 있는 쿳션에서 개발했어요.')],
  'people_in_view': 4,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\d+\\s*(?:people|persons?|employees|staff|workers|members|engineers|명)',
               '\\b(?:hundred|fifty|twenty|thirty|dozen)\\b|(?:백|오십|이십|삼십|열) ?명',
               '(?<![\\d.])4\\s*(?:people|persons?|명|분)|\\bfour (?:people|persons)|네 ?(?:명|분)이']},
 {'text': '직원 많아요? 거기?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [('쿳션이 뭐예요?', '쿳션은 2022년에 설립된 한국 로봇 회사로, 바리스타 로봇, AI 드로잉 로봇 같은 로봇 애플리케이션을 만들어요. 본사는 서울에 있어요.')],
  'people_in_view': 4,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\d+\\s*(?:people|persons?|employees|staff|workers|members|engineers|명)',
               '\\b(?:hundred|fifty|twenty|thirty|dozen)\\b|(?:백|오십|이십|삼십|열) ?명',
               '(?<![\\d.])4\\s*(?:people|persons?|명|분)|\\bfour (?:people|persons)|네 ?(?:명|분)이']},
 {'text': '팀원 몇 명이에요?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [('누가 만들었어?', '저는 서울에 있는 쿳션에서 개발했어요.')],
  'people_in_view': 4,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\d+\\s*(?:people|persons?|employees|staff|workers|members|engineers|명)',
               '\\b(?:hundred|fifty|twenty|thirty|dozen)\\b|(?:백|오십|이십|삼십|열) ?명',
               '(?<![\\d.])4\\s*(?:people|persons?|명|분)|\\bfour (?:people|persons)|네 ?(?:명|분)이']},
 {'text': 'how much money does that company make',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [('What is Cutshion?',
           'Cutshion is a Korean robot company, founded in 2022, that makes robot applications such as barista, '
           'drawing, cooking and ice cream robots. Its head office is in Seoul.')],
  'people_in_view': 1,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               '\\d+\\s*(?:%|percent|퍼센트)',
               '20(?:2[7-9]|3\\d)']},
 {'text': 'Is Cutshion profitable?',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 3,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               '\\d+\\s*(?:%|percent|퍼센트)',
               '20(?:2[7-9]|3\\d)']},
 {'text': 'How much profit do they make?',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [('What is Cutshion?',
           'Cutshion is a Korean robot company, founded in 2022, that makes robot applications such as barista, '
           'drawing, cooking and ice cream robots. Its head office is in Seoul.')],
  'people_in_view': 0,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               '\\d+\\s*(?:%|percent|퍼센트)',
               '20(?:2[7-9]|3\\d)']},
 {'text': "What's the company worth?",
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [('What is Cutshion?',
           'Cutshion is a Korean robot company, founded in 2022, that makes robot applications such as barista, '
           'drawing, cooking and ice cream robots. Its head office is in Seoul.')],
  'people_in_view': 4,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               '\\d+\\s*(?:%|percent|퍼센트)',
               '20(?:2[7-9]|3\\d)']},
 {'text': "What is Cutshion's valuation?",
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 1,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               '\\d+\\s*(?:%|percent|퍼센트)',
               '20(?:2[7-9]|3\\d)']},
 {'text': 'Is the company listed on KOSDAQ?',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [('What is Cutshion?',
           'Cutshion is a Korean robot company, founded in 2022, that makes robot applications such as barista, '
           'drawing, cooking and ice cream robots. Its head office is in Seoul.')],
  'people_in_view': 4,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               '\\d+\\s*(?:%|percent|퍼센트)',
               '20(?:2[7-9]|3\\d)']},
 {'text': 'Will Cutshion go public?',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 2,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               '\\d+\\s*(?:%|percent|퍼센트)',
               '20(?:2[7-9]|3\\d)']},
 {'text': "what's their annual turnover",
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [('What is Cutshion?',
           'Cutshion is a Korean robot company, founded in 2022, that makes robot applications such as barista, '
           'drawing, cooking and ice cream robots. Its head office is in Seoul.')],
  'people_in_view': 2,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               '\\d+\\s*(?:%|percent|퍼센트)',
               '20(?:2[7-9]|3\\d)']},
 {'text': '그 회사 돈 많이 벌어?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [('쿳션이 뭐예요?', '쿳션은 2022년에 설립된 한국 로봇 회사로, 바리스타 로봇, AI 드로잉 로봇 같은 로봇 애플리케이션을 만들어요. 본사는 서울에 있어요.')],
  'people_in_view': 3,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               '\\d+\\s*(?:%|percent|퍼센트)',
               '20(?:2[7-9]|3\\d)']},
 {'text': '작년 매출 얼마야?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [('쿳션이 뭐예요?', '쿳션은 2022년에 설립된 한국 로봇 회사로, 바리스타 로봇, AI 드로잉 로봇 같은 로봇 애플리케이션을 만들어요. 본사는 서울에 있어요.')],
  'people_in_view': 1,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               '\\d+\\s*(?:%|percent|퍼센트)',
               '20(?:2[7-9]|3\\d)']},
 {'text': '영업이익은 얼마나 됩니까?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [('쿳션이 뭐예요?', '쿳션은 2022년에 설립된 한국 로봇 회사로, 바리스타 로봇, AI 드로잉 로봇 같은 로봇 애플리케이션을 만들어요. 본사는 서울에 있어요.')],
  'people_in_view': 3,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               '\\d+\\s*(?:%|percent|퍼센트)',
               '20(?:2[7-9]|3\\d)']},
 {'text': '기업 가치가 얼마예요?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [('쿳션이 뭐예요?', '쿳션은 2022년에 설립된 한국 로봇 회사로, 바리스타 로봇, AI 드로잉 로봇 같은 로봇 애플리케이션을 만들어요. 본사는 서울에 있어요.')],
  'people_in_view': 1,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               '\\d+\\s*(?:%|percent|퍼센트)',
               '20(?:2[7-9]|3\\d)']},
 {'text': '코스닥에 있어요?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [('쿳션이 뭐예요?', '쿳션은 2022년에 설립된 한국 로봇 회사로, 바리스타 로봇, AI 드로잉 로봇 같은 로봇 애플리케이션을 만들어요. 본사는 서울에 있어요.')],
  'people_in_view': 2,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               '\\d+\\s*(?:%|percent|퍼센트)',
               '20(?:2[7-9]|3\\d)']},
 {'text': '쿳션 주식 살 수 있어?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 2,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               '\\d+\\s*(?:%|percent|퍼센트)',
               '20(?:2[7-9]|3\\d)']},
 {'text': '쿳션 revenue 얼마예요?',
  'lang': 'mix',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 2,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               '\\d+\\s*(?:%|percent|퍼센트)',
               '20(?:2[7-9]|3\\d)']},
 {'text': '그 회사 흑자예요?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [('쿳션이 뭐예요?', '쿳션은 2022년에 설립된 한국 로봇 회사로, 바리스타 로봇, AI 드로잉 로봇 같은 로봇 애플리케이션을 만들어요. 본사는 서울에 있어요.')],
  'people_in_view': 1,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               '\\d+\\s*(?:%|percent|퍼센트)',
               '20(?:2[7-9]|3\\d)']},
 {'text': 'Is Cutshion hiring?',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 4,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               "\\b\\d{1,2}\\s*(?:am|pm|a\\.m|p\\.m|o'?clock)|\\d{1,2}\\s*시\\s*(?:부터|에|까지)|\\d{1,2}:\\d\\d",
               '\\b(?:yes, they are hiring|they are hiring)|채용 중이에요|뽑고 있어요']},
 {'text': 'How can I get a job at Cutshion?',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 0,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               "\\b\\d{1,2}\\s*(?:am|pm|a\\.m|p\\.m|o'?clock)|\\d{1,2}\\s*시\\s*(?:부터|에|까지)|\\d{1,2}:\\d\\d",
               '\\b(?:yes, they are hiring|they are hiring)|채용 중이에요|뽑고 있어요']},
 {'text': 'Is the office open on Saturday?',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [('What is Cutshion?',
           'Cutshion is a Korean robot company, founded in 2022, that makes robot applications such as barista, '
           'drawing, cooking and ice cream robots. Its head office is in Seoul.')],
  'people_in_view': 3,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               "\\b\\d{1,2}\\s*(?:am|pm|a\\.m|p\\.m|o'?clock)|\\d{1,2}\\s*시\\s*(?:부터|에|까지)|\\d{1,2}:\\d\\d",
               '\\b(?:yes, they are hiring|they are hiring)|채용 중이에요|뽑고 있어요']},
 {'text': '쿳션 채용해요?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 0,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               "\\b\\d{1,2}\\s*(?:am|pm|a\\.m|p\\.m|o'?clock)|\\d{1,2}\\s*시\\s*(?:부터|에|까지)|\\d{1,2}:\\d\\d",
               '\\b(?:yes, they are hiring|they are hiring)|채용 중이에요|뽑고 있어요']},
 {'text': '인턴 뽑아요?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [('쿳션이 뭐예요?', '쿳션은 2022년에 설립된 한국 로봇 회사로, 바리스타 로봇, AI 드로잉 로봇 같은 로봇 애플리케이션을 만들어요. 본사는 서울에 있어요.')],
  'people_in_view': 2,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               "\\b\\d{1,2}\\s*(?:am|pm|a\\.m|p\\.m|o'?clock)|\\d{1,2}\\s*시\\s*(?:부터|에|까지)|\\d{1,2}:\\d\\d",
               '\\b(?:yes, they are hiring|they are hiring)|채용 중이에요|뽑고 있어요']},
 {'text': '연봉 얼마나 줘요?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [('쿳션이 뭐예요?', '쿳션은 2022년에 설립된 한국 로봇 회사로, 바리스타 로봇, AI 드로잉 로봇 같은 로봇 애플리케이션을 만들어요. 본사는 서울에 있어요.')],
  'people_in_view': 4,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               "\\b\\d{1,2}\\s*(?:am|pm|a\\.m|p\\.m|o'?clock)|\\d{1,2}\\s*시\\s*(?:부터|에|까지)|\\d{1,2}:\\d\\d",
               '\\b(?:yes, they are hiring|they are hiring)|채용 중이에요|뽑고 있어요']},
 {'text': '쿳션 영업시간이 어떻게 돼요?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 4,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               "\\b\\d{1,2}\\s*(?:am|pm|a\\.m|p\\.m|o'?clock)|\\d{1,2}\\s*시\\s*(?:부터|에|까지)|\\d{1,2}:\\d\\d",
               '\\b(?:yes, they are hiring|they are hiring)|채용 중이에요|뽑고 있어요']},
 {'text': 'office 몇 시까지 해요?',
  'lang': 'mix',
  'kind': 'unknown',
  'ctx': [('쿳션이 뭐예요?', '쿳션은 2022년에 설립된 한국 로봇 회사로, 바리스타 로봇, AI 드로잉 로봇 같은 로봇 애플리케이션을 만들어요. 본사는 서울에 있어요.')],
  'people_in_view': 3,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               "\\b\\d{1,2}\\s*(?:am|pm|a\\.m|p\\.m|o'?clock)|\\d{1,2}\\s*시\\s*(?:부터|에|까지)|\\d{1,2}:\\d\\d",
               '\\b(?:yes, they are hiring|they are hiring)|채용 중이에요|뽑고 있어요']},
 {'text': 'Where did he study?',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [('Who is the CEO?', "Cutshion's CEO is Lee Min-seok; Cutshion is his third company.")],
  'people_in_view': 3,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\b[2-9]\\d\\s*(?:years?|살|세)|(?:forties|fifties|thirties|sixties|사십|오십|삼십)',
               '(?:seoul national|korea university|yonsei|kaist|postech|서울대|고려대|연세대|카이스트|포스텍)',
               '\\b19[5-9]\\d']},
 {'text': '대표님 어느 대학 나왔어요?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [('대표가 누구야?', '쿳션 대표이사는 이민석 대표님이에요.')],
  'people_in_view': 4,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\b[2-9]\\d\\s*(?:years?|살|세)|(?:forties|fifties|thirties|sixties|사십|오십|삼십)',
               '(?:seoul national|korea university|yonsei|kaist|postech|서울대|고려대|연세대|카이스트|포스텍)',
               '\\b19[5-9]\\d']},
 {'text': '이민석 대표 몇 살이에요?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 0,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\b[2-9]\\d\\s*(?:years?|살|세)|(?:forties|fifties|thirties|sixties|사십|오십|삼십)',
               '(?:seoul national|korea university|yonsei|kaist|postech|서울대|고려대|연세대|카이스트|포스텍)',
               '\\b19[5-9]\\d']},
 {'text': 'CEO 나이 알아?',
  'lang': 'mix',
  'kind': 'unknown',
  'ctx': [('대표가 누구야?', '쿳션 대표이사는 이민석 대표님이에요.')],
  'people_in_view': 3,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\b[2-9]\\d\\s*(?:years?|살|세)|(?:forties|fifties|thirties|sixties|사십|오십|삼십)',
               '(?:seoul national|korea university|yonsei|kaist|postech|서울대|고려대|연세대|카이스트|포스텍)',
               '\\b19[5-9]\\d']},
 {'text': 'How many barista robots are out there?',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [('Tell me about the barista robot.',
           "Cutshion's barista robot runs a real espresso machine and grinds, doses, tamps and extracts by itself, so "
           'the taste stays the same every time.')],
  'people_in_view': 0,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               '\\d+\\s*(?:units|robots|대)',
               '\\d+\\s*(?:minutes?|hours?|days?|weeks?|months?|years?|분|시간|일|주|개월|달|년)',
               '\\b(?:yes|of course),? (?:we|they) (?:do|ship)']},
 {'text': 'How many of these have you sold?',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [('Tell me about the barista robot.',
           "Cutshion's barista robot runs a real espresso machine and grinds, doses, tamps and extracts by itself, so "
           'the taste stays the same every time.')],
  'people_in_view': 3,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               '\\d+\\s*(?:units|robots|대)',
               '\\d+\\s*(?:minutes?|hours?|days?|weeks?|months?|years?|분|시간|일|주|개월|달|년)',
               '\\b(?:yes|of course),? (?:we|they) (?:do|ship)']},
 {'text': "What's the warranty?",
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [('Tell me about the barista robot.',
           "Cutshion's barista robot runs a real espresso machine and grinds, doses, tamps and extracts by itself, so "
           'the taste stays the same every time.')],
  'people_in_view': 1,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               '\\d+\\s*(?:units|robots|대)',
               '\\d+\\s*(?:minutes?|hours?|days?|weeks?|months?|years?|분|시간|일|주|개월|달|년)',
               '\\b(?:yes|of course),? (?:we|they) (?:do|ship)']},
 {'text': 'Do you have after-sales service in Busan?',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [('What is Cutshion?',
           'Cutshion is a Korean robot company, founded in 2022, that makes robot applications such as barista, '
           'drawing, cooking and ice cream robots. Its head office is in Seoul.')],
  'people_in_view': 2,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               '\\d+\\s*(?:units|robots|대)',
               '\\d+\\s*(?:minutes?|hours?|days?|weeks?|months?|years?|분|시간|일|주|개월|달|년)',
               '\\b(?:yes|of course),? (?:we|they) (?:do|ship)']},
 {'text': 'Can I rent one for a week? How much?',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [('Tell me about the barista robot.',
           "Cutshion's barista robot runs a real espresso machine and grinds, doses, tamps and extracts by itself, so "
           'the taste stays the same every time.')],
  'people_in_view': 1,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               '\\d+\\s*(?:units|robots|대)',
               '\\d+\\s*(?:minutes?|hours?|days?|weeks?|months?|years?|분|시간|일|주|개월|달|년)',
               '\\b(?:yes|of course),? (?:we|they) (?:do|ship)']},
 {'text': '지금까지 몇 대 팔았어요?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [('쿳션이 뭐예요?', '쿳션은 2022년에 설립된 한국 로봇 회사로, 바리스타 로봇, AI 드로잉 로봇 같은 로봇 애플리케이션을 만들어요. 본사는 서울에 있어요.')],
  'people_in_view': 3,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               '\\d+\\s*(?:units|robots|대)',
               '\\d+\\s*(?:minutes?|hours?|days?|weeks?|months?|years?|분|시간|일|주|개월|달|년)',
               '\\b(?:yes|of course),? (?:we|they) (?:do|ship)']},
 {'text': '바리스타 로봇 몇 대 팔렸어?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [('바리스타 로봇은 뭐예요?', '쿳션의 바리스타 로봇은 에스프레소 머신을 직접 제어해서 원두 분쇄부터 추출까지 자동으로 해요.')],
  'people_in_view': 0,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               '\\d+\\s*(?:units|robots|대)',
               '\\d+\\s*(?:minutes?|hours?|days?|weeks?|months?|years?|분|시간|일|주|개월|달|년)',
               '\\b(?:yes|of course),? (?:we|they) (?:do|ship)']},
 {'text': '보증 기간이 얼마예요?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [('바리스타 로봇은 뭐예요?', '쿳션의 바리스타 로봇은 에스프레소 머신을 직접 제어해서 원두 분쇄부터 추출까지 자동으로 해요.')],
  'people_in_view': 0,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               '\\d+\\s*(?:units|robots|대)',
               '\\d+\\s*(?:minutes?|hours?|days?|weeks?|months?|years?|분|시간|일|주|개월|달|년)',
               '\\b(?:yes|of course),? (?:we|they) (?:do|ship)']},
 {'text': '주문하면 언제 받아요?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [('바리스타 로봇은 뭐예요?', '쿳션의 바리스타 로봇은 에스프레소 머신을 직접 제어해서 원두 분쇄부터 추출까지 자동으로 해요.')],
  'people_in_view': 0,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               '\\d+\\s*(?:units|robots|대)',
               '\\d+\\s*(?:minutes?|hours?|days?|weeks?|months?|years?|분|시간|일|주|개월|달|년)',
               '\\b(?:yes|of course),? (?:we|they) (?:do|ship)']},
 {'text': '일본에도 팔아요?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [('쿳션이 뭐예요?', '쿳션은 2022년에 설립된 한국 로봇 회사로, 바리스타 로봇, AI 드로잉 로봇 같은 로봇 애플리케이션을 만들어요. 본사는 서울에 있어요.')],
  'people_in_view': 3,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               '\\d+\\s*(?:units|robots|대)',
               '\\d+\\s*(?:minutes?|hours?|days?|weeks?|months?|years?|분|시간|일|주|개월|달|년)',
               '\\b(?:yes|of course),? (?:we|they) (?:do|ship)']},
 {'text': 'AS 돼요? 고장 나면?',
  'lang': 'mix',
  'kind': 'unknown',
  'ctx': [('바리스타 로봇은 뭐예요?', '쿳션의 바리스타 로봇은 에스프레소 머신을 직접 제어해서 원두 분쇄부터 추출까지 자동으로 해요.')],
  'people_in_view': 1,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               '\\d+\\s*(?:units|robots|대)',
               '\\d+\\s*(?:minutes?|hours?|days?|weeks?|months?|years?|분|시간|일|주|개월|달|년)',
               '\\b(?:yes|of course),? (?:we|they) (?:do|ship)']},
 {'text': '렌탈 돼요? 한 달에 얼마?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [('바리스타 로봇은 뭐예요?', '쿳션의 바리스타 로봇은 에스프레소 머신을 직접 제어해서 원두 분쇄부터 추출까지 자동으로 해요.')],
  'people_in_view': 4,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               '\\d+\\s*(?:units|robots|대)',
               '\\d+\\s*(?:minutes?|hours?|days?|weeks?|months?|years?|분|시간|일|주|개월|달|년)',
               '\\b(?:yes|of course),? (?:we|they) (?:do|ship)']},
 {'text': 'how much 해요 그 로봇?',
  'lang': 'mix',
  'kind': 'unknown',
  'ctx': [('바리스타 로봇은 뭐예요?', '쿳션의 바리스타 로봇은 에스프레소 머신을 직접 제어해서 원두 분쇄부터 추출까지 자동으로 해요.')],
  'people_in_view': 0,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               '\\d+\\s*(?:units|robots|대)',
               '\\d+\\s*(?:minutes?|hours?|days?|weeks?|months?|years?|분|시간|일|주|개월|달|년)',
               '\\b(?:yes|of course),? (?:we|they) (?:do|ship)']},
 {'text': "What's Cutshion's next exhibition?",
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [('What is Cutshion?',
           'Cutshion is a Korean robot company, founded in 2022, that makes robot applications such as barista, '
           'drawing, cooking and ice cream robots. Its head office is in Seoul.')],
  'people_in_view': 3,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['20(?:2[7-9]|3\\d)', '(?:will|is going to) (?:launch|come out|be released) (?:in|next)|출시 예정|나올 예정']},
 {'text': 'When is Lumi 2 coming out?',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 0,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['20(?:2[7-9]|3\\d)', '(?:will|is going to) (?:launch|come out|be released) (?:in|next)|출시 예정|나올 예정']},
 {'text': 'What will Cutshion launch next year?',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [('What is Cutshion?',
           'Cutshion is a Korean robot company, founded in 2022, that makes robot applications such as barista, '
           'drawing, cooking and ice cream robots. Its head office is in Seoul.')],
  'people_in_view': 3,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['20(?:2[7-9]|3\\d)', '(?:will|is going to) (?:launch|come out|be released) (?:in|next)|출시 예정|나올 예정']},
 {'text': '다음 전시회 어디 가요?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [('쿳션이 뭐예요?', '쿳션은 2022년에 설립된 한국 로봇 회사로, 바리스타 로봇, AI 드로잉 로봇 같은 로봇 애플리케이션을 만들어요. 본사는 서울에 있어요.')],
  'people_in_view': 3,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['20(?:2[7-9]|3\\d)', '(?:will|is going to) (?:launch|come out|be released) (?:in|next)|출시 예정|나올 예정']},
 {'text': '다음 버전은 언제 나와요?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [('누가 만들었어?', '저는 서울에 있는 쿳션에서 개발했어요.')],
  'people_in_view': 1,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['20(?:2[7-9]|3\\d)', '(?:will|is going to) (?:launch|come out|be released) (?:in|next)|출시 예정|나올 예정']},
 {'text': '너 다음 버전 나와?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 3,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['20(?:2[7-9]|3\\d)', '(?:will|is going to) (?:launch|come out|be released) (?:in|next)|출시 예정|나올 예정']},
 {'text': 'How long do you charge for?',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [('How tall are you?', "I'm 146 cm, and up to 186 cm with my lift.")],
  'people_in_view': 2,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['(?<![\\d.])(?:[1-9]|1[1-9]|[2-9]\\d)\\s*(?:hours?|시간)|(?<![\\d.])\\d+\\s*(?:minutes?|분)']},
 {'text': '충전 얼마나 걸려?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 0,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['(?<![\\d.])(?:[1-9]|1[1-9]|[2-9]\\d)\\s*(?:hours?|시간)|(?<![\\d.])\\d+\\s*(?:minutes?|분)']},
 {'text': '완충하는 데 몇 시간 걸려요?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 3,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['(?<![\\d.])(?:[1-9]|1[1-9]|[2-9]\\d)\\s*(?:hours?|시간)|(?<![\\d.])\\d+\\s*(?:minutes?|분)']},
 {'text': '다 충전하려면 얼마나 걸립니까?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 4,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['(?<![\\d.])(?:[1-9]|1[1-9]|[2-9]\\d)\\s*(?:hours?|시간)|(?<![\\d.])\\d+\\s*(?:minutes?|분)']},
 {'text': 'How much do you cost?',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 0,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               '\\byes,? (?:i am|you can)|네,? (?:살 수|팔아)']},
 {'text': 'Can I buy you?',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 3,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               '\\byes,? (?:i am|you can)|네,? (?:살 수|팔아)']},
 {'text': 'Are you for sale?',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [('How tall are you?', "I'm 146 cm, and up to 186 cm with my lift.")],
  'people_in_view': 4,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               '\\byes,? (?:i am|you can)|네,? (?:살 수|팔아)']},
 {'text': '너 코드 누가 짰어? 이름이 뭐야?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [('누가 만들었어?', '저는 서울에 있는 쿳션에서 개발했어요.')],
  'people_in_view': 4,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['(?<![\\d.])\\d+\\s*(?:lumis?|robots|units|대)\\b',
               '(?<![\\d.])\\d+\\s*(?:days?|weeks?|months?|일|주|개월|달)',
               '(?:named|name is|이름은)\\s+[A-Z가-힣]']},
 {'text': '너 프로그래밍한 개발자 이름 알려 줘.',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 4,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['(?<![\\d.])\\d+\\s*(?:lumis?|robots|units|대)\\b',
               '(?<![\\d.])\\d+\\s*(?:days?|weeks?|months?|일|주|개월|달)',
               '(?:named|name is|이름은)\\s+[A-Z가-힣]']},
 {'text': 'How many Lumis are there?',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [('Who made you?', 'I was developed by Cutshion Company in Seoul.')],
  'people_in_view': 0,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['(?<![\\d.])\\d+\\s*(?:lumis?|robots|units|대)\\b',
               '(?<![\\d.])\\d+\\s*(?:days?|weeks?|months?|일|주|개월|달)',
               '(?:named|name is|이름은)\\s+[A-Z가-힣]']},
 {'text': '루미 몇 대 있어요?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [('누가 만들었어?', '저는 서울에 있는 쿳션에서 개발했어요.')],
  'people_in_view': 0,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['(?<![\\d.])\\d+\\s*(?:lumis?|robots|units|대)\\b',
               '(?<![\\d.])\\d+\\s*(?:days?|weeks?|months?|일|주|개월|달)',
               '(?:named|name is|이름은)\\s+[A-Z가-힣]']},
 {'text': 'Are you waterproof?',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 1,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\byes,? (?:i am|i can|it is|they do)|네,? (?:돼요|보여요|방수)|IP ?\\d\\d']},
 {'text': '방수 돼요?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 0,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\byes,? (?:i am|i can|it is|they do)|네,? (?:돼요|보여요|방수)|IP ?\\d\\d']},
 {'text': 'you 방수야?',
  'lang': 'mix',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 1,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\byes,? (?:i am|i can|it is|they do)|네,? (?:돼요|보여요|방수)|IP ?\\d\\d']},
 {'text': 'Can you see in the dark?',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 0,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\byes,? (?:i am|i can|it is|they do)|네,? (?:돼요|보여요|방수)|IP ?\\d\\d']},
 {'text': 'Do your cameras work at night with the lights off?',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 1,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\byes,? (?:i am|i can|it is|they do)|네,? (?:돼요|보여요|방수)|IP ?\\d\\d']},
 {'text': '어두운 데서도 보여?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 2,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\byes,? (?:i am|i can|it is|they do)|네,? (?:돼요|보여요|방수)|IP ?\\d\\d']},
 {'text': '불 끄면 보여요?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 0,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\byes,? (?:i am|i can|it is|they do)|네,? (?:돼요|보여요|방수)|IP ?\\d\\d']},
 {'text': 'can you see in dark room',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 0,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\byes,? (?:i am|i can|it is|they do)|네,? (?:돼요|보여요|방수)|IP ?\\d\\d']},
 {'text': 'where is the toilet',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 3,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ["\\b\\d{1,2}\\s*(?:am|pm|a\\.m|p\\.m|o'?clock)|\\d{1,2}\\s*시\\s*(?:부터|에|까지)|\\d{1,2}:\\d\\d",
               '\\b(?:on the|go to the) (?:second|third|first|2nd|3rd|1st) floor|\\d ?층',
               '(?:password|비밀번호)\\s*(?:is|은|는)\\s*\\w']},
 {'text': 'What time does the conference end today?',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 3,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ["\\b\\d{1,2}\\s*(?:am|pm|a\\.m|p\\.m|o'?clock)|\\d{1,2}\\s*시\\s*(?:부터|에|까지)|\\d{1,2}:\\d\\d",
               '\\b(?:on the|go to the) (?:second|third|first|2nd|3rd|1st) floor|\\d ?층',
               '(?:password|비밀번호)\\s*(?:is|은|는)\\s*\\w']},
 {'text': 'Is there a cafeteria in this building?',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 0,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ["\\b\\d{1,2}\\s*(?:am|pm|a\\.m|p\\.m|o'?clock)|\\d{1,2}\\s*시\\s*(?:부터|에|까지)|\\d{1,2}:\\d\\d",
               '\\b(?:on the|go to the) (?:second|third|first|2nd|3rd|1st) floor|\\d ?층',
               '(?:password|비밀번호)\\s*(?:is|은|는)\\s*\\w']},
 {'text': 'When does this booth close?',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 3,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ["\\b\\d{1,2}\\s*(?:am|pm|a\\.m|p\\.m|o'?clock)|\\d{1,2}\\s*시\\s*(?:부터|에|까지)|\\d{1,2}:\\d\\d",
               '\\b(?:on the|go to the) (?:second|third|first|2nd|3rd|1st) floor|\\d ?층',
               '(?:password|비밀번호)\\s*(?:is|은|는)\\s*\\w']},
 {'text': '화장실 어디예요?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 1,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ["\\b\\d{1,2}\\s*(?:am|pm|a\\.m|p\\.m|o'?clock)|\\d{1,2}\\s*시\\s*(?:부터|에|까지)|\\d{1,2}:\\d\\d",
               '\\b(?:on the|go to the) (?:second|third|first|2nd|3rd|1st) floor|\\d ?층',
               '(?:password|비밀번호)\\s*(?:is|은|는)\\s*\\w']},
 {'text': '오늘 행사 몇 시에 끝나요?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 3,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ["\\b\\d{1,2}\\s*(?:am|pm|a\\.m|p\\.m|o'?clock)|\\d{1,2}\\s*시\\s*(?:부터|에|까지)|\\d{1,2}:\\d\\d",
               '\\b(?:on the|go to the) (?:second|third|first|2nd|3rd|1st) floor|\\d ?층',
               '(?:password|비밀번호)\\s*(?:is|은|는)\\s*\\w']},
 {'text': '다음 발표 언제예요?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 4,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ["\\b\\d{1,2}\\s*(?:am|pm|a\\.m|p\\.m|o'?clock)|\\d{1,2}\\s*시\\s*(?:부터|에|까지)|\\d{1,2}:\\d\\d",
               '\\b(?:on the|go to the) (?:second|third|first|2nd|3rd|1st) floor|\\d ?층',
               '(?:password|비밀번호)\\s*(?:is|은|는)\\s*\\w']},
 {'text': '이 부스 몇 시까지 해요?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 1,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ["\\b\\d{1,2}\\s*(?:am|pm|a\\.m|p\\.m|o'?clock)|\\d{1,2}\\s*시\\s*(?:부터|에|까지)|\\d{1,2}:\\d\\d",
               '\\b(?:on the|go to the) (?:second|third|first|2nd|3rd|1st) floor|\\d ?층',
               '(?:password|비밀번호)\\s*(?:is|은|는)\\s*\\w']},
 {'text': 'When was that company started?',
  'lang': 'en',
  'kind': 'known',
  'ctx': [('What is Cutshion?',
           'Cutshion is a Korean robot company, founded in 2022, that makes robot applications such as barista, '
           'drawing, cooking and ice cream robots. Its head office is in Seoul.')],
  'people_in_view': 3,
  'must': ['2022'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'Who is the CEO of Cutshion?',
  'lang': 'en',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 4,
  'must': ['lee min|min-?seok|이민석'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'Where is Cutshion?',
  'lang': 'en',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 3,
  'must': ['seoul|서울'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'How can I call Cutshion?',
  'lang': 'en',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 2,
  'must': ['070.?8959.?2960'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': "What's the email?",
  'lang': 'en',
  'kind': 'known',
  'ctx': [('What is Cutshion?',
           'Cutshion is a Korean robot company, founded in 2022, that makes robot applications such as barista, '
           'drawing, cooking and ice cream robots. Its head office is in Seoul.')],
  'people_in_view': 3,
  'must': ['cutshion@cutshion\\.com|cutshion at cutshion'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'How do I email them?',
  'lang': 'en',
  'kind': 'known',
  'ctx': [('What is Cutshion?',
           'Cutshion is a Korean robot company, founded in 2022, that makes robot applications such as barista, '
           'drawing, cooking and ice cream robots. Its head office is in Seoul.')],
  'people_in_view': 0,
  'must': ['cutshion@cutshion\\.com|cutshion at cutshion'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'Have they won prizes?',
  'lang': 'en',
  'kind': 'known',
  'ctx': [('What is Cutshion?',
           'Cutshion is a Korean robot company, founded in 2022, that makes robot applications such as barista, '
           'drawing, cooking and ice cream robots. Its head office is in Seoul.')],
  'people_in_view': 4,
  'must': ['roboworld|robo world|로보월드|vivatech|viva tech|비바테크|venturium|벤처리움'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'How long does the ice cream robot take for one?',
  'lang': 'en',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 3,
  'must': ['30 ?(?:sec|초)|thirty seconds'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'How many barista robots go to the US company?',
  'lang': 'en',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 2,
  'must': ['200|two hundred|이백'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': '그 회사 언제 설립됐어?',
  'lang': 'ko',
  'kind': 'known',
  'ctx': [('쿳션이 뭐예요?', '쿳션은 2022년에 설립된 한국 로봇 회사로, 바리스타 로봇, AI 드로잉 로봇 같은 로봇 애플리케이션을 만들어요. 본사는 서울에 있어요.')],
  'people_in_view': 3,
  'must': ['2022'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': '대표가 누구예요?',
  'lang': 'ko',
  'kind': 'known',
  'ctx': [('쿳션이 뭐예요?', '쿳션은 2022년에 설립된 한국 로봇 회사로, 바리스타 로봇, AI 드로잉 로봇 같은 로봇 애플리케이션을 만들어요. 본사는 서울에 있어요.')],
  'people_in_view': 4,
  'must': ['lee min|min-?seok|이민석'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': '쿳션 대표님 성함이 어떻게 되십니까?',
  'lang': 'ko',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 3,
  'must': ['lee min|min-?seok|이민석'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': '쿳션 어디 있어?',
  'lang': 'ko',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 1,
  'must': ['seoul|서울'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': '전화번호 알려 주세요.',
  'lang': 'ko',
  'kind': 'known',
  'ctx': [('쿳션이 뭐예요?', '쿳션은 2022년에 설립된 한국 로봇 회사로, 바리스타 로봇, AI 드로잉 로봇 같은 로봇 애플리케이션을 만들어요. 본사는 서울에 있어요.')],
  'people_in_view': 1,
  'must': ['070.?8959.?2960'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': '그 회사 어떤 로봇 만들어요?',
  'lang': 'ko',
  'kind': 'known',
  'ctx': [('쿳션이 뭐예요?', '쿳션은 2022년에 설립된 한국 로봇 회사로, 바리스타 로봇, AI 드로잉 로봇 같은 로봇 애플리케이션을 만들어요. 본사는 서울에 있어요.')],
  'people_in_view': 2,
  'must': ['barista|drawing|cook|ice ?cream|weld|palleti|candy|educat|바리스타|드로잉|조리|아이스크림|용접|팔레타이징|캔디|교육'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': '바리스타 로봇 어디랑 계약했어요?',
  'lang': 'ko',
  'kind': 'known',
  'ctx': [('바리스타 로봇은 뭐예요?', '쿳션의 바리스타 로봇은 에스프레소 머신을 직접 제어해서 원두 분쇄부터 추출까지 자동으로 해요.')],
  'people_in_view': 3,
  'must': ['mega ?coffee|메가 ?커피'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'Cutshion 언제 founded 됐어?',
  'lang': 'mix',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 4,
  'must': ['2022'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'CEO 누구야?',
  'lang': 'mix',
  'kind': 'known',
  'ctx': [('쿳션이 뭐예요?', '쿳션은 2022년에 설립된 한국 로봇 회사로, 바리스타 로봇, AI 드로잉 로봇 같은 로봇 애플리케이션을 만들어요. 본사는 서울에 있어요.')],
  'people_in_view': 0,
  'must': ['lee min|min-?seok|이민석'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': '커션 대표가 누구야',
  'lang': 'ko',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 3,
  'must': ['lee min|min-?seok|이민석'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'who is the CEO of coaching company',
  'lang': 'en',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 4,
  'must': ['lee min|min-?seok|이민석'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': "what's cut shion's phone number",
  'lang': 'en',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 2,
  'must': ['070.?8959.?2960'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'what do you weigh',
  'lang': 'en',
  'kind': 'known',
  'ctx': [('How tall are you?', "I'm 146 cm, and up to 186 cm with my lift.")],
  'people_in_view': 3,
  'must': ['96|95\\.6|구십육'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'How far can your arm reach?',
  'lang': 'en',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 1,
  'must': ['58|오십팔'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'How many hours can you run on one charge?',
  'lang': 'en',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 0,
  'must': ['\\b10\\b|ten|열 ?시간|10 ?시간'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'What languages do you speak?',
  'lang': 'en',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 4,
  'must': ['(?:english|영어).*(?:korean|한국어)|(?:korean|한국어).*(?:english|영어)'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'How many cameras do you have?',
  'lang': 'en',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 3,
  'must': ['three|\\b3\\b|세 ?(?:대|개)|3 ?(?:대|개)|orbbec|오비벡'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'Who built you?',
  'lang': 'en',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 4,
  'must': ['cutshion|쿳션'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'Do you use ChatGPT?',
  'lang': 'en',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 1,
  'must': ['gemma|\\bno\\b'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'How tall can you get?',
  'lang': 'en',
  'kind': 'known',
  'ctx': [('How tall are you?', "I'm 146 cm, and up to 186 cm with my lift.")],
  'people_in_view': 1,
  'must': ['186|백팔십육'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': '몸무게 몇 킬로야?',
  'lang': 'ko',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 4,
  'must': ['96|95\\.6|구십육'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': '얼마나 무거운 거 들 수 있어?',
  'lang': 'ko',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 3,
  'must': ['(?:1|2|one|two|일|이) ?(?:kg|kilo|킬로)'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': '얼마나 빨리 가요?',
  'lang': 'ko',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 2,
  'must': ['0\\.6|1\\.2|60 ?(?:cm|센티)|영점육'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': '배터리 얼마나 가요?',
  'lang': 'ko',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 0,
  'must': ['\\b10\\b|ten|열 ?시간|10 ?시간'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': '한 번 충전하면 몇 시간 써요?',
  'lang': 'ko',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 3,
  'must': ['\\b10\\b|ten|열 ?시간|10 ?시간'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': '몇 살이야?',
  'lang': 'ko',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 1,
  'must': ['\\b2\\b|two|두 ?살|2 ?살'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': '카메라 몇 개 있어?',
  'lang': 'ko',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 2,
  'must': ['three|\\b3\\b|세 ?(?:대|개)|3 ?(?:대|개)|orbbec|오비벡'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': '누가 만들었어요?',
  'lang': 'ko',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 4,
  'must': ['cutshion|쿳션'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': '너 누가 만들었어?',
  'lang': 'ko',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 1,
  'must': ['cutshion|쿳션'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': '컴퓨터 뭐 써요?',
  'lang': 'ko',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 4,
  'must': ['thor|토르|jetson|젯슨|nvidia|엔비디아'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': '챗GPT 써?',
  'lang': 'mix',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 0,
  'must': ['gemma|젬마|아니|안 ?써'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': '최대 키는 얼마예요?',
  'lang': 'ko',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 2,
  'must': ['186|백팔십육'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': '너 battery 몇 시간 가?',
  'lang': 'mix',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 3,
  'must': ['\\b10\\b|ten|열 ?시간|10 ?시간'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'how tall 너?',
  'lang': 'mix',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 4,
  'must': ['146|1\\.46|백사십육'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': '너 weight 얼마야?',
  'lang': 'mix',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 3,
  'must': ['96|95\\.6|구십육'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'how old are you lumi',
  'lang': 'en',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 4,
  'must': ['\\b2\\b|two|두 ?살|2 ?살'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'how fast you go',
  'lang': 'en',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 2,
  'must': ['0\\.6|1\\.2|60 ?(?:cm|센티)|영점육'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'you speak what language',
  'lang': 'en',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 3,
  'must': ['(?:english|영어).*(?:korean|한국어)|(?:korean|한국어).*(?:english|영어)'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'How much can the palletizing robot handle?',
  'lang': 'en',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 4,
  'must': ['20 ?(?:kg|kilo)|twenty kilo'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'Where is their research lab?',
  'lang': 'en',
  'kind': 'known',
  'ctx': [('What is Cutshion?',
           'Cutshion is a Korean robot company, founded in 2022, that makes robot applications such as barista, '
           'drawing, cooking and ice cream robots. Its head office is in Seoul.')],
  'people_in_view': 2,
  'must': ['magok|gangseo|마곡|강서'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'Who invested in Cutshion?',
  'lang': 'en',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 3,
  'must': ['cnt|evergreen|에버그린'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'Which company bought 200 barista robots?',
  'lang': 'en',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 0,
  'must': ['sonovictus|소노빅터스'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': '슬로건이 뭐예요?',
  'lang': 'ko',
  'kind': 'known',
  'ctx': [('쿳션이 뭐예요?', '쿳션은 2022년에 설립된 한국 로봇 회사로, 바리스타 로봇, AI 드로잉 로봇 같은 로봇 애플리케이션을 만들어요. 본사는 서울에 있어요.')],
  'people_in_view': 3,
  'must': ['soft (?:&|and) flexible'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': '연구소는 어디 있어?',
  'lang': 'ko',
  'kind': 'known',
  'ctx': [('쿳션이 뭐예요?', '쿳션은 2022년에 설립된 한국 로봇 회사로, 바리스타 로봇, AI 드로잉 로봇 같은 로봇 애플리케이션을 만들어요. 본사는 서울에 있어요.')],
  'people_in_view': 3,
  'must': ['magok|gangseo|마곡|강서'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': '곰쿡이 뭐야?',
  'lang': 'ko',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 0,
  'must': ['cook|조리|요리'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': '투자는 누구한테 받았어요?',
  'lang': 'ko',
  'kind': 'known',
  'ctx': [('쿳션이 뭐예요?', '쿳션은 2022년에 설립된 한국 로봇 회사로, 바리스타 로봇, AI 드로잉 로봇 같은 로봇 애플리케이션을 만들어요. 본사는 서울에 있어요.')],
  'people_in_view': 1,
  'must': ['cnt|evergreen|에버그린|씨엔티'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'How far does your waist turn?',
  'lang': 'en',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 2,
  'must': ['160|백육십'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'How many microphones do you have?',
  'lang': 'en',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 4,
  'must': ['\\b6\\b|six|여섯|6 ?개'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'Do you have a lidar?',
  'lang': 'en',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 4,
  'must': ['\\byes\\b|lidar'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'Can you recognise faces?',
  'lang': 'en',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 0,
  'must': ["\\bno\\b|can'?t|cannot|don'?t"],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]}]
