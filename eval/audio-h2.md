# H2: audio fingerprint as a second channel

Written Oct 27 2026 before any audio was fingerprinted. Free, local, no model calls. Exploratory.

## Hypothesis

A Shazam-style audio fingerprint (spectrogram peaks, hashed in pairs, vote on the time offset) tells us, independently of the picture, whether two clips share a soundtrack. That gives the harness three labels the picture alone cannot: **copy** (picture and sound agree), **sound replaced** (same picture, different sound: music or voice-over added), and **sound reused** (same sound, different picture). It should also survive re-encoding and partial reuse.

## Method

Audio extracted by ffmpeg to 8 kHz mono. Spectrogram (512-sample windows, 256 hop), local maxima in the log spectrum (15 by 15 neighbourhood) above the 80th percentile, each peak paired with up to 5 following peaks 0.1 to 2.0 s later, hash = (frequency 1, frequency 2, time gap). Two clips' hashes are matched; every shared hash votes for the time offset (64 ms bins). Score = votes in the best bin divided by the smaller clip's hash count. A clip has **usable audio** if it has at least 200 hashes. Code: `scripts/audio_h2.py`.

## Data

- The 30 pile clips (`data/spark_pile/clips`), all 435 pairs; truth by construction as in `eval/spark-pile.md` (the compilation counts as a partial copy of A1, N1, A3 and their copies).
- Natural cases: `A2_e5` (picture copy of A2 with the sound replaced by a tone); the four `_e1` copies (picture and sound sped up 1.25x, which a fingerprint is not built to survive); the compilation `A1N1A3_e4` (the soundtrack is cut together from three clips).
- Constructed (ffmpeg, in `data/spark_h2/clips`): `A1_swap`, `A3_swap`, `B2_swap` = the picture of A1, A3, B2 with the soundtrack of one donor clip. The donor is the first of N2, N3, N4, N5, N6 with at least 200 hashes and no relation to A1, A3 or B2.

## Threshold (fixed now)

τ = the highest audio score among **natural expected-no pairs where both clips have usable audio**. Not tuned afterwards. Everything at or above τ counts as "same sound".

## Pass bar (decided now)

1. **Copies:** among expected-yes pairs with usable audio on both sides, excluding the speed-changed `_e1` pairs and `A2_e5`: audio score at or above τ for at least 90%.
2. **Sound replaced:** `A2_e5` vs `A2` and each `X_swap` vs `X` (4 pairs) are below τ in audio.
3. **Sound reused:** each `X_swap` vs the donor clip (3 pairs) is at or above τ.
4. **No audio false match:** each `X_swap` vs every other clip that is neither X's family nor the donor: below τ.

## Reported, not scored

- How many of the 30 clips have usable audio (security cameras and screen recordings may have none).
- The `_e1` speed-changed pairs and the compilation against its sources.
- Same event, different camera (the four Phoenix cameras, the three Chelyabinsk cameras): do audio scores rise above the natural negatives?
- Whether audio recovers any picture-weak pair (pairs with the lowest SSCD aligned score among the true copies).

## Limits

Short clips (12 to 30 s), mostly ambient sound; ffmpeg edits not platform re-uploads; a constant offset only, no tempo handling; the donor is a single clip.

## Addendum A (Oct 27, written after the pile run, before the WhatsApp run)

Pile run, frozen bar: the bar was met on paper but on thin evidence. 15 of 30 pile clips have a digitally silent audio track (A1, B2, Y, N2, N5, N6 and others: RMS about 0), so only 4 copy pairs could be scored (4/4), two of the four "sound replaced" pairs were not scorable, sound reuse was found 3/3 (score 0.294 against a noise floor of 0.003), and speed-changed copies (1.25x) and different cameras scored at the noise floor. The pile does not tell us how audio behaves on real phone clips with real ambient sound.

So I run the same fingerprint on the real round trips from `eval/sscd-exploratory.md`: the 17 WhatsApp copies in `data/iphone_by_me/social_copies` and their originals (map in `MAP.csv`), plus the other clips in `data/iphone_by_me` (airshow, fireworks, Air Force clips: the same-place, same-kind-of-sound hard negatives). Families come from the map; everything else is a negative. Same parameters. τ = the highest score among negative pairs with usable audio on both sides (fixed now). Bar: at least 90% of the positive pairs with usable audio on both sides are at or above τ, reported with a Wilson interval. Reported: how many of these clips have usable audio, the five highest negatives, and the lowest positive.

## Addendum A.1 (Oct 27, after the first WhatsApp attempt, which was invalid)

My first attempt built the pool badly: `data/iphone_by_me` holds byte-identical copies of some clips in several folders, and unmapped WhatsApp copies of airshow and fireworks clips in `social_copies/<event>/`. Those scored 1.0 as "negatives" (they are duplicates), so tau was 1.0 and the 0 of 17 result is meaningless. It was not run again with a different rule. Corrected pool, as in `eval/sscd-exploratory.md`: the 17 mapped WhatsApp copies, their originals, and the other original clips (airshow, fireworks, Air Force folders) with byte-identical duplicates removed by file hash. Unmapped WhatsApp copies are excluded because their truth is not known. Tau rule, parameters and bar unchanged.

## Addendum A.2 (Oct 27, after the second WhatsApp attempt)

The second attempt still scored 1.0 on two negative pairs: `IMG_4018.MOV` and `video-5638_singular_display.mov` each exist twice, once at the top level and once in `airshow09262026/`, with different bytes. `MAP.csv` says so ("same clip also at airshow09262026/IMG_4018.MOV", "same file also at airshow09262026/"). Duplicates are therefore removed by file name, which is what the map records, not by file hash. Nothing else changes: same pool rule, same tau rule, same bar. The earlier two attempts' numbers are discarded because their pool was wrong.
