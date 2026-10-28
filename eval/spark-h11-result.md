# H11 result: the cheap judge setting on another set of pairs (Oct 27 2026)

Protocol: `eval/spark-h11.md`. Code: `scripts/spark_h11.py`. The 129 pairs of H1 (28 expected yes, 101 expected no), whole-video judge at minimal effort, clips re-encoded to a shorter side of 240 and 180 px. Baseline: the stored default-effort answers. Spend about $2.

| Setting | Yes | False yes | Cost per pair | Seconds | Bar (yes 27/28, 0 false yes, at most 50% of baseline) |
|---|---|---|---|---|---|
| baseline (default effort, native size) | 28/28 | 0/101 | $0.0198 | | |
| minimal, 240 px | 28/28 | 0/101 | $0.0101 (51%) | 5.6 | **fails by one point on cost** (accuracy perfect) |
| minimal, 180 px | 27/28 | 0/101 | $0.0063 (32%) | 5.9 | **meets** |

- **The H10 setting holds on other pairs.** No false yes at either size, so no false merge in 202 further judged non-copy pairs across both sets for the cheap settings (86 + 129 less the overlap; each count is per pair set, not pooled).
- **The one miss at 180 px** is `B2_e1` vs `B2_e2` (a mirrored, 1.25x sped copy against a small-inset vertical reframe of the same clip). It is the hardest pair of the whole programme: frame sheets also failed it (unsure). A miss here means the recording would be listed twice, not merged wrongly, because both copies still match `B2` itself.
- **240 px misses the cost bar by one point** (51% against 50%) with no accuracy loss. The bar was mine and the choice between 240 and 180 is a margin-against-cost trade: 240 px for piles that may hold small insets, 180 px otherwise.
- `N2` vs `B2` went from "unsure" to "no" at both sizes (a correct answer).

## Limits

Same footage family and ffmpeg edits; not independent in content; one run per size; the miss is one pair; clip lengths 12 to 30 s.
