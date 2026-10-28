"""New runs for the clip page: fetch posts or take uploaded clips, then match and verify, one run at a time.

Each run lives in <workdir>/<id>/ with clips/ (fetched and uploaded files) and run/ (the run directory). Commands go
through subprocess as argument lists, never a shell. The page never reads, asks for or prints MODEL_API_KEY: the verify
step inherits the environment, and only whether the variable exists is looked at.
"""
import os
import re
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from urllib.parse import urlsplit

VIDEO = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}
HOSTS = {"x.com", "twitter.com", "www.x.com", "www.twitter.com", "mobile.x.com", "mobile.twitter.com"}
MAX_URLS = 20
MAX_UPLOAD = 500 * 1024 * 1024
MAX_USD = 10.0
KEEP_LINES, LINE = 200, 300
ID = re.compile(r"[0-9a-f]{12}")
SRC = Path(__file__).resolve().parents[2]  # the directory that holds the indexreel package


def clean_url(u):
    """The URL if it is an https post (status) link on x.com or twitter.com, else ValueError."""
    u = str(u).strip()
    p = urlsplit(u)
    if (not u or re.search(r"\s", u) or p.scheme != "https" or p.username or p.password or p.port not in (None, 443)
            or (p.hostname or "").lower() not in HOSTS or "/status/" not in p.path):
        raise ValueError(f"not a post link on x.com or twitter.com: {u[:80]!r}")
    return u


def safe_name(name):
    """A plain file name with a video extension: no directories, only letters, digits and . _ -"""
    stem, ext = os.path.splitext(Path(str(name).replace("\\", "/")).name)
    if ext.lower() not in VIDEO:
        raise ValueError(f"not a video file: {str(name)[:80]!r}")
    return (re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._") or "clip")[:80] + ext.lower()


def default_steps(clips, run, urls, max_usd):
    """[(name, argv or None, why skipped)] for a run. Only whether MODEL_API_KEY is set is checked, never its value."""
    py = [sys.executable, "-m"]
    return [("fetch", py + ["indexreel.cli", "fetch", "--out", str(clips), "--", *urls] if urls else None, "no post links given"),
            ("match", py + ["indexreel.cli", "match", str(clips), "--out", str(run)], ""),
            ("verify", py + ["indexreel.verify", str(run), "--max-usd", f"{max_usd:g}"] if "MODEL_API_KEY" in os.environ else None,
             "MODEL_API_KEY is not set where this page was started; pairs the matcher is unsure about stay unresolved")]


class Runs:
    def __init__(self, workdir, steps=default_steps):
        self.workdir = Path(workdir).resolve()
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.steps, self.jobs, self.lock = steps, {}, threading.Lock()

    def new(self):
        rid = uuid.uuid4().hex[:12]
        (self.workdir / rid / "clips").mkdir(parents=True)
        return rid

    def dir(self, rid):
        d = self.workdir / rid
        return d if ID.fullmatch(str(rid)) and (d / "clips").is_dir() else None

    def run_dir(self, rid):
        d = self.dir(rid)
        return d / "run" if d and (d / "run" / "run.json").is_file() else None

    def save(self, rid, name, stream, length):
        """Store an uploaded clip in the run's clips folder under a safe, unused name."""
        d = self.dir(rid)
        if d is None or rid in self.jobs:
            raise ValueError("unknown run, or it has already started")
        if not 0 < length <= MAX_UPLOAD:
            raise ValueError(f"a file must be between 1 byte and {MAX_UPLOAD // 2**20} MB")
        name = safe_name(name)
        target, n = d / "clips" / name, 1
        while target.exists():
            n += 1
            target = d / "clips" / f"{Path(name).stem}-{n}{Path(name).suffix}"
        left = length
        with open(target, "wb") as f:
            while left:
                chunk = stream.read(min(1 << 20, left))
                if not chunk:
                    target.unlink()
                    raise ValueError("the upload ended early")
                f.write(chunk)
                left -= len(chunk)
        return target.name

    def start(self, rid, urls, max_usd):
        d = self.dir(rid)
        urls = [clean_url(u) for u in urls]
        if d is None or rid in self.jobs:
            raise ValueError("unknown run, or it has already started")
        if len(urls) > MAX_URLS:
            raise ValueError(f"at most {MAX_URLS} links at a time")
        if not 0 <= max_usd <= MAX_USD:
            raise ValueError(f"the spend cap must be between 0 and {MAX_USD:g} dollars")
        with self.lock:
            if any(j["state"] == "running" for j in self.jobs.values()):
                raise RuntimeError("another run is in progress")
            plan = self.steps(d / "clips", d / "run", urls, max_usd)
            self.jobs[rid] = {"id": rid, "state": "running", "error": "",
                              "steps": [{"name": n, "status": "pending", "lines": []} for n, _, _ in plan]}
        threading.Thread(target=self._run, args=(rid, plan), daemon=True).start()

    def job(self, rid):
        with self.lock:
            j = self.jobs.get(rid)
            return None if j is None else {**j, "steps": [{**s, "lines": list(s["lines"])} for s in j["steps"]]}

    def listing(self):
        out = []
        for d in sorted(self.workdir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)[:30]:
            if ID.fullmatch(d.name) and (d / "run" / "run.json").is_file():
                out.append({"id": d.name, "n_clips": sum(1 for f in (d / "clips").iterdir() if f.suffix.lower() in VIDEO)})
        return out

    def _set(self, rid, i, status=None, line=None, **job):
        with self.lock:
            j = self.jobs[rid]
            if status:
                j["steps"][i]["status"] = status
            if line is not None:
                j["steps"][i]["lines"] = (j["steps"][i]["lines"] + [line[:LINE]])[-KEEP_LINES:]
            j.update(job)

    def _run(self, rid, plan):
        d = self.dir(rid)
        env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONPATH": os.pathsep.join([str(SRC)] + ([os.environ["PYTHONPATH"]] if os.environ.get("PYTHONPATH") else []))}
        try:
            for i, (name, argv, why) in enumerate(plan):
                if argv is None:
                    self._set(rid, i, "skipped", why)
                    continue
                if name == "match" and sum(1 for f in (d / "clips").iterdir() if f.suffix.lower() in VIDEO) < 2:
                    self._set(rid, i, "failed", "need at least two clips; nothing was fetched or uploaded for the rest", state="failed",
                              error="need at least two clips")
                    return
                self._set(rid, i, "running")
                p = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env, cwd=str(d),
                                     stdin=subprocess.DEVNULL)
                for line in p.stdout:
                    self._set(rid, i, line=line.rstrip())
                code = p.wait()
                if code == 0 or (name == "fetch" and code == 1):  # fetch exits 1 when some links failed and others came through
                    self._set(rid, i, "ok" if code == 0 else "partial")
                else:
                    self._set(rid, i, "failed", f"{name} exited with code {code}", state="failed", error=f"{name} exited with code {code}")
                    return
            self._set(rid, len(plan) - 1, state="done")
        except Exception as e:  # keep the page informed whatever went wrong
            with self.lock:
                self.jobs[rid].update(state="failed", error=f"{type(e).__name__}: {str(e)[:200]}")
