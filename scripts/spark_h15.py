"""H15: escalate conflicts to the native-size default-effort judge. Protocol: eval/spark-h15.md (frozen before the run).

  PYTHONPATH=src:scripts python scripts/spark_h15.py run       needs MODEL_API_KEY in my shell
  PYTHONPATH=src:scripts python scripts/spark_h15.py report
"""
import itertools
import json
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

import spark_h14 as h14
import spark_pile as q
import spark_pilot2 as p
import spark_pilot3 as p3

D = h14.D
RES = D / "results_h15.jsonl"


def conflicts(ans):
    yes = {tuple(sorted(k)) for k, v in ans.items() if v == "yes"}
    nb = defaultdict(set)
    for a, b in yes:
        nb[a].add(b)
        nb[b].add(a)
    out = set()
    for h, n in nb.items():
        for c in itertools.combinations(sorted(n), 2):
            if ans.get(frozenset(c)) in ("no", "unsure"):
                out.add(tuple(sorted(c)))
    return sorted(out)


def run():
    cli = p.client()
    ans = h14.asked()
    done = {(r["a"], r["b"]) for r in map(json.loads, RES.read_text().splitlines())} if RES.exists() else set()
    todo = [x for c in conflicts(ans) for x in (c, c[::-1]) if x not in done]
    ids = {}
    for n in sorted({n for x in todo for n in x}):
        with open(q.C / f"{n}.mp4", "rb") as f:
            ids[n] = cli.files.create(purpose="user_data", file=f, expires_after={"anchor": "created_at", "seconds": 86400}).id

    def one(x):
        a, b = x
        content = [{"type": "input_text", "text": p3.PROMPT + "\nVideo A:"}, {"type": "input_file", "file_id": ids[a]},
                   {"type": "input_text", "text": "Video B:"}, {"type": "input_file", "file_id": ids[b]}]
        raw, a2, u = p.ask(cli, content)
        return {"a": a, "b": b, "answer": a2, "raw": None if a2 else raw, "input_tokens": u.input_tokens, "output_tokens": u.output_tokens}

    with ThreadPoolExecutor(4) as ex:
        for r in ex.map(one, todo):
            with RES.open("a") as fh:
                fh.write(json.dumps(r) + "\n")
            print(r["a"], r["b"], (r["answer"] or {}).get("same_footage"), flush=True)


def report():
    ns = q.names()
    ans = h14.asked()
    rows = [json.loads(l) for l in RES.read_text().splitlines()]
    full = defaultdict(list)
    for r in rows:
        full[tuple(sorted((r["a"], r["b"])))].append((r["answer"] or {}).get("same_footage"))
    cs = conflicts(ans)
    cleared = {c for c in cs if "yes" in full.get(c, [])}
    stand = [c for c in cs if c not in cleared]
    ans2 = dict(ans)
    for c in cleared:
        ans2[frozenset(c)] = "yes"
    yes = {tuple(sorted(k)) for k, v in ans2.items() if v == "yes"}
    nb = defaultdict(set)
    for a, b in yes:
        nb[a].add(b)
        nb[b].add(a)
    hubs = {h for h, n in nb.items() if any(c in stand for c in (tuple(sorted(x)) for x in itertools.combinations(sorted(n), 2)))}
    comps = [c for c in q.components(ns, [e for e in yes if not set(e) & hubs]) if not c <= hubs]
    same = lambda a, b: q.rec(a) is not None and q.rec(a) == q.rec(b)
    false = [e for e in yes if not set(e) & hubs and not same(*e)]
    cost = sum(r["input_tokens"] * 1.25 + r["output_tokens"] * 4.25 for r in rows) / 1e6
    print(f"conflicts raised {len(cs)}, cleared {len(cleared)}, standing {len(stand)}; flagged hubs {sorted(hubs)}")
    print(f"1 recordings {len(comps)} (bar 18): {'pass' if len(comps) == 18 else 'FAIL'}")
    print(f"2 false merges {len(false)} {false}; compilation merged with anything: {any(q.COMPILATION in e and q.COMPILATION not in hubs for e in yes)}")
    print(f"3 extra cost ${cost:.2f} (bar <= $0.50)")
    print("cleared:", sorted((c, full[c]) for c in cleared))
    print("standing:", sorted((c, full[c]) for c in stand)[:14])
    print("recording sizes:", sorted(len(c) for c in comps))


if __name__ == "__main__":
    run() if sys.argv[1] == "run" else report()
