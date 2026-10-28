# H15 result: escalate conflicts to the full-fidelity judge (Oct 27 2026)

Protocol: `eval/spark-h15.md`. Code: `scripts/spark_h15.py`. Conflicts taken from the H14 answers; each re-asked at native 360 px, default effort, one pair per request, both orders (24 calls). Spend $0.55.

| Rule | Bar | Result |
|---|---|---|
| 1 Recordings found | 18 | **18: pass** |
| 2 False merges | 0 | **0: pass**, compilation merged with nothing |
| 3 Extra cost | at most $0.50 | **$0.55: fails by $0.05** |

- 12 conflicts were raised. One was a missed copy: `B2_e1` against `B2_e2`, answered **yes in both orders** at full fidelity, so `B2` is no longer mistaken for a compilation and its family reassembles (recording sizes 4, 4, 3, 3, 2 and thirteen singletons).
- The other 11 were the real compilation (`A1N1A3_e4`): different recordings among the clips it contains, all answered **no in both orders**, so the compilation flag stands.
- The whole harness on the pile is now: SSCD candidates, cheap batched judge ($0.28), conflict escalation ($0.55): **$0.83 in total against $1.53 for the first pile test**, with 18 of 18 recordings and 0 false merges. The cost bar for the escalation was mine and was missed by 10%: asking each conflict in one order only (or a single conflict per flagged clip) would halve it, but I did not tune that after the fact.

## What it does and does not show

The pipeline now reproduces the pile result with a cheaper judge, and the one weak point of the cheap judge (a missed hardest pair) is repaired by escalation rather than by trusting the cheap answer. The consistency rule and the escalation were both written after seeing the pile fail, on this same pile: this is development evidence, not a test. The next real test is data it has not seen: the phone re-films, or a new pile.

## Limits

30 clips, one run, ffmpeg edits, one compilation, one hard miss; the escalation is only exercised when a conflict exists.
