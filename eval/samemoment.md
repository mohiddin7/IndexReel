# Same moment, different camera: can sound and picture show it, and can the model be asked well?

Written Oct 28 2026, before any clip for this test was filmed. Frozen by the commit that adds it. The rule under test was chosen on dev clips (section "Dev evidence") and is not changed after this commit. The run happens once, after the clips and the manifest exist.

## Why

The pipeline counts distinct recordings. The next question is about two clips that are **not** the same recording: were they filmed at the same moment, by two cameras? Asked as one question ("the same real-world occurrence at overlapping moments"), the verifier mixes three things that need different evidence. **Same place** shows in fixed structures. **Same occasion** (same place and day) shows in light, clocks and specific people or vehicles. **Same moment** shows in transients that both cameras caught. Practitioners who build multi-camera timelines sync by sound first, with picture cues as a check. Published multi-view benchmarks find that vision-language models are weak at cross-view correspondence. So the rule under test measures the moment from sound and picture, measures the place from local-feature geometry, and asks the model narrow questions with checkable details before any answer.

## Questions

1. When two cameras record one scene at once, does the sound-and-picture rule find that they overlap, with the right lag? Does it never claim an overlap for recordings that do not overlap, including the same place at another time, a lookalike place, a swapped soundtrack and shared music?
2. Does local-feature geometry say "same place" for the same place and never for a lookalike place?
3. Does the split prompt get specific, checkable answers from Muse Spark without a false "same moment"?

## Dev evidence (measured before this file; none of these clips is in the test)

Dev clips: 24 of my own clips from other days. 15 are phone clips of six places, 2 to 4 per place, minutes apart. 9 are clips of one airshow, 4 from an iPhone 14 Pro and 5 from Ray-Ban Meta Smart Glasses 2. By their metadata no two overlap in time, so every pair is a null for same moment.

- **Sound and picture envelopes**, as specified below, on the 49 within-place pairs:
  - With the full clip, glasses-glasses pairs peaked at lag 0.00 ± 0.15 s with audio z 8.3 to 14.0. Every glasses clip shares a sound in its first second.
  - With the first 1 s dropped, the highest audio z over the 49 pairs fell to 7.2, and no pair cleared audio z ≥ 8 with agreeing lags.
  - A known overlap (two windows of one 48 s clip, 15 s apart) scored audio z 12.6 and visual z 28.9, both lags +15.00 s.
  - Visual z alone reached 39 on non-overlapping glasses pairs (auto-exposure), so it is not evidence without the lag agreement.
- **Landmark sound fingerprint** (`indexreel.audio.score`): the highest score over the 49 pairs was 0.0063; the known overlap scored 0.148.
- **Local-feature geometry**:
  - The settings first tried (ratio 0.8, RANSAC 4 px) gave up to 136 inliers between different days: repeated stripes and clouds.
  - The strict settings below gave at most 8 between different days, and 18 of 49 same-place pairs cleared that. Sky-only, concert and lawn clips gave none.
- **Muse Spark, four ways of asking**: 12 pairs (7 same place and occasion, 5 different days), 240 px, minimal effort, one pass, $0.41.

  | Way of asking | Same place yes | Same occasion yes | Wrong yes |
  |---|---|---|---|
  | The shipped pair prompt (one same-event question) | not asked | 2 of 7 | 2 ("overlapping moments" for clips minutes apart) |
  | The split prompt below | 6 of 7 | 4 of 7 | 0 |
  | Keyframes plus a drawn feature-match image | 4 of 7 | 4 of 7 | 0 |
  | Blind description of each clip, then a text comparison | 4 of 7 | 3 of 7 | 0 |

  Some of the split prompt's anchors were real but generic ("grassy lawn", "low sun").

These are dev measurements on one person's clips, chosen with the data in view. This test exists to check them on clips that did not exist when they were chosen.

## Shoot (one person, about 90 minutes with the braced same-view takes of `eval/sameview.md`)

