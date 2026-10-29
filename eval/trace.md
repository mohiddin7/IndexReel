# Trace: finding earlier uploads of the same recording

Written Oct 28 2026, before any trace code exists and before any clip for this test has been fetched. The commit that adds this file freezes the split, the leak rule and the bars. Amendment A, written after dev work ends and before any test clip is fetched, will freeze the code commit and the constants. The test split is then run once.

## Why

A clip that spreads after a disaster is often older footage. When the same recording was posted before the claimed event, that post settles the timing question: this video cannot show that event. In an earlier exploratory study, an earlier copy contradicted 7 of 11 false claims and never supported one. But most of those copies were found through web pages that were themselves fact-checks, and some dates came from page text instead of the platform. This test measures the search without that shortcut. It also checks that a later upload, or a different recording, is never shown as the earlier copy.

## Question

Given one clip and the date it was claimed to show, does `indexreel trace` find an upload of the same recording that the platform dates before that claimed date? Does it do this without reading fact-check pages, and without ever showing a wrong copy or a wrong date?

## Cases

25 documented cases from 2017 to 2026, each published by AFP, Full Fact or Fact Crescendo, plus controls. Each case is a clip that people believed showed a current event, where the fact-checker named an earlier upload. Topics are natural disasters, weather, accidents, animals, space and sport only. Cases that share a recording or an event stay in the same split.

**Dev** (used to build and tune; may be run any number of times):

| id | claimed as (claimed date) | earlier upload named by the fact-check |
|---|---|---|
| d1 | Artemis II re-entry (2026-04-12) | NASA, "Reentry video as Orion returns from Artemis I", 2022-12-11 |
| d2 | Semeru lava flow (2021-12-05) | USGS Kilauea "firehose flow", Jan 2017 |
| d3 | Anak Krakatau eruption (2026-09-06) | Anak Krakatau night footage, YouTube 2018-11-06 |
| d4 | Hurricane Milton tornadoes (2024-10-10), compilation | Pilger tornado 2014 and Didsbury 2023, the storm chaser's own posts |
| d5 | Hurricane Melissa (2025-10-27), 16-clip compilation | 15 earlier clips, 2018 to 2025 |
| d6 | Cheyenne hail (2025-08-03), 14-clip compilation | 12 earlier clips, 2020 to 2023 |
| d7 | Dubai floods (2024-04-19) | Miyako port tsunami, 2011, YouTube upload 2021-02-25 |
| d8 | Noto earthquake (2024-01-02), compilation | the same Miyako clip, mirrored |
| d9 | Northern Japan earthquake (2026-04-21), compilation | four Noto 2024 recordings |
| d10 | Derna floods (2023-09-13); Nepal floods (2026-08-26), mirrored | Atami mudslide, YouTube 2021-07-03 |

Dev controls: the four genuine Noto clips inside d8.

**Test** (run once, after Amendment A):

| id | claimed as (claimed date) | earlier upload named by the fact-check | fact-check |
|---|---|---|---|
| t1 | Mauna Loa eruption (2022-12-01) | Kilauea Fissure 8, YouTube `BgjpSlzU9oU`, 2018-06-17 | Fact Crescendo, 2022-12-05 |
| t2 | Reykjanes eruption (2023-11-21) | Fagradalsfjall eruption, March 2021 | Full Fact, 2023-11-21 |
| t3 | Hurricane Helene storm surge (2024-09-25) | Hurricane Ian surge probe, YouTube `al8yTiCVfro`, 2022-09-29 | AFP 36H93JN |
| t4 | Dubai storm damage (2024-04-18) | video-game footage, YouTube `qxYlmMEhohU`, 2023-10-21 | AFP 34QW7XG |
| t5 | Taiwan tsunami (2024-04-03) | Tagajo tsunami, YouTube `5gELOQf_pMc`, 2011-03-17, flipped | AFP 34NE34P |
| t6 | Taipei 101 swaying (2024-04-03) | effects clip, TikTok 2022-08-17, since deleted | AFP 34NX6C7 |
| t7 | Turkey earthquake tsunami (2023-02-08) | Durban North Beach, YouTube `bnnoPfZ7_mo`, 2017-03-14 | AFP 338R4E6 |
| t8 | Morocco building collapse (2023-09-11) | Adana demolition, TikTok 2023-02-13, mirrored and slowed | AFP 33VK3L3 |
| t9 | Morocco home shaking (2023-09-09) | Oita, X and Facebook, 2022-01-21 | AFP 33VA4Y3 |
| t10 | Kamchatka earthquake (2025-07-30) | Myanmar shop CCTV, TikTok 2025-03-30 | AFP 68A67WE |
| t11 | LA wildfire rabbit rescue (2025-01-09) | Thomas Fire, YouTube `6uBuxJXlWrQ`, 2017-12-07 | AFP 36TQ2CR |
| t12 | Valencia floods (2024-10-31) | Zaragoza flood, agency report 2023-07-07 | AFP Factual 36LB4LG |
| t13 | Wayanad flooding (2024-07-30) | Meizhou time-lapse, June 2024 | AFP 36CA2W3 |
| t14 | Himlung Himal avalanche (2026-09-27) | Kapuche Lake, Instagram `CJ4osaYhmch`, 2021-01-11 | Fact Crescendo, 2026-09-29 |
| t15 | Qatar World Cup stadium fire (2022-11-23) | Hamburg match, YouTube `YVzNpl2i5sk`, 2018-05-13 | AFP 32TB9F9 |

