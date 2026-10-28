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

## Amendment 1 (Oct 28): floor lowered to 0.20, before any held-out run

The rule above fixed `floor` at 0.30 without tuning. The dev run showed that two true pairs, both re-films of one dark family, scored 0.24 and 0.26 and fell `apart`, so a verifier would never have seen them. I lowered `floor` to 0.20, the largest multiple of 0.05 that is at most the lowest `aligned` score of a dev positive (0.241). `merge_at` stays 0.55. The choice used the dev positives, so the dev counts below are not independent evidence; the held-out run, done once after this commit, is.

Same dev clips, same scores (cached), new bands:

| | 0.30 | 0.20 |
|---|---|---|
| positives merged / unresolved / apart (24) | 20 / 2 / 2 | 20 / 4 / 0 |
| negatives merged / unresolved / apart (252) | 0 / 1 / 251 | 0 / 7 / 245 |
| pairs a verifier has to look at (of 276) | 3 | 11 |

Eight more pairs reach the verifier: the two positives above and six negatives, all involving the dark night-city family or a simulated re-film of a different family (aligned 0.21 to 0.26). That is 4% of the pairs instead of 1%. Cost per pair is in the verifier's own log.

Measured while building the cache: it takes about 0.2 MB of disk per second of video (50 MB for the 240 s of dev clips), and a second run over the same clips took 2.7 s instead of 76.7 s with identical pairs. The message of the commit that added the cache says 2 MB per second; that figure is wrong.

## Amendment 2 (Oct 28): mirror margin and core span, bands unchanged

Two changes to what the matcher writes, made after the held-out run reported on 8410505 and before the next held-out set is touched. Neither moves a band.

**Mirror margin.** The aligned score was computed for the plain pair and for the pair with one clip flipped, and the flipped alignment was taken whenever its score was higher. SSCD is nearly flip-invariant, so with nothing mirrored the two differ by hundredths and the flag was set at random: flipped minus plain, on 252 unrelated dev pairs, ranged from -0.016 to +0.015 and was positive on 47% of them; on 41 true unmirrored pairs (24 dev fixtures, 17 phone-forwarded copies) from -0.047 to +0.011. Eight true mirror images (ffmpeg flips of dev clips) gave +0.030 to +0.059. The flipped alignment now has to beat the plain one by 0.02, which sits between the two groups. The calibration is thin: eight synthetic flips, all from one set of clips, so 0.02 is provisional. Effect on the 276 dev pairs: no band changes; `mirrored` was 1 on 124 pairs and is 0 on all; `aligned` fell on 123 pairs by at most 0.015 and rose on none; offset or span moved on 39 pairs (the tied ones).

**Core span.** Four columns at the end of `pairs.csv`: the longest run of consecutive sampled frames along the alignment whose cosine is at least 0.4 (`eval/run-format.md`). The cut-off was chosen on the build split of `eval/compilation.md` only: at 0.4, 29 of 30 true segments get a run and none of 198 wrong-family pairs gives one of two or more frames (0.5: 24 of 30; 0.6: 17 of 30). On the 24 dev clips, 22 of 24 true pairs have a core span and 4 of 252 unrelated pairs do (1 of 2 s or more). The columns are not used for bands.

Merge threshold 0.55 and floor 0.20 are unchanged.

## Amendment 3 (Oct 28): cover columns and partial copies, bands unchanged

Six columns at the end of `pairs.csv` (`cover_a`, `cover_b` and their spans) say how much of each clip the other matches, and `cluster.resolve_all` uses them to record a merged pair that covers part of both clips as shared footage (`partial`) instead of joining the recordings. Definitions in `eval/run-format.md` (Partial copies); the band of 2 frames and the share of 0.8 were set on the build split of `eval/partial.md`. No band changes, and `pairs.csv` of the 24 dev fixtures is identical to the run at 23614a4 apart from the new columns; none of the 276 dev pairs is partial. Runs pinned to 23614a4 and 18a42e4 do not have the columns and are not affected.
