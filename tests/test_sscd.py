import cv2
import numpy as np
import pytest

from indexreel import sscd


def unit(rows):
    a = np.asarray(rows, np.float32)
    return a / np.linalg.norm(a, axis=1, keepdims=True)


def test_score_is_one_for_the_same_clip_and_ignores_order():
    a = (unit([[1, 0, 0], [0, 1, 0]]), unit([[1, 0, 0], [0, 0, 1]]))
    b = (unit([[0, 0, 1], [1, 1, 0]]), unit([[0, 1, 0], [1, 0, 1]]))
    assert abs(sscd.score(a, a) - 1) < 1e-6
    assert abs(sscd.score(a, b) - sscd.score(b, a)) < 1e-6


def test_score_finds_a_mirrored_copy_and_not_an_unrelated_clip():
    plain = unit([[1, 0, 0, 0], [0, 1, 0, 0]])
    mirror = unit([[0, 0, 1, 0], [0, 0, 0, 1]])
    original = (plain, mirror)
    flipped_copy = (mirror, plain)  # what the same clip looks like after a left-right flip
    other = (unit([[1, 1, 1, 1], [1, -1, 1, -1]]), unit([[1, 1, -1, -1], [-1, 1, 1, -1]]))
    assert sscd.score(original, flipped_copy) > 0.99
    assert sscd.score(original, other) < 0.8


def test_one_frame_per_second(tmp_path):
    path = str(tmp_path / "t.mp4")
    w = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), 10, (64, 48))
    for i in range(35):  # 3.5 s at 10 fps
        w.write(np.full((48, 64, 3), i * 7, np.uint8))
    w.release()
    fr = sscd.frames_per_second(path)
    assert len(fr) == 3  # frames 5, 15 and 25; the one at 3.5 s would be frame 35, which does not exist
    assert [f.mean() for f in fr] == [pytest.approx(v, abs=6) for v in (35, 105, 175)]


def test_aligned_score_needs_the_frames_in_the_same_order():
    rng = np.random.default_rng(0)
    frames = unit(rng.normal(size=(10, 32)))
    noise = unit(rng.normal(size=(10, 32)))
    original = (frames, noise)
    shuffled = (frames[rng.permutation(10)], noise)
    trimmed = (frames[3:], noise[3:])  # a clip that starts 3 s in
    assert sscd.aligned_score(original, original) > 0.99
    assert sscd.aligned_score(original, trimmed) > 0.99
    assert sscd.score(original, shuffled) > 0.99  # best-match score cannot tell the order is gone
    assert sscd.aligned_score(original, shuffled) < 0.5
