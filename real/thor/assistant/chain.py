"""Several commands, questions and talk in one sentence ("look at me and wave", "go to p5 and tell me the weather",
"웨이브 하고 나 봐", "고개 들고 몇 시야?"): the parts in the order said, for lumi.chain_run to do one after the other.

plan(text, markers) -> [(kind, words, what), ...] or None when the sentence is not such a chain:
  "steps": a run of parts the mission reader reads whole (what: the steps; run by tasks/fetch.run_steps),
  "quick": one command the keyword rules take (what: brain.intent's (action, target); lumi.quick_command),
  "talk":  a question or something to answer (lumi.answer on these words: the weather, the time, "dance" -> I can't).
None: one part only, every part a step (a mission: read back first, lumi.mission_request), no command in it, or a
part that is neither a command nor clearly a question ("come here, I need help": the old paths answer it)."""
import re

from assistant import brain, steps

QUICK = {"look", "lift", "wave", "arm", "go_to", "come", "come_back", "follow", "move", "turn", "pick", "put", "move_object"}
DRIVES = {"go_to", "come", "come_back", "follow", "move", "turn"}   # after a failed step these depend on where Lumi is
_KO_ORDER = {"보": "봐", "흔들": "흔들어", "흔드": "흔들어", "돌": "돌아", "도": "돌아", "올리": "올려", "내리": "내려",
             "높이": "높여", "낮추": "낮춰", "들": "들어", "드": "들어", "숙이": "숙여", "커지": "커져", "작아지": "작아져",
             "낮아지": "낮아져", "높아지": "높아져", "돌리": "돌려", "오": "와", "따라오": "따라와", "가": "가"}
# "나 보고 ..." -> "나 봐", "고개 들고 ..." -> "고개 들어", "저를 보시고 ..." -> "저를 봐", "왼쪽으로 도시고" -> "왼쪽으로 돌아"
_KO_AND = re.compile(r"(" + "|".join(sorted(_KO_ORDER, key=len, reverse=True)) + r")(?:시)?고$")
ASK = re.compile(r"\?\s*$|^\W*(?:(?:also|and|then|so|ok|okay|robot|please|first|now|plus|oh|ah|um|uh|lumi)\W+)*"
                 r"(?:(?:what|where|when|who|why|how|which)(?:'s|'re|\s+(?:is|are|was|were|do|does|did|can|could|will|"
                 r"would|should|time|day|date|year|old|much|many|far|long|about|kind|your|you|made|built|created|"
                 r"invented|owns|makes)\b)|why\b|is|are|do|does|did|tell me|explain|describe)\b|"
                 r"\b(?:tell|telling) (?:me|us)\b|\bintroduce yourself\b|\b(?:say|tell me) your name\b|"
                 r"몇 ?시|몇|뭐|무엇|어때|알려|언제|어디|누구|왜|얼마|날씨|설명해|말해 ?줘|말하|얘기해|소개", re.I)
_SPLIT = re.compile(steps._SPLIT.pattern, re.I)
FETCHING = re.compile(r"\b(?:bring|fetch|deliver|carry)\b|가져|갖다", re.I)   # a part that carries something somewhere
_FILL = re.compile(rf"(?:{steps._FILL}|루미야?|lumi|hey|do me a favou?r|부탁(?:해|해요|할게)?|dear|sir|ma'?am|madam|buddy|"
                   r"my friend|robot|로봇아?|선생님?|yo|bro|dude|okay lumi|ok lumi|robot please|루미 ?씨|로봇 양반|여보세요|"
                   r"go ahead|okay\?|ok\?|right\?|thanks|thank you|yes|yeah|yep|yes\?|네|응|그래|will ya|will you|won'?t you|"
                   r"can\?|can|do it|do it now|just do it|alright\?|please\?|over here\??|this way\??|어디 ?한번|어디 ?보자|얼마나 걸리나|(?:pls |please )?(?:eh|huh|da|see|ya|yah|innit)\??|혹시|아 뭐라 그래야 되지|뭐라 그래야 되지|뭐더라|"
                   r"(?:아\s*)?영어로 ?뭐더라|(?:아\s*)?뭐라고 ?하지|"
                   r"(?:거기서?\s*)?(?:서|가만히)\s*있(?:어|게|으세요|으십시오)\s*(?:줄래|줄 ?수 ?있어요?|주실래요|주세요|줘|줘잉|주라|"
                   r"주면 ?안 ?될까요?|주면 ?좋겠어요?|주실 ?수 ?있어요?|주십시오|주이소)?|"
                   r"(?:거기서?\s*)?기다려\s*(?:줄래|주세요|줘)?)", re.I)   # tags, hesitations, "...가서 서 있어 줄래?"
RELATIVE = re.compile(r"^\W*(?:where|which|who|that|when)\s+(?:the|my|your|his|her|our|their|a|an|this|that|these|those|"
                      r"people|everyone|it|he|she|they|we|i)\b", re.I)   # "look right, where the door is": no question
