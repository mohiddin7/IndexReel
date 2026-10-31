import json
import shutil
from pathlib import Path

import cv2
import numpy as np
import pytest

from indexreel import cli, fetch

INFO = Path(__file__).parent / "fixtures" / "ytdlp_x_post.info.json"
URL = "https://x.com/example_account/status/1234567890123456789"


def fake_ytdlp(url, out):
    """Stands in for yt-dlp: writes what it writes for a one-video post, with no network."""
    w = cv2.VideoWriter(str(Path(out) / "twitter_1234567890123456789.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), 5, (32, 24))
    for _ in range(5):
        w.write(np.zeros((24, 32, 3), np.uint8))
    w.release()
    shutil.copy(INFO, Path(out) / "twitter_1234567890123456789.info.json")
    return 0, ""


def test_source_keeps_only_what_a_post_says():
    s = fetch.source_from_info(json.loads(INFO.read_text()), URL)
    assert s["platform"] == "x" and s["account"] == "example_account" and s["post_id"] == "1234567890123456789"
    assert s["posted_at"] == "2026-10-27T11:00:00Z" and s["caption"].startswith("Two angles") and s["url"] == URL
    assert set(s) == {"platform", "url", "post_id", "account", "posted_at", "caption", "fetched_utc"}
    assert "SECRET" not in json.dumps(s)


def test_source_with_missing_fields_has_nulls():
    s = fetch.source_from_info({"id": 7, "extractor": "tiktok", "upload_date": "20261027"}, "https://example.com/v/7")
    assert s["platform"] == "tiktok" and s["posted_at"] == "2026-10-27" and s["account"] is None and s["caption"] is None


@pytest.mark.parametrize("url,ok", [
    (URL, True), ("https://twitter.com/example_account/status/1", True), ("https://mobile.twitter.com/a/status/1", True),
    ("http://x.com/a/status/1", False), ("https://x.com/example_account", False), ("https://x.com/search?q=a", False),
    ("https://user@x.com/a/status/1", False), ("https://example.com/a/status/1", False), ("file:///etc/passwd", False),
    ("https://x.com/a/status/1 --exec", False)])
def test_only_post_urls_on_x_are_accepted(url, ok):
    assert (fetch.valid_url(url) is None) == ok


def test_another_host_needs_an_explicit_allowance():
    assert fetch.valid_url("https://example.com/v/1") is not None
    assert fetch.valid_url("https://example.com/v/1", ["example.com"]) is None


def test_urls_come_from_arguments_and_files_without_duplicates(tmp_path):
    f = tmp_path / "urls.txt"
    f.write_text(f"# test posts\n{URL}\n\nhttps://x.com/b/status/2\n")
    assert fetch.read_urls([str(f), URL, "https://x.com/c/status/3"]) == [URL, "https://x.com/b/status/2", "https://x.com/c/status/3"]


@pytest.mark.parametrize("message,code", [
    ("ERROR: [twitter] 1: No video could be found in this tweet", "no_video"),
    ("ERROR: HTTP Error 429: Too Many Requests", "rate_limited"),
    ("ERROR: [twitter] 1: NSFW tweet requires authentication", "private_or_login"),
    ("ERROR: [twitter] 1: Tweet is protected, log in", "private_or_login"),
    ("ERROR: [twitter] 1: Requested tweet is unavailable", "not_found"),
    ("ERROR: Unable to download webpage: timed out", "network"),
    ("ERROR: something else", "other")])
def test_errors_get_a_stable_code(message, code):
    assert fetch.classify(message) == code


def test_fetch_writes_a_clip_and_a_sidecar_and_never_overwrites(tmp_path):
    lines = []
    assert fetch.fetch([URL], tmp_path / "clips", fake_ytdlp, lines.append) == (1, 0, 0)
    assert lines[0] == f"fetch: ok {URL} -> twitter_1234567890123456789.mp4" and lines[-1] == "fetch: done 1 ok, 0 skipped, 0 failed"
    out = tmp_path / "clips"
    sidecar = out / "twitter_1234567890123456789.source.json"
    first = sidecar.read_text()
    assert not list(out.glob("*.info.json"))  # the raw info with signed URLs is gone
    assert "SECRET" not in first
    lines.clear()
    assert fetch.fetch([URL], out, fake_ytdlp, lines.append) == (0, 1, 0)
    assert lines[0].startswith("fetch: skip") and sidecar.read_text() == first


def test_a_failed_post_is_reported_with_its_code_and_the_others_go_on(tmp_path):
    def run(url, out):
        return (1, "ERROR: [twitter] 9: Requested tweet is unavailable") if url.endswith("/9") else fake_ytdlp(url, out)
    lines = []
    assert fetch.fetch(["https://x.com/a/status/9", URL], tmp_path, run, lines.append) == (1, 0, 1)
    assert lines[0] == "fetch: error https://x.com/a/status/9 not_found: ERROR: [twitter] 9: Requested tweet is unavailable"


def test_a_leftover_format_part_is_not_taken_as_the_video(tmp_path):
    def run(url, out):  # yt-dlp stopped before the merge: one audio part and the info are left
        (Path(out) / "twitter_1234567890123456789.f251.webm").write_bytes(b"x" * 2700)
        shutil.copy(INFO, Path(out) / "twitter_1234567890123456789.info.json")
        return 0, ""
    lines = []
    assert fetch.fetch([URL], tmp_path, run, lines.append) == (0, 0, 1)
    assert not any(ln.startswith("fetch: ok") for ln in lines)
    assert not (tmp_path / "twitter_1234567890123456789.source.json").exists()


def test_main_exit_codes(tmp_path, capsys):
    with pytest.raises(SystemExit) as e:
        fetch.main(["--out", str(tmp_path), "https://x.com/someone"], run=fake_ytdlp)
    assert e.value.code == 2 and "bad_url" in capsys.readouterr().out and not list(tmp_path.iterdir())
    with pytest.raises(SystemExit) as e:
        fetch.main(["--out", str(tmp_path), URL], run=fake_ytdlp)
    assert e.value.code == 0
    with pytest.raises(SystemExit) as e:
        fetch.main(["--out", str(tmp_path), "https://x.com/a/status/9"], run=lambda u, o: (1, "ERROR: unavailable"))
    assert e.value.code == 1


def test_match_reads_the_sidecar_next_to_a_clip(tmp_path):
    fetch.fetch([URL], tmp_path, fake_ytdlp, lambda _: None)
    assert cli.load_source(tmp_path / "twitter_1234567890123456789.mp4")["account"] == "example_account"
    assert cli.load_source(tmp_path / "local_file.mp4") is None


@pytest.mark.skipif(shutil.which("yt-dlp") is None, reason="yt-dlp not installed")
def test_every_option_we_pass_exists_in_the_installed_ytdlp():
    import subprocess
    helptext = subprocess.run(["yt-dlp", "--help"], capture_output=True, text=True).stdout
    opts = [a for a in fetch.ytdlp_cmd(URL, "out") if a.startswith("--") and a != "--"]
    assert [o for o in opts if o not in helptext] == []
