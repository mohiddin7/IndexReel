# Same moment v2: pre-registration for a fresh test (written Oct 31 2026, before any new clip exists)

Nothing under `data/samemoment2/` existed when this was written. The rule, the run script and the two played tracks stay in my private research folder for now; their sha256 hashes below pin them, so any change after this commit would show.

## What is frozen

| file | sha256 |
|---|---|
| `samemoment_v2.py` (the rule) | `f2c68597fbdf6fac1c5b573b6565df70a4f64017d38379bc951246f8835f3154` |
| `run_v2.py` (pairs, controls, bars) | `9b5b169e53ea5baf8c19e7debdf6c8a41febb6941f58e7f1b9ece53ce46454b0` |
| `beep_1hz_play.m4a` (the beep track the phone plays; 1 kHz, 0.15 s every 1.0 s, 180 s) | `b7fd01997f86f9f4fb4b04246573703a2be326922946e9cb4578a3fcc434a4dc` |
| `Hall_of_the_Mountain_King_play.m4a` (music track, same as Oct 30) | `b92c9d9fe4130cafa18bbb470922c8f7a1ad947f2ac617fbc14bf3015de6abe5` |

Run it once, after the manifest exists. Nothing is changed after a result is seen. Run `python -I samemoment_v2.py selftest` first (synthetic, no media): it must print `selftest ok`.

## The rule in plain words

Sound proposes the lag, and the rule only believes it when the lag is identifiable. No picture leg (see "What was dropped").

1. **Window:** each clip from 1.0 s after its start to 2.0 s before its clap (the clap is the truth and the rule never sees it).
2. **Sound:** 24 mel-band log energies at 50 Hz, each minus its 1 s running median. The two clips are cross-correlated band by band over all lags, summed over bands, and scored only where they overlap by 8 s or more.
3. **Three tests, all must hold, else the answer is "cannot tell":**
   - **Periodic?** If both windows repeat on themselves (self-correlation 0.15 or more at a spacing of 0.5 to 20 s), refuse. A beep or a steady beat gives a peak at every lag.
   - **Stands out?** The best lag scores at least 2.0 times the second-best lag outside a 0.5 s guard.
   - **Repeats in the clip?** Cut the shorter window in thirds. Each third, searched against the whole other clip, must score 4.0 robust-z or more within 0.3 s of the lag; at least 2 of 3 must.
4. **Output:** `sound lines up` (the claim is: the two soundtracks come from the same moment, at this lag) or `cannot tell` plus the reason. The rule never says "not the same moment".

Thresholds come from the Oct 30 dev data (below). They are not changed.

## Dev numbers (Oct 30 takes; DEV, tuned on them; `dev_pairs_v2.csv`)

5 same-moment pairs, 100 negatives in raw and copy form (50 + 50), 3 controls. Old rule on the same data: 0 of 5, found 0.
- Found at the right lag: **4 of 5** (lag error 0.01 to 0.02 s). Crossing t2 is "cannot tell" (best/second 1.39, the crossing's beep is loud on the iPhone).
- **0 of 101** negatives and shared-sound mixes claimed; the highest negative best/second ratio was 1.80. The two crossing iPhone takes at different times (sound z 12.8 under the old rule) are refused as periodic.
- Swapped soundtrack: 1 of 2 swap controls claimed (the street one). The sound there really does line up with the other clip, so a sound rule cannot see the swap.
- WhatsApp copy form: 3 of 5 positives found (crossing t1 falls to ratio 1.92, just under 2.0).

## Fresh test data

I film, iPhone braced plus Meta glasses worn, sound on, nothing trimmed, as on Oct 30: about 90 s of scene, walk 5 to 15 m to the side, start glasses (start gap 5 to 40 s), stand still, no deliberate sound, walk back, one loud clap in both views, wait 2 s, stop. Clips in `data/samemoment2/raw/<scene>_t<take>_<device>.<ext>` and `manifest.csv` with the columns of `eval/samemoment.md`; `place_kind` = street, park, beep, music (or indoor). I confirm every clap by ear before scoring.

**Minimum 8 takes:** `street_a` t1, t2 (second at least 10 min later); `park` t1, t2 (same); `beep` t1, t2 (a phone not filming plays `beep_1hz_play.m4a` from 0:00 within 1 to 2 m of the iPhone; take 2 at least 5 min later); `music` t1, t2 (same with the Mountain King track). **Optional:** `street_b` t1 (lookalike street), one indoor take. WhatsApp copies are optional; if made, copy-form results are reported, not barred.

**Pairs and truth:** positives = the iPhone and glasses clip of one take; truth lag = iPhone clap minus glasses clap. Negatives = every other pair of different takes (same place other time, lookalike, cross-scene). With the minimum: 8 positives, 112 negatives raw.

**Constructed controls** (`run_v2.py controls`, no filming): *swapped soundtrack* (2): the picture of `street_a` t2 iPhone with the sound of its t1 iPhone, paired with t1 glasses; the same for `park`. *Shared sound mix* (2): the music track, then the beep track, mixed 6 dB under the clip's own sound at 0 s under one clip and 5 s under a clip that does not overlap it (`park_t1_iphone` with `street_a_t2_glasses` for music; `street_a_t1_iphone` with `park_t2_glasses` for the beep).

## Bars

1. **0 false "same moment"** over all negatives (raw) and the 2 shared-sound mixes. Report the 95% upper bound (about 0.026 with 114). Failing bar 1 is a FAIL whatever else happens. This includes the real hazards: the beep played at another time, the music played at another time, the same place at another time, a lookalike street.
2. **Recall:** at least 75% of the raw positives, rounded up (6 of 8), claimed with the lag within 0.2 s of the truth.
3. **0 positives claimed at a wrong lag** (a wrong lag is a false claim, not a miss).

**Reported, not barred:** the 2 swapped-soundtrack controls. They are expected to be claimed (the sound does line up), so I do not count them in bar 1. A product must not present "sound lines up" as "these pictures are the same moment" without a check on the picture that this rule does not have. Also reported: every pair's numbers, abstention rate on positives and on the beep and music takes separately, copy-form results.

## What a pass would and would not mean

A pass shows: on a different day, with a different hazard set, sound-led identifiability found the lag and made no false claim. It does not show: cameras far apart (sound travel adds 0.3 s per 100 m), speech or crowds, clips under 40 s, reposts re-mixed with new music, or a deliberate edit. With 8 positives, 6 of 8 has a Wilson 95% interval of about 0.41 to 0.93. 0 of 114 bounds false claims only at about 2.6%.

## What was dropped, with numbers (dev)

- **Picture motion at the sound lag** (frame-difference energy, global and 3x3 regions, 1 s smoothing, z against other lags): on the 5 positives z = -0.5 to 0.7 (global) and -0.7 to 1.1 (regions); the swap controls -1.0 and -2.4. It does not see a shared event across different views.
- **Sound against own picture** (is a clip's sound coupled to its own motion; would catch a swap): genuine clips z = -1.6 to 2.7, swap clips -1.8 and 1.6. No separation.
- **P (local-feature place check) as a veto:** positives gave 0 to 13 inliers (the talk positive 0), lookalikes 0 to 4. A veto at "clearly different" would kill a true positive. Dropped.
