# Partial copies: a clip that holds only part of a recording must not join it

Written Oct 28 2026, before any partial-copy rule exists in code and before the test split has been run through anything. Generator: `scripts/make_partials.py`. Run format: `eval/run-format.md`. Matcher and thresholds: `eval/match-thresholds.md` (`merge_at` 0.55, `floor` 0.20, unchanged here).

## Problem

A recording is a connected component of merged pairs. The compilation rule (`eval/compilation.md`) keeps a clip made of several recordings from joining them, but only when at least two of those recordings are in the run. Real piles often lack the other source. In my first run on real posts (six test posts on X), one post was cut from the last 7 s of a second post's video followed by 7 s of another recording that was never posted. Its link to the second post (aligned 0.80, core span 0 to 7 s of its 14 s) merged it into that post's recording as if it were a copy, so the run counted 3 recordings where there are 4.

## What counts as a partial copy

A clip in which a stretch is a copy of part of one recording, and the rest is footage of recordings that are not in the run. The rest can come before, after or on both sides of the copied stretch.

Not partial copies:
- a trim (the clip is a stretch of one recording and nothing else), including a jump cut;
- a full copy with overlays, captions, reframing, an inset, a letterbox, or a re-film;
- a clip that contains a whole recording plus other footage (a *container*). From one pair this looks the same as an original and its trim, so this test does not ask the rule to catch it; it is reported.

## Hypothesis

A merged link whose core span covers only part of *both* clips (neither clip lies mostly inside the other) shows shared footage, not a copy. Recording such a link as "clip x contains footage of recording r over a to b s" instead of joining the two recordings fixes the case above. It does not change anything for full copies, trims and re-films, because in each of those at least one clip of the pair is covered almost entirely.

## Rule to be built (the form is fixed now; constants are set on the build split)

