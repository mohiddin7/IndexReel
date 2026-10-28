import csv
import json
import shutil
from pathlib import Path

import pytest

from indexreel import cluster, verify

RUN = Path(__file__).parent / "fixtures" / "run_fake"
ROOT = Path(__file__).parents[1]
A_FAMILY = ["a_copy~a_orig", "a_copy~a_refilm", "a_orig~a_refilm"]


class FakeJudge:
    """Answers from tables keyed by pair id: cheap[pid] for the group call, full[(a, b)] or full[pid] for the pair
    call (ordered key first), else the defaults."""

    def __init__(self, cheap=None, full=None, cheap_default="no", full_default="no"):
        self.cheap, self.full, self.calls = cheap or {}, full or {}, []
        self.cheap_default, self.full_default = cheap_default, full_default

    def group(self, anchor, cands):
        assert isinstance(cands, list) and all(Path(c).exists() for c in cands)
        a = Path(anchor).stem
        self.calls.append(("group", a, [Path(c).stem for c in cands]))
        return [{"same_footage": self.cheap.get(cluster.pair_id(a, Path(c).stem), self.cheap_default),
                 "shared_detail": "the same tree"} for c in cands], 0.004

    def pair(self, a, b):
        assert Path(a).exists() and Path(b).exists()
        a, b = Path(a).stem, Path(b).stem
        self.calls.append(("pair", a, b))
        ans = self.full.get((a, b), self.full.get(cluster.pair_id(a, b), self.full_default))
        return {"same_footage": ans, "same_event": "yes", "unsure_because": "dark"}, 0.02


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


def set_band(run, pid, band):
    with open(run / "pairs.csv", newline="") as f:
        r = list(csv.DictReader(f))
    for x in r:
        if x["pair_id"] == pid:
            x["band"] = band
    with open(run / "pairs.csv", "w", newline="") as f:
        w = csv.DictWriter(f, list(r[0]))
        w.writeheader()
        w.writerows(r)


def recordings(run):
    ids = [c["id"] for c in json.loads((run / "clips.json").read_text())["clips"]]
    rs = rows(run).values()
    return sorted(sorted(r["members"]) for r in cluster.recordings(ids, [(r["pair_id"], r["a"], r["b"], cluster.effective_band(r)) for r in rs]))


def test_merged_and_unresolved_pairs_get_a_verdict_apart_pairs_do_not(run, tmp_path):
    before = rows(run)
    judge = FakeJudge(cheap={p: "yes" for p in A_FAMILY})
    verify.verify(run, judge, verify.Cache(tmp_path / "cache"), sound={})
    after = rows(run)
    for p, r in after.items():
        assert {k: v for k, v in r.items() if not k.startswith("verify_")} == {k: v for k, v in before[p].items() if not k.startswith("verify_")}
        assert bool(r["verify_verdict"]) == (r["band"] != "apart")
    assert [after[p]["verify_verdict"] for p in A_FAMILY] == ["same"] * 3
    assert after["b_cam1~b_cam2"]["verify_verdict"] == "different"
    assert not any(c[0] == "pair" for c in judge.calls)  # no conflict anywhere, so no full-fidelity call
    assert list(next(csv.reader(open(run / "pairs.csv")))) == list(before["a_copy~a_refilm"]) + ["verify_same_event"]
    assert all(r["verify_same_event"] == "" for r in after.values())  # the cheap prompt does not ask about the event


def test_a_cheap_miss_inside_a_recording_is_re_asked_and_cleared(run, tmp_path):
    # a_copy~a_refilm cheap "no" makes it apart inside the recording joined through a_orig: a conflict
    judge = FakeJudge(cheap={"a_copy~a_orig": "yes", "a_orig~a_refilm": "yes"}, full={("a_refilm", "a_copy"): "yes"}, full_default="yes")
    spent, total = verify.verify(run, judge, verify.Cache(tmp_path / "cache"), sound={})
    after = rows(run)
    assert after["a_copy~a_refilm"]["verify_verdict"] == "same" and after["a_copy~a_refilm"]["verify_reason"].startswith("re-asked")
    assert after["a_copy~a_refilm"]["verify_confidence"] == "0.67"  # cheap no, then yes and yes
    asked = {cluster.pair_id(a, b) for k, a, b in [c for c in judge.calls if c[0] == "pair"]}
    assert asked == set(A_FAMILY)  # the conflicting pair and both join edges of that recording, both orders each
    assert recordings(run)[0] == ["a_copy", "a_orig", "a_refilm"]
    assert after["a_copy~a_refilm"]["verify_same_event"] == "yes"  # from the full-fidelity answers
    assert spent == pytest.approx(3 * 0.004 + 6 * 0.02)  # three group requests (b_cam1 and the a family), six full calls
    assert total == pytest.approx(sum(float(r["verify_cost_usd"] or 0) for r in after.values()))


def test_a_false_link_between_two_recordings_is_re_asked_and_split(run, tmp_path):
    # the held-out N11~T11 case: one cheap "same" joins two recordings that the matcher holds apart elsewhere
    set_band(run, "a_refilm~b_cam1", "unresolved")
    judge = FakeJudge(cheap={**{p: "yes" for p in A_FAMILY}, "a_refilm~b_cam1": "yes"}, full_default="yes",
                      full={"a_refilm~b_cam1": "no"})
    verify.verify(run, judge, verify.Cache(tmp_path / "cache"), sound={})
    after = rows(run)
    assert after["a_refilm~b_cam1"]["verify_verdict"] == "different"
    assert ["a_copy", "a_orig", "a_refilm"] in recordings(run) and ["b_cam1"] in recordings(run)
    assert [after[p]["verify_verdict"] for p in A_FAMILY] == ["same"] * 3


