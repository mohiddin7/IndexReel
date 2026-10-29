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
import os
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
PER_QUERY = 50  # results per YouTube query (yt-dlp and Data API); the pre-rank picks what is fetched
SIZE = 360  # largest shorter side fetched
MAX_S = 1800  # longest candidate fetched, seconds (the coarse pass keeps long ones cheap to match)
COARSE_OVER = 90  # candidates longer than this (s) are first cut to the stretch a coarse pass flags
COARSE_STEP = 4  # the coarse pass looks at one frame every this many seconds
MARGIN = 15  # seconds kept on each side of that stretch; inside it the match runs at 1 frame per second as usual
GUARD = {"web": 0.10, "queries": 0.03, "corroborate": 0.10}
VERIFY_GUARD = 0.05  # verify one candidate only while this much of --max-usd is left, and keep it in reserve  # stop before a call when less than this is left of --max-usd
SEARCH_PRICE = 2.50 / 1000  # USD per web search, on top of tokens
# eval/trace-v2.md: sources, their families, and the choices made before anything is downloaded
ALL_SOURCES = ("web", "keyframe", "channel", "ytapi", "youtube")  # taken in turn in this order
# keyframe search is off: on dev it reached no known earlier upload (eval/trace-v2.md, Amendment B)
SOURCES = ("web", "channel", "ytapi", "youtube")
FAMILY = {"web": "web", "keyframe": "keyframe", "channel": "youtube", "ytapi": "youtube", "youtube": "youtube"}
LEAKY = {"web", "keyframe"}  # sources that can read fact-check pages
BY_DATE = False  # yt-dlp search sorted by upload date instead of relevance
PRERANK = True  # order YouTube results by SSCD on YouTube's own preview frames
DATE_FILTER = True  # read the platform date without downloading; skip posts dated on or after the claimed date
KEYFRAMES = 3  # input frames sent to Cloud Vision web detection, in one request
VISION_CAP = {"day": 25, "total": 300}  # Vision requests; my console quota does not cover web detection
VISION_COUNTER = Path.home() / ".cache" / "indexreel" / "vision_requests.json"
KEY_NAME = "IndexReel_Trace_API_KEY_GCP"  # my Google API key, for the YouTube Data API and Cloud Vision only
CORROBORATE_SEARCHES = 3
PACE_S = 2  # seconds yt-dlp waits between requests to a platform: YouTube asks for a sign-in after a fast burst
COLUMNS = ["recording", "input", "source", "query", "url", "platform", "post_id", "account", "posted_at", "fetch",
           "clip", "duration_s", "cut_start_s", "cut_end_s", "coarse", "band", "verify_verdict", "evidence", "confirmed",
           "earlier", "leak_exposed", "shown", "claimed_date", "leak_copy", "prerank", "families", "strength",
           "corroborated_date", "corroboration_urls"]

QUERY_PROMPT = """You are shown one video. Answer with JSON only, no other text.
The footage may be older than it seems or from somewhere else, so work only from what the video shows.
1. Describe in one sentence what the video shows: the scene, the camera's view, the objects and the motion.
2. Say who most likely filmed or first published footage like this (for example a space agency, a geological survey, a news agency, a storm chaser, a security camera, a tour operator), and give that organisation's YouTube handle if it is a well-known organisation with an official channel, else "".
3. Write {n} short YouTube search queries that would reach the earliest upload of this footage: the visible content in plain words; the visible content with the likely source's name; the visible content with an earlier year or an earlier event of the same kind. If the video shows or speaks a language other than English, write one of the queries in that language.
Return {{"description": "...", "source": "...", "handle": "@...", "queries": ["...", ...]}}."""

