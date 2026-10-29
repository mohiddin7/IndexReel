# Same place, different recording: result (Oct 28 2026)

Protocol: `eval/sameplace.md`, frozen at `e948c78` before any WhatsApp copy was scored. Pipeline at `66a179b` (match, verify, clusters), run from a detached checkout. Scorer `scripts/sameview.py` at `e948c78`, with `--min-s 5`. The data is 15 handheld camera-roll clips by me in 6 groups (one place and sitting each, recorded minutes apart) and their 15 WhatsApp copies: 30 clips, 435 pairs. Run once, fresh cache, no human decisions. The manifest came from the footage step (copy matched to raw clip by duration and by eye) and was checked against the frozen groups before the run.

## Verdict: FAIL on bar 1

| | result | bar |
|---|---|---|
| 1 Automatic merges between different recordings | **4 / 420** (all 4 are the raw and copy combinations of one pair of recordings, `IMG_2951` and `IMG_2956`); no recording holds two recordings | 0 |
| 2 Copies found in their own recording (recordings of at least 5 s) | **14 / 14** | all |
| Copy of the one clip under 5 s (`IMG_2871`, 2.8 s) | found (reported, not scored) | reported |
| Recordings found | 15 (truth 15); 8 with status `unresolved` | reported |
| Matcher alone: different recordings in `merged` | 24 of 52 same-place pairs (G1 16, G3 4, G5 4); 0 of 368 cross-place (highest 0.131) | reported |
| Verifier cost | $0.897 at list prices, 18 pairs re-asked | reported |

Bar 1 failing makes the run a FAIL, as frozen. Amendment 1 of `eval/sameview.md`, carried into this protocol, counts a shared-footage claim between two different recordings as an automatic merge.

## The failure

`IMG_2951` (14.4 s) and `IMG_2956` (21.9 s) are two handheld pans over the same city view, recorded minutes apart. The matcher left all four of their pairs `unresolved`, at aligned 0.33 to 0.39. One cheap call per pair (180 px, minimal effort) said `same`, with reasons like "ends on the same aerial view … that opens video A, appearing as the contiguous preceding part of the same panoramic pan". The judge read a second pan that starts where the first one ended as one continuing recording. The two recordings share a view, not footage.

Nothing re-checked it. The four `same` answers agree with each other, so no conflict arose and no full-fidelity re-ask was triggered. The sound differed on all four pairs (0.002 to 0.004), and the sound may only escalate a pair that was not called `same`. The partial-copy rule (`a76f522`) then saw links that cover only part of both clips. It kept the two recordings apart and showed the links as shared footage, so the page would say "shares footage with" for two recordings that share none.

## What the verifier did well here

- The matcher merged **24** same-place negatives on its own: the river skyline (G1), the sunset over water (G3) and the street corner (G5). The verifier checked every merged pair and said `different` on 23 and abstained on 1, so all 24 were demoted to `unresolved`. Without verifying merged pairs, this set would have had 24 false merges. This is the first set where that check caught real errors (`eval/report2-refilm.md` measured only its recall cost).
- Of the 23 unresolved same-place negatives, it said `different` on 19. Its four `same` answers are the failure above.
- All 15 own-copy pairs were `merged` and confirmed `same`, 4 of them after re-asks. Recall is complete, including the 2.8 s clip.

## What this says

- Handheld recordings of one place, minutes apart, look like copies to the frame matcher: 24 of 52 same-place pairs crossed `merge_at`. On real camera rolls, the verifier is what keeps them apart.
- The judge has a specific blind spot: two consecutive pans of one view, where one ends where the other begins. It reads them as one recording continued. The sound disagreed and the shared span was partial, but neither was allowed to stop a `same`.
- Two rule changes could have caught it. Both are hypotheses for a new, pre-registered set and are not tuned here:
  1. A `same` on a pair whose sound clearly differs while both clips have usable sound goes to the full-fidelity judge.
  2. A link that covers only part of both clips and rests on one cheap answer is re-asked before it is shown as shared footage.

## Limits

One person's camera roll: 6 places, 15 recordings, 27 landscape and 3 portrait clips. The groups come from file numbers and creation dates. The failure is one pair of recordings counted four times through their copies, so 4/420 overstates how independent the errors are. Run once.
