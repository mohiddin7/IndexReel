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


def test_withdraw_view_says_how_each_join_of_a_kept_claim_was_made_and_the_page_words_it(run, tmp_path):
    (tmp_path / "claims.csv").write_text("clip,claim_id,claim_text\na_orig,c5,filmed twice\nb_cam1,c5,filmed twice\n")
    out = wall.withdraw_view(run, tmp_path / "claims.csv", "r2")
    assert [e["claim_id"] for e in out["kept"]] == ["c5"]
    how = {j["pair"]: j["how"] for j in out["kept"][0]["joins"]}
    assert how["a_copy~a_refilm"] == "approved by a person"  # the audit's approve_merge
    assert how["a_orig~a_refilm"].startswith("joined automatically")
    page = (Path(wall.__file__).parent / "index.html").read_text()
    assert "Still cited by footage from another recording (not checked to show the same event)" in page
    assert "Keep some video support" not in page and "e.joins" in page


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


def test_wilson_matches_the_intervals_written_in_the_eval_files():
    lo, hi = wall.wilson(48, 48)
    assert (round(lo, 2), round(hi, 2)) == (0.93, 1.00)
    lo, hi = wall.wilson(2, 1080)
    assert (round(lo, 4), round(hi, 4)) == (0.0005, 0.0067)
    assert round(wall.wilson(0, 1440)[1], 4) == 0.0027
    assert [round(x, 2) for x in wall.wilson(4, 4)] == [0.51, 1.0] and [round(x, 2) for x in wall.wilson(1, 4)] == [0.05, 0.70]


def test_results_status_comes_from_the_count_and_the_bar_not_from_the_file(tmp_path):
    rows = [{"label": "a", "k": 4, "n": 4, "bar_op": ">=", "bar_k": 3, "status": "FAIL"},
            {"label": "b", "k": 1, "n": 4, "bar_op": ">=", "bar_k": 3},
            {"label": "c", "k": 0, "n": 9, "bar_op": "<=", "bar_k": 0},
            {"label": "d", "k": 2, "n": 9, "bar_op": "<=", "bar_k": 0},
            {"label": "e", "k": 5, "n": 9},
            {"label": "f"}, {"label": "g", "status": "FAIL"}]
    (tmp_path / "r.json").write_text(json.dumps({"version": 1, "rows": rows}))
    out = wall.read_results(tmp_path / "r.json")
    assert [r["status"] for r in out] == ["PASS", "FAIL", "PASS", "FAIL", "REPORTED", "NOT RUN", "FAIL"]
    assert out[4]["ci"] and out[5]["ci"] is None


def test_the_results_file_in_eval_is_consistent_and_keeps_the_frozen_failures():
    root = Path(__file__).resolve().parents[1]
    rows = wall.read_results(wall.RESULTS)
    for r in rows:
        assert (root / r["source"]).is_file()  # every row names a file that exists
        k, n = r.get("k"), r.get("n")
        if k is not None and r.get("bar_op"):  # the status follows from the count and the bar, however the rows are filled in
            assert r["status"] == ("PASS" if (k >= r["bar_k"] if r["bar_op"] == ">=" else k <= r["bar_k"]) else "FAIL")
        if k is not None and n:
            assert 0 <= k <= n and r["ci"][0] <= k / n <= r["ci"][1]
        assert r["status"] in {"PASS", "FAIL", "REPORTED", "NOT RUN"}
    status = {r["label"]: r["status"] for r in rows}  # results of frozen runs: they are not rows that get filled in later
    assert status["SAM 3.1, simulated re-film recovered"] == "FAIL"
    assert status["Dev fixture recordings unchanged by the rule"] == "FAIL"
    assert status["Recordings mixing families after approving the correct links"] == "FAIL"
    assert [r["status"] for r in rows if r["group"].startswith("Held-out run 1")] == ["FAIL", "PASS"]


def test_results_reach_the_state_the_server_and_the_export(run, tmp_path):
    assert wall.state(run)["results"] is None
    s = wall.state(run, results=wall.RESULTS)
    assert len(s["results"]) == len(wall.read_results(wall.RESULTS))
    srv = wall.make_server(run, results=wall.RESULTS)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        assert len(json.loads(call(srv, "GET", "/api/state")[1])["results"]) == len(s["results"])
    finally:
        srv.shutdown()
        srv.server_close()
    _, _, data = exported(run, tmp_path)
    assert data["state"]["results"] is None
    wall.export(run, tmp_path / "with", results=wall.RESULTS)
    page = (tmp_path / "with" / "index.html").read_text()
    assert "eval/gate-result.md" in page and 'id="h-res"' in page


def test_pairs_carry_the_core_span_when_the_run_has_one_and_the_page_shows_the_history(run):
    assert wall.state(run)["pairs"][0]["core"] == [[0.0, 20.0], [0.0, 20.0]]
    older = [line.split(",")[:-4] for line in (run / "pairs.csv").read_text().splitlines()]  # a run made before the core columns
    (run / "pairs.csv").write_text("\n".join(",".join(r) for r in older) + "\n")
    assert all(p["core"] is None for p in wall.state(run)["pairs"])
    page = wall.PAGE.read_text()
    assert "History" in page and "The verifier changed these" in page and "matching core" in page
    assert "experimental" in page and "possible compilation" in page


def test_clip_sources_reach_the_page_data_and_the_export(run, tmp_path):
    clips = json.loads((run / "clips.json").read_text())
    clips["clips"][0]["source"] = {"platform": "x", "url": "https://x.com/someone/status/1", "account": "@someone",
                                   "posted_at": "2026-10-20T10:00:00Z", "caption": "look at this </script>"}
    (run / "clips.json").write_text(json.dumps(clips))
    out, page, data = exported(run, tmp_path)
    assert data["state"]["clips"][0]["source"]["account"] == "@someone" and "path" not in data["state"]["clips"][0]
    assert page.count("</script>") == 2  # the caption cannot close the data block
    html = wall.PAGE.read_text()
    assert "postCard" in html and "safeUrl" in html and "noopener" in html


