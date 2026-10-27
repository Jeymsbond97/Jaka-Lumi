"""English wordings for every intent kind (assistant/intent_bank.py), to reach the Korean depth: each kind's core
phrases (verbs x ways / objects / places) in polite, plain, casual and non-native frames, with and without "Lumi",
plus speech-to-text slips, and "no" wordings (other senses of the same verbs, remarks, someone else's body) that
must not move.

Every core here says its kind plainly with the words intent_bank._slot reads (a way for move / turn / look / lift, a
come or follow word, a place as <place>, an object as <obj>). Frames are applied to a fixed, spread share of the
cores (_pick, the same every run), so the bank grows by meaning, not by repeating one sentence.
"""
import re
import zlib


def _pick(texts, keep):
    """A fixed subset of about `keep` (0..1) of `texts`, spread over them, without repeats."""
    return [t for t in dict.fromkeys(texts) if keep >= 1 or zlib.crc32(t.encode()) % 1000 < keep * 1000]


def _x(*parts):
    """Every join of one choice from each part, spaces tidied."""
    out = [""]
    for p in parts:
        out = [f"{a} {b}" for a in out for b in p]
    return [" ".join(t.split()) for t in out]


DOUBLE = {"get", "put", "grab", "nab", "snag", "step", "shut", "drop", "spin", "swing", "tip", "pop", "nip", "hop",
          "run", "stop", "zip", "dip"}


def _ing(core):
    """The core with its first verb as -ing: "wave at me" -> "waving at me", "get over here" -> "getting over here"."""
    verb, _, rest = core.partition(" ")
    if verb in DOUBLE and not verb.endswith(("ing",)) and verb != "swing":
        v = verb + verb[-1] + "ing"
    elif verb.endswith("e") and not verb.endswith("ee"):
        v = verb[:-1] + "ing"
    else:
        v = verb + "ing"
    return f"{v} {rest}".strip()


# frames: {} is an imperative core
POLITE = ["please {}", "{} please", "could you {}", "could you please {}", "could you possibly {}", "can you {}",
          "can you please {}", "would you {}", "would you please {}", "would you kindly {}", "will you {}",
          "will you please {}", "i'd like you to {}", "i would like you to {}", "i want you to {}", "i need you to {}",
          "go ahead and {}", "kindly {}", "i'd appreciate it if you could {}", "it would be great if you could {}",
          "let's see you {}", "how about you {}", "you can {} now", "time to {}", "okay, {}", "alright, {}",
          "{} for me", "{} for me please", "{}, thanks", "{}, thank you", "{} now please", "lumi, could you {}",
          "lumi, please {}", "hey lumi, can you {}", "excuse me, could you {}"]
CASUAL = ["just {}", "c'mon, {}", "yo, {}", "{}, buddy", "{}, mate", "{} already", "quick, {}", "{} quick",
          "{} asap", "hey, {}", "lumi, {}", "{}, lumi", "{} real quick", "gonna need you to {}", "you gotta {}",
          "{} for us", "{} ok?", "{} right now", "{}, will ya", "{}, would ya", "lumi {}"]
BROKEN = ["you {} please", "please you {}", "you {} now", "lumi you {}", "{} pls", "{} plz", "you must {}",
          "you can {}?", "please do {}", "you {} for me", "please, please {}", "now you {}", "robot please {}",
          "you {} okay", "please {} okay", "{} please robot"]
FRAMES = POLITE + CASUAL + BROKEN
GERUND = ["would you mind {}", "mind {}", "how about {}", "try {}", "could you try {}",
          "would you consider {}", "start {}"]
# speech-to-text slips said at a booth: the same words heard a little wrong
SLIPS = [(r"\byour\b", "you're"), (r"\byour\b", "yor"), (r"\bthe\b", "da"), (r"\bthe\b", "a"), (r"\bplease\b", "pleas"),
         (r"\bright\b", "write"), (r"\bleft\b", "lift"), (r"\bhand\b", "hen"),
         (r"\bthat\b", "dat"), (r"\bthis\b", "dis"), (r"\bcome\b", "cum"), (r"\bwith\b", "wit")]


