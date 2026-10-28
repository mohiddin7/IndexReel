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
        p = e.get("pair")  # decisions about a clip, such as confirm_compilation, have no pair
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


MIN_CORE = 2.0  # seconds: a source's core span in a compilation must last at least this long (set on the build split)
TOL = 0.5       # seconds: spans overlapping by more than this cover the same stretch (spans lie on a 1 s grid)
SHARE = 0.8     # a merged link is partial when it covers less than this share of both clips (eval/partial.md, build split)


def _covered(row, side):
    """True when the pair's match covers at least SHARE of clip `side` ("a" or "b"); None in runs without cover columns."""
    try:
        return float(row[f"cover_{side}"]) >= SHARE
    except (KeyError, TypeError, ValueError):
        return None


def _core(row, clip):
    """The core span of a pair in the timeline of `clip`, or None."""
    side = "a" if row["a"] == clip else "b"
    s, e = row.get(f"core_{side}_start_s"), row.get(f"core_{side}_end_s")
    return (float(s), float(e)) if s not in (None, "") and e not in (None, "") else None


def _find(root, c):
    while root.setdefault(c, c) != c:
        root[c] = root[root[c]]
        c = root[c]
    return c


def _stretches(spans):
    """Stretches of a clip's timeline from (start, end, pair id, strength) spans, strongest pair first.

    A span that overlaps an existing stretch by more than TOL belongs to the one it overlaps most (copies of one
    recording, or a pair with another clip that also contains several sources); any other span starts a stretch.
    Weak spans therefore cannot join two strong ones into one stretch. Returns lists of (start, end, pair id).
    """
    out = []  # [start, end, members] of the strongest span of each stretch
    for st, en, key, _ in sorted(spans, key=lambda s: (-s[3], s[0], s[2])):
        best = max(out, key=lambda t: min(en, t[1]) - max(st, t[0]), default=None)
        if best and min(en, best[1]) - max(st, best[0]) > TOL:
            best[2].append((st, en, key))
        else:
            out.append([st, en, [(st, en, key)]])
    return [t[2] for t in sorted(out, key=lambda t: (t[0], t[1]))]


def _spans(x, rows, bands, skip=()):
    """(start, end, pair id, aligned) of the core span in x of every merged or unresolved pair of x lasting MIN_CORE.

    Pairs with a clip in `skip` are left out: a candidate compilation is not a source of another clip.
    """
    out = []
    for p, b in bands.items():
        if b in ("merged", "unresolved") and x in (rows[p]["a"], rows[p]["b"]) \
                and not {rows[p]["a"], rows[p]["b"]} & set(skip) - {x}:
            c = _core(rows[p], x)
            if c and c[1] - c[0] >= MIN_CORE:
                out.append((c[0], c[1], p, float(rows[p].get("aligned") or 0)))
    return out


def _segments(x, rows, bands, root, confirmed):
    """The sources clip x is a compilation of as segments, or None.

    `root` joins the clips that other merged links connect, leaving out every candidate hub; `confirmed` are the
    compilations already found, whose pairs with x are not evidence. A source is a group of
    x's partners in one such component; a stretch of x's timeline is covered by the sources whose pairs have a core
    span there. Stretches that share a source are one source, so x is a compilation only if its stretches reach
    two or more separate sources: it matches different recordings over different parts of its own timeline. A jump
    cut of one recording reaches one source twice and is not one. Returns (segments, number of stretches).
    """
    other = lambda p: rows[p]["b"] if rows[p]["a"] == x else rows[p]["a"]
    stretches = _stretches(_spans(x, rows, bands, confirmed))
    if len(stretches) < 2:
        return None
    parent = list(range(len(stretches)))
    seen = {}
    for i, st in enumerate(stretches):
        for _, _, p in st:
            j = seen.setdefault(_find(root, other(p)), i)
            parent[_find_list(parent, i)] = _find_list(parent, j)
    if len({_find_list(parent, i) for i in range(len(stretches))}) < 2:
        return None
    groups = {}
    for st in stretches:
        for a, b, p in st:
            groups.setdefault(_find(root, other(p)), []).append((a, b, p))
    segs = [{"links": sorted(p for _, _, p in g), "start_s": min(a for a, _, _ in g), "end_s": max(b for _, b, _ in g),
             "clips": sorted({other(p) for _, _, p in g})} for g in groups.values()]
    return sorted(segs, key=lambda g: (g["start_s"], g["end_s"])), len(stretches)


def _find_list(parent, i):
    while parent[i] != i:
        i = parent[i]
    return i


