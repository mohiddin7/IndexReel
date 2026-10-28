import csv
import json
from itertools import combinations
from pathlib import Path

import pytest

from indexreel import cluster

FIXTURES = Path(__file__).parent / "fixtures"
COLUMNS = ["pair_id", "a", "b", "score", "aligned", "mirrored", "offset_s", "a_start_s", "a_end_s", "b_start_s",
           "b_end_s", "band", "evidence", "evidence_a_s", "verify_verdict", "verify_confidence", "verify_reason",
           "verify_cost_usd", "core_a_start_s", "core_a_end_s", "core_b_start_s", "core_b_end_s"]


def load(d):
    clips = json.loads((d / "clips.json").read_text())["clips"]
    rows = list(csv.DictReader(open(d / "pairs.csv")))
    clusters = json.loads((d / "clusters.json").read_text())
    audit = [json.loads(line) for line in (d / "audit.jsonl").read_text().splitlines()]
    return clips, rows, clusters, audit, d


@pytest.fixture(scope="module", params=["run_fake", "run_fake_compilation"])
def run(request):
    return load(FIXTURES / request.param)


def triples(rows, bands=None):
    return [(r["pair_id"], r["a"], r["b"], (bands or {}).get(r["pair_id"], r["band"])) for r in rows]


def test_pairs_follow_the_format(run):
    clips, rows, _, _, d = run
    ids = [c["id"] for c in clips]
    assert list(rows[0]) == COLUMNS
    assert sorted((r["a"], r["b"]) for r in rows) == sorted(combinations(sorted(ids), 2))
    for r in rows:
        assert r["pair_id"] == f"{r['a']}~{r['b']}" and r["a"] < r["b"]
        assert abs(float(r["b_start_s"]) - float(r["a_start_s"]) - float(r["offset_s"])) < 1e-6
        assert bool(r["evidence"]) == (r["band"] != "apart")
        if r["evidence"]:
            assert (d / r["evidence"]).exists()
            assert len(r["evidence_a_s"].split(";")) == 3


def test_bands_and_clusters_follow_the_rules(run):
    _, rows, clusters, _, _ = run
    th = clusters["thresholds"]
    for r in rows:
        assert r["band"] == cluster.band(float(r["aligned"]), float(r["score"]), th["merge_at"], th["floor"])
    ids = [c["id"] for c in run[0]]
    assert (clusters["recordings"], clusters["compilations"], clusters.get("compilation_suggestions", [])) == cluster.resolve_all(ids, rows, [])


def test_audit_decisions_change_the_clusters():
    clips, rows, _, audit, _ = load(FIXTURES / "run_fake")
    bands = cluster.apply_audit({r["pair_id"]: r["band"] for r in rows}, audit)
    rec = {r["id"]: r for r in cluster.recordings([c["id"] for c in clips], triples(rows, bands))}
    assert rec["r1"]["status"] == "merged"  # the one unresolved pair inside it was approved
    undone = cluster.apply_audit({r["pair_id"]: r["band"] for r in rows}, audit + [{"pair": audit[0]["pair"], "action": "reset"}])
    assert undone[audit[0]["pair"]] == "unresolved"


def test_merging_is_not_transitive():
    pairs = [("a~b", "a", "b", "merged"), ("b~c", "b", "c", "merged"), ("a~c", "a", "c", "apart")]
    (r,) = cluster.recordings(["a", "b", "c"], pairs)
    assert r["members"] == ["a", "b", "c"] and r["status"] == "merged" and r["conflicts"] == ["a~c"]


def test_band_edges():
    assert cluster.band(0.54, 0.0, 0.54, 0.30) == "merged"
    assert cluster.band(0.29, 0.20, 0.54, 0.30) == "apart"
    assert cluster.band(0.29, 0.80, 0.54, 0.30) == "unresolved"  # frames match but not in time
    assert cluster.band(0.40, 0.40, 0.54, 0.30) == "unresolved"


@pytest.mark.parametrize("band,verdict,expected", [
    ("merged", "", "merged"), ("merged", "same", "merged"), ("merged", "different", "unresolved"),
    ("merged", "abstain", "unresolved"), ("unresolved", "same", "merged"), ("unresolved", "different", "apart"),
    ("unresolved", "abstain", "unresolved"), ("unresolved", "", "unresolved"), ("apart", "same", "apart"),
    ("apart", "", "apart")])
def test_effective_band(band, verdict, expected):
    assert cluster.effective_band({"band": band, "verify_verdict": verdict}) == expected


def test_a_compilation_is_a_suggestion_until_confirmed_then_its_own_recording(run):
    clips, rows, clusters, _, d = run
    if d.name != "run_fake_compilation":
        assert clusters["compilations"] == [] and "compilation_suggestions" not in clusters
        return
    (c,) = clusters["compilation_suggestions"]
    assert clusters["compilations"] == [] and c["clip"] == "v_upload"
    # unconfirmed, the clip is joined to its sources and the recording is undecided
    by_id = {r["id"]: r for r in clusters["recordings"]}
    assert by_id[c["recording"]]["status"] == "unresolved" and "v_upload" in by_id[c["recording"]]["members"]
    ids = [x["id"] for x in clips]
    rec, comps, sug = cluster.resolve_all(ids, rows, [{"action": "confirm_compilation", "clip": "v_upload"}])
    (k,) = comps
    by_id = {r["id"]: r for r in rec}
    assert sug == [] and by_id[k["recording"]]["status"] == "compilation" and by_id[k["recording"]]["members"] == ["v_upload"]
    assert sorted(by_id[s["recording"]]["members"][0] for s in k["segments"]) == ["p_orig", "q_cam", "r_cam"]
    assert [s["start_s"] for s in k["segments"]] == sorted(s["start_s"] for s in k["segments"])
