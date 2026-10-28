# H16 result: Muse Spark Open on Modal as the pair judge (Oct 27 2026)

Protocol: `eval/spark-open-h16.md`. Code: `scripts/spark_open_h16.py`. The 129 pairs of H1 at 180 px, `reasoning_effort` low, one pair per request, on the Modal Shared Endpoint `indexreel-spark-open` (model `meta-models/Muse-Spark-Open-816B-A42B`). Billed per token to workspace `indexreel`.

| | API Spark 1.3 (H11, minimal, 180 px) | Spark Open (low, 180 px) |
|---|---|---|
| Yes on expected-yes | 27/28 | **28/28** |
| False yes on expected-no | 0/101 | **0/101** |
| Failed or unparsed requests | | 0 of 129 |
| Tokens per pair (in / out) | 3,639 / not recorded | 3,303 / 559 |
| Cost per pair at list prices | $0.0063 | **$0.0065** |
| Seconds per request | 5.9 | 3.7 |

**Bar (same as H11): 27 of 28, 0 false yes, at most 3% failed: PASS.** Only one answer differs from the API model's: `B2_e1` against `B2_e2`, the hardest pair of the programme (mirrored and sped up against a small vertical reframe), which the API model missed at 180 px and Spark Open got right (yes).

**Metered cost:** `modal billing summary` shows $0.85 of LLM tokens for the run, matching the token count at list prices.

## What this says

- The harness is not tied to one hosted model: the open-weight release, served by a third party, reproduces the cheap judge's accuracy at the same price and a faster response. The judge can run on open weights, so clips need not leave the user's own infrastructure.
- The per-token price is the same as the Meta API's, so either service can carry the judge at the same cost per pair.

## Limits

Same pairs and footage as the settings were chosen on; one run; Spark Open used `low` reasoning, a nearest-match choice; no re-films; the endpoint is a shared service with unknown concurrency limits (4 requests at a time worked, none rejected). The 1-pair difference is not evidence that one model is better.