def _framed(cores, keep, ger=(), slips=0.15, kind=""):
    """Every core, a `keep` share of cores x FRAMES, the gerund frames on `ger`, and a share with one slip."""
    out = list(cores) + _pick([f.format(c) for c in cores for f in FRAMES], keep)
    out += _pick([f.format(_ing(c)) for c in ger for f in GERUND], max(keep * 2, 0.4))
    slipped = []
    for t in _pick(out, slips):
        for rx, to in SLIPS:
            if rx in (r"\bleft\b", r"\bright\b") and kind in ("look", "turn", "move", "lift"):   # the way word
                continue
            s = re.sub(rx, to, t, count=1)
            if s != t:
                slipped.append(s)
                break
    return list(dict.fromkeys(out + slipped))


# ---------------- wave (a handshake is a wave: owner 2026-10-23) ----------------
_WAVE = ["wave", "wave hi", "wave hello", "wave bye", "wave goodbye", "wave at me", "wave to me", "wave at us",
         "wave to us", "wave your hand", "wave your hand at me", "wave your hand at us", "wave your arm", "wave hello to us",
         "wave hello to everyone", "wave bye to the kids", "wave to the guests", "wave at the guests", "wave to the folks",
         "wave to the people", "wave at the visitors", "wave to my son", "wave to my mom", "wave to my friend",
         "wave to the crowd", "wave to the camera", "wave at the camera", "wave for the photo", "wave us goodbye",
         "wave us hello", "give a wave", "give us a wave", "give me a wave", "give a little wave", "give a big wave",
         "give them a wave", "throw us a wave", "throw me a wave", "do a wave", "do a little wave", "do the wave thing",
         "do your wave", "say hi with your hand", "say hello with your hand", "say bye with your hand",
         "say goodbye with your hand", "say hi with a wave", "say hello with a wave", "greet us with a wave",
         "greet me with your hand", "greet the guests with a wave", "greet the visitors with your hand",
         "wave your hand hello", "wave your hand goodbye", "wave your hand around", "wave your hand a little",
         "waggle your hand", "wiggle your hand hello", "flap your hand hello", "wave to the audience",
         "shake hands", "shake my hand", "shake hands with me", "shake hands with us", "shake hands with my friend",
         "shake hand", "shake hand with me", "give me a handshake", "give us a handshake", "do a handshake",
         "do a handshake with me", "let's shake hands", "let's shake hand", "let's shake on it", "shake on it",
         "handshake please", "handshake me", "hand shake", "do hand shaking", "make a handshake", "shake my hand hello",
         "shake hands nice to meet you", "wave hi to my daughter", "wave bye bye", "wave bye-bye to us"]
_WAVE_HAND = ["lumi wave", "lumi wave hi", "wave wave", "lumi, wave at the kids",
              "you wave hand", "you wave me please", "you shake hand me", "you hand shake please", "you make wave",
              "you do the wave", "make wave hand", "do wave for me", "do waving please", "hand shaking please",
              "shake hand with me can", "you can wave to me?", "you can shake hand?", "you wave hello okay",
              "wave yo hand", "wave da hand", "wave your hands", "waive your hand", "wave you're hand", "wave yur hand",
              "shake handz", "shak hands", "shake hans please", "shaking hands", "waving hello please",
              "a wave for the camera please", "one wave please", "one handshake please", "wave just once",
              "wave one time for me", "give the kids a wave", "give my mom a wave", "give everybody a wave",
              "a little wave for us", "a big wave for the crowd", "hello wave please", "bye wave please"]

# ---------------- arm_reach: the arm held out ("give me your hand") ----------------
_REACH = ["hold out your hand", "hold out your arm", "hold your hand out", "hold your arm out", "hold your hand out to me",
          "put your hand out", "put your arm out", "put out your hand", "put out your arm", "stick out your hand",
          "stick out your arm", "stick your hand out", "stick your arm out", "extend your arm", "extend your hand",
          "extend your arm to me", "extend your hand toward me", "extend your arm out", "reach out", "reach out to me",
          "reach out your hand", "reach out your arm", "reach your hand out", "reach your arm out", "reach toward me",
          "reach your arm toward me", "reach out in front", "stretch out your arm", "stretch out your hand",
          "stretch your arm out", "stretch your arm toward me", "stretch your hand out", "give me your hand",
          "give me your arm", "offer me your hand", "offer your hand", "show me your hand", "bring your hand out",
          "bring your arm out", "bring your hand forward", "move your hand toward me", "move your arm out",
          "pop your arm out", "pop your hand out", "send your arm out", "push your hand out", "your hand out please",
          "arm out front", "arm out", "hand out", "hand forward", "arm forward", "arm straight out", "straighten your arm",
          "straighten out your arm", "let me hold your hand", "let me see your hand", "reach out and give me your hand"]