SEARCH_PROMPT = """You are shown one video. Use web search to find posts on YouTube, X, TikTok, Instagram, Facebook, Reddit or Vimeo that carry this same footage, above all the earliest uploads. The footage may be older than it seems or from somewhere else, so search from what the video shows. Do not use or cite fact-checking sites or web archives such as {domains}. Search at most {n} times.
Answer with JSON only, no other text: {{"posts": [{{"url": "...", "why": "..."}}]}}, at most 10 posts, each a link to the post itself, not to an article about it."""

CORROBORATE_PROMPT = """You are shown one video, posted on {platform} on {posted} by {account}, with this caption: {caption}
Use web search to find when and where the event this footage shows happened. Prefer official sources (a government agency, the organisation that filmed it) and independent news reports from the time. Search at most {n} times.
Answer with JSON only, no other text: {{"event": "...", "date": "YYYY-MM-DD, or empty if no source gives it", "sources": [{{"url": "...", "date": "YYYY-MM-DD"}}]}}"""


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
    """YouTube results [{url, duration}] for a query, through yt-dlp without downloading anything; inside one channel
    with handle. BY_DATE sorts global search by upload date, newest first."""
    target = (f"https://www.youtube.com/{handle}/search?query={quote(query)}" if handle
              else f"https://www.youtube.com/results?search_query={quote(query)}&sp=CAI%3D" if BY_DATE  # upload date
              else f"ytsearch{n}:{query}")
    r = subprocess.run(["yt-dlp", "--ignore-config", "--no-warnings", "--flat-playlist", "--playlist-end", str(n),
                        "--print", "%(url)s\t%(duration)s", "--", target], capture_output=True, text=True, timeout=300)
    out = []
    for ln in r.stdout.splitlines():
        url, _, d = ln.strip().partition("\t")
        if url.startswith("https://"):
            out.append({"url": url, "duration": float(d) if d not in ("", "NA", "None") else None})
    return out if out or r.returncode == 0 else None  # None: the search failed, so it is not cached


class GoogleStop(Exception):
    """A Google source cannot go on for this run: no key, quota or rate limit, or another HTTP error."""


