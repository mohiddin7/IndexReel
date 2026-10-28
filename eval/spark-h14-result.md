# H14 result: the whole cheap harness on the pile (Oct 27 2026)

Protocol: `eval/spark-h14.md`. Code: `scripts/spark_h14.py`. 84 SSCD candidate pairs plus the verify round, judged at minimal effort, 180 px, up to 4 candidates per request. 35 requests, 154 s, billed cost **$0.28** (pile test: $1.53).

| Rule | Bar | Result |
|---|---|---|
| 1 Recordings found | 18 | **19: FAIL** |
| 2 False merges | 0 | **0** (the compilation merged with nothing) |
| 3 Cost | at most $0.60 | **$0.28** |

Why 19: the judge missed one true copy pair, `B2_e1` against `B2_e2` (the hardest pair of the programme: mirrored and sped up against a small vertical reframe; it was also the one miss at 180 px in H11). `B2` is yes-linked to both, so the consistency rule ("a clip yes-linked to two clips that are not the same footage is a compilation") flagged `B2` as a compilation and dropped its links. The family split. A single missed "no" is indistinguishable from a real compilation by this rule. Two answers differed from the pile test's (that pair, and `B2` against `N2`, "unsure" to "no" which is correct).

The cost and speed gain is real and the safety held; the rule cannot tell a miss from a compilation. Follow-up: H15, re-ask conflicting pairs at full fidelity before deciding (`eval/spark-h15.md`).

## Limits

The consistency rule was chosen after the first pile run failed, so this is a re-run of a tuned procedure with a cheaper judge. Same 30 clips, one run.
