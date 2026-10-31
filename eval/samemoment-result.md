# Same moment, two cameras: result (Oct 30 2026)

Protocol: `eval/samemoment.md`, frozen at `1bca24b`. Amendment 1 (`29fce3b`), the scorer change `5ffd361` and Amendment 2 (`70791ae`) were all committed before any claps, manifest or scorer step on these clips. The run used main at `70791ae`, with `scripts/samemoment.py` as of `5ffd361`.

The data is 5 takes I filmed on Oct 30 afternoon with an iPhone and Ray-Ban Meta glasses at the same time: `street` t1 and t2, `crossing` t1 and t2, and `talk` t1. There is also one iPhone take of a lookalike street (`street2`) with no glasses partner. WhatsApp copies of all 11 clips make 22 clips, plus 4 control clips.

`claps` proposed each clap and I confirmed every one by ear before anything was scored. In my words: "all claps are right at the center of audios and they are exactly same as whatsapps ones." The run was done once, on Oct 30 from 23:07 to 00:08 UTC (claps to report), with a fresh Spark cache.

## Verdict: FAIL (bars 2 and 4)

| | result | bar |
|---|---|---|
| 1 False "same moment" from S1, S2 and M, over all negatives and controls | **0 / 103** (50 raw, 50 copy-copy, 3 controls; 95% upper bound 0.029) | 0 |
| 2 Same-moment recall (S1 or S2, lag within 0.2 s) | **0 / 5** | at least 4 of 5 |
| 3 P "same place" on lookalike pairs | **0 / 4** | 0 |
| 4a M `same_place` yes on lookalike pairs | **3 / 4** | 0 |
| 4b Cards whose cited thing is in both frames | **55 / 63** (87.3%), 0 unmarked | at least 90% |
| Recall on the WhatsApp copies | **not measured** (scorer defect, below) | reported |
| `indexreel match` on all raw clips | **0 / 5** same-moment pairs joined (aligned 0.19 to 0.33: 4 `unresolved`, 1 `apart`), 7 recordings. Matcher only, no verify, at `ce3660b`. The matcher alone merged the 4 same-scene, same-device pairs at another time (aligned 0.57 to 0.71), as on the same-view sets. | reported, must join none |
| Spark cost | $0.8713 at list prices, 32 pairs, all answers completed | cap $1.50 |

Bar 2 alone makes this a FAIL. Bars 4a and 4b fail as well.

## The five same-moment pairs

The truth lag is the iPhone clap minus the glasses clap. Lags are in seconds.

| take | truth lag | sound z, lag | picture z, lag | landmark | S1, S2 | P inliers | M place, occasion, moment |
|---|---|---|---|---|---|---|---|
| street t1 | 21.36 | 9.02, 21.37 | 10.94, -40.92 | 0.002 | no, no | 8 | yes, yes, unsure |
| street t2 | 16.99 | 7.15, 16.99 | 18.19, -1.80 | 0.001 | no, no | 6 | unsure, unsure, unsure |
| crossing t1 | 40.61 | 9.00, 40.59 | 43.19, 46.92 | 0.000 | no, no | 13 | yes, yes, unsure |
| crossing t2 | 15.09 | 5.72, 28.49 | 10.51, -33.96 | 0.001 | no, no | 12 | yes, yes, unsure |
| talk t1 | 18.25 | 9.92, 18.26 | 14.22, 27.64 | 0.011 | no, no | 0 | yes, unsure, unsure |

- **Sound:** the sound peak sits within 0.03 s of the truth lag on 4 of 5 pairs. Crossing t2 is the exception: z 5.72, at a wrong lag. Of those 4, three clear the sound bar of 8 and street t2 reaches 7.15.
- **Picture:** on every pair the picture peak is strong (z 10 to 43) but 6 to 62 s away from the sound lag, so S1 refuses all 5.
  - The two cameras faced different ways, and the picture envelope (the mean of a 16×9 grey frame) follows each view's own motion, not a shared event.
- **S2:** the landmark fingerprint stays at or below 0.011, against its bar of 0.03, so S2 refuses all 5 as well.

## Negatives and controls (bar 1)

