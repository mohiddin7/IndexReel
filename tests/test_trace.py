import csv
import json

from indexreel import cli, cluster, trace, verify


class FakeSpark:
    """Answers the queries request and the web request; counts calls."""

    def __init__(self, posts, hits=(), queries=("lava river at night",), cost=0.01):
        self.posts, self.hits, self.queries, self.cost, self.calls = posts, list(hits), list(queries), cost, []

    def ask(self, clip, text, web):
        self.calls.append("web" if web else "queries")
        if web:
            return {"posts": [{"url": u} for u in self.posts]}, self.hits, self.cost, "completed"
        return {"description": "lava", "queries": self.queries}, [], self.cost, "completed"


def fake_fetcher(posted):
    """yt-dlp stand-in: writes a clip and its info.json; posted maps URL -> (extractor, id, ISO date) or None (fails)."""
    def run(url, out):
        if posted.get(url) is None:
            return 1, "ERROR: [generic] Unable to download webpage: HTTP Error 404: Not Found"
        ex, pid, when = posted[url]
        (out / f"{ex}_{pid}.mp4").write_bytes(b"x")
        stamp = int(__import__("datetime").datetime.fromisoformat(when + "T12:00:00+00:00").timestamp())
        (out / f"{ex}_{pid}.info.json").write_text(json.dumps({"id": pid, "extractor": ex, "timestamp": stamp, "webpage_url": url}))
        return 0, ""
    return run


def fake_matcher(bands):
    """indexreel match stand-in: one pairs.csv row per clip pair, band from `bands` (candidate stem -> band), else apart."""
    def match(folder, out, model):
        ids = sorted(p.stem for p in folder.iterdir() if p.suffix == ".mp4")
        out.mkdir(parents=True, exist_ok=True)
        with open(out / "pairs.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cli.PAIR_COLUMNS, restval="")
            w.writeheader()
            for i, a in enumerate(ids):
                for b in ids[i + 1:]:
                    other = b if a.startswith("input_") else a
                    w.writerow({"pair_id": cluster.pair_id(a, b), "a": a, "b": b, "band": bands.get(other, "apart"),
                                "evidence": f"frames/{cluster.pair_id(a, b)}.jpg"})
    return match


def run_dir(tmp_path, source=None):
    run = tmp_path / "run"
    run.mkdir()
    (tmp_path / "v.mp4").write_bytes(b"viral")
    clip = {"id": "viral", "path": str(tmp_path / "v.mp4"), **({"source": source} if source else {})}
    (run / "clips.json").write_text(json.dumps({"version": 1, "clips": [clip]}))
    with open(run / "pairs.csv", "w", newline="") as f:
        csv.writer(f).writerow(cli.PAIR_COLUMNS)
    with open(run / "claims.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerows([["clip", "claim_id", "claim_text", "quote", "status"],
                     ["viral", "c1", "Shows the Semeru eruption.", "Semeru", "approved"],
                     ["viral", "c2", "Filmed today.", "today", "rejected"]])
    return run


CH = {}
YT = {"lava river at night": ["https://www.youtube.com/watch?v=old", "https://www.youtube.com/watch?v=late"]}


def go(tmp_path, spark, posted, bands, dates=None, source=None, max_usd=1.0, hits=None):
    run = run_dir(tmp_path, source)
    s = trace.Searcher(spark, verify.Cache(tmp_path / "cache"), search=lambda q, n, h=None: YT.get(q, []) if h is None else CH.get(q, []), max_usd=max_usd,
                       log=lambda *_: None)
    rows = trace.trace(run, s, model=None, dates=dates or {"viral": "2021-12-05"}, log=lambda *_: None,
                       fetcher=fake_fetcher(posted), matcher=fake_matcher(bands))
    return run, s, rows


def test_excluded_sites_and_sections():
    assert trace.excluded("https://factcheck.afp.com/doc.afp.com.9U673E") and trace.excluded("https://afp.com")
    assert trace.excluded("https://www.reuters.com/fact-check/x") and not trace.excluded("https://www.reuters.com/world/x")
    assert trace.excluded("https://www.dw.com/en/fact-check-x/a-1") and not trace.excluded("https://www.dw.com/en/news/a-1")
    assert trace.excluded("https://www.bbc.com/news/articles/x", "BBC Verify: old video") and not trace.excluded("https://www.bbc.com/news/x")
    assert trace.excluded("https://web.archive.org/web/2020/https://youtube.com/watch?v=a")
    assert not trace.excluded("https://www.youtube.com/watch?v=a") and not trace.excluded("https://notafp.com/x")
    assert trace.leaky([{"url": "https://example.com/a", "title": "Video misrepresented as Semeru"},
                        {"url": "https://example.com/b", "title": "Kilauea firehose flow"}]) == [
        {"url": "https://example.com/a", "title": "Video misrepresented as Semeru"}]


