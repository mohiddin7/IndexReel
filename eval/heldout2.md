# Held-out run 2: the fixed verifier on a fresh split, once

Written Oct 28 2026 before any clip of `data/final2/` was opened, decoded or scored; I have seen only its file list. Frozen by the commit that adds it; the run happens after that commit, once.

## Why

The first held-out run (`eval/heldout.md`, result `eval/report.md`) joined 48/48 versions but made 2 false merges in 1,080, a FAIL. One came from the matcher (a re-film look-alike merged at aligned 0.597, above `merge_at` 0.55). The other came from the verifier (one cheap `same` that no conflict check re-asked, because `apart` pairs inside a recording were not read as conflicts). Two changes were then built and set on dev only:

- (a) Conflicts: an `apart` pair inside a would-be recording forces a full-fidelity re-ask, and neighbour pairs with no answer are asked (as in H14).
- (b) Merged pairs are no longer final: the verifier checks them too, and a disagreement leaves the pair unresolved. No threshold is added; checking every merged pair costs about $0.003 a pair.

The two errors are treated differently on purpose. A verifier `different` on a merged pair can only demote it to `unresolved`, where a human decides; it never turns a match into `apart`. A verifier `same` can join a pair only after the conflict check. So fix (b) can cost recall but cannot add a false merge, and that recall cost is reported on its own.

`data/final/` was not used for either change. It is spent. Verifier with both fixes: commit `6119685`. Dev check (the 24 dev clips, `indexreel match` at `8410505`): 24/24 positives joined (matcher alone 20/24), 0 false merges, 0 true pairs demoted, no conflict raised, $0.073. The re-ask path is covered by tests only, not by dev data.

## Question

On a fresh split that no setting has seen, does the fixed pipeline join the versions of each recording and never join two different recordings?

## Data

- `data/final2/`: blocks b17 to b24, each a target `T` and a look-alike `N` recorded separately: 16 fresh families, delivered by the footage step before this freeze.
- The three versions of `eval/gate.md` from `src/indexreel/variants.py`, unchanged: `orig`, `pip`, `refilm_sim`. `scripts/heldout.py prepare2` writes them. 48 clips and 1,128 pairs: **48 positive pairs** and **1,080 negative pairs**, the same shape as run 1.

## Frozen pipeline

- Code at commit `23614a4`, holding:
  - the verifier from `6119685` (fixes a and b);
  - the matcher's span columns, mirrored margin and `cluster.resolve` (`abe5ccb`, `23614a4`; `eval/match-thresholds.md` Amendment 2: mirrored margin 0.02 and the `core_*` columns are the only matcher output changes, and bands on the 276 dev pairs are identical to `8410505`);
  - bands, `merge_at` 0.55, `floor` 0.20 and theta 0.9, unchanged from `8410505`;
  - SSCD sha256 `9f26bd4c848cc19b73d2ae92eea6e04886f61a7b764ceb7a13aeee62e6a6db56`.
- Commands: `indexreel match data/heldout2/in --out data/heldout2/run`, then `python -m indexreel.verify data/heldout2/run --cache data/heldout2/verify_cache --max-usd 10` (fresh cache), then `scripts/heldout.py score2`. No human decisions, no rerun, no constant changed after this commit.
- Joined: `cluster.effective_band` is `merged`. Recordings come from `cluster.resolve` (effective bands, then the compilation step); a clip marked as a compilation joins nothing through its partial links.

## Pass bar (same as run 1)

1. 0 joined negative pairs, and no recording that mixes two families. A pair is joined when its effective band is `merged` and neither clip is marked a compilation.
2. At least 40 of 48 positive pairs joined (83%).

Bar 1 failing makes the run a FAIL.

## Reported

The same table as `eval/report.md`: matcher alone, then matcher plus verifier; each loss and each false merge with its band, verdicts and reason; conflicts raised and re-asked; cost. Also: **compilation flags** (expected 0, since this split has no compilations; every flag is reported as a false flag). One row of its own: **true pairs the matcher merged that the verifier demoted to `unresolved`** (the recall cost of fix b), on dev and on this split.

## Limits

Simulated copies; a small number of families, so the Wilson bound on false merges stays wide; the same template and re-film simulation as run 1, so this tests the fix, not generalisation to real copies.
