"""Withdraw a recording: which claims lose all their video support, which keep some (format in eval/run-format.md).

  PYTHONPATH=src python -m indexreel.withdraw <run dir> --claims claims.csv (--recording r2 | --clip <clip id>)

A claims file has one row per (claim, cited clip): columns clip, claim_id and optionally claim_text, as in a
hand-written claims sheet. Recordings are recomputed from pairs.csv plus audit.jsonl (cluster.resolve), so human
decisions and compilations count. A cited compilation supports a claim through the recordings it contains, each over
its span of the compilation, and withdrawing one of them loses that span only. Until a person confirms a suggested
compilation, its other spans are undecided support, never kept.
"""
import argparse
import csv
import json
from pathlib import Path

from indexreel import cluster


def run_recordings(run_dir, audit=None):
    """Recordings after human decisions (cluster.resolve_all). A confirmed compilation's recording carries its
    `segments`; the recording holding a suggested one carries `suggestions` {clip: segments}. audit=None reads audit.jsonl."""
    run_dir = Path(run_dir)
    ids = [c["id"] for c in json.loads((run_dir / "clips.json").read_text())["clips"]]
    rows = list(csv.DictReader(open(run_dir / "pairs.csv", newline="")))
    if audit is None:
        f = run_dir / "audit.jsonl"
        audit = [json.loads(line) for line in f.read_text().splitlines() if line.strip()] if f.exists() else []
    recs, comps, suggested = cluster.resolve_all(ids, rows, audit)
    by_id = {r["id"]: r for r in recs}
    for c in comps:
        by_id[c["recording"]]["segments"] = c["segments"]
    for c in suggested:
        by_id[c["recording"]].setdefault("suggestions", {})[c["clip"]] = c["segments"]
    return recs


def join_how(rows, audit):
    """{pair id: how that pair joined its clips}, for the pairs that are merged in the end: a person approved it, or it
    joined automatically (the matcher alone, matcher and verifier agreeing, or the verifier over an unsure matcher)."""
    approved = {}
    for e in audit:  # the last entry for a pair counts; reset hands it back to the machine
        if e.get("pair") and e["action"] in ("approve_merge", "split", "reset"):
            approved[e["pair"]] = e["action"] == "approve_merge"
    out = {}
    for r in rows:
        verdict = r.get("verify_verdict") or ""
        if approved.get(r["pair_id"]):
            out[r["pair_id"]] = "approved by a person"
        elif r["band"] == "unresolved" and verdict == "same":
            out[r["pair_id"]] = "joined automatically by the verifier (the matcher was unsure)"
        elif r["band"] == "merged" and verdict == "same":
            out[r["pair_id"]] = "joined automatically (matcher and verifier agree)"
        elif r["band"] == "merged":
            out[r["pair_id"]] = "joined automatically by the matcher (the verifier did not check it)"
    return out


def run_joins(run_dir, audit=None):
    """join_how for a run directory; audit=None reads audit.jsonl."""
    run_dir = Path(run_dir)
    rows = list(csv.DictReader(open(run_dir / "pairs.csv", newline="")))
    if audit is None:
        f = run_dir / "audit.jsonl"
        audit = [json.loads(line) for line in f.read_text().splitlines() if line.strip()] if f.exists() else []
    return join_how(rows, audit)


def read_claims(path, log=print):
    """{claim_id: [cited clip ids]} and {claim_id: claim_text}, in file order. A sheet with a `status` column (written
    by `indexreel claims`) counts only its approved rows and says how many it skipped; one without counts every row."""
    claims, text = {}, {}
    reader = csv.DictReader(open(path, newline=""))
    rows = list(reader)
    if "status" in (reader.fieldnames or []):
        kept = [r for r in rows if r["status"] == "approved"]
        if len(kept) < len(rows):
            log(f"claims: {len(rows) - len(kept)} of {len(rows)} rows are not approved and are not counted")
        rows = kept
    for r in rows:
        clips = claims.setdefault(r["claim_id"], [])
        if r["clip"] not in clips:
            clips.append(r["clip"])
        text.setdefault(r["claim_id"], r.get("claim_text") or "")
    return claims, text