SPEED_Q = re.compile(r"속도|몇으로|얼마나 (?:빨리|빠르게|천천히)|\bhow (?:fast|quick(?:ly)?|slow(?:ly)?)\b|\bwhat speed\b", re.I)
GREET = re.compile(r"인사|작별|\b(?:hello|hi|goodbye|bye)\b", re.I)   # a greeting made by waving
PAST = re.compile(r"\byou (?:got|went|were|did|turned|looked|moved|came|said|told)\b|\b(?:earlier|before|yesterday)\b", re.I)
BANK_KINDS = {"look", "lift", "turn", "move", "come", "come_back", "follow", "wave", "arm", "go_to"}   # a part the
                                                     # keyword rules miss, read by the intent bank (same slot rules)
CHAIN_ONLY = {"look", "lift", "wave", "come", "come_back", "follow"}   # a part that is no mission step: with one in it,
                                                     # a sentence the mission reader reads whole is still a chain


BACKGROUND = re.compile(r"[가-힣](?:는|은|인|던)(?:데|디)(?:요)?\W*$")   # "…말하는데," a clause that only sets the scene
SELF_PROMISE = re.compile(r"(?:^|\W)(?:i'?ll|i will|let me|i'?m going to|i can) (?:hold|take|keep|get|catch|grab) (?:it|that|this|them)\W*$|"
                          r"(?:^|\W)(?:내가|제가) (?:들|받|잡)(?:게|을게|을게요|게요|을께)\W*$", re.I)   # the speaker's part


def _restated(words, before):
    """A Korean part that says the order before it again in another level ("손 거둬!", "아 거두시겠어요?")."""
    from assistant import wording
    said = [w for w in re.findall(r"\w+", wording.ko_plain(words)) if not re.fullmatch(r"(?:줘|봐|주|좀|요)[가-힣]?|허허|하하|호호|헤헤|아|어", w)]
    if not said or len(said) > 3 or not re.fullmatch(r"[가-힣]{2,}|[가와]", said[-1]):
        return False
    last = said[-1]
    return any(last == w or len(w) > 1 and (w.startswith(last) or last.startswith(w))
               for w in re.findall(r"\w+", wording.ko_plain(before)) if re.fullmatch(r"[가-힣]+", w))


def _rule(words, markers):
    """brain.intent of a part, also of a Korean -고 form ("나 보고" read as "나 봐")."""
    rule = brain.intent(words, markers)
    ko = _KO_AND.sub(lambda m: _KO_ORDER[m.group(1)], words.strip())
    if not rule and ko != words.strip():
        rule = brain.intent(ko, markers)
    m = not rule and re.fullmatch(r"(?:(나|저|날|나를|저를)\s+)?([a-z][a-z ]*?)\s*(?:하고|해|해요|해 ?줘)?", words.strip())
    if m:                                                # Konglish: "나 look 하고" -> "look at me", "wave 해" -> "wave"
        en = m.group(2) + ((" at me" if m.group(2) == "look" else " me") if m.group(1) else "")
        rule = brain.intent(en, markers)
    if not rule and len(words.split()) > 1 or not rule and re.search(r"[가-힣]", words):
        from assistant import intent_bank                # "glance to your right", "고개 숙이고": the bank, by meaning
        got = intent_bank.read(ko, markers)
        rule = got if got and got[0] in BANK_KINDS else None
        if rule and rule[0] == "come_back" and re.fullmatch(r"\W*(?:루미야?\s*)?(?:원래 ?자리|제자리)(?:에|로)?\W*", words):
            rule = None                                  # "제자리에, 손 내밀어": "ready", no drive back
    return rule


def parts(text):
    """The sentence cut at and / then / 그리고 / -고 / -서, messages to say kept whole, fillers and the name dropped."""
    text = re.sub(r"(?<![\w가-힣])([\w가-힣]+)[—–-]+\s*(?=\1)", "", text)   # a stutter: "go ah— ahead", "센— 센티"
    cut, says = steps._cut_says(text)
    cut = re.sub(r"(?<=[가-힣])고\s*나서(?=[\s,]|$)", "고", cut)            # "-고 나서" = "-고"
    out = []
    for p in _SPLIT.split(cut):
        out += [q for q in steps._SPLIT_KO.split(p) if q.strip()]
    out = [re.sub(r"§(\d+)§", lambda m: f'"{says[int(m.group(1))]}"', p).strip(" ,.!") for p in out]
    for i in range(len(out) - 1, 0, -1):                 # "뒤로 물러서 줘": 서 is the verb's, 줘 no part of its own
        if re.fullmatch(r"(?:줘|줘요|주세요|주십시오|줄래요?\??|주실래요?\??|주라|주게|주이소|봐|봐요|보세요)\W*", out[i]):
            out[i - 1] += " " + out.pop(i)
    return [p for p in out if p and not re.fullmatch(rf"(?:{_FILL.pattern}|\W)+", p, re.I)]


