# H5 result: the judge on real phone re-films (Oct 28 2026)

Protocol: `eval/refilm-h5.md` (written before any model touched a re-film clip). Code: `scripts/refilm_h5.py`. 96 iPhone re-film clips (6 takes of 3 playlists) against 16 originals = 1,536 pairs per arm, Muse Spark Open on the Modal Shared Endpoint, prompt v3, `reasoning_effort` low, re-film as video B. No tuning, no re-asks.

| | 360 px | 180 px |
|---|---|---|
| Own original yes (bar 72/96) | **92/96** (Wilson 90 to 98%) | **91/96** (88 to 98%) |
| False yes on 1,440 expected no (bar 0) | **0** (upper bound 0.27%) | **0** |
| of which against the look-alike | 0/96 | 0/96 |
| Unsure / failed requests | 3 / 0 | 4 / 0 |
| Tokens per pair (in / out) | 5,383 / 277 | 1,856 / 319 |
| Cost (1,536 pairs) | $12.14 | **$5.64** |
| Seconds per request | 3.6 | 2.7 |

**Both arms PASS.** Both arms together cost $17.78 at list prices, which matches the metered cost Modal reported.

## Breakdown (yes on own original)

| | 360 px | 180 px |
|---|---|---|
| bezel / tight | 48/48, 44/48 | 45/48, 46/48 |
| handheld / straight on / off axis | 30/32, 31/32, 31/32 | 29/32, 32/32, 30/32 |
| playlist A / B / C | 30/32, 31/32, 31/32 | 29/32, 30/32, 32/32 |

88 clips are yes in both arms, 95 in at least one; only `C_b08_T` is missed by both.

## The misses

7 of the 9 misses (both arms) are `unsure`, all on two originals: `b04_T` (static night city and bridge) and `b08_T` (featureless grey sky). The reasons Spark gave are the prompt working as written: "generic sky background with no identifiable place, timing, or landmark", "identical viewpoint ... but static nighttime". It abstains when the picture has nothing distinctive, and it never turns that doubt into a yes. The other 2 are a plain `no` (`B_b04_N` at 360, `C_bezel_b03_T` at 180).

## Free matchers on the same pairs

- **SSCD** ranks the true original first for **96/96** clips. Own-original scores range from 0.480 to 0.727 (median); the highest score against any other original is 0.289. On this set a single threshold separates them, and the top-4 candidate rule of the pile harness would hand every true pair to the judge.
- **PDQ** ranks the true original first for only 67/96, with a median margin of 0.000. It is blind on re-films, as on the five earlier ones.
- **Audio:** not measured. The gate originals have no audio track, so there was nothing to fingerprint against (0/96 usable). This is a gap in the data, not a fingerprint result.

## What this says

- The step the harness was weakest on in theory (a phone filming a screen: perspective, moiré, glare, hand shake, a bezel in frame) does not break the cheap judge. At 180 px it costs $0.0037 per pair, recovers 95% of the true pairs and makes no false merges in 1,440.
- SSCD then Spark holds on real re-films: SSCD finds every true original, Spark confirms nearly all of them and refuses every look-alike, and the misses are honest abstentions that a human reviewer sees in the queue.
- Where both models struggle is low-detail footage (a dark static city, an empty sky). That is the case for the escalation path (360 px, default effort, both orders), and the interface should show it as "unsure, here is why", not hide it.

## Limits

16 recordings and 3 playbacks filmed twice, so the 96 clips are far from independent (the misses cluster on 2 originals). One phone, one monitor, one room, filmed by me. The 0/1,440 false yes covers these 16 originals only; a look-alike from the same event, shot by another camera at the same moment, was not in this set. No audio. Spark Open, not the Meta API model, though H16 showed the two agree. Exploratory: physical re-films never decide the gate, and `data/final/` was not touched.