_REACH_HAND = ["you give me hand", "you reach out arm", "you hold out hand", "give hand please", "you put hand out",
               "you stretch arm", "hand give me", "your hand give me", "give me you hand", "give mi your hand",
               "hold owt your hand", "reach owt", "stretch you arm", "extend you arm", "you extend hand please",
               "you can give me your hand?", "you can reach out?", "lumi, your hand", "your hand, lumi",
               "hand to me please", "arm to me please", "reach arm out please"]

# ---------------- arm_fold: the arm back to its rest pose ----------------
_FOLD = ["fold your arm", "fold your arm back", "fold your arm in", "fold up your arm", "fold the arm away",
         "put your arm down", "put your arm back", "put your arm away", "put your hand down", "put your hand back",
         "put the arm down", "lower your arm", "lower your hand", "bring your arm down", "bring your arm back",
         "bring your arm in", "bring your hand back", "pull your arm back", "pull your arm in", "pull your hand back",
         "pull back your arm", "draw your arm back", "draw your arm in", "take your arm back", "take your hand back",
         "retract your arm", "retract your hand", "tuck your arm in", "tuck your arm away", "tuck in your arm",
         "rest your arm", "relax your arm", "drop your arm", "arm down", "arm back", "arm in", "arm away",
         "arm back to rest", "arm to rest position", "arm back home", "reset your arm", "return your arm",
         "return your arm to rest", "go back to your rest pose", "back to your resting pose", "put your arm at rest",
         "stow your arm", "stow the arm", "park your arm", "put your arm in its place", "arm back where it was"]
_FOLD_HAND = ["you fold arm", "you put arm down", "arm down please robot", "fold you arm", "put you arm down",
              "you can put your arm down now", "okay, arm down", "thanks, arm back", "that's enough, arm back",
              "enough, put your arm down", "you arm back please", "arm go down", "arm go back", "your arm, fold it"]

# ---------------- arm_open / arm_close: the gripper ----------------
_OPEN = ["open your hand", "open your gripper", "open the gripper", "open your fingers", "open your claw",
         "open up your hand", "open your hand wide", "open your hand all the way", "spread your fingers",
         "spread your fingers apart", "unclench your hand", "unclench your fingers", "unclench your fist",
         "loosen your hand", "loosen your fingers", "relax your hand", "relax your fingers", "release your grip",
         "let your hand open", "hand open", "fingers open", "gripper open", "open the claw", "open your grip",
         "open the fingers", "widen your gripper", "spread the gripper"]
_OPEN_HAND = ["you open hand", "open you hand", "opn your hand", "open ur hand", "hand open please", "you open gripper",
              "gripper open please", "open hand pls", "you open fingers please", "open da gripper"]
_CLOSE = ["close your hand", "close your gripper", "close the gripper", "close your fingers", "close your claw",
          "close up your hand", "close your hand tight", "make a fist", "make a fist with your hand", "clench your hand",
          "clench your fist", "clench your fingers", "squeeze your fingers", "squeeze your hand shut", "shut your hand",
          "shut your gripper", "shut the gripper", "curl your fingers", "close the fingers", "hand closed", "fist please",
          "gripper close", "fingers close", "close the claw", "tighten your grip", "tighten your hand",
          "pinch your fingers together", "bring your fingers together"]
_CLOSE_HAND = ["you close hand", "close you hand", "clos your hand", "close ur hand", "hand close please",
               "you make fist", "gripper close please", "close hand pls", "you close gripper", "close da gripper"]

# ---------------- pick / fetch ----------------
_PICK = ["pick up the <obj>", "pick the <obj> up", "pick up that <obj>", "pick up this <obj>", "pick up a <obj>",
         "pick the <obj> up off the table", "pick up the <obj> on the table", "pick up the <obj> in front of you",
         "pick up the <obj> right there", "grab the <obj>", "grab that <obj>", "grab a <obj>", "grab the <obj> there",
         "grab the <obj> in front of you", "grab the <obj> off the table", "grab hold of the <obj>", "take the <obj>",
         "take that <obj>", "take a <obj>", "take the <obj> off the table", "take hold of the <obj>",
         "take the <obj> in your hand", "get the <obj>", "get that <obj>", "get hold of the <obj>",
         "get the <obj> off the table", "lift the <obj>", "lift up the <obj>", "lift that <obj> up", "scoop up the <obj>",
         "collect the <obj>", "snag the <obj>", "nab that <obj>", "pluck the <obj> off the table", "seize the <obj>",
         "pick out the <obj>", "pick the <obj> from the table", "grab me that <obj>", "go for the <obj>, pick it up",
         "pick that <obj> up for me", "get a grip on the <obj>", "get your hand on the <obj>", "grasp the <obj>",
         "grip the <obj>", "pick up the <obj> there", "take the <obj> there"]
