# Exploratory: SSCD on real round-trip copies and same-event recordings (Oct 26)

I wrote this before scoring anything. It is exploratory: no pre-registered split, no threshold, no verdict. It checks that the SSCD scorer works on real footage before the phone re-films arrive, and it tells me how far apart real positives and look-alike negatives sit. It decides nothing about the product. The threshold and the matcher choice come later, from dev re-films only.

## Scorer

SSCD (`sscd_disc_mixup`, torchscript), one frame per second (the frame at the middle of each second), shorter side resized to 224 px, embeddings L2-normalised. Clip score between clips A and B: for each frame of one clip, the best cosine against the frames of the other, averaged; taken in both directions and with one side mirrored; the maximum of the four. This is the spike's definition, unchanged. Code: `src/indexreel/sscd.py`, `scripts/score_clips.py`.

## Sets and ground truth

1. **Social copies.** 17 clips I sent through WhatsApp, each mapped to its original by duration and by looking at frames at 25% and 60% (SSCD took no part), recorded in `data/iphone_by_me/social_copies/MAP.csv`. The 17 pairs are the positives. Everything else in the pool is a negative: the 17 originals, plus 7 other airshow clips and 7 recordings of one fireworks show that are not in the map. Two originals are screen recordings and one is itself a recompressed file; the map says which. The same-event clips (airshow, fireworks, the neighbouring biplane clips IMG_4018 and IMG_4019) are the hard negatives.
2. **Volcano.** `data/event_volcano/ev1..ev4`, four USGS recordings of one eruption with the same corner logo. All six pairs are negatives.

## What I report

Per set: for each copy, whether its true original ranks first; the lowest positive score; the highest negative score; the gap between them; the five highest-scoring negative pairs. No threshold is chosen or applied. Wilson intervals on the top-1 rate.

## Limits

n = 17 positives; copies are recompressed and rescaled, not re-filmed; the map was made by me looking at frames; the pool has no screens, bezels or glare. A clean result here means the scorer works, not that re-films will match.

## Addendum A: aligned score (written after the first pass, before it was run)

The first pass (mean-of-best-match score, above) put all 17 true copies first but left a gap of only +0.003 between the lowest positive and the highest negative. The highest negatives are different recordings of the same scene (three fireworks recordings of one show with the same lit landmark; two airshow takes in the same place). I looked at their frames: they are not duplicates.

The mean-of-best-match score lets every frame match any frame, so two recordings of one scene score high. A recording and its copy also agree in time: frame i of one is frame i + d of the other. So I add a second score, **aligned**: put both clips' one-per-second embeddings in a similarity matrix; for every constant offset d take the mean cosine along that diagonal, over the frames the two clips overlap; the score is the highest such mean, over both mirror states of one clip. The overlap must be at least half of the shorter clip (and at least 3 frames, or the whole shorter clip if that is under 3). Only a constant offset is allowed: copies with changed speed are not handled, and a clip slid along a long clip gets many offsets to try, which favours the negatives.

Because I wrote this rule after seeing the first pass on these same clips, an improvement here is development evidence, not a test. It is judged on dev re-films next and on the held-out set once, with a threshold set on dev only. Same reporting as above, for both scores side by side.

## Result (Oct 26, evening)

Social copies, 17 positives and 1,111 negatives: all 17 true copies beat every negative that shares a clip with them (Wilson 95% 0.82 to 1.00) under both scores. Mean-of-best-match: lowest positive 0.655, highest negative 0.652 (gap +0.003). Aligned: lowest positive 0.653, highest negative 0.567 (gap +0.086). The highest negatives are different recordings of one scene (fireworks, airshow), checked by eye. Volcano, four recordings of one eruption: highest pair 0.554 (aligned 0.447), two night recordings with the same logo; a real phone re-film of night fireworks scored 0.370 earlier. So no single clip-level threshold looks safe, and the aligned score is development evidence only (Addendum A). Raw scores and embeddings are kept locally.
