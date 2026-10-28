"""H14: the whole cheap harness on the pile. Protocol: eval/spark-h14.md (frozen before the run).

  PYTHONPATH=src:scripts python scripts/spark_h14.py run      needs MODEL_API_KEY in my shell; round 1 then the verify round
  PYTHONPATH=src:scripts python scripts/spark_h14.py report
"""
import itertools
import json
import random
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor

import spark_h12 as h12
import spark_h9 as h9
import spark_pile as q
import spark_pilot2 as p

D = q.ROOT / "data" / "spark_h14"
RES = D / "results.jsonl"
K = 4


def groups(pairs):
    deg = Counter(n for a, b in pairs for n in (a, b))
    g = defaultdict(list)
    for a, b in pairs:
        x, y = (a, b) if (deg[a], a) >= (deg[b], b) else (b, a)
        g[x].append(y)
    return g


def chunks(pairs, seed):
    rng = random.Random(seed)
    out = []
    for anchor, partners in sorted(groups(pairs).items()):
        partners = sorted(partners)
        rng.shuffle(partners)
        out += [(anchor, partners[i:i + K]) for i in range(0, len(partners), K)]
    return out


def asked():
    if not RES.exists():
        return {}
    ans = {}
    for r in map(json.loads, RES.read_text().splitlines()):
        for i, c in enumerate(r["candidates"], 1):
            ent = next((e for e in ((r["answer"] or {}).get("results") or []) if str(e.get("candidate")) == f"B{i}"), None)
            ans[frozenset((r["anchor"], c))] = ent.get("same_footage") if ent else None
    return ans


def verify_pairs():
    ans = asked()
    yes = {k for k, v in ans.items() if v == "yes"}
    nb = defaultdict(set)
    for k in yes:
        a, b = tuple(k)
        nb[a].add(b)
        nb[b].add(a)
    return sorted({tuple(sorted(c)) for n in nb.values() for c in itertools.combinations(sorted(n), 2) if frozenset(c) not in ans})


def ask_all(cli, work, ids):
    def one(item):
        a, cands = item
        content = [{"type": "input_text", "text": h12.PROMPT + "\nVideo A:"}, {"type": "input_file", "file_id": ids[a]}]
        for i, c in enumerate(cands, 1):
            content += [{"type": "input_text", "text": f"Video B{i}:"}, {"type": "input_file", "file_id": ids[c]}]
        raw, ans, u, sec = h12.ask(cli, content)
        return {"anchor": a, "candidates": cands, "answer": ans, "raw": None if ans else raw, "input_tokens": u.input_tokens,
                "cached_tokens": u.input_tokens_details.cached_tokens, "output_tokens": u.output_tokens, "seconds": round(sec, 1)}
    with ThreadPoolExecutor(4) as ex:
        for r in ex.map(one, work):
            with RES.open("a") as fh:
                fh.write(json.dumps(r) + "\n")
            print(r["anchor"], len(r["candidates"]), flush=True)


def run():
    D.mkdir(exist_ok=True)
    cli = p.client()
    cands = [tuple(k.split("|")) for k in json.loads((q.D / "candidates.json").read_text())["sscd"]]
    ids = {}
    for n in q.names():
        with open(q.ROOT / "data/spark_h11/res180" / f"{n}.mp4", "rb") as f:
            ids[n] = cli.files.create(purpose="user_data", file=f, expires_after={"anchor": "created_at", "seconds": 86400}).id
    done = asked()
    todo = [(a, c) for a, c in chunks(cands, 2615) if not all(frozenset((a, x)) in done for x in c)]
    ask_all(cli, todo, ids)
    vp = [x for x in verify_pairs()]
    print("verify pairs", len(vp))
    done = asked()
    if vp:
        ask_all(cli, [(a, c) for a, c in chunks(vp, 2616) if not all(frozenset((a, x)) in done for x in c)], ids)


def report():
    ns = q.names()
    rows = [json.loads(l) for l in RES.read_text().splitlines()]
    ans = asked()
    yes = {tuple(sorted(k)) for k, v in ans.items() if v == "yes"}
    nb = defaultdict(set)
    for a, b in yes:
        nb[a].add(b)
        nb[b].add(a)
    hubs = {h for h, n in nb.items() if any(ans.get(frozenset(c)) in ("no", "unsure") for c in itertools.combinations(sorted(n), 2))}
    comps = [c for c in __import__("spark_pile").components(ns, [e for e in yes if not set(e) & hubs]) if not c <= hubs]
    found = len(comps)
    same = lambda a, b: q.rec(a) is not None and q.rec(a) == q.rec(b)
    false = [e for e in yes if not set(e) & hubs and not same(*e)]
    cost = sum(h9.billed(r) for r in rows)
    old = json.loads(json.dumps(sorted(json.loads((q.D / "candidates.json").read_text())["sscd"])))
    pile_ans = {frozenset((r["a"], r["b"])): (r["answer"] or {}).get("same_footage") for r in map(json.loads, (q.D / "results.jsonl").read_text().splitlines())}
    diff = [(tuple(sorted(k)), pile_ans[k], ans.get(k)) for k in pile_ans if k in ans and pile_ans[k] != ans[k]]
    print(f"requests {len(rows)}, pairs answered {len(ans)}, malformed {sum(1 for r in rows if not isinstance((r['answer'] or {}).get('results'), list))}, seconds {sum(r['seconds'] for r in rows):.0f}")
    print(f"hubs/compilations {sorted(hubs)}; recordings found {found} (truth 18); false merges {len(false)} {false}")
    print(f"1 recordings {found} (bar 18): {'pass' if found == 18 else 'FAIL'}")
    print(f"2 false merges {len(false)}, compilation merged with anything: {any(q.COMPILATION in e and q.COMPILATION not in hubs for e in yes)}")
    print(f"3 billed cost ${cost:.2f} (bar <= $0.60; pile test $1.53)")
    print("answers that differ from the pile test:", diff[:8], f"({len(diff)} of {len(pile_ans)})")
    print("recording sizes:", sorted(len(c) for c in comps))


if __name__ == "__main__":
    run() if sys.argv[1] == "run" else report()
