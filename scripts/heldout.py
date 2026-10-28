"""Held-out run, once. Protocol: eval/heldout.md (frozen before the run).

  PYTHONPATH=src python scripts/heldout.py prepare     the three versions of every final family (as in eval/gate.md)
  PYTHONPATH=src python -m indexreel match data/heldout/in --out data/heldout/run
  MODEL_API_KEY=... PYTHONPATH=src python -m indexreel.verify data/heldout/run --max-usd 10
  PYTHONPATH=src python scripts/heldout.py score       the numbers for eval/report.md

Run 2 (eval/heldout2.md), blocks b17 to b24 in data/final2, run dir data/heldout2/run:
  PYTHONPATH=src python scripts/heldout.py prepare2
  PYTHONPATH=src python scripts/heldout.py score2      effective bands and cluster.resolve, as shipped

Blocks b09 to b16 give families TNN (target) and NNN (look-alike); clip ids are <family>__<version>.
"""
import csv
import itertools
import json
import math
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "final"
D = ROOT / "data" / "heldout"
BLOCKS = range(9, 17)


def prepare(src=SRC, d=D, blocks=BLOCKS):
    from indexreel import variants
    out = d / "in"
    out.mkdir(parents=True, exist_ok=True)
    for b in blocks:
        for kind in "TN":
            frames = variants.load(src / f"b{b:02d}_{kind}.mp4")
            for name, make in variants.VARIANTS.items():
                variants.write(make(frames, b), out / f"{kind}{b:02d}__{name}.mp4")


def wilson(k, n, z=1.96):
    if n == 0:
        return float("nan"), float("nan")
    p, d = k / n, 1 + z * z / n
    c, r = p + z * z / (2 * n), z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - r) / d, (c + r) / d


def fam(clip):
    return clip.split("__")[0]


def joined(r):
    """The pipeline's call without a human: merged by the matcher, or unresolved and judged same."""
    return r["band"] == "merged" or (r["band"] == "unresolved" and r["verify_verdict"] == "same")


def components(ids, edges):
    root = {c: c for c in ids}

    def find(c):
        while root[c] != c:
            root[c] = root[root[c]]
            c = root[c]
        return c

    for a, b in edges:
        root[find(a)] = find(b)
    groups = {}
    for c in ids:
        groups.setdefault(find(c), set()).add(c)
    return list(groups.values())


def score(run=D / "run"):
    rows = list(csv.DictReader(open(run / "pairs.csv")))
    ids = [c["id"] for c in json.loads((run / "clips.json").read_text())["clips"]]
    pos = [r for r in rows if fam(r["a"]) == fam(r["b"])]
    neg = [r for r in rows if fam(r["a"]) != fam(r["b"])]
    out = []
    k = sum(joined(r) for r in pos)
    lo, hi = wilson(k, len(pos))
    out.append(f"1 positives joined {k}/{len(pos)} (Wilson 95% {lo:.2f} to {hi:.2f})")
    fm = [r["pair_id"] for r in neg if joined(r)]
    lo, hi = wilson(len(fm), len(neg))
    out.append(f"2 false merges (pairs) {len(fm)}/{len(neg)} (Wilson 95% {lo:.4f} to {hi:.4f}) {fm}")
    comps = components(ids, [(r["a"], r["b"]) for r in rows if joined(r)])
    mixed = [sorted(c) for c in comps if len({fam(x) for x in c}) > 1]
    out.append(f"3 recordings found {len(comps)} (truth {len({fam(i) for i in ids})}); groups mixing families {len(mixed)} {mixed}")
    by = Counter()
    for r in pos:
        v = tuple(sorted((r["a"].split("__")[1], r["b"].split("__")[1])))
        by[(v, r["band"], r["verify_verdict"] or "-")] += 1
    out.append("positives by version pair, band, verdict: " + "; ".join(f"{v[0]}+{v[1]} {b}/{vd} {n}" for (v, b, vd), n in sorted(by.items())))
    out.append("bands, positives: " + str(Counter(r["band"] for r in pos)) + "; negatives: " + str(Counter(r["band"] for r in neg)))
    out.append("verdicts on unresolved, positives: " + str(Counter(r["verify_verdict"] or "-" for r in pos if r["band"] == "unresolved"))
               + "; negatives: " + str(Counter(r["verify_verdict"] or "-" for r in neg if r["band"] == "unresolved")))
    out.append("losses (positives not joined): " + str([(r["pair_id"], r["band"], r["aligned"], r["verify_verdict"], r["verify_reason"]) for r in pos if not joined(r)]))
    out.append(f"verify cost ${sum(float(r['verify_cost_usd'] or 0) for r in rows):.4f} at list prices")
    print("\n".join(out))


