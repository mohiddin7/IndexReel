# Run format (version 1)

`indexreel match <clips dir> --out <run dir>` writes one run directory. Later stages (a verifier, a viewer, a withdrawal analysis) read it and add to it; none of them re-reads the clips to learn what the matcher decided. This file fixes the format. A small example is in `tests/fixtures/run_fake/` and `tests/test_run_format.py` checks that it follows these rules.

```
run/
  run.json        how the run was made
  clips.json      one entry per clip
  pairs.csv       one row per unordered pair of clips
  clusters.json   recordings built from the pairs
  frames/         aligned evidence images, one per merged or unresolved pair
  audit.jsonl     human decisions, append only
```

All times are seconds from the start of the clip, written with at most three decimals. Paths in `clips.json` are absolute, or relative to the run directory.

## clips.json

```
{"version": 1, "clips": [
  {"id": "b01_T", "path": "...", "duration_s": 10.0, "fps": 25.0, "width": 1920, "height": 1080,
   "frames_sampled": 10,
   "crop": {"method": "opencv", "quad": [[x, y], [x, y], [x, y], [x, y]], "fallback_share": 0.0}}]}
```

`id` is the file stem and is unique; it contains no `~`. `crop.quad` is the median accepted quadrilateral over the sampled frames, in source pixels (clockwise from top left), or `null` when no localiser result was used (`method: "none"`). `fallback_share` is the fraction of sampled frames where the localiser found nothing and the whole frame was used.

A clip that came from a post has a `source` key (absent for a local file):

```
"source": {"platform": "x", "url": "https://x.com/example_account/status/1234567890123456789",
           "post_id": "1234567890123456789", "account": "example_account",
           "posted_at": "2026-10-27T11:00:00Z", "caption": "Two angles of one fireworks show #test",
           "fetched_utc": "2026-10-28T09:30:00Z"}
```

All keys are strings and always present, `null` where the post does not say. `platform` is `x` for twitter.com and x.com posts, otherwise the lowercase extractor name. `account` has no `@`. `posted_at` is UTC ISO 8601, or only the date if that is all that is known. `caption` is cut at 2000 characters. `indexreel match` copies the sidecar `<clip>.source.json` that sits next to the clip, unchanged; nothing else of the post is kept.

Optional key `credit` (a string, for example `"NASA footage"`): who made the footage, written by hand in the sidecar for clips made from public-domain or licensed sources. Absent otherwise; `indexreel fetch` never writes it. A page may show it next to the clip.

## Fetching posts

`indexreel fetch --out <clips dir> <post URL or text file of URLs>...` downloads the videos of the posts it is given with yt-dlp and writes `<id>.<ext>` and `<id>.source.json` into the clips directory. The id is `<yt-dlp extractor>_<post id>` (for example `twitter_1234567890123456789`); a post with several videos gives up to four clips. An existing clip is never overwritten, so ids stay unique in a directory.

- **Accepted URLs:** https post URLs on x.com or twitter.com (path contains `/status/`), at most 20 per call; other hosts only with `--allow-host`. Profile and search URLs, other schemes and URLs with user information are refused with exit code 2 before anything is downloaded.
- **No credentials:** yt-dlp runs with an argument list, `--ignore-config --no-netrc`, no cookies, `--max-filesize 300M`; only public posts can be fetched. The raw info yt-dlp writes (signed media URLs and more) is deleted after the fields above are taken from it.
- **Output**, one line per event on stdout: `fetch: ok <url> -> <file>`, `fetch: skip <url> already fetched as <id>`, `fetch: error <url> <code>: <message>` and a last line `fetch: done <n> ok, <n> skipped, <n> failed`. Codes: `bad_url`, `private_or_login`, `not_found`, `no_video`, `rate_limited`, `network`, `other`; the message is the first `ERROR` line of yt-dlp, cut to 200 characters.
- **Exit code:** 0 when nothing failed, 1 when at least one URL failed (the others were still fetched), 2 for a usage error or a refused URL.

## pairs.csv

Columns, in this order:

