# Trace v3: the fixed code on new cases

Written Oct 30 2026. No clip of the new cases has been fetched, made, matched or run through trace. The commit that adds this file freezes the cases, the code, the settings, the quota plan, the cost cap and the bars. The test is then run once.

The v2 test (`eval/trace-v2.md`, result in `eval/trace-v2-result.md`) failed. Its 4 wrong statements were evidence images that did not show the link, not wrong matches. A budget order and the Data API's daily search quota cut search short from n3 on. That result stands. Since then trace has been fixed, one commit per finding (listed in the v2 result's correction). An exploratory rerun of n4 to n9 on the fixed code, not scored, found 3 of the 6. This test asks whether the fixed code holds up on cases it has never seen.

## Question

As in `eval/trace.md`: given one clip and the date it was claimed to show, does `indexreel trace` find an upload of the same recording that the platform dates before that claimed date, without reading fact-check pages, and without ever showing a wrong copy or a wrong date?

## Cases

**Test.** Run once.

| id | claimed as (claimed date) | earlier upload named by the fact-check | fact-check |
|---|---|---|---|
| n12 | landslide sweeps houses into water in Jammu, India (2025-08-26) | Alta, Norway, landslide of 2020-06-03, YouTube (NBC News), 2020-06-05 | Factly, 2025-08-29 |
| n13 | Cyclone Biparjoy waves at Somnath and Dwarka, Gujarat (2023-06-06) | waves over the Paseo Nuevo, San Sebastián, Spain, YouTube, 2021-01-10 | Factly, 2023-06-14 |
| n14 | cattle swept away in the Rio Grande do Sul floods, Brazil (2024-04-29) | Zacualpan river, Nayarit, Mexico, YouTube (Imagen Noticias), 2020-07-28 | g1 Fato ou Fake, 2024-05-07 |
| n15 | Super Typhoon Kong-rey in Batanes, Philippines (2024-10-30) | Typhoon Julian (Krathon) in Batanes, Facebook, 2024-09-30 | AFP 36L78U7 |
| n16 | Typhoon Yagi hits Hainan: staff hold hotel doors (2024-09-08) | rainstorm at a Shenzhen hotel, Bilibili, 2024-08-07 | AFP 36FU24C |
| n17 | deadly limestone mine landslide, Cirebon, Indonesia (2025-05-31) | Gunung Kuda rockfall of 2023-06-19, Instagram (infomjlk), 2023-06-20 | AFP 49AL8ZP |
| n18 | truck escapes a landslide in Chamba, Himachal Pradesh (2025-08-01) | West Sumatra, Indonesia, YouTube Shorts (The Weather Network), 2024-05-20; flipped in the false posts | AFP 699E6CQ |
| n19 | river rescue in Dharali, Uttarakhand (2025-08-06) | five men stranded in a river at Nalagarh, Himachal Pradesh, YouTube (Indian Express Punjab), 2022-07-29 | AFP 69ZC4WE |
| n20 | Uttarakhand flash flood (2025-08-05) | Bardonecchia, Italy, YouTube (The Sun), 2025-07-01 | Factly, 2025-08-19 |
| n21 | Marina Beach flooded by Cyclone Mandous, Chennai (2022-12-09) | Marina Beach after the rains of November 2021, YouTube Shorts, 2021-11-12 | Factly, 2022-12-12 |

None of these recordings or claimed events is in v1 or v2. Test ids go on from v2 (n12 on), so the scorer needs no change. n19 and n20 share a claimed event (the Uttarakhand floods of August 2025). Claimed dates follow Clarification 2 of `eval/trace.md`: the date of the viral post the fact-check quotes, or the start of the claimed event when it gives none. n12, n13 and n14 quote no post date, so their dates are the start of the claimed event: the Jammu landslides of Aug 26 2025, Biparjoy's formation on June 6 2023, and the start of the Rio Grande do Sul rains on Apr 29 2024.

**How the cases were found.** A web search assistant was asked for 18 candidate fact-checks. 13 of its links did not hold up: they returned 404, led to an unrelated article, or gave no earlier upload. One more was a brawl between two countries' fans, which I left out as too close to politics. I kept 3 of its cases (n13, n14, n21) and found the rest with a web search of fact-check sites. I read each fact-check myself and checked, with metadata only and nothing downloaded, that the earlier upload is still live and readable. Dropped on that check: a Typhoon Gaemi bridge clip (the YouTube original is gone); a Guangdong wind clip on Newsflare, a Sri Lanka waterspout on Facebook and a Venezuela flood on Instagram (their uploads cannot be fetched). An Atami mudslide clip was dropped because Atami is in v1. Nothing from these pages was used to build or tune trace.

