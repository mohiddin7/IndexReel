# H10 result: video resolution as a cost dial (Oct 27 2026)

Protocol: `eval/spark-h10.md`. Code: `scripts/spark_h10.py`. The 86 pairs of H1c, whole-video judge at minimal effort, clips re-encoded to a shorter side of 240, 180 and 120 px. Spend about $2.

| Setting | Yes | False yes | Input tokens | Cost per pair | Seconds | Bar (50% of default) |
|---|---|---|---|---|---|---|
| default effort, 360 px | 18/18 | 0/68 | 9,692 | $0.0185 (100%) | not recorded | baseline |
| minimal, 360 px | 18/18 | 0/68 | 9,692 | $0.0140 (76%) | 6.1 | (H8) |
| minimal, **240 px** | 18/18 | 0/68 | 5,840 | $0.0091 (49%) | 6.0 | **meets** |
| minimal, **180 px** | 18/18 | 0/68 | 3,259 | $0.0059 (32%) | 4.9 | **meets** |
| minimal, 120 px | 17/18 | **1/68** | 1,952 | $0.0042 (23%) | 4.6 | fails |

- **Tokens track resolution, not frame rate** (probe on one pair: 360p at 15 and at 5 fps both 11,221; 240p 6,901; 180p 3,781; 120p 2,261; audio about 500).
- **The cliff is between 180 and 120 px.** At 120 px the failures are all on the small-inset vertical layouts (`vb`): one false yes (`A1` vs a `vb` edit of `N4`), one "unsure" flips, plus one miss on a portrait zoom. 180 px produced two answer changes against the default, both harmless ("no" to "unsure" on a `vb` pair, and an "unsure" to "no" on a picture-in-picture pair that is also changed by every minimal run).
- **Recommended setting by the protocol: minimal effort at 180 px**, 32% of the default cost. The margin to the cliff is one step, so 240 px (49%) is the safer choice if a pile contains small insets. H11 tests both on another set of pairs.
- **Combined with the pair prefilter** (84 of 435 pairs on the 30-clip pile), a pile costs about 6% of judging every pair with the default setting: 84 x $0.0059 = $0.50 against 435 x $0.0185 = $8.05. This is an extrapolation from two separate tests, not one run.

## Limits

86 pairs, one run per size, same footage as H8; chosen and read on the same set (H11 is the check on another); the token curve was measured on 20 to 30 s clips and will differ for long ones.
