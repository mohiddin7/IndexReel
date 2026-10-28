# Held-out result: matcher plus verifier on the final split (Oct 28 2026)

Protocol: `eval/heldout.md`, frozen at `2ee11ff` before any final clip was opened, with Addendum A (`48b7ba5`): the verifier crashed on its first request with an argument bug, fixed in `a9125c5` before any answer existed. Matcher at `8410505` (`merge_at` 0.55, `floor` 0.20, theta 0.9). Code: `scripts/heldout.py`. 48 clips (16 families, 3 versions each), 1,128 pairs, run once, no human decisions.

## Verdict: FAIL on bar 1 (false merges)

| | result | bar |
|---|---|---|
| 1 False merges (joined negative pairs) | **2 / 1,080** (Wilson 95% 0.0005 to 0.0067); 2 recordings mix two families | 0 |
| 2 Positives joined | **48 / 48** (Wilson 95% 0.93 to 1.00) | at least 40 |
| Recordings found | 14 (truth 16) | reported |
| Verifier cost | $0.055 at list prices for 31 unresolved pairs, 0 escalations | reported |

Bar 1 failing makes the run a FAIL.

## The two false merges

Both are the target against its look-alike, both in their `refilm_sim` versions, the hardest negatives in the set (same kind of scene, same simulated screen, bezel and glare).

- **`N15__refilm_sim ~ T15__refilm_sim`: the matcher.** Aligned score 0.597, above `merge_at` 0.55, so the pair was `merged` and the verifier never saw it. On dev the highest negative was 0.537; this held-out negative is 0.06 higher.
- **`N11__refilm_sim ~ T11__refilm_sim`: the verifier.** The matcher left it `unresolved` (aligned 0.264, best-match score 0.565). One cheap call (180 px, minimal effort) said `same`: "river canyon with fallen tree branches in foreground over water and rocky cliffs in background matching A at end of pan". No conflict was raised, so it was never re-asked. The verifier's conflict check only looks at pairs it has answered and treats every other pair as no objection. Here the pairs that contradict the merge (`N11__orig` against `T11__refilm_sim`, and so on) are in the `apart` band. H14 asked such unasked neighbour pairs; the verifier as built does not, and does not read `apart` as a contradiction either. This is a gap between the measured harness and its implementation, found here.

Both merges pull a target and its look-alike into one recording of 6 clips, so 16 families become 14 recordings.

## Matcher alone against matcher plus verifier

| | matcher alone (`merged` band) | plus verifier |
|---|---|---|
| Positives joined | 35 / 48 | 48 / 48 |
| False merges | 1 | 2 |

On the 31 unresolved pairs, the verifier said `same` on all 13 positives and `different` on 17 of 18 negatives. Its one error is the merge above. By version pair, the 13 positives it recovered were 1 orig+pip, 6 orig+refilm_sim and 6 pip+refilm_sim. No positive fell to `apart`, so no loss was out of the verifier's reach. Sound was unusable on every unresolved pair (the sources have no audio track), so sound escalated nothing.

## What this says

- On simulated copies, the pipeline finds every version of every recording: 48/48, against 35/48 for the matcher alone. The verifier recovers all 13 pairs the matcher could not decide, for about five cents.
- It is not safe yet. A false merge is the error this product must not make, and both arrived through the same door: a simulated re-film of a look-alike scene. One came from a threshold set on dev that held-out data exceeds by 0.06. The other came from a single cheap judgement that nothing double-checked.
- Two changes follow from this, and both need their own pre-registered test on new data. Nothing here tests them, and this split is now spent:
  1. Treat an `apart` pair inside a would-be recording as a conflict that forces a full-fidelity re-ask. The run format already lists these as `conflicts`.
  2. Send merged pairs that rest on re-film-like evidence (low localiser acceptance, or aligned close to `merge_at`) to the verifier instead of merging them outright.

## Limits

Simulated copies of 16 recordings with one PiP template and one re-film simulation. The sources are silent. With 1,080 negatives, a 0/1,080 result would have bounded the false-merge rate at 0.36%; 2/1,080 does not bound it below 0.67%. The final split has now been used and cannot test the fixes above. Run once; the match output was not rerun after Addendum A.