@pytest.fixture
def suggested(tmp_path):
    """The compilation example as the matcher left it: a suggestion, no human decision yet."""
    shutil.copytree(COMPILATION, tmp_path / "sugg")
    (tmp_path / "sugg" / "audit.jsonl").write_text("")
    return tmp_path / "sugg"


def test_a_suggested_compilation_is_listed_with_its_spans_and_joins_nothing_yet(suggested):
    s = wall.state(suggested)
    (sg,) = s["suggestions"]
    assert sg["clip"] == "v_upload" and [(g["clips"], g["start_s"], g["end_s"]) for g in sg["segments"]][0] == (["q_cam"], 0.0, 2.0)
    assert not any(r["status"] == "compilation" for r in s["recordings"]) and s["clip_decisions"] == {}
    assert not any(p["band"] == "partial" for p in s["pairs"])
    assert next(r for r in s["recordings"] if "v_upload" in r["members"])["status"] == "unresolved"


def test_confirming_and_dismissing_a_compilation_are_one_audit_line_each_with_a_null_pair(suggested):
    entry = wall.append_audit(suggested, None, "confirm_compilation", "three sources", clip="v_upload")
    assert entry["pair"] is None and entry["clip"] == "v_upload" and entry["action"] == "confirm_compilation"
    assert json.loads((suggested / "audit.jsonl").read_text().splitlines()[-1]) == entry
    s = wall.state(suggested)
    assert s["suggestions"] == [] and s["clip_decisions"]["v_upload"]["note"] == "three sources"
    comp = next(r for r in s["recordings"] if r["status"] == "compilation")
    assert comp["members"] == ["v_upload"] and {p["id"]: p["band"] for p in s["pairs"]}["p_orig~v_upload"] == "partial"
    wall.append_audit(suggested, None, "dismiss_compilation", clip="v_upload")
    s = wall.state(suggested)
    assert s["suggestions"] == [] and not any(r["status"] == "compilation" for r in s["recordings"])
    assert s["clip_decisions"]["v_upload"]["action"] == "dismiss_compilation"
    assert len((suggested / "audit.jsonl").read_text().splitlines()) == 2


def test_compilation_actions_need_a_clip_of_the_run_and_no_pair(suggested):
    before = (suggested / "audit.jsonl").read_bytes()
    for pair, clip in ((None, "nope"), (None, None), ("p_orig~v_upload", "v_upload")):
        with pytest.raises(ValueError):
            wall.append_audit(suggested, pair, "confirm_compilation", clip=clip)
    with pytest.raises(ValueError):
        wall.append_audit(suggested, None, "split")  # a pair action without a pair
    assert (suggested / "audit.jsonl").read_bytes() == before


def test_the_page_and_the_withdraw_stage_still_agree_after_each_compilation_decision(suggested):
    from indexreel import withdraw
    assert wall.state(suggested)["recordings"] == withdraw.run_recordings(suggested)
    wall.append_audit(suggested, None, "confirm_compilation", clip="v_upload")
    assert wall.state(suggested)["recordings"] == withdraw.run_recordings(suggested)


def test_http_decides_a_compilation_by_clip(suggested):
    srv = wall.make_server(suggested)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        head = {"Content-Type": "application/json"}
        status, body = call(srv, "POST", "/api/decide", json.dumps({"clip": "v_upload", "action": "confirm_compilation"}), head)
        assert status == 200 and json.loads(body)["suggestions"] == []
        assert call(srv, "POST", "/api/decide", json.dumps({"clip": "zzz", "action": "confirm_compilation"}), head)[0] == 400
        assert json.loads((suggested / "audit.jsonl").read_text().splitlines()[-1])["pair"] is None
    finally:
        srv.shutdown()
        srv.server_close()


def test_the_page_has_the_confirm_and_dismiss_buttons_and_the_recorded_export_has_none(suggested, tmp_path):
    page = wall.PAGE.read_text()
    assert "confirm_compilation" in page and "dismiss_compilation" in page and "Possible compilations" in page
    out = tmp_path / "exp"
    wall.export(suggested, out)
    data = json.loads((out / "index.html").read_text().split('id="recorded-data">')[1].split("</script>")[0])
    assert data["state"]["suggestions"][0]["clip"] == "v_upload"


def test_withdraw_view_marks_an_unconfirmed_compilation_as_undecided_with_the_clip_to_decide(suggested, tmp_path):
    (tmp_path / "claims.csv").write_text("clip,claim_id,claim_text\nv_upload,k1,seen in the upload\np_orig,k2,seen at the source\n")
    r1 = next(r["id"] for r in wall.state(suggested)["recordings"] if "p_orig" in r["members"])
    out = wall.withdraw_view(suggested, tmp_path / "claims.csv", r1)
    (k1,) = out["undecided"]
    assert k1["claim_id"] == "k1" and k1["unconfirmed"] == ["v_upload"] and k1["lost_spans"][0]["confirmed"] is False
    assert [(x["start_s"], x["end_s"], x["confirmed"]) for x in k1["possible"]] == [(0.0, 2.0, False), (87.0, 105.0, False)]
    assert [e["claim_id"] for e in out["lost"]] == ["k2"] and out["kept"] == []
    wall.append_audit(suggested, None, "confirm_compilation", clip="v_upload")
    out = wall.withdraw_view(suggested, tmp_path / "claims.csv", r1)
    assert [e["claim_id"] for e in out["kept"]] == ["k1"] and out["undecided"] == [] and out["kept"][0]["lost_spans"][0]["confirmed"] is True


