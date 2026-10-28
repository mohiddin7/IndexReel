import csv
import json
from itertools import combinations
from pathlib import Path

import pytest

from indexreel import cluster

RUN = Path(__file__).parent / "fixtures" / "run_fake"
COLUMNS = ["pair_id", "a", "b", "score", "aligned", "mirrored", "offset_s", "a_start_s", "a_end_s", "b_start_s",
           "b_end_s", "band", "evidence", "evidence_a_s", "verify_verdict", "verify_confidence", "verify_reason",
           "verify_cost_usd", "core_a_start_s", "core_a_end_s", "core_b_start_s", "core_b_end_s"]


@pytest.fixture(scope="module")
def run():
    clips = json.loads((RUN / "clips.json").read_text())["clips"]
    rows = list(csv.DictReader(open(RUN / "pairs.csv")))
    clusters = json.loads((RUN / "clusters.json").read_text())
    audit = [json.loads(line) for line in (RUN / "audit.jsonl").read_text().splitlines()]
    return clips, rows, clusters, audit


def triples(rows, bands=None):
    return [(r["pair_id"], r["a"], r["b"], (bands or {}).get(r["pair_id"], r["band"])) for r in rows]


def test_pairs_follow_the_format(run):
    clips, rows, _, _ = run
    ids = [c["id"] for c in clips]
    assert list(rows[0]) == COLUMNS
    assert sorted((r["a"], r["b"]) for r in rows) == sorted(combinations(sorted(ids), 2))
    for r in rows:
        assert r["pair_id"] == f"{r['a']}~{r['b']}" and r["a"] < r["b"]
        assert abs(float(r["b_start_s"]) - float(r["a_start_s"]) - float(r["offset_s"])) < 1e-6
        assert bool(r["evidence"]) == (r["band"] != "apart")
        if r["evidence"]:
            assert (RUN / r["evidence"]).exists()
            assert len(r["evidence_a_s"].split(";")) == 3


def test_bands_and_clusters_follow_the_rules(run):
    _, rows, clusters, _ = run
    th = clusters["thresholds"]
    for r in rows:
        assert r["band"] == cluster.band(float(r["aligned"]), float(r["score"]), th["merge_at"], th["floor"])
    ids = [c["id"] for c in run[0]]
    assert clusters["recordings"] == cluster.recordings(ids, triples(rows))


def test_audit_decisions_change_the_clusters(run):
    clips, rows, _, audit = run
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
