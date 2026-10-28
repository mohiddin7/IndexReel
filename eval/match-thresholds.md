# Match thresholds (set on dev only)

I wrote the rule below before running `indexreel match` on the dev clips. It sets the two band thresholds of the run format (`eval/run-format.md`). It does not touch the gate split or the held-out set.

## Pipeline being thresholded

`indexreel match <clips dir> --out <run dir>`: every clip is decoded, the OpenCV localiser (edge-support cut-off theta = 0.9, set on dev in `eval/gate.md`, Amendment 1; no fixed inset rectangle) is run on frames at 5 fps, one localised frame per second is kept, SSCD embeds it (and its mirror), and every pair of clips gets the best-match score and the aligned score (`eval/sscd-exploratory.md`, Addendum A). A clip with no accepted quadrilateral on a frame is used whole, at its own aspect ratio.

## Data

Dev only: the 24 clips in the dev part of the gate fixtures (blocks 1 to 4; each of the 8 families as original, picture-in-picture and simulated re-film). A positive pair is two versions of one family (24 pairs); every other pair is a negative (252 pairs). The 8 families are 4 target clips and 4 look-alikes recorded separately, and the 3 versions of different families share a template, so the negatives include same-template look-alikes.

## Rule

- `merge_at`: the highest `aligned` score among the dev negatives plus 0.01, rounded up to two decimals, and not below 0.50. A pair at or above it is `merged`.
- `floor`: 0.30, fixed, not tuned. It only decides how many pairs the next stage has to look at.

## What I report

For the positives by version pair (original with PiP, original with re-film, PiP with re-film): how many land in `merged`, `unresolved` and `apart`. For the negatives: how many land in `unresolved` and `merged`. k/n with Wilson 95% intervals. By construction no dev negative is `merged`; that is not a result. The held-out evidence is the one-time run on the final split.

## Limits

Simulated copies; 8 families; the values are specific to this localiser and this sampling (one frame per second). Dark scenes gave the highest negatives in earlier runs, so `merge_at` is set by one or two scene families.

## Values

Dev run, `indexreel match` on the 24 dev clips (74 s on CPU for 240 s of video; the localiser found the inset on all 8 PiP clips with no fixed rectangle):

- Highest `aligned` score among the 252 dev negatives: 0.537 (the two simulated re-films of the night-city pair, target and look-alike). `merge_at` = 0.55. `floor` = 0.30.
- Positives (24): 20 `merged` (Wilson 95% 0.64 to 0.93), 2 `unresolved`, 2 `apart`.

| version pair | n | merged | unresolved | apart |
|---|---|---|---|---|
| original with PiP | 8 | 8 | 0 | 0 |
| original with re-film | 8 | 6 | 1 | 1 |
| PiP with re-film | 8 | 6 | 1 | 1 |

- Negatives (252): 0 `merged` (by construction), 1 `unresolved` (the night-city re-film pair above), 251 `apart`.
- The four positives that did not merge are all the night-city family (T04 and N04): the localiser accepted no quadrilateral on 100% and 90% of their re-film frames, and the whole dark frame scored 0.24 to 0.41. The two `apart` ones would never reach a verifier; that is a miss to report, not hide.
- Raw output: the run directory of this command on the dev fixtures (scores, spans, bands per pair).