def test_the_page_words_for_possible_compilation_spans_are_there():
    page = wall.PAGE.read_text()
    assert "compilation not yet confirmed" in page and "possible: " in page and "Confirm or dismiss the possible compilation" in page


PARTIAL_COLUMNS = ["pair_id", "a", "b", "score", "aligned", "mirrored", "offset_s", "a_start_s", "a_end_s", "b_start_s", "b_end_s",
                   "band", "evidence", "evidence_a_s", "verify_verdict", "verify_confidence", "verify_reason", "verify_cost_usd",
                   "core_a_start_s", "core_a_end_s", "core_b_start_s", "core_b_end_s",
                   "cover_a", "cover_b", "cover_a_start_s", "cover_a_end_s", "cover_b_start_s", "cover_b_end_s"]


def partial_run(tmp_path, with_covers=True):
    """o is a 20 s recording, p a full copy, x holds o's last 7 s and then 7 s of footage that is not in the run."""
    run = tmp_path / "partial"
    (run / "frames").mkdir(parents=True)
    ids = {"o": 20.0, "p": 20.0, "x": 14.0}
    (run / "clips.json").write_text(json.dumps({"version": 1, "clips": [
        {"id": i, "path": f"{i}.mp4", "duration_s": d, "fps": 25.0, "width": 640, "height": 360, "frames_sampled": int(d),
         "crop": {"method": "none", "quad": None, "fallback_share": 0.0}} for i, d in ids.items()]}))
    (run / "run.json").write_text(json.dumps({"version": 1, "command": "x", "created_utc": "2026-10-29T00:00:00Z", "git_commit": "0",
                                              "n_clips": 3, "sample": "1 frame per second", "thresholds": {"merge_at": 0.55, "floor": 0.2}}))
    (run / "clusters.json").write_text(json.dumps({"version": 1, "thresholds": {"merge_at": 0.55, "floor": 0.2, "score_used": "aligned"}, "recordings": []}))
    (run / "audit.jsonl").write_text("")
    spec = [("o~p", "o", "p", (1, 1), (0, 20), (0, 20)), ("o~x", "o", "x", (0.35, 0.5), (13, 20), (0, 7)),
            ("p~x", "p", "x", (0.35, 0.5), (13, 20), (0, 7))]
    with open(run / "pairs.csv", "w", newline="") as f:
        import csv as _csv
        w = _csv.DictWriter(f, fieldnames=PARTIAL_COLUMNS if with_covers else PARTIAL_COLUMNS[:22], restval="")
        w.writeheader()
        for pid, a, b, cov, sa, sb in spec:
            row = {"pair_id": pid, "a": a, "b": b, "score": 0.8, "aligned": 0.8, "mirrored": 0, "offset_s": 0, "a_start_s": sa[0], "a_end_s": sa[1],
                   "b_start_s": sb[0], "b_end_s": sb[1], "band": "merged"}
            if with_covers:
                row.update(cover_a=cov[0], cover_b=cov[1], cover_a_start_s=sa[0], cover_a_end_s=sa[1], cover_b_start_s=sb[0], cover_b_end_s=sb[1])
            w.writerow(row)
    return run


def test_a_pair_that_shares_only_part_of_both_clips_is_partial_and_joins_nothing(tmp_path):
    from indexreel import withdraw
    run = partial_run(tmp_path)
    s = wall.state(run)
    bands = {p["id"]: p["band"] for p in s["pairs"]}
    assert bands == {"o~p": "merged", "o~x": "partial", "p~x": "partial"}
    assert sorted(sorted(r["members"]) for r in s["recordings"]) == [["o", "p"], ["x"]]
    assert s["recordings"] == withdraw.run_recordings(run)
    pair = {p["id"]: p for p in s["pairs"]}["o~x"]
    assert pair["cover"] == [0.35, 0.5]
    assert {(g["clip"], g["start_s"], g["end_s"]) for g in pair["shared"]} == {("x", 0.0, 7.0), ("o", 13.0, 20.0)}
    x = next(r for r in s["recordings"] if r["members"] == ["x"])
    assert x["status"] == "single" and x["partial"]["x"][0]["links"] == ["o~x", "p~x"]
    assert not any(p["band"] == "unresolved" for p in s["pairs"])  # nothing is waiting on a decision


def test_the_audit_on_a_partial_pair_follows_the_format(tmp_path):
    run = partial_run(tmp_path)
    wall.append_audit(run, "o~x", "approve_merge")  # approving a partial pair keeps it partial
    assert {p["id"]: p["band"] for p in wall.state(run)["pairs"]}["o~x"] == "partial"
    wall.append_audit(run, "o~x", "split")
    wall.append_audit(run, "p~x", "split")
    s = wall.state(run)
    assert {p["id"]: p["band"] for p in s["pairs"]}["o~x"] == "apart" and not any(r.get("partial") for r in s["recordings"])
    wall.append_audit(run, "o~x", "reset")
    wall.append_audit(run, "p~x", "reset")
    assert {p["id"]: p["band"] for p in wall.state(run)["pairs"]}["p~x"] == "partial"


def test_a_run_without_cover_columns_has_no_partial_pairs(tmp_path):
    s = wall.state(partial_run(tmp_path, with_covers=False))
    assert {p["id"]: p["band"] for p in s["pairs"]}["o~x"] == "merged" and all(p["cover"] is None and p["shared"] == [] for p in s["pairs"])
    assert sorted(sorted(r["members"]) for r in s["recordings"]) == [["o", "p", "x"]]


