"""Bands and recordings: how pair scores become clusters (the rules are written in eval/run-format.md)."""


def pair_id(a, b):
    """Stable id of an unordered pair of clip ids."""
    a, b = sorted((a, b))
    return f"{a}~{b}"


def band(aligned, score, merge_at, floor):
    """merged: aligned score at or above merge_at. apart: below the floor on both scores. unresolved: anything else."""
    if aligned >= merge_at:
        return "merged"
    if aligned < floor and score < merge_at:
        return "apart"
    return "unresolved"


def effective_band(row):
    """The band a pair of pairs.csv counts as once the verifier has spoken, before any human decision.

    merged stays merged unless the verifier says different or abstains (then the two disagree and a person decides);
    unresolved becomes merged on same and apart on different; apart stays apart, it is never sent to the verifier.
    """
    band, verdict = row["band"], row.get("verify_verdict") or ""
    if band == "merged":
        return "merged" if verdict in ("", "same") else "unresolved"
    if band == "unresolved":
        return {"same": "merged", "different": "apart"}.get(verdict, "unresolved")
    return "apart"


def apply_audit(bands, audit):
    """Human decisions override the bands in file order, the last entry for a pair takes effect; reset restores the computed band."""
    out = dict(bands)
    for e in audit:
        p = e["pair"]
        if p not in out:
            continue
        if e["action"] == "approve_merge":
            out[p] = "merged"
        elif e["action"] == "split":
            out[p] = "apart"
        elif e["action"] == "reset":
            out[p] = bands[p]
    return out


def recordings(clip_ids, pairs):
    """Group clips into recordings. pairs is a list of (pair_id, a, b, band).

    A recording is a connected component of the merged pairs. It is `unresolved` when any unresolved pair touches one
    of its clips (a decision is still needed), `merged` when it has two or more clips and none, `single` otherwise.
    `conflicts` lists apart pairs whose two clips ended up in the same recording (merging is not transitive).
    """
    root = {c: c for c in clip_ids}

    def find(c):
        while root[c] != c:
            root[c] = root[root[c]]
            c = root[c]
        return c

    for _, a, b, bd in pairs:
        if bd == "merged":
            root[find(a)] = find(b)
    groups = {}
    for c in clip_ids:  # input order fixes member order and recording numbering
        groups.setdefault(find(c), []).append(c)
    out = []
    for i, members in enumerate(groups.values(), 1):
        m = set(members)
        ev = [p for p, a, b, bd in pairs if bd == "merged" and a in m and b in m]
        un = [p for p, a, b, bd in pairs if bd == "unresolved" and (a in m or b in m)]
        co = [p for p, a, b, bd in pairs if bd == "apart" and a in m and b in m]
        status = "unresolved" if un else "merged" if len(members) > 1 else "single"
        out.append({"id": f"r{i}", "members": members, "status": status, "evidence_pairs": ev,
                    "unresolved_pairs": un, "conflicts": co})
    return out
