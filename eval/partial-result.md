# Partial copies: result of the single test run

**Result: FAIL.** Bar 1 fails: 11 of 16 partial copies flagged (69%; Wilson 95% 0.44 to 0.86), against 80%. Bars 2 to 5 pass.

Two things a reader should know first:
- **Bar 3 was narrowed after I saw the build numbers** (Amendment 3 of `eval/partial.md`), before the test split was run or opened. Under its original wording bar 3 also passes on the test split: 0 controls demoted either way. On the build split the original wording would have counted one jump cut (it reached its family only through a partial copy).
- **The committed scorer and the protocol text define "its family's recording" differently**, and I noticed only after the run. The protocol says the recording holding the family's original. `scripts/score_partial.py` counts any recording holding a clip of the family, which also counts a copy that joined a lone trim of its family. The result above uses the committed scorer. Under the protocol's wording, n is 11 and 9 are flagged (82%; Wilson 0.52 to 0.95), which would pass. I do not claim that, because I chose between the two only after seeing both numbers. The stricter count is also the more meaningful one: a copy joined to a trim of its family is still counted as a copy.

Protocol: `eval/partial.md` (5695bae, Amendments 1 to 3 in d1c07eb, a24aad2 and a76f522). Rule and scorer: a76f522 (`COVER_BAND` 2 frames, `SHARE` 0.8). Run once from a76f522, matcher only (no verifier, $0): 92 clips (24 dev fixtures, 36 generated test clips, 32 phone re-films of takes A and B), 4,186 pairs, 4 min 8 s on CPU with the fixtures cached. Nothing was changed after the run.

## Bars (test split)

| bar | result | numbers |
|---|---|---|
| 1. Detection | FAIL | n = 16 partial copies joined to a clip of their family with the rule off (n of at least 10 needed); 11 flagged (69%) |
| 2. Approvals | PASS | approving every merged or unresolved link between a flagged copy and its family rejoins 0 of the 11 |
| 3. No demotion | PASS | 0 of the 22 fixtures, 8 trims, 7 jump cuts and 32 re-films that reach their family without the generated clips are demoted. Under the original wording also 0. Three controls reach their family only through a partial copy (reported) |
| 4. Fixtures unchanged | PASS | 276 fixture pairs identical to the 23614a4 run apart from the six cover columns; bands as in the frozen dev run; none partial; same recordings |
| 5. No wrong statements | PASS | 0 recordings mixing two families; every `partial` segment names a recording with a clip of the clip's own family |

## The five copies the rule missed

Each has the cause below. None is a stretch the rule saw and misjudged; each is a path the rule does not cover.

- **pt16, pt23, pt27: joined only through a short clip inside their copied stretch.** The copy's links to the family's full-length clips are unresolved, not merged, so it has no partial pair. Its only merged link is to a trim or jump cut of its family that lies inside the copied stretch (cover of the short clip 0.83 to 1.0). Geometrically that is the same as an original and its trim, so the link merges. The extension cuts such links only for a clip that already has a partial pair. pt23 thereby sits in its family's recording; pt16 and pt27 form a two-clip recording with the trim.
- **pt05: its only merged partner is a jump cut that the compilation rule falsely suggests as a compilation.** The pair covers half of each clip, but clips of a detected compilation keep the compilation rule, which leaves them joined until a person decides.
- **pt21: the family's original itself is falsely suggested as a compilation.** N03__orig matched a generated 3 s copy and the family's other clips over different stretches, so the compilation rule flagged it, and every link to it keeps the compilation behaviour.

Two of the five (pt05, pt21) come from false compilation suggestions on single-recording clips. The compilation rule's own test already showed it can falsely flag clips (`eval/compilation-result.md`). The other three would need a way to tell "contains a trim" from "is the original of a trim", which one pair cannot give.

## Full-copy margin (asked for, since build had a margin of one frame)

On the test split the lowest cover of a merged link between two single-recording clips of one family is **0.8**, exactly `SHARE`: the simulated re-film of T03 against its other clips and the real re-films, 8 of 10 frames. 0 of 229 such links fall below 0.8. The highest cover of a merged link between a partial copy and a full-length clip of its family is 0.7. So full copies still sit one frame from the threshold on these 10 s originals.

## Reported, not scored

- **Copies not joined even with the rule off:** 2 of 18, both with a 3 s segment.
- **Flagged by segment length:** 3 s 3/4, 5 s 4/6, 7 s 4/6. **By filler position:** after 4/5, before 5/6, both sides 2/5. **By variation:** plain 4/5, caption 3/4, letterbox 2/3, inset 2/4 (committed scorer's n).
- **Span IoU of the flagged copies:** 0.71 to 1.0.
- **Containers (whole original plus filler):** one of two is separated from its family as a clip sharing footage, through a partial pair. The other still merges, as the protocol expected.
- **Jump cuts:** 7 of 8 in their family's recording, as with the rule off. The other was not joined with the rule off either.
- **Re-films:** all 32 stay in their family's recording.
- **Build split (development numbers):** 7 of 7 flagged, all other bars pass, n = 7 (bar 1 needs 10).
- **Compilation build split** (`data/compilation/build` with the 24 fixtures, new code): compilations, suggestions and recordings identical with the rule on and off. No band moved in 946 pairs compared with the earlier run of that split, and no clip got a `partial` entry.
- **Real example** (six test posts on X, run again from a76f522, not tuned on): unchanged, 3 recordings. The post cut from the last 7 s of another post's video and 7 s of a recording that was never posted still merges into that post's recording. Its other 7 s show the same fissure from another recording, and they match within the band, so its cover is 1.0 (the other side 0.7) and the link counts as a full copy. This is the same-scene limit written in the protocol. Its link to the phone re-film of the second post is partial (covers 0.5 and 0.28), but both clips are already in one recording through other merged links, so the run now shows a `partial` entry naming the clip's own recording. A later display fix drops such entries: a `partial` entry names only other recordings. With it, every bar, copy and control count above is identical when recomputed on both splits.

## What this says

The rule does what it was built for when the copy has a merged link to a full-length clip of its source and no clip involved is a compilation suggestion: all 11 such copies were flagged. No full copy, trim, jump cut or re-film was demoted, and no statement names the wrong source. It misses copies whose only merged links are to short clips inside them, and copies tied to clips that the compilation rule falsely flags. It does not help the real case, where the rest of the clip is a recording of the same scene. Any change to the rule needs a fresh split and a new pre-registered protocol; this test split is spent.

## Limits

As in the protocol: eight 10 s originals, synthetic cuts, unrelated phone filler (plus four volcano recordings in the test split), a cover grid of 1/10 on these clips. 16 copies show failure modes, not rates.
