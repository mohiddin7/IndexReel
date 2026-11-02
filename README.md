# IndexReel

IndexReel counts how many separate recordings are behind a set of video posts, and shows the matching frames for every link it makes, so you can see for yourself which posts share footage.

## What it does

When something happens, the same footage spreads fast. People re-upload it, crop it, mirror it, film it off a TV or laptop with their phone, or cut several videos into one. Ten posts can come from one camera and still look like ten witnesses.

You give IndexReel the clips, or links to public X posts. It groups them by the recording they came from and shows, for each match, frames from both clips side by side at the same moment, so you can check the match yourself. You can split any match you disagree with, and every decision is logged.

It also reads each post's caption and suggests the claims the post makes about its footage, such as the place, the date and what happens, each with the exact caption words it came from. You approve or reject each claim. If one recording later turns out to be old or from somewhere else, you withdraw it, and IndexReel lists which approved claims are left with no video behind them.

For each recording it can also search YouTube and the web for earlier uploads of the same footage. When it confirms one, the page shows where and when that copy was posted, with matching frames, next to the claims made today. The searches are written from what the footage shows. When the X account is asked about a post, a place named in its caption can add two more searches (in English and the place's main language), but it never decides a match, because the claim may be the part that is wrong.

On X, you can tag @askIndexReel under a post with a video and ask whether it is new. It runs the earlier-copy search on that one video and replies with the earliest matching upload it could confirm, with its link and the frames side by side, or says it found none among the videos it checked. A reply is posted on its own only when both checks agree; anything else waits for me to review. Access is limited to a list of accounts, because the budget is small.

## You make the call

IndexReel puts the evidence in front of you and leaves the judgement to you. Every link comes with the frames that made it, every uncertain pair is marked as uncertain, and every decision you make is logged with the run. A claim that keeps its video support after a withdrawal still has footage behind it; whether the claim is right is still yours to decide.

## A real example

I made seven X posts from public-domain USGS videos of the 2018 Kīlauea eruption and one clip I filmed myself on Meta glasses at an airshow. They include an unedited upload, a cropped and mirrored copy, a phone re-film of my monitor, and a compilation cut from two different USGS recordings.

IndexReel first found 3 recordings. It suggested that post 5 is a compilation (seconds 0 to 7 from one recording, 7 to 14 from another). After I confirmed that on the page, the count became 4 recordings plus 1 compilation, which matches how I made the posts. Two of the posts open with the same USGS logo card and then show different lava; the evidence images make that visible, and Muse Spark judged them different recordings. Checking the uncertain pairs with Muse Spark cost $0.29.

From the seven captions, `indexreel claims` suggested 14 claims and quoted every one correctly from its caption ($0.012). Two of them described the post rather than the footage (for example "the video has no audio"), which is the kind of row the approval step is there to reject.

This is one case I built. The measured rates are in Results below.

## How far to trust it

Every test below was written down, with its pass bar, and committed before it was run, and failed tests are reported as failed. The main held-out test failed the first time (2 wrong joins out of 1,080 pairs that should stay apart), I fixed the two causes, and it passed on fresh clips (0 of 1,080).

---

The rest of this page is for developers and researchers.

## Built with Meta

| Meta model or tool | What it does in IndexReel | How it did in my tests |
|---|---|---|
| SSCD (Meta AI's copy-detection model, `sscd_disc_mixup`) | Turns every frame, and its mirror image, into a vector. All matching is built on it. | Ranked the true original first on 96/96 real phone re-films; 0/1,080 wrong joins in held-out run 2. It also scores two takes of the same view as copies, so nothing is decided on it alone. |
| Muse Spark | Checks uncertain and merged pairs; writes the searches for earlier uploads from the frames; suggests caption claims; on X, reads what a person asks and declines political topics. | Same footage in both orders on 14/14 edited copies, 0/42 non-copies called same. One cheap call took two takes of one view for one recording. |
| Muse Spark Open (open weights) | The same check run on my own GPU, to see whether open weights hold up. | Its own original called same on 91/96 re-films; 0 false "same" in 1,440 other pairs. |
| Muse Voice Transcribe | On X, when a caption names no place, a place said in the video can add searches. | Of 41 test clips, one had speech naming a place its caption lacked. |
| Ray-Ban Meta glasses | The second camera for my own test footage: the airshow clip in the example and the two-camera same-moment tests. | |
| Meta's Video Similarity Challenge (VSC 2022) | The idea behind the time check: a copy shows up as one straight line in a frame-by-frame similarity grid. | |
| PDQ (Meta's perceptual image hash) | A comparison only. | Ranked the true original first on 67/96 re-films, against SSCD's 96/96. |
| vPDQ and TMK+PDQF (Meta's video hashes, from ThreatExchange) | A comparison only. | On the 96 real re-films, TMK ranked the true original first on 80 and vPDQ matched none at its own threshold. Both find WhatsApp copies of the same file, as PDQ already does, and neither separates two takes of one view from a copy. |
| SAM 3.1 | Tested as the screen finder. Not used. | Lost the first test 1/4 to OpenCV's 4/4 on simulated re-films. A later check found most of that came from my prompt word ("screen" found 3 of 8 screens, "television screen" 6 of 8) and from scoring with PDQ; with both fixed it reached 3/4, still behind OpenCV. |
| Muse Wonder | Tried as the judge for the hardest pairs. Not used. | Found 10 of 12 hard true copies against Spark's 9, but called 2 of 12 pairs of different takes the same recording, at about five times the cost. |

## Choices, and what each one costs

I measured each choice against at least one alternative, either in the results above or in a check I ran after a test.

| Choice | What I gave up | Why |
|---|---|---|
| Match with SSCD, not PDQ | Nothing measurable | 96/96 against 67/96 on real re-films. |
| Never decide a match on SSCD's score alone | Every merged pair costs a Spark call | SSCD merged 24 same-place pairs of different recordings, and all 8 same-view pairs. Verify split every one. |
| OpenCV to find a filmed screen, not SAM 3.1 | SAM caught one inset that OpenCV missed | OpenCV 4/4 on re-films; SAM 3/4 even with the prompt and scoring fixed after the fact. |
| Muse Spark as judge, not Muse Wonder | One portrait re-film Wonder finds and Spark misses | Wonder called 2 of 12 different-take pairs the same; a false "same" is a false public statement. |
| Post on X on its own only when Spark and the geometric check both say same | Some true copies wait for a person: on trace v3, 1 of 6 | Each check was fooled where the other was not: Spark by two pans of one view, the geometric check by one same-view pair that Spark refused. The geometric check also read 3 true copies as different, so it can only allow a post, never block a match. |
| A re-ask counts a yes in either order | Nothing measurable | Requiring both orders would have lost 4 true pairs of 68 and stopped no false one. |
| Search from what the footage shows; a caption's place only adds searches, on X only | Some originals a caption could point to | On the red-sky post a Hindi search built from the caption's place found an upload from the day before. On the trace cases the same hint pushed one true source from 8th to 18th place, so trace leaves it off. |
| 10 candidates fetched per recording, not 20 | Nothing measurable | 15 or 20 found no extra source on 32 cases, at about 40 s per extra candidate. |
| No search of Instagram or Facebook through web search | 3 of 4 v3 misses were Facebook or Instagram posts | A prompt aimed at them reached 9 sources of 20 against 10 without it, for $1. |
| Evidence frames from inside the matching stretch, not the sharpest frames nearby | A short match can show three similar frames | Every wrong statement in the trace tests was an evidence image that did not show the link: frames from outside the matching stretch, or a mirror guessed wrong. Frames now come from inside the stretch, and the mirror is decided from the pixels. |
| Same moment from sound, with checks that the lag is unique | A copied soundtrack fools it | A brightness-over-time picture check never agreed across cameras facing different ways; a repeating beep makes a sound-only rule claim 8 false matches. On the same takes the uniqueness checks refuse it (development data; the fresh test was not run). |

## What it costs

Most of the choices above come down to money. Prices are list prices.

### Per check

| Step | Cost | Time |
|---|---|---|
| Matching (SSCD, the time line, the geometric check) | $0, on a laptop CPU | the geometric check takes 10 to 25 s per confirmed copy |
| Muse Spark, one batch of up to 4 pairs at 180 px | about 1 to 2 cents | seconds |
| Muse Spark re-ask at 360 px, both orders | about 8 cents | |
| Muse Wonder, one hard pair | about 10 cents, five times Spark | about 30 s |
| Muse Voice Transcribe | $0.18 per hour of speech; a free loudness check skips silent clips | |
| SAM 3.1 through the Meta Model API | $0.20 per 1,000 frames | |
| YouTube Data API search | free, but 100 searches a day; a check uses 3, or 5 with a caption's place | |

### Per answer on X

| | Cost |
|---|---|
| Muse Spark for one video (reading the question, the topic check, the searches, verify) | about 12 cents on my three tags |
| X, a reply with a link | $0.20 at the pay-per-use price I was given; not yet checked against a bill |
| X, a reply without a link ("none found") | 1 cent |
| Time from tag to queued reply | 12 to 18 minutes |

One answered tag comes to about 30 cents. The daily caps (25 checks, 3 per person, $5 of Spark, $5 of X) keep a bad day under about $10.

### Per test

Each test had a spending cap, written down before it ran.

| Test | Spend |
|---|---|
| held-out run 2 verify | $0.17 |
| real re-films | $0.47 |
| same place | $0.90 |
| same view | $0.06 |
| same moment | $0.87 |
| trace v1, v2, v3 | $1.16, $1.97, $1.06 |

Trace v2's $2 cap ran out before its last recordings were searched, which is why v3 and v4 have $3.

## Quickstart

Python 3.12.

```
git clone https://github.com/mohiddin7/indexreel && cd indexreel
pip install -e .                                     # also needs yt-dlp on PATH for fetch
# SSCD weights: sscd_disc_mixup.torchscript.pt from facebookresearch/sscd-copy-detection, into data/models/
indexreel fetch --out clips/ <post-url>...           # public x.com posts; keeps account, time and caption beside each clip
indexreel match clips/ --out run/                    # groups, scores and evidence images
MODEL_API_KEY=... indexreel verify run/ --max-usd 1  # Muse Spark checks uncertain and merged pairs (paid)
MODEL_API_KEY=... indexreel claims run/              # Muse Spark suggests caption claims (paid, default cap $0.10)
MODEL_API_KEY=... indexreel trace run/               # earlier uploads of each recording on the web (paid, default cap $1)
indexreel wall run/                                  # local page: groups, evidence, approve or split, claims, withdraw
indexreel wall run/ --export site/                   # read-only static copy that opens from a file
indexreel withdraw run/ --claims run/claims.csv --recording r2   # the withdraw lists in the terminal
indexreel wall --workdir runs/                       # local form: paste post links or choose files, then run everything
```

The local pages listen on 127.0.0.1 only. The new-run form takes only https post links on x.com or twitter.com and never asks for the model key; `verify`, `claims` and `trace` read `MODEL_API_KEY` from the environment that started them. Answers are cached, so a rerun of the same request costs nothing. The run directory format, including `claims.csv`, `trace.csv` and `audit.jsonl`, is in `eval/run-format.md`.

## How it works

1. **Find the picture.** An OpenCV quadrilateral finder looks for a filmed screen or a picture-in-picture inset in frames sampled at 5 fps and crops to it. A frame with no accepted quadrilateral is used whole. Its cut-off (theta 0.9) was set on development clips only. It matters for insets and for re-films that show the screen's edge. On real footage it rarely fires: on the 48 clips of the real re-film run it accepted a quadrilateral in only 4 clips, because those clips were filmed tight with no edge to find, so that result comes from SSCD on whole frames.
2. **Embed and align.** One frame per second, and its mirror image, goes through Meta's SSCD copy-detection model (`sscd_disc_mixup`), which turns a frame into a vector. Every pair of clips gets a best-match score and an aligned score: the highest mean cosine similarity along one constant time offset, which also gives the stretch of each clip that matches.
3. **Band each pair.** `merged` if the aligned score is at least 0.55 (the highest development negative, 0.537, plus 0.01). `apart` if the aligned score is below 0.20 and the best-match score is below 0.55. Everything else is `unresolved`, including pairs whose frames look alike but do not line up in time. The bands decide which check a pair gets, not whether it is the same recording: `merged` means "close enough to be checked as a copy", and the matcher alone joined 24 same-place pairs of different recordings, which verify then split.
4. **Verify (optional, paid).** Muse Spark sees every unresolved pair and re-checks every merged pair: one anchor clip and up to four candidates per request, 180 px, minimal reasoning effort. An unresolved pair it calls the same recording becomes merged, and one it calls different becomes apart. A merged pair it does not confirm goes back to unresolved for a person. A pair is re-asked at 360 px in both orders when its answers conflict, when Spark says same but the two clips' sound clearly does not match, and before a link is shown as shared footage. Sound never sets a verdict on its own.
5. **Group.** Recordings are the connected components of the merged pairs. Merging is not transitive, so an `apart` pair inside a recording is kept and shown as a conflict. A clip whose merged links cover different stretches from two recordings is suggested as a compilation, and joins nothing until a person confirms or dismisses it. A merged link that covers only part of both clips is recorded as shared footage instead of joining the recordings (experimental, see below).
6. **Claims (optional, paid).** Muse Spark reads every caption in one request and lists the claims about the footage, grouping the same claim across posts. Code drops any claim whose quote is not an exact substring of its caption. Every row starts as `suggested`.
7. **Earlier copies (optional, paid).** For each recording, Muse Spark looks at the clip and writes searches from what it shows; one search runs on the web, told to avoid fact-checking sites, and others on YouTube through yt-dlp, including the likely source's own channel. Candidates are fetched at low resolution, long ones are first scanned at one frame every 4 s, and each is matched against the recording with the steps above. A copy counts only when it is merged and verified, and the earliest one the platform dates before the claimed date is shown. Each confirmed copy then gets a geometric check: local features line the two videos up (mirror, crop, scale), and the moving detail must line up over time along one straight line, which gives the speed and the offset. A copy is marked automatic only when Muse Spark and the geometric check both say same; otherwise the page says "check it yourself". The geometric check never overrules a match it cannot confirm: in an exploratory check on the trace v3 pairs it read 3 true copies as different. Every page the web search returns is logged.
8. **Decide.** On the page a person approves or splits a pair, confirms or dismisses a compilation, and approves or rejects each claim. Every decision is appended to `audit.jsonl`, and recordings are recomputed from the pairs plus the audit.
9. **Withdraw.** For one recording, each approved claim that cites it is listed as lost (every cited clip is in that recording), still cited by footage from another recording (not checked to show the same event), with how that recording's links were made, or undecided (the other clips are tied to it by an unresolved pair). For a compilation, the page says which seconds of it come from the withdrawn recording.

SAM 3.1 was tested as the localiser and is not used (see the first row below). PDQ, Meta's perceptual image hash, is used only as a comparison.

## Results

Every protocol was committed before its run. Intervals are Wilson 95%. Copies are simulated or filmed by me unless the row says otherwise.

| Question | Result | n | File |
|---|---|---|---|
| Does SAM 3.1 beat an OpenCV localiser on picture-in-picture and simulated re-film? | **FAIL.** SAM 4/4 on PiP, 1/4 on re-film; OpenCV 3/4 and 4/4; 0 false merges either way. SAM returned no screen mask on 3 of 4 re-films. | 4 targets per transform | `eval/gate-result.md` |
| Development bands at 0.55 and 0.20 | Positives: 20 merged, 4 unresolved, 0 apart. Negatives: 0 merged, 7 unresolved, 245 apart. The 4 unmerged positives are one dark night-city recording where the localiser found no screen. The floor was lowered after seeing these, so they are not independent. | 24 positive, 252 negative pairs | `eval/match-thresholds.md` |
| Held-out run 1 | **FAIL.** 48/48 positives joined, but 2 of 1,080 negative pairs joined. Fixes: verify every merged pair, and re-ask conflicts at full resolution. | 48 + 1,080 pairs, 16 recordings | `eval/report.md` |
| Held-out run 2, fresh clips, fixed pipeline | **PASS.** 48/48 positives joined (0.93 to 1.00); 0/1,080 negatives joined (0 to 0.0035); 16 of 16 recordings found; verify cost $0.17. | 48 + 1,080 pairs, 16 recordings | `eval/report2.md` |
| Held-out run 2, real phone re-films sent through WhatsApp | **PASS.** 0/1,080 negatives joined (upper bound 0.35%); own original found for 27/32 re-films (0.68 to 0.93; bar 75%): landscape 16/16, portrait 11/16. All 5 misses are portrait, where the verifier called a true pair different or abstained. A crash on a cut-off verifier answer was fixed and recorded as an addendum before the rerun. Verify cost $0.47. | 32 re-films of 16 originals, handheld, no bezel | `eval/report2-refilm.md` |
| Same place, different recordings: my own handheld camera-roll clips, minutes apart | **FAIL.** 4 of 420 negative pairs joined automatically, all from one pair of consecutive handheld pans of one view, which the verifier called the same recording in one cheap call. The matcher alone joined 24 same-place pairs; re-checking merged pairs with the verifier split all 24. 14/14 WhatsApp copies found. Verify cost $0.90. | 15 recordings in 6 places, 15 WhatsApp copies | `eval/sameplace-result.md` |
| Same view, filmed twice from a resting phone: the hardest same-place case | **PASS.** 0/24 automatic merges between different recordings (same view 0/8). The matcher alone merged all 8 same-view pairs (aligned 0.82 to 0.96); the verifier split all 8. 4/4 WhatsApp copies found. Verify cost $0.06. | 2 views, 2 takes each, plus WhatsApp copies | `eval/sameview-result.md` |
| Same moment, two cameras (iPhone and Ray-Ban Meta glasses filming together), by sound and picture | **FAIL.** 0/103 false "same moment" claims, but 0 of 5 same-moment pairs found: the sound lag was right on 4 of 5, the picture lag never agreed. The vision model called a lookalike street the same place on 3 of 4. A sound-only rule would have claimed 8 negatives, because of a crossing's repeating beep. The page shows it only as exploratory. Cost $0.87. | 5 takes, 103 negatives | `eval/samemoment-result.md` |
| Earlier copies on the web (`indexreel trace`): debunked viral clips whose earlier original is documented by a fact-check | **FAIL** on finding, PASS on accuracy. 0 wrong statements: every earlier copy shown was confirmed the same recording by a blind reviewer, and none of 4 true-claim controls got one. Found 2 of 13 edited copies (0.04 to 0.42) and 0 of 2 real re-uploads. In 11 of 12 cases the original never reached the candidate list: search, not matching, is the limit. Cost $1.16. | 15 cases, 4 controls | `eval/trace-result.md` |
| Earlier copies, v2: new cases, YouTube Data API search before the claimed date | **FAIL.** 4 wrong statements: of 25 earlier confirmed copies, the blind reviewer could not tell 4 were the same recording from the evidence image (none judged different; no control got a copy). Found 1 of 1 real re-upload and 2 of 10 of my copies (needs 4). The Data API quota and the $2 cap ran out mid-run, so most later misses were not searched in full. Cost $1.97. | 11 cases, 4 controls | `eval/trace-v2-result.md` |
| Earlier copies, v3: fresh cases, evidence from the matching stretch, run alone on a fresh quota day | **FAIL.** 1 wrong statement: the confirmed copy for n13 is the very upload my clip was cut from, slowed, but the evidence image's three moments did not show the same shot. Found 0 of 1 real re-upload (its Facebook source never became a candidate) and 2 of 9 of my copies (needs 4). Nothing on any control. Cost $1.06. | 10 cases, 4 controls | `eval/trace-v3-result.md` |
| Earlier copies, v4: fresh cases, with a geometric check meant to rescue copies the matcher kept apart | **FAIL.** 0 wrong statements: every earlier copy shown was confirmed the same recording by a blind reviewer. Found 0 of 1 real re-upload and 2 of 9 of my copies (needs 4). Nothing on any control. The geometric check didn't run in this test because of a fault in how I set it up, so the rescue and the evidence image drawn on its line are still untested. Cost $1.36. | 10 cases, 4 controls | `eval/trace-v4-result.md` |
| Earlier copies, v5: fresh cases, with the geometric check running this time | **FAIL.** 2 wrong statements: of 12 earlier copies trace confirmed, the blind reviewer could not tell 2 were the same recording from the evidence image (each a small inset in a news video or graphic; neither was the copy shown; none judged different). Found 0 of 1 real re-upload and 1 of 9 of my copies (needs 4). Nothing on any control. The geometric check ran on every pair: its rescue tried 24 candidates the matcher kept apart and confirmed none, and one of the 5 copies marked automatic (Muse Spark and the geometric check both said same) was one of the 2 wrong statements. The run was interrupted once and resumed on the same cache. Cost $1.63. | 10 cases, 4 controls | `eval/trace-v5-result.md` |
| SSCD vs PDQ on real phone re-films of a monitor | SSCD ranks the true original first on 96/96 clips (own-original score 0.480 to 0.727, highest wrong 0.289); PDQ on 67/96 with median margin 0. This is ranking, not grouping accuracy. | 96 clips of 16 recordings, one phone, one room | `eval/refilm-h5-result.md` |
| Muse Spark Open as judge on the 96 re-films against all 16 originals | Own original called same: 91/96 at 180 px, 92/96 at 360 px. False "same" on 1,440 other pairs: 0 (upper bound 0.27%). The misses are dark static scenes and an empty sky, where it answers "unsure". | 96 clips, far from independent | `eval/refilm-h5-result.md` |
| Spark on edited copies, burned-in text masked | Same footage in both orders on 14/14 copies; 0/42 non-copy pairs called same. It never confirms that two cameras saw one event ("unsure" on 48/48 hard negatives). | 56 pairs, 12 source clips | `eval/spark-pilot3-result.md` |
| Sound as a second channel | 17/17 WhatsApp round trips above the threshold; highest negative 0.0066 against lowest positive 0.105. Missed speed-changed copies. | 57 clips | `eval/audio-h2-result.md` |
| Compilation rule | **FAIL** (2 of 4 bars). 19/24 compilations flagged with their own sources; 0/16 controls flagged. All failures involve one dark look-alike pair of night-city recordings: approving one unflagged compilation joined them. Shipped as a suggestion a person confirms. | 24 compilations, 16 controls | `eval/compilation-result.md` |
| Partial-copy rule | **FAIL** on detection: 11 of 16 partial copies flagged (0.44 to 0.86) against a bar of 80%. The other four bars pass (no demoted controls, no wrong statements). Shipped as experimental. | 16 partial copies | `eval/partial-result.md` |

## Related work

Most video copy detection is tested on simulated copies: a script warps, crops or overlays a clean source. TRECVID's camcording transformation, MUSCLE-VCD and VSC 2023 work this way, and VSC 2023 describes its screen re-recording as a perspective transform with shake [1, 2, 3]. VCDB contains real copies, 18% of them camcorded, but does not report results by that type [4]. I did not find a published comparison of a hash and a learned descriptor on real phone re-films of screens; the 96-clip row above is that comparison for one phone and one room. Pairwise detection of compilations is well covered [3, 5, 6]. I did not find a benchmark that scores what a compilation does to the grouping once its links are approved, so the compilation test above measures that.

## What was built before and during the event

I built IndexReel during the Meta Global AI Developer Hackathon (Oct 26 to Nov 4, 2026, Indie track). Before the event I did private research and one small synthetic copy-detection experiment on Oct 22; none of that code or data is in this repository. Everything here was committed after the `pre-window` tag (Oct 25), and `git log pre-window..HEAD` lists it. The commit messages and the dated `eval/` files record what was planned before each run and what changed after.

## Data and licences

The code is under the Apache License 2.0 (`LICENSE`). Test footage is my own phone recordings, public-domain USGS clips and clips whose licences are recorded in the fixtures. No third-party broadcast video is stored in or served from this repository, and cases from fact-checks are cited by link only. SSCD, PDQ and SAM are Meta's open releases under their own licences.

## References

1. George Awad, Paul Over, Wessel Kraaij. Content-Based Video Copy Detection Benchmarking at TRECVID. ACM Transactions on Information Systems 32(3), 1–40, 2014. https://doi.org/10.1145/2629531 (transformation T1, camcording, "simulated filming a movie on a screen" at different random angles; three angles in the 2008 transformation list, https://www-nlpir.nist.gov/projects/tv2008/final.cbcd.video.transformations.pdf).
2. Julien Law-To, Li Chen, Alexis Joly, Ivan Laptev, Olivier Buisson, Valerie Gouet-Brunet, Nozha Boujemaa, Fred Stentiford. Video Copy Detection: a Comparative Study. Proceedings of the 6th ACM International Conference on Image and Video Retrieval (CIVR 2007), 371–378. https://doi.org/10.1145/1282280.1282336 (its benchmark inserts randomly extracted, synthetically transformed segments into other video; the MUSCLE-VCD-2007 corpus of the CIVR 2007 showcase is described at https://www-rocq.inria.fr/imedia/civr-bench/data.html, which did not load when checked).
3. Ed Pizzi, Giorgos Kordopatis-Zilos, Hiral Patel, Gheorghe Postelnicu, Sugosh Nagavara Ravindra, Akshay Gupta, Symeon Papadopoulos, Giorgos Tolias, Matthijs Douze. The 2023 Video Similarity Dataset and Challenge. Computer Vision and Image Understanding 243, 103997, 2024. https://doi.org/10.1016/j.cviu.2024.103997; preprint arXiv:2306.09489.
4. Yu-Gang Jiang, Yudong Jiang, Jiajun Wang. VCDB: A Large-Scale Database for Partial Copy Detection in Videos. ECCV 2014, Lecture Notes in Computer Science 8692, 357–371. https://doi.org/10.1007/978-3-319-10593-2_24
5. Sifeng He, Xudong Yang, Chen Jiang, et al. (16 authors, Ant Group). A Large-scale Comprehensive Dataset and Copy-overlap Aware Evaluation Protocol for Segment-level Video Copy Detection. CVPR 2022, 21054–21063. https://doi.org/10.1109/CVPR52688.2022.02041; arXiv:2203.02654.
6. Lexing Xie, Apostol Natsev, Xuming He, John R. Kender, Matthew Hill, John R. Smith. Tracking Large-Scale Video Remix in Real-World Events. IEEE Transactions on Multimedia 15(6), 1244–1254, 2013. https://doi.org/10.1109/TMM.2013.2264929
