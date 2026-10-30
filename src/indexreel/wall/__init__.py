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
CLIP_ACTIONS = {"confirm_compilation", "dismiss_compilation"}  # about a clip, so the pair is null
CLAIM_ACTIONS = {"approve_claim": "approved", "reject_claim": "rejected", "reset_claim": "suggested"}  # about one row of the claims sheet
_claims_lock = threading.Lock()
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


TRACE_ID = re.compile(r"[A-Za-z0-9._-]+")


def read_trace(run):
    """The earlier-copy search of a run (trace.csv, eval/run-format.md) as {recording: {searched, leak, claimed, copies}}, or None.

    searched = rows whose fetch was ok. copies = the confirmed rows, each with its caption from the fetch sidecar and its
    evidence image when that is a file under trace/. Every field comes from the web, so the page shows it as text."""
    run = Path(run)
    f = run / "trace.csv"
    if not f.is_file():
        return None
    with open(f, newline="") as fh:
        rows = list(csv.DictReader(fh))
    root = (run / "trace").resolve()
    out = {}
    for r in rows:
        rec = out.setdefault(r["recording"], {"searched": 0, "leak": False, "claimed": "", "copies": [], "possible": []})
        rec["searched"] += r["fetch"] == "ok"
        rec["leak"] |= r.get("leak_exposed") == "1"
        rec["claimed"] = rec["claimed"] or r.get("claimed_date") or ""
        img = (run / r["evidence"]).resolve() if r["evidence"] else None
        evidence = r["evidence"] if img and img.is_file() and img.is_relative_to(root) else ""
        if r["confirmed"] != "1":
            if r.get("possible_source") == "1":  # a lead to check by eye: no date, never a copy
                rec["possible"].append({"url": r["url"], "platform": r["platform"], "account": r["account"], "evidence": evidence})
            continue
        caption, clip = "", r["clip"]
        if TRACE_ID.fullmatch(r["recording"]) and TRACE_ID.fullmatch(clip):
            side = root / r["recording"] / "clips" / f"{clip}.source.json"
            try:
                caption = str(json.loads(side.read_text()).get("caption") or "")[:600]
            except (OSError, ValueError):
                pass
        rec["copies"].append({
            "clip": clip, "url": r["url"], "platform": r["platform"], "account": r["account"], "posted_at": r["posted_at"],
            "source": r["source"], "earlier": r["earlier"] or None, "shown": r["shown"] == "1",
            "leak_copy": r.get("leak_copy") == "1", "date_check": r.get("date_check") or "", "caption": caption,
            "evidence": evidence})
    return out


def append_audit(run, pair, action, note="", clip=None, claim=None):
    """Append one human decision to audit.jsonl and return it. The file is never rewritten.

    A decision about a pair names the pair; confirming or dismissing a compilation names the clip and has pair null."""
    run = Path(run)
    if action in CLIP_ACTIONS or action in CLAIM_ACTIONS:
        if pair is not None or clip not in {c["id"] for c in json.loads((run / "clips.json").read_text())["clips"]}:
            raise ValueError(f"{action} needs a clip of this run and no pair: {clip!r}")
        if action in CLAIM_ACTIONS and not (isinstance(claim, str) and claim):
            raise ValueError(f"{action} needs the claim id")
    elif action not in ACTIONS:
        raise ValueError(f"unknown action: {action!r}")
    elif pair not in {r["pair_id"] for r in read_pairs(run)}:
        raise ValueError(f"unknown pair: {pair!r}")
    entry = {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "actor": "human", "action": action,
             "pair": pair, "note": str(note)[:500]}
    if action in CLIP_ACTIONS or action in CLAIM_ACTIONS:
        entry["clip"] = clip
    if action in CLAIM_ACTIONS:
        entry["claim"] = claim
    path = run / "audit.jsonl"
    with _audit_lock:
        # a file that ends without a newline would otherwise glue the new entry to its last line
        lead = "\n" if path.exists() and path.stat().st_size and not path.read_bytes().endswith(b"\n") else ""
        with open(path, "a") as f:
            f.write(lead + json.dumps(entry) + "\n")
            f.flush()
            os.fsync(f.fileno())
    return entry


def claims_file(run, explicit=None):
    """The claims sheet to use: the one named on the command line, else claims.csv inside the run directory."""
    if explicit:
        return Path(explicit)
    f = Path(run) / "claims.csv"
    return f if f.is_file() else None


def read_claim_rows(path):
    """(rows, reviewed): the rows of a claims sheet as {clip, claim_id, claim_text, quote, status}.

    A sheet with a status column (indexreel claims) is reviewed: only 'approved' rows count, 'rejected' rows are out, and
    anything else is still 'suggested'. A sheet without one (a hand-written list) counts every row as approved."""
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        reviewed = "status" in (reader.fieldnames or [])
        rows = []
        for r in reader:
            st = r.get("status") or "" if reviewed else "approved"  # exact values, as indexreel.withdraw reads them
            rows.append({"clip": r["clip"], "claim_id": r["claim_id"], "claim_text": r.get("claim_text") or "",
                         "quote": r.get("quote") or "", "status": st if st in ("approved", "rejected") else "suggested" if reviewed else "approved"})
    return rows, reviewed