_PICK_HAND = ["you pick <obj>", "you pick up <obj>", "you take <obj>", "you grab <obj>", "pick <obj> please",
              "grab <obj> please", "take <obj> please", "pickup the <obj>", "pick op the <obj>", "pik up the <obj>",
              "pick up da <obj>", "grap the <obj>", "grabb the <obj>", "pick up a <obj> pls", "you can pick the <obj>?",
              "<obj>, pick it up", "<obj>, grab it", "the <obj>, take it", "that <obj>, pick it up please"]
_FETCH = ["bring me the <obj>", "bring me a <obj>", "bring me that <obj>", "bring the <obj> to me", "bring the <obj> here",
          "bring the <obj> over", "bring the <obj> over here", "bring the <obj> my way", "bring a <obj> over to me",
          "bring over the <obj>", "fetch the <obj>", "fetch me the <obj>", "fetch me a <obj>", "fetch that <obj>",
          "fetch the <obj> for me", "get me the <obj>", "get me a <obj>", "get me that <obj>", "get the <obj> for me",
          "go get the <obj>", "go get me the <obj>", "go get a <obj>", "go fetch the <obj>", "go grab me the <obj>",
          "grab me the <obj>", "grab me a <obj>", "carry the <obj> to me", "deliver the <obj> to me",
          "bring the <obj> back to me", "bring me back the <obj>", "fetch me the <obj> from <place>",
          "bring me the <obj> from <place>", "get me the <obj> from <place>", "go get the <obj> from <place>",
          "grab me the <obj> from <place>", "fetch the <obj> from <place>", "bring the <obj> from <place> to me",
          "bring me a <obj> from <place>", "get the <obj> from <place> for me", "deliver the <obj> from <place>"]
_FETCH_HAND = ["you bring me <obj>", "you bring <obj> please", "bring <obj> to me", "bring me <obj> please",
               "bring here the <obj>", "brin me the <obj>", "bring mi the <obj>", "brung me the <obj>",
               "fetch <obj> for me", "you fetch me <obj>", "<obj> bring me please", "<obj>, bring it to me",
               "the <obj>, bring it here", "you go get <obj>", "you go <place> get <obj> for me",
               "from <place> bring me <obj>", "you bring <obj> from <place>", "bring me <obj> from <place> please"]

# ---------------- go_to: a marker on the map ----------------
_GO = ["go to <place>", "head to <place>", "head over to <place>", "head out to <place>", "drive to <place>",
       "drive over to <place>", "roll over to <place>", "roll on over to <place>", "wheel over to <place>",
       "cruise over to <place>", "make your way to <place>", "make your way over to <place>", "make for <place>",
       "get yourself to <place>", "get over to <place>", "take yourself to <place>", "move to <place>",
       "move over to <place>", "proceed to <place>", "travel to <place>", "navigate to <place>", "go over to <place>",
       "go on over to <place>", "go on to <place>", "go across to <place>", "go on ahead to <place>",
       "set off for <place>", "set course for <place>", "head for <place>", "go straight to <place>",
       "go directly to <place>", "go right to <place>", "swing by <place>", "stop by <place>", "drop by <place>",
       "pop over to <place>", "zip over to <place>", "hop over to <place>", "dash over to <place>",
       "hurry over to <place>", "go visit <place>", "visit <place>", "relocate to <place>", "reposition to <place>",
       "position yourself at <place>", "station yourself at <place>", "park yourself at <place>",
       "get going to <place>", "start driving to <place>", "start heading to <place>", "go over to the <place> spot",
       "take me to <place>", "lead me to <place>", "guide me to <place>", "show me the way to <place>",
       "walk me to <place>", "escort me to <place>", "go to the <place> marker", "drive to the spot <place>"]
_GO_HAND = ["you go <place>", "you go to <place>", "go <place> please", "go in <place>", "go at <place>",
            "please going to <place>", "you must go to <place>", "move to <place> please", "go <place> side",
            "you move to <place>", "drive <place> please", "go to <place> place please", "<place> please go",
            "<place>, go please", "<place>, head over", "<place> is where i need you", "to <place>, go",
            "next stop <place>", "destination <place>", "go to <place> quick quick", "goto <place> pls",
            "go too <place>", "go two <place>", "go to da <place>", "goes to <place>", "go tu <place>", "hed to <place>"]

