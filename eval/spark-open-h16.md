# H16: Muse Spark Open (open weights, on Modal) as the pair judge

Written Oct 27 2026 before the 129-pair run. Probe (two pairs, not scored): the Modal Shared Endpoint `indexreel-spark-open` (model `meta-models/Muse-Spark-Open-816B-A42B`, OpenAI-compatible chat completions, video sent as base64 `video_url`) accepted video, answered the copy pair "yes" and the different-camera pair "no" in about 3.5 s each, 3,406 and 4,294 prompt tokens at 180 px (the API's Spark 1.3 counted 3,781 for the first pair).

## Hypothesis

The open-weight model, served by Modal, judges "same recording" as well as the API model did in H11, so the harness does not depend on one hosted model and can run on open weights.

## Design

The 129 pairs of H1 (28 expected yes, 101 expected no), clips at 180 px shorter side (`data/spark_h11/res180`), orientation as stored, prompt v3 unchanged, one pair per request, `reasoning_effort` = `low` (Spark Open has no "minimal"; the levels are low, medium, high, xhigh; low renders strength 8; chosen as the nearest to the API's minimal, not tuned), `max_tokens` 4000, temperature and top_p at their defaults. 4 requests at a time; HTTP 429 retried with backoff. Billing is per token on the Modal workspace `indexreel`; `modal billing summary` gives the metered cost.

## Pass bar (decided now, the same as H11)

1. Yes on at least 27 of 28 expected-yes pairs.
2. **0** false yes on the 101 expected-no pairs.
3. At most 3% of requests unparseable or failed.

## Reported

Tokens, cost at the endpoint's listed prices ($1.25 in, $0.15 cached, $4.25 out per million), seconds per request; every answer that differs from the API model's answers in H11 at 180 px; the unsure count; the metered cost reported by `modal billing summary`.

## Limits

Same pairs and footage as H11, which chose the 180 px setting for the API model; one run; a different model checkpoint with different reasoning levels; no result here says anything about re-films.
