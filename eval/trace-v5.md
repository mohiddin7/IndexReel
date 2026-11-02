# Trace v5: the geometric check, tested at last

Written Nov 2 2026. No clip of the new cases has been fetched, made, matched or run through trace. The commit that adds this file freezes the cases, the code, the settings, the quota plan, the cost cap and the bars. The test is then run once.

v4 kept two changes, the geo rescue of copies the matcher kept apart and the evidence image drawn on geo's line, but never tested them: in its exported code geo looked for the SSCD model next to its own file, where there was none, so every geo call failed (`eval/trace-v4-result.md`, Deviation). Commit `897669b` fixes that: geo now uses the model path trace is given, as the matcher does, with a test that runs geo from an exported copy with the model elsewhere. Nothing else in trace, the matcher or the verifier changed since v4. This test asks the v4 question again on cases trace has never seen, now with geo running.

## What is new since v4

- **The fix** (`897669b`): `geo.verify` takes the model path, and trace passes its own `--sscd-model` to it, for both the check on confirmed copies and the rescue.
- **An arming check** in the run script, from the exported code, just before the run: every module imports from the export, the model file loads, geo says `same` on one known pair from v4 (the n31 input against the upload `ihGNXh-J9Sk`, a mirrored copy; no network, no paid call), and the API keys are set. Any failure stops the run before it starts and is logged. On v4's export this check fails; on v5's it passes.

The rescue and the card are as pre-registered in `eval/trace-v4.md` ("Geo rescue", "Card on geo's line"), with their dev evidence there.

## Question

As in `eval/trace.md`: given one clip and the date it was claimed to show, does `indexreel trace` find an upload of the same recording that the platform dates before that claimed date, without reading fact-check pages, and without ever showing a wrong copy or a wrong date?

## Cases

**Test.** Run once.

| id | claimed as (claimed date) | earlier upload named by the fact-check | fact-check |
|---|---|---|---|
| n32 | a sudden flood in Peru (2026-07-20) | the Tierras Blancas river mudflow, Nasca, 2025-02-06, YouTube (a local news outlet), 2025-02-07; the viral item is a compilation | AFP Factual C62C29E |
| n33 | the Japan earthquake of 2026-04-20 (2026-04-21) | cars shaking in a shopping-centre car park in Toyama in the Noto earthquake, YouTube (a newspaper), 2024-01-01; the viral item is a compilation of four clips | AFP A8TY2CQ |
| n34 | a cloudburst over Swat, Pakistan (2025-08-02) | a downburst over Lake Millstatt, Austria, time-lapse, YouTube (the photographer), 2018-06-12 | AFP 72772CQ |
| n35 | a cold lava flood at Tumpak Sewu after a Semeru eruption (2025-11-20) | the Tumpak Sewu mudflow of 2024-01-31, YouTube (a news site), 2024-02-02; the viral item has two clips | AFP 84L36ZQ |
| n36 | a landslide in Tanjung Bungah, Penang, after the 2025 monsoon rains (2025-11-07) | a road collapse and sinkhole at Tanjung Bungah, Facebook reel (a local TV page), 2017-11-05 | AFP 83MZ6CX |
| n37 | the Indonesian earthquake near Manado (2026-04-02) | a room shaking in the Davao Oriental earthquake, Facebook reel (a news channel), 2025-10-10 | AFP A6X67NQ |
| n38 | Hurricane Milton in Florida (2024-10-10) | a tornado near Didsbury, Alberta, Facebook (the storm chaser who filmed it), 2023-07-01; the viral item is a compilation | AFP 36K37DM |
| n39 | the Canadian wildfires of July 2026 (2026-07-15) | a forest fire in Quebec in 2023, Instagram (the person who filmed it), 2023-06-25 | AFP C3AU9ZQ |
| n40 | Cyclone Arnab making landfall in Andhra Pradesh (2026-10-28) | the Odisha tornado of 2026-03-15, Instagram (a news page), 2026-03-16 | Factly, 2026-10-29 |
| n41 | the Japan earthquake of 2026-04-20 (2026-04-21) | shoppers in a shoe shop in Oyabe in the Noto earthquake, Instagram (the shopper who filmed it), 2024-01-01 | AFP A8PR6NQ |

