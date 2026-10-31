# Trace v4: more earlier copies, still no wrong one

Written Oct 31 2026. No clip of the new cases has been fetched, made, matched or run through trace. The commit that adds this file freezes the cases, the code, the settings, the quota plan, the cost cap and the bars. The test is then run once.

v1 to v3 failed on finding (2/13, 2/10, 2/9 of my copies). v3's one wrong statement was an evidence image of a slowed copy whose three moments missed the shot (`eval/trace-v3-result.md`). Every case of v1 to v3 then became dev data. On it I tried six changes, cheapest first, and kept only those that helped without a new wrong copy. This test asks whether the kept changes find more on cases trace has never seen, with no wrong statement.

## What changed since v3, measured on the v1 to v3 cases (dev)

Measured on the 32 test cases of v1 to v3 (and their controls), with the search caches of those runs and fresh Data API searches where a change needed them. For each change: does the source upload reach the fetch list, does trace confirm an earlier copy, and does any new confirmed copy show a different recording (each one checked by eye).

| change | source reached | found | new wrong copy | kept |
|---|---|---|---|---|
| none (as v3) | 16 of 32 | my copies, as scored: 2 of 13 in v1, 2 of 10 in v2, 2 of 9 in v3 (n12, n19) | - | - |
| a web search prompt aimed at social posts | 9 of 20 on v2 and v3, against 10: it lost n8, which only web search had reached, and reached no new source | none new | none | no |
| the claimed place adds search queries | 8 of 17 on v2 and v3, as before; 5 of 11 on v1 against 6 (the extra results push one source from rank 8 to 18) | none new | none | no |
| search with the recording's best member | not measurable: every dev recording has one member | - | - | not built |
| fetch 15 or 20 candidates instead of 10 | 16 of 32 at 10, 15 and 20 | none new | - | no (each extra candidate costs about 40 s to match) |
| geo rescue of apart candidates | as before | **n20** as well (v3: 3 of 9): 2 copies the matcher had kept apart, both judged the same recording in v3's blind check | none | **yes** |
| the card drawn on geo's line | as before | as before | none; it removes v3's one wrong statement | **yes** |

**Geo rescue.** For a recording with fewer than 2 confirmed earlier copies, up to 3 earlier candidates the matcher kept apart, best aligned first, go to the geometric check. Only when it says `same` is verify asked, and only when verify then says `same` too, and a card can be drawn on geo's line, is the copy confirmed. Before keeping it I checked that it adds nothing wrong where it should not: geo said `same` on none of 95 earlier negatives (same place, other recordings); on the same-view set it said `same` once, on a pair verify calls `different`, so the rule above blocks it; and it said `same` on none of the 81 apart candidates of v1 and v2 it would check; and on no v3 control.

**Card on geo's line.** When geo's line for a confirmed copy is strong, the card shows the input at three times inside the span geo found the line on, beside the candidate at the times that line gives. v3's one wrong statement was n13's card, whose slowed copy's three moments missed the shot. On geo's line all three show the same wave. Redrawn this way, the 29 cards of v1 to v3 copies with a strong line each show the same moment on both sides when I look at them. That is my look, not a blind check.

The changes are in commit `633704c`, with tests. The replay spent $2.11 of its $3 cap ($1.02 of it on the social prompt) and 50 Data API searches.

## Question

As in `eval/trace.md`: given one clip and the date it was claimed to show, does `indexreel trace` find an upload of the same recording that the platform dates before that claimed date, without reading fact-check pages, and without ever showing a wrong copy or a wrong date?

## Cases

**Test.** Run once.

