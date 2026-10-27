"""Score every pair of clips with SSCD, write the scores, and report how positives and negatives separate.

Usage: PYTHONPATH=src python scripts/score_clips.py --model sscd.torchscript.pt --out pairs.csv \
         [--truth truth.csv] [--cache dir] clip1 clip2 ...
truth.csv has columns a,b (paths as given on the command line); those pairs are the positives, every other pair a negative.
No threshold is applied."""
import argparse
import csv
import hashlib
import itertools
import math
from pathlib import Path

import numpy as np

from indexreel import sscd


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def features(model, path, cache):
    p = Path(path)
    st = p.stat()
    key = hashlib.sha1(f"{p.resolve()}{st.st_size}{st.st_mtime_ns}".encode()).hexdigest()
    f = Path(cache) / f"{key}.npz" if cache else None
    if f and f.exists():
        z = np.load(f)
        return z["plain"], z["mirror"]
    plain, mirror = sscd.clip_features(model, p)
    if f:
        f.parent.mkdir(parents=True, exist_ok=True)
        np.savez(f, plain=plain, mirror=mirror)
    return plain, mirror


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--truth")
    ap.add_argument("--cache")
    ap.add_argument("clips", nargs="+")
    a = ap.parse_args()

    model = sscd.load(a.model)
    feats = {}
    for c in a.clips:
        feats[c] = features(model, c, a.cache)
        print(f"{len(feats[c][0]):4d} frames  {c}", flush=True)

    pos = set()
    if a.truth:
        for r in csv.DictReader(open(a.truth)):
            pos.add(frozenset((r["a"], r["b"])))
    missing = [p for p in pos if not p <= set(feats)]
    assert not missing, f"truth pairs name clips that were not given: {missing[:3]}"

    rows = []
    for x, y in itertools.combinations(a.clips, 2):
        rows.append((x, y, sscd.score(feats[x], feats[y]), sscd.aligned_score(feats[x], feats[y]),
                     int(frozenset((x, y)) in pos)))
    with open(a.out, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["a", "b", "score", "aligned", "same"])
        w.writerows(rows)
    print(f"\n{len(rows)} pairs: {sum(r[4] for r in rows)} positive")
    report(rows, 2, "score (best match per frame)")
    report(rows, 3, "aligned (constant time offset)")


def report(rows, col, name):
    P = [r for r in rows if r[4]]
    N = [r for r in rows if not r[4]]
    print(f"\n== {name} ==")
    if P:
        beaten = sum(r[col] > max(n[col] for n in N if r[0] in n[:2] or r[1] in n[:2]) for r in P)
        lo, hi = wilson(beaten, len(P))
        print(f"positive beats every negative sharing a clip with it: {beaten}/{len(P)} (Wilson 95% {lo:.2f} to {hi:.2f})")
        print(f"lowest positive {min(r[col] for r in P):.3f}")
    print(f"highest negative {max(r[col] for r in N):.3f}")
    if P:
        print(f"gap (lowest positive minus highest negative) {min(r[col] for r in P) - max(r[col] for r in N):+.3f}")
    print("five highest negatives:")
    for r in sorted(N, key=lambda r: -r[col])[:5]:
        print(f"  {r[col]:.3f}  {Path(r[0]).name}  {Path(r[1]).name}")


if __name__ == "__main__":
    main()