**Minimum path first.** The minimum is 9 takes: `street`, `talk`, `park` and `crossing`, each taken twice, plus `street2`. The same-view takes of `eval/sameview.md` (views `viewa` and `viewb`) fit between them on the same loop. Everything else (`indoor`, both takes, and `park2`) is optional and is filmed only if time and light allow.

**People.** Point the cameras away from people. No bystander's face should be recognisable; the only voices recorded on purpose are mine or those of people who agreed to it.

**Devices:** the iPhone (landscape, 1080p at 30 fps, 1x lens, braced on a ledge, bench or stand) and the Meta glasses (worn, default video settings). Sound stays on in both. Nothing is trimmed or edited on either device.

**One take** makes one same-moment pair, about 3 minutes:
1. Brace the iPhone facing the scene and start recording.
2. Walk 5 to 15 m away, to the side, so the two views differ. Start the glasses' recording there, facing the same part of the scene. The start gap is the walk, 5 to 15 s; never start the two together.
3. Stand still and look at the scene for about 30 s. Do not speak, except in `talk` (my own voice, or people who agreed) and `indoor` (the track or my reading). Do not clap or make other deliberate sounds.
4. Walk back and stand 1 to 2 m in front of the iPhone. Clap once, loudly, with your hands in the glasses' view and in the iPhone's frame.
5. Wait 2 s. Stop the glasses, then the iPhone.

The clap gives the true lag. Scoring stops 2 s before it, so the rule never sees it.

**Scenes** (5), each taken twice. Take 2 comes at least 10 and at most 60 minutes after take 1, from the same two spots. Film all take 1s along a loop, then the take 2s on the way back.

