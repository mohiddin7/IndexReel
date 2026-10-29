"""Blind sheets and score for the trace test (eval/trace.md: Bars, Clarification 1, Amendment A).

  python scripts/score_trace.py sheets <run dir> <manifest.csv> <inputs.csv> --out <dir> [--seed N]
  python scripts/score_trace.py score <dir> --answers1 <csv> --answers2 <csv>  (the answered sheet1.csv and sheet2.csv)

`sheets` takes every earlier confirmed copy in <run>/trace.csv (confirmed 1, earlier 1) and writes, in <dir>:
- sheet1/sheet1.csv (question i, test and control rows mixed): row, case, evidence (the core-span image, input left);
- sheet2/sheet2.csv (question ii, test rows only): row, case, original (the fact-check's description, the manifest's
  `original` column), candidate (the candidate's frames alone), posted_at;
- key.csv, never shown to the reviewer: row1, row2, case id, kind, edit, url, source, leak_exposed, leak_copy, control.
Each sheet is in its own folder with its own shuffle, its own row ids (a001..., b001...) and its own neutral case
labels (x01..., y01...), so nothing lines up across the sheets, and neither says which source found a row or which
rows are controls. The reviewer answers sheet 2 first. The reviewer answers `same`, `different` or `cannot tell` in an `answer`
column. `score` reads both answer sheets and prints bar 1, bars 2a and 2b, and the secondary count.
"""
import argparse
import csv
import math
import random
import shutil
import sys
from pathlib import Path


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


CONTROL, TEST = ("c", "k"), ("t", "n")  # case id prefixes: eval/trace.md (c, t) and eval/trace-v2.md (k, n)


def passes_leak(row):
    """Leak rule 2 per copy: trace's own leak_copy column when the run has it (eval/trace-v2.md, per source), else
    Amendment A, change 3 of eval/trace.md."""
    if row.get("leak_copy") in ("0", "1"):
        return row["leak_copy"] == "0"
    return row["leak_exposed"] != "1" or bool({"channel", "youtube"} & set(row["source"].split("+")))


def read(path):
    return list(csv.DictReader(open(path, newline="")))


