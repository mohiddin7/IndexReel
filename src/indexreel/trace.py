"""indexreel trace: look for earlier uploads of each recording of a run on the web, and confirm them with the matcher.

  MODEL_API_KEY=... indexreel trace <run dir> [--claimed-dates FILE] [--max-usd 1]

For each recording, Muse Spark proposes posts that may carry the same footage from two sources (eval/trace.md):
(A) web search, told to avoid fact-checking sites, and (B) YouTube search through yt-dlp with queries Spark writes
without web search. Candidates on excluded domains are dropped. At most MAX_CANDIDATES are fetched at low resolution,
matched against the recording's clip with `indexreel match` and checked with the verify stage. A candidate is a
confirmed copy only when its pair's effective band is `merged`. trace.csv lists every candidate; the earliest
confirmed copy that its platform dates before the claimed date is marked `shown`. Nothing is called true or false.
Spark answers and YouTube searches are cached, so a rerun costs nothing.
"""
import argparse
import csv
import hashlib
import json
import re
import subprocess
import time
from pathlib import Path
from urllib.parse import quote, urlsplit

from indexreel import cli, cluster, fetch, verify, withdraw

# Frozen in eval/trace.md (leak rule 1): host, or host plus path prefix.
EXCLUDED = ["afp.com", "reuters.com/fact-check", "apnews.com/article/fact-check", "snopes.com", "fullfact.org",
            "politifact.com", "leadstories.com", "factcheck.org", "aap.com.au/factcheck", "boomlive.in", "altnews.in",
            "factly.in", "factcrescendo.com", "newschecker.in", "thequint.com/news/webqoof", "indiatoday.in/fact-check",
            "vishvasnews.com", "logicallyfacts.com", "africacheck.org", "pesacheck.org", "misbar.com", "verafiles.org",
            "rappler.com", "tfc-taiwan.org.tw", "factcheckcenter.jp", "maldita.es", "newtral.es", "correctiv.org",
            "dpa-factchecking.com", "usatoday.com/story/news/factcheck", "verifythis.com", "annielab.org", "dfrac.org",
            "perma.cc", "archive.ph", "archive.today", "archive.org", "ghostarchive.org", "mvau.lt"]
# Sites where only the fact-check section is excluded: a page counts when its URL or title has one of these words.
SECTION_SITES = ["scmp.com", "dw.com", "bbc.com", "bbc.co.uk"]
SECTION_WORDS = ["fact-check", "fact check", "factcheck", "fact_check", "verify", "reality check", "reality_check"]
LEAK_WORDS = ["fact check", "fact-check", "debunk", "false", "misleading", "misrepresent", "miscaption", "hoax", "not from"]
# Post hosts a candidate may come from, and the yt-dlp extractors whose dates count (leak rule 4).
HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "x.com", "twitter.com", "www.tiktok.com",
         "tiktok.com", "www.instagram.com", "instagram.com", "www.facebook.com", "facebook.com", "m.facebook.com",
         "fb.watch", "www.reddit.com", "reddit.com", "old.reddit.com", "vimeo.com"}
PLATFORMS = {"youtube", "x", "tiktok", "instagram", "facebook", "reddit", "vimeo"}
MAX_CANDIDATES = 10
SEARCHES = 3  # web searches Spark is asked to make at most
QUERIES = 3  # YouTube queries
PER_QUERY = 5
SIZE = 360  # largest shorter side fetched
MAX_S = 1800  # longest candidate fetched, seconds (the coarse pass keeps long ones cheap to match)
COARSE_OVER = 90  # candidates longer than this (s) are first cut to the stretch a coarse pass flags
COARSE_STEP = 4  # the coarse pass looks at one frame every this many seconds
MARGIN = 15  # seconds kept on each side of that stretch; inside it the match runs at 1 frame per second as usual
GUARD = {"web": 0.10, "queries": 0.03}
VERIFY_GUARD = 0.05  # verify one candidate only while this much of --max-usd is left, and keep it in reserve  # stop before a call when less than this is left of --max-usd
SEARCH_PRICE = 2.50 / 1000  # USD per web search, on top of tokens
COLUMNS = ["recording", "input", "source", "query", "url", "platform", "post_id", "account", "posted_at", "fetch",
           "clip", "duration_s", "cut_start_s", "cut_end_s", "coarse", "band", "verify_verdict", "evidence", "confirmed",
           "earlier", "leak_exposed", "shown", "claimed_date", "leak_copy"]

