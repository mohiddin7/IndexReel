"""Same view, different recording: run once. Protocol: eval/sameview.md (frozen before any clip existed; Amendment 1:
run from a checkout of 66a179b with PYTHONPATH=<checkout>/src).

  PYTHONPATH=src python scripts/sameview.py prepare     every file in the manifest, flat, into data/sameview_in
  PYTHONPATH=src python -m indexreel match data/sameview_in --out data/sameview_run
  MODEL_API_KEY=... PYTHONPATH=src python -m indexreel.verify data/sameview_run --cache data/sameview_verify_cache --max-usd 3
  PYTHONPATH=src python scripts/sameview.py score

data/sameview/manifest.csv (written by the footage step): file (relative to data/sameview/, raw/<view>_<take>.mov or
whatsapp/<view>_<take>_whatsapp.mp4), view, take, kind (raw or whatsapp), original, platform. A recording is one
view and take; its WhatsApp copy belongs to it.
"""
import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "sameview"
RUN = ROOT / "data" / "sameview_run"
IN = ROOT / "data" / "sameview_in"


def manifest(path=DATA / "manifest.csv"):
    """{clip id: {view, recording, copy}} keyed by file stem, the id `indexreel match` gives a clip."""
    return {Path(m["file"]).stem: {"view": m["view"], "recording": f"{m['view']}_{m['take']}", "copy": m["kind"], "file": m["file"]}
            for m in csv.DictReader(open(path))}


def prepare():
    import shutil
    IN.mkdir(parents=True, exist_ok=True)
    for m in manifest().values():
        shutil.copy2(DATA / m["file"], IN / Path(m["file"]).name)


def kinds(meta, a, b):
    """positive: one recording and its copy; same_view: different recordings of one view; cross_view: the rest."""
    if meta[a]["recording"] == meta[b]["recording"]:
        return "positive"
    return "same_view" if meta[a]["view"] == meta[b]["view"] else "cross_view"


def score(run=RUN, manifest_path=DATA / "manifest.csv"):
    from indexreel import cluster
    meta = manifest(manifest_path)
    rows = list(csv.DictReader(open(run / "pairs.csv")))
    ids = [c["id"] for c in json.loads((run / "clips.json").read_text())["clips"]]
    recs, confirmed, suggested = cluster.resolve_all(ids, rows)
    where = {m: r["id"] for r in recs for m in r["members"]}
    eff = {r["pair_id"]: cluster.effective_band(r) for r in rows}
    kind = {r["pair_id"]: kinds(meta, r["a"], r["b"]) for r in rows}
    out = []
    fm = [p for p, k in kind.items() if k != "positive" and eff[p] == "merged"]
    mixed = [r["members"] for r in recs if len({meta[m]["recording"] for m in r["members"]}) > 1]
    sv = [p for p, k in kind.items() if k == "same_view"]
    out.append(f"1 automatic false merges: same-view {sum(p in fm for p in sv)}/{len(sv)}, all negatives {len(fm)}/{sum(k != 'positive' for k in kind.values())} {fm}; recordings mixing recordings {len(mixed)} {mixed}")
    copies = [c for c, m in meta.items() if m["copy"] == "whatsapp"]
    orig = {m["recording"]: c for c, m in meta.items() if m["copy"] == "raw"}
    found = [c for c in copies if where[c] == where[orig[meta[c]["recording"]]]]
    out.append(f"2 WhatsApp copies in their own recording {len(found)}/{len(copies)}; missed {sorted(set(copies) - set(found))}")
    out.append(f"recordings {len(recs)} (truth {len(orig)}); status {dict(Counter(r['status'] for r in recs))}; "
               f"compilation suggestions {[s['clip'] for s in suggested]}, confirmed {[c['clip'] for c in confirmed]}")
    out.append("every same-view and positive pair: kind, pair, aligned, score, band, verdict, confidence, effective band, reason")
    for r in sorted(rows, key=lambda r: (kind[r["pair_id"]], r["pair_id"])):
        if kind[r["pair_id"]] != "cross_view":
            out.append(f"  {kind[r['pair_id']]} {r['pair_id']} {r['aligned']} {r['score']} {r['band']} {r['verify_verdict'] or '-'} "
                       f"{r['verify_confidence'] or '-'} {eff[r['pair_id']]} | {r['verify_reason']}")
    shared = sorted({l for r in recs for parts in r.get("partial", {}).values() for s in parts for l in s["links"]})
    out.append(f"links shown as shared footage (partial, not joining recordings): {[(p, kind[p]) for p in shared]}")
    cv = [r for r in rows if kind[r["pair_id"]] == "cross_view"]
    out.append(f"cross-view pairs by band: {dict(Counter(r['band'] for r in cv))}; highest aligned {max((float(r['aligned']) for r in cv), default=float('nan')):.3f}")
    out.append(f"verify cost ${sum(float(r['verify_cost_usd'] or 0) for r in rows):.4f} at list prices")
    print("\n".join(out))


def selfcheck():
    meta = {"a": {"view": "v1", "recording": "v1_r1"}, "b": {"view": "v1", "recording": "v1_r1"},
            "c": {"view": "v1", "recording": "v1_r2"}, "d": {"view": "v2", "recording": "v2_r1"}}
    assert [kinds(meta, *p) for p in (("a", "b"), ("a", "c"), ("a", "d"))] == ["positive", "same_view", "cross_view"]


if __name__ == "__main__":
    {"prepare": prepare, "score": score, "selfcheck": selfcheck}[sys.argv[1]]()
