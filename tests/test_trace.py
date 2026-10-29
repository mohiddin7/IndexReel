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
    run.mkdir(parents=True)
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
    assert trace.post_url("https://www.youtube.com/results?search_query=lava") is None
    assert trace.post_url("https://www.youtube.com/playlist?list=PL1") is None and trace.post_url("https://www.youtube.com/@USGS") is None
    assert trace.post_url("https://www.youtube.com/shorts/abc") and trace.post_url("https://youtu.be/abc")


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


def test_no_claim_reaches_the_search(tmp_path):
    spark = FakeSpark([])
    seen = []
    orig = spark.ask
    spark.ask = lambda clip, text, web: (seen.append(text), orig(clip, text, web))[1]
    go(tmp_path, spark, {}, {})
    assert len(seen) == 2 and all("Semeru" not in t and "today" not in t for t in seen)


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
    assert {r["source"]: r["leak_copy"] for r in rows} == {"youtube": 0}  # only YouTube candidates here: none fails
    assert {r["claimed_date"] for r in rows} == {"2021-12-05"}
    assert json.loads((run / "trace" / "r1" / "search_hits.json").read_text())["leak_exposed"] == hits


def test_candidates_are_capped_and_a_rerun_is_free(tmp_path):
    web = [f"https://x.com/u/status/{i}" for i in range(20)]
    spark = FakeSpark(web)
    _, _, rows = go(tmp_path, spark, {}, {})
    assert sum(r["fetch"] == "over_cap" for r in rows) == len(rows) - trace.MAX_CANDIDATES
    assert rows[0]["source"] == "web" and rows[1]["source"] == "youtube"  # the sources alternate
    n = len(spark.calls)
    s = trace.Searcher(spark, verify.Cache(tmp_path / "cache"), search=lambda q, n, h=None: YT.get(q, []) if h is None else CH.get(q, []), log=lambda *_: None)
    s.candidates(str(tmp_path / "v.mp4"))
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
        order, _, _ = s.candidates(str(tmp_path / "v.mp4"))
        assert order[0] == ("channel", "lava river at night", "https://www.youtube.com/watch?v=official")
        assert [u for _, _, u in order[1:]] == YT["lava river at night"]
        spark.ask = lambda clip, text, web: orig(clip, text, web) if web else (
            {"queries": ["lava river at night"], "handle": "@x/../evil"}, [], 0.01, "completed")
        s2 = trace.Searcher(spark, verify.Cache(tmp_path / "cache2"), search=lambda q, n, h=None: [] if h else YT.get(q, []), log=lambda *_: None)
        assert all(src != "channel" for src, _, _ in s2.candidates(str(tmp_path / "v.mp4"))[0])  # a bad handle is ignored
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


def test_a_post_found_by_several_sources_lists_them_all(tmp_path):
    (tmp_path / "v.mp4").write_bytes(b"viral")
    s = trace.Searcher(FakeSpark(["https://www.youtube.com/watch?v=old"]), verify.Cache(tmp_path / "cache"),
                       search=lambda q, n, h=None: [] if h else YT.get(q, []), log=lambda *_: None)
    order, _, _ = s.candidates(str(tmp_path / "v.mp4"))
    assert order[0] == ("web+youtube", "lava river at night", "https://www.youtube.com/watch?v=old")
    assert [u for _, _, u in order].count("https://www.youtube.com/watch?v=old") == 1


def test_a_copy_found_only_by_a_leaky_web_search_is_marked(tmp_path):
    hits = [{"title": "Fact check: old lava video", "url": "https://example.com/a"}]
    _, _, rows = go(tmp_path, FakeSpark(["https://x.com/u/status/9", "https://www.youtube.com/watch?v=old"], hits=hits), {}, {})
    by = {r["url"]: r for r in rows}
    assert by["https://x.com/u/status/9"]["leak_copy"] == 1
    assert set(by["https://www.youtube.com/watch?v=old"]["source"].split("+")) == {"web", "youtube"}
    assert by["https://www.youtube.com/watch?v=old"]["leak_copy"] == 0  # YouTube search found it too


class FakeGoogle:
    def __init__(self, videos=(), pages=(), stop=None):
        self.v, self.p, self.stop, self.calls = list(videos), list(pages), stop, []

    def videos(self, q, before, n):
        self.calls.append(("videos", before))
        if self.stop:
            raise trace.GoogleStop(self.stop)
        return self.v

    def pages(self, jpegs):
        self.calls.append(("pages",))
        return self.p

    def video_info(self, ids):
        return {}


def searcher(tmp_path, spark, **kw):
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "v.mp4").write_bytes(b"viral")
    return trace.Searcher(spark, verify.Cache(tmp_path / "cache"), search=lambda q, n, h=None: [] if h else YT.get(q, []),
                          log=kw.pop("log", lambda *_: None), **kw)


