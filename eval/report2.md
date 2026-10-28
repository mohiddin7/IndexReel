# Held-out run 2 result: the fixed pipeline on the fresh final2 split (Oct 28 2026)

Protocol: `eval/heldout2.md`, frozen at `5e95007` before any final2 clip was opened. Code at `23614a4`: the matcher's bands are unchanged from run 1, and the verifier now has fixes (a) and (b) from `6119685`. Recordings come from `cluster.resolve`. Script: `scripts/heldout.py prepare2` and `score2`. 48 clips (blocks b17 to b24, 16 families, 3 versions each), 1,128 pairs, run once, no human decisions, no addendum.

## Verdict: PASS

| | result | bar |
|---|---|---|
| 1 False merges (joined negative pairs) | **0 / 1,080** (Wilson 95% 0.0000 to 0.0035); no recording mixes two families | 0 |
| 2 Positives joined | **48 / 48** (Wilson 95% 0.93 to 1.00) | at least 40 |
| Recordings found | **16** (truth 16), all with status `merged` | reported |
| Compilation flags (all would be false) | 0 | reported, expected 0 |
| True pairs demoted by fix (b) | 0 of 34 | reported |
| Verifier cost | $0.170 at list prices, 84 pairs verified | reported |

## What happened, pair by pair

- **Matcher:** 34 pairs `merged`, 50 `unresolved`, 1,044 `apart`. It merged 34 of 48 positives and no negative. The highest negative scored aligned 0.461 (`N18__refilm_sim ~ N22__refilm_sim`), below `merge_at` 0.55. The lowest merged positive scored 0.555.
- **Fix (b), verifying merged pairs:** the verifier said `same` on all 34 merged positives. Nothing was demoted, so fix (b) cost no recall here. There was also no merged negative for it to catch.
- **Unresolved pairs:** the verifier said `same` on all 14 unresolved positives (6 orig+refilm_sim, 8 pip+refilm_sim; aligned as low as 0.328). It said `different` on all 36 unresolved negatives, including the target against its own look-alike in block 18 (aligned 0.445). It never abstained, and every pair's confidence was 1.00.
- **Fix (a), conflicts:** none arose, so nothing was re-asked at full fidelity.
- **By version pair:** orig+pip 16/16, orig+refilm_sim 16/16, pip+refilm_sim 16/16.

## Run 1 against run 2

| | run 1 (`eval/report.md`) | run 2 |
|---|---|---|
| Positives joined, matcher alone | 35 / 48 | 34 / 48 |
| Positives joined, matcher plus verifier | 48 / 48 | 48 / 48 |
| False merges | 2 / 1,080 | 0 / 1,080 |
| Highest negative aligned score | 0.597 (merged) | 0.461 (unresolved) |
| Verifier cost | $0.055 | $0.170 (merged pairs now verified too) |

## What this says

- On a second fresh split, the shipped pipeline found every version of every recording and joined nothing it should not. That meets both bars, which run 1 did not.
- **This PASS does not show the fixes catching an error.** Run 1 failed through two specific paths: a negative above `merge_at`, and a single cheap `same` on a negative. Neither path came up here. No negative reached `merge_at`, and the verifier made no wrong `same`. Fix (b) ran on 34 merged pairs and cost no recall. Fix (a) never triggered. The evidence that the fixes repair run 1's errors comes from the unit tests (`tests/test_verify.py` replays the run-1 verifier error), not from held-out data.
- Verifying the merged pairs roughly tripled the verifier's cost, to $0.17 for 48 clips, at no recall cost on this split.

## Limits

These are simulated copies of 16 recordings, with the same PiP template and re-film simulation as run 1. A 0/1,080 result bounds the false-merge rate at 0.35% (Wilson 95%) on copies like these, not on copies in the wild. With 16 families, one hard look-alike more or less changes the picture, as run 1 showed. The real re-film arm (`eval/heldout2-refilm.md`) is pre-registered and not yet run. Run once.
