"""Score a partial-copy run against its truth (eval/partial.md). Read-only on the run directory.

  PYTHONPATH=src python scripts/score_partial.py <run dir> <truth.csv> [--identity data/identity_old] [--frozen data/match_dev_fixtures_floor020]
  PYTHONPATH=src python scripts/score_partial.py selftest

Rule off: cluster.resolve_all on the rows without the cover columns. Automatic: the run's clusters.json (checked
against a recompute). Approved: an audit that approves every merged or unresolved pair between a partial copy and
a clip of its family.
"""
import argparse
import csv
import json
import re
import sys
from collections import Counter
from math import sqrt
from pathlib import Path

from indexreel import cluster

COVER = ("cover_a", "cover_b", "cover_a_start_s", "cover_a_end_s", "cover_b_start_s", "cover_b_end_s")


def wilson(k, n, z=1.96):
    if not n:
        return 0.0, 1.0
    p = k / n
    c, h = p + z * z / (2 * n), z * sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return round((c - h) / (1 + z * z / n), 2), round((c + h) / (1 + z * z / n), 2)


def read_truth(path):
    out = {}
    for r in csv.DictReader(open(path, newline="")):
        segs = []
        for s in r["segments"].split(";"):
            a, b = s.split("@")[1].split("-")
            segs.append((float(a), float(b)))
        out[r["clip"]] = {**r, "span": (min(a for a, _ in segs), max(b for _, b in segs))}
    return out


def family_of(clip, truth):
    """Generated clips from the truth, fixtures by prefix, re-films by their dev clip (b01_T is T01)."""
    if clip in truth:
        return truth[clip]["family"]
    m = re.search(r"_b0(\d)_([TN])$", clip)
    return f"{m.group(2)}0{m.group(1)}" if m else clip.split("__")[0]


def kind_of(clip, truth):
    if clip in truth:
        return truth[clip]["kind"]
    return "refilm" if clip.startswith("devgate_refilm") else "fixture"


def iou(a, b):
    inter = max(0.0, min(a[1], b[1]) - max(a[0], b[0]))
    return inter / (max(a[1], b[1]) - min(a[0], b[0]))