def test_post_urls_only_from_platforms():
    assert trace.post_url("https://www.youtube.com/watch?v=a") and trace.post_url("https://x.com/a/status/1")
    assert trace.post_url("https://x.com/a") is None  # a profile, not a post
    assert trace.post_url("https://www.usgs.gov/media/videos/x") is None  # an article page, dated by its text only
    assert trace.post_url("https://www.youtube.com.evil.example/watch?v=a") is None


def test_earliest_confirmed_earlier_copy_is_shown_and_later_or_undated_ones_are_not(tmp_path):
    web = ["https://factcheck.afp.com/doc.afp.com.9U673E", "https://x.com/u/status/9", "https://www.usgs.gov/v"]
    posted = {"https://x.com/u/status/9": ("twitter", "9", "2017-01-28"),
              "https://www.youtube.com/watch?v=old": ("youtube", "old", "2017-02-02"),
              "https://www.youtube.com/watch?v=late": ("youtube", "late", "2022-01-01")}
    bands = {"twitter_9": "merged", "youtube_old": "merged", "youtube_late": "merged"}
    run, s, rows = go(tmp_path, FakeSpark(web), posted, bands)
    by = {r["url"]: r for r in rows}
    assert by[web[0]]["fetch"] == "excluded" and by[web[2]]["fetch"] == "not_a_post"
    assert by["https://x.com/u/status/9"]["platform"] == "x" and by["https://x.com/u/status/9"]["earlier"] == 1
    assert by["https://www.youtube.com/watch?v=late"]["earlier"] == 0  # a later upload is never shown
    assert [r["url"] for r in rows if r["shown"] == 1] == ["https://x.com/u/status/9"]
    assert by["https://x.com/u/status/9"]["evidence"].startswith("trace/r1/pairs/twitter_9/run/frames/")
    out = list(csv.DictReader(open(run / "trace.csv", newline="")))
    assert list(out[0]) == trace.COLUMNS and len(out) == len(rows)


def test_a_later_or_undated_copy_alone_is_never_shown(tmp_path):
    posted = {"https://www.youtube.com/watch?v=late": ("youtube", "late", "2022-01-01"),
              "https://www.facebook.com/watch/?v=7": ("generic", "7", "2016-01-01")}  # a page date, not the platform's
    _, _, rows = go(tmp_path, FakeSpark(["https://www.facebook.com/watch/?v=7"]), posted,
                    {"youtube_late": "merged", "generic_7": "merged"})
    assert {r["url"] for r in rows if r.get("confirmed") == 1} == set(posted)
    assert not any(r["shown"] for r in rows)
    assert next(r for r in rows if r["url"].endswith("v=7"))["earlier"] == ""


def test_an_unconfirmed_candidate_is_never_shown(tmp_path):
    posted = {"https://www.youtube.com/watch?v=old": ("youtube", "old", "2017-02-02"),
              "https://www.youtube.com/watch?v=late": ("youtube", "late", "2022-01-01")}
    _, _, rows = go(tmp_path, FakeSpark([]), posted, {"youtube_old": "unresolved"})
    assert not any(r["shown"] for r in rows) and {r["confirmed"] for r in rows if r.get("clip")} == {0}


def test_only_approved_claims_reach_spark(tmp_path):
    spark = FakeSpark([])
    seen = []
    orig = spark.ask
    spark.ask = lambda clip, text, web: (seen.append(text), orig(clip, text, web))[1]
    go(tmp_path, spark, {}, {})
    assert all("Semeru" in t and "Filmed today" not in t for t in seen)


def test_the_inputs_own_post_is_not_a_copy(tmp_path):
    src = {"platform": "youtube", "post_id": "late", "posted_at": "2022-01-01T00:00:00Z"}
    posted = {"https://www.youtube.com/watch?v=late": ("youtube", "late", "2022-01-01")}
    _, _, rows = go(tmp_path, FakeSpark([]), posted, {"youtube_late": "merged"}, source=src)
    late = next(r for r in rows if r["url"].endswith("late"))
    assert late["fetch"] == "same_post_as_input" and not late.get("confirmed")


def test_leak_exposed_when_search_read_a_fact_check(tmp_path):
    hits = [{"title": "Old video falsely shared as Semeru eruption", "url": "https://example.com/news"}]
    run, _, rows = go(tmp_path, FakeSpark([], hits=hits), {}, {})
    assert {r["leak_exposed"] for r in rows} == {1}
    assert json.loads((run / "trace" / "r1" / "search_hits.json").read_text())["leak_exposed"] == hits


