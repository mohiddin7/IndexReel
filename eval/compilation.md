# Compilations: a clip made of several recordings must not join them

Written Oct 28 2026, before any compilation rule exists in code and before the test split has been run through anything. Generator: `scripts/make_compilations.py`. Run format: `eval/run-format.md`. Matcher and thresholds: `eval/match-thresholds.md` (frozen matcher 8410505, `merge_at` 0.55, `floor` 0.20).

## Problem

A recording is a connected component of merged pairs (`eval/run-format.md`). A compilation clip holds consecutive pieces of several recordings, so it links to each of them. Every link is correct for its part of the clip, yet any two of them, approved together, join recordings that have nothing in common. On one real news case, a viral upload made of consecutive spans of four broadcasts linked to all four: one automatically, three through unresolved pairs. Approving the three unresolved pairs, each correct for its span, would have joined four separate recordings.

## What counts as a compilation

A clip made of two or more consecutive time segments, where at least two of the segments are copies of different recordings. A transition (cut or crossfade) between segments does not change this.

Not compilations:
- one recording with cuts, including a jump cut (two pieces of one recording with a gap between them);
- one recording with overlays, captions, reframing, an inset or a letterbox;
- two recordings shown at the same time (side by side, or picture-in-picture over another recording). This is out of scope here and is not in the test set.

## Hypothesis

A rule that reads each pair's aligned span (where in each clip the match lies, `a_start_s` to `b_end_s`) can see that one clip matches different recordings over different parts of its timeline. It can then flag that clip as a compilation and keep its links from joining those recordings, both in the automatic result and after people approve its links. It does this without changing anything for clips made from one recording.

## Test material (dev only)

Sources are the 8 dev originals the matcher was tuned on: `data/gate_run/in/dev/{T01..T04,N01..N04}__orig.mp4` (blocks b01 to b04: 4 targets and their 4 look-alikes; 640×360, 5 fps, 10 s, no sound). The final split (`data/final`) and the gate split are not used.

`scripts/make_compilations.py <split>` writes `data/compilation/<split>/<id>.mp4` and `truth.csv`:

- **Compilations.** 2 to 4 consecutive segments from different families, each 3.0 to 6.0 s long, starting at a random frame of its original (cuts mid-shot). Every fourth compilation starts with a target followed by its own look-alike (same block, same kind of scene). Each gets one variation, in rotation: plain, caption (burned-in subtitle), letterbox (9:16 frame with a blurred fill), letterbox plus caption, inset (the clip at 40% size on a plain grey canvas), and crossfade (0.4 s fades between segments).
- **Controls, single recording.** Trims: one piece of 4.0 to 8.0 s of one original. Jump cuts: two pieces of 2.6 to 3.4 s of one original, with a gap of 1.0 to 2.0 s between them. Each gets plain, caption, letterbox or inset, in rotation.
- All cut points are on the 5 fps frame grid, so the truth spans are exact. Clip ids are shuffled (`cb01`…, `ct01`…) and say nothing about the truth.

| split | seed | compilations | trims | jump cuts | `truth.csv` sha256 |
|---|---|---|---|---|---|
| build | 1 | 12 (6 with 2 segments, 6 with 3; 8 contain a target-and-look-alike pair) | 4 | 4 | `2b3e51e1366c7c040d62f85741ac269a4abda3031904cb90d3e7c6f36a38efe1` |
| test | 2 | 24 (12 with 2 segments, 6 with 3, 6 with 4; 10 contain a target-and-look-alike pair) | 8 | 8 | `d0fc4ac28c9be3e2fa08ffea5922844d91e415d8fe157e76c9e0f8962fd1f67d` |

The build split may be inspected and used to develop and tune the rule. The test split is run once, after the rule and the scoring script are committed, and nobody developing the rule looks at its clips or truth before then.

## Run

For each split: `indexreel match` on one folder holding the 24 dev fixture clips (`data/gate_run/in/dev/`: original, picture-in-picture and simulated re-film of each family) plus that split's clips. The rule is then applied as the run format specifies. I will commit a scoring script before the test run; it reads the run directory and `truth.csv`. The commit hash of the rule and the scorer are written in the result.

Two ways of counting recordings:
- **automatic:** recordings as the run computes them, with the rule applied and no human decisions;
- **approved:** an audit log that approves every pair that is `merged` or `unresolved` and joins a compilation to a clip of one of its own source families (the links a careful person would approve, each one correct for its span), then recordings recomputed with the run's own functions (`cluster.apply_audit`, `cluster.recordings`, plus the rule).

A family's clips are its original, its picture-in-picture, its simulated re-film, and every control made from it.

## Pass bar (test split, decided now)

1. **Detection.** At least 18 of the 24 compilations are flagged, each naming at least two of its own source families and no other family.
2. **No mixing.** 0 recordings contain clips of two families, in both the automatic and the approved count.
3. **Controls.** At most 1 of the 16 single-recording controls is flagged as a compilation, and 0 controls end up in a recording with another family.
4. **No change for the fixtures.** Restricted to the 24 dev fixtures, the bands of their 276 pairs and their recordings are the same as in the frozen matcher's dev run (`data/match_dev_fixtures_floor020`).

The rule passes with all four.

## Reported, not scored

- Bars 1 to 3 on the build split (development numbers).
- Detection by variation, by number of segments, by segment length (3 to 4 s against 4 to 6 s), and for target-and-look-alike pairs.
- For each missed compilation: whether each of its segments had any `merged` or `unresolved` link to its family. No link is a limit of the matcher; a link that went unused is a limit of the rule.
- Segment spans: the overlap (intersection over union) between each reported segment and its true span.
- Jump cuts flagged, kept apart from trims.
- Matcher time per split.
- The real case above, as an exploratory example only (private footage; not scored).

## Limits

- One set of 8 originals, 10 s each; both splits draw on the same originals, so the test split checks the rule, not new footage. Segments are short (3 to 6 s) because the originals are, and the matcher samples one frame per second, so a 3 s segment gives it about 3 frames.
- Synthetic edits made with ffmpeg. Real compilations add music, text cards, speed changes and segments from recordings that are not in the run; a segment with no copy in the run cannot be named, and this test does not include one.
- 24 compilations and 16 controls show failure modes, not rates: 18 of 24 has a Wilson 95% interval of about 0.55 to 0.88.