| Scene | What makes it | Why it is in |
|---|---|---|
| `street` | traffic passing | ordinary transients |
| `talk` | my own voice (I talk from the glasses' spot), or people who agreed to it; cameras away from other people | speech, no loud events |
| `park` | a quiet park: wind, birds, distant sounds | hard: few transients |
| `crossing` | a signalled pedestrian crossing with beeps | the beep repeats at any time, so take 1 against take 2 tests a periodic sound |
| `indoor` | a room: the track below from the speaker of a phone that is not filming, started from its beginning in both takes; or, without a second phone, me reading aloud | indoors, little picture change; with the track, take 1 against take 2 is the same sound at another time |

**Lookalike places** (2), one take each: `street2`, a different street of the same kind; `park2`, a different park. Each is also a same-moment pair.

**If time runs short**, the optional takes are dropped in this order: `park2`, then the `indoor` take 2, then `indoor`. With the minimum 9 same-moment pairs, bar 2 needs 7 of 9, and the false-claim bound widens (see "What a smaller n costs").

**Files:**
- `data/samemoment/raw/<scene>_t<take>_<device>.<ext>`, with device `iphone` or `glasses`, for example `street_t1_iphone.mov` and `street2_t1_glasses.mp4`. Lookalikes are take 1.
- After the shoot, each raw clip goes through WhatsApp; the downloaded copy is saved as `data/samemoment/whatsapp/<stem>_whatsapp.mp4`.
- **Track:** "In the Hall of the Mountain King" (Grieg), Musopen Symphony Orchestra, public domain on Wikimedia Commons: `https://upload.wikimedia.org/wikipedia/commons/b/bb/Musopen_-_In_the_Hall_Of_The_Mountain_King.ogg`, 154.1 s, sha256 `3bfa7424d3a148f1482a44688b77eb9138a7cea6cff7474799f1329181ab3342`, saved as `data/samemoment/music/Musopen_-_In_the_Hall_Of_The_Mountain_King.ogg`. It is used for the `indoor` scene and for the shared-music control.
- Manifest `data/samemoment/manifest.csv`, columns `file, scene, place_kind, take, device, kind, original, clap_s`:
  - `place_kind` is `street`, `talk`, `park`, `crossing` or `indoor`, so `street2` has `place_kind` `street`;
  - `kind` is `raw`, `whatsapp` or `control`, and `original` is a copy's raw file;
  - `clap_s` is the clap's time in that clip, in seconds.
- `clap_s` comes from `scripts/samemoment.py claps`, which proposes the largest sound onset in the clip's last 8 s. I confirm each by listening before anything is scored; a clip whose clap I cannot confirm is reported and not scored.
- The manifest is written before anything is scored.

## Constructed controls (made by `scripts/samemoment.py controls`, no filming)

The control clips are written to `data/samemoment/controls/` and enter the manifest with kind `control` and the `clap_s` that `controls.csv` gives (for an audio swap, the earlier of its two sources' claps). They are scored only in the 4 pairs below.

- **Audio swap (2):** the picture of `street_t2_iphone` with the sound of `street_t1_iphone`, paired with `street_t1_glasses`; the same for `talk`. The sound matches a moment the picture does not show.
- **Shared music (2):** the track above, with its level set 6 dB below the clip's own sound (by RMS), mixed under two clips that do not overlap. It starts at 0 s under `park_t1_iphone` and at 5 s under `street2_t1_glasses`; the pair is scored. The same is done for `talk_t1_glasses` against `crossing_t2_iphone`.

## Pairs and truth

The counts below are for the full shoot. With the minimum 9 takes: 9 positives; 144 negatives per form, of which 16 are same place at another time and 8 are lookalike pairs.

- **Same-moment positive:** the iPhone clip and the glasses clip of one take: 12 pairs. Truth lag = `clap_s` of the iPhone clip minus `clap_s` of the glasses clip.
- **Negatives:** every other pair of different takes, in raw and in copy-copy form: 264 per form. Of these:
  - same place, other time: 20 (4 per scene);
  - lookalike place: 16 (each lookalike's 2 clips against the 4 clips of its scene);
  - cross-scene: the rest.
- **Controls:** the 4 constructed pairs, all negatives.
- **Excluded:** a raw clip against its own WhatsApp copy (the same recording, not a same-moment pair), and the iPhone-glasses pair of one take in mixed raw-copy form.

## Rule under test (frozen)

**Window:** each clip from 1.0 s after its start to 2.0 s before its `clap_s`.

**Envelopes**, at 100 Hz:
- **Sound:** mono at 8 kHz; STFT with a 256-sample window and an 80-sample hop; log(1 + 100·|X|); positive frame-to-frame difference summed over frequency (spectral flux); minus a 1 s running median, clipped at 0.
- **Picture:** grey frames at 25 fps scaled to 16×9; positive frame-to-frame change of the mean; repeated to 100 Hz; minus a 1 s running median, clipped at 0.

**Cross-correlation:** both envelopes z-normalised; full cross-correlation over all lags.
- The lag is the peak position, as b's start on a's timeline.
- The peak z is (peak − mean) / sd of the correlation more than 2 s from the peak.

**S1, same moment:**
- sound z ≥ 8;
- picture z ≥ 5;
- |sound lag − picture lag| ≤ 0.5 s.

The sound z bar is the smallest integer above the dev null maximum (7.2).

**S2, same moment:** S1, or all of the following:
- the landmark fingerprint (`indexreel.audio.score`) on the windows is ≥ 0.03;
- its best offset (bin of 64 ms) is within 0.5 s of the picture lag;
- picture z ≥ 5.

**P, same place:**
- Features: SIFT with 1,500 features on 5 evenly spaced frames per clip, grey, long side 640 px.
- Matching: ratio test 0.7, mutual nearest neighbours only, homography by MAGSAC at 3 px.
- Score: the best inlier count over the 25 frame pairs.
- "Same place" at 16 inliers or more, twice the dev different-day maximum.

**M, Muse Spark split prompt** (`muse-spark-1.3`):
- Both clips are re-encoded to 240 px on the shorter side with all container metadata dropped.
- Minimal reasoning effort, `max_output_tokens` 4000, one request per pair, asked once.
- The iPhone clip is A where the pair has one; otherwise the manifest order decides.
- An answer cut off or failed counts as no answer.
- The prompt, verbatim:

```
You are shown two short videos, A and B. They may come from different cameras or different moments. Answer with JSON only, no other text. Ignore captions, stickers or titles an editor laid over the picture; signs and text that are part of the scene count.
First list checkable details, then answer. Only list a thing if you can point to it in both videos.
anchors: fixed things visible in both (buildings, skyline shapes, signs with their exact text, distinctive objects), each with its time in A and in B.
transients: specific moving things or sounds present in both (the same vehicle, person, aircraft, performer, a bang or a song), each with its time in A and in B.
contradictions: fixed things or conditions that differ (place, light, weather, season, time of day).
Questions, each answered yes, no or unsure:
same_place: yes only with at least two anchors; no if contradictions show a different place; otherwise unsure.
same_occasion: same place and the same day, within about an hour? yes only if same_place is yes and light, weather and transients agree; no if they contradict; otherwise unsure.
same_moment: do the recordings overlap in time? yes only with at least one transient at matching times; otherwise unsure or no.
Return {"anchors": [{"what": "...", "time_a_s": n, "time_b_s": n}], "transients": [{"what": "...", "time_a_s": n, "time_b_s": n}], "contradictions": ["..."],
"same_place": ..., "same_occasion": ..., "same_moment": ..., "because": "..."}.
```

- M runs on raw clips only, on 64 pairs (49 with the minimum shoot): the 12 positives, the 20 same-place-other-time pairs, the 16 lookalike pairs, the 4 controls, and 12 cross-scene pairs drawn with seed 29.
- Stop at $1.50; expected about $0.60.

**Reported, not under test (S0):** the sound-and-picture rule without the 1 s trim, at sound z ≥ 20, picture z ≥ 12, lags within 10 s. It is the earlier rule that the dev data found too strict for short clips.

## Commands (`scripts/samemoment.py`, at the commit that freezes this file)

1. `claps`: proposes each clip's clap. I confirm each by ear and write the manifest.
2. `controls`: makes the 4 control clips; I add them to the manifest.
3. `score`: S0, S1, S2 and P on every pair; bars 1 to 3 for S1, S2 and P.
4. `spark`: M on its 64 pairs, with a fresh cache, stopping at $1.50; writes the cards.
5. `report`: bar 4 from the marked cards, and the whole verdict.

The pipeline code (`indexreel.audio`, `indexreel.verify`'s Spark client and prices) is taken from the same commit. Nothing is rerun after a result is seen.

## Pass bars

1. **0 false "same moment"** from S1, S2 and M (`same_moment` yes) over all negatives and controls, raw and copy-copy. Report the 95% upper bound. Bar 1 failing is a FAIL whatever else happens.
2. **Same-moment recall:** S1 or S2 finds at least 75% of the raw positives, rounded up (9 of 12; 7 of 9 with the minimum shoot), with the found sound lag within 0.2 s of the truth lag. A pair found with a lag off by more than 0.2 s counts as not found and is reported as a wrong lag.
3. **Same place:** P says "same place" on 0 lookalike pairs (16; 8 with the minimum shoot).
4. **The model's evidence:**
   - M answers `same_place` yes on 0 lookalike pairs.
   - Every anchor and transient behind each M yes becomes a card: the cited text and the two cited frames, with no clip names and no truth (`spark` writes `cards.csv` and the images; the key stays with the scorer). A reviewer other than me, who has not seen the manifest, marks each card `yes` if the cited thing is in both frames and `no` otherwise. At least 90% must be `yes`, and no card may be left unmarked.

## Reported, whatever the result

- Every pair: sound z, picture z, both lags, the truth lag for positives, the S0, S1, S2 and P verdicts, and P's inlier count.
- Null distributions of sound z by device combination (iPhone-iPhone, glasses-glasses, iPhone-glasses).
- Recall on the copies.
- The controls in full.
- M's answers in full, with the generic anchors marked (an anchor that names no scene text and no unusual structure).
- `indexreel match` on all raw clips: whether any same-moment pair is joined as one recording, which it must not be.
- Costs.

## What a smaller n costs

With 12 positives, 9 of 12 is a recall of 0.75 (Wilson 95% interval 0.47 to 0.91). With the minimum shoot, 7 of 9 is 0.78 (0.45 to 0.94). Zero false claims over the 528 negative pairs (raw plus copy-copy) bounds the false-claim rate at about 0.6%. The minimum shoot has 9 takes and 18 clips: 144 negatives per form, 288 in all, so the bound is about 1.0%. Same place on lookalikes has 16 pairs (8 in the minimum), so 0 of 16 bounds that rate only at about 17% (31% for 0 of 8). That bar shows the failure is not common; it cannot show that it is rare.

## Limits

- One person, one iPhone and one pair of glasses. The two cameras are 5 to 15 m apart, so the sound reaches them almost together (at most about 45 ms apart), unlike cameras hundreds of metres from an explosion.
- The person filming walks through both views at the end; scoring stops before the clap, but footsteps before it are in the window.
- No scripted shows, no reused trending sounds beyond the two constructed controls, no long recordings (drift), no edited reposts beyond WhatsApp.
- A pass shows the rule on this kind of footage; it does not make "same moment" a verdict on posts. The product would show the evidence (both envelopes at the found lag, the frames at a shared transient), and a person decides.

## Amendment 1 (Oct 30, before any clip of this test exists: `data/samemoment/raw` holds 0 clips)

- **Change:** in `talk`, I play music from a phone that is not filming instead of speaking. It is the same track as in `indoor`: "In the Hall of the Mountain King", recorded above with sha256 `3bfa7424…3342`. The phone plays `data/samemoment/track/Hall_of_the_Mountain_King_play.m4a` (sha256 `b92c9d9fe4130cafa18bbb470922c8f7a1ad947f2ac617fbc14bf3015de6abe5`). That file is an AAC copy of the recorded track: 154.1 s long, with correlation 0.9994 at lag 0 against it at 8 kHz. The track starts from its beginning in both `talk` takes. This replaces the `talk` rows in step 3 and in the scene table ("my own voice … speech, no loud events").
- **Reason:** this is my choice on the day. With the same music in take 1 and take 2, the two `talk` takes carry the same sound content at different moments. That makes the `talk` same-place, other-time negatives harder (the sound can line up while the moment differs), so it cannot make bar 1 easier. The same holds for `talk` against `indoor`, if `indoor` is filmed.
- **Where the scorer treats `talk` by name:** only in the two constructed controls. The rule, the bars and the pair counts do not name it.
  - **Audio swap:** the `talk_t2_iphone` picture with the `talk_t1_iphone` sound, against `talk_t1_glasses`. It is built as before. The sound now matches the other clip at take 1's moment, while the picture is take 2.
  - **Shared music:** the track mixed under `talk_t1_glasses` at 0 s, against `crossing_t2_iphone` at 5 s. `talk_t1_glasses` now also carries the track from the room, so this negative has more shared music than planned, not less.
  - Both controls stay negatives and are scored as frozen.
- **Not decided by this change:** repeating music can also move the sound peak on the `talk` positive (a beat-period sidelobe). Any effect falls on bar 2's recall, not on false claims. It is reported in the pair table as frozen.
- Nothing else changes: the scorer (`scripts/samemoment.py` at `1bca24b`), the rule, the bars, the prompt and the pairs.

## Amendment 2 (Oct 30 evening, before any claps, manifest or scorer step on the afternoon clips)

**What exists.** Five of the nine minimum takes have both clips and a clap: `street` t1 and t2, `crossing` t1 and t2, and `talk` t1. Missing are `talk` t2, `park` t1 and t2, and `street2`'s glasses clip. `street2`'s iPhone clip exists alone. The optional takes were not filmed.

**The bars apply to the n that exists, as frozen:**
- **Bar 2:** 5 raw positives. The scorer rounds 75% up, so the bar is 4 of 5, with each found lag within 0.2 s of the truth lag.
- **Bar 1:** 0 false claims over 50 raw negatives, 50 copy-copy negatives and 3 controls: 103 in all. WhatsApp copies of all 11 clips are being made; without `street2` the counts are 40, 40 and 3. The scorer reports the 95% upper bound: about 0.029 for 103 negatives and 0.035 for 83. This is weaker than the 0.6% to 1.0% planned. If a copy is missing, only the copy-copy pairs that exist count.
- **Bar 3:** `street2`'s iPhone clip against the 4 `street` clips gives 4 lookalike pairs (0 of 4 bounds the rate only at about 53%). Without it there are no lookalike pairs, and bar 3 and bar 4's first point are reported as not testable, not as passed.
- **Same place, other time:** 8 pairs (`street` and `crossing`, 4 each), against 16 planned. There is none for `talk`.
- **M:** runs on the pairs `spark_pairs` picks from these: 5 positives, 8 other-time, 4 lookalike, 3 controls and 12 cross-scene, so 32 pairs, not 64. The cap is still $1.50.

**The lone clip.** `street2`'s iPhone clip enters the manifest as scene `street2`, place_kind `street`, take 1, device `iphone`. `pairs()` scores a clip with no partner as written: it makes no positive, lookalike pairs against the `street` clips and cross-scene pairs against the rest. Like every clip, it needs a clap I confirm by ear. If I can't confirm one, it is reported and not scored.

**Start gaps.** The glasses started 21.4, 40.6, 17.0, 15.1 and 18.3 s after the iPhone, against the 5 to 15 s planned. The scorer searches every lag: a full cross-correlation of the two windows for sound and for picture, and every offset for the landmark fingerprint. It has no limit that a 40.6 s gap could exceed. `crossing` t1's glasses window (1.0 to 58.7 s) lies inside the iPhone window (1.0 to 99.3 s) at that lag. So no pair is lost to its gap, and none is counted as found because of it.

**Crossing claps.** The iPhone hears the crossing's beep once a second, about as loud as a clap. Footage's candidates for the iPhone claps are off the beep grid: 101.265 s (`crossing` t1) and 57.125 s (`crossing` t2), each agreeing with the metadata gap within its 1 s rounding. `claps` proposes the largest onset in the last 8 s, which may be a beep. I confirm every clap by ear, as frozen. A clap I cannot tell from a beep is reported, and that clip is not scored.

**Controls (scorer change `5ffd361`, committed alone before this amendment).** `controls` built all 4 controls without checking its sources, and three of them now lack one:
- `swap_talk` needs `talk_t2_iphone`.
- The first shared-music pair needs `park_t1_iphone` and `street2_t1_glasses`.

At `5ffd361` it builds only the controls whose source clips are in the manifest with a clap, and prints the ones it skips. In place of `swap_talk` it adds `swap_crossing`, built the same way: the picture of `crossing_t2_iphone` with the sound of `crossing_t1_iphone`, paired with `crossing_t1_glasses`. It restores a planned negative of the same kind, so it can only make bar 1 harder. That gives 3 controls: `swap_street`, `swap_crossing`, and the shared music under `talk_t1_glasses` against `crossing_t2_iphone`. Nothing else in the scorer changes. The selftest now also checks the pair counts of this layout, controls included.

**Disclosed, nothing changes:**
- `talk` t1's track may be barely audible on the iPhone. Footage's rough check found nothing reliable either way, and whether the track started from its beginning in both clips is not known. Amendment 1's reasoning still holds: it can only make the `talk` positive harder to find.
- Before this amendment, footage looked at frame sheets, metadata and sound envelopes of these clips to identify the takes and propose claps. No scorer step (`claps`, `controls`, `score`, `spark`) has run on them, and I have seen no output of the rule on them.
- Five afternoon iPhone clips carry a -180 rotation tag. Every frame the scorer reads comes through ffmpeg, which applies the tag, so S1, S2, P and M are unaffected. The reported `indexreel match` check on all raw clips runs at `8272c1a`, which reads tagged clips upright. The code under test is otherwise as frozen.
