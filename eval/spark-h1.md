# H1: aligned frame pairs instead of whole videos

Written Oct 27 2026 before any frame sheet was built or sent. Exploratory, one run.

## Hypothesis

If the free matcher picks the best-matching frame pairs of two clips and Spark judges only those, Spark's "same recording" call stays as good as with the two whole videos, and each call costs much less. A matcher that narrows what Spark looks at is the harness doing part of the model's job.

## Arms (same pairs, same prompt wording about overlays, one answer per pair)

- **V, raw video pair:** answers that already exist (pile run, verify calls, pilot 3). Not re-asked. Prompt v3.
- **F, aligned frames:** one image per pair, 6 rows. Each row shows a frame of video A (left) and a frame of video B (right), labelled with their times. The 6 rows are the highest-scoring cells of the SSCD frame-similarity matrix (one frame per second, plain and mirrored), picked greedily with at least 2 s between picks in each video. Top and bottom 13% of every frame are masked as in pilot 3.
- **U, uniform frames (ablation):** the same sheet layout, but the 6 rows are the frames at 1/12, 3/12, 5/12, 7/12, 9/12, 11/12 of each video, with no matcher. It shows whether the matcher's choice of frames is what helps.

## Pairs

Every pair that has a video-arm answer in `data/spark_pile/results.jsonl`, `data/spark_pile/verify.jsonl` or `data/spark_pilot3/results.jsonl` and whose clips are in the pile. For a pair with answers in both orders, the orientation is the pile/verify one, else alphabetical. Expected label by construction: **yes** for two clips of one recording, and for the compilation against any clip of A1, N1 or A3 (partial reuse); **no** for everything else.

## Prompt (frozen in `scripts/spark_h1.py`)

Tells Spark what the sheet is, that rows may be mirrored, resized, cropped, overlaid or sped up, that two cameras on one event are `same_footage` no, and that partial reuse is yes. Returns `same_footage` (yes, no, unsure), `rows_matching` (row numbers whose two frames come from one recording), up to 3 observations and an unsure reason. Model `muse-spark-1.3`, Standard mode, no tools. No prompt edits after the first full run; the first pair is sent alone to check that images work and to measure tokens.

## Pass bar (decided now)

H1 PASSES if arm F:
1. calls yes on at least 90% of the expected-yes pairs, and within 1 pair of arm V's yes count;
2. makes **0** false yes on expected-no pairs;
3. costs at most 50% of arm V per pair (tokens and dollars, from the API usage).

Reported, not scored: unsure rate per arm; which edit types (vertical reframe, picture-in-picture, mirrored, audio swapped, compilation) F misses; F against U (does the matcher's choice matter); every disagreement between V and F.

## Limits

Easy edits of five clips plus a few real cameras; ffmpeg edits, no real re-films; F drops audio, so it cannot catch a copy that differs only in sound; the matcher picks the best-looking frames even for different cameras, which is the intended hard case, not an unbiased one. 30 clips, one run.
