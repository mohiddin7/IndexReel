# H5: the judge on real phone re-films

Written Oct 27 2026 before any model, matcher or fingerprint was run on a re-film clip. I read only `data/refilmed/README.md` and `MANIFEST.csv`. The clips are cut from my takes into `data/refilmed/clips/` with `clips_manifest.csv`. Exploratory, as the README says: physical re-films never decide the gate. `data/final/` is not touched.

## Question

Does the cheap judge (whole-video Spark, one pair per request, prompt v3) recognise a clip filmed off a monitor with a handheld iPhone as the same recording as its original, and refuse the look-alike?

## Data

- Six takes of the three `devgate` playlists (A handheld, B straight on, C about 20 degrees off axis; each filmed with the whole monitor and bezel visible, and again tight), 16 clips each = **96 re-film clips**. Each take's clip is cut from the cuts CSV of the playlist actually played (`playlist_played`), offset applied.
- **16 originals**: `data/gate/b01_T.mp4` to `b08_T.mp4` (targets) and `b01_N.mp4` to `b08_N.mp4` (look-alikes: the same kind of scene, a different recording).
- Truth by construction: a re-film clip with id `bXX_T` comes from the original `bXX_T` (expected **yes**), and from none of the other 15 (expected **no**, 15 per clip); the look-alike `bXX_N` is the hardest negative for a `bXX_T` clip and the reverse. Pairs: 96 x 16 = **1,536** per arm: 96 expected yes, 1,440 expected no (96 of them against the look-alike).
- The bezel and tight takes of one playlist are one playback filmed twice: they are reported together as one group per playlist and never split.

## Judges (same pairs, same prompt)

`muse-spark-open` on the Modal Shared Endpoint (`indexreel-spark-open`), prompt v3 unchanged, `reasoning_effort` low, one pair per request, 4 at a time, re-film clip as video B. Two arms: clips re-encoded to a shorter side of **360 px** (reference) and **180 px** (the cheap setting). Expected cost about $27 at list prices; stop and report if spend passes $35.

## Pass bar (decided now), for each arm

1. Yes on at least **72 of 96** re-film clips against their own original (75%).
2. **0** false yes on the 1,440 expected-no pairs (Wilson upper bound about 0.3%), including the 96 look-alike pairs.

## Reported, not scored

Yes rate by playlist and framing (bezel, tight) and by style (handheld, straight on, off axis); the clips missed and what the judge said; the same pairs in both arms; the unsure count; seconds and cost. Free, local, on the same 96 clips: SSCD (aligned score) top-1 of the true original among the 16 originals and the lowest margin; PDQ (`indexreel.match`) the same; the audio fingerprint match rate between each re-film clip and its original (the phone records the monitor speaker).

## Limits

16 distinct recordings and 6 takes of 3 playbacks, so the 96 clips are not 96 independent samples (bezel and tight, and the three playlists, show the same clips); one phone, one monitor, one room; the gate clips b05 to b08 and the dev clips b01 to b04 are pooled here and not split; no tuning happens on any of this; a result is exploratory.
