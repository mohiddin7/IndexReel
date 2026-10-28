# H11: confirm the cheap judge setting on a different set of pairs

Written Oct 27 2026 before any call. H10 found that minimal reasoning effort with the shorter side re-encoded to 240 or 180 px kept 18/18 yes and 0/68 false yes at 49% and 32% of the default cost, and broke at 120 px (one false yes, one miss, both on the small-inset layouts). That was found and read on one set of 86 pairs. This run asks whether it holds on a set that was not used to choose it.

## Design

The 129 pairs of H1 (`spark_h1.pair_list()`: 28 expected yes, 101 expected no; pile clips and edits). Arm V only, prompt v3, `reasoning.effort` minimal, clips re-encoded to a shorter side of 240 and of 180 px (same codec, crf 28, audio 64 kbit/s), each pair asked once per size, orientation as in the stored baseline. Baseline: the answers already collected at default effort and native size (pile run, verify calls, pilot 3), not re-asked.

## Pass bar for each size (decided now)

1. Yes on at least 27 of 28 expected-yes pairs.
2. **0** false yes on the 101 expected-no pairs.
3. Cost per pair at most 50% of the baseline's.

## Reported

Tokens, cost and seconds per pair; every pair whose answer differs from the baseline, with its clips; unsure count.

## Limits

Same footage family as the other tests; not independent in content, only in pairs and layouts (the pile edits `_e1` to `_e5`); still ffmpeg edits and no real re-films; one run per size.