# ---------------- come / follow / come_back ----------------
_COME = ["come here", "come over here", "come to me", "come over to me", "come closer", "come closer to me",
         "come a little closer", "come a bit closer", "come in closer", "come up closer", "come near me", "come near",
         "come toward me", "come towards me", "come my way", "come right here", "come up to me", "come on over",
         "come on over here", "come over here to me", "come here to me", "come here quickly", "come stand by me",
         "come to my side", "come next to me", "come right over", "get over here", "get closer", "get closer to me",
         "get a bit closer", "move closer", "move closer to me", "drive closer to me", "roll closer", "roll over to me",
         "roll over here", "drive over here", "drive over to me", "approach me", "approach", "draw closer", "come hither",
         "come to where i am", "come to where i'm standing", "come over where i am", "come by my side"]
_COME_HAND = ["you come here", "you come to me", "come here please robot", "you come closer", "come to me pls",
              "come hear", "come heer", "cum here", "kum here", "come ova here", "come over hear", "come closer pls",
              "lumi come", "lumi, come here", "lumi come to me", "here, come to me", "you approach me please",
              "you can come to me?", "you can come here?", "come here come here"]
_FOLLOW = ["follow me", "follow me please", "follow me around", "follow me closely", "follow right behind me",
           "follow along behind me", "follow along", "follow along with me", "follow my lead", "follow us",
           "follow me this way", "follow me over here", "keep following me", "come with me", "come along with me",
           "come along", "come along now", "walk with me", "walk along with me", "walk beside me", "walk behind me",
           "keep up with me", "keep close to me", "keep close behind me", "stick with me", "stick with us",
           "tag along", "tag along with me", "tag along behind me", "go with me", "go where i go",
           "be my shadow", "shadow me", "track me", "escort me", "accompany me", "trail behind me", "walk together with me",
           "come with us", "you're coming with me", "join me, follow me", "follow me to the next booth"]
_FOLLOW_HAND = ["you follow me", "you follow me please", "follow me pls", "fallow me", "folow me", "follo me",
                "follow mi", "you come with me", "come wit me", "come with mi", "you walk with me", "follow follow",
                "lumi follow me", "lumi, follow", "lumi, with me", "you can follow me?", "you go with me",
                "follow me okay", "follow me, robot"]
_BACK = ["come back", "come back here", "come back to your spot", "come back to where you were",
         "go back to where you were", "go back to your spot", "go back to your old spot", "go back to your place",
         "go back to the start", "go back to where you started", "go back to your starting point",
         "go back to your original spot", "go back to your original position", "go back to your previous spot",
         "go back to where you were standing", "head back to your spot", "head back to where you were",
         "return to your spot", "return to your place", "return to where you were", "return to where you started",
         "return to your starting point", "return to your original spot", "return to your original position",
         "return to the start", "return to start position", "return to your previous position",
         "get back to your spot", "get back to where you started", "back to your spot", "back to where you were",
         "back to your starting point", "move back to your spot", "drive back to your spot", "come back to your place",
         "go back where you came from", "return to where you came from"]
_BACK_HAND = ["you come back", "you go back your place", "go back you place", "return you spot", "you return",
              "come bak", "cum back", "come back pls", "go back to you're spot", "you go back where you were",
              "back to start please", "lumi, come back", "lumi come back please", "you can come back now"]

# ---------------- move: a short straight drive ----------------
_MOVE_VERB = ["move", "go", "drive", "roll", "step", "scoot", "slide", "shift", "inch", "back", "edge", "creep"]   # MOVE_VERB's
# words, or a way word the reader knows
_MOVE_WAY = ["forward", "back", "backward", "to the left", "to the right", "left", "right", "ahead"]
_MOVE_AMT = ["", "a bit", "a little", "a tad", "slightly", "just a bit", "1 meter", "a little more", "one step"]
_MOVE = [t for t in _x(_MOVE_VERB, _MOVE_WAY, _MOVE_AMT)
         if not re.match(r"(back|pull) (back|backward|ahead|forward)|(go|edge|creep|inch|nudge|budge|shuffle) ahead|"
                         r"(back|pull) (left|right|to the)|go back(?! \S)", t)]