def resolve_all(clip_ids, rows, audit=()):
    """Recordings, confirmed compilations and suggested compilations from pairs.csv rows plus the audit.

    The one recompute path every reader uses. Order: effective band of every pair, human decisions on top,
    compilation detection, connected components.

    A clip whose links reach different recordings over different parts of its own timeline is a *suggested*
    compilation. Nothing separates its sources until a person confirms it with an audit entry
    {"action": "confirm_compilation", "clip": id}; {"action": "dismiss_compilation", "clip": id} drops the
    suggestion. The last entry for a clip counts. A confirmed compilation keeps its links to its sources but none of
    them joins anything or counts as undecided (they are `partial`); it is a recording of its own with status
    `compilation`. While a suggestion stands, recordings are as if the rule did not exist, except that the recording
    holding the clip is `unresolved`, since a decision is needed.

    Partial copies: a pair that counts as merged after the audit and covers less than SHARE of both clips
    (`cover_a`, `cover_b`) shows shared footage, not a copy, unless one of its clips is a detected compilation. It is
    `partial` too. A clip with such a pair and no merged pair covering SHARE of it holds footage no link explains, so
    every merged pair of it is partial: a short clip inside it does not make it a copy either. The recording of each
    clip of a partial pair gets `partial` {clip: segments}: the recordings that clip shares footage with, over its
    cover span. Unresolved pairs are left as they are.

    Returns (recordings, compilations, suggestions); both lists hold
    {"clip", "recording", "segments": [{"recording", "clips", "links", "start_s", "end_s"}]} with the spans in the
    compilation's own timeline.

    Detection: a clip with two or more stretches is a candidate. Candidates are confirmed one at a time, the one
    with the most stretches first, and a detected compilation is no evidence for the others (a source shared by
    several compilations would otherwise look like one itself). Sources are found with all candidates left out of
    the graph, because two compilations that share sources would connect them. A candidate whose stretches all
    reach one source (a jump cut) or that lost its evidence is dropped and joins as an ordinary clip.
    """
    by_id = {r["pair_id"]: r for r in rows}
    bands = apply_audit({p: effective_band(r) for p, r in by_id.items()}, audit)
    pending = {x for x in clip_ids if len(_stretches(_spans(x, by_id, bands))) >= 2}
    hubs, segs = [], {}
    while pending:
        root = {}
        for p, b in bands.items():
            if b == "merged" and not {by_id[p]["a"], by_id[p]["b"]} & (pending | set(hubs)):
                root[_find(root, by_id[p]["a"])] = _find(root, by_id[p]["b"])
        found = {x: _segments(x, by_id, bands, root, hubs) for x in clip_ids if x in pending}
        valid = {x: f for x, f in found.items() if f}
        if not valid:
            break
        x = max(valid, key=lambda c: (valid[c][1], sum(g["end_s"] - g["start_s"] for g in valid[c][0])))
        hubs.append(x)
        segs[x] = valid[x][0]
        pending.discard(x)
    while True:  # the candidates that were left out of the graph no longer are: check each compilation again
        root = {}
        for p, b in bands.items():
            if b == "merged" and not {by_id[p]["a"], by_id[p]["b"]} & set(segs):
                root[_find(root, by_id[p]["a"])] = _find(root, by_id[p]["b"])
        again = {x: _segments(x, by_id, bands, root, set(segs) - {x}) for x in list(segs)}
        lost = [x for x, f in again.items() if f is None]
        if not lost:
            break
        for x in lost:
            del segs[x]
    segs = {x: again[x][0] for x in segs}
    said = {}
    for e in audit:
        if e.get("action") in ("confirm_compilation", "dismiss_compilation") and e.get("clip") in segs:
            said[e["clip"]] = e["action"]
    confirmed = {x for x in segs if said.get(x) == "confirm_compilation"}
    suggested = {x for x in segs if x not in said}
    partial = {p for p, b in bands.items() if b != "apart" and (by_id[p]["a"] in confirmed or by_id[p]["b"] in confirmed)}
    links = [p for p, b in bands.items() if b == "merged" and not {by_id[p]["a"], by_id[p]["b"]} & set(segs)]
    shared = {p for p in links if _covered(by_id[p], "a") is False and _covered(by_id[p], "b") is False}
    covered = {by_id[p][s] for p in links for s in "ab" if _covered(by_id[p], s)}
    cut = {by_id[p][s] for p in shared for s in "ab"} - covered  # holds footage no link explains: it contains, never is a copy
    shared |= {p for p in links if {by_id[p]["a"], by_id[p]["b"]} & cut}
    rec = recordings(clip_ids, [(p, r["a"], r["b"], "partial" if p in partial | shared else bands[p]) for p, r in by_id.items()])
    where = {c: r["id"] for r in rec for c in r["members"]}
    held = {}  # clip -> {recording it shares footage with: [(start, end, pair id, other clip)]}
    for p in sorted(shared):
        for x, y in ((by_id[p]["a"], by_id[p]["b"]), (by_id[p]["b"], by_id[p]["a"])):
            side = "a" if by_id[p]["a"] == x else "b"
            st, en = (float(by_id[p][f"cover_{side}_start_s"]), float(by_id[p][f"cover_{side}_end_s"])) \
                if by_id[p].get(f"cover_{side}_start_s") not in (None, "") else _core(by_id[p], x) \
                or (float(by_id[p][f"{side}_start_s"]), float(by_id[p][f"{side}_end_s"]))
            held.setdefault(x, {}).setdefault(where[y], []).append((st, en, p, y))
    for r in rec:
        for x in r["members"]:
            if x in held:
                r.setdefault("partial", {})[x] = sorted(
                    ({"recording": o, "clips": sorted({y for *_, y in g}), "links": sorted(p for _, _, p, _ in g),
                      "start_s": min(a for a, *_ in g), "end_s": max(b for _, b, *_ in g)} for o, g in held[x].items()),
                    key=lambda s: (s["start_s"], s["end_s"], s["recording"]))
    for r in rec:
        if r["members"][0] in confirmed:  # a confirmed compilation's links are all partial, so its recording has one clip
            r["status"] = "compilation"
        elif suggested & set(r["members"]):
            r["status"] = "unresolved"
    entry = lambda x: {"clip": x, "recording": where[x],
                       "segments": [{"recording": where[g["clips"][0]], "clips": g["clips"], "links": g["links"],
                                     "start_s": g["start_s"], "end_s": g["end_s"]} for g in segs[x]]}
    return rec, [entry(x) for x in clip_ids if x in confirmed], [entry(x) for x in clip_ids if x in suggested]


def resolve(clip_ids, rows, audit=()):
    """Recordings and confirmed compilations (see resolve_all, which also returns the suggestions)."""
    return resolve_all(clip_ids, rows, audit)[:2]
