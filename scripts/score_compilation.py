"""Score a compilation-test run against its truth (eval/compilation.md). Read-only on the run directory.

  PYTHONPATH=src python scripts/score_compilation.py <run dir> <truth.csv> [--frozen data/match_dev_fixtures_floor020]
  python scripts/score_compilation.py selftest

Automatic count: the run's clusters.json. Approved count: cluster.resolve() on the run's pairs with an audit that
approves every merged or unresolved pair joining a compilation to a clip of one of its own source families.
"""
import argparse
import csv
import json
from collections import Counter, defaultdict
from math import sqrt
from pathlib import Path


def wilson(k, n, z=1.96):
    if not n:
        return 0.0, 1.0
    p = k / n
    c, h = p + z * z / (2 * n), z * sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return round((c - h) / (1 + z * z / n), 2), round((c + h) / (1 + z * z / n), 2)


def read_truth(path):
    """{clip: row}, with families as a list and segments as [(family, clip_start, clip_end)]."""
    out = {}
    for r in csv.DictReader(open(path, newline="")):
        segs = []
        for s in r["segments"].split(";"):
            fam, rest = s.split(":")
            a, b = rest.split("@")[1].split("-")
            segs.append((fam, float(a), float(b)))
        out[r["clip"]] = {**r, "families": r["families"].split(";"), "segs": segs}
    return out


def family_of(clip, truth):
    """Fixture ids are <family>__<version>; a control has one family; a compilation has none."""
    if clip in truth:
        t = truth[clip]
        return None if t["kind"] == "compilation" else t["families"][0]
    return clip.split("__")[0]


def mixing(recs, truth):
    """Recordings whose clips come from two or more families."""
    bad = []
    for r in recs:
        fams = {family_of(c, truth) for c in r["members"]} - {None}
        if len(fams) > 1:
            bad.append((r["id"], sorted(fams)))
    return bad


def iou(a, b):
    inter = max(0.0, min(a[1], b[1]) - max(a[0], b[0]))
    return inter / (max(a[1], b[1]) - min(a[0], b[0]))


def detection(comps, recs, truth):
    """Per true compilation: flagged, families named through its segments' recordings, verdict and span IoUs."""
    members = {r["id"]: r["members"] for r in recs}
    entry = {c["clip"]: c for c in comps}
    out = {}
    for clip, t in truth.items():
        if t["kind"] != "compilation":
            continue
        e = entry.get(clip)
        named, best = set(), [0.0] * len(t["segs"])  # per true segment, the best IoU of a reported segment of its family
        for s in (e or {}).get("segments", []):
            fams = {family_of(m, truth) for m in members.get(s["recording"], [])} - {None}
            named |= fams
            for j, (fam, a, b) in enumerate(t["segs"]):
                if fam in fams:
                    best[j] = max(best[j], round(iou((a, b), (s["start_s"], s["end_s"])), 2))
        ious = best if e else []
        true = set(t["families"])
        out[clip] = {"flagged": e is not None, "named": sorted(named),
                     "ok": e is not None and len(named & true) >= 2 and named <= true, "iou": ious}
    return out


def approve_all(rows, truth):
    """Every merged or unresolved pair between a compilation and a clip of one of its own families."""
    audit = []
    for r in rows:
        if r["band"] not in ("merged", "unresolved"):
            continue
        for c, other in ((r["a"], r["b"]), (r["b"], r["a"])):
            t = truth.get(c)
            if t and t["kind"] == "compilation" and family_of(other, truth) in t["families"]:
                audit.append({"ts": "", "actor": "scorer", "action": "approve_merge", "pair": r["pair_id"], "note": ""})
    return audit


def fixtures_unchanged(rows, recs, frozen_dir, truth):
    """Bar 4: bands of the fixture pairs and the fixtures' recordings, against the frozen dev run."""
    old_rows = {r["pair_id"]: r["band"] for r in csv.DictReader(open(Path(frozen_dir) / "pairs.csv", newline=""))}
    new = {r["pair_id"]: r["band"] for r in rows if r["a"] not in truth and r["b"] not in truth}
    band_diff = sorted(p for p in old_rows if new.get(p) != old_rows[p])
    old_recs = json.loads((Path(frozen_dir) / "clusters.json").read_text())["recordings"]
    part = lambda rs: sorted(sorted(m) for m in ([c for c in r["members"] if c not in truth] for r in rs) if m)  # noqa: E731
    return band_diff, part(old_recs) == part(recs), len(old_rows)


