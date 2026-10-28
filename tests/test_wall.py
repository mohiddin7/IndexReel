import http.client
import json
import shutil
import threading
from pathlib import Path

import pytest

from indexreel import wall

FIXTURE = Path(__file__).parent / "fixtures" / "run_fake"
DISCLAIMER = "This shows which clips come from the same recording. It does not say whether anything is true or false."


@pytest.fixture
def run(tmp_path):
    shutil.copytree(FIXTURE, tmp_path / "run")  # the fixture's own audit.jsonl must stay as committed
    return tmp_path / "run"


def lines(run):
    return (run / "audit.jsonl").read_text().splitlines()


def test_append_adds_one_line_and_keeps_the_old_ones(run):
    before = (run / "audit.jsonl").read_bytes()
    entry = wall.append_audit(run, "a_orig~a_refilm", "split", "different room")
    after = (run / "audit.jsonl").read_bytes()
    assert after.startswith(before) and len(lines(run)) == 2
    assert json.loads(lines(run)[-1]) == entry
    assert entry["action"] == "split" and entry["pair"] == "a_orig~a_refilm" and entry["actor"] == "human"
    assert entry["note"] == "different room" and entry["ts"].endswith("Z")


def test_append_rejects_unknown_pairs_and_actions_without_touching_the_file(run):
    before = (run / "audit.jsonl").read_bytes()
    with pytest.raises(ValueError):
        wall.append_audit(run, "x~y", "split")
    with pytest.raises(ValueError):
        wall.append_audit(run, "a_orig~a_refilm", "delete")
    assert (run / "audit.jsonl").read_bytes() == before


def test_append_after_a_file_without_a_final_newline(run):
    p = run / "audit.jsonl"
    p.write_text(p.read_text().rstrip("\n"))
    wall.append_audit(run, "a_orig~a_refilm", "split")
    assert [json.loads(x)["action"] for x in lines(run)] == ["approve_merge", "split"]


def test_append_creates_the_file_when_there_is_none(run):
    (run / "audit.jsonl").unlink()
    wall.append_audit(run, "b_cam1~b_cam2", "approve_merge")
    assert len(lines(run)) == 1


