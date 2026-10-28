# H1 result: aligned frame pairs instead of whole videos (Oct 27 2026)

Protocol: `eval/spark-h1.md`. Code: `scripts/spark_h1.py`. 129 pairs (28 expected yes, 101 expected no), arm V = answers that already existed, F = 6 SSCD-aligned frame pairs, U = 6 uniform frames (ablation). One run; one transport failure was resumed, no answer was re-asked.

## Frozen bar: H1 FAILS on rule 2

| | V (whole videos) | F (aligned frames) | U (uniform frames) |
|---|---|---|---|
| Yes on expected-yes | 28/28 | 27/28 | 27/28 |
| False yes on expected-no | 0/101 | **3/101** | 4/101 |
| Tokens per pair | 10,745 | 939 | 1,008 |
| Cost per pair | $0.0198 | $0.0080 | $0.0076 |

1. F yes 96% (bar 90%, within 1 of V): pass. 2. F false yes 3 (bar 0): **fail**. 3. Cost 40% of V (bar 50%): pass.

## What the failure is

All three false yes involve one clip, `A1_e2`, the vertical reframe where the real picture is a tiny inset (about 100 by 40 pixels in the sheet) over a blurred background and a red bar. Spark invented matches: for `M` (a snowy Chelyabinsk dashcam) vs `A1_e2` it wrote "same snowy dashcam road at sunrise with pink sky" about an Arizona night clip. When the frames are too small to read, it fabricates evidence instead of saying unsure. U fails the same way on `A1_e2` (3 of its 4 false yes), plus one pair of Phoenix meteor clips from different years (`N4`, `N2`). The one miss, `B2_e1` vs `B2_e2`, was an "unsure" because the pair's frames were too small and blurred.

## What this says about the harness

- **The frame picker alone is not safe.** It needs a layout step first: crop to the real picture (the localiser stage: OpenCV or SAM) before building the sheet. Without it, a small, blurred input produces confident wrong evidence.
- **The SSCD frame choice did not help.** F and U score about the same (27/28 each; 3 and 4 false yes). On this pile the saving is cost (40% per call), not accuracy.
- **Whole-video input is still the safest judge** (28/28, 0 false yes), as it can see motion and the picture at full size.
- **Post-hoc, not a test:** use F as a cheap first pass and send only pairs where F says yes or unsure (31 of 129) to the video judge. That gave 28/28 and 0 false yes at 68% of the all-video cost ($1.74 against $2.56). It is chosen after seeing the failure and uses answers already collected.
- **Rule to add to the harness:** a "yes" backed only by small or blurred frames is not evidence. Require the picture to be big enough, or confirm with the video judge.

## Limits

One pile of 30 clips, five easy families; all failures come from one edited clip, so the false-yes count is small and clip-specific; ffmpeg edits, no real re-films; F drops audio. Next: H1b, crop to the real picture first (the localiser), then rebuild the sheets, to see whether F then reaches 0 false yes.
