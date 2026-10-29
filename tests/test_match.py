from pathlib import Path

import cv2
import numpy as np
import pytest

from indexreel import cli, cluster, localise

MODEL = cli.MODEL


def write_clip(path, seed, seconds=6, fps=10, screen=False):
    rng = np.random.default_rng(seed)
    pos = rng.uniform(40, 200, (6, 2))
    vel = rng.uniform(-6, 6, (6, 2))
    col = rng.integers(60, 255, (6, 3))
    base = np.clip(rng.normal(60, 25, (180, 320, 3)), 0, 255).astype(np.uint8)
    w = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (320, 180))
    for _ in range(seconds * fps):
        f = base.copy()
        for p, c in zip(pos, col):
            cv2.circle(f, (int(p[0]) % 320, int(p[1]) % 180), 18, tuple(int(x) for x in c), -1)
        if screen:
            cv2.rectangle(f, (60, 30), (260, 150), (220, 220, 220), 3)
        w.write(f)
        pos += vel
    w.release()


def test_sample_gives_one_frame_per_second(tmp_path):
    write_clip(tmp_path / "c.mp4", 1, seconds=6)
    s = localise.sample(tmp_path / "c.mp4")
    assert len(s["frames"]) == len(s["quads"]) == 6
    assert abs(s["duration_s"] - 6) < 0.2 and (s["width"], s["height"]) == (320, 180)


def test_sample_rectifies_a_framed_screen(tmp_path):
    write_clip(tmp_path / "s.mp4", 2, screen=True)
    s = localise.sample(tmp_path / "s.mp4")
    found = [q for q in s["quads"] if q is not None]
    assert found and localise.median_quad(s["quads"]) is not None
    assert all(f.shape == (360, 640, 3) for f, q in zip(s["frames"], s["quads"]) if q is not None)


@pytest.mark.skipif(not Path(MODEL).exists(), reason="SSCD model not in data/models")
def test_match_writes_a_run_that_follows_the_format(tmp_path):
    clips = tmp_path / "clips"
    clips.mkdir()
    write_clip(clips / "a.mp4", 3)
    write_clip(clips / "a_copy.mp4", 3)  # same frames written again
    write_clip(clips / "b.mp4", 4)
    rows, rec = cli.match(clips, tmp_path / "run", MODEL)
    assert list(rows[0]) == cli.PAIR_COLUMNS and len(rows) == 3
    by = {r["pair_id"]: r for r in rows}
    assert by["a~a_copy"]["band"] == "merged" and by["a~a_copy"]["aligned"] > 0.9
    assert by["a~a_copy"]["cover_a"] == by["a~a_copy"]["cover_b"] == 1.0  # a full copy covers both clips
    assert float(by["a~b"]["aligned"]) < float(by["a~a_copy"]["aligned"])
    for r in rows:
        assert r["b_start_s"] == r["a_start_s"] + r["offset_s"]
        assert bool(r["evidence"]) == (r["band"] != "apart") and (not r["evidence"] or (tmp_path / "run" / r["evidence"]).exists())
    assert rec == cluster.recordings(["a", "a_copy", "b"], [(r["pair_id"], r["a"], r["b"], r["band"]) for r in rows])
    assert (tmp_path / "run" / "audit.jsonl").read_text() == ""


@pytest.mark.skipif(not Path(MODEL).exists(), reason="SSCD model not in data/models")
def test_one_clip_makes_a_run_with_no_pairs_and_one_recording(tmp_path):
    clips = tmp_path / "clips"
    clips.mkdir()
    write_clip(clips / "a.mp4", 3)
    rows, rec = cli.match(clips, tmp_path / "run", MODEL)
    assert rows == [] and rec == cluster.recordings(["a"], [])
    assert (tmp_path / "run" / "pairs.csv").read_text().strip() == ",".join(cli.PAIR_COLUMNS)


def test_an_empty_folder_is_refused(tmp_path):
    with pytest.raises(SystemExit, match="no clips"):
        cli.find_clips(tmp_path)


@pytest.mark.skipif(not Path(MODEL).exists(), reason="SSCD model not in data/models")
def test_second_run_reads_the_cache(tmp_path, monkeypatch):
    clips = tmp_path / "clips"
    clips.mkdir()
    write_clip(clips / "a.mp4", 5)
    write_clip(clips / "b.mp4", 6)
    first, _ = cli.match(clips, tmp_path / "run1", MODEL, cache=tmp_path / "cache")
    monkeypatch.setattr(localise, "sample", lambda *a, **k: pytest.fail("decoded again"))
    second, _ = cli.match(clips, tmp_path / "run2", MODEL, cache=tmp_path / "cache")
    assert first == second
    assert (tmp_path / "run1" / "frames").exists() and len(list((tmp_path / "cache").glob("*.npz"))) == 2


@pytest.mark.parametrize("stage", ["verify", "withdraw", "wall"])
def test_stages_are_reachable_from_the_entry_point(stage, capsys):
    with pytest.raises(SystemExit) as e:
        cli.main([stage, "--help"])
    assert e.value.code == 0 and "run" in capsys.readouterr().out


def test_evidence_labels_name_posts_by_place_and_shorten_long_ids():
    assert cli.label({"id": "twitter_2115522805395542016", "source": {"platform": "x"}}, 5) == "post 5"
    assert cli.label({"id": "N01__refilm_sim"}, 3) == "N01__refilm_sim"  # short ids stay, so dev images do not change
    assert cli.label({"id": "devgate_refilm_A_bezel_b01_T"}, 1) == "devgate_re..ezel_b01_T"
