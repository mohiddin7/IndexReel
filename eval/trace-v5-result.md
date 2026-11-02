# Trace v5 test: result

The protocol is `eval/trace-v5.md` (commit 02542cf). The run used the code exported at `897669b` and nothing else. It started on Nov 2 2026 at 18:01:47 UTC after its arming check passed. It was killed at 19:50 UTC by a restart of the session it ran under, and resumed at 20:04:01 UTC with the same command, code and cache (see Deviations). It ended at 22:14:32 UTC (exit 0). YouTube never asked for a sign-in. The blind sheets and the score come from the frozen `scripts/score_trace.py`. The reviewer answered sheet 2 first and sheet 1 only after it. Scoring ran once. Every row is kept below.

## The geometric check, which v5 was run to test

This time geo ran on every call: 0 errors.

| what | result |
|---|---|
| Geo rescues of earlier candidates the matcher kept apart | **24 tried, 0 confirmed.** Geo answered `cannot tell` on all 24, so verify was never asked. |
| Geo on the 12 earlier confirmed copies | `same` on 5, `cannot tell` on 4, `different` on 3 |
| Automatic copies (verify `same` AND geo `same`) | 5 of 12. The blind reviewer answered `same` to question (i) on 4 and `cannot tell` on 1 (n34, `QyJG9sZbwOE`) |
| Copies left to check by eye (any other geo answer) | 7 of 12. The reviewer answered `same` on 6 and `cannot tell` on 1 (n35, `LpgWuFBcyhY`) |
| Geo `different` | 3 copies, all 3 judged the same recording by the reviewer. Geo's `different` was wrong each time; the AND rule kept them to check by eye, so it cost nothing but the automatic label |
| Evidence images drawn on geo's line | 5 of 12, the 5 geo `same` copies. Each stored image is byte for byte the one drawn on geo's line (checked after the run). The reviewer answered `same` on 4 and `cannot tell` on 1 (n34, `QyJG9sZbwOE`) |

So on fresh cases the rescue found nothing, and drawing the image on geo's line did not stop a wrong statement: one of the five such images, on a copy trace marked automatic, did not make the link plain.

## Verdict: FAIL

| bar | result | |
|---|---|---|
| 1. No wrong statement (decisive) | **2 wrong statements**: of 12 earlier confirmed copies, the blind reviewer answered `cannot tell` to question (i) for 2 (n34 `QyJG9sZbwOE`, n35 `LpgWuFBcyhY`, neither the copy shown) and `different` for none; no control had any confirmed copy | FAIL |
| 2a. Found, real re-uploads | **0 of 1** (n40), needs 1, Wilson 95% 0.00-0.79; fewer than 5 cases, too small to read much into | FAIL |
| 2b. Found, my copies | **1 of 9** (n34), needs 4, Wilson 95% 0.02-0.44 | FAIL |
| Secondary: found, counting leak-exposed sources | 2 of 10 (n34, n33) | |

Trace showed nothing on any control and never showed a copy the reviewer judged a different recording. Both wrong statements are copies trace confirmed but did not show: a small inset inside a news graphic or news video, where the image's aligned moments did not make the link plain.

## Each test case

"Fetched" counts the candidates downloaded and matched. "Earlier" counts confirmed copies that the platform dates before the claimed date. (i) and (ii) are the blind reviewer's answers for each earlier copy, the shown one first. "Source" is the upload I cut the input from; it was looked up only after scoring and is not used by any bar.

| case | input | fetched | earlier | copies (posted; geo) | (i) | (ii) | found | why not, or note |
|---|---|---|---|---|---|---|---|---|
| n32 | mine, flip | 5 | 2 | YouTube 2025-02-07 (shown; cannot tell); YouTube 2025-02-07 (same, automatic) | same, same | cannot tell, cannot tell | no | two other uploads of the Nasca mudflow, posted the day after it; the description of the original is generic, so (ii) could not tie them to it; the source was never a candidate |
| n33 | mine, slow motion | 2 | 2 | YouTube 2024-01-01 (shown; same, automatic); TikTok 2024-01-02 (different) | same, same | same, same | no (leak rule) | the shown copy is the source upload itself, but both copies were found only by web search, whose results for this recording were leak-exposed; counted in the secondary line only |
| n34 | mine, zoom | 2 | 2 | YouTube 2018-06-12 (shown; same, automatic); YouTube 2018-06-15 (same, automatic) | same, cannot tell | same, same | **yes** | the shown copy is the source upload itself; the second, a news video with the time-lapse as a small inset at another speed, is a wrong statement under bar 1 |
| n35 | mine, compilation | 2 | 2 | YouTube 2024-02-01 (shown; cannot tell); YouTube 2024-02-01 (cannot tell) | same, cannot tell | cannot tell, cannot tell | no | two uploads a day before my source; the second, a still inset in a news graphic, is a wrong statement under bar 1 |
| n36 | mine, flip | 5 | 2 | YouTube 2017-11-05 (shown; cannot tell); YouTube 2017-11-05 (different) | same, same | cannot tell, cannot tell | no | two YouTube uploads of the Penang sinkhole the day it happened; the source is a Facebook reel and was never a candidate |
| n37 | mine, slow motion | 10 | 2 | YouTube 2025-10-10 (shown; same, automatic); YouTube 2025-10-10 (different) | same, same | cannot tell, cannot tell | no | two uploads of the Davao room on the day of the quake; the source is a Facebook reel and was never a candidate |
| n38 | mine, zoom | 10 | 0 | - | | | no | the source is a Facebook video and was never a candidate |
| n39 | mine, compilation | 10 | 0 | - | | | no | the source is an Instagram post and was never a candidate |
| n40 | re-upload | 10 | 0 | - | | | no | the source is an Instagram post and was never a candidate; 5 candidates were too long |
| n41 | mine, flip | 10 | 0 | - | | | no | the source is an Instagram post and was never a candidate |
| k9-k12 | controls | 8-10 each | 0 | - | | | | nothing confirmed, as it should be |