def score(ids, rows, truth, auto=None, frozen_rows=None):
    fam = {c: family_of(c, truth) for c in ids}
    kind = {c: kind_of(c, truth) for c in ids}
    off = cluster.resolve_all(ids, [{k: v for k, v in r.items() if k not in COVER} for r in rows])[0]
    recomputed = cluster.resolve_all(ids, rows)[0]
    auto = recomputed if auto is None else auto
    approve = [{"pair": r["pair_id"], "action": "approve_merge"} for r in rows
               if r["band"] != "apart" and {kind[r["a"]], kind[r["b"]]} & {"partial"} and fam[r["a"]] == fam[r["b"]]]
    approved = cluster.resolve_all(ids, rows, approve)[0]

    def where(recs):
        return {c: r for r in recs for c in r["members"]}

    def with_family(recs, c):
        """True when c's recording holds another clip of c's family."""
        return any(fam[m] == fam[c] for m in where(recs)[c]["members"] if m != c)

    w_auto, rid = where(auto), {r["id"]: r for r in auto}
    out = {"recompute_matches": recomputed == auto, "copies": {}, "controls": {}}
    for c in ids:
        if kind[c] != "partial":
            continue
        joined_off = with_family(off, c)
        segs = w_auto[c].get("partial", {}).get(c, [])
        named = [s for s in segs if any(fam[m] == fam[c] for m in rid[s["recording"]]["members"])]
        best = max((round(iou(truth[c]["span"], (s["start_s"], s["end_s"])), 2) for s in named), default=0.0)
        flagged = not with_family(auto, c) and best >= 0.5
        out["copies"][c] = {"joined_off": joined_off, "flagged": flagged, "iou": best,
                            "approved_rejoined": with_family(approved, c),
                            **{k: truth[c][k] for k in ("variation", "position")},
                            "seg_s": round(truth[c]["span"][1] - truth[c]["span"][0], 1)}
    for c in ids:
        if kind[c] in ("fixture", "control_trim", "control_jumpcut", "refilm", "container"):
            out["controls"][c] = {"kind": kind[c], "family_off": with_family(off, c), "family_auto": with_family(auto, c)}
    n = [c for c, v in out["copies"].items() if v["joined_off"]]
    k = [c for c in n if out["copies"][c]["flagged"]]
    out["bar1"] = {"n": len(n), "flagged": len(k), "pass": len(n) >= 10 and len(k) >= 0.8 * len(n), "wilson": wilson(len(k), len(n))}
    back = [c for c in k if out["copies"][c]["approved_rejoined"]]
    out["bar2"] = {"rejoined": back, "pass": not back}
    # Amendment 3: a control counts when it reaches its family with the rule off even without the partial copies and
    # containers in the run; joined only through one of them, its link is shared footage and it is reported.
    single = [c for c in ids if kind[c] not in ("partial", "container")]
    keep = set(single)
    alone = cluster.resolve_all(single, [{k: v for k, v in r.items() if k not in COVER} for r in rows
                                         if r["a"] in keep and r["b"] in keep])[0]
    for c, v in out["controls"].items():
        v["family_without_generated"] = c in keep and with_family(alone, c)
    demoted = [c for c, v in out["controls"].items() if v["family_without_generated"] and not v["family_auto"]]
    out["bar3"] = {"demoted": demoted, "pass": not demoted,
                   "through_generated_only": sorted(c for c, v in out["controls"].items() if v["family_off"]
                                                    and not v["family_without_generated"] and v["kind"] != "container")}
    shared = {p for r in auto for segs in r.get("partial", {}).values() for s in segs for p in s["links"]}
    fixtures = [c for c in ids if kind[c] == "fixture"]
    fx_rows = [r for r in rows if kind[r["a"]] == kind[r["b"]] == "fixture"]
    bar4 = {"pairs": len(fx_rows), "partial": sorted(p for p in shared if p in {r["pair_id"] for r in fx_rows})}
    if frozen_rows is not None:  # (identity rows, frozen rows): Amendment 1
        same, fz = ({r["pair_id"]: r for r in x} for x in frozen_rows)
        bar4["columns_differ"] = sorted(r["pair_id"] for r in fx_rows
                                        if {k: v for k, v in r.items() if k not in COVER} != same.get(r["pair_id"]))
        bar4["bands_differ"] = sorted(r["pair_id"] for r in fx_rows if r["band"] != fz.get(r["pair_id"], {}).get("band"))
        mem = lambda recs: sorted(sorted(r["members"]) for r in recs)
        bar4["recordings_same"] = mem(cluster.resolve_all(fixtures, fx_rows)[0]) == mem(cluster.resolve_all(fixtures, list(fz.values()))[0])
        bar4["pass"] = (len(fx_rows) == 276 and not bar4["partial"] and not bar4["columns_differ"]
                        and not bar4["bands_differ"] and bar4["recordings_same"])
    else:
        bar4["pass"] = None
    out["bar4"] = bar4
    mixed = [(r["id"], sorted({fam[m] for m in r["members"]})) for r in auto if len({fam[m] for m in r["members"]}) > 1]
    wrong = [(x, s["recording"]) for r in auto for x, segs in r.get("partial", {}).items() for s in segs
             if not any(fam[m] == fam[x] for m in rid[s["recording"]]["members"])]
    out["bar5"] = {"mixed": mixed, "wrong_statements": wrong, "pass": not mixed and not wrong}
    out["pass"] = all(out[f"bar{i}"]["pass"] for i in range(1, 6))
    return out


