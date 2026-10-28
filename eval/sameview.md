# Same view, different recording: does the pipeline keep them apart?

Written Oct 28 2026, before any clip for this test was filmed. Frozen by the commit that adds it. The run happens after the clips and manifest exist, once.

## Why

On real phone re-films, dark footage did not trouble SSCD. The remaining false-merge risk is a pair that shares real static content: two different recordings of the same static view, filmed from the same spot a few minutes apart. On a static scene, a frame descriptor sees the same picture in both. Only things that change over time (cars, people, blinking lights, cloud, sound) can tell the two recordings apart. No dev, gate or held-out set so far has contained such a pair. This test adds them. It does not tune anything.

## Question

When the same static view is recorded twice from the same spot, does the shipped pipeline keep the two recordings apart automatically? Does it still join each recording with its own WhatsApp copy?

## Data

- I film 2 or 3 static views. Each view is recorded twice from the same spot, at least 3 minutes apart, as two separate recordings. Each take is 15 to 20 s, landscape, 1080p at 30 fps, 1x lens, phone braced. The phone's own sound stays in the files.
- The footage step adds a WhatsApp round-trip copy of every recording.
- Layout: `data/sameview/raw/<view>_<take>.mov` and `data/sameview/whatsapp/<view>_<take>_whatsapp.mp4`. The manifest is `data/sameview/manifest.csv` with columns `file, view, take, kind (raw or whatsapp), original, platform`, written before anything is scored.
- **Truth by construction:** a recording is one view and one take, and its WhatsApp copy belongs to it. With V views there are 4V clips and these pair kinds:
  - **positive:** a recording and its own copy. 2 per view.
  - **same-view negative:** the two takes of one view, in any combination of raw and copy. 4 per view.
  - **cross-view negative:** clips of different views.

## Pipeline (frozen)

- Code at `18a42e4`, the shipped pipeline:
  - `indexreel match` (`merge_at` 0.55, `floor` 0.20, theta 0.9, mirrored margin 0.02, SSCD sha256 `9f26bd4c848cc19b73d2ae92eea6e04886f61a7b764ceb7a13aeee62e6a6db56`), one frame per second;
  - `python -m indexreel.verify`, which checks every merged and unresolved pair, re-asks conflicts for at most 2 rounds, and uses sound only to escalate. The judge's prompt asks it to use picture and sound;
  - recordings from `cluster.resolve_all`, in which compilations are suggestions.
- Commands, in order:
  1. `scripts/sameview.py prepare`, which copies every manifest file flat into `data/sameview_in`
  2. `indexreel match data/sameview_in --out data/sameview_run`
  3. `python -m indexreel.verify data/sameview_run --cache data/sameview_verify_cache --max-usd 3`, with a fresh cache
  4. `scripts/sameview.py score`
- No human decisions and no rerun. Nothing is changed after this commit.

## Decision rule

A pair is **merged automatically** when its effective band (`cluster.effective_band`) is `merged`: the matcher merged it and the verifier did not disagree, or the matcher left it unresolved and the verifier said `same`. A WhatsApp copy is **found** when `cluster.resolve_all` puts it in the same recording as its raw file.

## Pass bar

1. **0 automatic merges between different recordings:** none of the same-view negatives (4 per view) and no other negative is merged automatically, and no recording holds two different recordings. Bar 1 failing is a FAIL whatever else happens.
2. **Every WhatsApp copy is found** in its own recording (2V of 2V).

## Reported, whatever the result

- For every same-view negative and every positive: aligned score, best-match score, band, verifier verdict, confidence, effective band and the verifier's reason.
- Cross-view pairs by band, and the highest cross-view aligned score.
- Recordings found against 2V, any compilation suggestion, and the verifier cost at list prices.
- Which band the same-view pairs land in. `merged` means the matcher alone would have joined them. `unresolved` means the verifier decided. `apart` means neither was needed.

## Limits

These are 2 or 3 views, one phone and one person. A static view filmed minutes apart is the easiest form of this risk to film. Two different cameras at one spot, or a webcam stream, are not covered. With so few pairs this is a check of one failure mode, not a rate. Sound differs between takes and the judge may use it, so the result covers the pipeline with sound, as shipped. A silent pair would be harder.