def plan(text, markers=(), cant=None):
    """See the module's doc. cant: a regex of orders Lumi can't do ("dance", "jump"): answered, the rest done."""
    from assistant import intent_bank
    if brain.held_back(text) or PAST.search(text) or intent_bank.TAG.search(text) or intent_bank.PAST_EN.search(text) or intent_bank.past_ko(text):
        return None                                      # "so you got shorter, didn't you?": talk about it, no order
    if re.search(r"(?:^|[\s,.!?—–-])(?:no,? no|아니(?:야|요|지)?|아 ?아니|i mean|sorry|correction|oops|actually|잘못 말했다)"
                 r"(?=[\s,.!?—–:-]|$)", text, re.I):
        return None                                      # a correction: the last thing said counts (brain.self_correct)
    text = re.sub(r"\bhundred and (?=\w)", "hundred ", text, flags=re.I)   # "a hundred and twenty degrees": one number
    ps = parts(text)
    whole, unread = steps.rules(text, markers)
    if len(ps) < 2 or whole and not unread and not any((_rule(p, markers) or ("",))[0] in CHAIN_ONLY for p in ps):
        return None                                      # one command, or a mission read whole
    rule = brain.intent(text, markers) or ("", "")
    if rule[0] == "look" and rule[1].endswith(f" {brain.HEAD_YAW[1]:g}"):
        return None                                      # "turn around and look": the head looks behind
    out = []
    for p in ps:
        if SELF_PROMISE.search(p) or out and _restated(p, out[-1][1]) or brain.GREET_ONLY.match(p):   # "hello robot, …"
            continue                                     # "흰색 머그컵 잡아!, 아 잡아 줄 수 있어요?": the order once
        got, unread = steps.rules(p, markers)
        rule = _rule(p, markers)
        if got and not unread and not (rule and rule[0] in ("look", "lift", "wave", "come", "come_back", "follow")):
            out.append(["steps", p, got])
        elif rule and rule[0] == "fetch" or FETCHING.search(p):
            return None                                  # "go to the exit and bring an orange back": a fetch, whole
        elif rule and rule[0] in QUICK:
            out.append(["quick", p, rule])
        elif RELATIVE.search(p):
            return None                                  # a part that tells more about the one before
        elif BACKGROUND.search(p):
            continue                                     # "이장이 말하는디, 팔 제자리로 해", "I'll hold it, give it here"
        elif out and out[-1][0] in ("quick", "steps") and _restated(p, out[-1][1]):
            continue                                     # "손 거둬!, 아 거두시겠어요?": the same order again, politely
        elif out and out[-1][0] == "quick" and out[-1][2][0] == "wave" and re.search(r"(?:면서|며|서)\W*$", out[-1][1]) and \
                GREET.search(p) and not rule:
            continue                                     # "손 흔들면서 인사하고 고개 숙여": the wave is the greeting
        elif ASK.search(p) or rule and rule[0] in ("weather", "search") or cant is not None and cant.match(p):
            out.append(["talk", p, None])
        else:
            return None
    if re.search(r"비켜|\bmake way\b|\bmove aside\b|\bget out of the way\b", text, re.I) and \
            sum(k == "quick" and w[0] == "move" for k, _, w in out) >= 2:
        return None                                      # "길 좀 비켜 줘, 오른쪽으로 40cm": one move that way, not two
    said = [_rule(p, markers) for _, p, _ in out]          # "reach out, reach out to me": one reach
    out = [x for i, x in enumerate(out) if not (i and (x[0] == "quick" and x[0::2] == out[i - 1][0::2] or
                                                      said[i] and said[i] == said[i - 1]))]
    if len(out) < 2:
        return None                                      # "wave, wave, wave!": one wave, said with feeling
    if any(k == "talk" and SPEED_Q.search(p) and i and re.search(r"고$|\b(?:holding|carrying|with)\b", out[i - 1][1], re.I)
           for i, (k, p, _) in enumerate(out)):
        return None                                      # "컵 들고 몇으로 가?": how fast it goes so, no order
    if any(k == "quick" and w[0] == "wave" and re.search(r"(?<!가)서$", p) and i + 1 < len(out) and
           GREET.search(out[i + 1][1]) for i, (k, p, w) in enumerate(out)):
        return None                                      # "손 흔들어서 작별 인사 해 줘": the wave is the greeting
    kinds = [k for k, _, _ in out]
    if "talk" not in kinds and "quick" not in kinds or "steps" not in kinds and "quick" not in kinds:
        return None                                      # all steps: a mission (read back); all talk: the LLM
    if any(k == "quick" and w[0] == "follow" for k, _, w in out[:-1]):
        return None                                      # following never ends: only as the last part
    merged = []                                          # steps next to each other: one mission ("take the cup and
    for k, p, w in out:                                  # put it back" needs the pick before it)
        if k == "steps" and merged and merged[-1][0] == "steps":
            joined = f"{merged[-1][1]}, then {p}"
            got, unread = steps.rules(joined, markers)
            merged[-1] = ["steps", joined, got if got and not unread else merged[-1][2] + w]
        else:
            merged.append([k, p, w])
    return [tuple(x) for x in merged]