QUERY_PROMPT = """You are shown one video. Answer with JSON only, no other text.
The footage may be older than it seems or from somewhere else, so work only from what the video shows.
1. Describe in one sentence what the video shows: the scene, the camera's view, the objects and the motion.
2. Say who most likely filmed or first published footage like this (for example a space agency, a geological survey, a news agency, a storm chaser, a security camera, a tour operator), and give that organisation's YouTube handle if it is a well-known organisation with an official channel, else "".
3. Write {n} short YouTube search queries that would reach the earliest upload of this footage: the visible content in plain words; the visible content with the likely source's name; the visible content with an earlier year or an earlier event of the same kind. If the video shows or speaks a language other than English, write one of the queries in that language.
Return {{"description": "...", "source": "...", "handle": "@...", "queries": ["...", ...]}}."""

SEARCH_PROMPT = """You are shown one video. Use web search to find posts on YouTube, X, TikTok, Instagram, Facebook, Reddit or Vimeo that carry this same footage, above all the earliest uploads. The footage may be older than it seems or from somewhere else, so search from what the video shows. Do not use or cite fact-checking sites or web archives such as {domains}. Search at most {n} times.
Answer with JSON only, no other text: {{"posts": [{{"url": "...", "why": "..."}}]}}, at most 10 posts, each a link to the post itself, not to an article about it."""


def _on(host, site):
    return host == site or host.endswith("." + site)


def excluded(url, title=""):
    """True for a page on a fact-checking site or web archive (leak rule 1 of eval/trace.md)."""
    p = urlsplit(url)
    host, path = (p.hostname or "").lower(), p.path.lower() or "/"
    for e in EXCLUDED:
        site, _, prefix = e.partition("/")
        if _on(host, site) and path.startswith("/" + prefix):
            return True
    text = (path + " " + (title or "")).lower()
    return any(_on(host, s) for s in SECTION_SITES) and any(w in text for w in SECTION_WORDS)


def leaky(hits):
    """The search hits that break leak rule 2: on an excluded site, or titled like a fact-check."""
    return [h for h in hits if excluded(h.get("url") or "", h.get("title") or "")
            or any(w in (h.get("title") or "").lower() for w in LEAK_WORDS)]


def post_url(url):
    """The URL if it may be fetched as a candidate post, else None. On YouTube only single videos count, not search
    results, playlists or channels."""
    url = (url or "").strip()
    if not url or excluded(url) or fetch.valid_url(url, HOSTS):
        return None
    p = urlsplit(url)
    if "youtube.com" in (p.hostname or "") and not (p.path == "/watch" and "v=" in p.query or p.path.startswith(("/shorts/", "/live/"))):
        return None
    return url


def day(stamp):
    return (stamp or "")[:10] or None


class SparkSearch(verify.SparkJudge):
    """The verify stage's Spark client, asked about one video with or without web search."""

    def ask(self, clip, text, web):
        """(answer, search hits [{title, url}], cost in USD, final status)."""
        content = [{"type": "input_text", "text": text + "\nVideo:"}, {"type": "input_file", "file_id": self._file(clip, 180)}]
        kw = {"tools": [{"type": "web_search"}], "include": ["web_search_call.results"]} if web else {}
        out, final = [], None
        with self.cli.responses.stream(model=verify.MODEL, input=[{"type": "message", "role": "user", "content": content}],
                                       max_output_tokens=8000, reasoning={"effort": "low" if web else "minimal"}, **kw) as s:
            for ev in s:
                if ev.type == "response.output_text.delta":
                    out.append(ev.delta)
                elif ev.type in ("response.completed", "response.incomplete", "response.failed"):
                    final = ev.response
        if final is None:
            return None, [], 0.0, "no final event"
        calls = [it for it in final.output if getattr(it, "type", "") == "web_search_call"]
        hits = [{"title": getattr(r, "title", None) or (r.get("title") if isinstance(r, dict) else None),
                 "url": getattr(r, "url", None) or (r.get("url") if isinstance(r, dict) else None)}
                for c in calls for r in (getattr(c, "results", None) or [])]
        u = final.usage
        cached = (u.input_tokens_details.cached_tokens or 0) if u and u.input_tokens_details else 0
        cost = ((u.input_tokens - cached) * verify.PRICE["input"] + cached * verify.PRICE["cached"]
                + u.output_tokens * verify.PRICE["output"]) / 1e6 if u else 0.0
        return (verify.parse("".join(out)) if final.status == "completed" else None), hits, cost + len(calls) * SEARCH_PRICE, final.status