def withdraw(recs, claims, withdrawn, joins=None):
    """Sort the claims citing recording `withdrawn` by what video support they have left.

    kept: some cited clip lies in a recording the matcher separated from the withdrawn one. That says the footage is
    still cited, not that it shows the same event: a copy the matcher missed or another event reads the same. With
    `joins` (run_joins) each entry lists, for the recordings it still cites, how each of their pairs was joined.
    undecided: every remaining recording is tied to the withdrawn one by an unresolved pair, so it may be the same
    recording; this is neither support nor loss until a person decides the pair.
    lost: every cited clip is in the withdrawn recording.
    A cited compilation stands for the recordings of its segments: `lost_spans` lists the stretches of it that are
    footage of the withdrawn recording, and `partial` the stretches still left as support. A cited clip that is only a
    suggested compilation (`unconfirmed`) loses its span of the withdrawn recording too, but its other spans are
    `possible` support: undecided until a person confirms or dismisses it. A suggestion that puts two or more source
    groups inside the withdrawn recording leaves the extent of the withdrawal open, so nothing citing it is lost.
    A cited clip that shares footage with the withdrawn recording (a `partial` entry naming it) loses that stretch,
    listed in `lost_spans`, and keeps the support of its own recording.
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
    open_ = sorted(c for c, segs in w.get("suggestions", {}).items() if sum(s["recording"] == withdrawn for s in segs) > 1)
    for cid, clips in claims.items():
        cited = list(dict.fromkeys(rec_of[c] for c in clips))
        parts, lost_spans, possible = [], [], []
        for r in cited:
            for s in by_id[r].get("segments", []) if r != withdrawn else []:
                span = {"clip": by_id[r]["members"][0], "recording": s["recording"], "start_s": s["start_s"], "end_s": s["end_s"],
                        "confirmed": True}
                (lost_spans if s["recording"] == withdrawn else parts).append(span)
        for c in clips:
            r = rec_of[c]
            for s in by_id[r].get("partial", {}).get(c, []) if r != withdrawn else []:
                if s["recording"] == withdrawn:  # shared footage: that stretch may be the withdrawn recording's
                    lost_spans.append({"clip": c, "recording": withdrawn, "start_s": s["start_s"], "end_s": s["end_s"],
                                       "confirmed": True})
            for s in by_id[r].get("suggestions", {}).get(c, []):
                if s["recording"] == r != withdrawn:
                    continue  # the clip's own recording supports it directly
                span = {"clip": c, "recording": s["recording"], "start_s": s["start_s"], "end_s": s["end_s"], "confirmed": False}
                (lost_spans if s["recording"] == withdrawn else possible).append(span)
        if withdrawn not in cited and not lost_spans:
            out["unaffected"].append(cid)
            continue
        direct = [r for r in cited if r != withdrawn and "segments" not in by_id[r]]
        remaining = list(dict.fromkeys(direct + [p["recording"] for p in parts]))
        tied = {r: [p for p in w["unresolved_pairs"] if p in by_id[r]["unresolved_pairs"]] for r in remaining}
        free = [r for r in remaining if not tied[r]]
        unconfirmed = sorted({p["clip"] for p in lost_spans + possible if not p["confirmed"]} | (set(open_) if withdrawn in cited else set()))
        kind = "kept" if free else "undecided" if remaining or possible or unconfirmed else "lost"
        left = free if free else list(dict.fromkeys(remaining + [p["recording"] for p in possible]))
        out[kind].append({"claim_id": cid, "remaining": left,
                          "tied_by": [] if free else sorted({p for r in remaining for p in tied[r]}),
                          "partial": [p for p in parts if p["recording"] in left], "lost_spans": lost_spans,
                          "possible": possible, "unconfirmed": unconfirmed,
                          "joins": [{"recording": r, "pair": p, "how": joins[p]} for r in left
                                    for p in by_id[r]["evidence_pairs"] if p in (joins or {})]})
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
        out = withdraw(recs, claims, rid, run_joins(a.run_dir))
    except ValueError as e:
        ap.error(str(e))
    w = out["withdrawn"]
    print(f"Withdrawn: {rid} ({w['status']}): {', '.join(w['members'])}")
    if w["unresolved_pairs"]:
        print(f"  Still undecided against it: {', '.join(w['unresolved_pairs'])}")
    for kind, title in (("lost", "Lose all video support"), ("kept", "Still cited by footage from another recording (not checked to show the same event)"),
                        ("undecided", "Undecided: the rest may be the same recording")):
        print(f"\n{title} ({len(out[kind])})")
        for e in out[kind]:
            extra = f"; open pairs {', '.join(e['tied_by'])}" if e["tied_by"] else ""
            left = f" -> {', '.join(e['remaining'])}" if e["remaining"] else ""
            print(f"  {e['claim_id']}: {text.get(e['claim_id'], '')}{left}{extra}")
            for j in e["joins"]:
                print(f"    {j['recording']}: {j['pair']} {j['how']}")
            for p in e["lost_spans"]:
                print(f"    lost: {p['clip']} contains footage of {rid} over {p['start_s']:g} to {p['end_s']:g} s")
            for p in e["partial"]:
                print(f"    left: {p['clip']} over {p['start_s']:g} to {p['end_s']:g} s ({p['recording']})")
            for p in e["possible"]:
                print(f"    possible: {p['clip']} over {p['start_s']:g} to {p['end_s']:g} s ({p['recording']}), compilation not yet confirmed")
            if e["unconfirmed"]:
                print(f"    confirm or dismiss the possible compilation {', '.join(e['unconfirmed'])} to decide")
    print(f"\nUnaffected: {', '.join(out['unaffected']) or 'none'}")


if __name__ == "__main__":
    main()
