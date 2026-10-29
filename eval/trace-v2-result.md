# Trace v2 test: result

The protocol is `eval/trace-v2.md` (commit eb40cd1), with Amendment B (f9ad5c1) and Clarification B1 (45b7481). Trace code is at f4b2dfe; the scorer at 1ca1683. The test split was run once, on Oct 29 2026 from 16:27:40 to 18:39:04 UTC, with a new, empty cache. YouTube never asked for a sign-in, so the resume rule was not used. Every row is kept below.

## Read this first: two limits cut the run short

Both limits were pre-registered, and the run went on as the protocol says, so this is the result. But they mean that most misses from n3 on are not search misses.

1. **The YouTube Data API's daily quota ran out** at recording n3 (HTTP 429, RESOURCE_EXHAUSTED). The dev measurements of the same day had used most of it. As pre-registered, that source stopped for the rest of the run.
2. **The $2 cap ran out** from n4 on. Verification cost $1.19 of the $1.97: every one of up to 9 confirmed copies of the same recording was verified on its own (n3 alone $0.67, n2 $0.25, n1 $0.16). So the web search was skipped for n4 to n7, and n8 and n9 got no search at all, not even the queries.

Trace runs the recordings in the order of their ids, so the sources each case actually had were:

| cases | web search | YouTube search (yt-dlp, channel) | YouTube Data API |
|---|---|---|---|
| k1-k4, n1, n10, n11, n2 | yes | yes | yes |
| n3 | yes | yes | no (quota) |
| n4, n5, n6, n7 | no (budget) | yes | no (quota) |
| n8, n9 | no (budget) | no (budget) | no (quota) |

A separate exploratory rerun of n4 to n9, after the quota resets, is reported at the end. It does not count toward the bars.

## Verdict: FAIL

| bar | result | |
|---|---|---|
| 1. No wrong statement (decisive) | **4 wrong statements**: of 25 earlier confirmed copies, the blind reviewer answered `cannot tell` to question (i) for 4 (2 on n1, 2 on n2), and `different` for none; no control showed any confirmed copy | FAIL |
| 2a. Found, real re-uploads | **1 of 1** (n1), Wilson 95% 0.21-1.00. It rests on one case, so it says little | PASS |
| 2b. Found, my copies | **2 of 10** (n2, n3), needs 4, Wilson 95% 0.06-0.51 | FAIL |
| Secondary: found, counting leak-exposed sources | 3 of 11 | |

Trace never showed a copy that the reviewer judged a different recording, and never showed anything on a control. But for 4 copies its own evidence image did not make the link plain, and under Clarification 1 of `eval/trace.md` that is a wrong statement.

## Each test case

"Fetched" counts the candidates downloaded and matched. "Earlier" counts confirmed copies that the platform dates before the claimed date. (i) and (ii) are the blind reviewer's answers for the copy trace showed.

| case | claimed as (claimed date) | input | sources | fetched | earlier | copy shown (posted) | (i) | (ii) | found | why not |
|---|---|---|---|---|---|---|---|---|---|---|
| n1 | Storm Eunice, UK (2022-02-18) | re-upload (Facebook, 2022-02-18) | all | 10 | 5 | YouTube, 2021-11-29 | cannot tell | same | **yes** (another earlier copy got `same` twice) | |
| n2 | Gofa landslide, Ethiopia (2024-07-24) | mine, flip | all | 10 | 9 | YouTube, 2022-06-27 | same | same | **yes** | |
| n3 | Mumbai monsoon (2025-08-19) | mine, slow motion | no Data API | 10 | 9 | YouTube, 2021-05-17 | same | same | **yes** | |
| n4 | Texas floods (2025-07-05) | mine, zoom | YouTube only | 10 | 0 | - | | | no | the named original was never a candidate, with YouTube search alone |
| n5 | Texas floods (2025-07-05) | mine, compilation | YouTube only | 8 | 0 | - | | | no | as n4 |
| n6 | Ragasa tornado (2025-09-24) | mine, flip | YouTube only | 10 | 0 | - | | | no | as n4 |
| n7 | Ragasa elevator shaft (2025-09-24) | mine, slow motion | YouTube only | 10 | 0 | - | | | no | as n4; the original is a Facebook video, which YouTube search cannot reach |
| n8 | Typhoon Shanshan (2024-08-30) | mine, zoom | none | 0 | 0 | - | | | no | no search: budget spent |
| n9 | LA fire tornadoes (2025-01-11) | mine, compilation | none | 0 | 0 | - | | | no | no search: budget spent |
| n10 | Pak Kret road collapse (2025-09-24) | mine, flip | all | 10 | 0 | - | | | no | the original is a TikTok post; it was never a candidate, and no candidate was the recording |
| n11 | Myanmar earthquake (2025-03-29) | mine, slow motion | all | 9 | 2 | YouTube (Newsflare), 2023-05-15 | same | cannot tell | no | two YouTube copies were confirmed (the Facebook original was never a candidate), but the reviewer could not tie their frames to Tabin |

