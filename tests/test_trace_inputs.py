import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("trace_inputs", Path(__file__).resolve().parents[1] / "scripts" / "trace_inputs.py")
ti = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ti)


def test_kind_b_cases_get_the_edits_in_turn_in_case_order():
    rows = [{"case": c, "kind": k} for c, k in [("t3", "b"), ("t1", "b"), ("t2", "a"), ("t5", "b"), ("t4", "none"),
                                                  ("t6", "b"), ("t7", "b")]]
    assert ti.edits_for(rows) == {"t1": "flip", "t3": "slow", "t5": "zoom", "t6": "compilation", "t7": "flip"}


def test_flips_never_cancel_and_each_edit_is_in_the_filter():
    assert ti.vf("flip", False).count("hflip") == 1 and ti.vf("flip", True).count("hflip") == 1
    assert ti.vf("slow", True).count("hflip") == 1 and "setpts=2*PTS" in ti.vf("slow", False)
    assert "crop=iw*0.7:ih*0.7" in ti.vf("zoom", False) and "hflip" not in ti.vf("zoom", False)
    assert ti.vf("compilation", False) == ti.SCALE


def test_case_order_is_numeric():
    rows = [{"case": c, "kind": "b"} for c in ("t11", "t2", "t1", "t10")]
    assert list(ti.edits_for(rows)) == ["t1", "t2", "t10", "t11"]


def test_a_compilation_puts_the_copy_between_two_synthetic_fillers(tmp_path):
    import subprocess
    src = tmp_path / "src.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "mandelbrot=s=320x240:rate=25", "-t", "8", "-pix_fmt",
                    "yuv420p", str(src)], check=True)
    (tmp_path / "out").mkdir()
    row = {"case": "t1", "source": str(src), "start_s": "1", "end_s": "5", "flipped": "0"}
    out = ti.make_b(row, "compilation", tmp_path / "out", tmp_path)
    d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)],
                             capture_output=True, text=True).stdout)
    assert abs(d - (6 + 4 + 6)) < 0.5
