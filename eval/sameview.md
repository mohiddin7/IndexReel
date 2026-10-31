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

## Amendment 1 (Oct 28, before any clip exists: `data/sameview/` holds 0 files)

The verify code in `18a42e4` crashes when a full-fidelity answer ends incomplete (the reasoning uses up `max_output_tokens`). That happened on the re-film arm (`eval/heldout2-refilm.md`, Addendum B). The fix is in `3ff95f6`: an incomplete or failed answer counts as no answer for that order and can never make a pair `same`. So this test now runs on the shipped pipeline at **`66a179b`**, which includes that fix. I change this before any clip exists, not after a crash.

What differs from `18a42e4` in the pipeline, all committed before this amendment:

- **verify:** the incomplete-answer fix (`3ff95f6`); `verify_reason` keeps whole sentences and has no doubled punctuation; a new `verify_same_event` column; a `--backend` option, left at its default `meta`. Prompts, effort, output caps, grouping, escalation and the decision rule are unchanged.
- **matcher and clusters:** a merged pair that covers only part of both clips becomes `partial` (shared footage) instead of joining recordings (`a76f522`, `eval/partial.md`); evidence-image labels; the `claims` command (not used here). Bands, `merge_at` 0.55, `floor` 0.20, theta 0.9 and the SSCD model are unchanged.

The run uses a detached checkout of `66a179b`, with `PYTHONPATH` set to its `src` for match, verify and the scorer, and `--sscd-model` given as an absolute path. The bars and the decision rule do not change. A pair whose effective band is `merged` counts as an automatic merge for bar 1, even if the matcher marks it `partial`, because a shared-footage link between two different recordings is also wrong. The report shows `partial` links separately.

Note only, not tested or tuned here: on the re-film arm, the cheap judge missed portrait re-films by saying `different` or abstaining without naming a detail (`eval/report2-refilm.md`). Nothing in this test depends on that.

## Amendment 2 (Oct 28 night, before any clip exists: `data/sameview/raw` holds 0 files)

**Reason:** the same-place test failed (`eval/sameplace-result.md`). One cheap `same` on two consecutive handheld pans of one view became a shared-footage claim between two different recordings. Nothing re-asked it, even though the two clips' sound did not match. That failure stays a FAIL and that set is not run again. This test now runs on **`8c05314`**, which adds two triggers for the full-fidelity judge:

1. A pair the cheap judge called `same` whose sound is usable on both clips but does not match (`audio.score` below `AUDIO_MATCH` 0.03, the existing threshold between the highest negative 0.0066 and the lowest copy 0.105 in `eval/audio-h2-result.md`).
2. A link that `cluster.resolve_all` would show as shared footage (`partial`).

No new constant is added, and nothing was set on the same-place data. As before, a `yes` in either order of the full-fidelity re-ask is `same`; otherwise the pair is `different` (`no` in both orders) or `abstain`. Prompts, effort, output caps and grouping are unchanged.

Other changes between `66a179b` and `8c05314` in `src/`: a new `trace` command and its entry in the command list (`cli.py`). This test does not use them, and `indexreel match` is unchanged.

Run from a detached checkout of `8c05314`. The commands, bars and decision rule are those of the protocol and Amendment 1.

## Amendment 3 (Oct 30, before any matcher or verify run on these clips)

**Reason:** the morning shoot gave one view, `viewa`, as two takes, `IMG_4217.MOV` and `IMG_4218.MOV` in `data/sameview/raw/`. They break two rules of the Data section. I decided to use them with the changes below rather than film `viewa` again. The footage step has looked at their frames and metadata. No `indexreel match`, verify or scorer run has touched them, and no WhatsApp copy exists yet. These are the only two takes of this view; no take was left out.

**What the clips are**, from their metadata: landscape 1920×1080, H.264 at about 30 fps, with AAC sound and a keyframe every 0.967 s. The phone was resting (not hand-held) in one place for both, as the frames show. Take 1 is 67.1 s long and take 2 is 46.2 s.

