# Same view, filmed twice: result (Oct 30 2026)

Protocol: `eval/sameview.md`, with Amendments 1 to 5 and Clarification 5a, all committed before any run on these clips (the last is `898fc7a`). Code: a detached checkout of `8c05314` with the reader fix `8272c1a` applied by `git apply` and nothing else (Amendment 5). Scorer: `scripts/sameview.py` from the same checkout, with no `--min-s`. The data is 2 static views, each filmed twice by me with the phone resting, cut to 20 s by one fixed rule, and a WhatsApp round-trip copy of each cut: 8 clips, 28 pairs. Run once, on Oct 30 from 23:08:35 to 23:11:02 UTC, with empty match and verify caches and no human decisions.

## Verdict: PASS

| | result | bar |
|---|---|---|
| 1 Automatic merges between different recordings | **0 / 24** negatives (same-view **0 / 8**, cross-view 0 / 16); no recording holds two recordings | 0 |
| 2 WhatsApp copies found in their own recording | **4 / 4** | all |
| Recordings found | 4 (truth 4), all 4 with status `unresolved` | reported |
| Matcher alone: same-view negatives in `merged` | **8 / 8** (aligned 0.906 to 0.956 for `viewa`, 0.816 to 0.848 for `viewb`) | reported |
| Cross-view pairs | 16 / 16 `apart`, highest aligned 0.153 | reported |
| Verifier cost | $0.0597 at list prices: 6 cheap calls, no pair re-asked | reported |

## Every same-view negative and positive

| kind | pair | aligned | score | matcher band | verdict, confidence | effective band | sound |
|---|---|---|---|---|---|---|---|
| positive | viewa_1 ~ viewa_1_whatsapp | 0.939 | 0.940 | merged | same, 1.00 | merged | matches (0.337) |
| positive | viewa_2 ~ viewa_2_whatsapp | 0.941 | 0.944 | merged | same, 1.00 | merged | matches (0.266) |
| positive | viewb_1 ~ viewb_1_whatsapp | 0.969 | 0.969 | merged | same, 1.00 | merged | matches (0.367) |
| positive | viewb_2 ~ viewb_2_whatsapp | 0.968 | 0.970 | merged | same, 1.00 | merged | matches (0.277) |
| same view | viewa_1 ~ viewa_2 | 0.956 | 0.983 | merged | different, 1.00 | unresolved | differs (0.002) |
| same view | viewa_1 ~ viewa_2_whatsapp | 0.911 | 0.933 | merged | different, 1.00 | unresolved | differs (0.001) |
| same view | viewa_1_whatsapp ~ viewa_2 | 0.906 | 0.931 | merged | different, 1.00 | unresolved | differs (0.001) |
| same view | viewa_1_whatsapp ~ viewa_2_whatsapp | 0.956 | 0.979 | merged | different, 1.00 | unresolved | differs (0.001) |
| same view | viewb_1 ~ viewb_2 | 0.836 | 0.854 | merged | different, 1.00 | unresolved | differs (0.002) |
| same view | viewb_1 ~ viewb_2_whatsapp | 0.829 | 0.849 | merged | different, 1.00 | unresolved | differs (0.001) |
| same view | viewb_1_whatsapp ~ viewb_2 | 0.816 | 0.836 | merged | different, 1.00 | unresolved | differs (0.001) |
| same view | viewb_1_whatsapp ~ viewb_2_whatsapp | 0.848 | 0.865 | merged | different, 1.00 | unresolved | differs (0.002) |

On every positive, the cheap judge said `same` and named moving things in both clips, such as "a single black car passing left to right across the road". On every same-view negative it said `no` and named nothing, because the answer only asks for a detail on a `yes`. The 6 calls covered the 12 pairs once each (one anchor against 1 to 3 candidates per call). No answer was incomplete and no re-ask trigger fired. No link was shown as shared footage (`partial`), and no compilation was suggested.

