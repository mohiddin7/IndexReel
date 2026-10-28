# H9: prompt caching on the pair judge

Written Oct 27 2026 before the ordered or shuffled run. The Model API docs (`prompt-caching`, `pricing-rate-limits`) say caching is automatic prefix caching, cached input costs $0.15 per million tokens against $1.25, and `usage.input_tokens_details.cached_tokens` reports hits. Our earlier cost numbers ignored it, so they are upper bounds. A probe (about 15 calls) showed an identical request is 97% cached, and pairs that share only their first clip hit the cache (about 1,250 shared tokens) only when `prompt_cache_key` is set, from the third request on.

## Hypothesis

If pairs that share the first clip are asked back to back with a stable `prompt_cache_key` and 24-hour retention, billed input cost per pair falls by at least 20% against the same pairs in shuffled order without a key, with the same accuracy.

## Design

The 129 pairs of H1, clips at 180 px shorter side, minimal effort, prompt v3 (as H11). Arm S (shuffled): the stored H11 orientation, random order, 4 threads, no key. Arm O (ordered): each pair oriented so its first clip is the one that appears in more pairs (ties by name); pairs grouped by first clip; groups run in parallel (4 threads), pairs within a group sequentially; `prompt_cache_key` = "indexreel-judge-v3", `prompt_cache_retention` = "24h". Both arms record `cached_tokens`. Billed cost = (input − cached) x $1.25 + cached x $0.15 + output x $4.25, per million.

## Pass bar (decided now)

1. O billed cost per pair at most 80% of S's.
2. O: yes on at least 27 of 28 expected-yes pairs and 0 false yes on the 101 expected-no pairs.

## Reported

Share of input tokens that were cached in each arm; seconds per call; answer changes between O, S and the H11 180 px run; cache hits by position within a group (1st, 2nd, 3rd and later).

## Limits

The cache is server-side and shared; other traffic and eviction change hit rates; hits depend on timing; one run per arm; the pile is 30 clips, so groups are small.