**Deviation 1, the gap.** 44 s passed between the end of take 1 and the start of take 2 (111 s start to start), where the rule asks for at least 3 minutes. The two recordings still do not overlap in time. A shorter gap leaves less time for light, traffic and sound to change, so the two takes are more alike. That makes the same-view negative harder for the pipeline, never easier, and cannot make bar 1 pass more easily.

**Deviation 2, the length, and one fixed cut.** The takes are longer than the 15 to 20 s asked for. Each raw take is cut by one rule, the same for both, fixed before any run and not chosen by looking for a segment:

- keep 2.0 s to 22.0 s from the start;
- use stream copy, with no re-encode: `ffmpeg -ss 2.0 -i <raw> -t 20.0 -map 0:v:0 -map 0:a:0 -c copy <out>.mov`;
- with a keyframe every 0.967 s, stream copy starts at the keyframe at 1.933 s. The cut's real start and duration are read with ffprobe and recorded before the run;
- the cuts are saved as `data/sameview/raw/viewa_1.mov` and `viewa_2.mov`, and the full takes and every file that is not part of this test are moved to `data/shoot_oct30_other/`, with a log of the renames.

The WhatsApp copies are made **from the cut files**, one round-trip each, as the protocol asks for every recording. Cutting a full-length WhatsApp copy separately would start at a different keyframe and leave the raw clip and its copy covering slightly different spans.

**Disclosure:** the footage step saw these clips' frames before this rule was fixed. The 2.0 to 22.0 s rule was set without looking at the frames: it is the first 20 s after a 2 s settle, and it is not a window picked for what happens in it.

**`viewb`** is filmed this afternoon to the original rules (a separate take at least 3 minutes later, 15 to 20 s, braced, landscape 1080p at 30 fps) and is not cut.

**What does not change:** the code (a detached checkout of `8c05314`, as Amendment 2 says), the commands, the bars, the decision rule and the manifest columns. `viewa` enters the manifest as takes `1` and `2` with the files above.

## Amendment 4 (Oct 30, before `viewb` is filmed: no `viewb` file exists)

`viewb`'s two takes are separate recordings, each 15 to 20 s, made with the phone resting in one spot. Any gap between them is allowed: stop, then record again. The reason is the same as for Deviation 1 in Amendment 3. A shorter gap makes the two recordings more alike, so the same-view negative gets harder, never easier, and it cannot help bar 1 pass. Nothing else changes.

## Amendment 5 (Oct 30, before `viewb` is cut and before any matcher or verify run on it)

**`viewb`'s takes.** `viewb` is `IMG_4250.MOV` (take 1, started 21:24:44 UTC, 44.6 s) and `IMG_4253.MOV` (take 2, started 21:40:11 UTC, 42.5 s). Take 2 started 15 min 27 s after take 1 and 14 min 42 s after take 1 ended, so the two do not overlap in time. Between them the same phone filmed `IMG_4251` and `IMG_4252`, which are takes of the same-moment test (`eval/samemoment.md`), not of this view. Mohiddin named only `IMG_4250` and `IMG_4253` as `viewb`, and footage's times and frames agree, so no take of this view was left out. Both takes are longer than Amendment 4's 15 to 20 s, so each is cut by Amendment 3's rule, unchanged: 2.0 s to 22.0 s from the start, by stream copy with the same `ffmpeg` command, saved as `data/sameview/raw/viewb_1.mov` and `viewb_2.mov`. Each cut's real start, duration, sha256 and rotation tag are read with `ffprobe` and recorded before the run, and the WhatsApp copies are made from the cut files.

**Was the phone moved between the takes?** Amendment 4 asks for both takes to be filmed with the phone resting in one spot. Two other takes were filmed in between, so the phone may have been picked up and put back. Footage measured this from upright frames of the uncut takes only (`ffmpeg` frames, OpenCV ORB with a RANSAC similarity fit at 3 px; no match, SSCD or verify run):
- between the takes, frames from the same second at 1, 2, 3 and 5 s: translation within 1.1 px of 1920, scale +0.01 to +0.07 %, rotation -0.02 to -0.05 degrees. The 2 s frame of take 1 against take 2 at 8, 12 and 16 s: within 1.1 px, scale -0.15 to +0.02 %, rotation up to -0.08 degrees;
- inside each take, frame 1 against frames at 5, 12, 20, 30 and 38 s: at most 0.5 px in take 1 and 0.9 px in take 2 (scale at most 0.04 % and 0.11 %, rotation at most 0.01 and 0.04 degrees). No hand motion is seen in either.

