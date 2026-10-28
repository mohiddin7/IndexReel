"""Pile test: SSCD proposes candidate pairs, Muse Spark judges them, the judged pairs are grouped into recordings.
Protocol: eval/spark-pile.md (frozen before the pile was scored).

  PYTHONPATH=src:scripts python scripts/spark_pile.py clips     build the 30-clip masked pile in data/spark_pile/clips
  PYTHONPATH=src:scripts python scripts/spark_pile.py score     stage 1: SSCD and PDQ on all 435 pairs, pick the candidates (free)
  PYTHONPATH=src:scripts python scripts/spark_pile.py run       stage 2: needs MODEL_API_KEY in my shell; Spark on the candidates; resumes
  PYTHONPATH=src:scripts python scripts/spark_pile.py report    stage 3: group into recordings and score the pass bar
"""
import itertools
import json
import random
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import numpy as np

import spark_pilot2 as p
import spark_pilot3 as p3

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "data" / "spark_pile"
C = D / "clips"
MODEL = ROOT / "data/models/sscd_disc_mixup.torchscript.pt"  # SSCD disc_mixup TorchScript weights
P1 = ["Y", "M", "I", "C0", "C4", "MA"]
COMPILATION = "A1N1A3_e4"
K, THRESH, SEED, MERGE_COVER = 4, 0.60, 2611, 0.60


def rec(c):
    """The recording a clip comes from (None for the compilation)."""
    return None if c == COMPILATION else c.split("_")[0]


def names():
    return sorted(f.stem for f in C.glob("*.mp4"))


def duration(c):
    cap = cv2.VideoCapture(str(C / f"{c}.mp4"))
    return cap.get(cv2.CAP_PROP_FRAME_COUNT) / (cap.get(cv2.CAP_PROP_FPS) or 30.0)


def clips():
    C.mkdir(parents=True, exist_ok=True)
    for f in (ROOT / "data/spark_pilot3/clips").glob("*.mp4"):
        if not f.name.startswith("_"):
            shutil.copy(f, C / f.name)
    for k in P1:
        p.ff("-i", str(ROOT / f"data/spark_pilot/clips/{k}.mp4"), "-vf", "scale=iw:ih" + p3.MASK,
             "-c:v", "libx264", "-crf", "28", "-c:a", "aac", "-b:a", "64k", "-movflags", "+faststart", str(C / f"{k}.mp4"))
    print(len(names()), "clips")


def score():
    from score_clips import features
    from indexreel import match, sscd
    model, ns = sscd.load(MODEL), names()
    f = {n: features(model, C / f"{n}.mp4", D / "sscd_cache") for n in ns}
    h = {n: match.sampled_hashes(C / f"{n}.mp4") for n in ns}
    rows = {}
    for a, b in itertools.combinations(ns, 2):
        rows[f"{a}|{b}"] = {"aligned": sscd.aligned_score(f[a], f[b]), "plain": sscd.score(f[a], f[b]), "pdq": match.score(h[a], h[b])}

    def topk(col):
        out = set()
        for n in ns:
            partners = sorted((m for m in ns if m != n), key=lambda m: -rows["|".join(sorted((n, m)))][col])[:K]
            out |= {"|".join(sorted((n, m))) for m in partners}
        return out
    cand = topk("aligned") | {k for k, v in rows.items() if v["aligned"] >= THRESH}
    (D / "scores.json").write_text(json.dumps(rows, indent=1))
    (D / "candidates.json").write_text(json.dumps({"sscd": sorted(cand), "pdq_top4": sorted(topk("pdq"))}, indent=1))
    print(len(ns), "clips,", len(rows), "pairs,", len(cand), "SSCD candidates")


def oriented():
    cand = json.loads((D / "candidates.json").read_text())["sscd"]
    rng = random.Random(SEED)
    return [tuple(reversed(k.split("|"))) if rng.random() < 0.5 else tuple(k.split("|")) for k in sorted(cand)]


def run():
    t0 = time.time()
    res = D / "results.jsonl"
    done = {tuple(sorted((r["a"], r["b"]))) for r in map(json.loads, res.read_text().splitlines())} if res.exists() else set()
    old = {}
    for r in map(json.loads, (ROOT / "data/spark_pilot3/results.jsonl").read_text().splitlines()):
        old[(r["a"], r["b"])] = r
    todo, reused = [], []
    for a, b in oriented():
        if tuple(sorted((a, b))) in done:
            continue
        (reused if (a, b) in old and old[(a, b)]["answer"] else todo).append((a, b))
    with res.open("a") as fh:
        for a, b in reused:
            fh.write(json.dumps({**old[(a, b)], "reused": True}) + "\n")
    print(len(reused), "reused from pilot 3,", len(todo), "to ask", flush=True)
    p.C = C
    cli = p.client()
    ids = p.upload(cli, {n for x in todo for n in x})

    def one(x):
        a, b = x
        content = [{"type": "input_text", "text": p3.PROMPT + "\nVideo A:"}, {"type": "input_file", "file_id": ids[a]},
                   {"type": "input_text", "text": "Video B:"}, {"type": "input_file", "file_id": ids[b]}]
        raw, ans, u = p.ask(cli, content)
        return {"a": a, "b": b, "answer": ans, "raw": None if ans else raw, "input_tokens": u.input_tokens, "output_tokens": u.output_tokens}

    with ThreadPoolExecutor(4) as ex:
        for r in ex.map(one, todo):
            with res.open("a") as fh:
                fh.write(json.dumps(r) + "\n")
            a = r["answer"] or {}
            print(r["a"], r["b"], a.get("same_footage"), flush=True)
    (D / "run_seconds.txt").write_text(str(round(time.time() - t0)))