- `indexreel match` adds two columns to `pairs.csv`: `cover_a` and `cover_b`, the share of each clip's duration covered by the pair's match along its best alignment (a run of frames at cosine 0.4 or more, as for the `core_*` columns, allowing gaps of at most `G` frames below it), capped at 1. Nothing else in `pairs.csv` changes.
- A link is **partial** when, after the verifier and the audit, it counts as merged, neither clip is a detected compilation (suggested, confirmed or dismissed; those keep the compilation rule's behaviour), and both `cover_a` and `cover_b` are below `SHARE`.
- A partial link joins nothing and is not undecided. Each clip with partial links gets, on its recording in `clusters.json`, a `partial` entry `{clip: segments}` in the same shape as a compilation's segments: one segment per recording it shares footage with, with the span in that clip's own timeline. Both clips of a partial link get one, since the run cannot tell which of them is the source of the shared stretch.
- An unresolved link stays unresolved, whatever its cover: a link nobody has checked must not become a claim of shared footage. A person who approves it (`approve_merge`) makes it merged, and the rule then applies, so approving a partial link does not join the two recordings either. `split` makes it apart as before.
- Withdraw: withdrawing recording r loses the stretch of every cited clip whose `partial` entry names r, the way it loses a compilation's span; the clip's own recording still supports the claim.
- Old runs without the cover columns have no partial links.

To be set on the build split only: `SHARE` (grid 0.6, 0.7, 0.75, 0.8, 0.85, 0.9) and `G` (0 to 3). If on the build split partial copies rejoin their family through a third clip (for example a short trim that lies inside the copied stretch), I may add one extension that cuts such links; it must be committed before the test run.

## Test material (dev only)

Sources are the 8 dev originals the matcher was tuned on: `data/gate_run/in/dev/{T01..T04,N01..N04}__orig.mp4` (640×360, 5 fps, 10 s, silent). Filler is footage from my own phone clips in `data/iphone_by_me/`, cut to 640×360 at 5 fps; none of it is a clip of any run, so it stands for a recording the run does not hold. Each split has its own filler clips (build: IMG_2851, 2854, 2858, 3647, 3800, 3821, 4018; test: IMG_4084, 4138, 4436, 6171, 7309, 9427, 9458). The final splits, the gate split, `data/compilation/test` and the held-out sets are not used.

`scripts/make_partials.py <split>` writes `data/partial/<split>/<id>.mp4` and `truth.csv`:

- **Partial copies.** One segment of one original, 3, 5 or 7 s long (in rotation), starting at a random frame, with filler after, before or on both sides (in rotation). The filler totals 0.4 to 1.6 times the segment, so the segment is about 38% to 71% of the copy. One variation each, in rotation: plain, caption (burned-in subtitle), letterbox (9:16 frame with a blurred fill), inset (40% size on a grey canvas).
- **Controls, single recording.** Trims (one piece of 4 to 8 s) and jump cuts (two pieces of 2.6 to 3.4 s with a gap of 1 to 2 s), made as in `eval/compilation.md`, same variations.
- **Containers.** A whole original with 3 to 6 s of filler before or after. Reported, not scored.
- **Real re-films.** The phone re-films of the dev clips in `data/refilmed/clips/` (one continuous take of a monitor per playlist; each take was filmed twice, tight and with the bezel, and the two files are one playback). Build: the two files of take C (16 clips). Test: the four files of takes A and B (32 clips).
- Cut points are on the 5 fps grid, so the truth spans are exact. Clip ids are shuffled (`pb01`…, `pt01`…) and say nothing about the truth.

| split | seed | partial copies | trims | jump cuts | containers | re-films | `truth.csv` sha256 |
|---|---|---|---|---|---|---|---|
| build | 11 | 12 | 4 | 4 | 2 | 16 | `6fd75b73ba804ea38b5a38b77ecf77d91c9bde280a1898f248c280e6318734b3` |
| test | 12 | 24 | 8 | 8 | 4 | 32 | `afafd22ff36fa9668d3681a40f5cdbb7eba89f64211f5739fe3da1f0d227cf25` |

Both splits were generated before this file was committed. The build split may be inspected and used to develop and tune the rule. The test split is run once, after the rule and the scoring script are committed, and I do not look at its clips or truth before then.

## Run

For each split: `indexreel match` on one folder holding the 24 dev fixture clips (`data/gate_run/in/dev/`), that split's generated clips and its real re-films. No verifier (matcher bands only, no paid calls). I will commit a scoring script before the test run; it reads the run directory and `truth.csv`, and the commit hashes of the rule and the scorer go in the result.

A clip's *family* is the original it comes from: a fixture's prefix, a re-film's dev clip (`b01_T` is T01, `b01_N` is N01, and so on), a generated clip's original. Filler belongs to no family. A family's recording is the recording holding its original.

Three counts, all from the same `pairs.csv`:
- **rule off:** `cluster.resolve_all` on the rows without the cover columns (the code as before);
- **automatic:** the run's own result with the rule;
- **approved:** an audit that approves every merged or unresolved link between a partial copy and a clip of its family, then recordings recomputed with the rule.

## Pass bar (test split, decided now)

Let n be the partial copies that sit in their family's recording when the rule is off (the cases the rule is for). A copy is **flagged** when, in the automatic count, it is in no recording with a clip of its family, and its recording carries a `partial` entry for it naming a recording that holds a clip of its family, over a span whose intersection over union with the true segment is at least 0.5.

1. **Detection.** n is at least 10, and at least 80% of the n copies are flagged.
2. **Approvals.** In the approved count, 0 of the flagged copies are in a recording with a clip of their family.
3. **No demotion.** Every fixture, trim, jump cut and real re-film that is in its family's recording with the rule off is still there in the automatic count: 0 exceptions.
4. **Fixtures unchanged.** The 276 pairs among the 24 fixtures have every column identical to the frozen dev run `data/match_dev_fixtures_floor020/pairs.csv` apart from the two new cover columns, none of them is partial, and the recordings of the fixtures (computed on those pairs) are the same.
5. **No wrong statements.** In the automatic count, 0 recordings hold clips of two families, and every `partial` segment names a recording that holds a clip of the same family as the clip carrying the entry.

The rule passes with all five.

## Reported, not scored

- Bars 1 to 5 on the build split (development numbers), and the values of `SHARE` and `G` tried there.
- Partial copies not in their family's recording even with the rule off (the matcher found no merged link): how many, by segment length.
- Detection by segment length, by filler position and by variation; span IoU of each flagged copy.
- Containers and jump cuts: where each ended up.
- Re-films: cover values of their links to their family's original.
- The compilation build split (`data/compilation/build` with the 24 fixtures) run again with the new code: recordings, compilations and suggestions compared with the code before the rule.
- The run on real posts above (`data/x_demo_run`), run again with the frozen rule, as a real example only: not scored and not tuned on.
- Matcher time per split.

## Limits

- Eight 10 s originals, cut with ffmpeg; both splits draw on them, so the test split checks the rule, not new footage. With one frame per second a 3 s segment gives the matcher about 3 frames.
- The filler is unrelated phone footage. In the real case the rest of the clip was another recording of the same scene, which may extend a core span into it and hide the partial copy; the synthetic set does not test that.
- By design the rule over-counts in some real cases: two trims of one recording that overlap only partly, with no clip in the run holding both, stay two recordings sharing footage; so do two uploads of one recording that each add their own intro or outro long enough to push both covers below `SHARE`.
- A container still merges with the recording it contains.
- 24 partial copies show failure modes, not rates: 80% of 20 has a Wilson 95% interval of about 0.58 to 0.92.