def test_withdraw_view_loses_the_shared_stretch_of_a_clip_that_has_its_own_recording(tmp_path):
    run = partial_run(tmp_path)
    (tmp_path / "claims.csv").write_text("clip,claim_id,claim_text\nx,k1,seen in x\no,k2,seen in o\n")
    r_o = next(r["id"] for r in wall.state(run)["recordings"] if "o" in r["members"])
    out = wall.withdraw_view(run, tmp_path / "claims.csv", r_o)
    assert [e["claim_id"] for e in out["lost"]] == ["k2"] and [e["claim_id"] for e in out["kept"]] == ["k1"]
    assert [(g["clip"], g["start_s"], g["end_s"]) for g in out["kept"][0]["lost_spans"]] == [("x", 0.0, 7.0)]


def test_the_page_has_the_wording_for_shared_footage_and_exports_it(tmp_path):
    page = wall.PAGE.read_text()
    assert "shares footage with" in page and "not counted as a copy" in page and "sharedNote" in page
    run = partial_run(tmp_path)
    wall.export(run, tmp_path / "exp")
    data = json.loads((tmp_path / "exp" / "index.html").read_text().split('id="recorded-data">')[1].split("</script>")[0])
    assert data["state"]["pairs"][1]["shared"] and "path" not in data["state"]["clips"][0]


def test_the_page_words_a_partial_pair_inside_one_recording_as_the_same_recording():
    page = wall.PAGE.read_text()
    assert "shares only part of its footage with" in page and "same recording, joined through other links" in page
    assert "g.recording === recOf(g.clip)" in page and "g.recording === r.id" in page


def test_the_page_names_posts_shows_the_verdict_first_and_counts_compilations_apart():
    page = wall.PAGE.read_text()
    assert "const nm = " in page and "`post ${i + 1}`" in page  # a clip with a source is "post N", not a long id
    assert "Verifier says:" in page and "same event, different footage" in page and 'v.same_event === "yes"' in page and "/^same" not in page
    assert page.index("verdict = `") < page.index("<strong>History</strong>")  # the verdict comes before the history line
    assert "recording${nRec === 1" in page and "compilation${nComp === 1" in page
    assert "function sharedPrefix" in page and "const stretchOf" in page and "comes from:" in page
    assert "overflow-wrap: anywhere" in page.split(".post {")[1].split("}")[0]


def test_compilation_stretches_carry_their_source_clips(suggested):
    s = wall.state(suggested)
    assert all(g["clips"] for g in s["suggestions"][0]["segments"])  # the page names each stretch by these clips, not by recording id


def test_a_confirmed_compilation_is_listed_under_decided_by_hand(suggested):
    page = wall.PAGE.read_text()
    assert "compilation confirmed by hand" in page and "Nothing has been decided by hand yet." in page
    wall.append_audit(suggested, None, "confirm_compilation", "cut from two", clip="v_upload")
    s = wall.state(suggested)
    assert s["clip_decisions"]["v_upload"]["action"] == "confirm_compilation"
    assert any(r["status"] == "compilation" and r["members"] == ["v_upload"] for r in s["recordings"])


def test_the_verifiers_same_event_answer_reaches_the_pair_data(run):
    text = (run / "pairs.csv").read_text().splitlines()
    head = text[0].split(",") + ["verify_same_event"]
    rows = [dict(zip(head, line.split(",") + [""])) for line in text[1:]]
    for r in rows:
        if r["pair_id"] == "b_cam1~b_cam2":
            r.update(verify_verdict="different", verify_same_event="unsure")
    (run / "pairs.csv").write_text("\n".join([",".join(head)] + [",".join(r[c] for c in head) for r in rows]) + "\n")
    p = {x["id"]: x for x in wall.state(run)["pairs"]}
    assert p["b_cam1~b_cam2"]["verify"]["same_event"] == "unsure" and p["b_cam1~b_cam2"]["verify"]["verdict"] == "different"
    assert "same_event" not in p["a_orig~a_refilm"]["verify"]  # an empty value is left out


SHEET = '''clip,claim_id,claim_text,quote,status
a_orig,c1,"Fire in the hills, at night",fire in the hills,suggested
a_copy,c1,"Fire in the hills, at night",the "hills" burn,suggested
a_orig,c2,Filmed in 2018,filmed in 2018,approved
c_alone,c3,A clip with a café sign,café sign,rejected
b_cam1,c4,Something odd,odd,
'''


@pytest.fixture
def sheet(tmp_path):
    f = tmp_path / "claims.csv"
    f.write_text(SHEET)
    return f


def test_a_sheet_with_a_status_column_is_reviewed_and_one_without_counts_every_row(sheet, tmp_path):
    rows, reviewed = wall.read_claim_rows(sheet)
    assert reviewed and [r["status"] for r in rows] == ["suggested", "suggested", "approved", "rejected", "suggested"]  # empty means suggested
    assert rows[1]["quote"] == 'the "hills" burn' and rows[0]["claim_text"] == "Fire in the hills, at night"
    plain = tmp_path / "plain.csv"
    plain.write_text(CLAIMS)
    rows, reviewed = wall.read_claim_rows(plain)
    assert not reviewed and {r["status"] for r in rows} == {"approved"} and all(r["quote"] == "" for r in rows)


def test_withdraw_counts_only_approved_rows_and_says_how_many_are_waiting(run, sheet):
    out = wall.withdraw_view(run, sheet, "r1")
    ids = {e["claim_id"] for k in ("lost", "kept", "undecided") for e in out[k]} | set(out["unaffected"])
    assert ids == {"c2"} and out["pending"] == 3 and out["text"] == {"c2": "Filmed in 2018"}  # c1 and c4 wait, c3 is rejected
    wall.set_claim_status(run, sheet, "a_orig", "c1", "approve_claim")
    wall.set_claim_status(run, sheet, "a_copy", "c1", "approve_claim")
    out = wall.withdraw_view(run, sheet, "r1")
    assert {e["claim_id"] for e in out["lost"]} == {"c1", "c2"} and out["pending"] == 1


