# H14: the whole cheap harness on the 30-clip pile, end to end

Written Oct 27 2026 before the run. The pile test (`eval/spark-pile-result.md`) judged the SSCD candidate pairs one at a time with the default settings and needed a post-hoc consistency check. Since then the judge got cheaper (H8, H10, H11, H9, H12). This asks whether the cheap configuration reproduces the pile result: 18 recordings, no false merges, at a fraction of the cost.

## Harness under test

1. Candidate pairs: the 84 SSCD pairs of the pile test (`data/spark_pile/candidates.json`, frozen rule: each clip's 4 best partners plus aligned score at least 0.60). Not recomputed.
2. Judge: `muse-spark-1.3`, minimal effort, clips at 180 px shorter side (`data/spark_h11/res180`), one anchor plus up to 4 candidates per request (prompt of `scripts/spark_h12.py`), cache key and 24-hour retention. Anchor = the clip with more candidate pairs (ties by name); candidate order seeded (2615).
3. Consistency check (the pile test's Addendum A): merge on yes; if a clip is yes-linked to two clips that the judge says are not the same footage, it is a compilation and its links stay partial; neighbour pairs never asked are asked in a second round, grouped the same way.
4. Recordings = connected components of merges, minus compilation clips.

## Pass bar (decided now)

1. **18** recordings found (truth, as in the pile test).
2. **0** false merges, and the compilation merges with nothing.
3. Total billed cost (round 1 and the verify round) at most $0.60, against $1.53 for the pile test's new calls.

## Reported

Number of requests and seconds; answers that differ from the pile test's; the verify pairs asked; split recordings.

## Limits

The consistency rule was chosen after seeing the pile test fail (Addendum A there), so this is a re-run of a tuned procedure with a cheaper judge, not a fresh test; same 30 clips; one run.