None of these recordings or claimed events is in v1 to v4. Test ids go on from v4 (n32 on), so the scorer needs no change. n33 and n41 share a claimed event (the Japan earthquake of April 2026) but are different footage from different fact-checks. Claimed dates follow Clarification 2 of `eval/trace.md`: the date of the viral post the fact-check quotes. The earlier uploads are on YouTube (n32 to n35), Facebook (n36 to n38) and Instagram (n39 to n41). Four viral items are compilations or two-clip videos (n32, n33, n35, n38); for each, the input is the one clip whose earlier upload the fact-check names.

**How the cases were found.** As for v4: a research assistant searched fact-check sites for miscaptioned disaster, weather and accident videos whose fact-check names the earlier upload by a link, and checked each earlier upload live with metadata only (nothing downloaded). It left out political, military and rivalry cases and every recording and claimed event of v1 to v4. Of its ten picks I replaced two whose claimed events were in v4 (Hurricane Melissa, as n24; Anak Krakatau in September 2026, as n23) with two of its reserves (n32, n41). Nothing from these pages was used to build or tune trace.

**Controls** (true claims, so no copy dated before the claimed date can exist). New for v5, none seen by trace before:

| id | what it shows (claimed date) | post |
|---|---|---|
| k9 | a tornado near Fort Stockton, Texas (2026-10-14) | YouTube, a weather video channel, 2026-10-15 UTC (the evening of Oct 14 in Texas) |
| k10 | Super Typhoon Bavi making landfall in the Mariana Islands (2026-07-05) | YouTube, a news channel, 2026-07-06 UTC |
| k11 | hail and storm damage in Arizona (2026-10-21) | Instagram, a TV meteorologist, 2026-10-22 UTC |
| k12 | a flash flood in Hurricane, Utah (2026-10-22) | X, a storm chaser, 2026-10-22 UTC |

k10's claimed date is the UTC day landfall began (the morning of Jul 6 local time is Jul 5 UTC), so that a genuine upload dated Jul 5 UTC cannot count as a wrong statement through the time-zone gap.

