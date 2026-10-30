import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location("second_look", Path(__file__).resolve().parents[1] / "scripts" / "second_look.py")
sl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sl)


def test_same_needs_two_anchors_and_only_edit_made_differences():
    a = [{"what": "fallen palm"}, {"what": "beige tower"}]
    assert sl.decide({"same_footage": "yes", "anchors": a, "differences": [{"edit_made": "yes"}]}) == "same"
    assert sl.decide({"same_footage": "yes", "anchors": a, "differences": [{"edit_made": "yes"}, {"edit_made": "no"}]}) == "different"
    assert sl.decide({"same_footage": "yes", "anchors": a[:1], "differences": []}) == "abstain"  # one anchor is not enough
    assert sl.decide({"same_footage": "yes", "anchors": a, "differences": [{"edit_made": "unsure"}]}) == "abstain"
    assert sl.decide({"same_footage": "no", "anchors": a, "differences": []}) == "different"
    assert sl.decide(None) == "abstain"


def test_aligned_times_follow_the_core_span_and_the_offset():
    p = {"core_a_start_s": "0", "core_a_end_s": "6", "offset_s": "19"}
    assert [(round(a, 2), round(b, 2)) for a, b in sl.aligned_times(p)] == [(1.0, 20.0), (3.0, 22.0), (5.0, 24.0)]
    assert sl.aligned_times({"a_start_s": "2", "a_end_s": "8", "offset_s": "-1"})[1] == (5.0, 4.0)  # no core: the match
    assert sl.aligned_times({}) == []


class Judge:
    def __init__(self, ans, cost=0.01):
        self.ans, self.cost, self.calls = ans, cost, 0

    def _ask(self, content, **kw):
        self.calls += 1
        assert sum(c["type"] == "input_image" for c in content) == 6
        return self.ans, self.cost


def test_run_stops_before_the_cap_and_a_rerun_asks_nothing(tmp_path):
    pairs = [{"pair_id": f"p{i}", "group": "sameplace_neg", "truth": "different", "note": "", "run": "r"} for i in range(10)]
    fr = lambda run, pid: [(1.0, 2.0, b"a", b"b")] * 3
    j = Judge({"same_footage": "no", "anchors": [], "differences": []})
    spent = sl.run(pairs, tmp_path, j, max_usd=0.05, workers=1, frames_of=fr, log=lambda *_: None)
    assert j.calls == 3 and abs(spent - 0.03) < 1e-9  # a fourth would risk passing $0.05 with its reserve
    rows = [json.loads(x) for x in (tmp_path / "results.jsonl").read_text().splitlines()]
    assert [r["verdict"] for r in rows] == ["different"] * 3
    j2 = Judge(None)
    sl.run(pairs[:2], tmp_path, j2, max_usd=1, workers=1, frames_of=fr, log=lambda *_: None)
    assert j2.calls == 0
    assert "| sameplace_neg | 0 | 0/3" in sl.report(tmp_path)


def test_only_cut_off_answers_are_asked_again_and_the_last_answer_counts(tmp_path):
    pairs = [{"pair_id": f"p{i}", "group": "sameplace_neg", "truth": "different", "note": "", "run": "r"} for i in range(2)]
    fr = lambda run, pid: [(1.0, 2.0, b"a", b"b")] * 3
    sl.run(pairs[:1], tmp_path, Judge({"same_footage": "no"}), workers=1, frames_of=fr, log=lambda *_: None)
    sl.run(pairs[1:], tmp_path, Judge(None), workers=1, frames_of=fr, log=lambda *_: None)  # cut off: no answer
    j = Judge({"same_footage": "no"})
    sl.run(pairs, tmp_path, j, workers=1, frames_of=fr, log=lambda *_: None, retry_cut=True, max_out=8000)
    assert j.calls == 1  # p1 only
    assert "| sameplace_neg | 0 | 0/2 (different 2)" in sl.report(tmp_path)


def test_wilson_interval():
    lo, hi = sl.wilson(0, 47)
    assert lo < 1e-9 and 0.07 < hi < 0.08
