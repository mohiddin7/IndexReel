# H10: video resolution as a cost dial for the whole-video judge

Written Oct 27 2026 before any pair was judged at a reduced resolution. Follows H8 (lower reasoning effort kept accuracy but input tokens remain about 86% of the cost). A four-call probe on one pair (A3 and its mirrored copy, effort minimal) showed input tokens fall with resolution and not with frame rate: 360p 11,221, 360p at 5 fps 11,221, 240p 6,901, 180p 3,781, 120p 2,261; audio is about 500 tokens. The probe judged the pair correctly at every size; one pair says nothing about accuracy.

## Hypothesis

Re-encoding clips to a smaller shorter side before upload cuts the cost per pair a lot and keeps the judge's accuracy on copies, hard negatives and layout edits, down to some size. The question is where it breaks.

## Design

The same 86 pairs and clips as H1c (`data/spark_h1c`). Each clip is re-encoded with ffmpeg so its shorter side is S pixels (S = 240, 180, 120; same codec, crf 28, audio kept at 64 kbit/s). Arm V only, prompt v3, `reasoning.effort` = minimal (the H8 setting), each pair asked once per size, same orientation. Baselines already collected: default effort at the original 360 px (H1c) and minimal at 360 px (H8).

## Pass bar for each size (decided now)

1. Yes on at least 17 of 18 expected-yes pairs.
2. **0** false yes on the 68 expected-no pairs.
3. Cost per pair at most 50% of the default-effort 360 px baseline.

The recommended judge setting is the smallest size that meets all three. If none does, the setting stays at minimal effort and 360 px.

## Reported

Tokens, cost and seconds per pair at each size; which pairs change answer against the 360 px baseline and their edit type (vertical, small inset, picture-in-picture, split screen); same-event answers on the hard negatives.

## Limits

Clips are 20 to 30 s and start at 360 px; real reposts differ in length and quality; 86 pairs, one run per size, the same footage as H8. The drop in token count at one size may differ for longer clips.
