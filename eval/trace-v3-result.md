# Trace v3 test: result

The protocol is `eval/trace-v3.md` (commit de5a7bf), with Clarification C1 (79f3346) and Amendment 1 (f2f7592). The run used the code exported at `70fc6f7` with `src/indexreel/fetch.py` from `9b8204b` and nothing else. It ran once, on Oct 31 2026 from 07:07:31 to 09:14:02 UTC (exit 0), alone on a fresh Pacific quota day, with a new, empty cache. YouTube never asked for a sign-in, so the resume rule was not used. The blind sheets and the score come from the frozen `scripts/score_trace.py`. The reviewer answered sheet 2 first and sheet 1 only after it. Scoring ran once. Every row is kept below.

## Verdict: FAIL

| bar | result | |
|---|---|---|
| 1. No wrong statement (decisive) | **1 wrong statement**: of 7 earlier confirmed copies, the blind reviewer answered `cannot tell` to question (i) for 1 (n13) and `different` for none; no control had any confirmed copy | FAIL |
| 2a. Found, real re-uploads | **0 of 1** (n21), needs 1, Wilson 95% 0.00-0.79; fewer than 5 cases, too small to read much into | FAIL |
| 2b. Found, my copies | **2 of 9** (n12, n19), needs 4, Wilson 95% 0.06-0.55 | FAIL |
| Secondary: found, counting leak-exposed sources | 2 of 10 | |

Trace showed nothing on any control and never showed a copy the reviewer judged a different recording. The one wrong statement is an evidence image that did not show the link. By construction, the copy behind it is the very video my n13 input was cut from (below).

## Each test case

"Fetched" counts the candidates downloaded and matched. "Earlier" counts confirmed copies that the platform dates before the claimed date. (i) and (ii) are the blind reviewer's answers for the copy trace showed. For kind (b), "source" is the upload I cut the input from, which is known for each case. It was looked up only after scoring and is not used by any bar.

| case | input | fetched | earlier | copy shown (posted) | (i) | (ii) | found | why not, or note |
|---|---|---|---|---|---|---|---|---|
| n12 | mine, flip | 2 | 2 | YouTube, 2020-06-04 | same | same | **yes** | both copies predate the source upload (2020-06-05), which was a candidate and was skipped by stop-at-2 |
| n13 | mine, slow motion | 10 | 1 | YouTube, 2021-01-10 | cannot tell | cannot tell | no | the copy is the source upload itself, but none of the image's three aligned moments showed the same shot: the wrong statement of bar 1 |
| n14 | mine, zoom | 2 | 2 | YouTube, 2020-07-28 | same | cannot tell | no | the copy is the source upload itself; question (ii) had only the text description of the original to go by |
| n15 | mine | 8 | 0 | - | | | no | the source is a Facebook video and was never a candidate |
| n16 | none | 0 | 0 | - | | | no | no input (Clarification C1) |
| n17 | mine, flip | 10 | 1 | YouTube, 2023-06-21 | same | cannot tell | no | a TV package with the same footage; the source is an Instagram reel and was never a candidate |
| n18 | mine, slow motion | 10 | 0 | - | | | no | the source (a YouTube Short) was never a candidate |
| n19 | mine, zoom | 10 | 1 | YouTube, 2022-07-29 | same | same | **yes** | found by web search, the channel source and the credit source together |
| n20 | mine, compilation | 10 | 0 | - | | | no | the source was a candidate but past the 10-fetch cap |
| n21 | re-upload | 10 | 0 | - | | | no | the source is a Facebook post and was never a candidate |
| k1-k4 | controls | 9-10 each | 0 | - | | | | nothing confirmed, as it should be |

## The wrong statement (n13)

The input is 20 s of the source upload, slowed. Trace fetched that very upload, the matcher joined the pair, and verification answered `same`. The image's three aligned moments did not show the same shot, and the third came from a different camera position. Under the bars that is a wrong statement, and it stands. The link was right but the image did not show it: the same kind of failure as v2's 4 wrong statements, now on a slow-motion copy. I have not looked into why the aligned moments missed.

## Reported

- **Cost:** $1.0585 of the $3 cap. Searches $0.895 over 31 requests; verification $0.163 over 9 answers.
- **Data API searches:** 39, the pre-registered most for 13 recordings. Nothing else searched that Pacific day.
- **Candidates:** 2420 rows; 110 fetched, 2174 over the fetch cap, 85 dated after the claim, 25 too long, 13 skipped by stop-at-2 (`enough_copies`, on n12 and n14).
- **Fetch failures:** 7, each on its own: 4 "video not available", 2 age-gated (no cookies were used), 1 HTTP 403. None was a leftover format part.
- **Matching and verification:** the matcher joined 7 pairs and kept 103 apart. Verification answered `same` on all 7.
- **`date_check`:** `id_agrees` on 2 fetched TikTok candidates, empty on the 108 YouTube ones by design. Every confirmed copy is on YouTube.
- **Credit source:** 142 candidates (89 on n19), 4 fetched. It was one of the three sources that found n19's copy.
- **`possible_source` leads:** 0.
- **Corroboration**, next to the bars, never a bar: a date was corroborated for 3 of the 5 shown copies: n12 2020-06-03 (the slide's date), n14 2020-07-27, n17 2023-06-19.

## Limits

As pre-registered in `eval/trace-v3.md`. Two more:

- Question (ii) shows the reviewer the text description of the original, not its frames. So `same` comes only when the event has one well-known recording or the candidate carries the uploader's mark. That cost n14, where the shown copy is the source upload itself, and n17. Bar 2b counts them as not found, and that stands.
- A source that never became a candidate (n15, n17, n18, n21) is a search miss. Three of the four are Facebook or Instagram posts, which the YouTube sources cannot reach.