def set_claim_status(run, claims, clip, claim_id, action, note=""):
    """Approve, reject or reset one row of the claims sheet: rewrite its status column, then log the decision in audit.jsonl."""
    if action not in CLAIM_ACTIONS:
        raise ValueError(f"unknown claim action: {action!r}")
    if claims is None:
        raise ValueError("no claims sheet")
    claims = Path(claims)
    with _claims_lock:
        with open(claims, newline="") as f:
            reader = csv.DictReader(f)
            fields, rows = list(reader.fieldnames or []), list(reader)
        if "status" not in fields:
            raise ValueError("this claims sheet has no status column, so its rows cannot be approved here")
        hit = [r for r in rows if r["clip"] == clip and r["claim_id"] == claim_id]
        if not hit:
            raise ValueError(f"no row for clip {clip!r} and claim {claim_id!r}")
        for r in hit:
            r["status"] = CLAIM_ACTIONS[action]
        tmp = claims.with_name(claims.name + ".tmp")
        with open(tmp, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, claims)
    return append_audit(run, None, action, note, clip=clip, claim=claim_id)


def withdraw_view(run, claims, recording):
    """Claims that lose, keep or may keep video support when `recording` is withdrawn (rules in indexreel.withdraw).

    Only approved rows count; `pending` says how many rows are still waiting for a person."""
    if claims is None:
        raise ValueError("no claims file: start the wall with --claims")
    rows, _ = read_claim_rows(claims)
    by_claim, text = {}, {}
    for r in rows:
        if r["status"] == "approved":
            clips = by_claim.setdefault(r["claim_id"], [])
            if r["clip"] not in clips:
                clips.append(r["clip"])
            text.setdefault(r["claim_id"], r["claim_text"])
    out = withdraw.withdraw(withdraw.run_recordings(run), by_claim, recording)
    return out | {"text": text, "pending": sum(r["status"] == "suggested" for r in rows)}


def export(run, out, claims=None, results=None):
    """Write a read-only copy of the page to `out`: index.html with the run embedded, plus the evidence images.

    Nothing here needs a server. Clip paths and the matching command are left out, and the clips themselves are not copied.
    """
    run, out = Path(run).resolve(), Path(out)
    claims = claims_file(run, claims)
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
    for rec in (s["trace"] or {}).values():
        for c in rec["copies"] + rec["possible"]:
            if c["evidence"]:
                (out / c["evidence"]).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(run / c["evidence"], out / c["evidence"])
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
    shared = {}  # pair id -> [{clip, recording, start_s, end_s}]: footage two clips share without being copies
    for rec in recs:
        for clip, segs in rec.get("partial", {}).items():
            for g in segs:
                for link in g["links"]:
                    shared.setdefault(link, []).append({"clip": clip, "recording": g["recording"], "start_s": g["start_s"], "end_s": g["end_s"]})
    suggestions = cluster.resolve_all([c["id"] for c in clips], rows, audit)[2]  # detected, not yet confirmed or dismissed
    by_hand = {}
    clip_decisions = {}
    for e in audit:  # the last entry for a pair counts; reset hands the pair back to the matcher
        if e.get("pair") in computed:
            by_hand[e["pair"]] = e if e["action"] != "reset" else None
        elif e["action"] in CLIP_ACTIONS:
            clip_decisions[e["clip"]] = e
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
            "band": "partial" if r["pair_id"] in shared or (current[r["pair_id"]] != "apart" and {r["a"], r["b"]} & compilations)
                    else current[r["pair_id"]],
            "shared": shared.get(r["pair_id"], []),
            "cover": [float(r["cover_a"]), float(r["cover_b"])] if r.get("cover_a") and r.get("cover_b") else None,
            "core": core if len(core) == 2 else None, "decision": by_hand.get(r["pair_id"]),
            "evidence": r["evidence"], "evidence_times": [[t, round(t + offset, 3)] for t in times],
            "verify": {k[7:]: r[k] for k in r if k.startswith("verify_") and r[k]}})
    claim_rows, claim_review = read_claim_rows(claims) if claims is not None else (None, False)
    return {"run": meta, "claims": claims is not None, "claim_rows": claim_rows, "claim_review": claim_review, "results": read_results(results) if results else None, "trace": read_trace(run), "thresholds": th, "clips": clips, "pairs": pairs, "recordings": recs, "suggestions": suggestions, "clip_decisions": clip_decisions, "audit": audit}


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
            return self.reply(200, state(run, claims_file(run, self.server.claims), self.server.results))
        if path == "/api/withdraw":
            try:
                return self.reply(200, withdraw_view(run, claims_file(run, self.server.claims), parse_qs(urlsplit(self.path).query).get("recording", [""])[0]))
            except (ValueError, KeyError, OSError) as e:
                return self.reply(400, {"error": str(e)})
        if path.startswith("/frames/"):
            f, root = (run / path[1:]).resolve(), (run / "frames").resolve()
            if f.is_file() and f.is_relative_to(root):
                return self.reply(200, f.read_bytes(), mimetypes.guess_type(f.name)[0] or "application/octet-stream")
        if path.startswith("/trace/") and path.endswith(".jpg"):  # evidence images of the earlier-copy search
            f, root = (run / path[1:]).resolve(), (run / "trace").resolve()
            if f.is_file() and f.is_relative_to(root):
                return self.reply(200, f.read_bytes(), "image/jpeg")
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
            if body.get("action") in CLAIM_ACTIONS:  # one row of the claims sheet: its status column, then the audit
                set_claim_status(run, claims_file(run, self.server.claims), body.get("clip"), body.get("claim"), body["action"], body.get("note", ""))
            else:
                append_audit(run, body.get("pair"), body["action"], body.get("note", ""), body.get("clip"))
        except TypeError as e:
            return self.reply(415, {"error": str(e)})
        except RuntimeError as e:
            return self.reply(409, {"error": str(e)})
        except (ValueError, KeyError, OSError, AttributeError) as e:
            return self.reply(400, {"error": str(e)})
        self.reply(200, state(run, claims_file(run, self.server.claims), self.server.results))


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
    ap.add_argument("--claims", type=Path, help="claims sheet (clip, claim_id, claim_text, and from `indexreel claims` quote and status) for the withdraw panel; default: claims.csv in the run directory")
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
