import http.client
import io
import json
import re
import sys
import threading
import time
from pathlib import Path

import pytest

from indexreel import wall
from indexreel.wall import runs

FIXTURE = Path(__file__).parent / "fixtures" / "run_fake"
PY = [sys.executable, "-c"]


def fake_steps(clips, run, urls, max_usd, fetch="", match=None, verify="print('verify: done')"):
    """Stand-ins for the three commands: the same shape as default_steps, nothing leaves this machine."""
    make = f"import pathlib;[pathlib.Path(r'{clips}', n).write_bytes(b'x') for n in ('twitter_1.mp4', 'twitter_2.mp4')];print('fetch: ok u -> twitter_1.mp4');" + fetch
    copy = match or f"import shutil;shutil.copytree(r'{FIXTURE}', r'{run}');print('match: 6 clips')"
    return [("fetch", PY + [make] if urls else None, "no post links given"), ("match", PY + [copy], ""), ("verify", PY + [verify], "")]


def wait(rs, rid, timeout=20):
    end = time.time() + timeout
    while time.time() < end:
        job = rs.job(rid)
        if job and job["state"] != "running":
            return job
        time.sleep(0.05)
    raise AssertionError("the run did not finish")


def test_only_https_post_links_on_x_are_accepted():
    for ok in ("https://x.com/a/status/1", " https://twitter.com/a/status/22?s=20 ", "https://mobile.x.com/a/status/3"):
        assert runs.clean_url(ok) == ok.strip()
    for bad in ("http://x.com/a/status/1", "https://x.com/a", "https://evil.example/a/status/1", "https://u:p@x.com/a/status/1",
                "https://x.com:8443/a/status/1", "https://x.com/a/status/1 https://x.com/b/status/2", "file:///etc/passwd",
                "--output=/tmp/x", "", "https://x.com.evil.example/a/status/1"):
        with pytest.raises(ValueError):
            runs.clean_url(bad)


def test_uploaded_names_become_plain_video_names():
    assert runs.safe_name("../../etc/Clip One!.MP4") == "Clip_One.mp4"
    assert runs.safe_name("a~b.mov") == "a_b.mov" and runs.safe_name("..x.mp4") == "x.mp4"
    for bad in ("notes.txt", "x.mp4.exe", "", "dir/", "....mp4"):
        with pytest.raises(ValueError):
            runs.safe_name(bad)


def test_uploads_are_stored_under_unused_names_and_only_before_the_start(tmp_path):
    rs = runs.Runs(tmp_path)
    rid = rs.new()
    assert rs.save(rid, "a.mp4", io.BytesIO(b"123"), 3) == "a.mp4"
    assert rs.save(rid, "a.mp4", io.BytesIO(b"456"), 3) == "a-2.mp4"
    assert (tmp_path / rid / "clips" / "a.mp4").read_bytes() == b"123"
    for length in (0, runs.MAX_UPLOAD + 1):
        with pytest.raises(ValueError):
            rs.save(rid, "b.mp4", io.BytesIO(b"x"), length)
    with pytest.raises(ValueError):
        rs.save(rid, "c.mp4", io.BytesIO(b"12"), 5)  # the stream ends early
    assert not (tmp_path / rid / "clips" / "c.mp4").exists()
    with pytest.raises(ValueError):
        rs.save("0" * 12, "a.mp4", io.BytesIO(b"1"), 1)
    rs2 = runs.Runs(tmp_path, steps=fake_steps)
    rid2 = rs2.new()
    rs2.start(rid2, ["https://x.com/a/status/1"], 1.0)
    wait(rs2, rid2)
    with pytest.raises(ValueError):
        rs2.save(rid2, "late.mp4", io.BytesIO(b"1"), 1)


def test_default_steps_use_argument_lists_and_never_carry_the_key(monkeypatch, tmp_path):
    monkeypatch.setenv("MODEL_API_KEY", "sk-test-123456")
    steps = runs.default_steps(tmp_path / "clips", tmp_path / "run", ["https://x.com/a/status/1"], 2.0)
    assert [n for n, _, _ in steps] == ["fetch", "match", "verify"]
    assert all(isinstance(a, list) and all(isinstance(x, str) for x in a) for _, a, _ in steps)
    assert steps[0][1][-3:] == ["--", "https://x.com/a/status/1"][-3:] or steps[0][1][-2:] == ["--", "https://x.com/a/status/1"]
    assert steps[2][1][-2:] == ["--max-usd", "2"] and "sk-test-123456" not in json.dumps(steps)
    monkeypatch.delenv("MODEL_API_KEY")
    steps = runs.default_steps(tmp_path / "clips", tmp_path / "run", [], 2.0)
    assert steps[0][1] is None and steps[2][1] is None and "MODEL_API_KEY" in steps[2][2]
    src = Path(runs.__file__).read_text()
    assert "getenv" not in src and 'environ.get("MODEL_API_KEY' not in src and 'environ["MODEL_API_KEY' not in src


