from indexreel import cluster


def row(a, b, band, core_a=None, core_b=None, verdict=""):
    a, b = sorted((a, b))
    r = {"pair_id": f"{a}~{b}", "a": a, "b": b, "band": band, "verify_verdict": verdict,
         "core_a_start_s": "", "core_a_end_s": "", "core_b_start_s": "", "core_b_end_s": ""}
    if core_a:
        r.update(core_a_start_s=core_a[0], core_a_end_s=core_a[1])
    if core_b:
        r.update(core_b_start_s=core_b[0], core_b_end_s=core_b[1])
    return r


def link(x, other, band, span, **kw):
    """A pair between clip x and a source, with the core span given in x's timeline."""
    a, b = sorted((x, other))
    return row(a, b, band, core_a=span if a == x else None, core_b=span if b == x else None, **kw)


def confirmed(ids, rows, audit=()):
    """resolve() with every suggested compilation confirmed by a person."""
    sug = cluster.resolve_all(ids, rows, audit)[2]
    return cluster.resolve(ids, rows, list(audit) + [{"action": "confirm_compilation", "clip": c["clip"]} for c in sug])


def members(rec):
    return sorted(sorted(r["members"]) for r in rec)


# a viral upload "v" made of four consecutive spans; g and k are two copies of the first source
IDS = ["g", "k", "n", "t", "v", "w"]
ROWS = [row("g", "k", "merged"), link("v", "g", "merged", (13, 52)), link("v", "k", "merged", (13, 52)),
        link("v", "n", "unresolved", (0, 13)), link("v", "w", "unresolved", (52, 63.5)),
        link("v", "t", "unresolved", (64, 125)), row("n", "t", "apart"), row("g", "n", "apart")]


def test_a_clip_matching_different_recordings_over_different_spans_is_a_compilation():
    rec, comps = confirmed(IDS, ROWS)
    assert members(rec) == [["g", "k"], ["n"], ["t"], ["v"], ["w"]]
    assert [c["clip"] for c in comps] == ["v"]
    assert [(s["start_s"], s["end_s"]) for s in comps[0]["segments"]] == [(0, 13), (13, 52), (52, 63.5), (64, 125)]
    status = {r["members"][0]: r["status"] for r in rec}
    assert status["v"] == "compilation" and status["n"] == status["t"] == "single"  # its links are not "undecided"
    seg = {s["links"][0]: s["recording"] for s in comps[0]["segments"]}
    assert len(set(seg.values())) == 4


def test_approving_every_link_does_not_join_the_sources():
    audit = [{"pair": p["pair_id"], "action": "approve_merge"} for p in ROWS if "v" in (p["a"], p["b"])]
    rec, comps = confirmed(IDS, ROWS, audit)
    assert members(rec) == [["g", "k"], ["n"], ["t"], ["v"], ["w"]] and len(comps) == 1


def test_one_recording_with_cuts_is_not_a_compilation():
    # a jump cut of o: its links reach the original and its copy, which are merged with each other: one group
    rows = [row("o", "p", "merged"), link("j", "o", "merged", (0, 3)), link("j", "p", "merged", (3, 6))]
    rec, comps = confirmed(["j", "o", "p"], rows)
    assert comps == [] and members(rec) == [["j", "o", "p"]]


def test_overlapping_spans_are_not_a_compilation_and_stay_a_conflict():
    rows = [link("x", "a", "merged", (0, 8)), link("x", "b", "merged", (4, 10)), row("a", "b", "apart")]
    rec, comps = confirmed(["a", "b", "x"], rows)
    assert comps == [] and members(rec) == [["a", "b", "x"]] and rec[0]["conflicts"] == ["a~b"]


def test_a_link_without_a_core_span_is_not_a_segment():
    rows = [link("x", "a", "merged", (0, 5)), link("x", "b", "unresolved", None), link("x", "c", "unresolved", (5, 6))]
    assert confirmed(["a", "b", "c", "x"], rows)[1] == []  # one segment long enough, one too short, one none


def test_two_segments_and_a_tolerated_crossfade():
    rows = [link("x", "a", "merged", (0, 6.5)), link("x", "b", "merged", (6, 12))]
    rec, comps = confirmed(["a", "b", "x"], rows)
    assert len(comps) == 1 and members(rec) == [["a"], ["b"], ["x"]]


