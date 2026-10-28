# Held-out run: matcher plus verifier on the final split, once

Written Oct 28 2026 before any clip of `data/final/` was opened, decoded or scored by me, and frozen by the commit that adds it. The run happens after that commit, once.

## Question

On footage that no setting was chosen on, does the pipeline (`indexreel match`, then `indexreel.verify` on the unresolved pairs) join the versions of each recording and never join two different recordings?

## Data

- Blocks b09 to b16 in `data/final/` (delivered before any gate result, never replaced). Each block has a target `T` and a look-alike `N`, recorded separately: 16 families.
- Each family gets the three versions of `eval/gate.md` from `src/indexreel/variants.py`, unchanged: `orig`, `pip` (studio-style template) and `refilm_sim` (screen warp, bezel, glare, shake). `scripts/heldout.py prepare` writes them as `<family>__<version>.mp4`.
- 48 clips and 1,128 pairs: **48 positive pairs** (3 per family) and **1,080 negative pairs**. 3 of those negatives per block are target against look-alike for the same version; the template is shared across families, so same-template negatives are included.
- No physical re-films. If re-films of the final playlists exist before the freeze, they are a separate, reported-only arm and never change the verdict.

## Frozen pipeline

- Code at commit `8410505` (matcher frozen there, see `eval/match-thresholds.md` Amendment 1; the verifier is unchanged since it was added). `indexreel match data/heldout/in` (the 48 prepared versions, not the 16 sources) with `merge_at` = 0.55 (`eval/match-thresholds.md`), `floor` = 0.20 (lowered from 0.30 on dev before this freeze, so the two dark dev re-film positives reach the verifier), localiser theta 0.9, SSCD `sscd_disc_mixup` (sha256 `9f26bd4c848cc19b73d2ae92eea6e04886f61a7b764ceb7a13aeee62e6a6db56`), one frame per second.
- `python -m indexreel.verify` with its committed settings: Muse Spark `muse-spark-1.3`, 180 px, minimal effort, an anchor plus up to 4 candidates per request, conflicts re-asked at 360 px with default effort in both orders, and sound used only to escalate. `--max-usd 10`; the answer cache is emptied before the run.
- No human decisions (`audit.jsonl` stays empty). No rerun, no prompt or threshold change after the first clip is scored.

## Decision rule

A pair is **joined** when its band is `merged`, or its band is `unresolved` and the verifier says `same`. Recordings are the connected components of the joined pairs. `abstain` and `different` are not joined. Unanswered pairs (budget or transport) are not joined and are counted.

## Pass bar

1. **False merges:** 0 joined negative pairs, and no recording that mixes two families. Wilson upper bound reported.
2. **Recall:** at least 40 of 48 positive pairs joined (83%).

A bar 1 failure is a FAIL whatever else happens.

## Reported, not scored

- Positives by version pair (orig+pip, orig+refilm_sim, pip+refilm_sim), each with band and verdict.
- Every positive not joined, with its aligned score, band and verdict reason. A positive in `apart` never reached the verifier, and the report says so.
- Negatives by band, and the verifier's verdicts on unresolved negatives.
- Recordings found against 16.
- Matcher alone (merged band only) against matcher plus verifier: what the verifier adds and what it costs.
- Verifier cost at list prices, number of requests, and wall time.

## Limits

These are simulated copies of 16 recordings: one PiP template and one re-film simulation. The result says nothing about copies in the wild, real phone re-films (see `eval/refilm-h5-result.md` for those) or other cameras at the same event. With 48 positives, a Wilson interval is wide. Two target clips are my own phone recordings. Everything runs once.
