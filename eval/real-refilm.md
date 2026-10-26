# Exploratory: five real phone re-films (Oct 26)

Not part of the gate and not a tuned result. I filmed five clips off my monitor with my phone. Each fills the whole phone frame with the screen content, so there is no bezel or room to find; this tests matching, not localisation.

Each re-film was compared with the five original clips (the true one and four unrelated scenes), one frame per second, whole clips, no localiser.

| Re-film of | PDQ closest frame (bits different of 256; match is 31 or fewer) | SSCD cosine, true original | SSCD cosine, best wrong original |
|---|---|---|---|
| Interchange traffic | 94 | 0.703 | 0.061 |
| Street traffic lights | 112 | 0.716 | 0.076 |
| Night fireworks | 104 | 0.370 | 0.068 |
| Aerial city | 102 | 0.692 | 0.144 |
| Building demolition | 106 | 0.458 | 0.119 |

- PDQ (256 bits, random pairs are near 128) finds no match on any real re-film.
- SSCD (Meta's copy-detection model) ranks the true original first on all five, with a clear gap.

Limits: n = 5; the wrong answers are four unrelated scenes, so this has no look-alike negatives and sets no threshold; screens fill the frame. The next test films the monitor with its bezel and surroundings visible and includes look-alike negatives, scored with a threshold set before the held-out data is touched.