def test_the_verifier_and_the_audit_come_first():
    rows = [link("x", "a", "merged", (0, 6)), link("x", "b", "unresolved", (6, 12), verdict="different")]
    assert confirmed(["a", "b", "x"], rows)[1] == []  # different makes the second link apart: one source only
    audit = [{"pair": "b~x", "action": "approve_merge"}]
    assert len(confirmed(["a", "b", "x"], rows, audit)[1]) == 1  # a person said it is the same


def test_without_compilations_resolve_equals_recordings():
    rows = [row("a", "b", "merged"), row("b", "c", "unresolved"), row("a", "c", "apart")]
    rec, comps, sug = cluster.resolve_all(["a", "b", "c"], rows)
    assert comps == [] and sug == [] and rec == cluster.recordings(["a", "b", "c"], [(r["pair_id"], r["a"], r["b"], r["band"]) for r in rows])


def test_two_copies_of_one_source_over_the_same_stretch_count_once():
    # o and p are two copies of one recording that the matcher did not merge; x also contains source q elsewhere
    rows = [link("x", "o", "merged", (0, 5)), link("x", "p", "unresolved", (0, 5)), link("x", "q", "merged", (5, 10))]
    rec, comps = confirmed(["o", "p", "q", "x"], rows)
    assert len(comps) == 1 and len(comps[0]["segments"]) == 3 and members(rec) == [["o"], ["p"], ["q"], ["x"]]
    only = [link("x", "o", "merged", (0, 5)), link("x", "p", "unresolved", (0, 5))]
    assert confirmed(["o", "p", "x"], only)[1] == []  # one stretch: not a compilation


def test_a_suggestion_changes_nothing_until_a_person_confirms_it():
    rec, comps, sug = cluster.resolve_all(IDS, ROWS)
    assert comps == [] and [s["clip"] for s in sug] == ["v"]
    plain = cluster.recordings(IDS, [(r["pair_id"], r["a"], r["b"], cluster.effective_band(r)) for r in ROWS])
    assert [r["members"] for r in rec] == [r["members"] for r in plain]  # joined as if the rule did not exist
    holder = next(r for r in rec if "v" in r["members"])
    assert holder["status"] == "unresolved"  # but a decision is needed
    assert cluster.resolve(IDS, ROWS) == (rec, comps)
    assert [s["clip"] for s in sug][0] == "v" and [g["clips"] for g in sug[0]["segments"]] == [["n"], ["g", "k"], ["w"], ["t"]]


def test_confirming_separates_the_sources_and_dismissing_leaves_them_joined():
    rec, comps, sug = cluster.resolve_all(IDS, ROWS, [{"action": "confirm_compilation", "clip": "v", "ts": "t1"}])
    assert [c["clip"] for c in comps] == ["v"] and sug == [] and members(rec) == [["g", "k"], ["n"], ["t"], ["v"], ["w"]]
    rec, comps, sug = cluster.resolve_all(IDS, ROWS, [{"action": "dismiss_compilation", "clip": "v"}])
    assert comps == [] and sug == [] and any(set(r["members"]) >= {"g", "v"} for r in rec)
    again = [{"action": "dismiss_compilation", "clip": "v"}, {"action": "confirm_compilation", "clip": "v"}]
    assert [c["clip"] for c in cluster.resolve_all(IDS, ROWS, again)[1]] == ["v"]  # the last entry counts


def test_a_confirmation_for_a_clip_that_is_not_a_suggestion_does_nothing():
    rows = [row("a", "b", "merged"), row("b", "c", "unresolved")]
    audit = [{"action": "confirm_compilation", "clip": "b"}]
    assert cluster.resolve_all(["a", "b", "c"], rows, audit) == (cluster.resolve_all(["a", "b", "c"], rows)[0], [], [])


def test_audit_lines_about_a_clip_do_not_break_the_band_decisions():
    bands = {"a~b": "unresolved"}
    audit = [{"action": "confirm_compilation", "pair": None, "clip": "a"}, {"action": "confirm_compilation", "clip": "a"},
             {"action": "approve_merge", "pair": "a~b"}]
    assert cluster.apply_audit(bands, audit) == {"a~b": "merged"}
