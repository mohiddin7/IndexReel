# Trace v2: better retrieval, tested on new cases

Written Oct 29 2026, before any trace code for v2 exists and before any clip of the new cases has been fetched, matched or run through trace. The commit that adds this file freezes the new cases, the split, the leak rule and the bars. Amendment B, written after dev work ends and before any test input is made, will freeze the code commit, the sources and the constants. The test split is then run once.

The first trace test (`eval/trace.md`, result in `eval/trace-result.md`) failed. It never made a wrong statement, but it found an earlier copy for only 2 of 15 cases. In 11 of the 12 cases with an input, the upload named by the fact-check was never a candidate: search was the bottleneck, not matching. That result stands. This is a new test with new cases, not a rerun.

## Question

As in `eval/trace.md`: given one clip and the date it was claimed to show, does `indexreel trace` find an upload of the same recording that the platform dates before that claimed date, without reading fact-check pages, and without ever showing a wrong copy or a wrong date? v2 changes only how candidates are found and chosen before they are fetched.

## What a first measurement showed

The v1 queries for the 10 v1 test cases whose named original is on YouTube, rerun on Oct 29 at 50 results per query instead of 5, returned that original for 3 of them: t15 at rank 1 (in v1 it came back past the cap of 10), t7 at rank 3 (found in v1), and t1 at rank 16. A larger pool and a better order can therefore recover a case or two. But for most cases no text query reaches the original at all, so v2 also tests search by date and search by image.

## Meta's own tools, checked first

