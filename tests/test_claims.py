import csv
import json

from indexreel import claims, cli, verify


class Fake:
    """Stands in for Spark: returns a fixed answer and counts requests."""

    def __init__(self, answer, cost=0.004, status="completed"):
        self.answer, self.cost, self.status, self.calls = answer, cost, status, 0

    def ask(self, text):
        self.calls += 1
        self.text = text
        return self.answer, self.cost, self.status


def run_dir(tmp_path, caps):
    run = tmp_path / "run"
    run.mkdir(parents=True)
    clips = [{"id": f"x{i}", "path": f"x{i}.mp4", **({"source": {"caption": c}} if c is not None else {})} for i, c in enumerate(caps, 1)]
    (run / "clips.json").write_text(json.dumps({"version": 1, "clips": clips}))
    return run


def read(run):
    return list(csv.DictReader(open(run / "claims.csv", newline="")))


CAPS = ["TEST POST. Lava at fissure 20, Kilauea, May 19, 2018. Source: USGS.", "Fissure 20 on Kilauea erupting, May 19, 2018.",
        "My own clip of an airshow in Leesburg, Virginia."]
ANSWER = {"claims": [
    {"claim": "Filmed on May 19, 2018.", "kind": "time", "cited": [{"post": "P1", "quote": "May 19, 2018"}, {"post": "P2", "quote": "May 19, 2018"}]},
    {"claim": "Shows fissure 20 on Kilauea.", "kind": "place", "cited": [{"post": "P1", "quote": "fissure 20, Kilauea"},
                                                                          {"post": "P2", "quote": "Fissure 20 on Kilauea"}]},
    {"claim": "Filmed at night.", "kind": "time", "cited": [{"post": "P3", "quote": "at night"}]},  # not in the caption
    {"claim": "An airshow in Leesburg, Virginia.", "kind": "event", "cited": [{"post": "P3", "quote": "airshow in Leesburg, Virginia"},
                                                                               {"post": "P9", "quote": "airshow"}]}]}


def test_claims_shared_by_posts_get_one_id_and_every_row_is_suggested(tmp_path):
    run, logs = run_dir(tmp_path, CAPS), []
    spent, cost = claims.extract(run, Fake(ANSWER), verify.Cache(tmp_path / "c"), log=logs.append)
    rows = read(run)
    assert list(rows[0]) == claims.COLUMNS and {r["status"] for r in rows} == {"suggested"}
    assert [(r["clip"], r["claim_id"]) for r in rows] == [("x1", "c1"), ("x2", "c1"), ("x1", "c2"), ("x2", "c2"), ("x3", "c3")]
    assert all(r["quote"] in CAPS[int(r["clip"][1:]) - 1] for r in rows)
    assert spent == cost == 0.004


def test_a_quote_that_is_not_in_the_caption_is_dropped_and_logged(tmp_path):
    run, logs = run_dir(tmp_path, CAPS), []
    claims.extract(run, Fake(ANSWER), verify.Cache(tmp_path / "c"), log=logs.append)
    assert "Filmed at night." not in {r["claim_text"] for r in read(run)}  # its only citation failed: no claim
    assert len(logs) == 2 and all(line.startswith("claims: dropped") for line in logs)  # "at night" and post P9
    assert any("at night" in line for line in logs) and any("P9" in line for line in logs)


def test_no_caption_means_no_claims_and_no_request(tmp_path):
    run, fake = run_dir(tmp_path, [None, "   "]), Fake(ANSWER)
    assert claims.extract(run, fake, verify.Cache(tmp_path / "c")) == (0.0, 0.0)
    assert fake.calls == 0 and read(run) == []


def test_the_answer_is_cached_and_the_budget_stops_a_new_request(tmp_path):
    run, cache = run_dir(tmp_path, CAPS), verify.Cache(tmp_path / "c")
    first, again = Fake(ANSWER), Fake({"claims": []})
    claims.extract(run, first, cache)
    assert claims.extract(run, again, cache) == (0.0, 0.004) and again.calls == 0 and len(read(run)) == 5
    other, logs, poor = run_dir(tmp_path / "o", ["Volcano at night, Hawaii."]), [], Fake(ANSWER)
    assert claims.extract(other, poor, cache, max_usd=0.001, log=logs.append) == (0.0, 0.0)
    assert poor.calls == 0 and logs[0].startswith("claims: stopped") and not (other / "claims.csv").exists()


def test_claims_is_a_subcommand():
    assert "claims" in [name for name, _, _ in cli.STAGES]


def test_a_response_cut_off_at_the_token_cap_writes_nothing_caches_nothing_and_says_so(tmp_path):
    run, cache, logs = run_dir(tmp_path, CAPS), verify.Cache(tmp_path / "c"), []
    cut = Fake(None, cost=0.017, status="incomplete (max_output_tokens)")
    assert claims.extract(run, cut, cache, log=logs.append) == (0.017, 0.0)
    assert cut.calls == 1 and not (run / "claims.csv").exists()
    assert logs == ["claims: the request ended incomplete (max_output_tokens), cost $0.0170; no claims written, nothing cached"]
    later = Fake(ANSWER)
    claims.extract(run, later, cache)
    assert later.calls == 1 and len(read(run)) == 5  # the cut-off answer was not cached
    logs.clear()
    assert claims.extract(run_dir(tmp_path / "u", CAPS), Fake(None, cost=None, status="failed"), verify.Cache(tmp_path / "d"),
                          log=logs.append) == (0.0, 0.0)
    assert logs[0].endswith("cost not reported; no claims written, nothing cached")


def test_spark_text_reads_the_final_event_itself_and_asks_once(monkeypatch):
    from types import SimpleNamespace as NS
    usage = NS(input_tokens=1000, output_tokens=4000, input_tokens_details=NS(cached_tokens=0))

    class Stream:
        def __init__(self, events):
            self.events = events

        def __enter__(self):
            return iter(self.events)

        def __exit__(self, *exc):
            return False

    calls = []

    def fake_init(self, workdir):
        self.cli = NS(responses=NS(stream=lambda **kw: calls.append(kw) or Stream(events)))

    monkeypatch.setattr(verify.SparkJudge, "__init__", fake_init)
    cut = NS(status="incomplete", incomplete_details=NS(reason="max_output_tokens"), error=None, usage=usage)
    events = [NS(type="response.output_text.delta", delta='{"cla'), NS(type="response.incomplete", response=cut)]
    ans, cost, status = claims.SparkText("w").ask("caption text")
    assert (ans, status, len(calls)) == (None, "incomplete (max_output_tokens)", 1)
    assert abs(cost - (1000 * 1.25 + 4000 * 4.25) / 1e6) < 1e-12 and calls[0]["reasoning"] == {"effort": "minimal"}
    done = NS(status="completed", incomplete_details=None, error=None, usage=usage)
    events = [NS(type="response.output_text.delta", delta='{"claims": []}'), NS(type="response.completed", response=done)]
    assert claims.SparkText("w").ask("caption text")[::2] == ({"claims": []}, "completed")
