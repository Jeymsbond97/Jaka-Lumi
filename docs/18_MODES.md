# Lumi's four modes

Four switches (dashboard, the Lumi app, `POST /assistant/modes`): **Greeter**, **Patrol**, **Wave** (`wave_greet`),
**Welcome** (`welcome`). Each works on its own, any mix may be on; `lumi.py` runs while any of them is on and stops
when all four are off (the hand comes down first). Owner's rules of 2026-11-16.

| Mode | What Lumi does |
|---|---|
| **Greeter** | Stays where it is and does everything except going somewhere: greets people who come close, talks, answers, sings, arm moves, "look at me". An order to go somewhere is refused ("switch on Patrol"). |
| **Patrol** | Everything Greeter does, plus drives and whole tasks (go to a point, routes and loops, fetch, missions). |
| **Wave** | Alone: the hand is always up in `wave_start` (also on drives, e.g. a dashboard loop of markers); a new person 0.8 to 6 m on the way: stop, 3 waves, drive on (each person once, until they leave the cameras' view); someone waving 1 to 5 m: turn to them and wave back while they wave; keep alive. Near home on the way to the charger it ignores people. With Greeter or Patrol on too: it only answers people who wave (on a drive it stops, raises the hand, waves, lowers it slowly to look, drives on); no waves at everyone, no keep alive. |
| **Welcome** | Only on the charger (it can't be switched on elsewhere): waves at each new person 0.8 to 6 m, waves back at people who wave 1 to 5 m, keep alive. |

**The hand:** on the charger it rests up in `wave_start`, with or without Welcome, and the next moves start from
there. Wave alone: always up. Greeter or Patrol on (also with Wave): a drive starts by lowering it slowly to `look`,
and the drive and its orders go on from `look`.

**Talk:** with only Wave and/or Welcome on, Lumi does not talk, take wake words or orders; it only waves. With Greeter
or Patrol on too, it greets, talks and does orders; a conversation comes first and the waving waits. Called while
driving (Greeter or Patrol), it stops, talks, and drives on to the same place after the conversation.

**Blocked way:** Lumi says so aloud (also with only Wave on) and tries the same place again until the way is free (a
loop, or a Wave trip; a single trip by voice waits for "try again" / "go around it").

**Keep alive** (part of Wave alone and Welcome, no switch): any wave starts a 30 s count. 30 s without a wave: on the
way, Lumi stops, turns toward the nearest person it sees at any distance (else straight ahead), waves 3 times and
drives on; at home it does that every 15 s until someone comes into range or waves.

**Safety:** the arm waves only with the base stopped (it waits for the base to stand), with nobody within 0.8 m
(`IDLE_CLEAR_M`), not while holding something, not in a conversation or task; a new drive waits for the swings to end.
STOP stops everything and switches Wave and Welcome off. Collision limits in Cobo π are still the defaults: test with
someone at STOP.

Values: `tasks/wave_greet.py` and `assistant/lumi.py`, listed in [TUNING.md](TUNING.md). The same text is in the Lumi
app repository, `docs/LUMI_MODES.md`.
