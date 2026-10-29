import csv
import importlib.util
from pathlib import Path

import cv2
import numpy as np

spec = importlib.util.spec_from_file_location("score_trace", Path(__file__).resolve().parents[1] / "scripts" / "score_trace.py")
st = importlib.util.module_from_spec(spec)
spec.loader.exec_module(st)

COLS = ["recording", "input", "source", "url", "posted_at", "evidence", "confirmed", "earlier", "leak_exposed"]


def setup(tmp_path):
    run = tmp_path / "run"
    (run / "ev").mkdir(parents=True)
    img = np.zeros((540, 640, 3), np.uint8)
    rows = []
    for i, (case, src, leak) in enumerate([("t1", "web", "0"), ("t2", "web", "1"), ("t3", "web+youtube", "1"),
                                           ("t4", "youtube", "0"), ("c1", "youtube", "0")]):
        cv2.imwrite(str(run / "ev" / f"{i}.jpg"), img)
        rows.append({"recording": f"r{i}", "input": case, "source": src, "url": f"https://x.com/u/status/{i}",
                     "posted_at": "2017-01-01", "evidence": f"ev/{i}.jpg", "confirmed": "1", "earlier": "1", "leak_exposed": leak})
    rows.append({**rows[0], "input": "t5", "confirmed": "0", "earlier": "1"})  # not confirmed: on no sheet
    st.write(run / "trace.csv", rows, COLS)
    man = [{"case": c, "kind": k, "original": f"orig {c}"} for c, k in
           [("t1", "a"), ("t2", "b"), ("t3", "b"), ("t4", "b"), ("t5", "a"), ("t6", "b"), ("t7", "none"), ("c1", "a")]]
    st.write(tmp_path / "manifest.csv", man, ["case", "kind", "original"])
    inp = [{"case": "t1", "kind": "a", "edit": ""}, {"case": "t2", "kind": "b", "edit": "flip"}, {"case": "t3", "kind": "b", "edit": "slow"},
           {"case": "t4", "kind": "b", "edit": "zoom"}, {"case": "t5", "kind": "a", "edit": ""}, {"case": "t6", "kind": "none", "edit": "compilation"}, {"case": "t7", "kind": "none", "edit": ""},
           {"case": "c1", "kind": "a", "edit": ""}]
    st.write(tmp_path / "inputs.csv", inp, ["case", "kind", "edit"])
    out = tmp_path / "sheets"
    assert st.sheets(run, tmp_path / "manifest.csv", tmp_path / "inputs.csv", out) == (5, 4)
    return out


def answer(out, name, default="same", **by_case):
    col = "row1" if name == "sheet1.csv" else "row2"
    key = {r[col]: r["case"] for r in st.read(out / "key.csv") if r[col]}
    rows = st.read(out / name.split(".")[0] / name)
    for r in rows:
        r["answer"] = by_case.get(key[r["row"]], default)
    st.write(out / f"ans_{name}", rows, list(rows[0]))
    return out / f"ans_{name}"


def test_sheets_hide_sources_and_controls(tmp_path):
    out = setup(tmp_path)
    s1, s2 = (out / "sheet1" / "sheet1.csv").read_text(), st.read(out / "sheet2" / "sheet2.csv")
    assert "youtube" not in s1 and "web" not in s1 and "c1" not in s1 and "t1" not in s1
    assert {r["original"] for r in s2} == {"orig t1", "orig t2", "orig t3", "orig t4"}  # no control on sheet 2
    assert cv2.imread(str(out / "sheet2" / s2[0]["candidate"])).shape[1] == 320  # the candidate half only


def test_the_two_sheets_share_no_row_ids_labels_or_images(tmp_path):
    out = setup(tmp_path)
    s1, s2 = st.read(out / "sheet1" / "sheet1.csv"), st.read(out / "sheet2" / "sheet2.csv")
    assert not {r["row"] for r in s1} & {r["row"] for r in s2}
    assert not {r["case"] for r in s1} & {r["case"] for r in s2}
    assert not {p.name for p in (out / "sheet1" / "img").iterdir()} & {p.name for p in (out / "sheet2" / "img").iterdir()}


def test_score_counts_leaks_per_copy_and_fails_on_any_unclear_link(tmp_path):
    out, said = setup(tmp_path), []
    ok = st.score(out, answer(out, "sheet1.csv"), answer(out, "sheet2.csv"), say=said.append)
    # found: t1 (web, not leaky), t3 (leaky but also youtube), t4; not t2 (web only, leaky); t5, t6, t7 nothing
    # (t7 has no input and was listed as "none": it counts under b)
    assert "score: bar 2a: found 1 of 2, need 1" in said[0] and "PASS" in said[0]
    assert "score: bar 2b: found 2 of 5, need 2" in said[1] and "PASS" in said[1]
    assert "including leak-exposed recordings 4 of 7" in said[2] and ok
    said.clear()
    assert not st.score(out, answer(out, "sheet1.csv", c1="cannot tell"), answer(out, "sheet2.csv"), say=said.append)
    assert any(s.startswith("score: wrong statement") and "c1" in s for s in said)
    said.clear()
    st.score(out, answer(out, "sheet1.csv"), answer(out, "sheet2.csv", t4="cannot tell", t3="different"), say=said.append)
    assert "found 0 of 5" in said[1] and "FAIL" in said[1] and not any(s.startswith("score: wrong statement") for s in said)


def test_wilson():
    lo, hi = st.wilson(6, 15)
    assert 0.19 < lo < 0.20 and 0.64 < hi < 0.65


def test_v2_runs_use_traces_leak_copy_column():
    assert st.passes_leak({"leak_copy": "0", "leak_exposed": "1", "source": "web"})  # e.g. web+ytapi in v2
    assert not st.passes_leak({"leak_copy": "1", "leak_exposed": "1", "source": "web"})
    assert st.passes_leak({"leak_copy": "", "leak_exposed": "1", "source": "web+youtube"})  # a v1 key


def test_v2_case_ids_are_scored_like_v1_ones():
    assert "k1".startswith(st.CONTROL) and "c1".startswith(st.CONTROL) and not "n1".startswith(st.CONTROL)
    assert "n11".startswith(st.TEST) and "t1".startswith(st.TEST) and not "k1".startswith(st.TEST)
