"""Withdraw a recording: which claims lose all their video support, which keep some (format in eval/run-format.md).

  PYTHONPATH=src python -m indexreel.withdraw <run dir> --claims claims.csv (--recording r2 | --clip <clip id>)

A claims file has one row per (claim, cited clip): columns clip, claim_id and optionally claim_text, as in a
hand-written claims sheet. Recordings are recomputed from pairs.csv plus audit.jsonl (cluster.resolve), so human
decisions and compilations count. A cited compilation supports a claim through the recordings it contains, each over
its span of the compilation, and withdrawing one of them loses that span only.
"""
import argparse
import csv
import json
from pathlib import Path

from indexreel import cluster


def run_recordings(run_dir, audit=None):
    """Recordings after human decisions (cluster.resolve); a compilation's recording carries its `segments`.
    audit=None reads audit.jsonl."""
    run_dir = Path(run_dir)
    ids = [c["id"] for c in json.loads((run_dir / "clips.json").read_text())["clips"]]
    rows = list(csv.DictReader(open(run_dir / "pairs.csv", newline="")))
    if audit is None:
        f = run_dir / "audit.jsonl"
        audit = [json.loads(line) for line in f.read_text().splitlines() if line.strip()] if f.exists() else []
    recs, comps = cluster.resolve(ids, rows, audit)
    by_id = {r["id"]: r for r in recs}
    for c in comps:
        by_id[c["recording"]]["segments"] = c["segments"]
    return recs


def read_claims(path):
    """{claim_id: [cited clip ids]} and {claim_id: claim_text}, in file order."""
    claims, text = {}, {}
    for r in csv.DictReader(open(path, newline="")):
        clips = claims.setdefault(r["claim_id"], [])
        if r["clip"] not in clips:
            clips.append(r["clip"])
        text.setdefault(r["claim_id"], r.get("claim_text") or "")
    return claims, text


def withdraw(recs, claims, withdrawn):
    """Sort the claims citing recording `withdrawn` by what video support they have left.

    kept: some cited clip lies in a recording the matcher separated from the withdrawn one.
    undecided: every remaining recording is tied to the withdrawn one by an unresolved pair, so it may be the same
    recording; this is neither support nor loss until a person decides the pair.
    lost: every cited clip is in the withdrawn recording.
    A cited compilation stands for the recordings of its segments: `lost_spans` lists the stretches of it that are
    footage of the withdrawn recording, and `partial` the stretches still left as support.
    """
    by_id = {r["id"]: r for r in recs}
    if withdrawn not in by_id:
        raise ValueError(f"no recording {withdrawn!r} in this run")
    rec_of = {c: r["id"] for r in recs for c in r["members"]}
    unknown = sorted({c for clips in claims.values() for c in clips} - rec_of.keys())
    if unknown:
        raise ValueError(f"claims cite clips not in this run: {unknown}")
    w = by_id[withdrawn]
    out = {"withdrawn": w, "lost": [], "kept": [], "undecided": [], "unaffected": []}
    for cid, clips in claims.items():
        cited = list(dict.fromkeys(rec_of[c] for c in clips))
        parts, lost_spans = [], []
        for r in cited:
            for s in by_id[r].get("segments", []) if r != withdrawn else []:
                span = {"clip": by_id[r]["members"][0], "recording": s["recording"], "start_s": s["start_s"], "end_s": s["end_s"]}
                (lost_spans if s["recording"] == withdrawn else parts).append(span)
        if withdrawn not in cited and not lost_spans:
            out["unaffected"].append(cid)
            continue
        direct = [r for r in cited if r != withdrawn and "segments" not in by_id[r]]
        remaining = list(dict.fromkeys(direct + [p["recording"] for p in parts]))
        tied = {r: [p for p in w["unresolved_pairs"] if p in by_id[r]["unresolved_pairs"]] for r in remaining}
        free = [r for r in remaining if not tied[r]]
        kind = "lost" if not remaining else "kept" if free else "undecided"
        left = free if free else remaining
        out[kind].append({"claim_id": cid, "remaining": left,
                          "tied_by": [] if free else sorted({p for r in remaining for p in tied[r]}),
                          "partial": [p for p in parts if p["recording"] in left], "lost_spans": lost_spans})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("run_dir")
    ap.add_argument("--claims", required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--recording")
    g.add_argument("--clip", help="withdraw the recording that holds this clip")
    a = ap.parse_args(argv)
    recs = run_recordings(a.run_dir)
    rid = a.recording or next((r["id"] for r in recs if a.clip in r["members"]), None)
    if rid is None:
        ap.error(f"clip {a.clip!r} is not in this run")
    claims, text = read_claims(a.claims)
    try:
        out = withdraw(recs, claims, rid)
    except ValueError as e:
        ap.error(str(e))
    w = out["withdrawn"]
    print(f"Withdrawn: {rid} ({w['status']}): {', '.join(w['members'])}")
    if w["unresolved_pairs"]:
        print(f"  Still undecided against it: {', '.join(w['unresolved_pairs'])}")
    for kind, title in (("lost", "Lose all video support"), ("kept", "Keep some video support"),
                        ("undecided", "Undecided: the rest may be the same recording")):
        print(f"\n{title} ({len(out[kind])})")
        for e in out[kind]:
            extra = f"; open pairs {', '.join(e['tied_by'])}" if e["tied_by"] else ""
            left = f" -> {', '.join(e['remaining'])}" if e["remaining"] else ""
            print(f"  {e['claim_id']}: {text.get(e['claim_id'], '')}{left}{extra}")
            for p in e["lost_spans"]:
                print(f"    lost: {p['clip']} contains footage of {rid} over {p['start_s']:g} to {p['end_s']:g} s")
            for p in e["partial"]:
                print(f"    left: {p['clip']} over {p['start_s']:g} to {p['end_s']:g} s ({p['recording']})")
    print(f"\nUnaffected: {', '.join(out['unaffected']) or 'none'}")


if __name__ == "__main__":
    main()
