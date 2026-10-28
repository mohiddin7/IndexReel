# Spark pile test: cheap matcher first, Spark only on the candidates

Written Oct 27 2026 before the pile was scored or any Spark call was made for it. Exploratory, not the gate. Pilots 1 to 3 (`eval/spark-pilot*.md`) asked Spark about hand-picked pairs. A real pile has no hand-picked pairs, and asking Spark about every pair costs n²/2 calls. This test checks the product loop on a 30-clip pile: a free matcher proposes candidate pairs, Spark judges only those, and the judged pairs are grouped into recordings.

## Question

Does "SSCD proposes, Spark judges" recover the right number of distinct recordings in a pile of 30 clips, with no false merges, using far fewer than all 435 pair calls?

## Pile (30 clips, all overlays masked as in pilot 3)

- The 24 clips of pilot 3 (`data/spark_pilot3/clips`: A1 to A4, B1, B2, N1 to N6 and their ffmpeg edits, plus the compilation `A1N1A3_e4`).
- The 6 sources of pilot 1 (Y, M, I: Chelyabinsk meteor, three cameras; C0, C4, MA: Starship IFT-1, three cameras), with the same top and bottom 13% mask. These are famous events, so they are distractors that add same-scene, different-camera pairs, not evidence about new footage.

Files go to `data/spark_pile/clips` (ignored by git). Footage is third-party and private research only, as in pilot 2.

## Ground truth (by construction)

18 distinct recordings: A1, A2, A3, A4, B1, B2, N1 to N6, Y, M, I, C0, C4, MA. Full copies of one recording (same recording even after edits):
- A1: A1, A1_e1, A1_e2, A1_e3. A2: A2, A2_e5. A3: A3, A3_e1, A3_e2, A3_e3. A4: A4, A4_e1, A4_e2. B2: B2, B2_e1, B2_e2.
- `A1N1A3_e4` is a compilation (A1 for 6 s, N1 for 6 s, A3 for 6 s). It is not a 19th recording. It has partial links to A1, N1, A3 and their edits, and must never merge them.

## Stage 1: candidate pairs (free, rule frozen now)

Embed every clip with SSCD as in `src/indexreel/sscd.py` (one frame per second, mirror-aware) and score all 435 pairs with `aligned_score`. Candidates are the union of
- each clip's 4 highest-scoring partners (k = 4: the largest family has 4 clips, so one slot of slack), and
- every pair with aligned score at least 0.60.

No threshold or k is tuned after seeing scores. Also computed, for comparison only: the plain `score`, and PDQ (`indexreel.match.score`) with the same top-4 rule.

## Stage 2: Spark on the candidates

The pilot 3 prompt v3, unchanged (`scripts/spark_pilot3.py`), model `muse-spark-1.3`, Standard mode, no tools. Each candidate pair is asked once, orientation fixed by a seeded coin (seed 2611). A pair already answered in pilot 3 (same files, same prompt, both orders) reuses the answer for the seeded orientation; no other pair is re-asked, and no prompt edits.

## Stage 3: group into recordings (rule frozen now)

- **Merge** a pair when Spark says `same_footage` yes and gives spans in both clips that each cover at least 60% of that clip's duration.
- **Partial link** when it says yes but a span covers less than 60% of either clip. Partial links never merge.
- **Needs review** when it says yes without spans. Not merged. Reported, and the count is shown both with and without them merged.
- **Unresolved** when it says unsure. Never merged.
- Recordings = connected components of merges, minus one for each compilation (a clip with partial links to two or more components that are not merged with each other).

## Pass bar (decided now)

1. **Candidates keep every family together:** using only candidate pairs, each of the 5 copy families is connected (a copy is allowed to reach its family through another copy). Also report the share of all true copy pairs that are candidates.
2. **Cost:** at most 100 candidate pairs (23% of 435) and at most $3 for the Spark stage.
3. **No false merges:** no merge between two clips of different recordings, and the compilation merges with nothing.
4. **Count:** recordings found = 18, or 17 to 19 reported as a near miss with the splits and joins named.

PASS needs 1 to 3 and a count of 18. Rule 3 failing is a FAIL for the loop whatever else happens.

## Reported, not scored

- Rank, under SSCD and under PDQ, of every true copy of each clip; which edit types (vertical reframe, picture-in-picture, compilation, swapped audio) the matcher ranks low.
- Spark yes/no/unsure counts on the candidate pairs, with the false candidates and what Spark said about them.
- Tokens, cost and wall-clock for the Spark stage, and the same extrapolated to piles of 100 and 300 clips under "all pairs" versus "top-4 plus threshold".

## Limits

One pile, built by me from ffmpeg edits and a few real cameras; the true families are small and easy to rank next to hard same-scene negatives. n = 30 shows whether the loop works and where it breaks, not a rate. Real re-films (the phone set) are not in this pile; they are a separate test on SSCD versus Spark.

## Addendum A (Oct 27, written after the first run, before the verify calls)

First run, frozen rules: stage 1 passed (SSCD kept 19/19 true copy pairs, 84 candidates; PDQ top-4 kept 7/19 and connected 2 of 5 families), cost $1.26 for 64 new calls, 0 false merges, and Spark answered yes on all 19 true copy pairs. **Rule 4 failed: 24 recordings found, not 18**, because my merge rule needed the shared span to cover 60% of both clips. Spark reports the span where the shared *event* is visible (for the 30 s security clips, about 7 s of meteor), so true copies were labelled partial links. The coverage rule was a bad design on my part; Spark's judgments were not the cause. The frozen result stands as a FAIL on rule 4.

Post-hoc rule, development evidence only: **merge on yes, then test consistency.** If clip H is yes-linked to x and y, then x and y must be yes-linked too. If Spark says no for (x, y), H is a compilation and its links become partial. If (x, y) was never asked, ask it (a verify call, at most one per neighbour pair of a clip with two or more neighbours). First run has 12 such unasked pairs (about $0.25). Same cost accounting; no prompt change. This rule was chosen after seeing the failure, so a pass under it is not a test.
