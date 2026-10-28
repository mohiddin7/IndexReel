# H1b: crop to the real picture before building the frame sheets

Written Oct 27 2026 before any cropped sheet was built or sent. Follows H1 (`eval/spark-h1-result.md`), whose three false "yes" all came from one clip, a vertical reframe where the real picture is a small inset over a blurred background.

## Hypothesis

If each clip is first cropped to its real picture (dropping blurred fill, flat studio backgrounds, banner bars and the black masks), the same frame sheets give Spark enough resolution to judge, and the false "yes" disappear, with the yes rate and the cost saving of H1 kept.

## Crop rule (frozen in `scripts/spark_h1b.py`)

Per clip, from 8 frames spread evenly over its length: texture = mean absolute Laplacian of the grey frame, lightly blurred (7 by 7). A pixel is "textured" above 0.3 times the 95th percentile of the texture map. Keep the rows and columns in which at least 10% of the pixels are textured; take the largest run of consecutive kept rows (gaps of up to 3 allowed) and the same for columns; that is the box, with a 4 px margin. If the box covers less than 20% of the frame, use the whole frame. No other tuning.

Sheets are built exactly as in H1 (same 6 SSCD-picked rows, same prompt, same call) except that every frame is cropped to its clip's box before the row is drawn.

## Arms and pairs

The same 129 pairs as H1. New arm **F2** (cropped aligned frames), all 129 asked once. Compared with V (whole videos), F and U from H1 (not re-asked).

## Pass bar (same as H1, decided now)

1. F2 yes on at least 90% of the 28 expected-yes pairs, and within 1 of V.
2. F2 false yes on the 101 expected-no pairs: **0**.
3. F2 cost at most 50% of V per pair.

## Reported, not scored

The box found for every clip, and which clips changed by more than 5% of the frame area; a contact sheet of the crops for the layout-edited clips; the pairs whose F2 answer differs from F; how many pairs would have a tile smaller than 120 px high in the original pixels (a "too small to judge" guard, not applied here).

## Limits

The rule is a texture heuristic written for these edits (blurred fill, flat background, banners); it may not fit other layouts. Same pile, same ffmpeg edits, one run.

## Addendum A (Oct 27, before any paid call): the crop rule failed its free check, H1b was not run

I built the cropped sheets (free) and looked at the boxes before sending anything. The crop rule is wrong for this data: it cropped 13 of 30 clips by more than 5% of the area, including 7 originals (night scenes cut to a lit band, for example `A3` to 24% of the frame), and it did **not** crop any of the four vertical reframes (`*_e2`), the only case H1 failed on. I then tried the repo's own OpenCV localiser (`indexreel.quad`, the gate's rule) on the same clips: it finds only partial boxes on the layout edits (for `A1_e2` a box 359 by 69 px where the inset is 360 by 202, an overlap of about 0.34; `A1_e3` about 0.64) and picks spurious quads on original clips. The black masks I draw on top and bottom of every source hide the inset's top and bottom edges, which is why edge-based finding fails here. No Spark call was made for H1b, no result exists, and I am not tuning the crop rule further against these same clips: a crop rule tuned on the six clips it must find would prove nothing. The follow-up is H1c (`eval/spark-h1c.md`): a router that avoids needing the crop at all, tested on new edits.