def report(run_dir, truth_path, frozen_dir, resolve):
    run_dir = Path(run_dir)
    truth = read_truth(truth_path)
    ids = [c["id"] for c in json.loads((run_dir / "clips.json").read_text())["clips"]]
    rows = list(csv.DictReader(open(run_dir / "pairs.csv", newline="")))
    cl = json.loads((run_dir / "clusters.json").read_text())
    auto_recs, auto_comps = cl["recordings"], cl.get("compilations", [])
    re_recs, re_comps = resolve(ids, rows, [])
    audit = approve_all(rows, truth)
    ap_recs, ap_comps = resolve(ids, rows, audit)

    det = detection(auto_comps, auto_recs, truth)
    k, n = sum(d["ok"] for d in det.values()), len(det)
    controls = {c: t for c, t in truth.items() if t["kind"] != "compilation"}
    flagged_ctrl = sorted(c for c in controls if c in {e["clip"] for e in auto_comps})
    rec_of = {m: r for r in auto_recs for m in r["members"]}
    wrong_ctrl = sorted(c for c in controls if {family_of(m, truth) for m in rec_of[c]["members"]} - {None, family_of(c, truth)})
    mix_auto, mix_ap = mixing(auto_recs, truth), mixing(ap_recs, truth)
    band_diff, recs_same, n_old = fixtures_unchanged(rows, auto_recs, frozen_dir, truth)

    bars = [("1 detection, at least 18 of 24 (3 in 4 on another split size)", f"{k}/{n} (Wilson {wilson(k, n)})", k * 24 >= 18 * n),
            ("2 no mixing, automatic and approved", f"{len(mix_auto)} and {len(mix_ap)} ({len(audit)} approvals)", not mix_auto and not mix_ap),
            ("3 controls flagged at most 1, wrong family 0", f"{len(flagged_ctrl)}/{len(controls)} flagged, {len(wrong_ctrl)} wrong family",
             len(flagged_ctrl) <= 1 and not wrong_ctrl),
            ("4 fixtures unchanged", f"{len(band_diff)} of {n_old} bands changed, recordings {'same' if recs_same else 'DIFFERENT'}",
             not band_diff and recs_same)]
    print(f"run {run_dir}\ntruth {truth_path}\n")
    for name, value, ok in bars:
        print(f"{'pass' if ok else 'FAIL'}  {name}: {value}")
    print("\nclusters.json equals resolve() with no audit:", sorted(map(json.dumps, auto_comps)) == sorted(map(json.dumps, re_comps))
          and sorted(sorted(r["members"]) for r in auto_recs) == sorted(sorted(r["members"]) for r in re_recs))
    if mix_auto or mix_ap:
        print("mixing (automatic):", mix_auto, "\nmixing (approved):", mix_ap)
    print("controls flagged:", flagged_ctrl, " wrong family:", wrong_ctrl,
          " jump cuts flagged:", sum(controls[c]["kind"] == "control_jumpcut" for c in flagged_ctrl))
    print("approved count also flags:", len(ap_comps), "compilations")

    by = defaultdict(Counter)
    for c, d in det.items():
        t = truth[c]
        long_ = all(b - a >= 4.0 for _, a, b in t["segs"])
        look = any(f"T0{i}" in t["families"] and f"N0{i}" in t["families"] for i in "1234")
        for key in (f"variation {t['variation']}", f"segments {len(t['segs'])}", f"all segments >= 4 s {long_}", f"target+look-alike {look}"):
            by[key]["n"] += 1
            by[key]["ok"] += d["ok"]
    print("\nreported (not scored):")
    for key in sorted(by):
        print(f"  {key}: {by[key]['ok']}/{by[key]['n']}")
    ious = sorted(i for d in det.values() for i in d["iou"])
    if ious:
        print(f"  segment IoU (best reported segment per true segment, 0 if none): median {ious[len(ious) // 2]}, min {ious[0]}, n {len(ious)}")
    band = {(r["a"], r["b"]): r["band"] for r in rows}
    for c, d in sorted(det.items()):
        if d["ok"]:
            continue
        linked = []
        for fam, _, _ in truth[c]["segs"]:
            hit = any(band.get(tuple(sorted((c, o)))) in ("merged", "unresolved") for o in ids if family_of(o, truth) == fam)
            linked.append(f"{fam}:{'link' if hit else 'no link'}")
        print(f"  missed {c} ({truth[c]['variation']}): flagged {d['flagged']}, named {d['named']}, {', '.join(linked)}")
    return bars