| column | meaning |
|---|---|
| `pair_id` | `a~b` with the two ids sorted; the key everything else uses |
| `a`, `b` | clip ids, `a < b` |
| `score` | SSCD best-match score (each sampled frame against its best frame in the other clip, averaged; both directions, one clip mirrored; the highest) |
| `aligned` | SSCD aligned score: the highest mean cosine along one constant time offset (see `eval/sscd-exploratory.md`, Addendum A) |
| `mirrored` | 1 if the best alignment needs one clip mirrored, else 0; the mirrored alignment must beat the plain one by 0.02, because SSCD scores differ by less than that when nothing is mirrored |
| `offset_s` | the offset of the best alignment: time in `b` minus time in `a` |
| `a_start_s`, `a_end_s` | the part of `a` the aligned frames cover |
| `b_start_s`, `b_end_s` | the same in `b` (`b_start_s = a_start_s + offset_s`) |
| `band` | `merged`, `unresolved` or `apart`, from the rule below |
| `evidence` | path of the evidence image relative to the run directory, empty when there is none |
| `evidence_a_s` | the times in `a` shown in that image, separated by `;` |
| `verify_verdict` | empty from the matcher; the verifier writes `same`, `different` or `abstain` |
| `verify_confidence` | empty; a number in [0, 1] |
| `verify_reason` | empty; one short sentence |
| `verify_cost_usd` | empty; cost of the verifier call for this pair |
| `verify_same_event` | added by the verifier after the other columns (readers that do not know it ignore it): the judge's `same_event` answer from the full-fidelity re-asks, `yes`, `no` or `unsure` (`unsure` when the two orders disagree); empty when the pair was only asked by the cheap prompt, which does not ask about the event. `same_event` yes with `verify_verdict` different reads as "same event, different footage" |
| `core_a_start_s`, `core_a_end_s` | the longest run of consecutive sampled frames along the alignment whose cosine is at least 0.4: where the two clips really match, inside `a_start_s`..`a_end_s`. Empty when no frame reaches 0.4 |
| `core_b_start_s`, `core_b_end_s` | the same run in `b` (its start is the start in `a` plus `offset_s`) |
| `cover_a`, `cover_b` | the share of each clip's sampled seconds that the other clip matches (see Partial copies), from 0 to 1 |
| `cover_a_start_s`, `cover_a_end_s`, `cover_b_start_s`, `cover_b_end_s` | where that match lies in each clip; empty when nothing matches |

Every unordered pair appears once. The sampled frame is the middle of each second, so frame `i` covers `[i, i+1)` seconds.

The aligned overlap (`a_start_s` to `b_end_s`) is at least half of the shorter clip, so for a short segment inside a longer clip it is wider than the segment. The core columns are the tight span; the compilation rule reads them.

## Evidence images

`frames/<pair_id>.jpg` exists for every `merged` or `unresolved` pair. It is 640 x 540 pixels: three rows and two columns of cells 320 x 180 pixels.

- The left column is clip `a`, the right column is clip `b`. A frame is fitted into its cell and padded with dark grey, so any aspect ratio keeps its shape.
- The three rows are the first, the middle and the last sampled frame of the overlap (`a_start_s` to `a_end_s`); on an overlap shorter than three frames some rows repeat. `evidence_a_s` lists the time in `a` of each row, in row order, separated by `;`. The time in `b` of the same row is that time plus `offset_s`.
- Each cell has the clip's label and its time in the top left corner. The label is `post N` for a clip from a post (N is its place in `clips.json`, from 1, as the wall page names it), otherwise the clip id, shortened to its first and last 10 characters around `..` when longer than 22. The time is the middle of the sampled second (frame `i` is shown as `i + 0.5` s).
- Each cell shows the frame the matcher scored, after localisation: rectified to 640 x 360 where the localiser accepted a quadrilateral, otherwise the whole frame. When `mirrored` is 1 the left cell is flipped left to right, so that it reads like the right one.

The example in `tests/fixtures/run_fake/` uses placeholder pictures in the same layout.

## Bands

With two thresholds `merge_at` and `floor` (written to `run.json` and `clusters.json`):

- `merged`: `aligned >= merge_at`.
- `apart`: `aligned < floor` and `score < merge_at`.
- `unresolved`: everything else. This includes a pair whose best-match `score` is high but whose frames do not line up in time.

`merge_at` is the smallest value with no false merge among the dev negatives; `floor` was chosen on dev. How both were set is in `eval/match-thresholds.md`. The verifier is meant to work on the `unresolved` pairs.

