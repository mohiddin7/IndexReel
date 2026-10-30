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

A separate exploratory rerun of n4 to n9, after the quota resets and on fixed code, is reported at the end. It does not count toward the bars.

## Verdict: FAIL

| bar | result | |
|---|---|---|
| 1. No wrong statement (decisive) | **4 wrong statements**: of 25 earlier confirmed copies, the blind reviewer answered `cannot tell` to question (i) for 4 (2 on n1, 2 on n2), and `different` for none; no control showed any confirmed copy | FAIL |
| 2a. Found, real re-uploads | **1 of 1** (n1), Wilson 95% 0.21-1.00. It rests on one case, so it says little | PASS |
| 2b. Found, my copies | **2 of 10** (n2, n3), needs 4, Wilson 95% 0.06-0.51 | FAIL |
| Secondary: found, counting leak-exposed sources | 3 of 11 | |

Trace never showed a copy that the reviewer judged a different recording, and never showed anything on a control. But for 4 copies its own evidence image did not make the link plain, and under Clarification 1 of `eval/trace.md` that is a wrong statement.

## Correction (Oct 29 2026, after an independent review of trace's code and these run files)

The verdict and every row below stay as first written. An independent reviewer, who did not build trace, read its code and this run's files. What it found changes some counts and the explanations, not the result.

- **Counts.** Trace counted a YouTube video found under two URLs (`/shorts/<id>` and `/watch?v=<id>`) as two candidates. The 25 earlier confirmed copies are 23 distinct videos. n1 fetched 9 distinct videos, not 10, with 4 earlier confirmed copies, not 5; n2 fetched 9, with 8 earlier, not 9. Each such duplicate also took a fetch slot.
- **n2's two `cannot tell` answers** (a004, a006). The explanation above, that the frames were "the same terrain at different scales", misses the main defect. Both candidates are mirror images of my input, but the matcher's `mirrored` flag said they were not. That flag comes from SSCD, which barely tells a frame from its mirror image, and trace drew the evidence image by it. With the orientation found from the pixels, the two sides line up.
- **a018's uneven gaps.** The candidate and the input play at the same speed. The order-keeping frame choice of Amendment B still moved each candidate frame on its own, away from the matcher's offset (28.5, 32.5 and 36.5 s became 28.0, 34.5 and 35.5 s). a021's three frames all came from a core span only 2 s long, which was all sky, while the clips matched over 13 s that included the street.
- **The cost.** The money did not go on verifying every copy as such. It went on verify's full-detail re-ask of links that cover only part of a clip, which nearly every trace pair is: 13 of the 27 verified pairs were re-asked, for $1.06 of the $1.19, and n3 alone took $0.66. The re-ask is not waste: it turned 2 cheap `same` answers into `different` and `abstain`. But verify's reserve ($0.05) was smaller than the web search's ($0.10), so verifying one recording used up the money the later recordings needed for their searches.
- **Bar 1 reading.** The scorer counts every earlier confirmed copy in `trace.csv` as a statement of trace. The page shows only the earliest of them (`shown`). Read the second way, bar 1 has 1 wrong statement (a018, the copy shown for n1), bar 2a is 0 of 1, and bar 2b stays 2 of 10. The run fails either way. I keep the stricter reading, every earlier confirmed copy, and a later protocol should say so in its own words.
- **Two scorer and image bugs that did not affect this run.** The scorer would have accepted a copy on a control that the reviewer judged `same`; bar 1 counts any such copy as wrong. And a candidate whose clip id sorts before `input_` (TikTok, Instagram, Reddit, Facebook) was drawn on the left, so sheet 2 would have shown the input instead of the candidate. No row of this run was hit by either.

The fixes are in trace since this run, one commit each: the scorer (3e6b4b3), the input always on the left (c949556), orientation from the pixels (fd49b8e), one speed ratio or the matcher's offset (4fd3893), frames spread over the cover span with the most detail (cc8578a), matching earliest first and stopping after 2 confirmed earlier copies, with every search run first (9027dd7), one URL per video (754755f), unranked videos last and vanished ones skipped (df3927f), failed date reads not cached (6c951bb), side labels without video ids (828de04) and letterbox bars trimmed before the pre-rank (d792cfb). None of them changes this result. The four images regenerated with them, for the record only, are described in the exploratory section at the end.

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

## After the test (not part of the bars)

### The four `cannot tell` images, drawn again with the fixed code

For the record only: nothing was scored again. Images are in the private run data (`regen/`).
- a018 (n1, the copy shown): the candidate now stays at the matcher's offset (28.5, 32.5, 36.5 s against 0.5, 4.5, 8.5 s), and the first row shows the same street on both sides.
- a021 (n1): the frames now come from the 13 s the clips share, not the 2 s core, and the first row shows the houses instead of sky.
- a004 and a006 (n2): the input is now shown the right way round. But both candidates are tight zooms on part of the slide beside my narrow, full-slope input, so the two sides are still hard to compare by eye. Showing the candidate's matched region at the input's scale would be the next step. None of these fixes does that.

### Exploratory rerun of n4 to n9

Run on Oct 30, 07:08 to 08:03 UTC, the first hour of a fresh Pacific quota day, on the fixed code at d792cfb, on copies of this run's folder and cache (so this result's files stay as they are), capped at $2. It spent $0.73 and made 21 Data API searches (n3 to n9; the other recordings' searches were already cached). No source stopped. It is exploratory: the bars are not scored again, nothing went to the blind reviewer, and "found" below is trace's own count of a shown, confirmed, leak-passing copy dated before the claim.

| case | input | fetched | earlier confirmed | copy shown (posted) | found by trace | note |
|---|---|---|---|---|---|---|
| n4 | mine, zoom | 10 | 0 | - | no | the named original (ViralHog, 2019) was never a candidate |
| n5 | mine, compilation | 9 | 0 | - | no | the named original was never a candidate |
| n6 | mine, flip | 10 | 1 | YouTube, 2023-09-04 | yes | the named original (the edited Short). The unedited 2016 footage came from web search, and verify called it `different` |
| n7 | mine, slow motion | 9 | 2 (then stopped) | YouTube, 2018-09-16 | yes | the Facebook original was never a candidate; the copy shown was posted the same day |
| n8 | mine, zoom | 2 (then stopped) | 2 | YouTube, 2024-05-04 | yes | the named original, found by web search; that source was not leak-exposed for n8 |
| n9 | mine, compilation | 10 | 0 | - | no | the original is a TikTok post; it was never a candidate |

So with every source and the fixed code, trace found 3 of these 6 (n6, n7, n8), where the test found none of them. The other recordings were rerun from cache too: n1 to n3 and n11 still show a copy (n1 the same 2021-11-29 copy as before; n2 and n3 stopped after 2 copies), n10 still has none, and no control has a confirmed copy. Not scored or blind-checked, this says only that the test's failures on n4 to n9 were partly budget and quota, and partly search.

## Limits

- 11 test cases; 2a rests on one case.
- Six of the 11 test cases did not get the full search, so bar 2b says little about v2's retrieval.
- Kind (b) inputs are copies I made, not the clips that spread.
- "Same recording" rests on one reviewer's judgement, made more strictly than in v1.
- Search results change from day to day, so a rerun would give different candidates.
- Post times say when a clip was posted, not when it was filmed.
