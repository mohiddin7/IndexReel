import shutil
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

from indexreel import geo


def make_pair(tmp_path):
    """B is moving blobs over a textured still; A = mirrored, 0.56x crop, played at 0.67x."""
    rng = np.random.default_rng(0)
    base = cv2.GaussianBlur(rng.integers(0, 255, (360, 640)).astype(np.uint8), (0, 0), 2)
    base = cv2.cvtColor(base, cv2.COLOR_GRAY2BGR)
    pa, pb = tmp_path / "a.mp4", tmp_path / "b.mp4"
    vb = cv2.VideoWriter(str(pb), cv2.VideoWriter_fourcc(*"mp4v"), 30, (640, 360))
    frames = []
    for k in range(240):
        f = base.copy()
        for s in range(6):
            x = int(320 + 250 * np.sin(0.05 * k + s)); y = int(180 + 120 * np.cos(0.031 * k * (s + 1)))
            cv2.circle(f, (x, y), 25, (255, 255, 255), -1)
        frames.append(f); vb.write(f)
    vb.release()
    va = cv2.VideoWriter(str(pa), cv2.VideoWriter_fourcc(*"mp4v"), 30, (360, 360))
    for k in range(150):
        f = frames[min(int(k * 0.67) + 40, 239)][:, 140:500][:, ::-1]
        va.write(np.ascontiguousarray(f))
    va.release()
    return pa, pb


@pytest.mark.skipif(not geo.SSCD_PATH.exists(), reason="SSCD model not in data/models")
def test_a_mirrored_cropped_slowed_copy_is_same_with_its_speed_and_offset(tmp_path):
    """The frozen self-test."""
    pa, pb = make_pair(tmp_path)
    o = geo.verify(pa, pb)
    assert o["verdict"] == "same" and o["flip"], o
    assert abs(o["slope"] - 0.67) < 0.05 and abs(o["offset_s"] - 40 / 30) < 0.3, o
    lo, hi = o["a_span_s"]  # A is 5 s long; the line maps the span inside B (8 s)
    assert 0 <= lo < hi <= 5.0 and 0 <= o["slope"] * hi + o["offset_s"] <= 8.0, o


def test_thresholds_are_the_frozen_ones():
    assert geo.THRESH == dict(reg_inliers=20, reg_share=0.6, rows_min=15, motion_min=1.5, same_support=0.5, same_z=6.0,
                              same_ncc=0.15, diff_z=3.0, diff_support=0.25)
    base = dict(reg_ok=True, motion=2.0, support=0.5, ridge_z=6.0, line_ncc=0.15, a_rows=15, flip=False, scale=1.0,
                slope=1.0, offset_s=0.0, sim_inliers=30, h_inliers=30)
    assert geo.decide(base)[0] == "same"
    assert geo.decide({**base, "support": 0.49})[0] == "cannot tell"
    assert geo.decide({**base, "support": 0.2})[0] == "different"
    assert geo.decide({**base, "support": 0.2, "a_rows": 14})[0] == "cannot tell"  # too few rows to say different
    assert geo.decide({**base, "motion": 1.4})[0] == "cannot tell"  # still scene
    assert geo.decide({**base, "reg_ok": False})[0] == "cannot tell"


@pytest.mark.skipif(not geo.SSCD_PATH.exists(), reason="SSCD model not in data/models")
def test_an_exported_copy_finds_the_model_it_is_given(tmp_path):
    """A test runs code exported to its own folder, with the model elsewhere: geo must use the path it is given,
    not one next to its own file (which in the export does not exist)."""
    shutil.copytree(Path(geo.__file__).parent, tmp_path / "code" / "src" / "indexreel")
    (tmp_path / "models").mkdir()
    model = tmp_path / "models" / "sscd.pt"
    model.symlink_to(geo.SSCD_PATH)
    pa, pb = make_pair(tmp_path)
    code = ("import sys; from indexreel import geo; assert not geo.SSCD_PATH.exists(), geo.SSCD_PATH; "
            "print(geo.verify(sys.argv[1], sys.argv[2], model=sys.argv[3])['verdict'])")
    out = subprocess.run([sys.executable, "-c", code, str(pa), str(pb), str(model)], cwd=tmp_path, capture_output=True,
                         text=True, env={"PYTHONPATH": str(tmp_path / "code" / "src"), "PATH": "/usr/bin:/bin"})
    assert out.returncode == 0 and out.stdout.strip() == "same", out.stderr[-500:]
