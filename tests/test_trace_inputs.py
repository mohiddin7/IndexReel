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