def ytsearch(query, n=PER_QUERY, handle=None):
    """YouTube watch URLs for a query, through yt-dlp without downloading anything; inside one channel with handle."""
    target = (f"https://www.youtube.com/{handle}/search?query={quote(query)}" if handle else f"ytsearch{n}:{query}")
    r = subprocess.run(["yt-dlp", "--ignore-config", "--no-warnings", "--flat-playlist", "--playlist-end", str(n),
                        "--print", "url", "--", target], capture_output=True, text=True, timeout=120)
    return [ln.strip() for ln in r.stdout.splitlines() if ln.startswith("https://")]


def run_low(url, out):
    """fetch.run_ytdlp at low resolution, skipping long videos."""
    cmd = fetch.ytdlp_cmd(url, out)
    i = cmd.index("--")
    cmd = cmd[:i] + ["-S", f"res:{SIZE}", "--match-filter", f"duration<={MAX_S}"] + cmd[i:]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, f"ERROR: {type(e).__name__}"
    lines = (r.stderr + "\n" + r.stdout).splitlines()
    err = next((ln for ln in lines if "error" in ln.lower()), "")
    if not err and any("does not pass filter" in ln for ln in lines):
        err = f"ERROR: longer than {MAX_S} s"
    return r.returncode, err


def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def sparse_frames(path, step, tmp):
    """One frame every `step` seconds, as BGR arrays."""
    import cv2
    for f in Path(tmp).glob("*.jpg"):
        f.unlink()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(path), "-vf", f"fps=1/{step},scale=-2:256", "-q:v", "3",
                    str(Path(tmp) / "%05d.jpg")], check=True)
    return [cv2.imread(str(f)) for f in sorted(Path(tmp).glob("*.jpg"))]


def narrow(model, input_path, cdir, work, rows, log=print):
    """Cut each long candidate to the stretch most like the input (eval/trace.md, dev constant). The full file moves
    to <work>/full/; the cut keeps the clip id, and the row says where in the post it starts and ends."""
    import numpy as np
    from indexreel import sscd
    net, feats, tmp = None, None, work / "coarse"
    (work / "full").mkdir(exist_ok=True)
    tmp.mkdir(exist_ok=True)
    cuts_file = work / "cuts.json"
    cuts = json.loads(cuts_file.read_text()) if cuts_file.exists() else {}
    for r in rows:
        if r.get("clip") in cuts:  # cut on an earlier run
            r.update(cuts[r["clip"]])
            continue
        f = next((p for p in sorted(cdir.glob(f"{r.get('clip')}.*")) if not p.name.endswith(".json")), None)
        if not r.get("clip") or f is None:
            continue
        r["duration_s"] = d = round(duration(f), 3)
        if d <= COARSE_OVER:
            continue
        t0 = time.time()
        if net is None:
            net = sscd.load(model)
            plain, mirror = sscd.clip_features(net, input_path)
            feats, dur_in = np.vstack([plain, mirror]), duration(input_path)
        fr = sparse_frames(f, COARSE_STEP, tmp)
        sims = (sscd.embed(net, fr) @ feats.T).max(1) if fr else np.zeros(1)
        best = int(sims.argmax())
        t = (best + 0.5) * COARSE_STEP
        a, b = max(0.0, t - dur_in - MARGIN), min(d, t + dur_in + MARGIN)
        full = work / "full" / f.name
        f.rename(full)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-i", str(full), "-c:v",
                        "libx264", "-crf", "23", "-c:a", "aac", str(cdir / (r["clip"] + ".mp4"))], check=True)
        cuts[r["clip"]] = {"duration_s": d, "cut_start_s": round(a, 3), "cut_end_s": round(b, 3), "coarse": round(float(sims.max()), 4)}
        cuts_file.write_text(json.dumps(cuts, indent=1))
        r.update(cuts[r["clip"]])
        log(f"trace: {r['clip']} {d:.0f} s cut to {a:.0f}-{b:.0f} s (coarse best {sims.max():.3f}) in "
            f"{time.time() - t0:.1f} s")