class Google:
    """YouTube Data API v3 search and Cloud Vision web detection, with my API key (eval/trace-v2.md). The key goes
    only into the request URL and is never logged."""

    def __init__(self, key, counter=VISION_COUNTER):
        self.key, self.counter = key, Path(counter)

    def _count_vision(self, images):
        """Count one Vision request on disk; GoogleStop once the day's or the total cap is reached."""
        c = json.loads(self.counter.read_text()) if self.counter.exists() else {"total": 0, "images": 0, "days": {}}
        today = time.strftime("%Y-%m-%d", time.gmtime())
        if c["total"] >= VISION_CAP["total"] or c["days"].get(today, 0) >= VISION_CAP["day"]:
            raise GoogleStop(f"Vision cap reached: {c['days'].get(today, 0)} requests today, {c['total']} in total")
        c["total"] += 1
        c["images"] += images
        c["days"][today] = c["days"].get(today, 0) + 1
        self.counter.parent.mkdir(parents=True, exist_ok=True)
        self.counter.write_text(json.dumps(c, indent=1))

    def _call(self, url, body=None):
        import urllib.error
        import urllib.request
        req = urllib.request.Request(url + ("&" if "?" in url else "?") + "key=" + quote(self.key),
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            try:
                reason = json.loads(e.read()).get("error", {}).get("status") or ""
            except ValueError:
                reason = ""
            raise GoogleStop(f"HTTP {e.code} {reason}".strip()) from None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise GoogleStop(type(e).__name__) from None

    def videos(self, query, before, n=PER_QUERY):
        """[{url, posted_at}]: YouTube videos for a query, uploaded before the day `before` (YYYY-MM-DD)."""
        d = self._call("https://www.googleapis.com/youtube/v3/search?part=snippet&type=video&order=relevance"
                       f"&maxResults={min(n, 50)}&q={quote(query)}&publishedBefore={before}T00:00:00Z")
        return [{"url": f"https://www.youtube.com/watch?v={it['id']['videoId']}", "posted_at": it["snippet"].get("publishedAt")}
                for it in d.get("items", []) if it.get("id", {}).get("videoId")]

    def video_info(self, ids):
        """{video id: {day, duration}} for up to 50 YouTube ids, from the platform's own record."""
        d = self._call("https://www.googleapis.com/youtube/v3/videos?part=snippet,contentDetails"
                       f"&maxResults=50&id={','.join(ids[:50])}")
        out = {}
        for it in d.get("items", []):
            m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", it.get("contentDetails", {}).get("duration") or "")
            secs = sum(int(x or 0) * k for x, k in zip(m.groups(), (86400, 3600, 60, 1))) if m else None
            out[it["id"]] = {"day": day(it.get("snippet", {}).get("publishedAt")), "duration": secs}
        return out

    def pages(self, jpegs):
        """[{url, title}]: pages that carry images matching any of the frames."""
        import base64
        self._count_vision(len(jpegs))
        d = self._call("https://vision.googleapis.com/v1/images:annotate", {"requests": [
            {"image": {"content": base64.b64encode(j).decode()}, "features": [{"type": "WEB_DETECTION", "maxResults": 50}]}
            for j in jpegs]})
        out = []
        for resp in d.get("responses", []):
            for p in (resp.get("webDetection") or {}).get("pagesWithMatchingImages", []):
                out.append({"url": p.get("url"), "title": re.sub(r"<[^>]+>", "", p.get("pageTitle") or "")})
        return out


def keyframes(path, k=KEYFRAMES):
    """k JPEG frames spread over the clip, at most 640 px wide."""
    import cv2
    d = duration(path) or 1.0
    out = []
    for i in range(k):
        f = frame_at(path, d * (i + 0.5) / k)
        if f is not None:
            if f.shape[1] > 640:
                f = cv2.resize(f, (640, round(f.shape[0] * 640 / f.shape[1])))
            out.append(cv2.imencode(".jpg", f, [cv2.IMWRITE_JPEG_QUALITY, 85])[1].tobytes())
    return out


def post_meta(url):
    """{day, duration} of a post from its platform, read by yt-dlp without downloading."""
    try:
        time.sleep(PACE_S)
        r = subprocess.run(["yt-dlp", "--ignore-config", "--no-warnings", "--skip-download", "--socket-timeout", "20",
                            "--print", "%(extractor)s\t%(timestamp)s\t%(upload_date)s\t%(duration)s", "--", url],
                           capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        return {}
    ln = (r.stdout.strip().splitlines() or [""])[-1].split("\t")
    if len(ln) != 4 or ln[0].lower() == "generic":
        return {}
    ex, ts, ud, d = ln
    if ts not in ("", "NA"):
        dayv = time.strftime("%Y-%m-%d", time.gmtime(float(ts)))
    else:
        dayv = f"{ud[:4]}-{ud[4:6]}-{ud[6:8]}" if re.fullmatch(r"\d{8}", ud) else None
    return {"day": dayv, "duration": float(d) if d not in ("", "NA") else None}


def youtube_id(url):
    p = urlsplit(url)
    if (p.hostname or "").endswith("youtu.be"):
        return p.path.strip("/") or None
    m = re.search(r"(?:v=|/shorts/|/live/)([A-Za-z0-9_-]+)", url)
    return m.group(1) if m else None


class Thumbs:
    """Pre-rank: SSCD of YouTube's own preview frames of a video against the input's frames (plain and mirrored)."""

    def __init__(self, model, cache):
        self.model, self.cache, self.net, self.feats = model, cache, None, {}

    def _get(self, url):
        import urllib.request
        try:
            with urllib.request.urlopen(url, timeout=20) as r:
                return r.read()
        except OSError:
            return None

    def scores(self, clip, ids):
        import cv2
        import numpy as np
        from indexreel import sscd
        from concurrent.futures import ThreadPoolExecutor
        out, sha = {}, verify.sha(clip)
        keys = {vid: hashlib.sha256(json.dumps(["thumb", sha, vid]).encode()).hexdigest() for vid in ids}
        todo = [vid for vid in ids if self.cache.get(keys[vid]) is None]
        names = ("hq1", "hq2", "hq3", "hqdefault")
        with ThreadPoolExecutor(16) as ex:
            got = dict(zip(todo, ex.map(lambda v: [self._get(f"https://i.ytimg.com/vi/{v}/{n}.jpg") for n in names], todo)))
        for vid in ids:
            key = keys[vid]
            hit = self.cache.get(key)
            if hit is None:
                if self.net is None:
                    self.net = sscd.load(self.model)
                if clip not in self.feats:
                    self.feats[clip] = np.vstack(sscd.clip_features(self.net, clip))
                imgs = [cv2.imdecode(np.frombuffer(b, np.uint8), cv2.IMREAD_COLOR) for b in got[vid] if b]
                imgs = [i for i in imgs if i is not None]
                hit = {"score": float((sscd.embed(self.net, imgs) @ self.feats[clip].T).max()) if imgs else None}
                self.cache.put(key, hit)
            out[vid] = hit["score"]
        return out


def run_low(url, out):
    """fetch.run_ytdlp at low resolution, skipping long videos."""
    cmd = fetch.ytdlp_cmd(url, out)
    i = cmd.index("--")
    cmd = cmd[:i] + ["-S", f"res:{SIZE}", "--match-filter", f"duration<={MAX_S}", "--sleep-requests", str(PACE_S),
                     "--sleep-interval", str(PACE_S)] + cmd[i:]
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

    def __init__(self, spark, cache, search=ytsearch, max_usd=1.0, log=print, google=None, thumbs=None, meta=None,
                 sources=SOURCES, prerank=PRERANK, date_filter=DATE_FILTER):
        self.spark, self.cache, self.search, self.max_usd, self.log, self.spent = spark, cache, search, max_usd, log, 0.0
        self.google, self.thumbs, self.meta = google, thumbs, meta
        self.sources, self.prerank, self.date_filter = set(sources), prerank, date_filter
        self.leaks, self.notes, self.scores = {}, {}, {}  # of the last candidates() call

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

    def _cached(self, key, fn):
        key = hashlib.sha256(json.dumps(key).encode()).hexdigest()
        hit = self.cache.get(key)
        if hit is None:
            v = fn()
            if v is None:  # failed: not cached, so a rerun tries again
                return []
            hit = {"v": v}
            self.cache.put(key, hit)
        return hit["v"] if "v" in hit else hit.get("urls")  # a YouTube search cached by v1 trace

    def _google(self, kind, key, fn):
        """A Google call, cached; on GoogleStop that source is off for the rest of the run."""
        if self.google is None or kind in self.notes.get("_off", set()):
            return []
        try:
            return self._cached(key, fn)
        except GoogleStop as e:
            self.notes.setdefault("_off", set()).add(kind)
            self.log(f"trace: the {kind} source stopped for this run ({e})")
            return []

    def candidates(self, clip, before=None):
        """([(source, query, url)] in fetch order, search hits, leak-exposed hits). Also sets, for this call:
        self.leaks {source: leak-exposed hits}, self.notes {url: why it is not fetched}, self.scores {url: pre-rank}."""
        off = self.notes.get("_off", set())
        self.leaks, self.notes, self.scores = {}, {"_off": off}, {}
        ans, _ = self._spark("queries", clip, QUERY_PROMPT.format(n=QUERIES), False)
        queries = [str(q) for q in ((ans or {}).get("queries") or []) if str(q).strip()][:QUERIES]
        handle = str((ans or {}).get("handle") or "").strip()
        handle = handle if re.fullmatch(r"@[A-Za-z0-9._-]{2,40}", handle) else None
        lists = {s: [] for s in ALL_SOURCES}
        info = {}  # url -> {duration, day} known from search
        for q in queries:
            for h, s in ((None, "youtube"), (handle, "channel")):
                if s not in self.sources or (h is None and s == "channel"):
                    continue
                key = ["ytsearch", PER_QUERY, q] + ([h] if h else []) + (["sp=CAI"] if BY_DATE and not h else [])
                for it in self._cached(key, lambda: self.search(q, PER_QUERY, h)):
                    it = it if isinstance(it, dict) else {"url": it}
                    lists[s].append((s, q, it["url"]))
                    info.setdefault(it["url"], {})["duration"] = it.get("duration")
            if "ytapi" in self.sources and before:
                for it in self._google("ytapi", ["ytapi", PER_QUERY, q, before], lambda: self.google.videos(q, before, PER_QUERY)):
                    lists["ytapi"].append(("ytapi", q, it["url"]))
                    info.setdefault(it["url"], {})["day"] = day(it.get("posted_at"))
        hits = []
        if "web" in self.sources:
            text = SEARCH_PROMPT.format(n=SEARCHES, domains=", ".join(EXCLUDED[:6] + ["perma.cc", "archive.org"]))
            ans, hits = self._spark("web", clip, text, True)
            lists["web"] = [("web", "", str((p or {}).get("url") or "")) for p in ((ans or {}).get("posts") or []) if isinstance(p, dict)]
            self.leaks["web"] = leaky(hits)
        if "keyframe" in self.sources and self.google is not None:
            frames = keyframes(clip)
            fh = hashlib.sha256(b"".join(hashlib.sha256(j).digest() for j in frames)).hexdigest()
            pages = self._google("keyframe", ["vision", fh], lambda: self.google.pages(frames)) if frames else []
            lists["keyframe"] = [("keyframe", "", p["url"]) for p in pages if post_url(p.get("url"))]
            self.leaks["keyframe"] = leaky(pages)
            hits = hits + pages
        order, at = [], {}
        srcs = [lists[s] for s in ALL_SOURCES]
        for i in range(max(map(len, srcs))):  # take the sources in turn
            for src in srcs:
                if i < len(src):
                    s, q, u = src[i]
                    if u not in at:
                        at[u] = len(order)
                        order.append((s, q, u))
                    elif s not in order[at[u]][0].split("+"):  # found again: keep every source that found it
                        s0, q0, _ = order[at[u]]
                        order[at[u]] = (f"{s0}+{s}", q0 or q, u)
        if self.prerank and self.thumbs is not None:
            ids = {u: youtube_id(u) for _, _, u in order if post_url(u) and youtube_id(u)}
            sc = self.thumbs.scores(clip, sorted(set(ids.values())))
            self.scores = {u: sc.get(v) for u, v in ids.items() if sc.get(v) is not None}
            # posts that cannot be pre-ranked (not on YouTube) keep their turn ahead of ranked ones
            order.sort(key=lambda o: -self.scores.get(o[2], 2.0))
        if self.date_filter and before and "ytapi" in self.sources:  # YouTube dates from the Data API, not yt-dlp
            ids = sorted({youtube_id(u) for _, _, u in order if post_url(u) and youtube_id(u)})
            known = {}
            for i in range(0, len(ids), 50):
                known.update(self._google("ytapi", ["videos", ids[i:i + 50]], lambda: self.google.video_info(ids[i:i + 50])))
            for _, _, u in order:
                v = known.get(youtube_id(u) or "")
                if v:
                    info.setdefault(u, {}).update({k: x for k, x in v.items() if x is not None})
        kept = 0
        for _, _, u in order:
            if kept >= MAX_CANDIDATES or not post_url(u):
                continue
            d = (info.get(u) or {}).get("duration")
            if d and d > MAX_S:
                self.notes[u] = "too_long"
                continue
            if self.date_filter and before and self.meta is not None:
                dayv = (info.get(u) or {}).get("day")
                if dayv is None:
                    m = self._cached(["meta", u], lambda: self.meta(u))
                    dayv, d = m.get("day"), m.get("duration")
                    if d and d > MAX_S:
                        self.notes[u] = "too_long"
                        continue
                if dayv and dayv >= before:
                    self.notes[u] = "after_claim"
                    continue
            kept += 1
        all_leaks = [h for v in self.leaks.values() for h in v]
        return order, hits, all_leaks

    def corroborate(self, clip, info):
        """The date-corroboration answer for one shown copy ({} when skipped)."""
        text = CORROBORATE_PROMPT.format(platform=info.get("platform") or "", posted=day(info.get("posted_at")) or "",
                                         account=info.get("account") or "", caption=(info.get("caption") or "")[:1000],
                                         n=CORROBORATE_SEARCHES)
        ans, _ = self._spark("corroborate", clip, text, True)
        return ans if isinstance(ans, dict) else {}


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

    order, hits, leaks = searcher.candidates(str(src), before)  # what the clip shows only; the claims stay on the page
    exposed = {s for s, v in searcher.leaks.items() if v} if searcher.leaks else ({"web"} if leaks else set())
    work = run / "trace" / rec["id"]
    cdir = work / "clips"
    cdir.mkdir(parents=True, exist_ok=True)
    (work / "search_hits.json").write_text(json.dumps({"hits": hits, "leak_exposed": leaks,
                                                       "leak_exposed_by_source": searcher.leaks}, indent=1))
    rows, urls = [], []
    for s, q, u in order:
        row = {"recording": rec["id"], "input": clip["id"], "source": s, "query": q, "url": u, "leak_exposed": int(bool(exposed)),
               "prerank": round(searcher.scores[u], 4) if u in searcher.scores else "",
               "families": "+".join(sorted({FAMILY.get(x, x) for x in s.split("+")}))}
        if not post_url(u):
            row["fetch"] = "excluded" if excluded(u) else "not_a_post"
        elif u in searcher.notes:
            row["fetch"] = searcher.notes[u]
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
        # found only by sources that also read fact-check pages: fails leak rule 2 (eval/trace-v2.md, per source)
        r["leak_copy"] = int(set(r["source"].split("+")) <= exposed)
    if shown and hasattr(searcher, "corroborate"):
        corroborate(searcher, shown[0], cdir)
    return rows


def corroborate(searcher, r, cdir):
    """Date corroboration and strength of the shown copy (eval/trace-v2.md, Corroboration)."""
    f = next((p for p in sorted(cdir.glob(r["clip"] + ".*")) if not p.name.endswith(".json")), None)
    info = json.loads((cdir / f"{r['clip']}.source.json").read_text()) if (cdir / f"{r['clip']}.source.json").exists() else {}
    ans = searcher.corroborate(str(f), info) if f else {}
    found = str(ans.get("date") or "")[:10] if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(ans.get("date") or "")[:10]) else ""
    urls = [str(s.get("url")) for s in (ans.get("sources") or []) if isinstance(s, dict) and s.get("url")]
    sites = {(urlsplit(u).hostname or "").lower().removeprefix("www.") for u in urls} - {""}
    corroborated = bool(found) and found <= (day(r.get("posted_at")) or "") and len(sites) >= 2
    r["corroborated_date"] = found if corroborated else ""
    r["corroboration_urls"] = " ".join(urls)
    r["strength"] = "strong" if "+" in r["families"] or corroborated else "single-source"


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
    cache = verify.Cache(a.cache / "trace")
    key = os.environ.get(KEY_NAME)
    if not key:
        print(f"trace: no {KEY_NAME}, so the YouTube Data API and keyframe sources are skipped")
    searcher = Searcher(SparkSearch(a.cache / "verify" / "clips"), cache, max_usd=a.max_usd,
                        google=Google(key) if key else None, thumbs=Thumbs(a.sscd_model, cache), meta=post_meta)
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