def test_a_run_goes_through_the_three_steps_and_leaves_a_readable_run_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "sk-test-123456")
    rs = runs.Runs(tmp_path, steps=fake_steps)
    rid = rs.new()
    rs.start(rid, ["https://x.com/a/status/1"], 1.0)
    job = wait(rs, rid)
    assert job["state"] == "done" and [s["status"] for s in job["steps"]] == ["ok", "ok", "ok"]
    assert job["steps"][0]["lines"] == ["fetch: ok u -> twitter_1.mp4"] and "sk-test-123456" not in json.dumps(job)
    assert len(wall.state(rs.run_dir(rid))["pairs"]) == 15 and [r["id"] for r in rs.listing()] == [rid]


def test_a_run_without_links_uses_uploads_and_skips_fetch(tmp_path):
    rs = runs.Runs(tmp_path, steps=lambda c, r, u, m: fake_steps(c, r, u, m))
    rid = rs.new()
    for n in ("a.mp4", "b.mp4"):
        rs.save(rid, n, io.BytesIO(b"x"), 1)
    rs.start(rid, [], 0.0)
    job = wait(rs, rid)
    assert job["state"] == "done" and [s["status"] for s in job["steps"]] == ["skipped", "ok", "ok"]
    assert job["steps"][0]["lines"] == ["no post links given"]


def test_fewer_than_two_clips_stops_before_the_matcher(tmp_path):
    rs = runs.Runs(tmp_path, steps=fake_steps)
    rid = rs.new()
    rs.save(rid, "only.mp4", io.BytesIO(b"x"), 1)
    rs.start(rid, [], 1.0)
    job = wait(rs, rid)
    assert job["state"] == "failed" and job["error"] == "need at least two clips"
    assert [s["status"] for s in job["steps"]] == ["skipped", "failed", "pending"]


def test_a_failing_step_stops_the_run_and_a_partial_fetch_goes_on(tmp_path):
    bad = lambda c, r, u, m: fake_steps(c, r, u, m, match="import sys;print('match: boom');sys.exit(3)")
    rs = runs.Runs(tmp_path, steps=bad)
    rid = rs.new()
    rs.start(rid, ["https://x.com/a/status/1"], 1.0)
    job = wait(rs, rid)
    assert job["state"] == "failed" and job["error"] == "match exited with code 3"
    assert [s["status"] for s in job["steps"]] == ["ok", "failed", "pending"] and "match: boom" in job["steps"][1]["lines"]
    part = lambda c, r, u, m: fake_steps(c, r, u, m, fetch="import sys;sys.exit(1)")
    rs = runs.Runs(tmp_path / "p", steps=part)
    rid = rs.new()
    rs.start(rid, ["https://x.com/a/status/1"], 1.0)
    job = wait(rs, rid)
    assert job["state"] == "done" and job["steps"][0]["status"] == "partial"


def test_one_run_at_a_time_and_inputs_are_checked_before_anything_starts(tmp_path):
    slow = lambda c, r, u, m: fake_steps(c, r, u, m, fetch="import time;time.sleep(1.5)")
    rs = runs.Runs(tmp_path, steps=slow)
    a, b = rs.new(), rs.new()
    rs.start(a, ["https://x.com/a/status/1"], 1.0)
    with pytest.raises(RuntimeError):
        rs.start(b, ["https://x.com/a/status/2"], 1.0)
    with pytest.raises(ValueError):
        rs.start(b, ["https://evil.example/a/status/2"], 1.0)
    with pytest.raises(ValueError):
        rs.start(b, [f"https://x.com/a/status/{i}" for i in range(21)], 1.0)
    for cap in (-1, 11):
        with pytest.raises(ValueError):
            rs.start(b, [], cap)
    wait(rs, a)


@pytest.fixture
def server(tmp_path):
    srv = wall.make_server(workdir=tmp_path, steps=fake_steps)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv
    srv.shutdown()
    srv.server_close()


def call(srv, method, path, body=None, headers=None):
    c = http.client.HTTPConnection("127.0.0.1", srv.server_address[1])
    c.request(method, path, body=body, headers=headers or {})
    r = c.getresponse()
    return r.status, r.read(), dict(r.getheaders())