- **Muse Spark web search** (used in v1 and kept). It returns text results only (title, URL, snippet); it has no image or video search, and on the Messages API it does not accept allowed or blocked domain lists ([search grounding](https://dev.meta.ai/docs/search-grounding)). So fact-check pages cannot be kept out at the source, which is why the leak rule exists.
- **Meta Content Library and API.** Access needs a qualified academic or not-for-profit research institution; review takes 2 to 3 weeks, and Meta's processing another 2 to 3 weeks ([get access](https://developers.facebook.com/docs/content-library-and-api/get-access/)). Data may not leave Meta's secure research environment ([FAQ](https://developers.facebook.com/docs/content-library-and-api/support/faqs/)). Search matches keywords in post text, with since and until dates, not images or video ([search guide](https://developers.facebook.com/docs/content-library-and-api/content-library-api/guides/search-guide/)). It cannot be used for this test on eligibility, time or export grounds.
- The Graph API offers no search of public posts. Page Public Content Access reads pages that are named, it does not search ([reference](https://developers.facebook.com/docs/features-reference/page-public-content-access/)).

No Meta tool can search public video by date or by image within this test, so v2 also measures Google's official APIs. Bing's visual search API has been retired, and TinEye's API is a paid commercial plan. No search engine's web interface is scraped.

## Cases

**Dev.** The 25 cases of v1: its dev cases d1-d10 and **its test cases t1-t15, which were v1's test set** and are closed since its result. Their inputs already exist. Three new cases are added to dev:

| id | claimed as (claimed date) | earlier upload named by the fact-check | fact-check |
|---|---|---|---|
| e1 | American Airlines plane skids off the runway at O'Hare in the January 2024 storms (2024-01-12) | ABC7 Chicago, YouTube, 2019-11-11 | AFP 34FL4MD |
| e2 | Tornado in KwaZulu-Natal, South Africa (2024-06-03) | drone footage of the Andover, Kansas tornado, X (Reed Timmer), 2022-04-30 | AFP 34VR37J |
| e3 | Crocodile in a flooded street in Ambala, India (2023-07-10) | crocodile in Shivpuri, Madhya Pradesh, Facebook, 2022-08-14 | AFP 33P927W |

**Test** (run once, after Amendment B). None of these recordings or claimed events is in v1. Cases that share a claimed event stay together (n4 and n5; n6 and n7).

| id | claimed as (claimed date) | earlier upload named by the fact-check | fact-check |
|---|---|---|---|
| n1 | Storm Eunice blows a wheelie bin and trampoline away, UK (2022-02-18) | suspected tornado in Barking, London, TikTok, 2021-06-25 | Full Fact, 2022-02-22 |
| n2 | Gofa landslide, Ethiopia (2024-07-24) | Meghalaya landslide, India, YouTube (Northeast Live 2022-06-27; CNN-News18 2022-06-28) | AFP 368T7R9 |
| n3 | Sea at the Gateway of India, Mumbai monsoon (2025-08-19) | Cyclone Tauktae, YouTube (CNN-News18), 2021-05-17 | AFP 724M8G6 |
| n4 | Texas Hill Country floods, compilation clip (2025-07-05) | camper swept away, Indiana, YouTube (ViralHog), 2019-02-09; sped up and flipped | AFP 66AV2NQ |
| n5 | Texas Hill Country floods, compilation clip (2025-07-05) | wave on Roi-Namur, Kwajalein, YouTube, 2024-01-24; sped up and flipped | AFP 66AV2NQ |
| n6 | Tornado during Typhoon Ragasa, China (2025-09-24) | effects-edited tornado clip, YouTube, 2023-09-04 (from Hurricane Matthew footage, YouTube 2016-10-08) | AFP 773D2T3 |
| n7 | Elevator shaft collapses in Typhoon Ragasa, China (2025-09-24) | Typhoon Mangkhut, Hong Kong, Facebook, 2018-09-16 | AFP 777T7NT |
| n8 | Building torn apart by Typhoon Shanshan, Japan (2024-08-30) | Lincoln, Nebraska tornado dashcam, YouTube, 2024-05-04 | AFP 36FK4DF |
| n9 | Fire tornadoes in the Los Angeles wildfires (2025-01-11) | Remington Fire, Wyoming, TikTok, 2024-08-23 | AFP 36UD2A6 |
| n10 | Road collapse in Pak Kret, Thailand (2025-09-24) | road collapse in Nonthaburi, TikTok, 2024-04-06 | AFP 77FQ9WE |
| n11 | Start of the Myanmar earthquake in Mandalay (2025-03-29) | mud volcano at Tabin Wildlife Resort, Malaysia, Facebook, 2022-09-18 | AFP 39GX3ZR |

Claimed dates follow Clarification 2 of `eval/trace.md`: the date of the viral post the fact-check quotes, or the start of the claimed event when it gives none. n6, n7 and n10 quote posts without a usable date, so their dates are the start of the claimed event (Ragasa's landfall in Guangdong; the Bangkok road collapse of Sept 24 2025 that the Pak Kret posts followed).

**Controls** (true claims, so no copy dated before the claimed date can exist):

| id | clip (claimed date) | why there is no earlier copy |
|---|---|---|
| k1 | sinkhole opening in front of a Bangkok hospital (2025-09-24) | genuine, filmed and reported that day |
| k2 | Artemis II launch, NASA's recap (2026-04-01) | NASA footage of the launch, public domain |
| k3 | lava fountain engulfing a USGS webcam at Kīlauea (2025-12-06) | USGS footage of that episode, public domain |
| k4 | my own airshow clip, as c3 in `eval/trace.md` (2026-09-26) | I filmed it and posted it once |

k4 was a control in v1; it is reused because no earlier copy of it can exist, and nothing was tuned on it.

## Inputs

As in `eval/trace.md` (Inputs, Clarification 2): kind (a) is a live post linked from the case's fact-check and dated on or after the claimed date, used as fetched; kind (b) is my copy of the earlier upload, re-encoded at 720 px, flipped where the fact-check says the viral clip was, and given one of four edits in turn in test-id order (flip, slow motion, zoom, compilation segment). The two kinds are reported separately. A case with no input stays in the test and is scored as not found.

One change: the compilation edit now places the copy between two 6 s pieces of a synthetic pattern made by ffmpeg, not NASA footage. Keyframe search could otherwise find copies of the filler itself, which are real uploads of a different recording.

From the fact-check pages checked on Oct 29, n1 has a live viral repost (a Facebook video of 2022-02-18), so it is kind (a); the others are kind (b) unless a live repost linked from their fact-check is found before the inputs are made. With so few kind (a) cases, bar 2a is marked as too small to read much into.

## Sources

Each source is measured on dev; Amendment B states which are used.

- **Web:** Muse Spark with web search, as frozen in Amendment A of `eval/trace.md`.
- **YouTube:** queries written by a Spark request without web search, from what the clip shows only (no claim), as in Amendment A. Searched three ways: `yt-dlp` search, sorted by relevance or by upload date; inside the channel Spark names; and the **YouTube Data API v3** `search.list` with `publishedBefore` set to the claimed date, so that only uploads made before it are returned.
- **Keyframe:** Google **Cloud Vision web detection** on a few keyframes of the input. It returns pages and images that match each frame; candidates are the video posts among those pages.

The two Google sources need my API key. When it is absent, or a quota or rate limit is hit, that source stops for the run, the log says so, and the run goes on with the others.

**Choosing what to fetch.** Search may return many more results than are fetched. Dev may use, before any download: the duration in the search result (over 30 minutes is skipped, as in v1); a pre-rank by comparing YouTube's own small preview frames of each result with the input's frames using the same SSCD model; and the platform's upload date, read without downloading, so that posts dated on or after the claimed date are not fetched (trace never shows them). At most 10 candidates are fetched per recording, as in v1. Matching, verification, the coarse pass, the evidence image and the rule for a confirmed copy are unchanged from Amendment A of `eval/trace.md`.

**Dev measurement.** For each dev case with a known earlier upload, **retrieval recall** is whether a known earlier upload of the recording is among the fetched candidates. It is measured for each source alone and for their combinations, without and with the pre-rank and the date filter. Amendment B picks the combination with the highest dev recall within the cost cap, and full dev runs check it for wrong statements before it is frozen.

## Leak rule

As in `eval/trace.md`, rules 1 to 4, with Amendment A (search reads the clip only; leak rule 2 per copy). Keyframe search is treated like web search: it can return fact-check pages. For each recording, the web source and the keyframe source are each marked `leak_exposed` on their own when any page they returned is on the excluded list or has a fact-check word in its title. A confirmed copy passes rule 2 when at least one source that found it is not leak-exposed. The YouTube sources cannot leak by construction, as in v1.

## Corroboration

Reported next to the bars, never part of them.

- **Families.** web (Spark search), YouTube (yt-dlp, channel and Data API together, since they search the same index) and keyframe (Cloud Vision).
- **Date search.** For each copy trace shows, one separate Spark web search asks when the event the footage shows happened, with links to official and independent sources (the agency's own page, news archives). Here fact-check pages may be cited as evidence for a date. They are never a source of candidates.
- **Strong copy.** A shown copy is **strong** when two families found it, or when one did and the date search gives a date on or before the copy's post date, cited by at least two different sites. Otherwise it is **single-source**.
- New `trace.csv` columns: `families`, `strength`, `corroborated_date`, `corroboration_urls` (documented in `eval/run-format.md`).

## Bars

Unchanged from `eval/trace.md` with Clarification 1: a case is found when trace shows a confirmed copy dated by the platform on a UTC day strictly before the claimed date, the copy passes the leak rule, and the blind reviewer answers `same` to question (i) and to question (ii).

1. **No wrong statement (decisive).** Across the 11 test cases and 4 controls, no earlier copy shown is a different recording (question (i) `different` or `cannot tell`), dated on or after the claimed date, or dated by anything other than the platform. On a control, any earlier copy shown is a wrong statement.
2. **Found on at least 40% of the test cases of each input kind**, rounded up: (2a) real re-uploads and (2b) my copies, each with its own k of n and Wilson 95% interval, never added together. A kind with fewer than 5 cases still gets its bar, marked as too small to read much into.

The run passes only if 1, 2a and 2b all pass. The blind check is done as in v1, by the same separate reviewer, from shuffled sheets that do not say which source found a row or which rows are controls.

## Reported

As in `eval/trace.md`, plus: the number of candidates from each source and family, how many were skipped before download and why (duration, date, rank), the strength of each copy shown, found counted with leak-exposed sources (secondary), and cost per source. The test run stops at $2 (`--max-usd`).

## Limits

- 11 test cases give a wide interval, and kind (a) has very few.
- The dev set holds v1's test set. It was the right size to learn from, but trace v2 is tuned on cases whose answers are known.
- Spark and the Google services may have seen the fact-checks or their keyframes; no rule removes that.
- Search results change from day to day, so a rerun would give different candidates.
- "Same recording" is one blind reviewer's judgement.
- A post time says when a clip was posted, not when it was filmed.
