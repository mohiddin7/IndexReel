# Spark pilot 2 result (Oct 26): strong on "same recording", unreliable on "same event"

Protocol: `eval/spark-pilot2.md`, frozen before the first call. 48 pairs, `muse-spark-1.3` Standard mode, one pass, prompt v2. Cost $0.94 (about $0.02 a pair). One batch of calls was lost to a transport error (`no response.completed`) before any answer was saved; I added a retry for that and re-ran the same pairs. No answer was ever re-asked.

| Rule | Bar | Result |
|---|---|---|
| 1 Edited copies: same_footage yes | 11 of 14 | **14 of 14** |
| 2 Other camera, same moment: same_footage no / same_event yes | 9 of 9 / 7 of 9 | **9 of 9 / 9 of 9** |
| 3 Hard negatives: same_event no / same_footage yes | 22 of 24 / 0 | **8 of 24 (FAIL) / 0** |
| False merges (same_footage yes on a non-copy) | 0 | **0 of 33** |

Rule 3 fails: on 24 different-event pairs Spark said same_event yes 10 times and unsure 6 times. Overall verdict under my own rule: **FAIL on the event question, PASS on the recording question.** Zero false merges, but 0 of 33 does not rule out a false-merge rate of about 10% (Wilson upper bound).

## What this says

1. **Recording identity.** Spark found the same recording in every edit, including the vertical reframe and the picture-in-picture, where the PDQ matcher scored 0.001. PDQ cleared 0.5 on 8 of the 14 copies. On the compilation (6 s of A1, 6 s of the Winnipeg clip, 6 s of A3) it returned shared spans [0, 6], [6, 11] and [12, 17.5] against a truth of 0 to 6, 6 to 12 and 12 to 18. No localiser and no matcher code was involved.
2. **Event identity.** It cannot tell two similar meteors apart. Typical reasoning: "both show a bright moving light in the night sky". The "same event yes" answers sit on both real same-event pairs and different-event pairs, so the answer carries no signal here. A Spark "same event" must never turn into "independent witness".
3. **No sign of memorised events.** Asked where and when each clip was filmed, Spark named no place or event from the footage. Every date it gave came from a burned-in clock; clips without a clock came back "unknown".

## What I do not conclude

- 39 of 48 answers cite a clock, date or overlay. The edited copies keep the original's burned-in text (for example "2026-10-06 01:03:46 cam002"), so Spark may be matching on the text and not the pixels. This is the main hole in the 14 of 14. The next run masks the overlays first.
- One run, one prompt, one order per pair. No repeat for consistency, no check of A/B order bias.
- Latency not measured. The cost grows with the square of the pile: 20 clips is 190 pairs, about $3.80.
- A Winnipeg clip and the Phoenix 2016 clips were the "different event" cases; none was a different camera of a genuinely different event with a visible distinguishing detail.

## Next

Pilot 3: mask burned-in overlays before cutting the edits, run each pair twice with the order swapped, and add 10 different-event pairs that differ in a visible way (location, light, weather). Decide after that whether Spark becomes the "same recording" verifier behind a cheap PDQ prefilter.
