"""H9: prompt caching on the pair judge. Protocol: eval/spark-h9.md (frozen before the run).

  PYTHONPATH=src:scripts python scripts/spark_h9.py run S|O     needs MODEL_API_KEY in my shell; resumes
  PYTHONPATH=src:scripts python scripts/spark_h9.py report
"""
import json
import random
import re
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor

import numpy as np

import spark_h1 as h
import spark_h11 as h11
import spark_pilot2 as p
import spark_pilot3 as p3

D = h11.D
KEY = "indexreel-judge-v3"
IN, CACHED, OUT = 1.25, 0.15, 4.25


def pairs_S():
    base = [(a, b) for a, b, _ in h.pair_list()]
    random.Random(2613).shuffle(base)
    return base


def groups_O():
    deg = Counter(n for a, b, _ in h.pair_list() for n in (a, b))
    g = defaultdict(list)
    for a, b, _ in h.pair_list():
        x, y = (a, b) if (deg[a], a) >= (deg[b], b) else (b, a)
        g[x].append((x, y))
    return g


def ask(cli, content, arm):
    kw = {"prompt_cache_key": KEY, "prompt_cache_retention": "24h"} if arm == "O" else {}
    for attempt in range(3):
        try:
            text = []
            t0 = time.time()
            with cli.responses.stream(model="muse-spark-1.3", max_output_tokens=8000, reasoning={"effort": "minimal"},
                                      input=[{"type": "message", "role": "user", "content": content}], **kw) as s:
                for ev in s:
                    if ev.type == "response.output_text.delta":
                        text.append(ev.delta)
                u = s.get_final_response().usage
            raw = "".join(text)
            m = re.search(r"\{.*\}", raw, re.S)
            try:
                ans = json.loads(m.group(0)) if m else None
            except json.JSONDecodeError:
                ans = None
            return raw, ans, u, time.time() - t0
        except RuntimeError:
            if attempt == 2:
                raise


def run(arm):
    cli = p.client()
    res = D / f"results_h9_{arm}.jsonl"
    done = {(r["a"], r["b"]) for r in map(json.loads, res.read_text().splitlines())} if res.exists() else set()
    work = [[x for x in g if x not in done] for g in groups_O().values()] if arm == "O" else [[x] for x in pairs_S() if x not in done]
    work = [w for w in work if w]
    ids = {}
    for n in sorted({n for w in work for x in w for n in x}):
        with open(D / "res180" / f"{n}.mp4", "rb") as f:
            ids[n] = cli.files.create(purpose="user_data", file=f, expires_after={"anchor": "created_at", "seconds": 86400}).id

    def one(item):
        a, b = item
        content = [{"type": "input_text", "text": p3.PROMPT + "\nVideo A:"}, {"type": "input_file", "file_id": ids[a]},
                   {"type": "input_text", "text": "Video B:"}, {"type": "input_file", "file_id": ids[b]}]
        raw, ans, u, sec = ask(cli, content, arm)
        return {"arm": arm, "a": a, "b": b, "answer": ans, "raw": None if ans else raw, "input_tokens": u.input_tokens,
                "cached_tokens": u.input_tokens_details.cached_tokens, "output_tokens": u.output_tokens, "seconds": round(sec, 1)}

    def chain(w):
        out = []
        for item in w:
            r = one(item)
            r["pos"] = len(out) + 1
            out.append(r)
            with res.open("a") as fh:
                fh.write(json.dumps(r) + "\n")
        return out

    with ThreadPoolExecutor(4) as ex:
        for out in ex.map(chain, work):
            print(arm, [(r["a"], r["b"], (r["answer"] or {}).get("same_footage"), r["cached_tokens"]) for r in out][:2], flush=True)


def billed(r):
    return ((r["input_tokens"] - r["cached_tokens"]) * IN + r["cached_tokens"] * CACHED + r["output_tokens"] * OUT) / 1e6


def report():
    pairs = h.pair_list()
    pos = {tuple(sorted((a, b))) for a, b, _ in pairs if h.truth(a, b)}
    allp = {tuple(sorted((a, b))) for a, b, _ in pairs}
    arms = {}
    for arm in ("S", "O"):
        f = D / f"results_h9_{arm}.jsonl"
        if f.exists():
            arms[arm] = [json.loads(l) for l in f.read_text().splitlines()]
    base = {tuple(sorted((r["a"], r["b"]))): r for r in map(json.loads, (D / "results_res180.jsonl").read_text().splitlines())}
    ans = lambda r: (r["answer"] or {}).get("same_footage")
    for arm, rows in arms.items():
        if len(rows) < len(pairs):
            print(arm, "incomplete", len(rows))
            continue
        yes = sum(ans(r) == "yes" for r in rows if tuple(sorted((r["a"], r["b"]))) in pos)
        fy = sum(ans(r) == "yes" for r in rows if tuple(sorted((r["a"], r["b"]))) not in pos)
        tin, tc = sum(r["input_tokens"] for r in rows), sum(r["cached_tokens"] for r in rows)
        print(f"{arm}: yes {yes}/{len(pos)}, false yes {fy}/{len(allp) - len(pos)}, cached {tc / tin:.0%} of input, billed/pair ${np.mean([billed(r) for r in rows]):.4f}, "
              f"full-price/pair ${np.mean([(r['input_tokens'] * IN + r['output_tokens'] * OUT) / 1e6 for r in rows]):.4f}, seconds {np.mean([r['seconds'] for r in rows]):.1f}")
        print("   answer changes vs H11 180 px:", [(r["a"], r["b"], ans(base[tuple(sorted((r['a'], r['b'])))]), ans(r)) for r in rows
                                                 if ans(base[tuple(sorted((r["a"], r["b"])))]) != ans(r)][:6])
        if arm == "O":
            for lo, hi, name in ((1, 1, "1st"), (2, 2, "2nd"), (3, 99, "3rd+")):
                sel = [r for r in rows if lo <= r["pos"] <= hi]
                if sel:
                    print(f"   position {name}: {len(sel)} calls, cached {sum(r['cached_tokens'] for r in sel) / sum(r['input_tokens'] for r in sel):.0%} of input")
    if len(arms) == 2 and all(len(v) >= len(pairs) for v in arms.values()):
        o, s = np.mean([billed(r) for r in arms["O"]]), np.mean([billed(r) for r in arms["S"]])
        print(f"1 O billed cost / S billed cost = {o / s:.0%} (bar <= 80%)")


if __name__ == "__main__":
    run(sys.argv[2]) if sys.argv[1] == "run" else report()