- No negative or control passed S1 or S2. M answered `same_moment` yes on none of its 32 pairs: on the 5 positives it said `unsure` every time.
- Highest sound z on negatives, by device pair: iPhone-iPhone 12.79, iPhone-glasses 10.24, glasses-glasses 6.94.
  - 8 of the 103 negatives reach sound z 8 or more. The highest are the two `crossing` iPhone takes at different times (12.8, raw and copy alike): the crossing's beep once a second gives both clips the same sound pattern.
  - Every one of the 8 was refused because its picture lag disagreed. The highest picture z on a negative is 111.
- Controls: S1 and S2 refused all 3.
  - The two audio swaps put the sound peak at the true sound lag, as constructed, at z 6.7 and 7.2. Their picture lags disagreed.
  - The shared-music pair reached sound z 5.25.

## The model's evidence (bar 4)

- **4a: M said `same_place` yes on 3 of the 4 lookalike pairs.** In each, the lone `street2` iPhone take was set against a `street` clip, and each yes cited 2 anchors.
  - The truth is the manifest's scene label, fixed before any scoring.
  - The geometry check agrees with the label: 0, 0, 0 and 4 SIFT inliers on those pairs, against 0 to 13 on the positives and 6 to 275 on same-place pairs at another time.
- **4b: 55 of 63 cards were marked present.** A reviewer other than me did the marking, from the cards and frames alone, without the manifest or any answer.
  - Its reading, settled before it counted: every concrete object a line names must be visible in both frames, and a sound can't be in a frame.
  - The 8 "no" cards:
    - 3 name a low sun that is missing from one frame;
    - 1 names houses missing from one frame;
    - 1 names a fixture's base missing from one frame;
    - 1 names a second figure missing from one frame;
    - 2 are sound-only transients.
  - The protocol didn't say how to read a line naming several things, or a cited sound. A looser reading, checking only the main object, gives 59 of 63 (93.7%). It is reported only as a secondary count: the strict reading was fixed before counting, and choosing the looser one after seeing the strict one fail would move the bar.
- M on the other pairs:
  - same place at another time: `same_place` yes on 8 of 8 and `same_occasion` yes on 7 of 8;
  - cross-scene: no `same_place` yes on any of 12 (7 no, 5 unsure).
- M's answers in full cite real scene text, so they stay in the private data folder and are summarised here by count, not quoted.

## Scorer defect: copy recall not measured

The protocol reports "recall on the copies" and excludes only the mixed raw-copy form of a take, which implies copy-copy positive pairs: a take's iPhone copy against its glasses copy. `pairs()` at `1bca24b` (unchanged since) skips a same-take pair before it adds the copy form, and the selftest froze that. So the scorer printed `copies_found: 0`, which means not measured, not none found.

This touches no bar: all 50 copy-copy negatives were scored, and bar 2 counts raw positives only. The missing pairs were not added after the results were seen.

## What this says

- On two cameras 5 to 15 m apart and facing different ways, the frozen rule found no shared moment. The sound lined up on 4 of 5 takes, but the picture signal in the rule doesn't see a shared event across viewpoints, and the rule requires both.
- **Post hoc, not a claim:** a sound-only rule (sound z ≥ 8 at any picture lag) would have found 3 of 5 positives at the right lag. It would also have claimed 8 of the 103 negatives, led by the two `crossing` takes at different times.
  - Where a place has a periodic sound, sound alone matches a different moment. The picture check is what kept bar 1 at 0.
  - Any sound-led rule needs its own pre-registered test with periodic-sound negatives.
- M never claimed a same moment, but it called two lookalike streets the same place 3 times out of 4.
- Strict local geometry (P) kept those pairs apart.

## Limits

One person, one iPhone, one pair of glasses and one afternoon. 5 of the 9 planned takes exist (Amendment 2), so the bounds are wide:
- 0 of 103 bounds the false-claim rate only at about 2.9%;
- 0 of 4 lookalikes bounds the same-place error at about 53%.

The lookalike pairs all rest on one lone clip. The start gaps were 15 to 41 s instead of 5 to 15 s; the lag search covers them (Amendment 2). The run was done once.