JSON = {"Content-Type": "application/json"}


def test_http_new_run_end_to_end_and_the_run_opens_under_its_own_path(server):
    status, body, _ = call(server, "GET", "/")
    assert status == 200 and b"New run" in body.replace(b"new run", b"New run") and b"does not say whether anything is true or false" in body
    assert json.loads(call(server, "GET", "/api/runs")[1])["runs"] == []
    rid = json.loads(call(server, "POST", "/api/runs", "{}", JSON)[1])["id"]
    status, body, _ = call(server, "POST", f"/api/runs/{rid}/files", b"video bytes", {"Content-Type": "application/octet-stream", "X-Filename": "my%20clip.mp4"})
    assert status == 200 and json.loads(body)["saved"] == "my_clip.mp4"
    status, _, _ = call(server, "POST", f"/api/runs/{rid}/start", json.dumps({"urls": ["https://x.com/a/status/1"], "max_usd": 1}), JSON)
    assert status == 200
    deadline = time.time() + 20
    while time.time() < deadline:
        job = json.loads(call(server, "GET", f"/api/runs/{rid}")[1])
        if job["state"] != "running":
            break
        time.sleep(0.05)
    assert job["state"] == "done"
    status, _, headers = call(server, "GET", f"/r/{rid}")
    assert status == 301 and headers["Location"] == f"/r/{rid}/"
    assert b"IndexReel clip wall" in call(server, "GET", f"/r/{rid}/")[1]
    assert len(json.loads(call(server, "GET", f"/r/{rid}/api/state")[1])["pairs"]) == 15
    assert call(server, "GET", f"/r/{rid}/frames/a_orig~a_refilm.jpg")[1][:2] == b"\xff\xd8"
    status, body, _ = call(server, "POST", f"/r/{rid}/api/decide", json.dumps({"pair": "b_cam1~b_cam2", "action": "split"}), JSON)
    assert status == 200 and json.loads(body)["audit"][-1]["action"] == "split"
    assert len((server.runs.workdir / rid / "run" / "audit.jsonl").read_text().splitlines()) == 2


def test_http_refuses_what_a_local_page_should_not_do(server):
    rid = json.loads(call(server, "POST", "/api/runs", "{}", JSON)[1])["id"]
    assert call(server, "GET", "/api/state")[0] == 404 and call(server, "GET", "/r/not-an-id/")[0] == 404
    assert call(server, "GET", f"/r/{rid}/")[0] == 404  # no run directory yet
    assert call(server, "GET", f"/r/{'0' * 12}/api/state")[0] == 404
    assert call(server, "POST", "/api/runs", "{}", {"Content-Type": "text/plain"})[0] == 415
    assert call(server, "POST", f"/api/runs/{rid}/files", b"x", {"Content-Type": "application/json", "X-Filename": "a.mp4"})[0] == 415
    assert call(server, "POST", f"/api/runs/{rid}/files", b"x", {"Content-Type": "application/octet-stream", "X-Filename": "a.txt"})[0] == 400
    assert call(server, "POST", f"/api/runs/{rid}/start", json.dumps({"urls": ["http://x.com/a/status/1"]}), JSON)[0] == 400
    assert call(server, "POST", f"/api/runs/{rid}/start", "{not json", JSON)[0] == 400
    assert call(server, "POST", "/api/runs", "{}", {**JSON, "Host": "evil.example"})[0] == 403
    assert call(server, "POST", "/api/runs", "{}", {**JSON, "Origin": "https://evil.example"})[0] == 403
    assert call(server, "GET", "/api/runs", headers={"Origin": "http://127.0.0.1:1"})[0] == 200
    assert not (server.runs.workdir / rid / "run").exists()


def test_http_a_second_start_while_one_runs_is_refused(tmp_path):
    srv = wall.make_server(workdir=tmp_path, steps=lambda c, r, u, m: fake_steps(c, r, u, m, fetch="import time;time.sleep(1.5)"))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        a = json.loads(call(srv, "POST", "/api/runs", "{}", JSON)[1])["id"]
        b = json.loads(call(srv, "POST", "/api/runs", "{}", JSON)[1])["id"]
        body = json.dumps({"urls": ["https://x.com/a/status/1"]})
        assert call(srv, "POST", f"/api/runs/{a}/start", body, JSON)[0] == 200
        assert call(srv, "POST", f"/api/runs/{b}/start", body, JSON)[0] == 409
        wait(srv.runs, a)
    finally:
        srv.shutdown()
        srv.server_close()