Controls (true claims): k1 (Bangkok sinkhole, 2025-09-24), k2 (Artemis II launch, 2026-04-01), k3 (USGS lava fountain, 2025-12-06) and k4 (my airshow clip, 2026-09-26) each fetched 8 to 10 candidates. None had a confirmed copy, so none showed one. The date filter skipped 70 candidates across the run as dated on or after their claimed date.

## The 4 wrong statements

All four are `cannot tell`, not `different`. I looked at the images after scoring; they explain the answers but do not change them.

- **n2, two copies** (a004, a006): both candidates are tight zooms on part of the slide scar, while my input is a narrow, mirrored frame of the whole slope. The three frame pairs show the same terrain at different scales, which the reviewer could not align.
- **n1, the copy shown** (a018): the first pair is plainly the same street, but the other two pairs are near-featureless storm sky with a small dark object, picked with uneven time gaps (4 s on the input against 1 s on the candidate). The order-preserving choice of frames (Amendment B) kept them in order, but SSCD has little to go on in empty sky, so the chosen moments are not convincing.
- **n1, another copy** (a021): sky only on both sides, and the candidate is a small portrait inset.

So the matcher's decisions may well be right, but the evidence image does not show it. Frames are picked by time inside the core span, without regard to how much they show.

## Corroboration (reported, not scored)

Corroboration marked n1 and n11 `strong` and n2 and n3 `single-source`. n11's date is right: a news report of Sept 19 2022 and a Sabah tourism page both put the eruption at Tabin in September 2022, matching the Facebook original. **n1's is wrong**: the copy shown, captioned "Somewhere in Doncaster", was posted two days after Storm Arwen, and the date search tied it to that storm (a Met Office page and a Scottish government review, 2021-11-27). Full Fact dates the footage to June 2021 in Barking. A date search led by a copy's own caption can agree with that copy's mislabel. In this test, `strong` was not a reliable mark, and a corroborated date should not be shown as the footage's date.

## The blind check

The same separate reviewer as in v1 answered both sheets. As a process improvement over v1, which the protocol's wording allows, the sheets were in separate folders with their own shuffles, row ids and case labels, and the reviewer was given sheet 2 alone first and answered it before seeing any of sheet 1. In v1 the reviewer saw sheet 2's descriptions while judging sheet 1, and sheet 1's pairs before sheet 2.

- Sheet 2 (question ii, 25 rows): 18 `same`, 7 `cannot tell`. The reviewer judged more strictly than in v1: a scene and a date alone gave `cannot tell`, and `same` needed a landmark, a place caption, or a match to a captioned row on the same sheet.
- Sheet 1 (question i, 25 rows): 21 `same`, 4 `cannot tell`. The reviewer notes that sheet 1 is not fully independent of sheet 2, because many candidates appeared on both.
- The reviewer saw no key, ran no trace code and changed no answer after writing it.

## Compared with dev

On v1's own test cases, used as v2's dev set, v2 found 9 of 15, where v1 found 2. On the new test cases, with full search for only 5 of them (n1, n2, n10, n11, and n3 without the Data API), it found 3. That is too little to say whether the dev gain carries over. The exploratory rerun below speaks to n4 to n9.

## Cost

Test run $1.97 (verify $1.19, the rest Spark search, queries and corroboration), claims $0.011. Dev $2.02. v2 in total: about $4.00. Trace in total, v1 and v2: about $7.35 of $10. The Data API and Vision cost nothing (18 Vision requests in all, none in the test).

## Lessons

- **The cap was planned wrong, and the coordinator and I share that.** The coordinator approved a $2 cap, and I proposed it, without asking how verification scales when search finds many copies of one recording. Trace should stop verifying a recording's candidates once it has 2 confirmed earlier copies; the rest add cost, not evidence.
- **The daily API quota is a budget too.** Nobody planned the Data API's daily quota for test day, and the dev measurements of the same morning used most of it. A test run should start on a fresh quota day, or with a quota count kept like the Vision counter.
- **Evidence frames need content, not only order.** Frames should come from moments where the two clips match strongly and show something (not empty sky), and a copy whose image does not show the link plainly should not be shown.
- **Corroboration should not echo a copy's caption.** The date search should look for the footage's origin independently of the copy it is given, or its date should not be shown as the footage's date.

## Exploratory rerun of n4 to n9 (not part of the bars)

Pending. Approved by the coordinator for the next quota day: the same frozen code and the same cache (copied, so this result's files stay as they are), capped at $2. Its numbers will go here, apart from everything above.

## Limits

- 11 test cases; 2a rests on one case.
- Six of the 11 test cases did not get the full search, so bar 2b says little about v2's retrieval.
- Kind (b) inputs are copies I made, not the clips that spread.
- "Same recording" rests on one reviewer's judgement, made more strictly than in v1.
- Search results change from day to day, so a rerun would give different candidates.
- Post times say when a clip was posted, not when it was filmed.