_MOVE_HAND = ["back up a bit", "back up a little", "back up a tad", "back up 1 meter", "back off a little",
              "back away a little", "back away from me a bit", "reverse a little", "reverse 1 meter", "pull back a bit",
              "take a step back", "take a step forward", "take a step to the left", "take a step to the right",
              "take two steps back", "take one step forward", "side step to the left", "side step to the right",
              "scooch over to the left", "scooch to the right a bit", "move over to the left a little",
              "move over to the right a bit", "give me some room, back up", "you move forward", "you go back 1 meter",
              "you move left a little", "you move right a little", "move forword", "moov back", "go bakwards",
              "mov left", "mov right", "move fwd a bit", "go forward pls", "move back pls", "go backward a little pls"]

# ---------------- turn: the base on the spot ----------------
_TURN = _x(["turn", "rotate", "spin", "pivot", "swivel", "turn yourself", "rotate yourself", "turn your body",
            "rotate your body", "turn your base", "rotate your base", "swing"],
           ["left", "right", "to the left", "to the right", "to your left", "to your right", "left 90 degrees",
            "right 90 degrees", "90 degrees left", "90 degrees right", "90 degrees to the left", "90 degrees to the right",
            "a little to the left", "a little to the right", "a bit left", "a bit right"])
_TURN_HAND = ["turn around", "turn yourself around", "turn all the way around", "turn the other way", "do a 180",
              "do a u-turn", "make a u-turn", "about face", "face the other way", "spin all the way around",
              "do a full spin", "make a left turn", "make a right turn", "hang a left", "hang a right", "take a left turn",
              "take a right turn", "do a left turn", "do a right turn", "do a quick left turn", "turn left on the spot",
              "turn right on the spot", "turn in place to the left", "turn in place to the right", "you turn left",
              "you turn right", "you turn around", "turn lef", "turn rite", "tern left", "tern right", "trun left",
              "trun right", "rotate leff", "turn to left side", "turn to right side", "turn left side", "turn right side",
              "turn left 90", "turn right 90 degree", "turn 90 degree left", "turn 90 degree right"]

# ---------------- look: the head ----------------
_LOOK = _x(["look", "glance", "peek", "gaze", "turn your head", "move your head", "point your head", "turn your eyes",
            "turn your gaze", "eyes", "face", "take a look", "sneak a peek"],
           ["left", "right", "up", "down", "to the left", "to the right", "to your left", "to your right", "upward",
            "downward", "up at the ceiling", "down at the floor", "over to the left", "over to the right",
            "at me", "over here", "this way", "toward me", "straight ahead", "to the front"])
_LOOK = [t for t in _LOOK if not re.match(r"face (up|down|upward|downward|left|right|to|over|this|straight)|eyes (to the|toward)|"
                                          r"(take|sneak) a (look|peek) (up|down|left|right|upward|downward|this)", t)]
_LOOK_HAND = ["look up at me", "look me in the eye", "look me in the face", "look at my face", "eyes on me please",
              "eyes up here", "eyes over here", "head up", "head down", "head left", "head right", "lift your head up",
              "raise your head", "lower your head", "tilt your head up", "tilt your head down", "tip your head back",
              "bow your head", "nod your head down", "chin up", "chin down", "look over your left shoulder",
              "look over your right shoulder", "look over at the left", "look over at the right", "glance up",
              "glance down", "peek up", "peek down", "look skyward", "look at the sky", "look at the ground",
              "look at your feet", "look straight at me", "look this way please", "look over here please",
              "look back to the front", "face forward again", "eyes front", "look a bit more left", "look a bit more right",
              "look a little higher", "look a little lower", "you look left", "you look right", "you look up", "you look down",
              "you look me", "you look at me please", "look at mee", "luk at me", "lok up", "lok down", "look upp",
              "look dawn", "look rite", "look lef", "look leftside", "look rightside"]

# ---------------- lift: the body up / down ----------------
_LIFT = _x(["raise yourself", "lift yourself", "raise your body", "lift your body", "lower yourself", "lower your body",
            "bring yourself", "move your body", "move yourself", "push yourself", "get yourself",
            "drop yourself", "sink yourself", "raise your torso", "lower your torso", "lift your torso"],
           ["up", "down", "up a bit", "down a bit", "up a little", "down a little", "higher", "lower", "all the way up",
            "all the way down"])
