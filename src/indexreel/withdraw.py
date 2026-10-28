"""Withdraw a recording: which claims lose all their video support, which keep some (format in eval/run-format.md).

  PYTHONPATH=src python -m indexreel.withdraw <run dir> --claims claims.csv (--recording r2 | --clip <clip id>)

A claims file has one row per (claim, cited clip): columns clip, claim_id and optionally claim_text, as in a
hand-written claims sheet. Recordings are recomputed from pairs.csv plus audit.jsonl, so human decisions count.
"""
import argparse
import csv
import json
from pathlib import Path

from indexreel import cluster


def run_recordings(run_dir, audit=None):
    """Recordings after human decisions: cluster.apply_audit, then cluster.recordings. audit=None reads audit.jsonl."""
    run_dir = Path(run_dir)
    ids = [c["id"] for c in json.loads((run_dir / "clips.json").read_text())["clips"]]
    rows = list(csv.DictReader(open(run_dir / "pairs.csv", newline="")))
    if audit is None:
        f = run_dir / "audit.jsonl"
        audit = [json.loads(line) for line in f.read_text().splitlines() if line.strip()] if f.exists() else []
    bands = cluster.apply_audit({r["pair_id"]: r["band"] for r in rows}, audit)
    return cluster.recordings(ids, [(r["pair_id"], r["a"], r["b"], bands[r["pair_id"]]) for r in rows])


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
        if withdrawn not in cited:
            out["unaffected"].append(cid)
            continue
        remaining = [r for r in cited if r != withdrawn]
        tied = {r: [p for p in w["unresolved_pairs"] if p in by_id[r]["unresolved_pairs"]] for r in remaining}
        free = [r for r in remaining if not tied[r]]
        kind = "lost" if not remaining else "kept" if free else "undecided"
        out[kind].append({"claim_id": cid, "remaining": free if free else remaining,
                          "tied_by": [] if free else sorted({p for r in remaining for p in tied[r]})})
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
    print(f"\nUnaffected: {', '.join(out['unaffected']) or 'none'}")


if __name__ == "__main__":
    main()
