# H1c: route risky layouts to the whole-video judge, tested on new edits

Written Oct 27 2026 before the new clips were built or any call was made. Follows H1 (frame sheets failed on a tiny vertical-reframe inset) and H1b (no reliable crop; not run).

## Hypothesis

Frame sheets are cheap but unsafe when a clip's real picture is small inside the frame. Rather than finding the picture, the harness decides per pair which judge to use. A simple policy can keep the false "yes" at zero and still cost clearly less than judging every pair with whole videos.

## Policies, all decided now (answers for them come from the same two arms, so no extra calls)

- **V**: whole-video judge on every pair (baseline).
- **F**: frame sheet on every pair.
- **R, router**: whole-video judge if either clip is portrait (height greater than width); frame sheet otherwise.
- **C, cascade**: frame sheet first; pairs where it says yes or unsure go to the whole-video judge, and that answer is final.
- **RC**: the router, then the cascade on the pairs it sent to frames.

## Holdout data (new edits, built now from pile clips; none was used in H1, H1b or any tuning)

Twelve edited clips, `data/spark_h1c/clips`, ffmpeg, libx264 crf 28, at most 20 s:
- `vz` portrait zoom crop (centre 9:16 of the clip, no blur): A2, A4, B1.
- `vb` portrait with a smaller inset (75% width) over blurred fill, black bar, white caption block: N1, N4, B2.
- `pp` picture-in-picture: the clip at 240 px wide in the bottom-right corner **over another real recording**: A2 over N3, A4 over N1, B1 over N5 (contains two recordings).
- `ss` split screen, each clip centre-cropped to a half: B1|N4, A2|N5, A4|N3 (two recordings).

## Pairs

For each edited clip: its source clip(s) (expected **yes**; for `pp` and `ss` both sources), then 3 same-kind hard negatives (other Phoenix cameras for an A source, B2 or B1 for a B source, other N clips for an N source) and 3 random other clips, all excluding the sources' families (expected **no**). Choices seeded (seed 2612). Each pair asked once in each arm (V and F), orientation by the same seed, overlays masked as before (the pile clips already are; the new edits are made from the masked clips).

## Pass bar for a policy (decided now)

1. Yes on at least 90% of the expected-yes pairs.
2. **0** false yes on the expected-no pairs.
3. Cost per pair at most 70% of V's.

The recommended policy is the cheapest one that meets all three. If none does, V stays the only judge.

## Reported, not scored

Arm F alone per edit type (`vz`, `vb`, `pp`, `ss`): which layouts break frame sheets; the fraction of pairs each policy sends to video; every false yes with its observations; whether Spark's span for the partly-copied clips (`pp`, `ss`) is sensible.

## Limits

Twelve clips from the same footage as the rest of the pile; ffmpeg layouts I chose (real reposts differ); the routing rule is simple on purpose and will not catch a landscape clip with a tiny inset (an assumption the `pp` edits test). One run.
