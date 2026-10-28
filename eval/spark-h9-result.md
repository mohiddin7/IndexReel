# H9 result: prompt caching on the pair judge (Oct 27 2026)

Protocol: `eval/spark-h9.md`. Code: `scripts/spark_h9.py`. The 129 pairs of H1 at 180 px, minimal effort. Arm S shuffled, no key; arm O grouped by first clip with `prompt_cache_key` and 24-hour retention. Billed cost uses the cached-input rate ($0.15 per million) from the Meta docs. Spend about $1.4.

| | Yes | False yes | Input tokens cached | Billed per pair | Full price per pair | Seconds per call |
|---|---|---|---|---|---|---|
| S shuffled, no key | 27/28 | 0/101 | 19% | $0.0056 | $0.0063 | 5.9 |
| O grouped, key, 24h | 28/28 | 0/101 | 36% | $0.0049 | $0.0064 | 4.4 |

**Bar: O billed at most 80% of S. Result 88%: fails.** Accuracy held (28/28, 0/101).

- **Position in a group:** the first call in a group was 8% cached, the second 10%, the third and later 50%. The cache needs about two requests to warm, and my groups are small (22 groups for 129 pairs), so most calls were early ones.
- **Caching already helps without any effort:** the shuffled arm got 19% of its input from cache (the shared prompt text and chance hits), so the baseline cost numbers in earlier results were slightly high ($0.0063 full price against $0.0056 billed).
- **A modest, free gain:** ordering plus a key saves about 12% of billed cost and 25% of latency (4.4 s against 5.9 s per call) with no accuracy cost. It does not change the plan. Bigger groups (a clip compared with many others) would raise the share cached; that is untested.
- **Orientation matters on the hardest pair:** `B2_e1` against `B2_e2`, missed at 180 px in the stored orientation, was found when the other clip came first. One pair, so only a note: at small sizes the order can flip a hard answer, which supports asking such pairs in both orders.

## Cost of the recommended configuration so far

Minimal effort, 180 px, grouped with a cache key: about $0.005 per pair against $0.0198 for the first pilots' default (about 25%). With the SSCD prefilter (84 of 435 pairs on the 30-clip pile) a pile of 30 costs about $0.45. Contributor mode (a decision, not tested) would cut it a further 12-fold.

## Limits

One run per arm; small groups; other traffic and eviction affect hits; the key and retention are hints.