Test controls (true claims, so no earlier upload exists):

| id | clip (claimed date) | why there is no earlier copy |
|---|---|---|
| c1 | Hurricane Ian street shark, Fort Myers (2022-09-28) | authentic, first posted that morning (Snopes) |
| c2 | Deer running through smoke, Los Angeles (2025-01-09) | genuine, published that day (AFP 36TQ2CR) |
| c3, c4 | two of my own clips, posted on X in October 2026 | I filmed them and posted them once |

## Inputs

For each test case and control, I fetch one input clip with `indexreel fetch`, before the run and without running any part of trace on it. For a test case, the input is, in this order of preference:

- **(a) real re-upload:** a live post of the footage, made on or after the claimed date (the viral post or a later repost), used as fetched;
- **(b) our copy:** if no such post can be fetched, a copy I make from the earlier upload named by the fact-check, with ffmpeg (`scripts/trace_inputs.py`, written during dev). Every copy is re-encoded at 720 px on the long side. A copy is also flipped wherever the fact-check says the viral clip was flipped. On top of that, (b) copies get one of four edits that the cases show are common, assigned in turn in test-id order: **flip**; **slow motion** at half speed; **zoom**, a centre crop to 70% of the width and height, scaled back up; and **compilation segment**, the copy placed between two unrelated public-domain clips from the USGS volcano set.

**Claims, not fact-check wording.** The input's caption is the viral post's own caption, as the fact-check quotes it (its English translation where the fact-check gives one). Nothing written by the fact-checker enters the input. `indexreel claims` extracts the claims from that caption, and I approve or reject each row before the run. Trace searches from the clip and the **approved claims only**. The claimed date is the date in the table.

The kind of each input, (a) or (b), and for (b) its edit, are recorded in `data/trace_test/manifest.csv` before the run. A (b) copy is made from the very file the search should find, and its edits are simpler than real viral edits. So (a) and (b) are **separate rows in every result, with no combined headline number**. If neither (a) nor (b) is possible for a case (t6, whose earlier upload is deleted, may be one), the case stays in the test and is scored as not found, in its own row "no input".

## Leak rule

1. **Excluded domains.** No candidate URL may be on a fact-checking site. The list is frozen here: afp.com, reuters.com/fact-check, apnews.com/article/fact-check, snopes.com, fullfact.org, politifact.com, leadstories.com, factcheck.org, aap.com.au/factcheck, boomlive.in, altnews.in, factly.in, factcrescendo.com, newschecker.in, thequint.com/news/webqoof, indiatoday.in/fact-check, vishvasnews.com, logicallyfacts.com, africacheck.org, pesacheck.org, misbar.com, verafiles.org, rappler.com, tfc-taiwan.org.tw, factcheckcenter.jp, maldita.es, newtral.es, correctiv.org, dpa-factchecking.com, usatoday.com/story/news/factcheck, verifythis.com, annielab.org, dfrac.org, scmp.com (fact-check articles), dw.com (fact-check articles), bbc.com (Verify and Reality Check), perma.cc, archive.ph, archive.today, archive.org, ghostarchive.org, mvau.lt. The search request asks Spark to avoid these domains. Trace then drops any candidate on them.
2. **Search provenance.** Trace keeps every page the web search returned for a recording. A candidate found through web search counts only if none of those pages is on the list in rule 1, and none has a title containing "fact check", "fact-check", "debunk", "false", "misleading", "misrepresent", "miscaption", "hoax" or "not from". If any page fails this test, that recording is marked `leak_exposed`, and any copy found through web search for it scores as not found.
3. **Query source.** Search queries come from the clip and its approved claims only. A separate Spark request without web search writes the queries for the second source (YouTube search through yt-dlp), so that source cannot leak by construction.
4. **Dates.** A post time counts only when it comes from the platform's own extractor (yt-dlp's `timestamp` or `upload_date` for YouTube, X, TikTok, Instagram, Facebook, Reddit or Vimeo). Candidates from yt-dlp's generic extractor, or dated only by page text, are never shown as earlier copies.