def verify():
    """Post-hoc (Addendum A): ask the neighbour pairs of every clip with two or more yes-links that were never asked."""
    rows = [json.loads(l) for l in (D / "results.jsonl").read_text().splitlines()]
    ans = {frozenset((r["a"], r["b"])): (r["answer"] or {}).get("same_footage") for r in rows}
    nb = {}
    for k, v in ans.items():
        if v == "yes":
            a, b = tuple(k)
            nb.setdefault(a, set()).add(b)
            nb.setdefault(b, set()).add(a)
    need = sorted({tuple(sorted(c)) for n in nb.values() for c in itertools.combinations(sorted(n), 2) if frozenset(c) not in ans})
    out = D / "verify.jsonl"
    if out.exists():
        need = [x for x in need if x not in {tuple(sorted((r["a"], r["b"]))) for r in map(json.loads, out.read_text().splitlines())}]
    rng = random.Random(SEED + 1)
    need = [x[::-1] if rng.random() < 0.5 else x for x in need]
    p.C = C
    cli = p.client()
    ids = p.upload(cli, {n for x in need for n in x})

    def one(x):
        a, b = x
        content = [{"type": "input_text", "text": p3.PROMPT + "\nVideo A:"}, {"type": "input_file", "file_id": ids[a]},
                   {"type": "input_text", "text": "Video B:"}, {"type": "input_file", "file_id": ids[b]}]
        raw, a2, u = p.ask(cli, content)
        return {"a": a, "b": b, "answer": a2, "raw": None if a2 else raw, "input_tokens": u.input_tokens, "output_tokens": u.output_tokens}
    with ThreadPoolExecutor(4) as ex:
        for r in ex.map(one, need):
            with out.open("a") as fh:
                fh.write(json.dumps(r) + "\n")
            print(r["a"], r["b"], (r["answer"] or {}).get("same_footage"), flush=True)


def posthoc():
    """Addendum A rule: merge on yes, a clip yes-linked to two clips that Spark says are not the same footage is a compilation."""
    ns = names()
    rows = [json.loads(l) for f in ("results.jsonl", "verify.jsonl") if (D / f).exists() for l in (D / f).read_text().splitlines()]
    ans = {frozenset((r["a"], r["b"])): (r["answer"] or {}).get("same_footage") for r in rows}
    yes = {tuple(sorted(k)) for k, v in ans.items() if v == "yes"}
    nb = {}
    for a, b in yes:
        nb.setdefault(a, set()).add(b)
        nb.setdefault(b, set()).add(a)
    hubs = {h for h, n in nb.items() if any(ans.get(frozenset(c)) in ("no", "unsure") for c in itertools.combinations(sorted(n), 2))}
    comps = components(ns, [e for e in yes if not set(e) & hubs])
    comps = [c for c in comps if not c <= hubs]
    for h in hubs:
        comps.append({h})
    found = len(comps) - len(hubs)
    same = lambda a, b: rec(a) is not None and rec(a) == rec(b)
    false = [e for e in yes if not set(e) & hubs and not same(*e)]
    print(f"\npost-hoc (Addendum A): hubs/compilations {sorted(hubs)}, recordings {found} (truth 18), false merges {false}")
    print("  families split:", [sorted(c) for c in comps if len(c) > 1 and len({rec(x) for x in c}) > 1] or "none joined wrongly")
    print("  recording sizes:", sorted(len(c) for c in comps if not c <= hubs))
    v = D / "verify.jsonl"
    vrows = [json.loads(l) for l in v.read_text().splitlines()] if v.exists() else []
    print(f"  verify calls {len(vrows)}, cost ${sum(r['input_tokens'] * 1.25 + r['output_tokens'] * 4.25 for r in vrows) / 1e6:.2f}")


def cover(span, c):
    try:
        return (float(span[1]) - float(span[0])) / duration(c)
    except (TypeError, ValueError, IndexError, ZeroDivisionError):
        return None


def components(ns, edges):
    parent = {n: n for n in ns}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for a, b in edges:
        parent[find(a)] = find(b)
    g = {}
    for n in ns:
        g.setdefault(find(n), set()).add(n)
    return list(g.values())