def test_concurrent_appends_stay_whole_lines(run):
    ts = [threading.Thread(target=wall.append_audit, args=(run, "b_cam1~b_cam2", "split", "x" * 400)) for _ in range(20)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(lines(run)) == 21
    assert all(json.loads(x)["pair"] for x in lines(run))


def test_state_applies_the_audit_to_pairs_and_recordings(run):
    s = wall.state(run)
    p = {x["id"]: x for x in s["pairs"]}
    assert p["a_copy~a_refilm"]["computed"] == "unresolved" and p["a_copy~a_refilm"]["band"] == "merged"
    assert p["a_copy~a_refilm"]["decision"]["note"] == "same screen, same room"
    assert {r["id"]: r["status"] for r in s["recordings"]}["r1"] == "merged"
    wall.append_audit(run, "a_orig~a_refilm", "split")
    s = wall.state(run)
    assert {x["id"]: x for x in s["pairs"]}["a_orig~a_refilm"]["band"] == "apart"
    assert s["recordings"][0]["conflicts"] == ["a_orig~a_refilm"]  # a_copy~a_refilm still merges them
    wall.append_audit(run, "a_orig~a_refilm", "reset")
    wall.append_audit(run, "a_copy~a_refilm", "reset")
    s = wall.state(run)
    assert {x["id"]: x for x in s["pairs"]}["a_copy~a_refilm"]["decision"] is None
    assert {x["id"]: x for x in s["pairs"]}["a_copy~a_refilm"]["band"] == "unresolved"
    assert s["pairs"][0]["evidence_times"] == [[0.5, 0.5], [10.0, 10.0], [19.5, 19.5]]


def test_page_carries_the_fixed_disclaimer():
    assert DISCLAIMER in wall.PAGE.read_text()


@pytest.fixture
def server(run):
    srv = wall.make_server(run)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv
    srv.shutdown()
    srv.server_close()


def call(srv, method, path, body=None, headers=None):
    c = http.client.HTTPConnection("127.0.0.1", srv.server_address[1])
    c.request(method, path, body=body, headers=headers or {})
    r = c.getresponse()
    return r.status, r.read()


def test_http_serves_page_state_and_frames(server):
    status, body = call(server, "GET", "/")
    assert status == 200 and DISCLAIMER in body.decode()
    status, body = call(server, "GET", "/api/state")
    assert status == 200 and len(json.loads(body)["pairs"]) == 15
    status, body = call(server, "GET", "/frames/a_orig~a_refilm.jpg")
    assert status == 200 and body[:2] == b"\xff\xd8"
    assert call(server, "GET", "/frames/../audit.jsonl")[0] == 404
    assert call(server, "GET", "/frames/%2e%2e/audit.jsonl")[0] == 404


def test_http_decision_is_appended_and_returned(server, run):
    head = {"Content-Type": "application/json"}
    status, body = call(server, "POST", "/api/decide", json.dumps({"pair": "b_cam1~b_cam2", "action": "approve_merge"}), head)
    assert status == 200 and json.loads(body)["audit"][-1]["pair"] == "b_cam1~b_cam2"
    assert len(lines(run)) == 2
    assert call(server, "POST", "/api/decide", json.dumps({"pair": "nope", "action": "split"}), head)[0] == 400
    assert call(server, "POST", "/api/decide", "not json", head)[0] == 400
    assert call(server, "POST", "/api/decide", json.dumps({"pair": "b_cam1~b_cam2", "action": "split"}),
                {"Content-Type": "text/plain"})[0] == 415
    assert len(lines(run)) == 2


def test_http_refuses_foreign_host_names(server, run):
    head = {"Host": "evil.example", "Content-Type": "application/json"}
    assert call(server, "GET", "/api/state", headers={"Host": "evil.example"})[0] == 403
    assert call(server, "POST", "/api/decide", json.dumps({"pair": "b_cam1~b_cam2", "action": "split"}), head)[0] == 403
    assert len(lines(run)) == 1


CLAIMS = """clip,claim_id,claim_text
a_orig,c1,only on the first recording
a_orig,c2,seen twice
c_alone,c2,seen twice
b_cam1,c3,both cameras
b_cam2,c3,both cameras
c_alone,c4,elsewhere
"""


@pytest.fixture
def claims_server(run, tmp_path):
    (tmp_path / "claims.csv").write_text(CLAIMS)
    srv = wall.make_server(run, claims=tmp_path / "claims.csv")
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv
    srv.shutdown()
    srv.server_close()


def test_withdraw_view_sorts_claims_with_the_audit_applied(run, tmp_path):
    (tmp_path / "claims.csv").write_text(CLAIMS)
    out = wall.withdraw_view(run, tmp_path / "claims.csv", "r1")  # r1 is merged because the audit approved a_copy~a_refilm
    assert [e["claim_id"] for e in out["lost"]] == ["c1"] and [e["claim_id"] for e in out["kept"]] == ["c2"]
    assert out["unaffected"] == ["c3", "c4"] and out["text"]["c1"] == "only on the first recording"
    out = wall.withdraw_view(run, tmp_path / "claims.csv", "r2")
    assert [(e["claim_id"], e["tied_by"]) for e in out["undecided"]] == [("c3", ["b_cam1~b_cam2"])]


def test_http_withdraw_and_its_errors(claims_server, server):
    status, body = call(claims_server, "GET", "/api/withdraw?recording=r1")
    assert status == 200 and [e["claim_id"] for e in json.loads(body)["lost"]] == ["c1"]
    assert json.loads(call(claims_server, "GET", "/api/state")[1])["claims"] is True
    assert call(claims_server, "GET", "/api/withdraw?recording=r99")[0] == 400
    assert call(claims_server, "GET", "/api/withdraw")[0] == 400
    assert call(server, "GET", "/api/withdraw?recording=r1")[0] == 400  # no claims file given
    assert json.loads(call(server, "GET", "/api/state")[1])["claims"] is False


def test_http_withdraw_refuses_claims_citing_unknown_clips(run, tmp_path):
    (tmp_path / "claims.csv").write_text("clip,claim_id\nnot_a_clip,x\n")
    srv = wall.make_server(run, claims=tmp_path / "claims.csv")
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        assert call(srv, "GET", "/api/withdraw?recording=r1")[0] == 400
    finally:
        srv.shutdown()
        srv.server_close()


def exported(run, tmp_path, claims=None):
    out = tmp_path / "export"
    wall.export(run, out, claims)
    page = (out / "index.html").read_text()
    data = json.loads(page.split('id="recorded-data">')[1].split("</script>")[0])
    return out, page, data


def test_export_is_a_static_read_only_copy_without_local_paths(run, tmp_path):
    before = (run / "audit.jsonl").read_bytes()
    out, page, data = exported(run, tmp_path)
    assert 'content="recorded"' in page and DISCLAIMER in page
    assert sorted(p.name for p in (out / "frames").iterdir()) == sorted(p.name for p in (run / "frames").iterdir())
    assert [r["status"] for r in data["state"]["recordings"]][0] == "merged"  # the recorded decision is applied
    assert data["state"]["pairs"][1]["decision"]["note"] == "same screen, same room"
    assert all("path" not in c for c in data["state"]["clips"]) and "clips/a_orig.mp4" not in page
    assert "indexreel match" not in page and "git_commit" not in page
    assert (run / "audit.jsonl").read_bytes() == before and not (out / "audit.jsonl").exists()


def test_export_embeds_the_withdraw_views_when_given_claims(run, tmp_path):
    (tmp_path / "claims.csv").write_text(CLAIMS)
    _, _, data = exported(run, tmp_path, tmp_path / "claims.csv")
    assert data["state"]["claims"] is True
    assert [e["claim_id"] for e in data["withdraw"]["r1"]["lost"]] == ["c1"]
    assert set(data["withdraw"]) == {r["id"] for r in data["state"]["recordings"]}


def test_export_cannot_be_closed_early_by_text_in_a_note(run, tmp_path):
    wall.append_audit(run, "b_cam1~b_cam2", "split", "</script><b>x</b>")
    _, page, data = exported(run, tmp_path)
    assert page.count("</script>") == 2 and "</script><b>" not in page  # the data block and the page script
    assert data["state"]["audit"][-1]["note"] == "</script><b>x</b>"


def test_export_refuses_a_full_directory_and_evidence_outside_frames(run, tmp_path):
    (tmp_path / "full").mkdir()
    (tmp_path / "full" / "keep.txt").write_text("x")
    with pytest.raises(ValueError):
        wall.export(run, tmp_path / "full")
    (run / "pairs.csv").write_text((run / "pairs.csv").read_text().replace("frames/b_cam1~b_cam2.jpg", "audit.jsonl"))
    with pytest.raises(ValueError):
        wall.export(run, tmp_path / "out2")
    assert not (tmp_path / "out2" / "index.html").exists()


def test_the_live_page_still_has_its_buttons_and_the_recorded_page_marks_itself():
    page = wall.PAGE.read_text()
    assert 'content="live"' in page and "RECORDED ?" in page and "<!--DATA-->" in page


COMPILATION = FIXTURE.parent / "run_fake_compilation"


def test_the_page_groups_clips_exactly_as_the_withdraw_stage_does():
    from indexreel import withdraw
    for fixture in (FIXTURE, COMPILATION):
        assert wall.state(fixture)["recordings"] == withdraw.run_recordings(fixture)


def test_a_verifier_answer_counts_before_any_human_decision(run):
    text = (run / "pairs.csv").read_text().splitlines()
    head = text[0].split(",")
    rows = [dict(zip(head, line.split(","))) for line in text[1:]]
    for r in rows:
        if r["pair_id"] == "b_cam1~b_cam2":
            r["verify_verdict"] = "different"
    (run / "pairs.csv").write_text("\n".join([",".join(head)] + [",".join(r[c] for c in head) for r in rows]) + "\n")
    p = {x["id"]: x for x in wall.state(run)["pairs"]}["b_cam1~b_cam2"]
    assert (p["matcher"], p["computed"], p["band"]) == ("unresolved", "apart", "apart")
    wall.append_audit(run, "b_cam1~b_cam2", "approve_merge")
    p = {x["id"]: x for x in wall.state(run)["pairs"]}["b_cam1~b_cam2"]
    assert p["band"] == "merged" and p["decision"]["action"] == "approve_merge"


def test_a_compilation_is_its_own_recording_with_partial_pairs_and_its_spans():
    s = wall.state(COMPILATION)
    comp = next(r for r in s["recordings"] if r["status"] == "compilation")
    assert comp["members"] == ["v_upload"] and len(comp["segments"]) == 3
    bands = {p["id"]: p["band"] for p in s["pairs"]}
    assert bands["p_orig~v_upload"] == "partial" and bands["p_copy~p_orig"] == "merged"
    assert "p_orig~v_upload" not in [p["id"] for p in s["pairs"] if p["band"] == "unresolved"]


def test_withdraw_view_names_the_lost_and_the_remaining_stretches_of_a_compilation(tmp_path):
    (tmp_path / "claims.csv").write_text("clip,claim_id,claim_text\nv_upload,k1,seen in the upload\np_orig,k2,seen at the source\n")
    s = wall.state(COMPILATION)
    r1 = next(r["id"] for r in s["recordings"] if "p_orig" in r["members"])
    out = wall.withdraw_view(COMPILATION, tmp_path / "claims.csv", r1)
    k1 = out["kept"][0]
    assert [(x["clip"], x["start_s"], x["end_s"]) for x in k1["lost_spans"]] == [("v_upload", 13.0, 52.0)]
    assert [(x["start_s"], x["end_s"]) for x in k1["partial"]] == [(0.0, 2.0), (87.0, 105.0)]
    assert [e["claim_id"] for e in out["lost"]] == ["k2"]


def test_the_page_words_for_compilation_spans_are_there():
    page = wall.PAGE.read_text()
    assert "contains footage of" in page and "still supports it over" in page