def test_candidates_are_capped_and_a_rerun_is_free(tmp_path):
    web = [f"https://x.com/u/status/{i}" for i in range(20)]
    spark = FakeSpark(web)
    _, _, rows = go(tmp_path, spark, {}, {})
    assert sum(r["fetch"] == "over_cap" for r in rows) == len(rows) - trace.MAX_CANDIDATES
    assert rows[0]["source"] == "web" and rows[1]["source"] == "youtube"  # the sources alternate
    n = len(spark.calls)
    s = trace.Searcher(spark, verify.Cache(tmp_path / "cache"), search=lambda q, n, h=None: YT.get(q, []) if h is None else CH.get(q, []), log=lambda *_: None)
    s.candidates(str(tmp_path / "v.mp4"), ["Shows the Semeru eruption."])
    assert len(spark.calls) == n and s.spent == 0.0


def test_no_request_beyond_the_budget(tmp_path):
    spark = FakeSpark(["https://x.com/u/status/1"])
    _, s, rows = go(tmp_path, spark, {}, {}, max_usd=0.05)
    assert spark.calls == ["queries"] and s.spent <= 0.05  # the web request's guard did not fit


def test_a_long_candidate_is_cut_around_the_stretch_that_matches_the_input(tmp_path):
    import subprocess
    import pytest
    if not cli.MODEL.exists():
        pytest.skip("SSCD model not present")
    (tmp_path / "c").mkdir()
    (tmp_path / "w").mkdir()
    long, clip = tmp_path / "c" / "youtube_long.mp4", tmp_path / "input.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "mandelbrot=s=320x240:rate=5", "-t", "120", "-pix_fmt",
                    "yuv420p", str(long)], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-ss", "60", "-to", "70", "-i", str(long), "-vf", "hflip", str(clip)], check=True)
    rows = [{"clip": "youtube_long"}, {"clip": ""}]
    trace.narrow(cli.MODEL, clip, tmp_path / "c", tmp_path / "w", rows, log=lambda *_: None)
    r = rows[0]
    assert r["duration_s"] == 120.0 and r["cut_start_s"] <= 60 and r["cut_end_s"] >= 70
    assert r["cut_end_s"] - r["cut_start_s"] <= 2 * 10 + 2 * trace.MARGIN  # the stretch may start anywhere in the input
    assert (tmp_path / "w" / "full" / "youtube_long.mp4").exists() and trace.duration(long) < 60
    rows2 = [{"clip": "youtube_long"}]
    trace.narrow(cli.MODEL, clip, tmp_path / "c", tmp_path / "w", rows2, log=lambda *_: None)  # a rerun keeps the cut
    assert rows2[0]["cut_start_s"] == r["cut_start_s"] and trace.duration(long) < 60


def test_a_named_channel_is_searched_and_comes_before_global_search(tmp_path):
    CH["lava river at night"] = ["https://www.youtube.com/watch?v=official"]
    (tmp_path / "v.mp4").write_bytes(b"viral")
    try:
        spark = FakeSpark([])
        orig = spark.ask
        spark.ask = lambda clip, text, web: orig(clip, text, web) if web else (
            {"queries": ["lava river at night"], "handle": "@USGS"}, [], 0.01, "completed")
        s = trace.Searcher(spark, verify.Cache(tmp_path / "cache"), search=lambda q, n, h=None: YT.get(q, []) if h is None else CH.get(q, []) if h == "@USGS" else [],
                           log=lambda *_: None)
        order, _, _ = s.candidates(str(tmp_path / "v.mp4"), [])
        assert order[0] == ("channel", "lava river at night", "https://www.youtube.com/watch?v=official")
        assert [u for _, _, u in order[1:]] == YT["lava river at night"]
        spark.ask = lambda clip, text, web: orig(clip, text, web) if web else (
            {"queries": ["lava river at night"], "handle": "@x/../evil"}, [], 0.01, "completed")
        s2 = trace.Searcher(spark, verify.Cache(tmp_path / "cache2"), search=lambda q, n, h=None: [] if h else YT.get(q, []), log=lambda *_: None)
        assert all(src != "channel" for src, _, _ in s2.candidates(str(tmp_path / "v.mp4"), [])[0])  # a bad handle is ignored
    finally:
        CH.clear()


def test_core_evidence_shows_three_rows_from_inside_the_core_span(tmp_path):
    import subprocess
    import cv2
    v = tmp_path / "v.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "mandelbrot=s=320x180:rate=5", "-t", "12", "-pix_fmt",
                    "yuv420p", str(v)], check=True)
    pdir = tmp_path / "pair"
    pdir.mkdir()
    for name in ("input_x.mp4", "youtube_y.mp4"):
        (pdir / name).symlink_to(v)
    p = {"a": "input_x", "b": "youtube_y", "core_a_start_s": "2", "core_a_end_s": "8", "offset_s": "1", "mirrored": "0"}
    assert trace.core_evidence(pdir, p, tmp_path / "out" / "core.jpg")
    assert cv2.imread(str(tmp_path / "out" / "core.jpg")).shape[:2] == (3 * cli.THUMB[1], 2 * cli.THUMB[0])
    assert not trace.core_evidence(pdir, {**p, "core_a_start_s": ""}, tmp_path / "none.jpg")