| id | claimed as (claimed date) | earlier upload named by the fact-check | fact-check |
|---|---|---|---|
| n22 | a tornado in Texas (2025-01-19) | Andover, Kansas tornado of 2022-04-29, YouTube Shorts, 2022-05-15 | AFP 36XQ9G4 |
| n23 | Anak Krakatau erupting, Indonesia (2026-09-06) | Anak Krakatau at night, October 2018, YouTube, 2018-11-05 | AFP C7VM3NQ |
| n24 | Hurricane Melissa in Jamaica (2025-10-28) | Tropical Storm Barry, July 2019, YouTube Shorts, 2019-07-13 | Full Fact, 2025-10-31 |
| n25 | hikers flee a Mount Dukono eruption, North Halmahera (2026-05-09) | the same eruption in August 2024, YouTube (The Telegraph), 2024-08-21; first posted on Instagram 2024-08-18 | AFP B2GM6NQ |
| n26 | a small tsunami in California during the January fires (2025-01-13) | the Pierpont Bay rogue wave, Ventura, Facebook (the person who filmed it), 2023-12-28 | AFP 36U879E |
| n27 | a landslide in Baguio, Benguet, during Typhoon Emong (2025-07-24) | road landslide at Tabuk, Kalinga, during Typhoon Kristine, Facebook reel, 2024-10-24 | VERA Files, 2025-07-28 |
| n28 | tsunami waves hit Palawan, Philippines (2026-06-08) | typhoon storm surge on coastal houses, Facebook reel, 2025-11-09 | AFP Factual B6EQ8CR |
| n29 | flash flood in Guwahati, Assam (2025-06-03) | Sainj valley flood, Himachal Pradesh, Instagram, 2024-09-08 | AFP 62NA2ZU |
| n30 | power projects swept away in the Nepal floods (2026-08-26) | a hydropower plant's embankment washed away, Khyber Pakhtunkhwa, Pakistan, Instagram, 2022-08-28 | AFP C6M39WH |
| n31 | a landslide in the Nepal floods (2026-08-27) | the Wayanad, Kerala landslide of 2026-07-07, Instagram reel, 2026-07-07 | AFP C6PF2CQ |

None of these recordings or claimed events is in v1, v2 or v3. Test ids go on from v3 (n22 on), so the scorer needs no change. n30 and n31 share a claimed event (the Nepal floods of August 2026) but are different footage. Claimed dates follow Clarification 2 of `eval/trace.md`: the date of the viral post the fact-check quotes. The earlier uploads are on YouTube (n22 to n25), Facebook (n26 to n28) and Instagram (n29 to n31).

**How the cases were found.** A research assistant searched fact-check sites for miscaptioned disaster, weather and accident videos whose fact-check names the earlier upload, and checked each earlier upload live with metadata only (nothing downloaded). It left out political, military and rivalry cases and everything in v1 to v3. Of its ten picks I replaced one whose false claim blamed another country's dam, as too close to politics, with one of its reserves (n24). Nothing from these pages was used to build or tune trace, and no v4 case was part of the dev replay.

**Controls** (true claims, so no copy dated before the claimed date can exist). New for v4, none seen by trace before:

| id | what it shows (claimed date) | post |
|---|---|---|
| k5 | a waterspout near downtown Fort Myers, Florida (2026-03-16) | YouTube, a local news station, 2026-03-17 UTC |
| k6 | a flood through a village in Nepal's Himalayan region (2026-08-26) | X, a news agency, 2026-08-27 UTC |
| k7 | stranded residents in the Haleiwa, Oahu floods (2026-03-20) | Instagram, a weather channel, 2026-03-20 |
| k8 | a landslide at Itogon, Benguet, during Typhoon Emong (2025-07-25) | Facebook, a regional state TV page, 2025-07-25 |

Each control's claimed date is the event's day, so a copy dated before it would be a wrong statement. k6 shares its event with n30 and n31.

## Inputs

As in `eval/trace-v3.md`: kind (a) is a live post linked from the case's fact-check and dated on or after the claimed date, used as fetched. Kind (b) is my copy of the earlier upload, re-encoded at 720 px and flipped where the fact-check says the viral clip was, given one of four edits in turn in test-id order: flip, slow motion, zoom, compilation segment with synthetic filler. A case with no input stays in the test and is scored as not found. The controls are kind (a), fetched as posted.

n23 has a live viral repost (a Facebook reel of 2026-09-06), so it is kind (a). The others are kind (b): n22 flip, n24 slow motion, n25 zoom, n26 compilation, n27 flip, n28 slow motion, n29 zoom, n30 compilation, n31 flip. The segment of each kind (b) source is chosen from the fact-check's description of the viral clip.

## Frozen code and settings