Each control's claimed date is the event's day (k10's, its first UTC day), so a copy dated before it would be a wrong statement.

## Inputs

As in `eval/trace-v4.md`: kind (a) is a live post linked from the case's fact-check and dated on or after the claimed date, used as fetched. Kind (b) is my copy of the earlier upload, re-encoded at 720 px and flipped where the fact-check says the viral clip was, given one of four edits in turn in test-id order: flip, slow motion, zoom, compilation segment with synthetic filler. A case with no input stays in the test and is scored as not found. The controls are kind (a), fetched as posted.

n40 has live viral reposts on X dated on the claimed date, so it is kind (a), from the repost Factly lists fourth, beside the tornado it lists fourth. Factly does not say the order matches. So before matching I look at that clip: if it does not show the Odisha tornado as the fact-check describes it, n40 is made as kind (b) from its earlier upload instead, and the edits below shift by the same rule. The others are kind (b): n32 flip, n33 slow motion, n34 zoom, n35 compilation, n36 flip, n37 slow motion, n38 zoom, n39 compilation, n41 flip. The segment of each kind (b) source is chosen from the fact-check's description of the viral clip.

## Frozen code and settings

- Code at commit `897669b`: `src/indexreel/trace.py`, `src/indexreel/geo.py`, `scripts/trace_inputs.py` and `scripts/score_trace.py`. The run uses that commit's code, exported to a git-ignored folder, so nothing committed later reaches it. The model is passed by its full path.
- Everything else is as in `eval/trace-v4.md`. Keyframe search stays off. At most 10 candidates are fetched per recording.

## Quota and cost plan

- Trace makes at most 3 Data API searches per recording, so at most 42 for the 14 recordings here, and it stops that source at 100 a day.
- **The run is on Pacific quota day Nov 2, not a fresh one.** v3 and v4 each started five minutes after midnight Pacific so that nothing else had used that day's 100 search.list calls. v5 runs on Nov 2 instead, as soon as this file is committed and the inputs are made, so that its blind review and score are done in time for the submission. An unrelated bot pass that morning had used 11 calls, which leaves 89, against v5's most of 42, so the run cannot stall on quota as v2 did. Nothing else runs a Data API search from the start of the run until it ends. If the run goes past midnight Pacific, the rest of it counts against Nov 3, which is fresh.
- The run stops at **$3** (`--max-usd 3`), as in v3 and v4, which spent $1.06 and $1.36.
- The v2 resume rule applies unchanged if YouTube blocks downloads. No cookies, accounts, proxies or VPNs are used.

## Leak rule

As in `eval/trace-v2.md`: a confirmed copy passes when at least one source that found it is not leak-exposed.

## Bars

As in `eval/trace-v4.md`, unchanged. A case is found when trace shows a confirmed copy that the platform dates on a UTC day strictly before the claimed date, the copy passes the leak rule, and the blind reviewer answers `same` to question (i) and to question (ii).

1. **No wrong statement (decisive).** Counted over every earlier confirmed copy in `trace.csv`, shown or not. A copy is wrong when it is a different recording (question (i) `different` or `cannot tell`, answered on its evidence image), dated on or after the claimed date, or dated by anything other than the platform. On a control, any earlier confirmed copy is wrong.
2. **Found on at least 40% of the test cases of each input kind**, rounded up: (2a) real re-uploads and (2b) my copies, each with its own k of n and Wilson 95% interval, never added together. A kind with fewer than 5 cases still gets its bar, marked as too small to read much into.

The run passes only if 1, 2a and 2b all pass. Copies confirmed through the geo rescue are counted and reported apart as well, but are scored like any other copy.

## Blind check

As in v2 to v4: the same separate reviewer answers two sheets, in separate folders with their own shuffle, row ids and case labels, and neither says which source found a row or which rows are controls. Sheet 2 (question ii) is given alone first. Sheet 1 (question i) is given only after sheet 2's answers are written. Answers are not changed after they are written. Scoring runs once, after both sheets. The score goes on the results page whatever it is.

## Reported

As in v4: the number of geo rescues tried and confirmed, for each confirmed copy whether its evidence image was drawn from geo's line, and the number of geo errors (expected 0). If geo errors on more than a few pairs, the result says so first.

## Limits

- 10 test cases give a wide interval.
- The rescue and the card were chosen on v1 to v3, where every recording has one member and most sources are on YouTube. Six of the ten v5 sources are on Facebook or Instagram, where trace found nothing in v4 (8 of 9 kind (b) sources never became candidates). A rescue can only help when some earlier upload reaches the candidate list.
- Question (ii) shows the reviewer the text description of the original, not its frames. In v4 that cost two cases whose copy was right.
- The cards drawn on geo's line were checked in dev by my eye only. The blind reviewer sees them for the first time here.
- Verify can call an edited copy `different` when the edit adds something. A copy missed that way makes trace show a later copy, never a wrong one.
- Bars use the platform's UTC day, while claimed dates are local.
- Spark and YouTube may have seen the fact-checks; no rule removes that.
- Search results change from day to day, so a rerun would give different candidates.
- "Same recording" is one blind reviewer's judgement.
- n40's kind (a) input rests on Factly's list order; the rule above handles a mismatch before matching, never after.
- k9 is 15 minutes long, so its matching takes longer than the others'.
- The arming check's known pair comes from v4, whose score is final; it is used only to show geo can run, never scored.

## Test commands, in order, once

1. Write `data/trace_v5_test/manifest.csv` for the test cases and controls, with the segment of each kind (b) source chosen from the fact-check's description.
2. `python scripts/trace_inputs.py data/trace_v5_test/manifest.csv --out data/trace_v5_test/in`
3. `indexreel match data/trace_v5_test/in --out data/trace_v5_test/run`
4. `python -m indexreel.claims data/trace_v5_test/run`, then I approve or reject the rows (for the page only), through the page's audit path.
5. `sh data/trace_v5_test/run.sh`: the arming check, then straight away `indexreel trace data/trace_v5_test/run --claimed-dates data/trace_v5_test/in/claimed_dates.csv --max-usd 3 --cache data/trace_v5_test/cache --sscd-model <full path>`, with a new, empty cache, on the code exported at `897669b`.
6. The two blind sheets from `trace.csv` with `scripts/score_trace.py`, sheet 2 first, then the score once. FAIL rows are kept.