def test_approving_rewrites_the_status_and_logs_one_audit_line(run, sheet):
    import csv as _csv
    before = (run / "audit.jsonl").read_text().splitlines()
    entry = wall.set_claim_status(run, sheet, "a_orig", "c1", "approve_claim", "checked the caption")
    rows = list(_csv.DictReader(open(sheet, newline="")))
    assert [(r["clip"], r["claim_id"], r["status"]) for r in rows][:2] == [("a_orig", "c1", "approved"), ("a_copy", "c1", "suggested")]
    assert rows[1]["quote"] == 'the "hills" burn' and rows[3]["claim_text"] == "A clip with a café sign" and list(rows[0]) == ["clip", "claim_id", "claim_text", "quote", "status"]
    lines = (run / "audit.jsonl").read_text().splitlines()
    assert lines[:len(before)] == before and len(lines) == len(before) + 1 and json.loads(lines[-1]) == entry
    assert (entry["action"], entry["pair"], entry["clip"], entry["claim"], entry["note"], entry["actor"]) == ("approve_claim", None, "a_orig", "c1", "checked the caption", "human")
    wall.set_claim_status(run, sheet, "a_orig", "c1", "reject_claim")
    wall.set_claim_status(run, sheet, "a_orig", "c1", "reset_claim")
    assert next(r for r in _csv.DictReader(open(sheet, newline="")) if r["clip"] == "a_orig" and r["claim_id"] == "c1")["status"] == "suggested"
    assert not (sheet.parent / "claims.csv.tmp").exists()


def test_a_bad_claim_decision_changes_nothing(run, sheet, tmp_path):
    before_sheet, before_audit = sheet.read_bytes(), (run / "audit.jsonl").read_bytes()
    for clip, cid, action in (("a_orig", "c9", "approve_claim"), ("nope", "c1", "approve_claim"), ("a_orig", "c1", "delete_claim")):
        with pytest.raises(ValueError):
            wall.set_claim_status(run, sheet, clip, cid, action)
    plain = tmp_path / "plain.csv"
    plain.write_text(CLAIMS)
    with pytest.raises(ValueError):
        wall.set_claim_status(run, plain, "a_orig", "c1", "approve_claim")  # a hand-written sheet has no status to set
    with pytest.raises(ValueError):
        wall.append_audit(run, None, "approve_claim", clip="a_orig")  # no claim id
    assert sheet.read_bytes() == before_sheet and (run / "audit.jsonl").read_bytes() == before_audit


def test_claim_lines_in_the_audit_do_not_change_pairs_recordings_or_compilations(run, sheet):
    from indexreel import withdraw
    base = wall.state(run)
    wall.set_claim_status(run, sheet, "a_orig", "c1", "approve_claim")
    after = wall.state(run, sheet)
    assert after["recordings"] == base["recordings"] == withdraw.run_recordings(run)
    assert [p["band"] for p in after["pairs"]] == [p["band"] for p in base["pairs"]] and after["clip_decisions"] == base["clip_decisions"]


def test_the_claims_sheet_defaults_to_claims_csv_in_the_run_directory(run, sheet, tmp_path):
    assert wall.claims_file(run) is None
    (run / "claims.csv").write_text(SHEET)
    assert wall.claims_file(run) == run / "claims.csv" and wall.claims_file(run, sheet) == sheet
    s = wall.state(run, wall.claims_file(run))
    assert s["claims"] and s["claim_review"] and len(s["claim_rows"]) == 5
    out = tmp_path / "exp"
    wall.export(run, out)  # no --claims given: the sheet in the run directory is used
    data = json.loads((out / "index.html").read_text().split('id="recorded-data">')[1].split("</script>")[0])
    assert len(data["state"]["claim_rows"]) == 5 and set(data["withdraw"]) == {r["id"] for r in data["state"]["recordings"]}
    assert {e["claim_id"] for k in ("lost", "kept") for e in data["withdraw"]["r1"][k]} == {"c2"}  # only the approved row


def test_http_approves_a_claim_and_withdraw_follows(run, sheet):
    srv = wall.make_server(run, claims=sheet)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        head = {"Content-Type": "application/json"}
        body = json.dumps({"action": "approve_claim", "clip": "a_orig", "claim": "c1", "note": "ok"})
        status, out = call(srv, "POST", "/api/decide", body, head)
        assert status == 200 and {(r["clip"], r["claim_id"]): r["status"] for r in json.loads(out)["claim_rows"]}[("a_orig", "c1")] == "approved"
        status, out = call(srv, "GET", "/api/withdraw?recording=r1")
        assert status == 200 and json.loads(out)["pending"] == 2
        assert call(srv, "POST", "/api/decide", json.dumps({"action": "approve_claim", "clip": "a_orig", "claim": "zz"}), head)[0] == 400
        assert call(srv, "POST", "/api/decide", json.dumps({"action": "approve_claim", "clip": "a_orig", "claim": "c1"}), {"Content-Type": "text/plain"})[0] == 415
        assert json.loads((run / "audit.jsonl").read_text().splitlines()[-1])["action"] == "approve_claim"
    finally:
        srv.shutdown()
        srv.server_close()


def test_the_page_marks_the_quote_in_the_caption_and_warns_when_it_is_not_there():
    page = wall.PAGE.read_text()
    assert "Claims to review" in page and "approve_claim" in page and "reject_claim" in page and "reset_claim" in page
    assert "<mark>${esc(quote)}</mark>" in page and "The quote was not found in this post's caption" in page
    assert "not counted until approved" in page and "Only approved claims count in Withdraw" in page


