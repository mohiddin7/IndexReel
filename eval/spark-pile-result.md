# Spark pile test: result (Oct 27 2026)

Protocol: `eval/spark-pile.md` (frozen before scoring; Addendum A written after the first run). Code: `scripts/spark_pile.py`. Exploratory, 30 clips, one run.

## Frozen rules

| Rule | Bar | Result |
|---|---|---|
| 1 Candidates keep every copy family connected | 5 of 5 | **SSCD 5 of 5** (19 of 19 true copy pairs kept in 84 candidates). PDQ top-4: 2 of 5 (7 of 19). |
| 2 Cost | at most 100 pairs, $3 | **PASS**: 84 pairs (19% of 435), 64 new Spark calls $1.26 (20 reused from pilot 3), 265 s. |
| 3 False merges | 0 | **PASS**: 0. The compilation merged with nothing. |
| 4 Recordings found | 18 | **FAIL: 24.** My merge rule needed the shared span to cover 60% of both clips. |

Why rule 4 failed: Spark said `same_footage` yes on all 19 true copy pairs, but reports the span where the shared *event* is visible (about 7 s of a 30 s security clip), so true copies were classed as partial links. This is a design error in my rule, not a Spark error.

## Post-hoc rule (Addendum A, development evidence only)

Merge on yes; a clip yes-linked to two clips that Spark says are not the same footage is a compilation, and its links stay partial. Twelve never-asked neighbour pairs were asked (12 calls, $0.27); Spark said no for every pair that mixed A1, A3 or N1 (the three recordings inside the compilation) and yes for the compilation against copies of the same recording.

Result: **18 recordings, 0 false merges, only `A1N1A3_e4` flagged as a compilation**, recording sizes 4, 4, 3, 3, 2 and thirteen singletons. Total new Spark cost $1.53 for the whole pile. Because the rule was chosen after seeing the failure, this shows the loop can work, not that it does.

## What this says

- A free matcher can shrink the work: SSCD's four best partners per clip kept every true copy; PDQ's did not (it ranks true copies beyond position 4 for 12 of 16 clips, because layout edits blind it). 84 calls instead of 435.
- Cost at larger piles, extrapolated from $0.02 a call: all pairs about $99 at 100 clips and $894 at 300; top-4 about $5 and $14. The extrapolation assumes the candidate count grows like 3 per clip and that real piles keep the true copies in the top 4. Neither is tested.
- Spark's spans are event spans, not clip coverage. Do not use coverage to decide merges. Use pair consistency instead (the compilation check).
- The failure map matters more than the pass: the compilation was only caught by checking pairs I had not asked. A pile where the cheap matcher misses a link would silently split a recording.

## Limits

Easy true families (ffmpeg edits of five clips), five of them; one compilation; no real re-films; SSCD ranked edits well here but PDQ-style blindness on re-films is still unmeasured for Spark; the post-hoc rule was tuned on this pile.