def write(path, rows, fields):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def sheets(run, manifest, inputs, out, seed=2910):
    import cv2
    run, out = Path(run), Path(out)
    for d in ("sheet1", "sheet2"):
        (out / d / "img").mkdir(parents=True, exist_ok=True)
    man = {r["case"]: r for r in read(manifest)}
    kind = {r["case"]: r for r in read(inputs)}
    rng = random.Random(seed)
    labels = []
    for prefix in ("x", "y"):  # each sheet labels the cases on its own, so labels do not line up across sheets
        cases = sorted(man)
        rng.shuffle(cases)
        labels.append({c: f"{prefix}{i:02d}" for i, c in enumerate(cases, 1)})
    rows = [r for r in read(run / "trace.csv") if r["confirmed"] == "1" and r["earlier"] == "1"]
    order1, order2 = rows[:], [r for r in rows if not r["input"].startswith(CONTROL)]
    rng.shuffle(order1)
    rng.shuffle(order2)  # its own order: a row's place on one sheet says nothing about the other
    id1 = {id(r): f"a{i:03d}" for i, r in enumerate(order1, 1)}
    id2 = {id(r): f"b{i:03d}" for i, r in enumerate(order2, 1)}
    s1, s2, key = [], [], []
    for r in order1:
        case, rid = r["input"], id1[id(r)]
        shutil.copy(run / r["evidence"], out / "sheet1" / "img" / f"{rid}.jpg")
        s1.append({"row": rid, "case": labels[0][case], "evidence": f"img/{rid}.jpg", "answer": ""})
    for r in order2:
        case, rid = r["input"], id2[id(r)]
        img = cv2.imread(str(run / r["evidence"]))
        cv2.imwrite(str(out / "sheet2" / "img" / f"{rid}.jpg"), img[:, img.shape[1] // 2:])
        s2.append({"row": rid, "case": labels[1][case], "original": man[case].get("original", ""),
                   "candidate": f"img/{rid}.jpg", "posted_at": r["posted_at"], "answer": ""})
    for r in rows:
        case = r["input"]
        key.append({"row1": id1[id(r)], "row2": id2.get(id(r), ""), "case": case, "kind": kind.get(case, {}).get("kind", ""),
                    "edit": kind.get(case, {}).get("edit", ""), "url": r["url"], "source": r["source"],
                    "leak_exposed": r["leak_exposed"], "leak_copy": r.get("leak_copy", ""), "control": int(case.startswith(CONTROL))})
    key.sort(key=lambda k: k["row1"])
    write(out / "sheet1" / "sheet1.csv", s1, ["row", "case", "evidence", "answer"])
    write(out / "sheet2" / "sheet2.csv", s2, ["row", "case", "original", "candidate", "posted_at", "answer"])
    write(out / "key.csv", key, ["row1", "row2", "case", "kind", "edit", "url", "source", "leak_exposed", "leak_copy", "control"])
    write(out / "cases.csv", [{"case": c, "kind": kind.get(c, {}).get("kind", "none"), "edit": kind.get(c, {}).get("edit", ""),
                               "intended": man[c].get("kind", "")} for c in sorted(man)], ["case", "kind", "edit", "intended"])
    return len(s1), len(s2)


def score(d, answers1, answers2, say=print):
    d = Path(d)
    key = {r["row1"]: r for r in read(d / "key.csv")}
    a1 = {r["row"]: r["answer"].strip().lower() for r in read(answers1)}
    a2 = {r["row"]: r["answer"].strip().lower() for r in read(answers2)}
    # any earlier confirmed copy on a control is wrong (eval/trace.md, bar 1), whatever the reviewer answers
    wrong = [r for r in key if key[r]["control"] == "1" or a1.get(r) != "same"]
    for r in wrong:
        why = "a control" if key[r]["control"] == "1" else f"question (i) answered {a1.get(r) or 'nothing'}"
        say(f"score: wrong statement {r} ({key[r]['case']}, {key[r]['url']}): {why}")
    found, found_leaky = set(), set()
    for r, k in key.items():
        if k["control"] == "0" and a1.get(r) == "same" and a2.get(k["row2"]) == "same":
            (found if passes_leak(k) else found_leaky).add(k["case"])
    cases = read(d / "cases.csv")
    out = {}
    for kind in ("a", "b"):
        # a case without an input counts against the kind it was meant for (Bars, bar 2)
        meant = lambda c: c["intended"] if c["intended"] in ("a", "b") else "b"  # no input: (b) unless a re-upload was meant
        n = [c["case"] for c in cases if c["case"].startswith(TEST) and (c["kind"] == kind or (c["kind"] == "none" and meant(c) == kind))]
        k = sum(c in found for c in n)
        need = math.ceil(0.4 * len(n))
        lo, hi = wilson(k, len(n))
        out[kind] = k >= need
        small = " (fewer than 5 cases: too small to read much into)" if len(n) < 5 else ""
        say(f"score: bar 2{kind}: found {k} of {len(n)}, need {need}, Wilson 95% {lo:.2f}-{hi:.2f}: "
            f"{'PASS' if out[kind] else 'FAIL'}{small}")
    say(f"score: secondary: found including leak-exposed recordings {len(found | found_leaky)} of "
        f"{sum(c['case'].startswith(TEST) for c in cases)}")
    ok = not wrong and out["a"] and out["b"]
    say(f"score: bar 1: {len(wrong)} wrong statements: {'PASS' if not wrong else 'FAIL'}")
    say(f"score: run {'PASS' if ok else 'FAIL'}")
    return ok


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sheets")
    s.add_argument("run")
    s.add_argument("manifest")
    s.add_argument("inputs")
    s.add_argument("--out", required=True)
    s.add_argument("--seed", type=int, default=2910)
    c = sub.add_parser("score")
    c.add_argument("dir")
    c.add_argument("--answers1", required=True)
    c.add_argument("--answers2", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "sheets":
        n1, n2 = sheets(a.run, a.manifest, a.inputs, a.out, a.seed)
        print(f"score_trace: {n1} rows on sheet 1, {n2} on sheet 2")
    else:
        sys.exit(0 if score(a.dir, a.answers1, a.answers2) else 1)


if __name__ == "__main__":
    main()
