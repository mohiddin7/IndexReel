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
| `core_a_start_s`, `core_a_end_s` | the longest run of consecutive sampled frames along the alignment whose cosine is at least 0.4: where the two clips really match, inside `a_start_s`..`a_end_s`. Empty when no frame reaches 0.4 |
| `core_b_start_s`, `core_b_end_s` | the same run in `b` (its start is the start in `a` plus `offset_s`) |

Every unordered pair appears once. The sampled frame is the middle of each second, so frame `i` covers `[i, i+1)` seconds.

The aligned overlap (`a_start_s` to `b_end_s`) is at least half of the shorter clip, so for a short segment inside a longer clip it is wider than the segment. The core columns are the tight span; the compilation rule reads them.

## Evidence images

`frames/<pair_id>.jpg` exists for every `merged` or `unresolved` pair. It is 640 x 540 pixels: three rows and two columns of cells 320 x 180 pixels.

- The left column is clip `a`, the right column is clip `b`. A frame is fitted into its cell and padded with dark grey, so any aspect ratio keeps its shape.
- The three rows are the first, the middle and the last sampled frame of the overlap (`a_start_s` to `a_end_s`); on an overlap shorter than three frames some rows repeat. `evidence_a_s` lists the time in `a` of each row, in row order, separated by `;`. The time in `b` of the same row is that time plus `offset_s`.
- Each cell has the clip id and its time in the top left corner. The time is the middle of the sampled second (frame `i` is shown as `i + 0.5` s).
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

A recording is a connected component of the `merged` pairs. `status` is `unresolved` if any `unresolved` pair touches one of its clips, otherwise `merged` for two or more clips and `single` for one. `conflicts` lists `apart` pairs whose two clips are in the same recording: merging is not transitive, and the format keeps the contradiction instead of hiding it. Recordings are numbered `r1, r2, ...` in the order of their first clip in `clips.json`. `src/indexreel/cluster.py` computes this from `pairs.csv`.

## audit.jsonl

One JSON object per line, appended and never edited:

```
{"ts": "2026-10-29T14:03:11Z", "actor": "human", "action": "approve_merge", "pair": "a~b", "note": ""}
```

`action` is `approve_merge` (the pair becomes `merged`), `split` (the pair becomes `apart`) or `reset` (back to the computed band). Entries apply in file order; the last entry for a pair takes effect. Whoever shows or exports the clusters recomputes them from `pairs.csv` plus this file (`cluster.apply_audit`, then `cluster.recordings`); `clusters.json` holds the matcher's own result without human decisions.

## run.json

`{"version": 1, "command": "...", "created_utc": "...", "git_commit": "...", "n_clips": 8, "sample": "1 frame per second", "thresholds": {"merge_at": ..., "floor": ...}, "localiser": {"method": "opencv", "theta": 0.9}, "sscd_model_sha256": "..."}`

## Changing the format

A change adds a column or a key and raises `version` only when it removes or re-defines one. Readers ignore keys and columns they do not know.
