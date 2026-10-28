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