def test_the_page_and_the_terminal_count_the_same_claims(run, sheet, tmp_path):
    from indexreel import withdraw
    plain = tmp_path / "plain.csv"
    plain.write_text(CLAIMS)
    for f in (sheet, plain):
        by_claim, text = withdraw.read_claims(f, log=lambda _: None)
        rows, _ = wall.read_claim_rows(f)
        mine = {}
        for r in rows:
            if r["status"] == "approved":
                mine.setdefault(r["claim_id"], []).append(r["clip"])
        assert mine == by_claim
        out = wall.withdraw_view(run, f, "r1")
        theirs = withdraw.withdraw(withdraw.run_recordings(run), by_claim, "r1", withdraw.run_joins(run))
        assert {k: [e["claim_id"] for e in out[k]] for k in ("lost", "kept", "undecided")} == {k: [e["claim_id"] for e in theirs[k]] for k in ("lost", "kept", "undecided")}
        assert out["unaffected"] == theirs["unaffected"]


TRACE_HEAD = "recording,input,source,query,url,platform,post_id,account,posted_at,fetch,clip,duration_s,cut_start_s,cut_end_s,coarse,band,verify_verdict,evidence,confirmed,earlier,leak_exposed,shown"


def trace_run(run, extra=""):
    """A trace.csv over the fixture run: r1 has an earliest copy (shown) and a later one, r2 found nothing."""
    rows = [
        "r1,a_orig,web,,https://example.org/v/1,youtube,1,acct1,2017-12-07T08:05:07Z,ok,cand1,10,,,,merged,same,trace/r1/pairs/cand1/core.jpg,1,1,1,1",
        "r1,a_orig,youtube,q,https://example.org/v/2,youtube,2,acct2,2018-01-02T00:00:00Z,ok,cand2,10,,,,merged,same,../../etc/passwd,1,0,1,0",
        "r1,a_orig,web,,javascript:alert(1),,,,,error other,,,,,,,,,0,,1,0",
        "r2,b_cam1,web,,https://example.org/v/3,youtube,3,acct3,2019-01-01T00:00:00Z,ok,cand3,10,,,,apart,,,0,1,0,0",
    ]
    (run / "trace.csv").write_text("\n".join([TRACE_HEAD] + rows) + "\n")
    for rec, clip, cap in (("r1", "cand1", "<b>hi</b> " + "x" * 700), ("r1", "cand2", "later copy")):
        (run / "trace" / rec / "clips").mkdir(parents=True, exist_ok=True)
        (run / "trace" / rec / "clips" / f"{clip}.source.json").write_text(json.dumps({"caption": cap}))
    (run / "trace" / "r1" / "pairs" / "cand1").mkdir(parents=True)
    (run / "trace" / "r1" / "pairs" / "cand1" / "core.jpg").write_bytes(b"\xff\xd8jpeg")
    (run / "secret.jpg").write_bytes(b"nope")


def test_trace_is_none_without_a_trace_csv(run):
    assert wall.read_trace(run) is None and wall.state(run)["trace"] is None


def test_trace_reads_copies_captions_and_counts_only_fetched_posts(run):
    trace_run(run)
    t = wall.read_trace(run)
    assert t["r1"]["searched"] == 2 and t["r2"]["searched"] == 1 and t["r1"]["leak"] and not t["r2"]["leak"]
    first, later = t["r1"]["copies"]
    assert first["shown"] and first["earlier"] == "1" and len(first["caption"]) == 600 and first["evidence"] == "trace/r1/pairs/cand1/core.jpg"
    assert not later["shown"] and later["earlier"] == "0" and later["caption"] == "later copy"
    assert later["evidence"] == ""  # a path that leaves trace/ is not an evidence image
    assert t["r2"]["copies"] == []  # a candidate that was not confirmed is not listed


def test_trace_served_over_http_only_from_inside_trace(run):
    trace_run(run)
    srv = wall.make_server(run)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        assert call(srv, "GET", "/trace/r1/pairs/cand1/core.jpg") == (200, b"\xff\xd8jpeg")
        assert call(srv, "GET", "/trace/../secret.jpg")[0] == 404
        assert call(srv, "GET", "/trace/%2e%2e/secret.jpg")[0] == 404
        assert json.loads(call(srv, "GET", "/api/state")[1])["trace"]["r1"]["copies"][0]["shown"]
    finally:
        srv.shutdown()
        srv.server_close()


def test_trace_export_carries_the_section_and_its_images(run, tmp_path):
    trace_run(run)
    out, page, data = exported(run, tmp_path)
    assert (out / "trace/r1/pairs/cand1/core.jpg").read_bytes() == b"\xff\xd8jpeg" and not (out / "secret.jpg").exists()
    assert data["state"]["trace"]["r1"]["copies"][0]["url"] == "https://example.org/v/1"


def test_the_page_words_the_trace_section_without_saying_true_or_new():
    page = wall.PAGE.read_text()
    assert "Earliest confirmed copy found:" in page and "That does not mean the footage is new." in page
    assert "not posted before the claimed date" in page and "found only by a web search that also read fact-checking pages" in page
    assert "also read fact-checking pages" in page and "not when it was filmed" in page
    assert "filmed on" not in page and "original" not in page.split("function traceCard")[1].split("function withdrawBox")[0]