**Controls** (true claims, so no copy dated before the claimed date can exist): k1 to k4 of `eval/trace-v2.md`, with the same inputs and claimed dates. In v2's test and its exploratory rerun none of them had a confirmed copy, and nothing in trace was tuned on them.

## Inputs

As in `eval/trace-v2.md`: kind (a) is a live post linked from the case's fact-check and dated on or after the claimed date, used as fetched. Kind (b) is my copy of the earlier upload, re-encoded at 720 px and flipped where the fact-check says the viral clip was. Each kind (b) copy gets one of four edits, in turn and in test-id order: flip, slow motion, zoom, compilation segment with synthetic filler. A case with no input stays in the test and is scored as not found.

n21 has a live viral repost (a Facebook video of 2022-12-09), so it is kind (a). The others are kind (b). Their edits, in id order: n12 flip, n13 slow motion, n14 zoom, n15 compilation, n16 flip, n17 slow motion, n18 zoom (on top of the flip the fact-check reports), n19 compilation, n20 flip. Kind (a) rests on one case, so bar 2a says little either way.

## Frozen code and settings

- Code at commit `70fc6f7`: `src/indexreel/trace.py`, `scripts/trace_inputs.py` and `scripts/score_trace.py`. The matcher and verifier are unchanged from `eval/trace.md`.
- **Checked live before the freeze.** The credit source and the id dates had never met the live services. On Oct 30 I ran trace on v2's dev cases e1 to e3 only, on a copy of their cache, capped at $0.40. It spent $0.36 in all and made no new Data API search. The run found one bug: the credit source took the social pages a later copy's description names (`facebook.com/Reuters`, `instagram.com/APNews/`) as posts, and they used 8 of e3's 10 fetch slots. Commit `a922f05` (with a test) counts a Facebook, Instagram, TikTok, Reddit or Vimeo link as a post only when its path shows one. The same run on that commit then showed a confirmed earlier copy for all three cases, each plainly the same recording on its image. No v3 case was fetched, seen or run.
- **Sources:** credit, web, channel, Data API and yt-dlp; keyframe search is off. 3 queries, written from the clip only; 50 results per query in each YouTube source. The credit source reads the descriptions of later YouTube copies and follows the posts they link and the channels they name. It skips a description that reads like a fact-check or links to one. It is not leak-exposed.
- **Before download:** a result longer than 30 minutes is skipped, and so is one the platform dates on or after the claimed date. YouTube results are ordered by SSCD on YouTube's preview frames, with letterbox bars trimmed. One URL is kept per video, unranked videos go last, and videos the Data API no longer returns are skipped. At most 10 candidates are fetched per recording.
- **Cost order:** every recording's searches run before any matching. Candidates are matched earliest first. A recording stops after 2 confirmed earlier copies, and its remaining candidates are marked `enough_copies`. Verify keeps $0.05 in reserve for each recording still to come.
- **Evidence image:** the input is always on the left. Orientation comes from the pixels. Times follow the matcher's offset, or one speed ratio (0.5 or 2) when it is clearly better. A core span under 6 s is widened to the cover span. The wider side is cropped to the other's view when at least 15 ORB matches survive RANSAC. Sides are labelled input and candidate, with no video ids.
- **Dates:** a copy whose own post id (X, TikTok, Instagram) contradicts its date is never shown as earlier. Facebook and Vimeo dates are marked editable.
- **Possible earlier source (display only).** An earlier candidate that verification called `different`, while its answer said both clips show the same place or event and named the detail, is marked `possible_source` in `trace.csv` and in the log as a lead to check by eye. It is never confirmed, never shown as a copy, never counted in a bar, and costs no extra request. It was added (commit `70fc6f7`, with a test) after n6 of the v2 rerun, where verification called the unedited 2016 footage of an edited clip `different` while naming the same landmarks. On the v2 runs it marks that pair and one more: a clip of n2's landslide scar that may be a second camera at the same place, which is why it is a lead and not a copy.
- **Corroboration:** as in v2, reported next to the bars and never part of them.

## Quota and cost plan

- The YouTube Data API's `search.list` has its own bucket of 100 calls a day, reset at midnight Pacific. Trace makes at most 3 per recording, so at most 42 for the 14 recordings here. Trace counts its calls in a file outside the repo and stops that source at 100.
- The test runs alone, on a fresh Pacific quota day: it starts after 07:00 UTC on Sat Oct 31, which is midnight Pacific. No other Data API search runs that Pacific day.
- The run stops at **$3** (`--max-usd 3`). v2's test spent $1.97 before stopping.
- If YouTube blocks downloads, the v2 resume rule applies unchanged. I stop the run and resume it with the same command and the same cache. No code, setting or cache entry changes in between, nobody looks at partial output, and every stop and resume is logged with its time. No cookies, accounts, proxies or VPNs are used. A block that lasts more than a few hours is logged with its times in the result, and I decide on any next step only after that.

