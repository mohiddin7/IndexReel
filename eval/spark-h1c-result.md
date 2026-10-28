# H1c result: routing frames vs whole video (Oct 27 2026)

Protocol: `eval/spark-h1c.md`. Code: `scripts/spark_h1c.py`. 86 pairs (18 expected yes, 68 expected no) on 12 new edits never used before, both arms (V whole video, F frame sheet) asked once each. Transport failures were resumed; no answer was re-asked. Spend $2.50.

## Policies against the frozen bar (yes at least 90%, 0 false yes, cost at most 70% of V)

| Policy | Yes | False yes | Pairs sent to video | Cost vs V | Verdict |
|---|---|---|---|---|---|
| V whole video always | 18/18 | **0/68** | 86 | 100% | baseline |
| F frames always | 17/18 | 4/68 | 0 | 58% | fails |
| R router (portrait goes to video) | 17/18 | 1/68 | 38 | 79% | fails |
| C cascade (frames, then video for yes/unsure) | 17/18 | 0/68 | 22 | 83% | fails on cost |
| RC router then cascade | 17/18 | 0/68 | 50 | 93% | fails on cost |

**No policy meets the bar, so V stays the only judge.** The cheap policies that are safe (C, RC) save 7 to 17%, which is not worth the extra moving parts.

## What we learned

- **The whole-video judge generalises.** It got 18/18 and 0 false yes on four layouts it had not seen: portrait zoom, a small inset over blurred fill, picture-in-picture over another real recording (both recordings found), and split screen. With H1 it has 0 false yes in 169 non-copy pairs on layout-edited clips (not independent; Wilson upper bound 2.2%). This is a clean holdout confirmation of the main finding.
- **Frame sheets fail beyond vertical clips.** F gave false yes on 3 of 16 `vb` pairs and on a picture-in-picture pair (landscape), so the router's "portrait only" rule misses real cases (R has 1 false yes). The failure is the same as in H1: when the real picture is small, Spark invents matching details. F also missed the split-screen copy (said no).
- **The cost story was wrong.** Frame sheets send about 890 input tokens against 9,700 for video, but they make Spark think longer: 2,241 output tokens per call against 1,496. Output tokens cost 3.4 times as much, so F costs $0.0106 per pair against $0.0185, not the 40% seen in H1.
- **So the lever is elsewhere.** Judging fewer pairs (the SSCD prefilter: 84 of 435 pairs) saves about 80%; frame sheets save 17% at best. The doc check below found two cheaper dials, `reasoning.effort` and prompt caching.

## Limits

12 clips from the same footage; layouts I chose; one run; the cost ratio depends on clip length (the new clips are at most 20 s).
