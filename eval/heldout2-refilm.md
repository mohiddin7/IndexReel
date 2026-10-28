# Held-out run 2, real re-film arm: phone re-films of the final2 originals, posted and downloaded back

Written Oct 28 2026, before any re-film of the final2 originals exists and before any final2 clip was opened by me (I have seen only the file list). Frozen by the commit that adds it. This is a separate protocol from `eval/heldout2.md` (the simulated arm). Both use the same code, and nothing in code or thresholds changes between the two runs, whichever runs first.

## Question

Does the pipeline put a realistic phone re-film of a recording into the same recording as its original after the re-film has been posted to a platform and downloaded back, without joining it to any other recording? The re-films are handheld, filmed tight with no bezel, and some are portrait.

## Data

- **Originals:** the 16 final2 sources `data/final2/b17_T.mp4` to `b24_N.mp4`, each a target or its look-alike from 8 blocks, unchanged.
- **Re-films:** made by me after this commit. Each one films an original playing on a screen, handheld, framed tight with no bezel visible, some in portrait. Each take is posted through X or WhatsApp and the platform's copy is downloaded back. Only the downloaded copy is used.
- **Manifest:** `data/final2_refilm/manifest.csv`, written when the re-films are made and before any is scored, with one row per re-film: `file`, `original` (for example `b19_T`), `framing` (`landscape` or `portrait`), `platform` (`x` or `whatsapp`). Truth comes from the manifest by construction. File names never reach the models: the matcher reads pixels, and the judge sees "Video A" and "Video B".
- `scripts/heldout.py prepare_refilm` puts the 16 originals and every re-film (named `refilm_<stem>`) into one folder, so the run is one pile: every re-film is scored against all 16 originals and against every other re-film.

## Pipeline (frozen)

- Code at commit `23614a4`, the same as `eval/heldout2.md`: `indexreel match` (`merge_at` 0.55, `floor` 0.20, theta 0.9, mirrored margin 0.02, SSCD sha256 `9f26bd4c848cc19b73d2ae92eea6e04886f61a7b764ceb7a13aeee62e6a6db56`), then `python -m indexreel.verify` (verifier from `6119685`: every merged and unresolved pair, conflict re-asks, at most 2 rounds), then `cluster.resolve`.
- Commands: `indexreel match data/heldout2_refilm/in --out data/heldout2_refilm/run`, then `python -m indexreel.verify data/heldout2_refilm/run --cache data/heldout2_refilm/verify_cache --max-usd 10` (fresh cache), then `scripts/heldout.py score_refilm`. No human decisions; run once.

## Decision rule

A re-film is **found** when `cluster.resolve` puts it in the same recording as its own original. A pair is **joined** when its effective band is `merged` and neither clip is marked a compilation.

## Pass bar

1. **No false merges:** 0 joined pairs between clips of different originals (re-film against original, and re-film against re-film), and no recording that mixes two originals.
2. **Found:** at least 75% of the re-films are found (the H5 bar, `eval/refilm-h5.md`).

A bar 1 failure is a FAIL whatever else happens.

## Reported, not scored

- Found rate by framing (landscape, portrait) and by platform (X, WhatsApp), each as k/n.
- Each own-original pair by band and verdict.
- The matcher alone (own original in the `merged` band) against matcher plus verifier.
- Every miss, with its framing, platform, aligned score, band and verdict reason. A miss in the `apart` band never reached the verifier, and the report says so.
- Compilation flags (expected 0). Re-asks. Cost at list prices.

## Limits

One person, one phone, one screen and one room. The 16 originals come in 8 target and look-alike pairs. Re-films of one original are not independent of each other. The platforms' processing on the day of upload is whatever it was then. Sound is the screen's speaker recorded by the phone, and the final2 sources may be silent. The arm tests the shipped pipeline on realistic copies of fresh recordings, not on copies found in the wild.