def test_trace_reads_claimed_date_and_leak_copy_when_the_columns_exist(run):
    trace_run(run)
    f = run / "trace.csv"
    head, *rows = f.read_text().splitlines()
    f.write_text("\n".join([head + ",claimed_date,leak_copy"] + [r + (",2018-01-01,1" if r.startswith("r1,a_orig,web,,https") else ",2018-01-01,0" if r.startswith("r1") else ",,0") for r in rows]) + "\n")
    t = wall.read_trace(run)
    assert t["r1"]["claimed"] == "2018-01-01" and t["r2"]["claimed"] == ""
    assert [c["leak_copy"] for c in t["r1"]["copies"]] == [True, False]


def test_the_trace_credit_line_names_the_poster_and_uses_the_inputs_own_credit_key():
    js = wall.PAGE.read_text().split("function traceCard")[1].split("function traceBox")[0]
    assert "input.credit" in js and "Copy posted" in js and "Credit: " in js


def test_trace_corroborated_date_and_strength_never_reach_the_page_data(run):
    trace_run(run)
    f = run / "trace.csv"
    head, *rows = f.read_text().splitlines()
    f.write_text("\n".join([head + ",corroborated_date,corroboration"] + [r + ",2021-11-26,strong" for r in rows]) + "\n")
    assert "2021-11-26" not in json.dumps(wall.state(run)["trace"]) and "strong" not in json.dumps(wall.state(run)["trace"])
    page = wall.PAGE.read_text()
    assert "corroborat" not in page


def test_trace_date_check_notes_and_still_no_corroborated_date(run):
    trace_run(run)
    f = run / "trace.csv"
    head, *rows = f.read_text().splitlines()
    f.write_text("\n".join([head + ",date_check,corroborated_date"] + [r + (",editable,2021-11-26" if i == 0 else ",id_agrees,2021-11-26") for i, r in enumerate(rows)]) + "\n")
    t = wall.read_trace(run)
    assert [c["date_check"] for c in t["r1"]["copies"]] == ["editable", "id_agrees"]
    assert "2021-11-26" not in json.dumps(t)
    js = wall.PAGE.read_text()
    assert "this platform lets the uploader change the date" in js and "the post's own id agrees with this date" in js and "corroborat" not in js


def test_trace_copies_say_whether_the_check_was_automatic(run):
    trace_run(run)
    assert [(c["automatic"], c["geo_detail"]) for c in wall.read_trace(run)["r1"]["copies"]] == [(False, ""), (False, "")]  # an older run
    f = run / "trace.csv"
    head, *rows = f.read_text().splitlines()
    f.write_text("\n".join([head + ",geo,geo_detail,automatic"] + [r + (",same,mirrored; scale 0.9; slope 1.0,1" if i == 0 else ",different,not aligned,0") for i, r in enumerate(rows)]) + "\n")
    copies = wall.read_trace(run)["r1"]["copies"]
    assert [(c["automatic"], c["geo_detail"]) for c in copies] == [(True, "mirrored; scale 0.9; slope 1.0"), (False, "")]
    js = wall.PAGE.read_text().split("function copyLine")[1].split("function traceCard")[0]
    assert "automatic: same footage" in js and "confirmed by matching, check it yourself" in js and "c.automatic" in js


def possible_run(run):
    """trace_run plus a possible_source column: r2's candidate is an unconfirmed lead, with its own image."""
    trace_run(run)
    f = run / "trace.csv"
    head, *rows = f.read_text().splitlines()
    rows[3] = rows[3].replace("cand3,10,,,,apart,,,0,1,0,0", "cand3,10,,,,apart,different,trace/r2/pairs/cand3/core.jpg,0,1,0,0")
    f.write_text("\n".join([head + ",possible_source"] + [r + (",1" if r.startswith("r2,") else ",") for r in rows]) + "\n")
    (run / "trace" / "r2" / "pairs" / "cand3").mkdir(parents=True)
    (run / "trace" / "r2" / "pairs" / "cand3" / "core.jpg").write_bytes(b"\xff\xd8lead")


def test_trace_possible_sources_are_kept_apart_from_confirmed_copies_and_carry_no_date(run):
    possible_run(run)
    t = wall.read_trace(run)
    assert t["r2"]["copies"] == [] and [p["url"] for p in t["r2"]["possible"]] == ["https://example.org/v/3"]
    p = t["r2"]["possible"][0]
    assert p["evidence"] == "trace/r2/pairs/cand3/core.jpg" and "posted_at" not in p and "earlier" not in p and "shown" not in p
    assert "2019-01-01" not in json.dumps(t["r2"]["possible"])
    assert t["r1"]["possible"] == [] and all(not c["shown"] or c["clip"] == "cand1" for c in t["r1"]["copies"])


def test_trace_without_a_possible_source_column_has_no_leads(run):
    trace_run(run)
    assert wall.read_trace(run)["r2"]["possible"] == []


def test_trace_possible_source_images_reach_the_export_and_the_page_words_them_as_a_lead(run, tmp_path):
    possible_run(run)
    out, page, data = exported(run, tmp_path)
    assert (out / "trace/r2/pairs/cand3/core.jpg").read_bytes() == b"\xff\xd8lead"
    js = wall.PAGE.read_text().split("function traceCard")[1].split("function traceBox")[0]
    assert "Possible earlier source: check it yourself" in js and "\"confirmed earlier copy\"" in js
    assert "p.posted_at" not in js and "corroborat" not in js


def sync_dir(tmp_path, **over):
    """A result.json as the matcher writes it for two cameras, with its three frame-pair images."""
    d = tmp_path / "park_sync"
    d.mkdir()
    res = {"version": 1, "a": "park_a", "b": "park_b", "lag_s": 24.0, "peak": 0.91, "sidelobe_ratio": 7.5,
           "clap_lag_s": 23.99, "metadata_lag_s": 24.0, "rule_passed": True, "bar": 8,
           "pairs": [{"a_s": 10.0 * i, "b_s": 10.0 * i + 24.0, "image": f"pair{i}.jpg"} for i in (1, 2, 3)]} | over
    for p in res["pairs"] if isinstance(res["pairs"], list) else []:
        if isinstance(p, dict) and isinstance(p.get("image"), str) and "/" not in p["image"] and p["image"] != "missing.jpg":
            (d / p["image"]).write_bytes(b"\xff\xd8" + p["image"].encode())
    (d / "result.json").write_text(json.dumps(res))
    return d / "result.json"


