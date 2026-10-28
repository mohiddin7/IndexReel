# H12: one anchor clip against several candidates in a single request

Written Oct 27 2026 before the run. Follows H9 (caching saved 12%; the anchor clip is still paid for once per pair). If a single request carries the anchor once and several candidates, the anchor's tokens and the shared reasoning are paid once per group instead of once per pair.

## Hypothesis

Asking about one anchor and up to 5 or 10 candidates in one request keeps the pair judge's accuracy and cuts the billed cost per pair to at most 60% of the grouped per-pair arm of H9 (O: $0.0049 per pair).

## Design

The 129 pairs of H1 at 180 px, minimal effort, same cache key and 24-hour retention as H9's O arm. Pairs are grouped by anchor exactly as in H9 (the clip that appears in more pairs; ties by name). Each anchor's candidates are put in a seeded shuffled order (seed 2614) and split into requests of at most K candidates. Two arms: **M5** (K = 5) and **M10** (K = 10). Each request: the anchor video, then candidates "B1" to "BN", one answer per candidate as JSON. Prompt (frozen in `scripts/spark_h12.py`): judge the picture and sound not on-screen text; for each candidate decide independently whether it has footage from the anchor's original camera recording, with the same rules as prompt v3 for edits, partial reuse and other cameras; do not compare candidates with each other; return `{"results": [{"candidate": "B1", "same_footage": yes|no|unsure, "shared_detail": ... or null}, ...]}`.

## Pass bar for each arm (decided now)

1. Yes on at least 27 of 28 expected-yes pairs and **0** false yes on the 101 expected-no pairs.
2. Billed cost per pair (request cost divided by the pairs it covers, cached tokens at the cached rate) at most 60% of H9's O arm.
3. Every request returns a parseable answer with one entry per candidate, for all but at most one request.

## Reported

Accuracy by position in the request (first versus last candidates) and by group size; answer changes against H9 O; seconds per request and per pair; any answer attached to the wrong candidate.

## Limits

Small groups (22 anchors, most with 3 to 8 candidates); same footage; one run per arm; position effects need more data than this to measure.

## Addendum A (Oct 27, before any successful H12 call)

The first launch failed on every request that held six videos: `HTTP 400, request contains 6 videos, exceeding the maximum of 5 allowed per request`. I did not find this limit in the doc pages I read (`file-handling`, `video-understanding`, `pricing-rate-limits`, `prompt-caching`, `error-handling`, `models`, `protocols/responses`); I treat it as a measured limit. One anchor plus candidates must therefore be at most 5 videos, i.e. K at most 4. No request succeeded, so no answer was seen. The arms become **M2** (K = 2) and **M4** (K = 4). Everything else, including the pass bar and the seed, is unchanged. Not run: K = 5 and K = 10.
