"""Clip wall: a local page that shows a run directory (eval/run-format.md) and records human decisions in its audit.jsonl."""
import argparse
import csv
import json
import mimetypes
import os
import re
import shutil
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from indexreel import cluster, withdraw
from indexreel.wall.runs import Runs

ACTIONS = {"approve_merge", "split", "reset"}
PAGE = Path(__file__).with_name("index.html")
RESULTS = Path(__file__).resolve().parents[3] / "eval" / "results.json"  # frozen bars and measurements, shown read-only
RUN_PATH = re.compile(r"/r/([0-9a-f]{12})(/.*)?")
NEW_PAGE = Path(__file__).with_name("new.html")
_audit_lock = threading.Lock()


def wilson(k, n, z=1.96):
    """95% Wilson score interval for k of n."""
    p, d = k / n, 1 + z * z / n
    c, h = (p + z * z / (2 * n)) / d, z * (p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5 / d
    return max(0.0, c - h), min(1.0, c + h)


def read_results(path):
    """Rows of eval/results.json with their status and interval worked out, so a bar and a count cannot disagree."""
    rows = json.loads(Path(path).read_text())["rows"]
    for r in rows:
        k, n = r.get("k"), r.get("n")
        if k is None:
            r["status"] = r.get("status", "NOT RUN")
        elif r.get("bar_op"):
            r["status"] = "PASS" if (k >= r["bar_k"] if r["bar_op"] == ">=" else k <= r["bar_k"]) else "FAIL"
        else:
            r["status"] = r.get("status", "REPORTED")
        r["ci"] = [round(x, 4) for x in wilson(k, n)] if k is not None and n else None
    return rows


def read_pairs(run):
    with open(Path(run) / "pairs.csv", newline="") as f:
        return list(csv.DictReader(f))


def read_audit(run):
    p = Path(run) / "audit.jsonl"
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()] if p.exists() else []


def append_audit(run, pair, action, note=""):
    """Append one human decision to audit.jsonl and return it. The file is never rewritten."""
    run = Path(run)
    if pair not in {r["pair_id"] for r in read_pairs(run)}:
        raise ValueError(f"unknown pair: {pair!r}")
    if action not in ACTIONS:
        raise ValueError(f"unknown action: {action!r}")
    entry = {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "actor": "human", "action": action,
             "pair": pair, "note": str(note)[:500]}
    path = run / "audit.jsonl"
    with _audit_lock:
        # a file that ends without a newline would otherwise glue the new entry to its last line
        lead = "\n" if path.exists() and path.stat().st_size and not path.read_bytes().endswith(b"\n") else ""
        with open(path, "a") as f:
            f.write(lead + json.dumps(entry) + "\n")
            f.flush()
            os.fsync(f.fileno())
    return entry


def withdraw_view(run, claims, recording):
    """Claims that lose, keep or may keep video support when `recording` is withdrawn (rules in indexreel.withdraw)."""
    if claims is None:
        raise ValueError("no claims file: start the wall with --claims")
    by_claim, text = withdraw.read_claims(claims)
    out = withdraw.withdraw(withdraw.run_recordings(run), by_claim, recording)
    return out | {"text": text}


def export(run, out, claims=None, results=None):
    """Write a read-only copy of the page to `out`: index.html with the run embedded, plus the evidence images.

    Nothing here needs a server. Clip paths and the matching command are left out, and the clips themselves are not copied.
    """
    run, out = Path(run).resolve(), Path(out)
    if out.exists() and any(out.iterdir()):
        raise ValueError(f"{out} is not empty")
    s = state(run, claims, results)
    s["run"] = {k: s["run"][k] for k in ("n_clips", "sample", "created_utc", "thresholds", "localiser") if k in s["run"]}
    s["clips"] = [{k: v for k, v in c.items() if k != "path"} for c in s["clips"]]
    views = {r["id"]: withdraw_view(run, claims, r["id"]) for r in s["recordings"]} if claims else {}
    frames = (run / "frames").resolve()
    for p in s["pairs"]:
        if p["evidence"]:
            src = (run / p["evidence"]).resolve()
            if not (src.is_file() and src.is_relative_to(frames)):
                raise ValueError(f"evidence image of {p['id']} is not a file under frames/: {p['evidence']}")
            (out / p["evidence"]).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, out / p["evidence"])
    data = json.dumps({"state": s, "withdraw": views}).replace("</", "<\\/")  # "<\/" is still valid JSON, and cannot close the script tag
    page = PAGE.read_text().replace('content="live"', 'content="recorded"')
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(page.replace("<!--DATA-->", f'<script type="application/json" id="recorded-data">{data}</script>'))
    return out / "index.html"


