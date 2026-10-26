"""Day-1 gate runner, following eval/gate.md exactly.

  python scripts/gate.py prepare dev|gate   make the three versions of every family at 640x360, 5 fps
  python scripts/gate.py tune dev           choose theta (edge-support cut-off) for the OpenCV control on dev only
  python scripts/gate.py cv dev|gate        OpenCV control with the frozen theta: localise every frame, write 10 fps output
  python scripts/gate.py score dev          dev numbers and the threshold (diagnostic only)
  python scripts/gate.py score gate         the verdict; run once, after both arms exist

Blocks b01-b04 are dev and b05-b08 are gate. Block bNN gives families TNN (target) and NNN (look-alike).
"""
import csv
import itertools
import json
import sys
from pathlib import Path

import cv2
import numpy as np

from indexreel import match, quad, variants

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RUN = DATA / "gate_run"
BLOCKS = {"dev": range(1, 5), "gate": range(5, 9)}
PIP_QUAD = np.float32([[variants.PIP_RECT[0], variants.PIP_RECT[1]], [variants.PIP_RECT[2], variants.PIP_RECT[1]],
                       [variants.PIP_RECT[2], variants.PIP_RECT[3]], [variants.PIP_RECT[0], variants.PIP_RECT[3]]])


def source(block, kind):
    """Only the 10-second MP4 cut that the footage step delivered; never a raw source."""
    p = DATA / "gate" / f"b{block:02d}_{kind}.mp4"
    if not p.exists():
        raise FileNotFoundError(f"{p} not delivered yet")
    return p


def prepare(split):
    out = RUN / "in" / split
    out.mkdir(parents=True, exist_ok=True)
    for b in BLOCKS[split]:
        for kind in "TN":
            fam = f"{kind}{b:02d}"
            frames = variants.load(source(b, kind))
            for name, make in variants.VARIANTS.items():
                variants.write(make(frames, b), out / f"{fam}__{name}.mp4")
            print("prepared", fam, flush=True)


GRID = [0, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]  # Amendment 1 in eval/gate.md
THETA = RUN / "cv_theta.json"


def gray(f):
    return cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)


def localise_cv(frames, theta):
    prev, out, fallbacks = None, [], 0
    for f in frames:
        g = gray(f)
        q = quad.pick(quad.edge_candidates(g, extra=[PIP_QUAD]), g, prev, theta)
        fallbacks += q is None
        out.append(quad.warp(f, q))
        prev = g
    return out, fallbacks


def read_frames(path):
    cap, out = cv2.VideoCapture(str(path)), []
    while True:
        ok, f = cap.read()
        if not ok:
            return out
        out.append(f)


def run_cv(split):
    theta = json.loads(THETA.read_text())["theta"]
    out = RUN / "out" / split / "cv"
    out.mkdir(parents=True, exist_ok=True)
    log = {}
    for p in sorted((RUN / "in" / split).glob("*.mp4")):
        warped, fb = localise_cv(read_frames(p), theta)
        variants.write(warped, out / p.name, repeat=2)
        log[p.stem] = fb
        print(p.stem, "full-frame fallbacks:", fb, flush=True)
    (RUN / "out" / split / "cv_fallbacks.json").write_text(json.dumps(log, indent=1))


def tune(split):
    """Pick theta on dev only. Only the frames the scorer samples matter, so only those are localised."""
    assert split == "dev", "theta is set on dev only"
    clips = {}
    for p in sorted((RUN / "in" / "dev").glob("*.mp4")):
        fr = read_frames(p)
        clips[p.stem] = [(fr[i], gray(fr[i]), gray(fr[i - 1]) if i else None) for i in range(0, len(fr), 5)]
        clips[p.stem] = [(f, g, prev, quad.edge_candidates(g, extra=[PIP_QUAD])) for f, g, prev in clips[p.stem]]
    table = []
    for theta in GRID:
        feats = {name: match.hashes([quad.warp(f, quad.pick(c, g, prev, theta)) for f, g, prev, c in fr])
                 for name, fr in clips.items()}
        rows = []
        for a, b in itertools.combinations(sorted(feats), 2):
            fa, va = a.split("__")
            fb, vb = b.split("__")
            rows.append({"a": a, "b": b, "fa": fa, "va": va, "fb": fb, "vb": vb, "same": fa == fb,
                         "pdq": match.score(feats[a], feats[b])})
        thr = threshold(rows)
        hits = {v: sum(h for _, h in targets(rows, thr, v)) for v in ("pip", "refilm_sim")}
        table.append((theta, sum(hits.values()), hits))
        print(f"theta={theta} threshold={thr:.4f} pip={hits['pip']}/4 refilm_sim={hits['refilm_sim']}/4", flush=True)
    best = max(table, key=lambda t: (t[1], t[0]))
    THETA.write_text(json.dumps({"theta": best[0], "dev_hits": best[2], "table": [[t[0], t[1]] for t in table]}))
    print("chosen theta:", best[0])


def pairs(split, arm):
    paths = sorted((RUN / "out" / split / arm).glob("*.mp4"))
    feats = {p.stem: match.sampled_hashes(p) for p in paths}
    rows = []
    for a, b in itertools.combinations(sorted(feats), 2):
        fa, va = a.split("__")
        fb, vb = b.split("__")
        rows.append({"a": a, "b": b, "fa": fa, "va": va, "fb": fb, "vb": vb, "same": fa == fb,
                     "pdq": match.score(feats[a], feats[b])})
    return rows


def threshold(rows):
    return max(0.5, max(r["pdq"] for r in rows if not r["same"]))


def targets(rows, thr, variant):
    pos = [r for r in rows if r["same"] and r["fa"].startswith("T") and {r["va"], r["vb"]} == {"orig", variant}]
    return [(r["fa"], r["pdq"] > thr) for r in pos]


def score(split, arms=("cv", "sam")):
    results = {}
    for arm in arms:
        if not (RUN / "out" / split / arm).exists():
            print(f"{arm}: no output for {split}")
            continue
        dev = pairs("dev", arm)
        rows = dev if split == "dev" else pairs(split, arm)
        thr = threshold(dev)
        fp = sum(r["pdq"] > thr for r in rows if not r["same"])
        hits = {v: targets(rows, thr, v) for v in ("pip", "refilm_sim")}
        results[arm] = {"threshold": thr, "false_merges": fp, "hits": hits}
        with open(RUN / "out" / split / f"{arm}_pairs.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        print(f"{split}/{arm}: threshold={thr:.4f} false_merges={fp} "
              + " ".join(f"{v}={sum(h for _, h in t)}/{len(t)}" for v, t in hits.items()))
    if split == "gate" and {"cv", "sam"} <= results.keys():
        k = lambda arm, v: sum(h for _, h in results[arm]["hits"][v])
        ok = (results["cv"]["false_merges"] == results["sam"]["false_merges"] == 0
              and min(k("sam", v) for v in ("pip", "refilm_sim")) >= 3
              and max(k("sam", v) - k("cv", v) for v in ("pip", "refilm_sim")) >= 1)
        print("GATE:", "PASS" if ok else "FAIL")
    return results


if __name__ == "__main__":
    cmd, split = sys.argv[1], sys.argv[2]
    {"prepare": prepare, "tune": tune, "cv": run_cv, "score": score}[cmd](split)