## Effective bands

Once the verifier has filled `verify_verdict`, a pair counts as the band below (`cluster.effective_band`); with an empty verdict it counts as its `band`.

| `band` | `verify_verdict` | counts as |
|---|---|---|
| merged | empty or `same` | merged |
| merged | `different` or `abstain` | unresolved |
| unresolved | `same` | merged |
| unresolved | `different` | apart |
| unresolved | `abstain` or empty | unresolved |
| apart | anything | apart |

A merged pair the verifier doubts goes back to a person instead of staying merged or becoming apart: the two stages disagree. Recordings, `conflicts` and `status` are computed on effective bands, and the audit is applied on top of them.

## clusters.json

```
{"version": 1, "thresholds": {"merge_at": 0.54, "floor": 0.30, "score_used": "aligned"},
 "recordings": [{"id": "r1", "members": ["a", "b"], "status": "unresolved",
                 "evidence_pairs": ["a~b"], "unresolved_pairs": ["b~c"], "conflicts": []}]}
```

A recording is a connected component of the `merged` pairs. `status` is `unresolved` if any `unresolved` pair touches one of its clips, otherwise `merged` for two or more clips and `single` for one; a compilation (below) is `compilation`. `conflicts` lists `apart` pairs whose two clips are in the same recording: merging is not transitive, and the format keeps the contradiction instead of hiding it. Recordings are numbered `r1, r2, ...` in the order of their first clip in `clips.json`. `src/indexreel/cluster.py` computes this from `pairs.csv`.

`clusters.json` also holds `"compilations": [...]` (empty, or absent in older runs) as described in the next section.

## Compilations

A clip made of consecutive pieces of several recordings links to each of them, and every link is correct for its piece, yet approving them together would join recordings that have nothing in common. `cluster.resolve` therefore looks for clips whose links reach different recordings over different parts of their own timeline.

- A pair's core span in a clip (`core_*` columns) is where the two clips match. A clip's *stretches* are the groups of its merged or unresolved pairs whose core spans (at least 2 s long) overlap by more than 0.5 s, strongest pair (`aligned`) first; copies of one recording match the same stretch. Core spans lie on the 1 s sampling grid.
- A clip with two or more stretches is a candidate. Its partners are grouped into sources by the merged links that do not touch a candidate; stretches that reach a common source count as one. The clip is a **compilation** when its stretches reach two or more sources. A jump cut of one recording reaches one source twice and is not one. Candidates are confirmed one at a time, most stretches first, and a confirmed compilation is not evidence for another clip; each confirmed clip is then checked again against the final graph.
- A detected compilation is only a **suggestion** until a person confirms it. While it stands, recordings are exactly as if the rule did not exist (the clip is joined to its sources by its merged links), except that the recording holding the clip has `status` `unresolved`, because a decision is needed. The suggestion is listed in `clusters.json` under `compilation_suggestions` (key absent when there are none).
- **Confirming** (audit action `confirm_compilation`) makes the clip's links to its sources, merged or unresolved, `partial`: they join nothing and do not count as undecided. The clip is a recording of its own with `status` `compilation`, and appears in `compilations`. **Dismissing** (`dismiss_compilation`) drops the suggestion and leaves the clip joined as it was. The last entry for a clip counts; an entry for a clip that is not suggested does nothing.

```
{"clip": "v_upload", "recording": "r4",
 "segments": [{"recording": "r2", "clips": ["q_cam"], "links": ["q_cam~v_upload"], "start_s": 0, "end_s": 2}, ...]}
```

`compilations` and `compilation_suggestions` hold entries of this shape. `start_s` and `end_s` are in the compilation's own timeline, segments are in time order, `clips` are the source clips of the segment and `recording` is the recording holding the first of them (while the suggestion stands this can be the same recording for every segment, since nothing is separated yet). The rule runs after the verifier and after the audit, so approving every link of a clip that is a confirmed compilation does not join its sources; a person can still split or approve a link between the sources themselves.

`cluster.resolve_all(clip_ids, rows, audit)` returns `(recordings, compilations, suggestions)`; `cluster.resolve` returns the first two, which with no `confirm_compilation` entry means a run without any compilation.

