# Same place, different recording: real handheld clips must stay apart

Written Oct 28 2026. The raw clips exist in `data/sameview/my_phone/raw/`. I have not opened, decoded or scored any of them, and what I know of them is the description below. The WhatsApp copies do not exist yet. This file is frozen by the commit that adds it, before any copy is scored.

## Why

`eval/sameview.md` tests the hardest form of the risk: a static view, braced, filmed twice from one spot. This test uses what a phone's camera roll really holds. These are handheld clips of one place, one sitting, recorded minutes apart. Each clip is a separate recording of the same scene, which is the case a frame matcher is most likely to join wrongly. Nothing is tuned on it.

## Question

When one place is recorded several times by hand within minutes, does the shipped pipeline keep the recordings apart automatically? Does it still join each recording with its own WhatsApp copy?

## Data

- **Raw clips:** 15 camera-roll clips by me in `data/sameview/my_phone/raw/`. They are handheld, mostly 4K at 60 fps and portrait, 2.8 to 48 s long. One file is one recording.
- **Groups**, one place and one sitting each, by the clip number in the file name (taken from the creation-date tag):
  - G1: 0057, 0058, 0059, 0060
  - G2: 2113, 2125 (45 min apart)
  - G3: 2141, 2142
  - G4: 2444, 2449
  - G5: 2871, 2872, 2873
  - G6: 2951, 2956
- **Copies:** I send each raw clip through WhatsApp and save the downloaded copy in `data/sameview/my_phone/whatsapp/`. A raw clip with no copy is reported and has no positive pair.
- **Manifest:** `data/sameview/my_phone/manifest.csv` has the columns of `eval/sameview.md`: `file, view, take, kind, original, platform`. `view` is the group (G1 to G6), `take` is the clip number, `kind` is `raw` or `whatsapp`, and `original` is a copy's raw file. It is written before anything is scored. Clip ids are file stems and must be unique.
- **Truth by construction** (n given for 15 raw clips, each with a copy):
  - **positive:** a raw clip and its own copy. 15.
  - **same-place negative:** two different recordings of one group, in any raw/copy combination. 4 per pair of recordings: 13 such pairs, so 52.
  - **cross-place negative:** clips of different groups. 368.
- **Short clips, decided now:** the matcher samples one frame per second, so a clip under 5 s gives at most 4 frames. The duration is the raw clip's `duration_s` in the run's `clips.json`, as `indexreel match` measures it.
  - Short clips stay in the pile and **count fully for bar 1**, because a short clip can still cause a false merge.
  - For **bar 2**, only recordings of at least 5 s count. The copies of shorter recordings are reported separately and not scored.

## Frozen pipeline

- **Code:** match, verify and clusters from the shipped pipeline at **`66a179b`**, the same version as `eval/sameview.md` Amendment 1, which includes `3ff95f6` (incomplete answers count as no answer). The scorer and prepare step are `scripts/sameview.py` from the commit that freezes this file, which adds `--data`, `--into` and `--min-s` and changes nothing else in how `eval/sameview.md` is scored. It runs from a detached checkout of `66a179b`, with `PYTHONPATH` set to its `src`, and the SSCD model (sha256 `9f26bd4c848cc19b73d2ae92eea6e04886f61a7b764ceb7a13aeee62e6a6db56`) given by absolute path. Bands, `merge_at` 0.55, `floor` 0.20 and theta 0.9 are as shipped.
- **Commands:**
  1. `scripts/sameview.py prepare --data data/sameview/my_phone --into data/sameplace_in`
  2. `indexreel match data/sameplace_in --out data/sameplace_run`
  3. `python -m indexreel.verify data/sameplace_run --cache data/sameplace_verify_cache --max-usd 3`, with a fresh cache and the default `meta` backend
  4. `scripts/sameview.py score --data data/sameview/my_phone --run data/sameplace_run --min-s 5`
- No human decisions and no rerun.

## Decision rule (as in `eval/sameview.md`)

- A pair is **merged automatically** when its effective band (`cluster.effective_band`) is `merged`. This includes a link the pipeline shows as shared footage (`partial`), because claiming shared footage between two different recordings is also wrong.
- A copy is **found** when `cluster.resolve_all` puts it in the same recording as its raw clip.

## Pass bar

1. **0 automatic merges between different recordings** (52 same-place and 368 cross-place negatives), and no recording holding two different recordings. Bar 1 failing is a FAIL whatever else happens.
2. **Every copy of a recording of at least 5 s is found** in its own recording.

## Reported, whatever the result

- For every same-place negative and every positive: duration, aligned score, best-match score, band, verdict, confidence, effective band, `verify_same_event` and the verifier's reason.
- Shared-footage links. Cross-place pairs by band, with the highest aligned score.
- Copies of clips under 5 s, found or not.
- Portrait and landscape counts.
- Verifier cost at list prices.
- Which band the same-place negatives land in: `merged` means the matcher alone would have joined them.

## Limits

These are one person's camera roll: 6 places and 15 clips. The groups come from file numbers and creation dates, not from a check of the content. Handheld motion makes the recordings differ more than a braced pair would, so this is easier than `eval/sameview.md` on the picture. It is harder on scale, because the clips are 4K portrait shrunk to 180 px for the cheap judge. That is the setting where the re-film arm's misses were (`eval/report2-refilm.md`). The sound is real and differs between recordings, and the judge hears it. With these few pairs, this checks one failure mode; it does not measure a rate.