def test_a_merged_pair_the_judge_rejects_is_demoted_never_apart(run, tmp_path):
    judge = FakeJudge(cheap={"a_copy~a_refilm": "yes", "a_orig~a_refilm": "yes"})  # a_copy~a_orig cheap "no"
    verify.verify(run, judge, verify.Cache(tmp_path / "cache"), sound={})
    r = rows(run)["a_copy~a_orig"]
    assert r["band"] == "merged" and r["verify_verdict"] == "different"
    assert cluster.effective_band(r) == "unresolved"


def test_rerun_comes_from_the_cache(run, tmp_path):
    cache = verify.Cache(tmp_path / "cache")
    verify.verify(run, FakeJudge(cheap={"a_copy~a_refilm": "yes"}), cache, sound={})
    first = rows(run)
    assert first["a_copy~a_refilm"]["verify_verdict"] == "same"
    spent, _ = verify.verify(run, Refuse(), cache, sound={})
    assert spent == 0 and rows(run) == first


def test_matching_sound_escalates_but_does_not_decide(run, tmp_path):
    judge = FakeJudge(cheap={p: "yes" for p in A_FAMILY})
    verify.verify(run, judge, verify.Cache(tmp_path / "cache"), sound={"b_cam1~b_cam2": 0.2})
    r = rows(run)["b_cam1~b_cam2"]
    assert ("pair", "b_cam1", "b_cam2") in judge.calls
    assert r["verify_verdict"] == "different" and "sound matches (0.200)" in r["verify_reason"]


def test_budget_stops_new_calls(run, tmp_path):
    spent, _ = verify.verify(run, FakeJudge(), verify.Cache(tmp_path / "cache"), sound={}, max_usd=0)
    assert spent == 0 and not any(r["verify_verdict"] for r in rows(run).values())


def test_an_anchor_with_several_candidates_gets_one_request(run, tmp_path):
    for p in ("a_copy~b_cam1", "a_orig~b_cam1", "a_refilm~b_cam1", "b_cam1~c_alone"):
        set_band(run, p, "unresolved")  # b_cam1 now has 5 pairs, so it anchors 4 candidates then 1
    judge = FakeJudge(cheap={"b_cam1~b_cam2": "yes"})
    verify.verify(run, judge, verify.Cache(tmp_path / "cache"), sound={})
    groups = sorted(c for c in judge.calls if c[0] == "group" and c[1] == "b_cam1")
    assert groups == sorted([("group", "b_cam1", ["a_copy", "a_orig", "a_refilm", "b_cam2"]), ("group", "b_cam1", ["c_alone"])])
    assert rows(run)["b_cam1~b_cam2"]["verify_verdict"] == "same"


def test_anchor_takes_at_most_four_candidates():
    pairs = [("hub", f"x{i}") for i in range(6)]
    assert verify.chunks(pairs) == [("hub", ["x0", "x1", "x2", "x3"]), ("hub", ["x4", "x5"])]


def test_prompts_are_the_measured_ones():
    assert verify.GROUP_PROMPT in (ROOT / "scripts" / "spark_h12.py").read_text()
    assert verify.PAIR_PROMPT in (ROOT / "scripts" / "spark_pilot3.py").read_text()


def test_baseten_judge_sends_one_two_video_request_per_candidate(tmp_path, monkeypatch):
    from types import SimpleNamespace as NS
    sent = []

    class Completions:
        def create(self, model, messages, **kw):
            videos = [p for p in messages[0]["content"] if p["type"] == "video_url"]
            sent.append(len(videos))
            usage = NS(prompt_tokens=1000, completion_tokens=100, prompt_tokens_details=NS(cached_tokens=0))
            msg = NS(content='{"results": [{"candidate": "B1", "same_footage": "yes"}]}')
            return NS(usage=usage, choices=[NS(message=msg)])

    monkeypatch.setenv("BASETEN_API_KEY", "test")
    monkeypatch.setattr(verify, "encode", lambda path, size, workdir: Path(path))
    judge = verify.BasetenJudge(tmp_path)
    judge.cli = NS(chat=NS(completions=Completions()))
    clips = []
    for n in ("a", "b", "c"):
        (tmp_path / f"{n}.mp4").write_bytes(n.encode())
        clips.append(str(tmp_path / f"{n}.mp4"))
    answers, cost = judge.group(clips[0], clips[1:])
    assert sent == [2, 2] and [a["same_footage"] for a in answers] == ["yes", "yes"]
    assert cost == pytest.approx(2 * (1000 * 1.25 + 100 * 4.25) / 1e6)


def test_reasons_keep_whole_sentences():
    long = "First sentence is here. " + "Second one runs on " * 12 + "and ends."
    assert verify.sentences(long) == "First sentence is here."
    assert verify.sentences("Short. Also short.") == "Short. Also short."
    one = "One very long sentence " * 20
    assert verify.sentences(one) == one.strip()  # never cut inside a sentence


def test_same_event_across_orders():
    assert [verify.same_event(x) for x in (["yes", "yes"], ["no", "yes"], ["no", None], [], [None])] == ["yes", "unsure", "no", "", ""]