The constants (core cosine 0.4, at least 2 s, overlap 0.5 s) were set on the build split of `eval/compilation.md`. `tests/fixtures/run_fake_compilation/` is an invented run with one compilation of three recordings.

## Partial copies

A clip that holds part of a recording followed or preceded by footage the run does not have (another recording that was never posted) links to that recording over part of its timeline. The compilation rule cannot see this, since it needs two sources in the run; joining the two would count the clip as a copy.

- `cover_a` and `cover_b` say how much of each clip the other one matches. The offset used is the one with the most sampled frames at cosine 0.4 or more along it (closest to `offset_s` on ties; a nearly static scene leaves the aligned offset undecided). A frame counts when it reaches 0.4 against a frame of the other clip within 2 frames of that offset, so dips, re-films and jump cuts do not cut the span short. Each span runs from the first to the last counted frame, but no longer than the other clip's span moved by the offset (in slow footage the frames next to a shared stretch still match within 2 frames).
- A pair that counts as merged after the verifier and the audit is **partial** when both covers are below 0.8: neither clip lies mostly inside the other, so they share footage rather than being copies. A clip with a partial pair and no merged pair covering 0.8 of it holds footage no link explains; every merged pair of that clip is partial too, so a short clip that lies inside it does not make it a copy either. Clips of a detected compilation (suggested, confirmed or dismissed) keep the compilation rule instead. Unresolved pairs stay unresolved, whatever their covers: a link nobody has checked is not a claim of shared footage. Approving a partial pair (`approve_merge`) does not join the recordings; `split` makes it apart.
- A partial pair joins nothing and is not undecided. The recording of each of its clips carries `"partial": {clip: segments}` in the compilations' segment shape: one segment per other recording that clip shares footage with (a partial pair whose clips other merged pairs already join names nothing), `start_s` and `end_s` in that clip's own timeline (from the cover spans), `clips` and `links` the partners and pairs. Both clips of a partial pair get an entry, because the run cannot tell which of them is the source of the shared stretch. The key is absent on recordings without partial pairs, and runs without the cover columns have none.
- Withdrawing a recording r loses the stretch of every cited clip whose `partial` entry names r (listed as `lost_spans`); the clip's own recording still supports the claim.

```
{"id": "r4", "members": ["x"], "status": "single", ...,
 "partial": {"x": [{"recording": "r2", "clips": ["o", "p"], "links": ["o~x", "p~x"], "start_s": 0, "end_s": 7}]}}
```

The constants (band 2 frames, share 0.8) were set on the build split of `eval/partial.md`. By design the rule over-counts two trims of one recording that overlap only partly when no clip in the run holds both, and a clip that holds a whole recording plus other footage still merges with it unless it also has a partial pair.

## audit.jsonl

One JSON object per line, appended and never edited:

```
{"ts": "2026-10-29T14:03:11Z", "actor": "human", "action": "approve_merge", "pair": "a~b", "note": ""}
```

`action` is `approve_merge` (the pair becomes `merged`), `split` (the pair becomes `apart`) or `reset` (back to the computed band). Decisions about a clip carry `"pair": null` and `"clip": "<id>"`: `confirm_compilation` or `dismiss_compilation` (see Compilations). Decisions about a row of `claims.csv` carry `"pair": null`, `"clip": "<id>"` and `"claim": "<claim_id>"`: `approve_claim`, `reject_claim` or `reset_claim` (back to `suggested`); the page also writes the new `status` into that row of `claims.csv`, which stays the sheet readers use. `cluster` ignores these lines. Entries apply in file order; the last entry for a pair takes effect. Whoever shows or exports the clusters recomputes them from `pairs.csv` plus this file with `cluster.resolve(clip_ids, rows, audit)`, which returns the recordings and the compilations; `clusters.json` holds the matcher's own result without human decisions (`resolve` with an empty audit).

## claims.csv