def selftest():
    import tempfile
    truth_rows = [
        {"clip": "c1", "split": "x", "kind": "compilation", "variation": "plain", "families": "T01;N01",
         "segments": "T01:0.00-4.00@0.00-4.00;N01:2.00-6.00@4.00-8.00"},
        {"clip": "k1", "split": "x", "kind": "control_jumpcut", "variation": "plain", "families": "T01",
         "segments": "T01:0.00-3.00@0.00-3.00;T01:5.00-8.00@3.00-6.00"}]
    ids = ["T01__orig", "N01__orig", "c1", "k1"]
    rows = [{"pair_id": "N01__orig~T01__orig", "a": "N01__orig", "b": "T01__orig", "band": "apart"},
            {"pair_id": "N01__orig~c1", "a": "N01__orig", "b": "c1", "band": "unresolved"},
            {"pair_id": "T01__orig~c1", "a": "T01__orig", "b": "c1", "band": "merged"},
            {"pair_id": "T01__orig~k1", "a": "T01__orig", "b": "k1", "band": "merged"},
            {"pair_id": "N01__orig~k1", "a": "N01__orig", "b": "k1", "band": "apart"},
            {"pair_id": "c1~k1", "a": "c1", "b": "k1", "band": "unresolved"}]
    recs = [{"id": "r1", "members": ["T01__orig", "k1"]}, {"id": "r2", "members": ["N01__orig"]}, {"id": "r3", "members": ["c1"]}]
    comps = [{"clip": "c1", "recording": "r3", "segments": [{"recording": "r1", "start_s": 0.0, "end_s": 4.0},
                                                            {"recording": "r2", "start_s": 4.2, "end_s": 8.0}]}]
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        with open(d / "truth.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(truth_rows[0]))
            w.writeheader()
            w.writerows(truth_rows)
        truth = read_truth(d / "truth.csv")
        det = detection(comps, recs, truth)
        assert det["c1"]["ok"] and det["c1"]["iou"] == [1.0, 0.95], det
        assert approve_all(rows, truth) == [{"ts": "", "actor": "scorer", "action": "approve_merge", "pair": p, "note": ""}
                                            for p in ("N01__orig~c1", "T01__orig~c1", "c1~k1")]  # a control counts as its family
        assert mixing(recs, truth) == [] and mixing([{"id": "r9", "members": ["T01__orig", "k1", "N01__orig", "c1"]}], truth) == [("r9", ["N01", "T01"])]
        assert not detection([], recs, truth)["c1"]["ok"]
        other = recs + [{"id": "r4", "members": ["T02__orig"]}]
        wrong = [{**comps[0], "segments": comps[0]["segments"] + [{"recording": "r4", "start_s": 0, "end_s": 1}]}]
        assert not detection(wrong, other, truth)["c1"]["ok"]  # names a family that is not in the clip
        assert wilson(18, 24) == (0.55, 0.88)
    print("selftest ok")


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["selftest"]:
        selftest()
    else:
        ap = argparse.ArgumentParser()
        ap.add_argument("run_dir")
        ap.add_argument("truth")
        ap.add_argument("--frozen", default="data/match_dev_fixtures_floor020")
        a = ap.parse_args()
        from indexreel.cluster import resolve
        report(a.run_dir, a.truth, a.frozen, resolve)