def frame_at(path, t):
    import cv2
    cap = cv2.VideoCapture(str(path))
    cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, t) * 1000)
    ok, f = cap.read()
    cap.release()
    return f if ok else None


def core_evidence(pdir, p, out):
    """Three aligned frame pairs from inside the pair's core span (where the two clips really match), so the image
    shows the link even when the input is cut from a longer video. Returns False when the pair has no core span."""
    import cv2
    import numpy as np
    if not p.get("core_a_start_s"):
        return False
    a0, a1, k = float(p["core_a_start_s"]), float(p["core_a_end_s"]), float(p["offset_s"])
    path = {f.stem: f for f in pdir.iterdir() if f.is_symlink()}
    ts = sorted({a0 + 0.5, (a0 + a1) / 2, max(a0 + 0.5, a1 - 0.5)})
    rows = []
    for t in ts + [ts[-1]] * (3 - len(ts)):
        fa, fb = frame_at(path[p["a"]], t), frame_at(path[p["b"]], t + k)
        if fa is None or fb is None:
            return False
        left, right = cli.thumb(fa[:, ::-1] if p.get("mirrored") == "1" else fa), cli.thumb(fb)
        for img, name, at in ((left, p["a"], t), (right, p["b"], t + k)):
            cv2.putText(img, f"{name[:22]} {at:.1f}s", (6, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
        rows.append(np.hstack([left, right]))
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 75])
    return True


class Searcher:
    """The two sources with caching and a spending cap. spark and search are injectable for tests."""

    def __init__(self, spark, cache, search=ytsearch, max_usd=1.0, log=print):
        self.spark, self.cache, self.search, self.max_usd, self.log, self.spent = spark, cache, search, max_usd, log, 0.0

    def _spark(self, kind, clip, text, web):
        key = hashlib.sha256(json.dumps([verify.MODEL, kind, text, verify.sha(clip)]).encode()).hexdigest()
        hit = self.cache.get(key)
        if hit is None:
            if self.spent + GUARD[kind] > self.max_usd:
                self.log(f"trace: skipped the {kind} request, ${self.spent:.4f} spent of --max-usd {self.max_usd}")
                return None, []
            ans, hits, cost, status = self.spark.ask(clip, text, web)
            self.spent += cost
            if status != "completed":
                self.log(f"trace: the {kind} request ended {status}, cost ${cost:.4f}; not cached")
                return None, hits
            hit = {"answer": ans, "hits": hits, "cost": cost}
            self.cache.put(key, hit)
        return hit["answer"], hit["hits"]

    def candidates(self, clip):
        """([(source, query, url)] in fetch order, search hits, leak-exposed hits)."""
        ans, _ = self._spark("queries", clip, QUERY_PROMPT.format(n=QUERIES), False)
        queries = [str(q) for q in ((ans or {}).get("queries") or []) if str(q).strip()][:QUERIES]
        handle = str((ans or {}).get("handle") or "").strip()
        handle = handle if re.fullmatch(r"@[A-Za-z0-9._-]{2,40}", handle) else None
        yt, chan = [], []
        for q in queries:
            for h, out in ((None, yt), (handle, chan)) if handle else ((None, yt),):
                key = hashlib.sha256(json.dumps(["ytsearch", PER_QUERY, q] + ([h] if h else [])).encode()).hexdigest()
                urls = (self.cache.get(key) or {}).get("urls")
                if urls is None:
                    urls = self.search(q, PER_QUERY, h)
                    self.cache.put(key, {"urls": urls})
                out += [("channel" if h else "youtube", q, u) for u in urls]
        text = SEARCH_PROMPT.format(n=SEARCHES, domains=", ".join(EXCLUDED[:6] + ["perma.cc", "archive.org"]))
        ans, hits = self._spark("web", clip, text, True)
        web = [("web", "", str((p or {}).get("url") or "")) for p in ((ans or {}).get("posts") or []) if isinstance(p, dict)]
        order, at = [], {}
        for i in range(max(len(web), len(chan), len(yt))):  # take the sources in turn: web, channel, YouTube
            for src in (web, chan, yt):
                if i < len(src):
                    s, q, u = src[i]
                    if u not in at:
                        at[u] = len(order)
                        order.append((s, q, u))
                    elif s not in order[at[u]][0].split("+"):  # found again: keep every source that found it
                        s0, q0, _ = order[at[u]]
                        order[at[u]] = (f"{s0}+{s}", q0 or q, u)
        return order, hits, leaky(hits)