def test_posts_dated_on_or_after_the_claim_or_too_long_are_not_fetched(tmp_path):
    meta = {"https://www.youtube.com/watch?v=old": {"day": "2017-02-02", "duration": 60},
            "https://www.youtube.com/watch?v=late": {"day": "2021-12-05", "duration": 60},
            "https://x.com/u/status/9": {"day": "2017-01-01", "duration": 4000}}
    s = searcher(tmp_path, FakeSpark(["https://x.com/u/status/9"]), meta=lambda u: meta[u])
    s.candidates(str(tmp_path / "v.mp4"), "2021-12-05")
    assert s.notes["https://www.youtube.com/watch?v=late"] == "after_claim"  # the claimed day itself is not earlier
    assert s.notes["https://x.com/u/status/9"] == "too_long" and "https://www.youtube.com/watch?v=old" not in s.notes
    _, _, rows = go(tmp_path / "g", FakeSpark([]), {"https://www.youtube.com/watch?v=old": ("youtube", "old", "2017-02-02")}, {})
    assert not any(r["fetch"] in ("after_claim", "too_long") for r in rows)  # without a meta reader nothing is skipped


def test_prerank_orders_youtube_results_and_keeps_other_posts_ahead(tmp_path):
    class Thumbs:
        def scores(self, clip, ids):
            return {"old": 0.2, "late": 0.9}
    s = searcher(tmp_path, FakeSpark(["https://x.com/u/status/9"]), thumbs=Thumbs())
    order, _, _ = s.candidates(str(tmp_path / "v.mp4"))
    assert [u for _, _, u in order] == ["https://x.com/u/status/9", "https://www.youtube.com/watch?v=late",
                                        "https://www.youtube.com/watch?v=old"]
    assert s.scores["https://www.youtube.com/watch?v=late"] == 0.9


def test_google_sources_and_a_leak_counted_per_source(tmp_path, monkeypatch):
    monkeypatch.setattr(trace, "keyframes", lambda clip: [b"frame"])
    g = FakeGoogle(videos=[{"url": "https://www.youtube.com/watch?v=api", "posted_at": "2015-01-01T00:00:00Z"}],
                   pages=[{"url": "https://www.tiktok.com/@a/video/1", "title": "lava"},
                          {"url": "https://factcheck.afp.com/x", "title": "Fact check"}])
    s = searcher(tmp_path, FakeSpark(["https://x.com/u/status/9"]), google=g, sources=trace.ALL_SOURCES)
    order, _, _ = s.candidates(str(tmp_path / "v.mp4"), "2021-12-05")
    src = {u: x for x, _, u in order}
    assert src["https://www.youtube.com/watch?v=api"] == "ytapi" and src["https://www.tiktok.com/@a/video/1"] == "keyframe"
    assert ("videos", "2021-12-05") in g.calls and set(s.leaks) == {"web", "keyframe"} and s.leaks["keyframe"] and not s.leaks["web"]
    s2 = searcher(tmp_path / "n", FakeSpark([]), google=g)
    s2.candidates(str(tmp_path / "n" / "v.mp4"))  # no claimed date: the date-bounded search is not made
    assert ("videos", None) not in g.calls


def test_a_google_quota_error_stops_that_source_only(tmp_path, monkeypatch):
    monkeypatch.setattr(trace, "keyframes", lambda clip: [b"frame"])
    said = []
    s = searcher(tmp_path, FakeSpark([]), google=FakeGoogle(stop="HTTP 403 quotaExceeded"), log=said.append)
    order, _, _ = s.candidates(str(tmp_path / "v.mp4"), "2021-12-05")
    assert [u for _, _, u in order] == YT["lava river at night"]
    assert any("ytapi source stopped" in m for m in said)


def test_the_api_key_never_appears_in_an_error(monkeypatch):
    import io
    import urllib.error
    import urllib.request

    def fail(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, io.BytesIO(b'{"error": {"status": "PERMISSION_DENIED"}}'))
    monkeypatch.setattr(urllib.request, "urlopen", fail)
    try:
        trace.Google("SECRET123").videos("lava", "2020-01-01")
    except trace.GoogleStop as e:
        assert "SECRET123" not in str(e) and "403" in str(e)
    else:
        raise AssertionError("no GoogleStop")


def test_strength_of_the_shown_copy(tmp_path):
    def ask_with(answer):
        spark = FakeSpark([])
        orig = spark.ask
        spark.ask = lambda clip, text, web: ((answer, [], 0.01, "completed") if "when and where" in text else orig(clip, text, web))
        return spark
    posted = {"https://www.youtube.com/watch?v=old": ("youtube", "old", "2017-02-02")}
    two_sites = {"date": "2017-01-31", "sources": [{"url": "https://www.usgs.gov/a"}, {"url": "https://www.bbc.com/b"}]}
    for answer, want in ((two_sites, "strong"), ({**two_sites, "sources": two_sites["sources"][:1]}, "single-source"),
                         ({**two_sites, "date": "2017-03-01"}, "single-source")):
        tmp_path = tmp_path / "x"
        _, _, rows = go(tmp_path, ask_with(answer), posted, {"youtube_old": "merged"})
        r = next(r for r in rows if r["shown"] == 1)
        assert r["strength"] == want and r["families"] == "youtube"
        assert r["corroborated_date"] == ("2017-01-31" if want == "strong" else "")
    tmp_path = tmp_path / "y"
    _, _, rows = go(tmp_path, ask_with({}), posted, {"youtube_old": "merged"})  # found by one family, no date
    assert next(r for r in rows if r["shown"] == 1)["strength"] == "single-source"


