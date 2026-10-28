"""H12: one anchor clip against several candidates per request. Protocol: eval/spark-h12.md (frozen before the run).

  PYTHONPATH=src:scripts python scripts/spark_h12.py run 2|4     needs MODEL_API_KEY in my shell; resumes
  PYTHONPATH=src:scripts python scripts/spark_h12.py report
"""
import json
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np

import spark_h1 as h
import spark_h9 as h9
import spark_pilot2 as p

D = h9.D
PROMPT = """You are shown one reference video A followed by N candidate videos B1 to BN. Answer with JSON only, no other text. Judge the picture and the sound, not any text drawn on the screen.
For each candidate, decide independently whether it contains footage from the same original camera recording as A. A copy may be re-encoded, resized, cropped, mirrored, sped up, overlaid, given other music, or only partly reused. A video cut together from several recordings counts as yes if any part comes from A's recording. Two different cameras filming the same event are no. Do not compare the candidates with each other. Answer yes, no or unsure.
Return {"results": [{"candidate": "B1", "same_footage": ..., "shared_detail": "..." or null}, ...]} with one entry per candidate, in order."""


def requests(K):
    out = []
    rng = random.Random(2614)
    for anchor, items in sorted(h9.groups_O().items()):
        partners = [y for _, y in items]
        rng.shuffle(partners)
        for i in range(0, len(partners), K):
            out.append((anchor, partners[i:i + K]))
    return out


def ask(cli, content):
    for attempt in range(3):
        try:
            text = []
            t0 = time.time()
            with cli.responses.stream(model="muse-spark-1.3", max_output_tokens=8000, reasoning={"effort": "minimal"},
                                      prompt_cache_key=h9.KEY, prompt_cache_retention="24h",
                                      input=[{"type": "message", "role": "user", "content": content}]) as s:
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


def run(K):
    cli = p.client()
    res = D / f"results_h12_M{K}.jsonl"
    done = {(r["anchor"], tuple(r["candidates"])) for r in map(json.loads, res.read_text().splitlines())} if res.exists() else set()
    todo = [(a, c) for a, c in requests(K) if (a, tuple(c)) not in done]
    ids = {}
    for n in sorted({n for a, c in todo for n in [a] + c}):
        with open(D / "res180" / f"{n}.mp4", "rb") as f:
            ids[n] = cli.files.create(purpose="user_data", file=f, expires_after={"anchor": "created_at", "seconds": 86400}).id

    def one(item):
        a, cands = item
        content = [{"type": "input_text", "text": PROMPT + "\nVideo A:"}, {"type": "input_file", "file_id": ids[a]}]
        for i, c in enumerate(cands, 1):
            content += [{"type": "input_text", "text": f"Video B{i}:"}, {"type": "input_file", "file_id": ids[c]}]
        raw, ans, u, sec = ask(cli, content)
        return {"K": K, "anchor": a, "candidates": cands, "answer": ans, "raw": None if ans else raw, "input_tokens": u.input_tokens,
                "cached_tokens": u.input_tokens_details.cached_tokens, "output_tokens": u.output_tokens, "seconds": round(sec, 1)}

    with ThreadPoolExecutor(4) as ex:
        for r in ex.map(one, todo):
            with res.open("a") as fh:
                fh.write(json.dumps(r) + "\n")
            print(K, r["anchor"], len(r["candidates"]), r["cached_tokens"], flush=True)


def report():
    pairs = h.pair_list()
    truth = {frozenset((a, b)): h.truth(a, b) for a, b, _ in pairs}
    o = [json.loads(l) for l in (D / "results_h9_O.jsonl").read_text().splitlines()]
    o_ans = {frozenset((r["a"], r["b"])): (r["answer"] or {}).get("same_footage") for r in o}
    o_cost = np.mean([h9.billed(r) for r in o])
    print(f"H9 O baseline: billed/pair ${o_cost:.4f}")
    for K in (2, 4):
        f = D / f"results_h12_M{K}.jsonl"
        if not f.exists():
            continue
        rows = [json.loads(l) for l in f.read_text().splitlines()]
        need = len(requests(K))
        if len(rows) < need:
            print(f"M{K} incomplete {len(rows)}/{need}")
            continue
        got, bad, pos_hits = {}, 0, {}
        for r in rows:
            res = (r["answer"] or {}).get("results")
            if not isinstance(res, list) or len(res) != len(r["candidates"]):
                bad += 1
            for i, c in enumerate(r["candidates"], 1):
                ent = next((e for e in (res or []) if str(e.get("candidate")) == f"B{i}"), None)
                if ent:
                    got[frozenset((r["anchor"], c))] = (ent.get("same_footage"), i, len(r["candidates"]), r["anchor"], c)
        pos = [k for k, v in truth.items() if v]
        neg = [k for k, v in truth.items() if not v]
        yes = sum(got.get(k, (None,))[0] == "yes" for k in pos)
        fy = [tuple(sorted(k)) for k in neg if got.get(k, (None,))[0] == "yes"]
        missing = [k for k in truth if k not in got]
        npairs = sum(len(r["candidates"]) for r in rows)
        billed = sum(h9.billed(r) for r in rows) / npairs
        ok = yes >= 27 and not fy and billed <= 0.6 * o_cost and bad <= 1
        print(f"M{K}: requests {len(rows)}, yes {yes}/{len(pos)}, false yes {len(fy)}/{len(neg)}, missing answers {len(missing)}, malformed requests {bad}, "
              f"billed/pair ${billed:.4f} ({billed / o_cost:.0%} of O), seconds/request {np.mean([r['seconds'] for r in rows]):.1f}, seconds/pair {sum(r['seconds'] for r in rows) / npairs:.2f} "
              f"-> {'MEETS BAR' if ok else 'fails'} {fy[:4]}")
        ch = [(v[3], v[4], o_ans.get(k), v[0]) for k, v in got.items() if o_ans.get(k) != v[0]]
        print("   answer changes vs H9 O:", ch[:8], f"({len(ch)})")
        first = [v for v in got.values() if v[1] == 1]
        last = [v for v in got.values() if v[1] == v[2] and v[2] > 1]
        acc = lambda vs: sum((v[0] == "yes") == bool(truth[frozenset((v[3], v[4]))]) for v in vs) / max(1, len(vs))
        print(f"   agreement with truth by position: first {acc(first):.0%} ({len(first)}), last {acc(last):.0%} ({len(last)})")


if __name__ == "__main__":
    run(int(sys.argv[2])) if sys.argv[1] == "run" else report()
