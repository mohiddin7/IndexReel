import csv
import shutil
from pathlib import Path

import pytest

from indexreel import verify

RUN = Path(__file__).parent / "fixtures" / "run_fake"
ROOT = Path(__file__).parents[1]


class FakeJudge:
    """Answers from a table keyed by clip ids: cheap[(anchor, candidate)] and full[(a, b)] give same_footage."""

    def __init__(self, cheap, full=None):
        self.cheap, self.full, self.calls = cheap, full or {}, []

    def group(self, anchor, cands):
        a = Path(anchor).stem
        self.calls.append(("group", a, [Path(c).stem for c in cands]))
        return [{"same_footage": self.cheap.get((a, Path(c).stem), "no"), "shared_detail": "the same tree"} for c in cands], 0.004

    def pair(self, a, b):
        a, b = Path(a).stem, Path(b).stem
        self.calls.append(("pair", a, b))
        return {"same_footage": self.full.get((a, b), "no"), "unsure_because": "dark"}, 0.02


class Refuse:
    def group(self, *a):
        raise AssertionError("should come from the cache")

    pair = group


@pytest.fixture
def run(tmp_path):
    d = tmp_path / "run"
    shutil.copytree(RUN, d)
    (d / "clips").mkdir()
    for name in ("a_orig", "a_copy", "a_refilm", "b_cam1", "b_cam2", "c_alone"):
        (d / "clips" / f"{name}.mp4").write_bytes(name.encode())  # content only feeds the cache key
    return d


def rows(run):
    return {r["pair_id"]: r for r in csv.DictReader(open(run / "pairs.csv"))}


def test_only_unresolved_pairs_get_a_verdict_and_conflicts_escalate(run, tmp_path):
    before = rows(run)
    judge = FakeJudge(cheap={("b_cam1", "b_cam2"): "no"}, full={("a_refilm", "a_copy"): "yes"})
    spent, total = verify.verify(run, judge, verify.Cache(tmp_path / "cache"), sound={})
    after = rows(run)
    # a_copy and a_refilm are both merged with a_orig, so the cheap "no" is a conflict and is re-asked in both orders
    assert after["a_copy~a_refilm"]["verify_verdict"] == "same"
    assert after["a_copy~a_refilm"]["verify_reason"].startswith("escalated")
    assert after["a_copy~a_refilm"]["verify_confidence"] == "0.33"  # one yes among no, no, yes
    assert ("pair", "a_copy", "a_refilm") in judge.calls and ("pair", "a_refilm", "a_copy") in judge.calls
    assert after["b_cam1~b_cam2"]["verify_verdict"] == "different"
    assert not any(c[0] == "pair" and "b_cam1" in c for c in judge.calls)
    for p, r in after.items():
        assert {k: v for k, v in r.items() if not k.startswith("verify_")} == {k: v for k, v in before[p].items() if not k.startswith("verify_")}
        assert bool(r["verify_verdict"]) == (r["band"] == "unresolved")
    assert spent == pytest.approx(2 * 0.004 + 2 * 0.02)  # two group requests (no shared anchor), two escalation calls
    assert total == pytest.approx(sum(float(r["verify_cost_usd"] or 0) for r in after.values()))
    assert list(next(csv.reader(open(run / "pairs.csv")))) == list(before["a_copy~a_refilm"])


def test_rerun_comes_from_the_cache(run, tmp_path):
    cache = verify.Cache(tmp_path / "cache")
    verify.verify(run, FakeJudge(cheap={("a_copy", "a_refilm"): "yes"}), cache, sound={})
    first = rows(run)
    spent, _ = verify.verify(run, Refuse(), cache, sound={})
    assert spent == 0 and rows(run) == first


def test_matching_sound_escalates_but_does_not_decide(run, tmp_path):
    judge = FakeJudge(cheap={})
    verify.verify(run, judge, verify.Cache(tmp_path / "cache"), sound={"b_cam1~b_cam2": 0.2})
    r = rows(run)["b_cam1~b_cam2"]
    assert ("pair", "b_cam1", "b_cam2") in judge.calls
    assert r["verify_verdict"] == "different" and "sound matches (0.200)" in r["verify_reason"]


def test_budget_stops_new_calls(run, tmp_path):
    spent, _ = verify.verify(run, FakeJudge(cheap={}), verify.Cache(tmp_path / "cache"), sound={}, max_usd=0)
    assert spent == 0 and not any(r["verify_verdict"] for r in rows(run).values())


def test_anchor_takes_at_most_four_candidates():
    pairs = [("hub", f"x{i}") for i in range(6)]
    assert verify.chunks(pairs) == [("hub", ["x0", "x1", "x2", "x3"]), ("hub", ["x4", "x5"])]


def test_prompts_are_the_measured_ones():
    assert verify.GROUP_PROMPT in (ROOT / "scripts" / "spark_h12.py").read_text()
    assert verify.PAIR_PROMPT in (ROOT / "scripts" / "spark_pilot3.py").read_text()