## What this says

- **The matcher cannot tell two takes of a static view apart.** It put all 8 same-view negatives in `merged`, at aligned scores as high as the positives (`viewa`: 0.906 to 0.956 against 0.939 to 0.941). It aligned the `viewa` takes 8 s apart, on frames of the same still scene. On its own it would have joined each view's two takes into one recording.
- **The verifier caught all 8**, each in one cheap call at 180 px. What changes between the takes is what moves through the view (cars, people) and the light. That is the case where the verifier is needed. Without verifying merged pairs, this set would have had 8 automatic false merges.
- **The page still sends these links to a person.** A `different` on a `merged` pair demotes it to `unresolved`, not to `apart`, so all four recordings show `unresolved` links for review. Nothing is joined automatically, but nothing is called settled either.

## Records

**Cuts** (Amendments 3 and 5): `ffmpeg -ss 2.0 -i <raw> -t 20.0 -map 0:v:0 -map 0:a:0 -c copy`, once per take. `IMG_4217` became `viewa_1.mov`, `IMG_4218` `viewa_2.mov`, `IMG_4250` `viewb_1.mov` and `IMG_4253` `viewb_2.mov`. Every cut has start_time 0, video 20.002 s and audio 20.011 s. Its first decoded frame is source t = 2.000 s, with 2 leading frames from the keyframe at 1.933 s hidden by the edit list. The `viewb` cuts keep the -180 rotation tag; the `viewa` cuts have none.

| file | sha256 |
|---|---|
| raw/viewa_1.mov | 20ac6f50ba24bd26999bc51e4919b1f2d4f11d511af5cbe48fa182d9203d4518 |
| raw/viewa_2.mov | 3b3f48826bebfdb2c21a5963f01845bada580104db6132b1a420ca1940aedd3d |
| raw/viewb_1.mov | f1185bdeceaadb00724f8885c1f1c5286a018c61c774adce4c40ad2f2dbd353c |
| raw/viewb_2.mov | a842c1acecc585dd2ffe0b9cc32ac8fc3a4b3220e254c4fa3d5c4a6d9cba2db0 |
| manifest.csv | e12898cc09a933df5b49d17ba447405b4c7d8e108f12cc1362c3208615ec1aa6 |

The WhatsApp copies are 848x480, 20.013 to 20.033 s long. The `viewb` copies keep the -180 tag (Clarification 5a). Each copy was matched to its cut by duration, rotation tag and frame difference.

**Code checks before the run** (Amendment 5): the source lines changed in the checkout are exactly those of `8272c1a`. `tests/test_rotation.py` passed 2 of 2 there. Both readers decoded every frame of `viewa_1` and `viewa_2` pixel for pixel the same (600 frames each). `run.json` records `git_commit` `8c05314`, because the fix was applied to the working tree, not committed. The changed files' sha256 values are: `cli.py` dbef1f85…, `localise.py` bb4858ac…, `match.py` 83a478c3…, `sscd.py` f91114b2…, `tests/test_rotation.py` 1d6aaf7a…. The SSCD model sha256 is 9f26bd4c….

**Disclosed before the run:** the `viewa` takes are 44 s apart and were longer than asked (Amendment 3). The lower light in `viewb`'s second take makes its negatives a little easier, a bias toward a pass (Amendment 5). I filmed both views and looked at their frames while sorting the files; no match, verify or scoring step had been run on them before this run.

## Limits

8 same-view negatives from 2 views, one phone and one person. With 0 of 8, the 95% Wilson interval for the same-view false-merge rate is 0 to 0.32, and with 0 of 24 negatives it is 0 to 0.14. The 8 answers are not independent. The judge sees one anchor against several candidates in one call, so each view's 4 negatives rest on 2 calls. Things moved through both views, and the judge may have relied on that. A view where nothing moves, a silent pair, or two cameras at one spot are not covered. Run once.