`indexreel claims <run dir> [--max-usd 0.10]` asks Muse Spark (the verify stage's client, text only) which claims the captions in `clips.json` (`source.caption`) make about their footage, and writes `claims.csv`, one row per claim and citing clip:

| column | meaning |
|---|---|
| `clip` | the citing clip's id |
| `claim_id` | `c1`, `c2`, ...: one id per claim; a claim several captions make has one id and one row per citing clip (the grouping is Spark's) |
| `claim_text` | the claim as a short neutral sentence |
| `quote` | the words of that clip's caption that make the claim, an exact substring of it |
| `status` | `suggested` when written; a person approving or rejecting a row sets it (`approved`, `rejected`) |

- Only claims about what the footage shows: where, when, what happens. Remarks about the post itself (test notices, source credits, links, hashtags, how it was edited or re-filmed) are left out by the prompt.
- A citation whose `quote` is not an exact substring of that clip's caption is dropped and logged (`claims: dropped ...`); a claim left with no citation is not written. This is checked in code, whatever the model answers.
- Clips without a caption make no claims; a run with no caption makes no request and writes only the header.
- One request covers every caption of the run, at minimal reasoning effort and at most 4,000 output tokens. It is made only if its worst case (every output token used) is within `--max-usd`; otherwise nothing is written. It is made once: an answer that does not complete (for example cut off at the token cap) ends with `claims: the request ended <status>, cost ...; no claims written, nothing cached` and is not asked again. The answer is cached by model, prompt and captions (`~/.cache/indexreel/claims`), so a rerun costs nothing and needs no key. The last line is `claims: spent $X now; the answer used cost $Y at list prices`.
- `withdraw` (the command and the wall page alike) counts only rows with `status` `approved` when the sheet has a `status` column, and says how many rows it skipped; a hand-written sheet without the column counts every row. Approval is per row: a claim cited by two posts is supported only through its approved rows.

## trace.csv

`indexreel trace <run dir> [--claimed-dates FILE] [--max-usd 1]` looks for earlier uploads of each recording and writes `trace.csv`, one row per candidate post, plus a work folder `trace/<recording>/`. The rules it follows are in `eval/trace.md` and `eval/trace-v2.md`. It never says a claim is true or false.

| column | meaning |
|---|---|
| `recording` | recording id from `clusters.json` (after human decisions) |
| `input` | the recording's clip that was searched for (its first member) |
| `source` | `credit` (a post linked, or a YouTube channel named by @handle, in the description of a YouTube copy posted on or after the claimed date; a description that reads like a fact-check gives nothing), `web` (Spark with web search), `keyframe` (Cloud Vision web detection on the input's keyframes), `channel` (YouTube search inside the channel Spark named as the likely first source), `ytapi` (YouTube Data API search for uploads before the claimed date) or `youtube` (YouTube search); every source that found the post, joined with `+` (for example `web+youtube`) |
| `query` | the YouTube query that found it; empty for `web` and `keyframe` |
| `url` | the candidate post |
| `platform`, `post_id`, `account`, `posted_at` | from the fetched post's sidecar (see Fetching posts); `posted_at` is the platform's own post time |
| `fetch` | `ok`, `error <code>` (codes as in Fetching posts), `excluded` (a fact-checking site or web archive), `not_a_post` (not a post on YouTube, X, TikTok, Instagram, Facebook, Reddit or Vimeo), `over_cap` (more than 10 candidates), `after_claim` (the platform dates it on or after the claimed date, read before download), `too_long` (longer than 30 minutes, read before download; a longer video that gets through fails with `error other`), `same_post_as_input`, `unavailable` (the YouTube Data API does not return the video: deleted or private), `enough_copies` (fetched, but not matched or verified, because two earlier copies dated before it were already confirmed) |
| `clip` | the fetched candidate's id in `trace/<recording>/clips/` |
| `duration_s` | the fetched video's length |
| `cut_start_s`, `cut_end_s`, `coarse` | for a candidate longer than 90 s: the stretch it was cut to before matching (a coarse pass at one frame every 4 s finds the stretch most like the input, plus the input's length and 15 s on each side) and the coarse pass's best cosine; empty otherwise. Times in the evidence are relative to the cut |
| `band` | the effective band of the pair (input, candidate), from `indexreel match` and the verify stage run on those two clips alone (`trace/<recording>/pairs/<clip>/run/`) |
| `verify_verdict` | the verifier's verdict on that pair, empty when it was not asked |
| `evidence` | an evidence image relative to the run directory: `trace/<recording>/pairs/<clip>/core.jpg`, three aligned frame pairs from inside the pair's core span (or, when that is under 6 s, the most detailed frame of each third of the cover span), the input always on the left, labelled `input` and `candidate` with their times. Black bars are trimmed; when one side shows only part of the other (a zoom or crop), the wider side is cropped to that view and labelled `cropped`; an input shown mirrored is labelled `mirrored`; when the pair has no core span, the matcher's own image, with its halves swapped if needed so the input is on the left (`trace/<recording>/pairs/<clip>/matcher.jpg`) |
| `confirmed` | 1 when `band` is `merged`, else 0 |
| `earlier` | 1 when the platform dates the post on a UTC day before the claimed date, 0 when not; empty when the post has no platform date (yt-dlp's generic extractor or no date) or no claimed date is known |
| `leak_exposed` | 1 when any page the web or keyframe search returned for this recording was on a fact-checking site or web archive, or had a fact-check title (`trace/<recording>/search_hits.json` lists them, by source) |
| `shown` | 1 on the earliest confirmed copy with `earlier` 1; at most one row per recording |
| `claimed_date` | the recording's claimed date (see below), the same on every row of a recording; empty when none is known |
| `leak_copy` | 1 when every source that found this post (web, keyframe) also returned a fact-checking page for this recording: the copy fails leak rule 2 (`eval/trace-v2.md`). Trace does not know which page led to a post, so this does not say the post was found through a fact-check |
| `prerank` | SSCD similarity of YouTube's own preview frames of the post to the input's frames, used to order YouTube results before download; empty for posts not on YouTube |
| `families` | the source families that found the post: `credit`, `web`, `keyframe`, `youtube` (`channel`, `ytapi` and `youtube` together), joined with `+` |
| `strength` | on the shown row only: `strong` when two families found it, or when the date search below gives a date on or before its post date, cited by at least two sites; else `single-source` |
| `corroborated_date` | on the shown row only: the date of the footage's event from a separate web search, when it counts as corroboration; else empty |
| `corroboration_urls` | on the shown row only: the pages that search cited, separated by spaces. Fact-check pages may be among them; they never find candidates |
| `date_check` | `id_agrees` or `id_differs` when the post id itself carries its post time (X, TikTok and Instagram ids do) and is within a day of `posted_at` or not; `editable` for Facebook and Vimeo, where a post's date can be changed or its video replaced later; else empty. A copy whose id differs from its date is never `earlier` |

- The claimed date of a recording is the earliest date in `--claimed-dates` (CSV `clip, claimed_date`) for its clips, else the earliest `posted_at` of its clips.
- Search reads only what the recording's clip shows. No claim, caption or post text goes into it: a claim may be false in its event, place or date, and searching for it pulls in material about the claimed event (`eval/trace.md`, Amendment A). The claims stay in `claims.csv` and on the page, beside the earliest copy.
- The YouTube Data API and keyframe sources need my Google API key in `IndexReel_Trace_API_KEY_GCP`; without it, or after a quota or HTTP error, they are skipped for the run and the log says so. Vision requests are counted in `~/.cache/indexreel/vision_requests.json` and stop at 25 a day and 300 in total. Data API searches (`search.list`) have their own Google bucket of 100 calls a day, reset at midnight Pacific time; trace counts them in `~/.cache/indexreel/ytapi_searches.json`, says at the start how many are left, and stops that source at 100. Each recording uses up to 3.
- Spark answers, YouTube searches, Google answers, preview-frame scores and post dates are cached (`~/.cache/indexreel/trace`), so a rerun costs nothing. A Spark request is made only while enough of `--max-usd` is left for it; each candidate is verified only while $0.05 is left beyond $0.05 kept back for each recording still to come (its date search). Every recording's search runs before any matching. Fetched candidates are matched and verified earliest post first, and a recording's matching stops once two earlier copies are confirmed. The last lines are `trace: <n> candidates, <n> confirmed copies, <n> shown; spent $X now` and one `trace: <recording>: earliest confirmed copy <url> posted <time> on <platform>` per shown row.

## run.json

`{"version": 1, "command": "...", "created_utc": "...", "git_commit": "...", "n_clips": 8, "sample": "1 frame per second", "thresholds": {"merge_at": ..., "floor": ...}, "localiser": {"method": "opencv", "theta": 0.9}, "sscd_model_sha256": "..."}`

## Changing the format

A change adds a column or a key and raises `version` only when it removes or re-defines one. Readers ignore keys and columns they do not know.
