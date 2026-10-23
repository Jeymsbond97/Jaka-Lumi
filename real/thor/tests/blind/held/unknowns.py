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

held-out: only scored, never read by whoever fixes the code.
"""

CASES = [{'text': 'How many people work at that company?',
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
 {'text': 'how many people work there?',
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
  'must_not': ['\\d+\\s*(?:people|persons?|employees|staff|workers|members|engineers|명)',
               '\\b(?:hundred|fifty|twenty|thirty|dozen)\\b|(?:백|오십|이십|삼십|열) ?명',
               '(?<![\\d.])4\\s*(?:people|persons?|명|분)|\\bfour (?:people|persons)|네 ?(?:명|분)이']},
 {'text': 'so how many people are in your company',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [('Who made you?', 'I was developed by Cutshion Company in Seoul.')],
  'people_in_view': 1,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\d+\\s*(?:people|persons?|employees|staff|workers|members|engineers|명)',
               '\\b(?:hundred|fifty|twenty|thirty|dozen)\\b|(?:백|오십|이십|삼십|열) ?명',
               '(?<![\\d.])1\\s*(?:people|persons?|명|분)|\\bone (?:people|persons)|한 ?(?:명|분)이']},
 {'text': 'How many engineers work on you?',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [('Who made you?', 'I was developed by Cutshion Company in Seoul.')],
  'people_in_view': 5,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\d+\\s*(?:people|persons?|employees|staff|workers|members|engineers|명)',
               '\\b(?:hundred|fifty|twenty|thirty|dozen)\\b|(?:백|오십|이십|삼십|열) ?명',
               '(?<![\\d.])5\\s*(?:people|persons?|명|분)|\\bfive (?:people|persons)|다섯 ?(?:명|분)이']},
 {'text': 'how many staff does Cutshion have',
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
 {'text': 'Is it a big company? Like how many people?',
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
  'must_not': ['\\d+\\s*(?:people|persons?|employees|staff|workers|members|engineers|명)',
               '\\b(?:hundred|fifty|twenty|thirty|dozen)\\b|(?:백|오십|이십|삼십|열) ?명',
               '(?<![\\d.])3\\s*(?:people|persons?|명|분)|\\bthree (?:people|persons)|세 ?(?:명|분)이']},
 {'text': 'um, how many people work at the company that made you?',
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
 {'text': 'how many guys work there',
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
  'must_not': ['\\d+\\s*(?:people|persons?|employees|staff|workers|members|engineers|명)',
               '\\b(?:hundred|fifty|twenty|thirty|dozen)\\b|(?:백|오십|이십|삼십|열) ?명',
               '(?<![\\d.])4\\s*(?:people|persons?|명|분)|\\bfour (?:people|persons)|네 ?(?:명|분)이']},
 {'text': 'Is it just a few people, or a big team?',
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
 {'text': 'how many people does cut shin employ',
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
 {'text': '그 회사 직원 몇 명이야?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [('쿳션이 뭐예요?', '쿳션은 2022년에 설립된 한국 로봇 회사로, 바리스타 로봇, AI 드로잉 로봇 같은 로봇 애플리케이션을 만들어요. 본사는 서울에 있어요.')],
  'people_in_view': 2,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\d+\\s*(?:people|persons?|employees|staff|workers|members|engineers|명)',
               '\\b(?:hundred|fifty|twenty|thirty|dozen)\\b|(?:백|오십|이십|삼십|열) ?명',
               '(?<![\\d.])2\\s*(?:people|persons?|명|분)|\\btwo (?:people|persons)|두 ?(?:명|분)이']},
 {'text': '쿳션 직원이 몇 명이에요?',
  'lang': 'ko',
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
 {'text': '직원 몇 명이에요?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [('쿳션이 뭐예요?', '쿳션은 2022년에 설립된 한국 로봇 회사로, 바리스타 로봇, AI 드로잉 로봇 같은 로봇 애플리케이션을 만들어요. 본사는 서울에 있어요.')],
  'people_in_view': 2,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\d+\\s*(?:people|persons?|employees|staff|workers|members|engineers|명)',
               '\\b(?:hundred|fifty|twenty|thirty|dozen)\\b|(?:백|오십|이십|삼십|열) ?명',
               '(?<![\\d.])2\\s*(?:people|persons?|명|분)|\\btwo (?:people|persons)|두 ?(?:명|분)이']},
 {'text': '거기 몇 명 일해?',
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
 {'text': '쿳션에는 몇 분이 일하세요?',
  'lang': 'ko',
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
 {'text': '쿳션 직원 수 알려 주십시오.',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 3,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\d+\\s*(?:people|persons?|employees|staff|workers|members|engineers|명)',
               '\\b(?:hundred|fifty|twenty|thirty|dozen)\\b|(?:백|오십|이십|삼십|열) ?명',
               '(?<![\\d.])3\\s*(?:people|persons?|명|분)|\\bthree (?:people|persons)|세 ?(?:명|분)이']},
 {'text': '쿳션 팀은 몇 명이야?',
  'lang': 'ko',
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
 {'text': '커션 직원 몇 명이에요',
  'lang': 'ko',
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
 {'text': 'Cutshion 직원 몇 명?',
  'lang': 'ko',
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
 {'text': '그 회사 how many people 일해요?',
  'lang': 'mix',
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
 {'text': 'how many 직원 there?',
  'lang': 'mix',
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
 {'text': "What's Cutshion's revenue?",
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 4,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               '\\d+\\s*(?:%|percent|퍼센트)',
               '20(?:2[7-9]|3\\d)']},
 {'text': 'What were their sales last year?',
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
 {'text': 'Is Cutshion on the stock market?',
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
 {'text': 'Can I buy Cutshion stock?',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 0,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               '\\d+\\s*(?:%|percent|퍼센트)',
               '20(?:2[7-9]|3\\d)']},
 {'text': 'When is the IPO?',
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
 {'text': '쿳션 매출이 얼마예요?',
  'lang': 'ko',
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
 {'text': '쿳션 상장했어요?',
  'lang': 'ko',
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
 {'text': '언제 상장해요?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [('쿳션이 뭐예요?', '쿳션은 2022년에 설립된 한국 로봇 회사로, 바리스타 로봇, AI 드로잉 로봇 같은 로봇 애플리케이션을 만들어요. 본사는 서울에 있어요.')],
  'people_in_view': 4,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               '\\d+\\s*(?:%|percent|퍼센트)',
               '20(?:2[7-9]|3\\d)']},
 {'text': 'Do they take interns?',
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
               "\\b\\d{1,2}\\s*(?:am|pm|a\\.m|p\\.m|o'?clock)|\\d{1,2}\\s*시\\s*(?:부터|에|까지)|\\d{1,2}:\\d\\d",
               '\\b(?:yes, they are hiring|they are hiring)|채용 중이에요|뽑고 있어요']},
 {'text': "I'm a student, can I apply there?",
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
               "\\b\\d{1,2}\\s*(?:am|pm|a\\.m|p\\.m|o'?clock)|\\d{1,2}\\s*시\\s*(?:부터|에|까지)|\\d{1,2}:\\d\\d",
               '\\b(?:yes, they are hiring|they are hiring)|채용 중이에요|뽑고 있어요']},
 {'text': 'Are there any open positions?',
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
               "\\b\\d{1,2}\\s*(?:am|pm|a\\.m|p\\.m|o'?clock)|\\d{1,2}\\s*시\\s*(?:부터|에|까지)|\\d{1,2}:\\d\\d",
               '\\b(?:yes, they are hiring|they are hiring)|채용 중이에요|뽑고 있어요']},
 {'text': "What's the salary like there?",
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
 {'text': 'What are the office hours?',
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
               "\\b\\d{1,2}\\s*(?:am|pm|a\\.m|p\\.m|o'?clock)|\\d{1,2}\\s*시\\s*(?:부터|에|까지)|\\d{1,2}:\\d\\d",
               '\\b(?:yes, they are hiring|they are hiring)|채용 중이에요|뽑고 있어요']},
 {'text': 'When does the Seoul office open?',
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
 {'text': 'What time does Cutshion close?',
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
 {'text': '거기 취직하려면 어떻게 해?',
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
 {'text': '사무실 몇 시에 열어요?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [('쿳션이 뭐예요?', '쿳션은 2022년에 설립된 한국 로봇 회사로, 바리스타 로봇, AI 드로잉 로봇 같은 로봇 애플리케이션을 만들어요. 본사는 서울에 있어요.')],
  'people_in_view': 0,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               "\\b\\d{1,2}\\s*(?:am|pm|a\\.m|p\\.m|o'?clock)|\\d{1,2}\\s*시\\s*(?:부터|에|까지)|\\d{1,2}:\\d\\d",
               '\\b(?:yes, they are hiring|they are hiring)|채용 중이에요|뽑고 있어요']},
 {'text': '주말에도 영업합니까?',
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
 {'text': '지금 jobs 있어요? 쿳션에',
  'lang': 'mix',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 2,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               "\\b\\d{1,2}\\s*(?:am|pm|a\\.m|p\\.m|o'?clock)|\\d{1,2}\\s*시\\s*(?:부터|에|까지)|\\d{1,2}:\\d\\d",
               '\\b(?:yes, they are hiring|they are hiring)|채용 중이에요|뽑고 있어요']},
 {'text': '사람 뽑아?',
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
 {'text': 'How old is the CEO?',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [('Who is the CEO?', "Cutshion's CEO is Lee Min-seok; Cutshion is his third company.")],
  'people_in_view': 2,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\b[2-9]\\d\\s*(?:years?|살|세)|(?:forties|fifties|thirties|sixties|사십|오십|삼십)',
               '(?:seoul national|korea university|yonsei|kaist|postech|서울대|고려대|연세대|카이스트|포스텍)',
               '\\b19[5-9]\\d']},
 {'text': 'How old is he?',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [('Who is the CEO?', "Cutshion's CEO is Lee Min-seok; Cutshion is his third company.")],
  'people_in_view': 1,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\b[2-9]\\d\\s*(?:years?|살|세)|(?:forties|fifties|thirties|sixties|사십|오십|삼십)',
               '(?:seoul national|korea university|yonsei|kaist|postech|서울대|고려대|연세대|카이스트|포스텍)',
               '\\b19[5-9]\\d']},
 {'text': 'Which university did Lee Min-seok go to?',
  'lang': 'en',
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
 {'text': 'Is the CEO married?',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [('Who is the CEO?', "Cutshion's CEO is Lee Min-seok; Cutshion is his third company.")],
  'people_in_view': 1,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\b[2-9]\\d\\s*(?:years?|살|세)|(?:forties|fifties|thirties|sixties|사십|오십|삼십)',
               '(?:seoul national|korea university|yonsei|kaist|postech|서울대|고려대|연세대|카이스트|포스텍)',
               '\\b19[5-9]\\d']},
 {'text': 'How old was he when he founded it?',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [('Who is the CEO?', "Cutshion's CEO is Lee Min-seok; Cutshion is his third company.")],
  'people_in_view': 4,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\b[2-9]\\d\\s*(?:years?|살|세)|(?:forties|fifties|thirties|sixties|사십|오십|삼십)',
               '(?:seoul national|korea university|yonsei|kaist|postech|서울대|고려대|연세대|카이스트|포스텍)',
               '\\b19[5-9]\\d']},
 {'text': '대표님 나이가 어떻게 돼요?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [('대표가 누구야?', '쿳션 대표이사는 이민석 대표님이에요.')],
  'people_in_view': 0,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\b[2-9]\\d\\s*(?:years?|살|세)|(?:forties|fifties|thirties|sixties|사십|오십|삼십)',
               '(?:seoul national|korea university|yonsei|kaist|postech|서울대|고려대|연세대|카이스트|포스텍)',
               '\\b19[5-9]\\d']},
 {'text': '그 사람 몇 살이야?',
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
 {'text': '대표님 결혼하셨어요?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [('대표가 누구야?', '쿳션 대표이사는 이민석 대표님이에요.')],
  'people_in_view': 2,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\b[2-9]\\d\\s*(?:years?|살|세)|(?:forties|fifties|thirties|sixties|사십|오십|삼십)',
               '(?:seoul national|korea university|yonsei|kaist|postech|서울대|고려대|연세대|카이스트|포스텍)',
               '\\b19[5-9]\\d']},
 {'text': 'Who founded it, and how old is he?',
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
  'must_not': ['\\b[2-9]\\d\\s*(?:years?|살|세)|(?:forties|fifties|thirties|sixties|사십|오십|삼십)',
               '(?:seoul national|korea university|yonsei|kaist|postech|서울대|고려대|연세대|카이스트|포스텍)',
               '\\b19[5-9]\\d']},
 {'text': 'How many robots has Cutshion sold?',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 2,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               '\\d+\\s*(?:units|robots|대)',
               '\\d+\\s*(?:minutes?|hours?|days?|weeks?|months?|years?|분|시간|일|주|개월|달|년)',
               '\\b(?:yes|of course),? (?:we|they) (?:do|ship)']},
 {'text': 'How long is the warranty on the barista robot?',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 1,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               '\\d+\\s*(?:units|robots|대)',
               '\\d+\\s*(?:minutes?|hours?|days?|weeks?|months?|years?|분|시간|일|주|개월|달|년)',
               '\\b(?:yes|of course),? (?:we|they) (?:do|ship)']},
 {'text': 'How fast can you deliver one?',
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
 {'text': 'If I order today, when does it arrive?',
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
 {'text': 'Do you ship to Germany?',
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
               '\\d+\\s*(?:units|robots|대)',
               '\\d+\\s*(?:minutes?|hours?|days?|weeks?|months?|years?|분|시간|일|주|개월|달|년)',
               '\\b(?:yes|of course),? (?:we|they) (?:do|ship)']},
 {'text': 'How much is the barista robot?',
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
 {'text': '배송 얼마나 걸려요?',
  'lang': 'ko',
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
 {'text': '바리스타 로봇 가격 얼마예요?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 4,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               '\\d+\\s*(?:units|robots|대)',
               '\\d+\\s*(?:minutes?|hours?|days?|weeks?|months?|years?|분|시간|일|주|개월|달|년)',
               '\\b(?:yes|of course),? (?:we|they) (?:do|ship)']},
 {'text': '그거 얼마야?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [('바리스타 로봇은 뭐예요?', '쿳션의 바리스타 로봇은 에스프레소 머신을 직접 제어해서 원두 분쇄부터 추출까지 자동으로 해요.')],
  'people_in_view': 3,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               '\\d+\\s*(?:units|robots|대)',
               '\\d+\\s*(?:minutes?|hours?|days?|weeks?|months?|years?|분|시간|일|주|개월|달|년)',
               '\\b(?:yes|of course),? (?:we|they) (?:do|ship)']},
 {'text': 'Will you be at CES next year?',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [('Who made you?', 'I was developed by Cutshion Company in Seoul.')],
  'people_in_view': 4,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['20(?:2[7-9]|3\\d)', '(?:will|is going to) (?:launch|come out|be released) (?:in|next)|출시 예정|나올 예정']},
 {'text': 'Will there be a newer version of you?',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [('Who made you?', 'I was developed by Cutshion Company in Seoul.')],
  'people_in_view': 4,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['20(?:2[7-9]|3\\d)', '(?:will|is going to) (?:launch|come out|be released) (?:in|next)|출시 예정|나올 예정']},
 {'text': 'Are you going to be sold in shops next year?',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 3,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['20(?:2[7-9]|3\\d)', '(?:will|is going to) (?:launch|come out|be released) (?:in|next)|출시 예정|나올 예정']},
 {'text': '내년에 신제품 나와요?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [('쿳션이 뭐예요?', '쿳션은 2022년에 설립된 한국 로봇 회사로, 바리스타 로봇, AI 드로잉 로봇 같은 로봇 애플리케이션을 만들어요. 본사는 서울에 있어요.')],
  'people_in_view': 4,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['20(?:2[7-9]|3\\d)', '(?:will|is going to) (?:launch|come out|be released) (?:in|next)|출시 예정|나올 예정']},
 {'text': '루미 2는 언제 나와?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 3,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['20(?:2[7-9]|3\\d)', '(?:will|is going to) (?:launch|come out|be released) (?:in|next)|출시 예정|나올 예정']},
 {'text': '다음 CES에도 나와요?',
  'lang': 'mix',
  'kind': 'unknown',
  'ctx': [('쿳션이 뭐예요?', '쿳션은 2022년에 설립된 한국 로봇 회사로, 바리스타 로봇, AI 드로잉 로봇 같은 로봇 애플리케이션을 만들어요. 본사는 서울에 있어요.')],
  'people_in_view': 4,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['20(?:2[7-9]|3\\d)', '(?:will|is going to) (?:launch|come out|be released) (?:in|next)|출시 예정|나올 예정']},
 {'text': 'How long does it take to charge you?',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 3,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['(?<![\\d.])(?:[1-9]|1[1-9]|[2-9]\\d)\\s*(?:hours?|시간)|(?<![\\d.])\\d+\\s*(?:minutes?|분)']},
 {'text': 'How many hours to full charge?',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 2,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['(?<![\\d.])(?:[1-9]|1[1-9]|[2-9]\\d)\\s*(?:hours?|시간)|(?<![\\d.])\\d+\\s*(?:minutes?|분)']},
 {'text': 'charging 몇 시간 걸려요?',
  'lang': 'mix',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 2,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['(?<![\\d.])(?:[1-9]|1[1-9]|[2-9]\\d)\\s*(?:hours?|시간)|(?<![\\d.])\\d+\\s*(?:minutes?|분)']},
 {'text': 'how long the charge take',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 2,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['(?<![\\d.])(?:[1-9]|1[1-9]|[2-9]\\d)\\s*(?:hours?|시간)|(?<![\\d.])\\d+\\s*(?:minutes?|분)']},
 {'text': "What's your price?",
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [('How tall are you?', "I'm 146 cm, and up to 186 cm with my lift.")],
  'people_in_view': 0,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               '\\byes,? (?:i am|you can)|네,? (?:살 수|팔아)']},
 {'text': 'How much did it cost to make you?',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [('Who made you?', 'I was developed by Cutshion Company in Seoul.')],
  'people_in_view': 2,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               '\\byes,? (?:i am|you can)|네,? (?:살 수|팔아)']},
 {'text': '너 얼마야?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 4,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               '\\byes,? (?:i am|you can)|네,? (?:살 수|팔아)']},
 {'text': '루미 가격이 얼마예요?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 0,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               '\\byes,? (?:i am|you can)|네,? (?:살 수|팔아)']},
 {'text': '너 살 수 있어?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 1,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               '\\byes,? (?:i am|you can)|네,? (?:살 수|팔아)']},
 {'text': '너 만드는 데 얼마 들었어?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [('누가 만들었어?', '저는 서울에 있는 쿳션에서 개발했어요.')],
  'people_in_view': 4,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               '\\byes,? (?:i am|you can)|네,? (?:살 수|팔아)']},
 {'text': '너 price 얼마야?',
  'lang': 'mix',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 0,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               '\\byes,? (?:i am|you can)|네,? (?:살 수|팔아)']},
 {'text': 'how much you cost',
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
 {'text': '로봇 한 대 가격이 어떻게 되십니까? 루미요.',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 0,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['\\$\\s*\\d|\\d[\\d,.]*\\s*(?:won|원|dollars?|달러|만 ?원|억|million|billion|thousand|천만)',
               '\\byes,? (?:i am|you can)|네,? (?:살 수|팔아)']},
 {'text': "Who wrote your code? What's his name?",
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [('Who made you?', 'I was developed by Cutshion Company in Seoul.')],
  'people_in_view': 1,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['(?<![\\d.])\\d+\\s*(?:lumis?|robots|units|대)\\b',
               '(?<![\\d.])\\d+\\s*(?:days?|weeks?|months?|일|주|개월|달)',
               '(?:named|name is|이름은)\\s+[A-Z가-힣]']},
 {'text': "What's the name of the engineer who programmed you?",
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 2,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['(?<![\\d.])\\d+\\s*(?:lumis?|robots|units|대)\\b',
               '(?<![\\d.])\\d+\\s*(?:days?|weeks?|months?|일|주|개월|달)',
               '(?:named|name is|이름은)\\s+[A-Z가-힣]']},
 {'text': '너 같은 로봇 몇 대 만들었어?',
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
 {'text': 'How long did it take to build you?',
  'lang': 'en',
  'kind': 'unknown',
  'ctx': [('Who made you?', 'I was developed by Cutshion Company in Seoul.')],
  'people_in_view': 4,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ['(?<![\\d.])\\d+\\s*(?:lumis?|robots|units|대)\\b',
               '(?<![\\d.])\\d+\\s*(?:days?|weeks?|months?|일|주|개월|달)',
               '(?:named|name is|이름은)\\s+[A-Z가-힣]']},
 {'text': '너 만드는 데 얼마나 걸렸어?',
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
 {'text': "Where's the restroom?",
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
 {'text': 'When is the next talk?',
  'lang': 'en',
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
 {'text': 'Where can I park?',
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
 {'text': "What's the Wi-Fi password here?",
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
 {'text': 'Who is speaking after lunch?',
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
 {'text': '화장실 어디 있어?',
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
 {'text': '이 건물에 식당 있어요?',
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
 {'text': '주차 어디에 해요?',
  'lang': 'ko',
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
 {'text': '와이파이 비밀번호 뭐예요?',
  'lang': 'ko',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 2,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ["\\b\\d{1,2}\\s*(?:am|pm|a\\.m|p\\.m|o'?clock)|\\d{1,2}\\s*시\\s*(?:부터|에|까지)|\\d{1,2}:\\d\\d",
               '\\b(?:on the|go to the) (?:second|third|first|2nd|3rd|1st) floor|\\d ?층',
               '(?:password|비밀번호)\\s*(?:is|은|는)\\s*\\w']},
 {'text': 'restroom 어디예요?',
  'lang': 'mix',
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
 {'text': 'toilet 어디 있어요?',
  'lang': 'mix',
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
 {'text': '행사 schedule 알려 줘',
  'lang': 'mix',
  'kind': 'unknown',
  'ctx': [],
  'people_in_view': 2,
  'must': ["not sure|don'?t know|do not know|not known|no (exact )?information|don'?t have|do not have|isn'?t "
           "(on|listed|public)|not (on|listed|public)|can'?t (say|tell)|cannot (say|tell)|no idea|not something i "
           '(have|know)|staff|contact|ask|모르|몰라|알 수 없|알지 못|확실하지|정보가 없|정보는 없|없어서|가지고 있지 않|나와 있지 않|직원|문의|연락|알려 드릴 수 '
           '없|말씀드리기 어렵'],
  'must_not': ["\\b\\d{1,2}\\s*(?:am|pm|a\\.m|p\\.m|o'?clock)|\\d{1,2}\\s*시\\s*(?:부터|에|까지)|\\d{1,2}:\\d\\d",
               '\\b(?:on the|go to the) (?:second|third|first|2nd|3rd|1st) floor|\\d ?층',
               '(?:password|비밀번호)\\s*(?:is|은|는)\\s*\\w']},
 {'text': 'When was Cutshion founded?',
  'lang': 'en',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 0,
  'must': ['2022'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'What year did they start?',
  'lang': 'en',
  'kind': 'known',
  'ctx': [('Who made you?', 'I was developed by Cutshion Company in Seoul.')],
  'people_in_view': 4,
  'must': ['2022'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'who runs that company',
  'lang': 'en',
  'kind': 'known',
  'ctx': [('What is Cutshion?',
           'Cutshion is a Korean robot company, founded in 2022, that makes robot applications such as barista, '
           'drawing, cooking and ice cream robots. Its head office is in Seoul.')],
  'people_in_view': 2,
  'must': ['lee min|min-?seok|이민석'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': "Who's the boss there?",
  'lang': 'en',
  'kind': 'known',
  'ctx': [('Who made you?', 'I was developed by Cutshion Company in Seoul.')],
  'people_in_view': 2,
  'must': ['lee min|min-?seok|이민석'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': "Where's their office?",
  'lang': 'en',
  'kind': 'known',
  'ctx': [('What is Cutshion?',
           'Cutshion is a Korean robot company, founded in 2022, that makes robot applications such as barista, '
           'drawing, cooking and ice cream robots. Its head office is in Seoul.')],
  'people_in_view': 3,
  'must': ['seoul|서울'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'which city is it in',
  'lang': 'en',
  'kind': 'known',
  'ctx': [('Who made you?', 'I was developed by Cutshion Company in Seoul.')],
  'people_in_view': 3,
  'must': ['seoul|서울'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': "What's their phone number?",
  'lang': 'en',
  'kind': 'known',
  'ctx': [('What is Cutshion?',
           'Cutshion is a Korean robot company, founded in 2022, that makes robot applications such as barista, '
           'drawing, cooking and ice cream robots. Its head office is in Seoul.')],
  'people_in_view': 4,
  'must': ['070.?8959.?2960'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'What does Cutshion make?',
  'lang': 'en',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 3,
  'must': ['barista|drawing|cook|ice ?cream|weld|palleti|candy|educat|바리스타|드로잉|조리|아이스크림|용접|팔레타이징|캔디|교육'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'What kind of robots do they build?',
  'lang': 'en',
  'kind': 'known',
  'ctx': [('What is Cutshion?',
           'Cutshion is a Korean robot company, founded in 2022, that makes robot applications such as barista, '
           'drawing, cooking and ice cream robots. Its head office is in Seoul.')],
  'people_in_view': 1,
  'must': ['barista|drawing|cook|ice ?cream|weld|palleti|candy|educat|바리스타|드로잉|조리|아이스크림|용접|팔레타이징|캔디|교육'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'What else do they make besides you?',
  'lang': 'en',
  'kind': 'known',
  'ctx': [('Who made you?', 'I was developed by Cutshion Company in Seoul.')],
  'people_in_view': 3,
  'must': ['barista|drawing|cook|ice ?cream|weld|palleti|candy|educat|바리스타|드로잉|조리|아이스크림|용접|팔레타이징|캔디|교육'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'Did Cutshion win any awards?',
  'lang': 'en',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 1,
  'must': ['roboworld|robo world|로보월드|vivatech|viva tech|비바테크|venturium|벤처리움'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'Who did they sign the barista deal with?',
  'lang': 'en',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 2,
  'must': ['mega ?coffee|메가 ?커피'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': '쿳션 언제 생겼어요?',
  'lang': 'ko',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 1,
  'must': ['2022'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': '본사가 어디예요?',
  'lang': 'ko',
  'kind': 'known',
  'ctx': [('쿳션이 뭐예요?', '쿳션은 2022년에 설립된 한국 로봇 회사로, 바리스타 로봇, AI 드로잉 로봇 같은 로봇 애플리케이션을 만들어요. 본사는 서울에 있어요.')],
  'people_in_view': 3,
  'must': ['seoul|서울'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': '이메일 주소가 뭐예요?',
  'lang': 'ko',
  'kind': 'known',
  'ctx': [('쿳션이 뭐예요?', '쿳션은 2022년에 설립된 한국 로봇 회사로, 바리스타 로봇, AI 드로잉 로봇 같은 로봇 애플리케이션을 만들어요. 본사는 서울에 있어요.')],
  'people_in_view': 4,
  'must': ['cutshion@cutshion\\.com|cutshion at cutshion'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': '쿳션은 뭐 만들어?',
  'lang': 'ko',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 4,
  'must': ['barista|drawing|cook|ice ?cream|weld|palleti|candy|educat|바리스타|드로잉|조리|아이스크림|용접|팔레타이징|캔디|교육'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': '상 받은 거 있어요?',
  'lang': 'ko',
  'kind': 'known',
  'ctx': [('쿳션이 뭐예요?', '쿳션은 2022년에 설립된 한국 로봇 회사로, 바리스타 로봇, AI 드로잉 로봇 같은 로봇 애플리케이션을 만들어요. 본사는 서울에 있어요.')],
  'people_in_view': 0,
  'must': ['roboworld|robo world|로보월드|vivatech|viva tech|비바테크|venturium|벤처리움'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': '쿳션 office 어디예요?',
  'lang': 'mix',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 1,
  'must': ['seoul|서울'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'How tall are you?',
  'lang': 'en',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 0,
  'must': ['146|1\\.46|백사십육'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'How heavy are you?',
  'lang': 'en',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 1,
  'must': ['96|95\\.6|구십육'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'How much can you lift?',
  'lang': 'en',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 2,
  'must': ['(?:1|2|one|two|일|이) ?(?:kg|kilo|킬로)'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'How much can you carry in your hand?',
  'lang': 'en',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 4,
  'must': ['(?:1|2|one|two|일|이) ?(?:kg|kilo|킬로)'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'How fast can you drive?',
  'lang': 'en',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 1,
  'must': ['0\\.6|1\\.2|60 ?(?:cm|센티)|영점육'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'How long does your battery last?',
  'lang': 'en',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 1,
  'must': ['\\b10\\b|ten|열 ?시간|10 ?시간'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'How old are you?',
  'lang': 'en',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 1,
  'must': ['\\b2\\b|two|두 ?살|2 ?살'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'Who made you?',
  'lang': 'en',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 1,
  'must': ['cutshion|쿳션'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'What computer is inside you?',
  'lang': 'en',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 2,
  'must': ['thor|jetson|nvidia'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'And how much do you weigh?',
  'lang': 'en',
  'kind': 'known',
  'ctx': [('How tall are you?', "I'm 146 cm, and up to 186 cm with my lift.")],
  'people_in_view': 0,
  'must': ['96|95\\.6|구십육'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': '키가 몇이에요?',
  'lang': 'ko',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 4,
  'must': ['146|1\\.46|백사십육'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': '팔 길이가 얼마예요?',
  'lang': 'ko',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 1,
  'must': ['58|오십팔'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': '무슨 언어 할 수 있어요?',
  'lang': 'ko',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 4,
  'must': ['(?:english|영어).*(?:korean|한국어)|(?:korean|한국어).*(?:english|영어)'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'how many 카메라 있어요?',
  'lang': 'mix',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 1,
  'must': ['three|\\b3\\b|세 ?(?:대|개)|3 ?(?:대|개)|orbbec|오비벡'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'who make you',
  'lang': 'en',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 2,
  'must': ['cutshion|쿳션'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': "What's the slogan of Cutshion?",
  'lang': 'en',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 3,
  'must': ['soft (?:&|and) flexible'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'How long does the candy ball robot take?',
  'lang': 'en',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 2,
  'must': ['20 ?(?:sec|초)|twenty seconds'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'What is GOMCOOK?',
  'lang': 'en',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 0,
  'must': ['cook|조리|요리'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': "What's Pionoid?",
  'lang': 'en',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 1,
  'must': ['platform|api|app|플랫폼'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'What is CUVision?',
  'lang': 'en',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 4,
  'must': ['vision|camera|image|비전|카메라'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'Where did they win the VivaTech award?',
  'lang': 'en',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 4,
  'must': ['paris|파리'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'Does Cutshion have an office in America?',
  'lang': 'en',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 2,
  'must': ['mclean|virginia|맥린|버지니아'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'How much was the seed investment?',
  'lang': 'en',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 1,
  'must': ['500|five hundred|오억|5억'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': '미국에도 사무실 있어요?',
  'lang': 'ko',
  'kind': 'known',
  'ctx': [('쿳션이 뭐예요?', '쿳션은 2022년에 설립된 한국 로봇 회사로, 바리스타 로봇, AI 드로잉 로봇 같은 로봇 애플리케이션을 만들어요. 본사는 서울에 있어요.')],
  'people_in_view': 1,
  'must': ['mclean|virginia|맥린|버지니아|미국'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': '비바테크에서 상 받았어요?',
  'lang': 'ko',
  'kind': 'known',
  'ctx': [('쿳션이 뭐예요?', '쿳션은 2022년에 설립된 한국 로봇 회사로, 바리스타 로봇, AI 드로잉 로봇 같은 로봇 애플리케이션을 만들어요. 본사는 서울에 있어요.')],
  'people_in_view': 0,
  'must': ['\\byes\\b|네|받았|tech for change'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'How far can you turn your head?',
  'lang': 'en',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 4,
  'must': ['180|백팔십'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'Can you climb stairs?',
  'lang': 'en',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 2,
  'must': ["\\bno\\b|can'?t|cannot"],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'What speech recognition do you use?',
  'lang': 'en',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 4,
  'must': ['whisper'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'What can you pick up?',
  'lang': 'en',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 3,
  'must': ['cup|bottle|apple'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': '고개 얼마나 돌아가?',
  'lang': 'ko',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 4,
  'must': ['180|백팔십'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': '마이크 몇 개야?',
  'lang': 'ko',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 2,
  'must': ['\\b6\\b|여섯|6 ?개'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': '계단 올라갈 수 있어?',
  'lang': 'ko',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 1,
  'must': ['못|없|아니'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': '음성 인식 뭐 써요?',
  'lang': 'ko',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 2,
  'must': ['whisper|위스퍼'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': '얼굴 알아볼 수 있어요?',
  'lang': 'ko',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 1,
  'must': ['못|없|아니|않'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': '뭐 집을 수 있어?',
  'lang': 'ko',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 2,
  'must': ['컵|병|사과|cup'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': '라이다 있어요?',
  'lang': 'ko',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 1,
  'must': ['네|있|lidar|라이다'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': 'how far you can reach 팔로?',
  'lang': 'mix',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 0,
  'must': ['58|오십팔'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]},
 {'text': '너 몇 kg까지 들어?',
  'lang': 'mix',
  'kind': 'known',
  'ctx': [],
  'people_in_view': 1,
  'must': ['(?:1|2|one|two|일|이) ?(?:kg|kilo|킬로)'],
  'must_not': ["not sure|don'?t know|do not know|no (exact )?information|no idea|모르|몰라|알 수 없|정보가 없|정보는 없"]}]