def test_vision_requests_stop_at_the_daily_cap_and_are_counted_on_disk(tmp_path, monkeypatch):
    monkeypatch.setattr(trace, "VISION_CAP", {"day": 2, "total": 300})
    g = trace.Google("k", counter=tmp_path / "count.json")
    monkeypatch.setattr(g, "_call", lambda url, body=None: {"responses": [{"webDetection": {"pagesWithMatchingImages": [
        {"url": "https://www.tiktok.com/@a/video/1", "pageTitle": "<b>lava</b>"}]}}]})
    assert g.pages([b"x"]) == [{"url": "https://www.tiktok.com/@a/video/1", "title": "lava"}]
    g.pages([b"x"])
    try:
        g.pages([b"x"])
    except trace.GoogleStop as e:
        assert "cap" in str(e)
    else:
        raise AssertionError("no stop at the cap")
    c = json.loads((tmp_path / "count.json").read_text())
    assert c["total"] == 2 and c["images"] == 2
    monkeypatch.setattr(trace, "keyframes", lambda clip: [b"frame"])
    said = []
    s = searcher(tmp_path / "s", FakeSpark([]), google=g, log=said.append, sources=trace.ALL_SOURCES)
    s.candidates(str(tmp_path / "s" / "v.mp4"))  # over the cap: the run goes on without the keyframe source
    assert any("keyframe source stopped" in m for m in said) and c["total"] == 2


def test_keyframe_search_is_off_by_default(tmp_path, monkeypatch):
    monkeypatch.setattr(trace, "keyframes", lambda clip: [b"frame"])
    g = FakeGoogle(pages=[{"url": "https://www.tiktok.com/@a/video/1", "title": "lava"}])
    searcher(tmp_path, FakeSpark([]), google=g).candidates(str(tmp_path / "v.mp4"), "2021-12-05")
    assert ("pages",) not in g.calls


def test_a_failed_youtube_search_is_not_cached(tmp_path):
    calls = []
    def search(q, n, h=None):
        calls.append(q)
        return None if len(calls) == 1 else YT.get(q, [])
    (tmp_path / "v.mp4").write_bytes(b"viral")
    s = trace.Searcher(FakeSpark([]), verify.Cache(tmp_path / "cache"), search=search, log=lambda *_: None)
    assert s.candidates(str(tmp_path / "v.mp4"))[0] == []
    assert [u for _, _, u in s.candidates(str(tmp_path / "v.mp4"))[0]] == YT["lava river at night"]


def test_youtube_dates_come_from_the_data_api_when_it_is_on(tmp_path, monkeypatch):
    g = trace.Google("k")
    monkeypatch.setattr(g, "_call", lambda url, body=None: {"items": [
        {"id": "old", "snippet": {"publishedAt": "2017-02-02T00:00:00Z"}, "contentDetails": {"duration": "PT1M5S"}},
        {"id": "late", "snippet": {"publishedAt": "2022-01-01T00:00:00Z"}, "contentDetails": {"duration": "PT1H0M1S"}}]})
    assert g.video_info(["old", "late"]) == {"old": {"day": "2017-02-02", "duration": 65}, "late": {"day": "2022-01-01", "duration": 3601}}
    monkeypatch.setattr(g, "videos", lambda q, before, n: [])
    metas = []
    s = searcher(tmp_path, FakeSpark([]), google=g, meta=lambda u: metas.append(u) or {})
    s.candidates(str(tmp_path / "v.mp4"), "2021-12-05")
    assert s.notes["https://www.youtube.com/watch?v=late"] == "too_long" and "https://www.youtube.com/watch?v=old" not in s.notes
    assert metas == []  # no yt-dlp request for a date the API gave


def test_evidence_follows_a_slowed_input(tmp_path):
    import subprocess
    import pytest
    if not cli.MODEL.exists():
        pytest.skip("SSCD model not present")
    orig, slow = tmp_path / "o.mp4", tmp_path / "s.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "mandelbrot=s=320x240:rate=10", "-t", "20", "-pix_fmt",
                    "yuv420p", str(orig)], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-ss", "4", "-to", "12", "-i", str(orig), "-vf", "setpts=2*PTS", str(slow)], check=True)
    frames = [trace.frame_at(slow, t) for t in (1.0, 8.0, 15.0)]
    got = trace.best_match_times(cli.MODEL, frames, orig, 4.0, 12.0)
    assert [abs(g - (4 + t / 2)) <= 0.5 for g, t in zip(got, (1.0, 8.0, 15.0))] == [True] * 3  # an offset alone would drift
