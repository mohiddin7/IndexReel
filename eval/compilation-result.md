# Compilations: result

Protocol: `eval/compilation.md` (0155f7d, frozen before the rule existed). Rule: `cluster.resolve` at 23614a4, with the matcher's core-span columns from abe5ccb; its constants were set on the build split only (core cosine 0.4, at least 2 s of core run, 0.5 s tolerance between segments, mirror margin 0.02). Scorer: `scripts/score_compilation.py` at 9f31c42, committed before the test run. The test split was run once, by indexreel match on the 24 dev fixtures plus the 40 test clips (2,016 pairs, 3 min 40 s on CPU). `run.json` records f2d6888; between 23614a4 and f2d6888 only the clip page and withdraw changed, not the matcher or `cluster.py`. The truth file's sha256 matches the protocol (`d0fc4ac2…`). I reran the scorer on the run directory and got the same numbers.

## Verdict by the frozen bar (test split)

| Bar | Result | |
|---|---|---|
| 1. At least 18 of 24 compilations flagged, naming at least two of their own families and no other | 19/24 (Wilson 95% 0.60 to 0.91) | pass |
| 2. 0 recordings mixing families, automatic and approved | 0 automatic; 1 approved (312 approvals): T04 and N04 joined | FAIL |
| 3. At most 1 of 16 controls flagged, 0 in a recording with another family | 0/16 flagged (0 of 8 jump cuts), 0 wrong family | pass |
| 4. The 276 fixture pairs and their recordings unchanged | 0 of 276 bands changed; recordings differ (N04__orig and N04__pip split) | FAIL |

**The rule does not pass as frozen** (2 of 4 bars). The test split is spent; a changed rule needs a new split and a new protocol.

## The same run without the rule

The same scorer on the same `pairs.csv`, with plain connected components (the matcher's bands, no verifier answers in this run, and the same audit; no compilation rule):

| | no rule | rule |
|---|---|---|
| Recordings mixing families, automatic | 1, holding all 8 families | 0 |
| Recordings mixing families, approved | 1, holding all 8 families | 1 (T04 and N04) |
| Controls in a recording with another family | 16 of 16 | 0 of 16 |

On the build split, without the rule, 2 recordings already mixed families automatically, and all 8 families became one recording once the links a careful person would approve were approved.

## Failures

All three failures involve the dark look-alike pair T04 and N04: two different night-city recordings, the pair that set `merge_at` (highest dev negative, aligned 0.537) and the one where the localiser misses most often.
- **Bar 4.** The fixture `N04__pip` was flagged as a compilation, so its links became partial and it left the recording {N04__orig, N04__pip}. No band changed; the recording count did.
- **Bar 2.** `ct02` (letterbox; T04 then N04) was the one test compilation not flagged. Approving its two correct links joined the two families.
- **Bar 1.** 23 of 24 compilations were flagged, but 4 (ct10, ct12, ct13, ct18) also name a family that is not in them: T04 each time, next to a true N04 segment.

## Reported, not scored

| | detected |
|---|---|
| plain | 3/4 |
| caption | 4/4 |
| letterbox | 2/4 |
| letterbox plus caption | 4/4 |
| inset | 3/4 |
| crossfade | 3/4 |
| 2 segments / 3 / 4 | 10/12, 4/6, 5/6 |
| every segment 4 s or longer / some shorter | 7/10, 12/14 |
| contains a target and its look-alike / does not | 9/10, 10/14 |

- Every segment of every missed compilation had a `merged` or `unresolved` link to its own family. The misses come from the rule's grouping on the T04/N04 pair, not from missing links.
- Segment spans: the best reported segment per true segment has intersection over union median 0.94, minimum 0.51 (n 64).
- Build split (development numbers; the constants were set on it): 12/12 flagged, 0 and 0 mixing (123 approvals), 0/8 controls flagged, fixtures unchanged, span IoU median 0.94.

## Exploratory: one real case (not scored)

A viral upload made of consecutive spans of four broadcasts of one earthquake, run with the five other uploads that a fact-check traced (six clips, private footage, matched at f2d6888). The rule flags the viral upload as a compilation with four segments: 0 to 13 s, 23 to 52 s, 52 to 63 s and 87 to 105 s, each linked to a different recording. The recordings are the four the fact-check names. After approving all five of the upload's links, the four recordings stay apart. Before the rule, the same approvals would have joined all six clips.

## Limits

- 8 originals of 10 s each, ffmpeg edits, 24 compilations and 16 controls. Both splits use the same originals, so this checks the rule, not new footage.
- The failures sit on one family pair. A different set of originals could show other failure modes or none; this set cannot tell which.
- Real compilations add music, text cards and speed changes, and contain segments with no copy in the run. None of those are tested here.

## Cost

No model calls. Matcher: 3 min 40 s on CPU for the test split.
