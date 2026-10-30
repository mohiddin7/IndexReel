"""Phone clips carry a rotation tag; every OpenCV frame read must come out upright (ffmpeg's autorotate does this already)."""
import subprocess

import cv2
import numpy as np

from indexreel import localise, match, sscd
from test_match import write_clip


def rotated(tmp_path):
    """A 320x180 clip tagged to display rotated by 90 degrees (as an iPhone portrait clip is), plus its plain frames."""
    plain, tagged = tmp_path / "p.mp4", tmp_path / "r.mp4"
    write_clip(plain, 3, seconds=3)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-display_rotation", "90", "-i", str(plain), "-c", "copy", str(tagged)], check=True)
    cap, frames = cv2.VideoCapture(str(plain)), []
    while (r := cap.read())[0]:
        frames.append(r[1])
    return tagged, frames


def test_every_reader_gives_upright_frames(tmp_path):
    tagged, frames = rotated(tmp_path)
    up = [cv2.rotate(f, cv2.ROTATE_90_COUNTERCLOCKWISE) for f in frames]
    assert np.array_equal(sscd.frames_per_second(tagged)[0], up[5])
    assert all(np.array_equal(a, b) for a, b in zip(match.sampled_hashes(tagged), match.hashes(up[::match.SAMPLE_EVERY])))
    s = localise.sample(tagged)
    assert (s["width"], s["height"]) == (180, 320) and s["frames"][0].shape[0] > s["frames"][0].shape[1]


def test_a_cache_written_by_the_sideways_reader_is_not_reused(tmp_path, monkeypatch):
    """A cache entry under the key used before the upright reader (no reader version) must not be read back."""
    import hashlib
    import json

    from indexreel import cli
    tagged, _ = rotated(tmp_path)
    st, theta, sha = tagged.stat(), localise.THETA, "model"
    old = f"{tagged.resolve()}|{st.st_size}|{st.st_mtime_ns}|{theta}|{localise.LONG_SIDE}|{localise.RATE}|{sha}"
    cache = tmp_path / "cache"
    cache.mkdir()
    np.savez(cache / f"{hashlib.sha1(old.encode()).hexdigest()}.npz", plain=np.zeros((3, 512)), mirror=np.zeros((3, 512)),
             thumbs=np.zeros((3, 9, 16, 3)), quads=np.full((3, 4, 2), np.nan),
             meta=json.dumps({"fps": 10.0, "duration_s": 3.0, "width": 320, "height": 180}))
    monkeypatch.setattr(sscd, "embed", lambda net, frames: np.zeros((len(frames), 512), np.float32))
    meta = cli.analyse(tagged, None, theta, sha, cache)[0]
    assert (meta["width"], meta["height"]) == (180, 320)
