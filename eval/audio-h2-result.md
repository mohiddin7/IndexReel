# H2 result: audio fingerprint as a second channel (Oct 27 2026)

Protocol: `eval/audio-h2.md` with Addenda A, A.1, A.2. Code: `scripts/audio_h2.py`. Free, local, no model calls. Two runs: the 30-clip pile and the real WhatsApp round trips.

## Pile (30 clips; frozen bar met, on thin evidence)

| Check | Result |
|---|---|
| Clips with usable audio | **15 of 30**. The rest have digitally silent tracks (RMS about 0): most security cameras, the Chelyabinsk dashcam, Starship clips. |
| 1 Copies at or above tau (tau = 0.0032, the noise floor) | 4 of 4 (only 4 copy pairs had sound on both sides) |
| 2 Sound replaced reads as "different sound" | 2 of 2 scorable (`A2_e5` 0.000; `A3_swap` 0.0031, razor-thin against tau); 2 of 4 not scorable (original silent) |
| 3 Sound reused under another picture reads as "same sound" | 3 of 3 (score 0.294 against a noise floor of 0.003) |
| 4 Swapped clips against unrelated clips | none above tau (max 0.0031) |
| Speed-changed copies (1.25x) | missed (0.0008 to 0.0032, noise), as expected: no tempo handling |
| Different cameras, same event (Phoenix) | no lift (0.0004 to 0.0012). Audio cannot say "same event". |
| Compilation vs its sources | N1 0.294, A3 0.048 (its 6 s segment in a quiet clip), others near noise |

## Real WhatsApp round trips (Addendum A, corrected twice)

57 clips (17 mapped WhatsApp copies, their originals, the other airshow, fireworks and Air Force clips), 53 with usable sound. Tau (highest of 1,361 negative pairs) = 0.0066.

- **Copies at or above tau: 17 of 17** (Wilson 95% 0.82 to 1.00). Bar 90%: pass.
- Lowest positive 0.105; highest negative 0.0066: a **16-fold gap**. The negatives include other recordings of the same airshow and the same fireworks show, with the same kind of sound.
- Two earlier attempts were thrown away: my pool held duplicate files, which scored 1.0 as "negatives". The tau rule and bar never changed; only the pool did, and both fixes are written in the protocol.

## What this says

- Audio is a strong, clean second channel **when there is sound**: real platform round trips match 17 of 17 with a wide gap, and re-used soundtracks under new pictures are found. Real phone clips have sound (53 of 57); the pile's footage does not, which is why the pile looked weak.
- It gives the harness labels the picture alone lacks: **sound replaced** (same picture, different sound) and **sound reused** (same sound, different picture).
- It cannot say two different cameras saw the same event, and it does not survive a speed change. Missing sound must be reported as "no audio evidence", never as a mismatch.
- Audio did not rescue any picture-weak copy in the pile (those clips are silent). Whether it helps on picture-weak real re-films is untested.

## Limits

Short clips; ffmpeg edits and WhatsApp only, no other platforms; constant offset only; the pool was corrected after the first runs (documented); the swapped clips use a single donor; tau rides the noise floor, so a harder negative set could raise it.
