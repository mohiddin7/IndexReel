# Trace v4 test: result

The protocol is `eval/trace-v4.md` (commit d9d96bc). The run used the code exported at `633704c` and nothing else. It ran once, on Nov 1 2026 from 07:06:19 to 09:33:04 UTC (exit 0), alone on a fresh Pacific quota day, with a new, empty cache. YouTube never asked for a sign-in, so the resume rule was not used. The blind sheets and the score come from the frozen `scripts/score_trace.py`. The reviewer answered sheet 2 first and sheet 1 only after it. Scoring ran once. Every row is kept below.

## Deviation: the geometric check never ran

I found this after the run, from its log. It is a fault in how I set the run up, not a change to the protocol, and the run is scored as it ran.

- **Cause.** `geo.py` finds the SSCD model at a path next to its own file. In the exported code that path is inside the export folder, where there is no model file. The `--sscd-model` setting reaches only the matcher, not geo. The dev replay ran from the working tree, where the file exists, so it never met this.
- **Effect.** All 42 geo calls failed with "file not found":
  - **Rescue:** 36 were rescue attempts on earlier candidates the matcher kept apart. Each returned at once, so 0 rescues were tried and 0 confirmed.
  - **Confirmed copies:** 6 were on the 6 confirmed copies, so each got `automatic` 0 (a copy to check by eye), as the AND rule says.
  - **Cards:** with no geo line, every evidence image was drawn the old way.
- **What this run did not test.** It did not test the geo rescue or the card drawn on geo's line, the two changes v4 was set up to measure. Its score shows trace with both changes inert. "Found" in the bars does not use `automatic`, so the 6 copies are scored like any other confirmed copy.

## Verdict: FAIL

| bar | result | |
|---|---|---|
| 1. No wrong statement (decisive) | **0 wrong statements**: the blind reviewer answered `same` to question (i) for all 6 earlier confirmed copies; no control had any confirmed copy | PASS |
| 2a. Found, real re-uploads | **0 of 1** (n23), needs 1, Wilson 95% 0.00-0.79; fewer than 5 cases, too small to read much into | FAIL |
| 2b. Found, my copies | **2 of 9** (n25, n31), needs 4, Wilson 95% 0.06-0.55 | FAIL |
| Secondary: found, counting leak-exposed sources | 2 of 10 | |

Trace showed nothing on any control, and every copy it confirmed was judged the same recording as the input. It found too few. Two cases had a right copy but failed question (ii). Six had no copy at all.

## Each test case

"Fetched" counts the candidates downloaded and matched. "Earlier" counts confirmed copies that the platform dates before the claimed date. (i) and (ii) are the blind reviewer's answers for each earlier copy. For kind (b), "source" is the upload I cut the input from, which is known for each case. I looked it up only after scoring, and no bar uses it.

| case | input | fetched | earlier | copy (posted) | (i) | (ii) | found | why not, or note |
|---|---|---|---|---|---|---|---|---|
| n22 | mine, flip | 10 | 1 | YouTube, 2022-05-15 | same | cannot tell | no | the copy is the source upload itself; the reviewer had only the text description to go by, and many people filmed that tornado |
| n23 | re-upload | 2 | 2 | YouTube, 2018-11-05 (shown); YouTube, 2019-11-03 | same, same | cannot tell, cannot tell | no | the shown copy is the upload the fact-check links; many people filmed that eruption and the description names no mark; stop-at-2 skipped the other 8 |
| n24 | mine, slow motion | 9 | 0 | - | | | no | the source (a YouTube Short) was never a candidate; 1 fetch failed on the network |
| n25 | mine, zoom | 10 | 1 | YouTube, 2024-08-21 | same | same | **yes** | another upload of the drone footage, same day as my source, which was never a candidate |
| n26 | mine, compilation | 8 | 0 | - | | | no | 8 earlier YouTube uploads fetched (5 from Dec 28-29 2023, around the source's date), all kept apart by the matcher; the source is a Facebook video; this is the kind of case the geo rescue was for, and it never ran |
| n27 | mine, flip | 10 | 0 | - | | | no | the source is a Facebook reel and was never a candidate |
| n28 | mine, slow motion | 10 | 0 | - | | | no | the source is a Facebook reel and was never a candidate |
| n29 | mine, zoom | 10 | 0 | - | | | no | the source is an Instagram post and was never a candidate |
| n30 | mine, compilation | 10 | 0 | - | | | no | the source is an Instagram post and was never a candidate; 1 candidate unavailable, 1 too long |
| n31 | mine, flip | 9 | 2 | YouTube, 2026-07-07 (shown); YouTube, 2026-07-07 | same, same | same, same | **yes** | two YouTube uploads of the CCTV, one inside a TV broadcast, both found by web search; the source is an Instagram reel |
| k5-k8 | controls | 10 each | 0 | - | | | | nothing confirmed, as it should be |

## Blind answers

Sheet 2 (question ii): 3 `same`, 3 `cannot tell`, 0 `different`. Sheet 1 (question i): 6 `same`. The reviewer's notes say this about some of the `same` answers:

- On the two n23 rows, "a second camera beside the first, filming the same explosion, would look much the same".
- On n25, the first of the three aligned moments showed two different frames; on one n31 row the first moment was slightly apart. In both, the second and third matched.

The answer files' hashes were checked before scoring (sheet 2 `1a938c5a...`, sheet 1 `79730f21...`).

## Reported

- **Cost:** $1.3628 of the $3 cap. Searches $0.834; verification $0.529 over 25 cached answers.
- **Data API searches:** 42, the pre-registered most for 14 recordings. Nothing else searched that Pacific day.
- **Candidates:** 3312 rows:
  - 128 fetched;
  - 3099 over the fetch cap;
  - 62 dated after the claim;
  - 9 skipped by stop-at-2 (8 on n23, 1 on n31);
  - 7 not a post (search pages, a playlist, profiles, a viral-video site);
  - 5 too long;
  - 2 fetch failures (1 network error, 1 video not available). No cookies were used.
- **Matching and verification:** the matcher joined 6 pairs. Verification answered `same` on 6 pairs and `different` on 13.
- **Geo rescues:** 36 attempts, 0 tried, 0 confirmed (see Deviation).
- **Evidence drawn from geo's line:** 0 of 6. All were drawn the old way.
- **`date_check`:** `id_agrees` on the 2 fetched TikTok candidates, empty on the 126 YouTube ones by design. Every confirmed copy is on YouTube.
- **Credit source:** 431 candidates, 3 fetched; it found no confirmed copy.
- **`possible_source` leads:** 0.
- **Corroboration**, next to the bars, never a bar: a date was corroborated for 3 of the 4 shown copies: n22 2022-04-29, n23 2018-10-24, n25 2024-08-17.

## Limits

As pre-registered in `eval/trace-v4.md`. Three more:

- The geo fault above means this run says nothing about the two changes v4 kept. Testing them needs a new pre-registration with fresh cases. Its setup should first check that the exported code can load every model file.
- Question (ii) shows the reviewer the text description of the original, not its frames. So `same` comes only when the event has one well-known recording or the candidate carries the uploader's mark. That cost n22 and n23, where the copy is the source upload or the upload the fact-check links. Bars 2a and 2b count them as not found, and that stands.
- A source that never became a candidate is a search miss: 8 of 9 kind (b) cases (only n22's source was a candidate), and 6 of those 8 sources are Facebook or Instagram posts, which the YouTube sources cannot reach.