def report(out):
    for i in range(1, 6):
        b = out[f"bar{i}"]
        print(f"bar {i}: {'PASS' if b['pass'] else 'FAIL' if b['pass'] is False else 'n/a'}  "
              + json.dumps({k: v for k, v in b.items() if k != "pass"}))
    print(f"overall: {'PASS' if out['pass'] else 'FAIL'}   (clusters.json equals a recompute: {out['recompute_matches']})")
    cp = out["copies"]
    print(f"\npartial copies: {len(cp)}; joined to their family with the rule off: {sum(v['joined_off'] for v in cp.values())}")
    for key in ("seg_s", "position", "variation"):
        t = Counter((v[key], v["flagged"]) for v in cp.values() if v["joined_off"])
        print(f"  flagged by {key}: " + ", ".join(f"{g}: {t[(g, True)]}/{t[(g, True)] + t[(g, False)]}"
                                                  for g in sorted({g for g, _ in t})))
    print("  not joined with the rule off, by segment length: "
          + json.dumps(Counter(v["seg_s"] for v in cp.values() if not v["joined_off"])))
    for c, v in sorted(cp.items()):
        print(f"  {c}: joined_off={v['joined_off']} flagged={v['flagged']} iou={v['iou']} seg={v['seg_s']}s "
              f"{v['position']} {v['variation']} approved_rejoined={v['approved_rejoined']}")
    ct = Counter((v["kind"], v["family_off"], v["family_auto"]) for v in out["controls"].values())
    print("\ncontrols (kind, with family rule off, with family rule on): count")
    for key, n in sorted(ct.items()):
        print(f"  {key}: {n}")


def selftest():
    truth = {"pz": {"clip": "pz", "kind": "partial", "family": "T01", "variation": "plain", "position": "after",
                    "segments": "T01:0.00-5.00@0.00-5.00", "span": (0.0, 5.0)}}

    def r(a, b, band, cover, core):
        return {"pair_id": f"{a}~{b}", "a": a, "b": b, "band": band, "aligned": "0.8", "verify_verdict": "",
                "a_start_s": "0", "a_end_s": "5", "b_start_s": "0", "b_end_s": "5", "cover_a": cover[0], "cover_b": cover[1],
                "core_a_start_s": core[0], "core_a_end_s": core[1], "core_b_start_s": core[0], "core_b_end_s": core[1]}
    ids = ["T01__orig", "T01__pip", "pz"]
    rows = [r("T01__orig", "T01__pip", "merged", (1, 1), (0, 10)), r("T01__orig", "pz", "merged", (0.5, 0.5), (0, 5)),
            r("T01__pip", "pz", "unresolved", (0.5, 0.5), (0, 5))]
    out = score(ids, rows, truth)
    assert out["copies"]["pz"]["joined_off"] and out["copies"]["pz"]["flagged"], out["copies"]
    assert not out["copies"]["pz"]["approved_rejoined"] and out["bar3"]["pass"] and out["bar5"]["pass"]
    rows[1]["cover_a"] = "1"  # the original's side fully covered: a trim, so it joins and is not flagged
    out = score(ids, rows, truth)
    assert not out["copies"]["pz"]["flagged"]
    print("selftest ok")


def main(argv=None):
    if (argv or sys.argv[1:])[:1] == ["selftest"]:
        return selftest()
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("truth")
    ap.add_argument("--identity", default="data/identity_old", help="fixtures matched at 23614a4 (all columns)")
    ap.add_argument("--frozen", default="data/match_dev_fixtures_floor020", help="the frozen dev run (bands, recordings)")
    a = ap.parse_args(argv)
    run = Path(a.run)
    ids = [c["id"] for c in json.loads((run / "clips.json").read_text())["clips"]]
    rows = list(csv.DictReader(open(run / "pairs.csv", newline="")))
    auto = json.loads((run / "clusters.json").read_text())["recordings"]
    load = lambda d: list(csv.DictReader(open(Path(d) / "pairs.csv", newline="")))
    frozen = (load(a.identity), load(a.frozen))
    report(score(ids, rows, read_truth(a.truth), auto, frozen))


if __name__ == "__main__":
    main()
