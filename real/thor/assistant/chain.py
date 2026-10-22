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
_KO_ORDER = {"보": "봐", "흔들": "흔들어", "돌": "돌아", "올리": "올려", "내리": "내려", "높이": "높여", "낮추": "낮춰",
             "들": "들어"}                                      # "나 보고 ..." -> "나 봐", "고개 들고 ..." -> "고개 들어"
ASK = re.compile(r"\?\s*$|^\W*(?:what|what'?s|where|when|who|why|how|which|is|are|do|does|did|tell me|explain|describe)\b|"
                 r"몇 ?시|몇|뭐|무엇|어때|알려|언제|어디|누구|왜|얼마|날씨|설명해|말해 ?줘|얘기해", re.I)
_SPLIT = re.compile(steps._SPLIT.pattern, re.I)
_FILL = re.compile(rf"(?:{steps._FILL}|루미야?|lumi|hey)", re.I)


def _rule(words, markers):
    """brain.intent of a part, also of a Korean -고 form ("나 보고" read as "나 봐")."""
    rule = brain.intent(words, markers)
    if not rule:
        ko = re.sub(r"(보|흔들|돌|올리|내리|높이|낮추|들)고$", lambda m: _KO_ORDER[m.group(1)], words)
        rule = brain.intent(ko, markers) if ko != words else None
    return rule


def parts(text):
    """The sentence cut at and / then / 그리고 / -고 / -서, messages to say kept whole, fillers and the name dropped."""
    cut, says = steps._cut_says(text)
    cut = re.sub(r"(?<=[가-힣])고\s*나서(?=[\s,]|$)", "고", cut)            # "-고 나서" = "-고"
    out = []
    for p in _SPLIT.split(cut):
        out += [q for q in steps._SPLIT_KO.split(p) if q.strip()]
    out = [re.sub(r"§(\d+)§", lambda m: f'"{says[int(m.group(1))]}"', p).strip(" ,.!") for p in out]
    return [p for p in out if p and not re.fullmatch(rf"(?:{_FILL.pattern}|\W)+", p, re.I)]


def plan(text, markers=(), cant=None):
    """See the module's doc. cant: a regex of orders Lumi can't do ("dance", "jump"): answered, the rest done."""
    ps = parts(text)
    whole, unread = steps.rules(text, markers)
    if len(ps) < 2 or whole and not unread:
        return None                                      # one command, or a mission read whole
    rule = brain.intent(text, markers) or ("", "")
    if rule[0] == "look" and rule[1].endswith(f" {brain.HEAD_YAW[1]:g}"):
        return None                                      # "turn around and look": the head looks behind
    out = []
    for p in ps:
        got, unread = steps.rules(p, markers)
        rule = _rule(p, markers)
        if got and not unread and not (rule and rule[0] in ("look", "lift", "wave", "come", "come_back", "follow")):
            out.append(["steps", p, got])
        elif rule and rule[0] in QUICK:
            out.append(["quick", p, rule])
        elif ASK.search(p) or rule and rule[0] in ("weather", "search") or cant is not None and cant.match(p):
            out.append(["talk", p, None])
        else:
            return None
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