def state(run, claims=None, results=None):
    """Everything the page draws: pairs with their computed and current band, and recordings with human decisions applied."""
    run = Path(run)
    clips = json.loads((run / "clips.json").read_text())["clips"]
    th = json.loads((run / "clusters.json").read_text())["thresholds"]
    meta = json.loads((run / "run.json").read_text())
    rows, audit = read_pairs(run), read_audit(run)
    computed = {r["pair_id"]: cluster.effective_band(r) for r in rows}  # the matcher's band with the verifier's answer
    current = cluster.apply_audit(computed, audit)
    recs = withdraw.run_recordings(run, audit)  # cluster.resolve: the one recompute path, so ids match the withdraw panel
    compilations = {r["members"][0] for r in recs if r["status"] == "compilation"}
    by_hand = {}
    for e in audit:  # the last entry for a pair counts; reset hands the pair back to the matcher
        if e["pair"] in computed:
            by_hand[e["pair"]] = e if e["action"] != "reset" else None
    pairs = []
    for r in rows:
        offset = float(r["offset_s"])
        core = [[float(r[a]), float(r[b])] for a, b in (("core_a_start_s", "core_a_end_s"), ("core_b_start_s", "core_b_end_s"))
                if r.get(a) and r.get(b)]  # where the two clips really match; absent in older runs
        times = [float(t) for t in r["evidence_a_s"].split(";")] if r["evidence_a_s"] else []
        pairs.append({
            "id": r["pair_id"], "a": r["a"], "b": r["b"], "score": float(r["score"]), "aligned": float(r["aligned"]),
            "mirrored": r["mirrored"] == "1", "offset_s": offset,
            "a_span": [float(r["a_start_s"]), float(r["a_end_s"])], "b_span": [float(r["b_start_s"]), float(r["b_end_s"])],
            "matcher": r["band"], "computed": computed[r["pair_id"]],
            "band": "partial" if current[r["pair_id"]] != "apart" and {r["a"], r["b"]} & compilations else current[r["pair_id"]],
            "core": core if len(core) == 2 else None, "decision": by_hand.get(r["pair_id"]),
            "evidence": r["evidence"], "evidence_times": [[t, round(t + offset, 3)] for t in times],
            "verify": {k[7:]: r[k] for k in r if k.startswith("verify_") and r[k]}})
    return {"run": meta, "claims": claims is not None, "results": read_results(results) if results else None, "thresholds": th, "clips": clips, "pairs": pairs, "recordings": recs, "audit": audit}