## Blind answers

Sheet 2 (question ii): 4 `same`, 8 `cannot tell`, 0 `different`. Sheet 1 (question i): 10 `same`, 2 `cannot tell`, 0 `different`. The answer files' hashes were checked before scoring (sheet 2 `aeb62954...`, sheet 1 `0b455607...`). The reviewer's notes on the two `cannot tell` rows of sheet 1: n35's candidate "is a small still inset in a news graphic ... no moment matches"; n34's is "a small inset in a news video, from the same viewpoint", whose "time runs at a different rate" and whose third row is a black transition.

## Deviations

1. **The run was killed and resumed.** It ran as a background job of the session that started it; a restart of that session killed it at 19:50 UTC (the last write to its log), during the fourth of 14 recordings (control k9). The three other controls were done; no test recording had started. With the coordinator's yes, I ran the same command again at 20:04:01 UTC on the same code and cache, after the arming check passed again, detached from the session. v2's resume rule (`eval/trace-v2.md`) covers only a stop when YouTube asks for a sign-in, so this is a deviation, done that rule's way: no code, setting or cache entry changed between stop and resume. The first run's log is kept.
2. **The four recordings run twice did not come out identical, but their outcome did.** Searches and Spark answers came from the cache, and no Data API search was made after the resume. Two candidates whose download had failed with HTTP 403 in the first run (one on k11, one on k9) downloaded on the resume, because trace does not cache a failed fetch. That changed one of k11's three rescue checks and let k9 finish its rescues. Every rescue on those four recordings answered `cannot tell`, and none of them had a confirmed copy in either run.
3. **I read the partial log.** The resume rule says nobody looks at partial output. I read the first run's log to find out why it stopped. It held only the four controls: their candidates and 9 geo `cannot tell` answers. No test case had started.

## Reported

- **Cost:** $1.6281 of the $3 cap ($0.7254 before the kill, $0.9027 after). Searches $0.940; verification $0.688.
- **Data API searches:** 39, all before the kill, against the pre-registered most of 42, on Pacific day Nov 2, which an unrelated bot pass had used 11 of. Nothing else searched until the run ended.
- **Candidates:** 2754 rows: 104 fetched, 2575 over the fetch cap, 37 dated after the claim, 26 skipped by stop-at-2, 8 too long, 3 fetch failures (2 "video not available", 1 unavailable), 1 not a post.
- **Matching and verification:** the matcher joined 12 pairs and kept 92 apart. Verification answered `same` on 12 and `different` on 1.
- **`date_check`:** `id_agrees` on 4 fetched TikTok candidates, `editable` on 1 Facebook one, empty on the 99 YouTube ones by design. Every confirmed copy but one TikTok is on YouTube.
- **Credit source:** 240 candidates, 4 fetched; it found no confirmed copy.
- **`possible_source` leads:** 0.
- **Corroboration**, next to the bars, never a bar: a date was corroborated for 3 of the 6 shown copies: n33 2024-01-01, n34 2018-06-10, n37 2025-10-10.

## Limits

As pre-registered in `eval/trace-v5.md`. Three more:

- Question (ii) shows the reviewer the text description of the original, not its frames. Four cases (n32, n35, n36, n37) had copies the reviewer judged the same recording as the input on (i), but `cannot tell` on (ii). Bar 2b counts them as not found, and that stands.
- A source that never became a candidate is a search miss: 7 of the 9 kind (b) sources, all 5 on Facebook or Instagram among them. Trace instead found other uploads of the same footage for n32, n35, n36 and n37.
- n33's viral caption ended with a remark about another country; only its first sentence was used as the input's caption, as for v4's n22.