def claimed_dates(path):
    """{clip id: YYYY-MM-DD} from a CSV with columns clip, claimed_date."""
    return {r["clip"]: r["claimed_date"][:10] for r in csv.DictReader(open(path, newline=""))} if path else {}


def trace_recording(run, rec, clips, searcher, dates, model, max_usd, judge=None, cache=None, fetcher=run_low,
                    matcher=cli.match, verifier=verify.verify, narrower=narrow, log=print):
    """trace.csv rows for one recording; candidates go to <run>/trace/<recording>/."""
    run = Path(run)
    by_id = {c["id"]: c for c in clips}
    members = [m for m in rec["members"] if m in by_id]
    clip = by_id[members[0]]
    src = Path(clip["path"]) if Path(clip["path"]).is_absolute() else run / clip["path"]
    posted = [day((by_id[m].get("source") or {}).get("posted_at")) for m in members]
    before = min([dates[m] for m in members if m in dates] or [p for p in posted if p] or [None])
    own = {((by_id[m].get("source") or {}).get("platform"), (by_id[m].get("source") or {}).get("post_id")) for m in members}

    order, hits, leaks = searcher.candidates(str(src))  # what the clip shows only; the claims stay on the page
    work = run / "trace" / rec["id"]
    cdir = work / "clips"
    cdir.mkdir(parents=True, exist_ok=True)
    (work / "search_hits.json").write_text(json.dumps({"hits": hits, "leak_exposed": leaks}, indent=1))
    rows, urls = [], []
    for s, q, u in order:
        row = {"recording": rec["id"], "input": clip["id"], "source": s, "query": q, "url": u, "leak_exposed": int(bool(leaks))}
        if not post_url(u):
            row["fetch"] = "excluded" if excluded(u) else "not_a_post"
        elif len(urls) >= MAX_CANDIDATES:
            row["fetch"] = "over_cap"
        else:
            urls.append(u)
        rows.append(row)
    said = []
    fetch.fetch(urls, cdir, run=fetcher, say=said.append)
    got = {}
    for line in said:
        log(line)
        parts = line.split()
        if parts[1] == "ok":
            got[parts[2]] = Path(parts[4]).stem
        elif parts[1] == "error":
            got[parts[2]] = "error " + parts[3].rstrip(":")
        elif parts[1] == "skip":
            got[parts[2]] = parts[-1]
    for row in rows:
        if row["url"] in got:
            v = got[row["url"]]
            row["fetch"], row["clip"] = (v, "") if v.startswith("error") else ("ok", v)
            if row["clip"]:
                info = json.loads((cdir / f"{v}.source.json").read_text())
                row.update({k: info.get(k) or "" for k in ("platform", "post_id", "account", "posted_at")})
                if (info.get("platform"), info.get("post_id")) in own:
                    row["fetch"], row["clip"] = "same_post_as_input", ""

    fetched = [r for r in rows if r.get("clip")]
    if fetched:
        link = Path(f"input_{clip['id']}{src.suffix.lower()}")
        for r in rows:  # candidates fetched but not kept (the input's own post) stay out of the match
            if r.get("fetch") == "same_post_as_input":
                for f in cdir.glob(f"{got[r['url']]}.*"):
                    f.unlink()
        narrower(model, src, cdir, work, fetched, log)
        for r in fetched:  # the input against each candidate on its own: no money on candidate-to-candidate pairs
            cand = next(p for p in sorted(cdir.glob(r["clip"] + ".*")) if not p.name.endswith(".json"))
            pdir = work / "pairs" / r["clip"]
            pdir.mkdir(parents=True, exist_ok=True)
            for name, target in ((link.name, src.resolve()), (cand.name, cand.resolve())):
                if not (pdir / name).is_symlink():
                    (pdir / name).symlink_to(target)
            out = pdir / "run"
            t0 = time.time()
            matcher(pdir, out, model)
            left = max_usd - searcher.spent
            if judge and left >= VERIFY_GUARD:
                spent, _ = verifier(out, judge, cache, max_usd=left - VERIFY_GUARD, workers=1)
                searcher.spent += spent
            elif judge:
                log(f"trace: {r['clip']} not verified, ${searcher.spent:.4f} spent of --max-usd {max_usd}")
            p = next(iter(csv.DictReader(open(out / "pairs.csv", newline=""))), None)
            log(f"trace: {r['clip']} matched in {time.time() - t0:.0f} s")
            if p is None:
                continue
            ev = f"trace/{rec['id']}/pairs/{r['clip']}/core.jpg"
            if not (p.get("evidence") and core_evidence(pdir, p, run / ev)):
                ev = f"trace/{rec['id']}/pairs/{r['clip']}/run/{p['evidence']}" if p.get("evidence") else ""
            r.update({"band": cluster.effective_band(p), "verify_verdict": p.get("verify_verdict", ""), "evidence": ev})
            r["confirmed"] = int(r["band"] == "merged")
            dated = r.get("platform") in PLATFORMS and day(r.get("posted_at"))
            r["earlier"] = (int(day(r["posted_at"]) < before) if before else "") if dated else ""
    shown = sorted((r for r in rows if r.get("confirmed") == 1 and r.get("earlier") == 1), key=lambda r: r["posted_at"])
    for r in rows:
        r["shown"] = int(bool(shown) and r is shown[0])
        r["claimed_date"] = before or ""
        # found only by a web search that also read fact-check pages: fails leak rule 2 of eval/trace.md
        r["leak_copy"] = int(bool(leaks) and set(r["source"].split("+")) <= {"web"})
    return rows