## Pipeline

- **Sources:** (A) Muse Spark with the `web_search` tool, asked for at most 3 searches per recording and for links to posts that carry the video; (B) `yt-dlp ytsearch` with at most 3 queries written by Spark without web search, at most 5 results each.
- **Fetch:** at most 10 candidates per recording, low resolution (at most 360 px on the short side), duration at most 15 minutes, with the fetch module's rules: no credentials and public posts only. Candidates are fetched in the order the sources rank them, alternating between A and B.
- **Match:** the input and its candidates go into one clips directory, and then into `indexreel match` and `python -m indexreel.verify`, unchanged from the commit named in Amendment A. A candidate is a **confirmed copy** of the input only when `cluster.effective_band` of their pair is `merged`, which includes a verify `same` that survived the conflict check.
- **Output:** `trace.csv` (format in `eval/run-format.md`). It has one row per candidate, with its source, URL, platform, platform post time, band, verdict, evidence path and leak flags. Trace shows the earliest confirmed copy that is dated before the claimed date. It never says true or false.

Constants that dev may set before Amendment A: the prompts, the number of searches and queries, the candidate cap (at most 10), and the resolution. Amendment A lists their values. Nothing may change after it.

## Bars

A case is **found** when trace shows a confirmed copy that (i) the platform dates on a calendar day (UTC) strictly before the claimed date, (ii) passes the leak rule, and (iii) a blind reviewer judges to be the same recording as the input.

**Blind same-recording check.** (iii), and the "different recording" part of bar 1, are judged by a separate reviewer: another session of this project, one that did not build trace and already scores tests. It works from a sheet with one row per earlier confirmed copy that trace shows. Each row has the case id, the fact-check's description of the original, the path of the candidate's evidence image and the platform date. Rows from test cases and controls are mixed and shuffled. The sheet does not say which source found a row, or whether a row belongs to a control. For each row the reviewer answers `same`, `different` or `cannot tell`. `cannot tell` counts as not the same, and as a wrong statement under bar 1. I do not change the reviewer's answers.

1. **No wrong statement (decisive).** Across all 15 test cases and 4 controls, trace never shows as an earlier confirmed copy a post that is a different recording, that the platform dates on or after the claimed date, or that is dated by anything other than the platform. On a control, any earlier confirmed copy is a wrong statement. One such statement makes the run a FAIL.
2. **Found on at least 40% of the test cases of each input kind**, rounded up, judged separately: (2a) real re-uploads and (2b) our copies. Each kind has its own k of n and Wilson 95% interval, and the two are never added together. Cases with no input count as not found in the kind they were meant for: (a) if a re-upload was found but could not be fetched, otherwise (b). A kind with fewer than 5 cases still gets its bar, marked as too small to read much into.

Bar 1 failing makes the run a FAIL whatever bar 2 says. The run passes only if 1, 2a and 2b all pass.

## Reported

- For each case: the input kind and edit, the approved claims, the number of candidates from each source, the confirmed copies with their platform times, the earliest copy shown, `leak_exposed`, and cost.
- **Found including leak-exposed recordings**, as a secondary number. It shows how much fact-check pages would have helped. It never counts toward bar 2.
- Every miss, each with its reason: no candidate was the recording, the recording was a candidate but was not confirmed, or the input could not be made.
- Cost per recording and in total. The test run stops at $3 (`--max-usd`).

## Limits

- 15 test cases give a wide interval.
- The fact-checks are public, so Spark may have seen some of them in training, and no rule can remove that.
- Kind (b) inputs are copies I made, not the clips that spread.
- "Same recording" is one blind reviewer's judgement, against the fact-check's description, not ground truth.
- A post time says when a clip was posted, not when it was filmed.
- Platforms delete posts, so a miss can mean the upload is gone (t6).
