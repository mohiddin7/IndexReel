# Spark pilot result (Oct 26): passes the bar I set, but the bar was easy

Protocol: `eval/spark-pilot.md`, frozen before the first call. One pass over 23 pairs, `muse-spark-1.3` Standard mode, no reruns. Cost $0.50 (about 13k input tokens per pair).

| Rule | Bar | Result |
|---|---|---|
| Copies: same_footage yes | 7 of 8 | **7 of 8** (miss: MA vs its 240p re-encode, answered no and said a heavy re-encode "cannot be fully ruled out") |
| Different event: same_event no | 8 of 9, never same_footage yes | **9 of 9**, no false merge |
| Other camera, same moment: same_event yes, same_footage no | 3 of 4, and 4 of 4 | **4 of 4 and 4 of 4** (Y-M, Y-I, M-I, C0-C4) |
| No same_footage yes on any non-copy pair | 0 | **0** |

Overall: PASS. Zero "unsure" answers, zero unparsable replies.

What I do not conclude:
- The negatives were easy: a day-lit meteor against a rocket launch. A pass on them says little about two similar events (two launches, two storms), which is where a false "same event" would hurt. This is the real test and it is not yet run.
- Both events are famous. Spark may be recognising them, not matching frames. I cannot tell from this run.
- 19 of 23 answers mention a clock, timestamp or overlay in their observations. For the Chelyabinsk cameras the clocks disagree by 10 minutes and Spark still said same event, so it did not rely on the clock alone. For the NASA pair it cited the shared UTC overlay.
- It was inconsistent on the Starship ground view: C0-MA said no, C4-MA said yes, for the same event with no shared moment.
- Audio was not tested.
- 23 pairs, one run. This shows feasibility and failure modes. It is not a rate.

Next: a second pilot with hard negatives (different launches, different meteor clips), overlays masked, and the PDQ matcher scored on the same pairs so the "disagreement" is measured.
