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
import datetime
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

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
MAX_S = 900  # longest candidate fetched, seconds
GUARD = {"web": 0.10, "queries": 0.03}  # stop before a call when less than this is left of --max-usd
SEARCH_PRICE = 2.50 / 1000  # USD per web search, on top of tokens
COLUMNS = ["recording", "input", "source", "query", "url", "platform", "post_id", "account", "posted_at", "fetch",
           "clip", "band", "verify_verdict", "evidence", "confirmed", "earlier", "leak_exposed", "shown"]

QUERY_PROMPT = """You are shown one video and the claims its post made about it. Answer with JSON only, no other text.
Describe what the video shows in one sentence: the scene, place clues, any visible text, the kind of event. Then write {n} short search queries that would find other uploads of this same footage on YouTube, in the language that fits the place. The claims may be wrong (the footage may be older or from somewhere else), so write at least one query from what is visible alone, without the claimed place or date.
Return {{"description": "...", "queries": ["...", ...]}}.
Claims: {claims}"""

SEARCH_PROMPT = """You are shown one video and the claims its post made about it. Use web search to find posts on YouTube, X, TikTok, Instagram, Facebook, Reddit or Vimeo that carry this same footage, above all the earliest uploads. The claims may be wrong (the footage may be older or filmed elsewhere), so also search for what is visible, without the claimed place or date. Do not use or cite fact-checking sites or web archives such as {domains}. Search at most {n} times.
Answer with JSON only, no other text: {{"posts": [{{"url": "...", "why": "..."}}]}}, at most 10 posts, each a link to the post itself, not to an article about it.
Claims: {claims}"""


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
    """The URL if it may be fetched as a candidate post, else None."""
    url = (url or "").strip()
    return url if url and not excluded(url) and not fetch.valid_url(url, HOSTS) else None


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


def ytsearch(query, n=PER_QUERY):
    """YouTube watch URLs for a query, through yt-dlp without downloading anything."""
    r = subprocess.run(["yt-dlp", "--ignore-config", "--no-warnings", "--flat-playlist", "--print", "url",
                        "--", f"ytsearch{n}:{query}"], capture_output=True, text=True, timeout=120)
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

    def candidates(self, clip, claims):
        """([(source, query, url)] in fetch order, search hits, leak-exposed hits)."""
        listed = "; ".join(claims) or "(none)"
        ans, _ = self._spark("queries", clip, QUERY_PROMPT.format(n=QUERIES, claims=listed), False)
        queries = [str(q) for q in ((ans or {}).get("queries") or []) if str(q).strip()][:QUERIES]
        yt = []
        for q in queries:
            key = hashlib.sha256(json.dumps(["ytsearch", PER_QUERY, q]).encode()).hexdigest()
            urls = (self.cache.get(key) or {}).get("urls")
            if urls is None:
                urls = self.search(q, PER_QUERY)
                self.cache.put(key, {"urls": urls})
            yt += [("youtube", q, u) for u in urls]
        text = SEARCH_PROMPT.format(n=SEARCHES, claims=listed, domains=", ".join(EXCLUDED[:6] + ["perma.cc", "archive.org"]))
        ans, hits = self._spark("web", clip, text, True)
        web = [("web", "", str((p or {}).get("url") or "")) for p in ((ans or {}).get("posts") or []) if isinstance(p, dict)]
        order, seen = [], set()
        for i in range(max(len(web), len(yt))):  # alternate the sources, web first
            for src in (web, yt):
                if i < len(src):
                    s, q, u = src[i]
                    if u not in seen:
                        seen.add(u)
                        order.append((s, q, u))
        return order, hits, leaky(hits)


def claimed_dates(path):
    """{clip id: YYYY-MM-DD} from a CSV with columns clip, claimed_date."""
    return {r["clip"]: r["claimed_date"][:10] for r in csv.DictReader(open(path, newline=""))} if path else {}


def recording_claims(run, members, log=print):
    f = Path(run) / "claims.csv"
    if not f.exists():
        return []
    cited, text = withdraw.read_claims(f, log)
    return [text[c] for c, clips in cited.items() if set(clips) & set(members) and text[c]]


def trace_recording(run, rec, clips, searcher, dates, model, max_usd, judge=None, cache=None, fetcher=run_low,
                    matcher=cli.match, verifier=verify.verify, log=print):
    """trace.csv rows for one recording; candidates go to <run>/trace/<recording>/."""
    run = Path(run)
    by_id = {c["id"]: c for c in clips}
    members = [m for m in rec["members"] if m in by_id]
    clip = by_id[members[0]]
    src = Path(clip["path"]) if Path(clip["path"]).is_absolute() else run / clip["path"]
    posted = [day((by_id[m].get("source") or {}).get("posted_at")) for m in members]
    before = min([dates[m] for m in members if m in dates] or [p for p in posted if p] or [None])
    own = {((by_id[m].get("source") or {}).get("platform"), (by_id[m].get("source") or {}).get("post_id")) for m in members}

    order, hits, leaks = searcher.candidates(str(src), recording_claims(run, members, log))
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
        input_id = "input_" + clip["id"]
        link = cdir / f"{input_id}{src.suffix.lower()}"
        if not link.exists():
            link.symlink_to(src.resolve())
        for r in rows:  # candidates fetched but not kept (the input's own post) stay out of the match
            if r.get("fetch") == "same_post_as_input":
                for f in cdir.glob(f"{got[r['url']]}.*"):
                    f.unlink()
        out = work / "run"
        matcher(cdir, out, model)
        left = max(0.0, max_usd - searcher.spent)
        spent, _ = verifier(out, judge, cache, max_usd=left) if judge else (0.0, 0.0)
        searcher.spent += spent
        pairs = {r["pair_id"]: r for r in csv.DictReader(open(out / "pairs.csv", newline=""))}
        for r in fetched:
            p = pairs.get(cluster.pair_id(input_id, r["clip"]))
            if p is None:
                continue
            r.update({"band": cluster.effective_band(p), "verify_verdict": p.get("verify_verdict", ""),
                      "evidence": f"trace/{rec['id']}/run/{p['evidence']}" if p.get("evidence") else ""})
            r["confirmed"] = int(r["band"] == "merged")
            dated = r.get("platform") in PLATFORMS and day(r.get("posted_at"))
            r["earlier"] = (int(day(r["posted_at"]) < before) if before else "") if dated else ""
    shown = sorted((r for r in rows if r.get("confirmed") == 1 and r.get("earlier") == 1), key=lambda r: r["posted_at"])
    for r in rows:
        r["shown"] = int(bool(shown) and r is shown[0])
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
