# H12 result: one anchor against several candidates per request (Oct 27 2026)

Protocol: `eval/spark-h12.md` (with Addendum A: a request may hold at most 5 videos, so K is 2 or 4). Code: `scripts/spark_h12.py`. The 129 pairs of H1 at 180 px, minimal effort, cache key and 24-hour retention. Spend about $0.9.

| Arm | Requests | Yes | False yes | Billed per pair | vs H9 O ($0.0049) | Seconds per pair | Malformed |
|---|---|---|---|---|---|---|---|
| M2 (anchor + up to 2) | 70 | 28/28 | 0/101 | $0.0033 | 68% | 2.05 | 0 |
| M4 (anchor + up to 4) | 42 | 28/28 | 0/101 | $0.0030 | **61%** | 1.32 | 0 |

**Bar: at most 60% of H9's O arm. M4 misses by one point (61%), M2 by eight (68%). Strictly: fails.** Accuracy was untouched: every answer is identical to H9's O arm (0 changes), accuracy 100% in first and last position, no malformed output, no answer attached to the wrong candidate.

- The saving is smaller than the arithmetic suggests because the anchors in this pile have few partners (42 requests for 129 pairs, about 3 candidates per request) and caching already covered part of the repeated anchor.
- Batching candidates costs no accuracy and cuts time per pair about three-fold (1.3 s against about 4.4 s for one pair per request).
- The limit of 5 videos per request caps the gain: the anchor is shared at most four ways.
- Whether positions beyond the first, with harder content, degrade is untested at this size; there was no sign of it here.

## Cost of the recommended configuration so far

Minimal effort, 180 px, up to 4 candidates per request with a cache key: about $0.0030 per pair, 15% of the $0.0198 of the first pilots. On the 30-clip pile with the SSCD prefilter that is about $0.25 for the 84 candidate pairs.

## Limits

Same footage, 22 anchors, one run per arm; the pair set was used to choose the earlier settings (180 px, minimal) too.
