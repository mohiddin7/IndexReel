"""indexreel fetch: download the videos of the posts you name, with a sidecar that says where each clip came from.

  indexreel fetch --out <clips dir> <post URL or file of URLs>...

Only the URLs given are fetched (post URLs on X by default); nothing is crawled and no credentials are used. Each
clip <id>.<ext> gets <id>.source.json, which `indexreel match` copies into clips.json (eval/run-format.md).
"""
import argparse
import datetime
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

X_HOSTS = {"x.com", "www.x.com", "mobile.x.com", "twitter.com", "www.twitter.com", "mobile.twitter.com"}
MAX_URLS = 20
PLATFORM = {"twitter": "x"}
# first match wins; the text is yt-dlp's own error line, lower-cased
CODES = [("no_video", ("no video", "no media")),
         ("rate_limited", ("429", "rate limit", "too many requests")),
         ("private_or_login", ("login", "log in", "private", "protected", "sign in", "age-restricted", "authoriz", "authenticat", "nsfw")),
         ("not_found", ("404", "not found", "unavailable", "deleted", "does not exist", "suspended")),
         ("network", ("timed out", "timeout", "connection", "network", "unable to download"))]


def valid_url(url, allow_hosts=()):
    """None when the URL may be fetched, otherwise the reason it may not."""
    if re.search(r"\s", url):
        return "whitespace in the URL"
    p = urlsplit(url)
    if p.scheme != "https":
        return "only https URLs are accepted"
    if "@" in p.netloc:
        return "a URL with user information is not accepted"
    host = (p.hostname or "").lower()
    if host in X_HOSTS:
        return None if "/status/" in p.path else "only post URLs (with /status/) are accepted, not profiles or searches"
    if host in {h.lower() for h in allow_hosts}:
        return None
    return f"host {host or '?'} is not allowed (use --allow-host to add it)"


def read_urls(items):
    """Each item is a URL or a text file of URLs (one per line, # comments); order kept, duplicates dropped."""
    out = []
    for it in items:
        lines = Path(it).read_text().splitlines() if Path(it).is_file() else [it]
        for line in lines:
            line = line.strip()
            if line and not line.startswith("#") and line not in out:
                out.append(line)
    return out


def classify(message):
    low = message.lower()
    return next((code for code, words in CODES if any(w in low for w in words)), "other")


def source_from_info(info, url, now=None):
    """The few fields kept from yt-dlp's info.json; None where the post does not say."""
    stamp, day = info.get("timestamp"), info.get("upload_date")
    if stamp:
        posted = datetime.datetime.fromtimestamp(stamp, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    elif day and len(str(day)) == 8:
        posted = f"{str(day)[:4]}-{str(day)[4:6]}-{str(day)[6:]}"
    else:
        posted = None
    extractor = (info.get("extractor") or info.get("extractor_key") or "").lower()
    account = info.get("uploader_id") or info.get("channel_id")
    text = info.get("description") or info.get("title")
    now = now or datetime.datetime.now(datetime.timezone.utc)
    return {"platform": PLATFORM.get(extractor, extractor) or None, "url": info.get("webpage_url") or url,
            "post_id": str(info["id"]) if info.get("id") is not None else None,
            "account": str(account).lstrip("@") if account else None, "posted_at": posted,
            "caption": str(text)[:2000] if text else None, "fetched_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ")}


def ytdlp_cmd(url, out):
    """The yt-dlp command for one post. yt-dlp reads no netrc unless asked with --netrc."""
    return ["yt-dlp", "--ignore-config", "--no-warnings", "--no-progress", "--restrict-filenames",
            "--playlist-items", "1-4", "--max-filesize", "300M", "--write-info-json", "-f", "bv*+ba/b",
            "--merge-output-format", "mp4", "-o", str(Path(out) / "%(extractor)s_%(id)s.%(ext)s"), "--", url]


def run_ytdlp(url, out):
    """Run yt-dlp for one post; returns (exit code, the first error line of its output or '')."""
    try:
        r = subprocess.run(ytdlp_cmd(url, out), capture_output=True, text=True, timeout=900)
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, f"ERROR: {type(e).__name__}"
    # A bad option prints "yt-dlp: error: ..." (lower case), so match either case.
    err = next((ln for ln in (r.stderr + "\n" + r.stdout).splitlines() if "error" in ln.lower()), "")
    return r.returncode, err


def fetch(urls, out, run=run_ytdlp, say=print):
    """Fetch each URL into `out`; say() gets one `fetch:` line per event. Returns (ok, skipped, failed)."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    ok = skipped = failed = 0
    for url in urls:
        code, err = run(url, out)
        news = sorted(out.glob("*.info.json"))  # each one is deleted below, so these are this run's
        if not news:
            failed += 1
            reason = classify(err) if err else "no_video"
            say(f"fetch: error {url} {reason}: {(err or 'no video was downloaded').strip()[:200]}")
            continue
        for info_file in news:
            stem = info_file.name[: -len(".info.json")]
            info = json.loads(info_file.read_text())
            info_file.unlink()  # the raw info holds signed media URLs and more than we keep
            # exactly <stem>.<ext>: a leftover format part (<stem>.f251.webm) is not the video
            video = next((p for p in sorted(out.glob(stem + ".*"))
                          if p.stem == stem and not p.name.endswith((".json", ".part"))), None)
            sidecar = out / f"{stem}.source.json"
            if video is None:
                failed += 1
                say(f"fetch: error {url} {classify(err) if err else 'no_video'}: {(err or 'no video file for ' + stem).strip()[:200]}")
            elif sidecar.exists():
                skipped += 1
                say(f"fetch: skip {url} already fetched as {stem}")
            else:
                sidecar.write_text(json.dumps(source_from_info(info, url), indent=1))
                ok += 1
                say(f"fetch: ok {url} -> {video.name}")
    say(f"fetch: done {ok} ok, {skipped} skipped, {failed} failed")
    return ok, skipped, failed


def main(argv=None, run=run_ytdlp):
    ap = argparse.ArgumentParser(prog="indexreel fetch", description=__doc__.split("\n\n")[0])
    ap.add_argument("urls", nargs="+", help="post URLs, or text files with one URL per line")
    ap.add_argument("--out", required=True, help="clips directory to write into")
    ap.add_argument("--allow-host", action="append", default=[], help="allow post URLs on this host as well (repeatable)")
    a = ap.parse_args(argv)
    urls = read_urls(a.urls)
    if not urls or len(urls) > MAX_URLS:
        ap.error(f"give between 1 and {MAX_URLS} URLs")
    bad = [(u, why) for u in urls if (why := valid_url(u, a.allow_host))]
    for u, why in bad:
        print(f"fetch: error {u} bad_url: {why}")
    if bad:
        sys.exit(2)
    ok, skipped, failed = fetch(urls, a.out, run)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
