# Trace test: result

The protocol is `eval/trace.md` (commit b61ff0d), with Clarification 1 (6237818), Amendment A (d54beed) and Clarification 2 (8b19122). Trace code is at a402bb5, the input script at c985aac and the scoring script at 377206a. The test split was run once, on Oct 29 2026, with a new, empty cache, and was not run again. Every row is kept below.

## Verdict: FAIL

| bar | result | |
|---|---|---|
| 1. No wrong statement (decisive) | **0 wrong statements**: 8 earlier confirmed copies were shown, and the blind reviewer judged all 8 the same recording as the input; no control showed an earlier copy | PASS |
| 2a. Found, real re-uploads | **0 of 2**, needs 1, Wilson 95% 0.00-0.66 (too few cases to read much into) | FAIL |
| 2b. Found, our copies (cases with no input count here) | **2 of 13**, needs 6, Wilson 95% 0.04-0.42 | FAIL |
| Secondary: found, counting leak-exposed recordings | 3 of 15 | |

Trace never showed a wrong copy or a wrong date: not on the test cases, and not on the four true-claim controls, two of which had copies posted on or after their claimed date. But it found an earlier copy for only 2 of 15 test cases. Nearly every miss was a search miss. The matcher did not cause them.

## Each test case

"Fetched" counts the candidates that were downloaded and matched. Leak means the recording's web search read a page from a fact-checking site or with a fact-check title. "Earlier confirmed" counts copies that were merged with the input and dated by the platform before the claimed date.

| case | claimed as (claimed date) | input | fetched | leak | earlier confirmed copies | found | why not |
|---|---|---|---|---|---|---|---|
| t1 | Mauna Loa eruption (2022-11-27) | ours, flip | 7 | no | 0 | no | the original upload (YouTube, 2018) was never a candidate |
| t2 | Reykjanes eruption (2023-11-15) | ours, slow motion | 10 | yes | 0 | no | never a candidate |
| t3 | Hurricane Helene storm surge (2024-09-25) | re-upload (X, 2024-09-26) | 7 | yes | 0 | no | never a candidate |
| t4 | Dubai storm damage (2024-04-18) | ours, zoom | 9 | no | 0 | no | never a candidate |
| t5 | Taiwan tsunami (2024-04-03) | ours, compilation segment (and flipped, as the fact-check says) | 10 | yes | 0 | no | never a candidate |
| t6 | Taipei 101 swaying (2024-04-03) | none (the earlier TikTok post is deleted) | - | - | - | no | no input |
| t7 | Turkey earthquake tsunami (2023-02-08) | ours, flip | 9 | yes | 3: 2017-03-12 and 2017-03-13 (web), 2017-03-14 (the broadcaster's own upload, YouTube search) | **yes** | |
| t8 | Morocco building collapse (2023-09-11) | none (the earlier TikTok post is known only from an archive) | - | - | - | no | no input |
| t9 | Morocco home shaking (2023-09-09) | ours, slow motion | 5 | yes | 0 | no | never a candidate |
| t10 | Kamchatka earthquake (2025-07-30) | re-upload (the viral X post) | 10 | no | 0 | no | never a candidate |
| t11 | LA wildfire rabbit rescue (2025-01-09) | ours, zoom | 10 | yes | 4: two broadcaster uploads of 2017-12-07 (web), 2017-12-12 and 2017-12-14 (YouTube search) | **yes** | |
| t12 | Valencia floods (2024-10-31) | none (the agency page no longer carries the video) | - | - | - | no | no input |
| t13 | Wayanad flooding (2024-07-30) | ours, compilation segment | 8 | yes | 1: 2024-06-25 (web only) | no | the copy came only from web search on a leak-exposed recording (leak rule 2) |
| t14 | Himlung Himal avalanche (2026-09-27) | ours, flip | 9 | yes | 0 | no | never a candidate |
| t15 | Qatar World Cup stadium fire (2022-11-23) | ours, slow motion | 6 | yes | 0 | no | YouTube search returned the original upload, but past the 10-candidate cap, so it was never fetched |

Controls (true claims):

| control | claimed date | fetched | confirmed copies | earlier | wrong statements |
|---|---|---|---|---|---|
| c1 shark in a flooded street, Fort Myers | 2022-09-28 | 6 | 0 | 0 | 0 |
| c2 deer fleeing the Eaton Fire | 2025-01-07 | 10 | 1 (TikTok, 2025-01-08) | 0 | 0 |
| c3 my own airshow clip | 2026-09-26 | 10 | 0 | 0 | 0 |
| c4 USGS lava at fissure 20 | 2018-05-19 | 9 | 2 (2018-05-20, 2018-05-21) | 0 | 0 |

## Why it failed

1. **Search, not matching.** For 11 of the 12 test cases with an input, the upload the fact-check names was never a candidate, even when it is a plain YouTube upload (t1, t5). The one exception is t15, where it was returned past the cap. Every candidate that was fetched got a decision: none was left unresolved. Every copy that was found matched with a verify `same`. Spark's queries describe what the clip shows, and they seldom reach a particular upload.
2. **Fact-check pages in the web search.** 10 of the 16 recordings were `leak_exposed`. Footage that has been recycled is exactly the footage that has been fact-checked, so web search keeps landing on the fact-checks. Under the leak rule, copies found only through such a search do not count, and t13 was lost that way. Both cases that were found also had a copy from YouTube search, which cannot leak.
3. **Caps.** 14 candidates were skipped as longer than 30 minutes, and on t15 the original fell past the cap of 10 candidates.
4. **Missing and unreachable posts.** Three cases had no input, because the earlier upload was deleted or survives only as an archive or a page without the video. Other candidates were private, needed a login (Instagram, Reddit, Facebook), or had been deleted on YouTube.

## The blind check

A second reviewer, who did not build trace, answered both sheets using only the sheet folder. It saw no key, ran no trace code, and changed no answer after writing it.
- Question (i) (8 rows): all 8 `same`. The candidates included mirrored copies, wider frames with broadcaster logos, a screen capture of a web page, and a small inset inside a caption card.
- Question (ii) (8 rows): all 8 `same`. Three of them (both web copies for t7, and the copy for t13) show no readable place name, so those answers rest on the scene and the post date. One candidate's caption claims a different event (a house fire); the reviewer judged the footage, not the caption.
- The reviewer listed both sheets before starting, so it saw the sheet 2 descriptions before judging sheet 1. Its sheet 2 answers are not blind to sheet 1, because the sheet 1 images had already shown each candidate beside its input.

## Deviation from the wording of the protocol

- c1: Clarification 2 named the earliest X post of 2022-09-28. That post still lists the video, but its media returns HTTP 403 in every format, and the other posts of that day have no video left. The input is instead the video agency's licensed YouTube upload of the same authentic footage, posted 2022-09-30. It meets the kind (a) rule: a live post of the footage dated on or after the claimed date. The claimed date stayed 2022-09-28. This was decided and recorded before any run.

## Cost and time

The test run cost $1.16, and the claims for the page $0.016. Dev cost $2.14. Matching 135 candidates on a laptop CPU, with the coarse pass on long ones, took most of the run.

## Limits

- 15 test cases and 2 real re-uploads give wide intervals.
- 10 of the 13 our-copy inputs are edits I made from the original, which are easier to match than real viral edits. They mainly test search.
- "Same recording" rests on one reviewer's judgement.
- Post times say when a clip was posted, not when it was filmed.
- A search engine's results change from day to day, so a rerun would give different candidates. This run is the result.