## Leak rule

As in `eval/trace-v2.md`: a confirmed copy passes when at least one source that found it is not leak-exposed. Web search is leak-exposed for a recording when any page it returned is excluded or carries a fact-check word in its title.

## Bars

A case is found when trace shows a confirmed copy that the platform dates on a UTC day strictly before the claimed date, the copy passes the leak rule, and the blind reviewer answers `same` to question (i) and to question (ii).

1. **No wrong statement (decisive).** Counted over **every earlier confirmed copy in `trace.csv`**, shown or not: this is the stricter reading (L2 of the v2 bug hunt) and the one the scorer uses. Stop-at-2 makes it at most 2 per recording. A copy is wrong when it is a different recording (question (i) `different` or `cannot tell`), dated on or after the claimed date, or dated by anything other than the platform. On a control, any earlier confirmed copy is wrong.
2. **Found on at least 40% of the test cases of each input kind**, rounded up: (2a) real re-uploads and (2b) my copies, each with its own k of n and Wilson 95% interval, never added together. A kind with fewer than 5 cases still gets its bar, marked as too small to read much into.

The run passes only if 1, 2a and 2b all pass.

## Blind check

As in v2: the same separate reviewer answers two sheets. The sheets are in separate folders, each with its own shuffle, row ids and case labels, and neither says which source found a row or which rows are controls. Sheet 2 (question ii) is given alone first. Sheet 1 (question i) is given only after sheet 2's answers are written. Answers are not changed after they are written. Scoring runs once, after both sheets.

## Reported

As in v2, plus `enough_copies`, `date_check`, the number of `possible_source` leads (each looked at by me after scoring, not part of the bars), the credit source's candidates, the Data API searches used, and cost per source. Corroboration is reported next to the bars, never as a bar.

## Limits

- About 10 test cases give a wide interval, and kind (a) may have very few.
- Verify can call an edited copy `different` when the edit adds something, as with n6's 2016 footage in the exploratory rerun. A copy missed that way makes trace show a later copy, never a wrong one.
- Bars use the platform's UTC day, while claimed dates are local (L5 of the bug hunt, not fixed).
- Spark and YouTube may have seen the fact-checks; no rule removes that.
- Search results change from day to day, so a rerun would give different candidates.
- "Same recording" is one blind reviewer's judgement.

## Test commands, in order, once

1. Write `data/trace_v3_test/manifest.csv` for the test cases, with the segment of each kind (b) source chosen from the fact-check's description, and copy k1 to k4's inputs from `data/trace_v2_test/in`.
2. `python scripts/trace_inputs.py data/trace_v3_test/manifest.csv --out data/trace_v3_test/in`
3. `indexreel match data/trace_v3_test/in --out data/trace_v3_test/run`
4. `python -m indexreel.claims data/trace_v3_test/run`, then I approve or reject the rows (for the page only).
5. On Sat Oct 31 after 07:00 UTC: `indexreel trace data/trace_v3_test/run --claimed-dates data/trace_v3_test/in/claimed_dates.csv --max-usd 3 --cache data/trace_v3_test/cache`, with a new, empty cache.
6. The two blind sheets from `trace.csv` with `scripts/score_trace.py`, then the score once. FAIL rows are kept.

## Clarification C1 (Oct 30 2026, after the inputs were made, before trace ran on any of them)

n16's earlier upload on Bilibili and the qq.com copy its fact-check names could not be fetched, so n16 is kind none: it stays in the test and is scored as not found. `scripts/trace_inputs.py` at `70fc6f7` gives the edits in turn to the kind (b) cases only, so from n17 on each case has the next edit of the cycle: n17 flip, n18 slow motion (on top of the reported flip), n19 zoom, n20 compilation. The rule is unchanged; the list in Inputs assumed n16 would be kind (b). With 13 recordings trace makes at most 39 Data API searches. Nothing else changes.

## Amendment 1 (Oct 31 2026, before trace ran on any v3 case)

A run of the X bot on a post that is not a v3 case crashed trace. For one YouTube candidate, yt-dlp left only an audio format part (`<stem>.f251.webm`, 2.7 KB) and its info, with no merged video. `fetch.fetch` took that part as the video and said `ok`, and trace then read a sidecar that did not exist and stopped. The v3 run takes the same path. Commit `9b8204b` (with a test) accepts only a file named exactly `<stem>.<ext>`, so a leftover part is a failed fetch, which trace already records as `error no_video` for that candidate. The fix turns a crash into a counted fetch failure. It cannot add a candidate or a confirmed copy, so it cannot make a result look better. No v3 case was fetched, seen or run.

The run uses the code exported at `70fc6f7` with `src/indexreel/fetch.py` from `9b8204b` and nothing else. Later commits on main that change the matcher's frame reading are not part of this test.