_LIFT = [t for t in _LIFT if not re.match(r"(raise|lift)\b.*\b(down|lower)\b|(lower|drop|sink)\b.*\b(up|higher)\b", t)]
_LIFT_HAND = ["make yourself taller", "make yourself shorter", "make yourself a bit taller", "make yourself a bit shorter",
              "get taller", "get shorter", "grow taller", "grow a bit taller", "stand up taller", "stand up tall",
              "shrink down", "shrink a little", "go up a bit", "go down a bit", "go up a little", "go down a little",
              "rise up", "rise up a bit", "squat down", "squat down a bit", "sink down", "sink down a little",
              "be taller", "be shorter", "get yourself higher", "get yourself lower", "body up", "body down",
              "body up please", "body down please", "lift up", "lift down", "lift up a bit", "lift down a bit",
              "raise the lift", "lower the lift", "torso up", "torso down", "you go up", "you go down", "you body up",
              "you body down", "you make tall", "you make small", "make you taller", "make you shorter",
              "raise urself up", "lower urself down", "lift yourself up pls", "lower yourself down pls",
              "get a bit taller", "get a bit shorter", "get lower", "get higher"]

# ---------------- no: the same verbs in other senses, remarks, someone else's body ----------------
_NO = [
    # wave / shake / hand in other senses
    "shake your head", "shake your head no", "shake the bottle", "shake the cup", "shake it off", "shake a leg",
    "shake it up", "shake things up", "shake your hips", "nod your head", "nod yes", "the heat wave is terrible",
    "microwave my lunch", "catch the wave", "wave of people coming", "new wave", "they waved at me", "she shook my hand",
    "he gave me a handshake", "nice wave", "good handshake", "cute wave", "your wave is cute", "your handshake is strong",
    "waving is fun", "the kids love your wave", "do you like waving", "first wave of guests", "sound waves",
    "high five", "gimme five", "fist bump", "thumbs up", "give me a thumbs up", "clap your hands", "clap for us",
    "applause please", "a round of applause", "raise your hand if you agree", "hands up if you're ready",
    "everybody raise your hand", "hands on your head", "hands in the air", "put your hands together",
    # reach / hand / arm in other senses
    "reach me by email", "reach out to our team", "reach out to sales", "reach the top", "reach a deal",
    "give me a hand with the boxes", "i need a hand", "hand me your phone number", "hand in your homework",
    "on the other hand", "hands off", "hands down", "second hand", "a hand of cards", "my arm hurts", "arm wrestling",
    "armed guards", "arm yourself with patience", "stretch before running", "stretch your legs",
    "extend the deadline", "extend my stay", "hold out a little longer", "hold on", "hold up", "hold on a sec",
    "hold your horses", "hold the door", "hold that thought", "offer me a discount", "show me the menu",
    "show me your badge", "show me the way", "show me around", "put your hands up", "put your phone away",
    "put it on my tab", "put that on the list", "fold the paper", "fold the laundry", "fold the chairs",
    "lower the price", "lower your voice", "lower the volume", "drop it", "drop the topic", "drop me a line",
    "relax", "just relax", "take it easy", "rest a bit", "take a rest", "pull yourself together", "pull over",
    "open the door", "open the box", "open the bottle", "open the window", "open the app", "open your mind",
    "open your mouth", "open your eyes", "close the door", "close your eyes", "close the window", "close the app",
    "close the deal", "make a wish", "make a decision", "make a fist when you're angry", "squeeze the lemon",
    # pick / take / get / bring in other senses
    "pick a number", "pick a song", "pick a color", "pick one for me", "pick your favorite", "pick a side",
    "pick up the pace", "pick up the phone", "pick me up at six", "pick me up", "pick up where we left off",
    "take a seat", "take a picture", "take a photo of us", "take a break", "take care", "take your time", "take it easy",
    "take a guess", "take a look at this", "take a deep breath", "take note", "take me seriously", "take the stairs",
    "take the elevator", "take the bus", "get some rest", "get well soon", "get ready", "get it together",
    "get a life", "get real", "get it?", "get lost", "grab a seat", "grab a coffee with me later", "grab some lunch",
    "bring it on", "bring your friends", "bring up the topic", "bring me luck", "bring the kids next time",
    "fetch the ball", "go fetch, doggy", "deliver a speech", "carry on", "carry on talking",
    "i'll get the cup myself", "i'll take the bottle", "my son took the cup", "someone took my bottle",
    "the cup is on the table", "that cup is mine", "i love this cup", "this bottle is empty", "what a nice cup",
    # go / come / follow / back in other senses
    "go ahead", "go ahead, ask", "go on, tell me", "go figure", "go for it", "go team", "here we go", "let it go",
    "go easy on me", "how's it going", "go get 'em", "go away", "get out of here", "go to sleep",
    "go to bed", "go to school", "go to work", "go to hell", "go back to sleep", "go back to the topic",
    "come on", "come on now", "oh come on", "come again", "come in", "come on in", "come to think of it",
    "come up with an idea", "come true", "come clean", "come what may", "comes with a warranty", "where do you come from",
    "follow the signs", "follow the rules", "follow your dreams", "follow your heart", "follow up by email",
    "follow us on instagram", "follow the news", "i don't follow", "i follow you", "follow that car",
    "back to the topic", "back in a minute", "be right back", "back me up on this", "get back to work", "welcome back",
    "come back later", "come back tomorrow", "i'll be back", "she's coming back", "the guests will come back",
    # move / turn / look / lift in other senses
    "move on", "let's move on", "move on to the next topic", "moving on", "that movie moved me", "nice moves",
    "make a move", "move it, people", "turn the music up", "turn up the volume", "turn down the volume", "turn it off",
    "turn on the light", "turn off the tv", "turn the page", "it's your turn", "my turn", "take turns", "turn red",
    "turn into a car", "turn in your homework", "turn it down a notch", "look it up", "look out", "watch out",
    "look who's here", "look sharp", "look busy", "look alive", "look forward to it", "look after the kids",
    "look into it", "look at this mess", "you look great", "you look tired", "looks good", "looking good",
    "lift my spirits", "lift the ban", "lift weights", "take the lift", "where is the lift", "raise the price",
    "raise the bar", "raise a question", "raise your voice", "keep your voice down", "speak up", "cheer up",
    "lighten up", "grow up", "shut up", "hurry up", "stand up for yourself", "stand up comedy", "sit down please, everyone",
    # things Lumi cannot do, said like a motion
    "fly up to the ceiling", "fly up", "fly to the ceiling", "fly up to the sky", "fly up high", "jump up to the ceiling",
    "jump up", "jump up high", "climb up to the ceiling", "float up to the ceiling", "climb the wall", "fly away",
    # someone else's body, reports, talk
    "my kid wants to wave at you", "my son is following me", "the dog follows me", "he moved to the left",
    "the car turned right", "she looked up", "my mom raised her hand", "a robot at the mall waved at me",
    "robots that follow people are cool", "following people is hard", "turning is hard for robots",
    "lifting heavy things is hard", "picking up cups is tricky", "bringing coffee is a nice job",
    "can your friend robot wave", "the other robot can turn around", "the barista robot picks up cups",
]

