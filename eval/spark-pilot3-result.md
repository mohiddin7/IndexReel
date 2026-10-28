# Spark pilot 3 result (Oct 26): the recording result survives with the text removed; Spark abstains on events

Protocol: `eval/spark-pilot3.md`, frozen before the first call. Burned-in text masked, 56 pairs each asked in both orders (112 calls), prompt v3, `muse-spark-1.3` Standard mode, one pass. Cost $2.22.

| Rule | Bar | Result |
|---|---|---|
| 1 Edited copies: same_footage yes in both orders | 12 of 14 | **14 of 14** |
| 2 Non-copy pairs with any same_footage yes | 0 | **0 of 42** |
| 3 Hard negatives with any same_event yes | at most 2 of 24 | **0 of 24** |
| 4 Easy negatives (meteor vs rocket): same_event no in both orders | 7 of 8 | **0 of 8 (FAIL)** |
| 5 same_footage identical across orders | 90% | **100% (56 of 56)** |

Under my own bar this is a **FAIL on rule 4 only**. The cause is the prompt I chose: it allows "no" only when details contradict, and Spark answered "unsure" on 13 of 16 meteor-against-rocket answers. That is over-cautious, not wrong.

## What it says

1. **Recording identity holds without any on-screen text.** All 28 answers on the edited copies (mirror and speed-up, vertical reframe, picture-in-picture, compilation, swapped audio) said same footage, in both orders. No answer cited a clock, date or overlay (0 of 112). Compilation spans came back within about one second of the truth (A1 [0, 6], N1 [6, 11], A3 [12, 17] against 0 to 6, 6 to 12, 12 to 18).
2. **No false merge in 84 non-copy answers** (42 pairs, both orders), and every answer was the same in both orders.
3. **Strict "same event" turns Spark into an abstainer.** Hard negatives: 48 of 48 "unsure", none "yes". Real same-event pairs: 15 "unsure", 3 "yes" (each with a plausible shared detail such as the flare mid-flight). So it never over-claims, but it also cannot confirm that two cameras saw the same event. That is the honest behaviour for "possible separate recording, unresolved", and it means Spark cannot supply the independence evidence by itself.

## What I do not conclude

- 56 pairs, one pass, one prompt per pair, 12 source clips from two event types. Zero false merges in 42 pairs allows a rate up to about 8% (Wilson upper bound).
- The edits are ffmpeg edits, not real reposts. A real re-film off a screen is not in this set; the project's SSCD work covers real phone re-films.
- The masking removes the top and bottom 13% of every frame, which also removes some sky.
- Latency is not measured. Cost grows with the square of the pile (about $0.02 a pair).