def trace(run, searcher, model=cli.MODEL, dates=None, judge=None, cache=None, log=print, **kw):
    """Write <run>/trace.csv for every recording. Returns the rows."""
    run = Path(run)
    clips = json.loads((run / "clips.json").read_text())["clips"]
    rows = []
    for rec in withdraw.run_recordings(run):
        rows += trace_recording(run, rec, clips, searcher, dates or {}, model, searcher.max_usd, judge, cache, log=log, **kw)
    with open(run / "trace.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore", restval="")
        w.writeheader()
        w.writerows(rows)
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(prog="indexreel trace", description=__doc__.split("\n\n")[0])
    ap.add_argument("run", type=Path, help="run directory written by `indexreel match`")
    ap.add_argument("--claimed-dates", type=Path, help="CSV with columns clip, claimed_date (YYYY-MM-DD); default: "
                                                        "the earliest post time of the recording's clips")
    ap.add_argument("--max-usd", type=float, default=1.0, help="stop making new calls once this much is spent")
    ap.add_argument("--cache", type=Path, default=Path.home() / ".cache" / "indexreel")
    ap.add_argument("--sscd-model", default=str(cli.MODEL))
    a = ap.parse_args(argv)
    searcher = Searcher(SparkSearch(a.cache / "verify" / "clips"), verify.Cache(a.cache / "trace"), max_usd=a.max_usd)
    rows = trace(a.run, searcher, a.sscd_model, claimed_dates(a.claimed_dates),
                 verify.SparkJudge(a.cache / "verify" / "clips"), verify.Cache(a.cache / "verify" / "answers"))
    n = sum(r.get("confirmed") == 1 for r in rows)
    print(f"trace: {len(rows)} candidates, {n} confirmed copies, {sum(r.get('shown') == 1 for r in rows)} shown; "
          f"spent ${searcher.spent:.4f} now")
    for r in rows:
        if r.get("shown") == 1:
            print(f"trace: {r['recording']}: earliest confirmed copy {r['url']} posted {r['posted_at']} on {r['platform']}")


if __name__ == "__main__":
    main()
