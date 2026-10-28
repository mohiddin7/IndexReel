import csv
from pathlib import Path

import pytest

from indexreel import withdraw

RUN = Path(__file__).parent / "fixtures" / "run_fake"


@pytest.fixture(scope="module")
def recs():
    return withdraw.run_recordings(RUN)


def rec_of(recs, clip):
    return next(r["id"] for r in recs if clip in r["members"])


def verdicts(out):
    return {e["claim_id"]: k for k in ("lost", "kept", "undecided") for e in out[k]} | {c: "unaffected" for c in out["unaffected"]}


def test_recordings_follow_the_audit_not_the_raw_clusters(recs):
    # the audit approves a_copy~a_refilm, so recording a has no unresolved pair left
    a = next(r for r in recs if "a_orig" in r["members"])
    assert sorted(a["members"]) == ["a_copy", "a_orig", "a_refilm"] and a["status"] == "merged"
    split = [{"action": "split", "pair": p} for p in ("a_orig~a_refilm", "a_copy~a_refilm")]
    again = withdraw.run_recordings(RUN, audit=split)
    assert rec_of(again, "a_refilm") != rec_of(again, "a_orig")


def test_withdrawing_a_recording_sorts_the_claims(recs):
    claims = {"k1": ["a_orig"], "k2": ["a_copy", "c_alone"], "k3": ["a_refilm", "b_cam1"], "k4": ["b_cam2"]}
    out = withdraw.withdraw(recs, claims, rec_of(recs, "a_copy"))
    assert verdicts(out) == {"k1": "lost", "k2": "kept", "k3": "kept", "k4": "unaffected"}
    assert next(e for e in out["kept"] if e["claim_id"] == "k2")["remaining"] == [rec_of(recs, "c_alone")]


def test_support_tied_to_the_withdrawn_recording_by_an_unresolved_pair_is_undecided(recs):
    # b_cam1 and b_cam2 may be one recording: withdrawing b_cam1 neither keeps nor loses a claim resting on b_cam2
    claims = {"k5": ["b_cam1", "b_cam2"], "k6": ["b_cam1", "c_alone"], "k7": ["b_cam1"]}
    out = withdraw.withdraw(recs, claims, rec_of(recs, "b_cam1"))
    assert verdicts(out) == {"k5": "undecided", "k6": "kept", "k7": "lost"}
    assert out["undecided"][0]["tied_by"] == ["b_cam1~b_cam2"]
    assert out["withdrawn"]["unresolved_pairs"] == ["b_cam1~b_cam2"]


def test_claims_file_groups_rows_by_claim_and_rejects_unknown_clips(tmp_path, recs):
    p = tmp_path / "claims.csv"
    with open(p, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["clip", "claim_id", "claim_type", "claim_text"])
        w.writerows([["a_orig", "k1", "place", "Paris"], ["c_alone", "k1", "place", "Paris"], ["b_cam1", "k2", "date", "July 4"]])
    claims, text = withdraw.read_claims(p)
    assert claims == {"k1": ["a_orig", "c_alone"], "k2": ["b_cam1"]} and text["k1"] == "Paris"
    with pytest.raises(ValueError, match="not in this run"):
        withdraw.withdraw(recs, {"k9": ["nope"]}, "r1")
    with pytest.raises(ValueError, match="no recording"):
        withdraw.withdraw(recs, claims, "r99")


def test_cli_prints_the_three_lists(tmp_path, capsys):
    p = tmp_path / "claims.csv"
    p.write_text("clip,claim_id,claim_text\na_orig,k1,Paris\nc_alone,k2,Lyon\n")
    withdraw.main([str(RUN), "--claims", str(p), "--clip", "a_orig"])
    out = capsys.readouterr().out
    assert "Lose all video support (1)" in out and "k1" in out and "Unaffected: k2" in out


def test_a_cited_compilation_loses_only_the_span_of_the_withdrawn_recording():
    # v_upload holds r2 (0-2 s), r1 (13-52 s) and r3 (87-105 s); p_orig and p_copy are r1
    recs = withdraw.run_recordings(RUN.parent / "run_fake_compilation")
    claims = {"k1": ["v_upload"], "k2": ["p_orig"], "k3": ["z_alone"]}
    out = withdraw.withdraw(recs, claims, rec_of(recs, "p_orig"))
    assert verdicts(out) == {"k1": "kept", "k2": "lost", "k3": "unaffected"}
    k1 = out["kept"][0]
    assert k1["lost_spans"] == [{"clip": "v_upload", "recording": rec_of(recs, "p_orig"), "start_s": 13.0, "end_s": 52.0,
                                 "confirmed": True}]
    assert k1["unconfirmed"] == [] and k1["possible"] == []
    assert [(p["recording"], p["start_s"], p["end_s"]) for p in k1["partial"]] == [(rec_of(recs, "q_cam"), 0.0, 2.0),
                                                                                (rec_of(recs, "r_cam"), 87.0, 105.0)]
    # withdrawing the compilation itself loses a claim that cites only it
    assert verdicts(withdraw.withdraw(recs, claims, rec_of(recs, "v_upload")))["k1"] == "lost"


def test_an_unconfirmed_compilation_leaves_its_other_spans_undecided():
    # empty audit: v_upload is only a suggested compilation, held in r(p_orig) with links to q_cam and r_cam unresolved
    recs = withdraw.run_recordings(RUN.parent / "run_fake_compilation", audit=[])
    claims = {"k1": ["v_upload"], "k2": ["p_orig"], "k3": ["q_cam"]}
    out = withdraw.withdraw(recs, claims, rec_of(recs, "p_orig"))
    assert verdicts(out) == {"k1": "undecided", "k2": "lost", "k3": "unaffected"}
    k1 = out["undecided"][0]
    assert k1["unconfirmed"] == ["v_upload"]
    assert [(p["start_s"], p["end_s"], p["confirmed"]) for p in k1["lost_spans"]] == [(13.0, 52.0, False)]
    assert [(p["recording"], p["start_s"]) for p in k1["possible"]] == [(rec_of(recs, "q_cam"), 0.0), (rec_of(recs, "r_cam"), 87.0)]


def test_a_suggestion_with_two_sources_inside_the_withdrawn_recording_makes_its_losses_undecided():
    seg = lambda clips: {"recording": "r1", "clips": clips, "links": [], "start_s": 0.0, "end_s": 1.0}  # noqa: E731
    recs = [{"id": "r1", "members": ["a", "b", "c"], "status": "unresolved", "unresolved_pairs": [],
             "suggestions": {"c": [seg(["a"]), seg(["b"])]}}, {"id": "r2", "members": ["z"], "status": "single", "unresolved_pairs": []}]
    out = withdraw.withdraw(recs, {"kb": ["b"], "kz": ["z"]}, "r1")
    assert verdicts(out) == {"kb": "undecided", "kz": "unaffected"} and out["undecided"][0]["unconfirmed"] == ["c"]