def score2(run=ROOT / "data" / "heldout2" / "run"):
    from indexreel import cluster
    rows = list(csv.DictReader(open(run / "pairs.csv")))
    ids = [c["id"] for c in json.loads((run / "clips.json").read_text())["clips"]]
    recs, comps = cluster.resolve(ids, rows)
    hubs = {c["clip"] for c in comps}
    eff = {r["pair_id"]: cluster.effective_band(r) for r in rows}
    j = lambda r: eff[r["pair_id"]] == "merged" and not {r["a"], r["b"]} & hubs
    pos = [r for r in rows if fam(r["a"]) == fam(r["b"])]
    neg = [r for r in rows if fam(r["a"]) != fam(r["b"])]
    out = []
    k = sum(j(r) for r in pos)
    lo, hi = wilson(k, len(pos))
    out.append(f"1 positives joined {k}/{len(pos)} (Wilson 95% {lo:.2f} to {hi:.2f}); matcher alone {sum(r['band'] == 'merged' for r in pos)}/{len(pos)}")
    fm = [r["pair_id"] for r in neg if j(r)]
    lo, hi = wilson(len(fm), len(neg))
    mixed = [r["members"] for r in recs if len({fam(m) for m in r["members"]}) > 1]
    out.append(f"2 false merges (pairs) {len(fm)}/{len(neg)} (Wilson 95% {lo:.4f} to {hi:.4f}) {fm}; recordings mixing families {len(mixed)} {mixed}")
    out.append(f"recordings found {len(recs)} (truth {len({fam(i) for i in ids})}); status {dict(Counter(r['status'] for r in recs))}")
    out.append(f"compilation flags (all false here) {len(hubs)} {sorted(hubs)}")
    dem = [(r["pair_id"], r["aligned"], r["verify_verdict"], r["verify_reason"]) for r in pos if r["band"] == "merged" and eff[r["pair_id"]] != "merged"]
    out.append(f"true pairs demoted by verifying merged pairs {len(dem)} {dem}")
    out.append(f"negatives merged by the matcher {sum(r['band'] == 'merged' for r in neg)}, demoted by the verifier {sum(r['band'] == 'merged' and eff[r['pair_id']] != 'merged' for r in neg)}")
    out.append(f"re-asked at full fidelity {sum(r['verify_reason'].startswith('re-asked') for r in rows)} pairs; conflicts left in recordings {sum(len(r['conflicts']) for r in recs)}")
    out.append("losses (positives not joined): " + str([(r["pair_id"], r["band"], r["aligned"], r["verify_verdict"], r["verify_reason"]) for r in pos if not j(r)]))
    out.append(f"verify cost ${sum(float(r['verify_cost_usd'] or 0) for r in rows):.4f} at list prices")
    print("\n".join(out))


def selfcheck():
    rows = [{"band": "merged", "verify_verdict": ""}, {"band": "unresolved", "verify_verdict": "same"},
            {"band": "unresolved", "verify_verdict": "abstain"}, {"band": "apart", "verify_verdict": ""}]
    assert [joined(r) for r in rows] == [True, True, False, False]
    assert sorted(map(sorted, components(["a", "b", "c"], [("a", "b")]))) == [["a", "b"], ["c"]]
    assert abs(wilson(0, 1080)[1] - 0.00355) < 1e-4


if __name__ == "__main__":
    {"prepare": prepare, "score": score, "selfcheck": selfcheck, "score2": score2,
     "prepare2": lambda: prepare(ROOT / "data" / "final2", ROOT / "data" / "heldout2", range(17, 25))}[sys.argv[1]]()