class Handler(BaseHTTPRequestHandler):
    """Serves the page, the run state, the evidence frames and the POSTs that append a decision. Local use only.

    With a workdir (server.runs) it also serves a new-run page and every run under /r/<id>/."""

    def reply(self, code, body, ctype="application/json", headers=()):
        if not isinstance(body, bytes):
            body = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in headers:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def host_ok(self):
        # refuse other Host names (DNS rebinding) and other origins: the page is for this machine only
        local = ("127.0.0.1", "localhost")
        origin = self.headers.get("Origin")
        if self.headers.get("Host", "").rsplit(":", 1)[0] in local and (origin is None or urlsplit(origin).hostname in local):
            return True
        self.reply(403, {"error": "forbidden host"})
        return False

    def route(self, path):
        """(run dir, path inside it); run dir is None when the request is not for a run."""
        if self.server.runs is None:
            return self.server.run, path
        m = RUN_PATH.fullmatch(path)
        return (self.server.runs.run_dir(m.group(1)), m.group(2) or "/") if m else (None, path)

    def do_GET(self):
        if not self.host_ok():
            return
        path, runs = unquote(urlsplit(self.path).path), self.server.runs
        if runs is not None:
            if path == "/":
                return self.reply(200, NEW_PAGE.read_bytes(), "text/html; charset=utf-8")
            if path == "/api/runs":
                return self.reply(200, {"runs": runs.listing(), "verify_available": "MODEL_API_KEY" in os.environ})
            if m := re.fullmatch(r"/api/runs/([0-9a-f]{12})", path):
                job = runs.job(m.group(1))
                return self.reply(200 if job else 404, job or {"error": "no such run"})
            if m := re.fullmatch(r"/r/([0-9a-f]{12})", path):  # the page's links are relative, so it needs the trailing slash
                return self.reply(301, b"", "text/plain", [("Location", path + "/")])
        run, path = self.route(path)
        if run is None:
            return self.reply(404, {"error": "not found"})
        if path == "/":
            return self.reply(200, PAGE.read_bytes(), "text/html; charset=utf-8")
        if path == "/api/state":
            return self.reply(200, state(run, self.server.claims, self.server.results))
        if path == "/api/withdraw":
            try:
                return self.reply(200, withdraw_view(run, self.server.claims, parse_qs(urlsplit(self.path).query).get("recording", [""])[0]))
            except (ValueError, KeyError, OSError) as e:
                return self.reply(400, {"error": str(e)})
        if path.startswith("/frames/"):
            f, root = (run / path[1:]).resolve(), (run / "frames").resolve()
            if f.is_file() and f.is_relative_to(root):
                return self.reply(200, f.read_bytes(), mimetypes.guess_type(f.name)[0] or "application/octet-stream")
        self.reply(404, {"error": "not found"})

    def json_body(self):
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            raise TypeError("send application/json")  # a cross-site form cannot send this
        length = int(self.headers.get("Content-Length", 0))
        if length > 1 << 20:
            raise ValueError("body too large")
        return json.loads(self.rfile.read(length) or b"{}")

    def do_POST(self):
        if not self.host_ok():
            return
        path, runs = unquote(urlsplit(self.path).path), self.server.runs
        try:
            if runs is not None and path == "/api/runs":
                self.json_body()
                return self.reply(200, {"id": runs.new()})
            if runs is not None and (m := re.fullmatch(r"/api/runs/([0-9a-f]{12})/(files|start)", path)):
                rid = m.group(1)
                if m.group(2) == "files":
                    if self.headers.get("Content-Type", "") != "application/octet-stream":
                        raise TypeError("send application/octet-stream")
                    name = runs.save(rid, unquote(self.headers.get("X-Filename", "")), self.rfile, int(self.headers.get("Content-Length", 0)))
                    return self.reply(200, {"saved": name})
                body = self.json_body()
                runs.start(rid, body.get("urls", []), float(body.get("max_usd", 1.0)))
                return self.reply(200, runs.job(rid))
            run, path = self.route(path)
            if run is None or path != "/api/decide":
                return self.reply(404, {"error": "not found"})
            body = self.json_body()
            append_audit(run, body["pair"], body["action"], body.get("note", ""))
        except TypeError as e:
            return self.reply(415, {"error": str(e)})
        except RuntimeError as e:
            return self.reply(409, {"error": str(e)})
        except (ValueError, KeyError, OSError, AttributeError) as e:
            return self.reply(400, {"error": str(e)})
        self.reply(200, state(run, self.server.claims, self.server.results))


def make_server(run=None, port=0, claims=None, results=None, workdir=None, steps=None):
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.run = Path(run).resolve() if run else None
    server.runs = Runs(workdir, **({"steps": steps} if steps else {})) if workdir else None  # new-run mode: runs live under /r/<id>/
    server.results = Path(results).resolve() if results else None
    server.claims = Path(claims).resolve() if claims else None  # claims sheet for the withdraw panel, read on each request
    return server


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m indexreel.wall", description="Open a run directory in a local browser page.")
    ap.add_argument("run", type=Path, nargs="?", help="run directory written by `indexreel match`")
    ap.add_argument("--workdir", type=Path, help="serve a new-run page and keep its runs in this folder, instead of opening one run")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--results", type=Path, default=RESULTS if RESULTS.is_file() else None, help="results JSON shown in the Results section (default: eval/results.json)")
    ap.add_argument("--export", type=Path, metavar="DIR", help="write a read-only static copy to DIR instead of serving")
    ap.add_argument("--claims", type=Path, help="claims sheet (clip, claim_id, claim_text) for the withdraw panel")
    args = ap.parse_args(argv)
    if bool(args.run) == bool(args.workdir):
        ap.error("give a run directory or --workdir, not both and not neither")
    if args.export and not args.run:
        ap.error("--export needs a run directory")
    for name in ("clips.json", "pairs.csv", "clusters.json", "run.json") if args.run else ():
        if not (args.run / name).is_file():
            ap.error(f"{args.run} has no {name}")
    if args.results and not args.results.is_file():
        ap.error(f"no results file {args.results}")
    if args.claims and not args.claims.is_file():
        ap.error(f"no claims file {args.claims}")
    if args.export:
        try:
            print(f"wrote {export(args.run, args.export, args.claims, args.results)}")
        except ValueError as e:
            ap.error(str(e))
        return
    server = make_server(args.run, args.port, args.claims, args.results, args.workdir)
    print(f"http://127.0.0.1:{server.server_address[1]}/  (Ctrl-C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