- Code at commit `633704c`: `src/indexreel/trace.py`, `src/indexreel/geo.py`, `scripts/trace_inputs.py` and `scripts/score_trace.py`. The matcher and verifier are unchanged from `eval/trace.md`. The run uses that commit's code, exported to a git-ignored folder, so nothing committed later reaches it.
- Everything else is as in `eval/trace-v3.md` (sources, before-download rules, cost order, evidence image, dates, possible earlier source, corroboration), with the kept changes above. Keyframe search stays off. At most 10 candidates are fetched per recording.

## Quota and cost plan

- Trace makes at most 3 Data API searches per recording, so at most 42 for the 14 recordings here, and it stops that source at 100 a day.
- The test runs alone, on a fresh Pacific quota day: it starts at 07:05 UTC on Sun Nov 1, five minutes after midnight Pacific. No other Data API search runs that Pacific day.
- The run stops at **$3** (`--max-usd 3`), as in v3, which spent $1.06.
- The v2 resume rule applies unchanged if YouTube blocks downloads. No cookies, accounts, proxies or VPNs are used.

## Leak rule

As in `eval/trace-v2.md`: a confirmed copy passes when at least one source that found it is not leak-exposed. Web search is leak-exposed for a recording when any page it returned is excluded or carries a fact-check word in its title.

## Bars

As in `eval/trace-v3.md`, unchanged. A case is found when trace shows a confirmed copy that the platform dates on a UTC day strictly before the claimed date, the copy passes the leak rule, and the blind reviewer answers `same` to question (i) and to question (ii).

1. **No wrong statement (decisive).** Counted over every earlier confirmed copy in `trace.csv`, shown or not. A copy is wrong when it is a different recording (question (i) `different` or `cannot tell`, answered on its evidence image), dated on or after the claimed date, or dated by anything other than the platform. On a control, any earlier confirmed copy is wrong.
2. **Found on at least 40% of the test cases of each input kind**, rounded up: (2a) real re-uploads and (2b) my copies, each with its own k of n and Wilson 95% interval, never added together. A kind with fewer than 5 cases still gets its bar, marked as too small to read much into.

The run passes only if 1, 2a and 2b all pass. Copies confirmed through the geo rescue are counted and reported apart as well, but are scored like any other copy.

## Blind check

As in v2 and v3: the same separate reviewer answers two sheets, in separate folders with their own shuffle, row ids and case labels, and neither says which source found a row or which rows are controls. Sheet 2 (question ii) is given alone first. Sheet 1 (question i) is given only after sheet 2's answers are written. Answers are not changed after they are written. Scoring runs once, after both sheets. The score goes on the results page whatever it is.

## Reported

As in v3, plus the number of geo rescues tried and confirmed, and for each confirmed copy whether its evidence image was drawn from geo's line.

## Limits

- 10 test cases give a wide interval, and kind (a) rests on one case (n23).
- The kept changes were chosen on v1 to v3, where every recording has one member and most sources are on YouTube. v4 has more Facebook and Instagram sources, where trace found nothing in dev.
- The cards redrawn on geo's line in dev were checked by my eye only, never blind. The blind reviewer sees v4's cards for the first time.
- Verify can call an edited copy `different` when the edit adds something. A copy missed that way makes trace show a later copy, never a wrong one.
- Bars use the platform's UTC day, while claimed dates are local.
- Spark and YouTube may have seen the fact-checks; no rule removes that.
- Search results change from day to day, so a rerun would give different candidates.
- "Same recording" is one blind reviewer's judgement.

## Test commands, in order, once

1. Write `data/trace_v4_test/manifest.csv` for the test cases and controls, with the segment of each kind (b) source chosen from the fact-check's description.
2. `python scripts/trace_inputs.py data/trace_v4_test/manifest.csv --out data/trace_v4_test/in`
3. `indexreel match data/trace_v4_test/in --out data/trace_v4_test/run`
4. `python -m indexreel.claims data/trace_v4_test/run`, then I approve or reject the rows (for the page only).
5. At 07:05 UTC on Sun Nov 1: `indexreel trace data/trace_v4_test/run --claimed-dates data/trace_v4_test/in/claimed_dates.csv --max-usd 3 --cache data/trace_v4_test/cache`, with a new, empty cache, on the code exported at `633704c`.
6. The two blind sheets from `trace.csv` with `scripts/score_trace.py`, sheet 2 first, then the score once. FAIL rows are kept.