So the phone rested in both takes, and the framing shift between them is about as large as the drift inside one take. The framing gives the matcher no easier way to tell the takes apart than `viewa` has. What does differ is the light, lower in take 2, filmed about 16 minutes later. Like the gap in Amendment 3, a change between takes makes them less alike, so it makes `viewb`'s same-view negatives somewhat easier to keep apart, a bias toward passing bar 1. The result reports every same-view negative per pair, so each view's negatives can be read on their own.

**Disclosure:** I filmed `viewb` and saw its frames in my first look at the footage (step-1 frame sheets). Nobody who matched or scored the clips had seen them. No `indexreel match`, verify or scorer run has touched them, and no WhatsApp copy exists yet.

**The rotation tag.** Both takes carry a -180 rotation tag: the phone was upside down. At `8c05314`, `match`, `sscd` and `localise` read frames with OpenCV, which ignores the tag, so a raw `viewb` clip comes out upside down while its WhatsApp copy, which has the rotation baked in, comes out upright. Every raw-vs-copy pair of `viewb` would then compare an upside-down picture with an upright one. A same-view negative would come out apart for that reason alone, which would help bar 1 pass. A positive (a raw clip and its own copy) would come out not merged for the same reason, which would make the positive bars fail. Either way, the test would be measuring the reader, not the matcher. `verify` reads frames with `ffmpeg`, which applies the tag, so it is not affected.

**The fix.** The run uses `8c05314` plus matcher's commit `8272c1a` and nothing else. `8272c1a` adds one `match.open_video` that sets `CAP_PROP_ORIENTATION_AUTO` and uses it in `match.sampled_hashes`, `sscd.frames_per_second` and `localise.sample`. It also puts a reader version (`READER = 2`) in `cli.analyse`'s cache key and adds `tests/test_rotation.py`. It changes no threshold, band, prompt or decision logic. In the detached checkout of `8c05314`, the commit's diff (`git diff 8272c1a~1 8272c1a`) applies with `git apply` and no hand-merge; the one hunk in `cli.py` lands one line earlier than in the commit. The sha256 of each changed file in the checkout is recorded in the result, and `tests/test_rotation.py` is run there before the run. The match and verify caches both start empty.

**`viewa` is unchanged.** `viewa_1.mov` and `viewa_2.mov` carry no rotation tag (checked with `ffprobe`). Before the run, every frame of both clips is decoded with the `8c05314` reader and with the patched reader, and the two must be pixel-for-pixel equal. If any frame differs, I stop and write it down here before going on.

**What does not change:** the commands, the bars, the decision rule and the manifest columns.

## Clarification 5a (Oct 30, before any matcher or verify run on these clips)

Amendment 5 says a WhatsApp copy has the rotation baked in and comes out upright. The copies don't. Measured with `ffprobe`, `viewb_1_whatsapp.mp4` and `viewb_2_whatsapp.mp4` (848x480) keep the -180 rotation tag, as their raw cuts do. `viewa_1_whatsapp.mp4` and `viewa_2_whatsapp.mp4` carry no tag, like the `viewa` cuts. So at `8c05314`, a raw `viewb` clip and its own copy would both have been read upside down. The 180 degree mismatch Amendment 5 describes for `viewb`'s raw-vs-copy pairs, and for its same-view negatives, would not have arisen. It would have arisen between the views instead: every `viewb` clip read upside down against every `viewa` clip read upright. That would make the cross-view pairs easier to keep apart, while `verify`, which reads through `ffmpeg`, sees all of them upright. The conclusion is unchanged: the run uses `8c05314` plus `8272c1a`, so every clip is read upright by the matcher and the verifier alike. Nothing else changes.