INTENT = {
    "wave": _framed(_WAVE, 0.12, ger=_WAVE[:30]) + _WAVE_HAND,
    "arm_reach": _framed(_REACH, 0.12, ger=_REACH[:25]) + _REACH_HAND,
    "arm_fold": _framed(_FOLD, 0.12, ger=_FOLD[:20]) + _FOLD_HAND,
    "arm_open": _framed(_OPEN, 0.15, ger=_OPEN[:10]) + _OPEN_HAND,
    "arm_close": _framed(_CLOSE, 0.15, ger=_CLOSE[:10]) + _CLOSE_HAND,
    "pick": _framed(_PICK, 0.1, ger=_PICK[:20]) + _PICK_HAND,
    "fetch": _framed(_FETCH, 0.1, ger=_FETCH[:20]) + _FETCH_HAND,
    "go_to": _framed(_GO, 0.06, ger=_GO[:20]) + _GO_HAND,
    "come": _framed(_COME, 0.15, ger=_COME[:20], kind="come") + _COME_HAND,
    "follow": _framed(_FOLLOW, 0.15, ger=_FOLLOW[:20]) + _FOLLOW_HAND,
    "come_back": _framed(_BACK, 0.15, ger=_BACK[:16]) + _BACK_HAND,
    "move": _framed(_pick(_MOVE, 0.5), 0.03, kind="move") + _MOVE_HAND,
    "turn": _framed(_TURN, 0.05, kind="turn") + _TURN_HAND,
    "look": _framed(_LOOK, 0.04, kind="look") + _LOOK_HAND,
    "lift": _framed(_LIFT, 0.06, kind="lift") + _LIFT_HAND,
    "no": _NO,
}

if __name__ == "__main__":
    for k, v in INTENT.items():
        print(f"{k:10} {len(v)}")
    print("total", sum(map(len, INTENT.values())))