def report():
    ns = names()
    scores = json.loads((D / "scores.json").read_text())
    cands = json.loads((D / "candidates.json").read_text())
    rows = [json.loads(l) for l in (D / "results.jsonl").read_text().splitlines()]
    same = lambda a, b: rec(a) is not None and rec(a) == rec(b)
    key = lambda a, b: "|".join(sorted((a, b)))
    true_pairs = {key(a, b) for a, b in itertools.combinations(ns, 2) if same(a, b)}
    fams = [set(c) for c in components(ns, [tuple(k.split("|")) for k in true_pairs]) if len(c) > 1]
    print(f"{len(ns)} clips, {len(true_pairs)} true copy pairs, {len(fams)} families, {len({rec(n) for n in ns} - {None})} recordings")

    for name, cset in (("SSCD", cands["sscd"]), ("PDQ top-4", cands["pdq_top4"])):
        cs = set(cset)
        kept = len(cs & true_pairs)
        conn = [any(f <= c for c in components(sorted(f), [tuple(k.split("|")) for k in cs & true_pairs if set(k.split("|")) <= f])) for f in fams]
        print(f"1 {name}: candidates {len(cs)}/435, true copy pairs kept {kept}/{len(true_pairs)}, families connected {sum(conn)}/{len(fams)} (bar all)")

    merges, partial, review, unsure, no, wrong = [], [], [], [], [], []
    for r in rows:
        a, b, ans = r["a"], r["b"], r["answer"] or {}
        v = ans.get("same_footage")
        if v == "yes":
            ca, cb = cover(ans.get("shared_span_a"), a), cover(ans.get("shared_span_b"), b)
            if ca is None or cb is None:
                review.append((a, b))
            elif ca >= MERGE_COVER and cb >= MERGE_COVER:
                merges.append((a, b))
            else:
                partial.append((a, b))
        elif v == "unsure":
            unsure.append((a, b))
        else:
            no.append((a, b))
    false_merges = [m for m in merges if not same(*m)]
    comps = components(ns, merges)
    n_comp = 1 if any(COMPILATION in c and len(c) == 1 for c in comps) else 0
    found = len(comps) - n_comp
    cost = sum(r["input_tokens"] * 1.25 + r["output_tokens"] * 4.25 for r in rows) / 1e6
    new = [r for r in rows if not r.get("reused")]
    newcost = sum(r["input_tokens"] * 1.25 + r["output_tokens"] * 4.25 for r in new) / 1e6
    print(f"2 Spark pairs {len(rows)} ({len(rows) - len(new)} reused, {len(new)} new), cost of new calls ${newcost:.2f} (bar <=100 pairs, <=$3); all ${cost:.2f}")
    print(f"3 false merges {len(false_merges)} (bar 0): {false_merges}")
    print(f"  compilation merged with anything: {any(COMPILATION in m for m in merges)}")
    print(f"4 recordings found {found} (truth 18; 17-19 near miss)")
    split = [f for f in fams if len([c for c in comps if c & f]) > 1]
    print(f"  split families: {[sorted(f) for f in split]}")
    print(f"  merged/partial/needs-review/unsure/no: {len(merges)}/{len(partial)}/{len(review)}/{len(unsure)}/{len(no)}; unparsed {sum(r['answer'] is None for r in rows)}")
    print(f"  with needs-review merged, recordings: {len(components(ns, merges + review)) - n_comp}")
    print("  partial links:", partial)
    print("  review:", review)
    print("  yes/unsure on non-copy candidate pairs:", [(a, b, (next(r for r in rows if (r['a'], r['b']) == (a, b))['answer'] or {}).get('same_footage')) for a, b in unsure + [x for x in merges + partial + review if not same(*x)] if not same(a, b)])
    print("\nrank of true copies (aligned SSCD / PDQ), 1 = best of 29 partners:")
    for col in ("aligned", "pdq"):
        worst = []
        for n in ns:
            sibs = [m for m in ns if same(n, m) and m != n]
            if not sibs:
                continue
            order = sorted((m for m in ns if m != n), key=lambda m: -scores[key(n, m)][col])
            worst.append((max(order.index(m) + 1 for m in sibs), n))
        worst.sort(reverse=True)
        print(f"  {col}: worst-ranked sibling per clip, top 8 worst: {worst[:8]}; clips whose worst sibling is beyond rank 4: {sum(w > K for w, _ in worst)}/{len(worst)}")
    t = D / "run_seconds.txt"
    print("wall-clock for the Spark stage:", t.read_text() + " s" if t.exists() else "n/a")
    n = len(rows)
    per = cost / n if n else 0
    for N in (30, 100, 300):
        print(f"  cost at {N} clips: all pairs {N * (N - 1) // 2} calls = ${N * (N - 1) // 2 * per:.0f}; top-{K} about {N * K * 3 // 5} calls = ${N * K * 3 // 5 * per:.0f}")


if __name__ == "__main__":
    {"clips": clips, "score": score, "run": run, "verify": verify, "report": lambda: (report(), posthoc())}[sys.argv[1]]()
