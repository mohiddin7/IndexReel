import numpy as np

from indexreel import cluster, sscd, withdraw


def row(a, b, band, cover=None, span_a=None, span_b=None, verdict=""):
    """A pair; cover is (cover_a, cover_b) and the spans are the cover spans, all in the sorted (a, b) order."""
    r = {"pair_id": f"{a}~{b}", "a": a, "b": b, "band": band, "verify_verdict": verdict, "aligned": "0.8",
         "a_start_s": "0", "a_end_s": "5", "b_start_s": "0", "b_end_s": "5",
         "core_a_start_s": "", "core_a_end_s": "", "core_b_start_s": "", "core_b_end_s": ""}
    if cover:
        sa, sb = span_a or (0, 5), span_b or (0, 5)
        r.update(cover_a=str(cover[0]), cover_b=str(cover[1]), cover_a_start_s=str(sa[0]), cover_a_end_s=str(sa[1]),
                 cover_b_start_s=str(sb[0]), cover_b_end_s=str(sb[1]))
    return r


def members(rec):
    return sorted(sorted(r["members"]) for r in rec)


# o is a 20 s recording, p its full copy, x holds o's last 7 s and then 7 s of a recording that is not in the run
IDS = ["o", "p", "x"]
ROWS = [row("o", "p", "merged", (1, 1), (0, 20), (0, 20)), row("o", "x", "merged", (0.35, 0.5), (13, 20), (0, 7)),
        row("p", "x", "merged", (0.35, 0.5), (13, 20), (0, 7))]


def test_a_link_covering_part_of_both_clips_records_shared_footage_instead_of_joining():
    rec, comps, sug = cluster.resolve_all(IDS, ROWS)
    assert members(rec) == [["o", "p"], ["x"]] and comps == sug == []
    r_op, r_x = (next(r for r in rec if c in r["members"]) for c in ("o", "x"))
    assert r_x["status"] == "single" and r_x["partial"] == {"x": [{"recording": r_op["id"], "clips": ["o", "p"],
                                                                   "links": ["o~x", "p~x"], "start_s": 0.0, "end_s": 7.0}]}
    assert r_op["partial"]["o"] == [{"recording": r_x["id"], "clips": ["x"], "links": ["o~x"], "start_s": 13.0, "end_s": 20.0}]


def test_a_trim_or_a_full_copy_still_joins():
    rows = [row("o", "t", "merged", (0.35, 1), (13, 20), (0, 7)), row("o", "p", "merged", (1, 0.9))]
    rec = cluster.resolve_all(["o", "p", "t"], rows)[0]
    assert members(rec) == [["o", "p", "t"]] and not any("partial" in r for r in rec)


def test_a_short_clip_inside_the_partial_copy_does_not_pull_it_back_in():
    # t (a trim of o) lies inside x's copied stretch: x~t covers all of t, but x is never covered by anything
    rows = ROWS + [row("o", "t", "merged", (0.2, 1)), row("p", "t", "merged", (0.2, 1)), row("t", "x", "merged", (1, 0.3))]
    rec = cluster.resolve_all(["o", "p", "t", "x"], rows)[0]
    assert members(rec) == [["o", "p", "t"], ["x"]]
    x = next(r for r in rec if r["members"] == ["x"])
    assert sorted(x["partial"]["x"][0]["links"]) == ["o~x", "p~x", "t~x"]


def test_unresolved_stays_undecided_and_the_audit_decides():
    rows = [ROWS[0], row("o", "x", "unresolved", (0.35, 0.5), (13, 20), (0, 7))]
    rec = cluster.resolve_all(IDS[:2] + ["x"], rows)[0]
    assert next(r for r in rec if "x" in r["members"])["status"] == "unresolved" and not any("partial" in r for r in rec)
    approved = cluster.resolve_all(IDS, rows, [{"pair": "o~x", "action": "approve_merge"}])[0]
    assert members(approved) == [["o", "p"], ["x"]] and "partial" in next(r for r in approved if r["members"] == ["x"])
    split = cluster.resolve_all(IDS, ROWS, [{"pair": "o~x", "action": "split"}, {"pair": "p~x", "action": "split"}])[0]
    assert members(split) == [["o", "p"], ["x"]] and not any("partial" in r for r in split)


def test_runs_without_cover_columns_are_unchanged():
    old = [{k: v for k, v in r.items() if not k.startswith("cover_")} for r in ROWS]
    assert members(cluster.resolve_all(IDS, old)[0]) == [["o", "p", "x"]]


def test_a_detected_compilation_keeps_the_compilation_rule():
    # v is a+b back to back; both links cover part of both clips, but v is a compilation suggestion, so it stays joined
    rows = [row("a", "v", "merged", (0.5, 0.5)), row("b", "v", "merged", (0.5, 0.5))]
    for r, span in zip(rows, ((0, 5), (5, 10))):
        r.update(core_b_start_s=str(span[0]), core_b_end_s=str(span[1]))
    rec, comps, sug = cluster.resolve_all(["a", "b", "v"], rows)
    assert [s["clip"] for s in sug] == ["v"] and members(rec) == [["a", "b", "v"]] and not any("partial" in r for r in rec)


def test_withdrawing_the_source_loses_the_shared_stretch_only():
    rec = cluster.resolve_all(IDS, ROWS)[0]
    r_op = next(r["id"] for r in rec if "o" in r["members"])
    out = withdraw.withdraw(rec, {"k1": ["x"], "k2": ["o"]}, r_op)
    k1 = out["kept"][0]
    assert k1["claim_id"] == "k1" and k1["lost_spans"] == [{"clip": "x", "recording": r_op, "start_s": 0.0, "end_s": 7.0,
                                                           "confirmed": True}]
    assert [e["claim_id"] for e in out["lost"]] == ["k2"]


def frames(seq, d=8):
    """Unit embeddings for a sequence of scene ids: equal ids are identical frames, different ids are orthogonal."""
    out = np.zeros((len(seq), d), np.float32)
    out[np.arange(len(seq)), seq] = 1
    return out, out


def test_cover_spans_on_a_shared_stretch_a_static_scene_and_a_jump_cut():
    src = frames([0, 1, 2, 3, 4, 5, 6, 7])
    tail = (np.vstack([src[0][4:], np.zeros((4, 8), np.float32)]),) * 2  # o's last 4 frames, then 4 unlike anything
    al = sscd.aligned_match(src, tail)
    assert sscd.cover_spans(src, tail, al[1], al[4], 2) == ((4, 8), (0, 4))
    still = frames([0] * 10)
    assert sscd.cover_spans(still, still, 3, False, 2) == ((0, 10), (0, 10))  # whatever offset the score chose
    jump = (np.vstack([src[0][0:3], src[0][5:8]]),) * 2
    al = sscd.aligned_match(jump, src)
    assert sscd.cover_spans(jump, src, al[1], al[4], 2)[0] == (0, 6)  # both pieces, across the cut



def test_a_partial_pair_inside_one_recording_names_no_recording():
    # c lies inside a (so a~c merges), b is a full copy of a, and b~c covers part of both: c is already in a's recording
    rows = [row("a", "b", "merged", (1, 1)), row("a", "c", "merged", (0.5, 1)), row("b", "c", "merged", (0.5, 0.6))]
    rec = cluster.resolve_all(["a", "b", "c"], rows)[0]
    assert members(rec) == [["a", "b", "c"]] and "partial" not in rec[0]