def test_sync_reads_the_matchers_result(tmp_path):
    s = wall.read_sync(sync_dir(tmp_path))
    assert (s["a"], s["b"], s["lag_s"], s["clap_lag_s"], s["metadata_lag_s"]) == ("park_a", "park_b", 24.0, 23.99, 24.0)
    assert [p["image"] for p in s["pairs"]] == ["pair1.jpg", "pair2.jpg", "pair3.jpg"] and s["peak"] == 0.91 and s["sidelobe_ratio"] == 7.5


def test_sync_clap_and_clock_may_be_missing(tmp_path):
    s = wall.read_sync(sync_dir(tmp_path, clap_lag_s=None, metadata_lag_s=None))
    assert s["clap_lag_s"] is None and s["metadata_lag_s"] is None


@pytest.mark.parametrize("over", [
    {"lag_s": "24"}, {"lag_s": True}, {"peak": None}, {"a": ""}, {"pairs": []}, {"version": 2},
    {"pairs": [{"a_s": 1, "b_s": 2, "image": "../x.jpg"}] * 3}, {"pairs": [{"a_s": 1, "b_s": 2, "image": "x.png"}] * 3},
    {"pairs": [{"a_s": 1, "b_s": 2, "image": "missing.jpg"}] * 3}, {"clap_lag_s": "23.99"},
    {"rule_passed": "yes"}, {"bar": "8"}])
def test_sync_refuses_a_result_it_cannot_trust(tmp_path, over):
    with pytest.raises(ValueError):
        wall.read_sync(sync_dir(tmp_path, **over))


def test_sync_reaches_the_live_state_and_the_images_are_served_only_from_its_folder(run, tmp_path):
    f = sync_dir(tmp_path)
    (tmp_path / "secret.jpg").write_bytes(b"nope")
    assert wall.state(run)["sync"] is None and wall.state(run, sync=f)["sync"]["lag_s"] == 24.0
    srv = wall.make_server(run, sync=f)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        assert json.loads(call(srv, "GET", "/api/state")[1])["sync"]["pairs"][0]["image"] == "pair1.jpg"
        assert call(srv, "GET", "/sync/pair1.jpg") == (200, b"\xff\xd8pair1.jpg")
        assert call(srv, "GET", "/sync/result.json")[0] == 404 and call(srv, "GET", "/sync/../secret.jpg")[0] == 404
        assert call(srv, "GET", "/sync/%2e%2e/secret.jpg")[0] == 404
    finally:
        srv.shutdown()
        srv.server_close()


def test_sync_is_never_served_without_the_flag(run, tmp_path):
    sync_dir(tmp_path)
    srv = wall.make_server(run)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        assert call(srv, "GET", "/sync/pair1.jpg")[0] == 404 and json.loads(call(srv, "GET", "/api/state")[1])["sync"] is None
    finally:
        srv.shutdown()
        srv.server_close()


def test_sync_is_private_so_an_export_refuses_it_and_carries_none(run, tmp_path):
    f = sync_dir(tmp_path)
    out, page, data = exported(run, tmp_path)
    assert data["state"]["sync"] is None and not (out / "sync").exists() and "pair1.jpg" not in page
    with pytest.raises(SystemExit):
        wall.main([str(run), "--export", str(tmp_path / "x"), "--sync", str(f)])


def test_the_page_words_the_same_moment_box_as_exploratory_and_never_says_verified():
    page = wall.PAGE.read_text()
    box = page.split("function syncBox")[1].split("function withdrawBox")[0]
    assert "Same moment" in page and "exploratory" in box.lower()
    assert "sound lines up" in box and "Two cameras recorded the same moment" in box
    assert "signed(" not in box and "s.lag_s < 0" in box and '"after"' in box and '"before"' in box and "started together" in box
    assert "Checked against" in box and "a clap filmed by both" in box and "the files' clocks" in box
    assert "verified" not in box.lower() and "true" not in box.lower().replace("true;", "")


def test_sync_keeps_the_rule_verdict_and_a_missing_one_is_not_a_pass(tmp_path):
    s = wall.read_sync(sync_dir(tmp_path, rule_passed=False))
    assert s["rule_passed"] is False and s["bar"] == 8
    (tmp_path / "other").mkdir()
    s = wall.read_sync(sync_dir(tmp_path / "other", rule_passed=None, bar=None))
    assert s["rule_passed"] is None and s["bar"] is None


def test_the_page_does_not_claim_the_same_moment_unless_the_rule_passed():
    box = wall.PAGE.read_text().split("function syncBox")[1].split("function withdrawBox")[0]
    assert "s.rule_passed === true" in box
    assert "Not enough shared sound to say these two recordings caught the same moment." in box
    assert "where the clap filmed by both puts it" in box and "too weak to claim" in box and "Frames at the strongest sound match" in box
    assert "No verdict from the sound rule" in box
    claim = box.index("Two cameras recorded the same moment")
    assert box.index("s.rule_passed === true") < claim  # the claim sits inside the passed branch
    assert "same place, not a shared event" in box


def test_the_pair_card_does_not_state_a_mirror_the_image_label_is_the_only_place():
    page = wall.PAGE.read_text()  # the pairs.csv flag is SSCD's and can disagree with the pixels; the image says it
    assert "one clip mirrored" not in page and "${mirrored}" not in page
