"""H16: Muse Spark Open on a Modal Shared Endpoint as the pair judge. Protocol: eval/spark-open-h16.md (frozen before the run).

  PYTHONPATH=src:scripts python scripts/spark_open_h16.py run       needs MODAL_PROXY_TOKEN_ID and MODAL_PROXY_TOKEN_SECRET in my shell and ENDPOINT_URL
  PYTHONPATH=src:scripts python scripts/spark_open_h16.py report
"""
import base64
import json
import os
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from openai import OpenAI, RateLimitError

import spark_h1 as h
import spark_h11 as h11
import spark_pilot3 as p3

D = h11.D
RES = D / "results_h16.jsonl"
MODEL = "meta-models/Muse-Spark-Open-816B-A42B"
IN, CACHED, OUT = 1.25, 0.15, 4.25


def client():
    return OpenAI(base_url=os.environ["ENDPOINT_URL"].rstrip("/") + "/v1",
                  api_key=os.environ["MODAL_PROXY_TOKEN_ID"] + "." + os.environ["MODAL_PROXY_TOKEN_SECRET"], timeout=600)


def vid(n):
    return {"type": "video_url", "video_url": {"url": "data:video/mp4;base64," + base64.b64encode((D / "res180" / f"{n}.mp4").read_bytes()).decode()}}


def ask(cli, a, b):
    content = [{"type": "text", "text": p3.PROMPT + "\nVideo A:"}, vid(a), {"type": "text", "text": "Video B:"}, vid(b)]
    for attempt in range(6):
        try:
            t0 = time.time()
            r = cli.chat.completions.create(model=MODEL, messages=[{"role": "user", "content": content}], max_tokens=4000, reasoning_effort="low")
            raw = r.choices[0].message.content or ""
            m = re.search(r"\{.*\}", raw, re.S)
            try:
                ans = json.loads(m.group(0)) if m else None
            except json.JSONDecodeError:
                ans = None
            u = r.usage
            cached = getattr(getattr(u, "prompt_tokens_details", None), "cached_tokens", 0) or 0
            return {"a": a, "b": b, "answer": ans, "raw": None if ans else raw, "input_tokens": u.prompt_tokens, "cached_tokens": cached,
                    "output_tokens": u.completion_tokens, "seconds": round(time.time() - t0, 1)}
        except RateLimitError:
            time.sleep(min(60, 2 ** attempt + random.random()))
        except Exception as e:  # transport or server error: retry, never re-ask an answered pair
            if attempt == 5:
                return {"a": a, "b": b, "answer": None, "raw": f"ERROR {type(e).__name__}: {str(e)[:200]}", "input_tokens": 0, "cached_tokens": 0, "output_tokens": 0, "seconds": 0}
            time.sleep(2 ** attempt)
    return {"a": a, "b": b, "answer": None, "raw": "ERROR rate limited", "input_tokens": 0, "cached_tokens": 0, "output_tokens": 0, "seconds": 0}


def run():
    cli = client()
    done = {(r["a"], r["b"]) for r in map(json.loads, RES.read_text().splitlines()) if r["answer"] is not None} if RES.exists() else set()
    todo = [(a, b) for a, b, _ in h.pair_list() if (a, b) not in done]
    with ThreadPoolExecutor(4) as ex:
        for r in ex.map(lambda x: ask(cli, *x), todo):
            with RES.open("a") as fh:
                fh.write(json.dumps(r) + "\n")
            print(r["a"], r["b"], (r["answer"] or {}).get("same_footage"), r["seconds"], flush=True)


def billed(r):
    return ((r["input_tokens"] - r["cached_tokens"]) * IN + r["cached_tokens"] * CACHED + r["output_tokens"] * OUT) / 1e6


def report():
    pairs = h.pair_list()
    last = {}
    for r in map(json.loads, RES.read_text().splitlines()):
        if r["answer"] is not None or (r["a"], r["b"]) not in last:
            last[(r["a"], r["b"])] = r
    pos = [(a, b) for a, b, _ in pairs if h.truth(a, b)]
    neg = [(a, b) for a, b, _ in pairs if not h.truth(a, b)]
    ans = lambda r: (r["answer"] or {}).get("same_footage")
    base = {(r["a"], r["b"]): r for r in map(json.loads, (D / "results_res180.jsonl").read_text().splitlines())}
    bad = sum(1 for k in last if last[k]["answer"] is None)
    yes = sum(ans(last[k]) == "yes" for k in pos if k in last)
    fy = [k for k in neg if k in last and ans(last[k]) == "yes"]
    rows = list(last.values())
    print(f"answered {len(last) - bad}/{len(pairs)}, unparsed or failed {bad} ({bad / len(pairs):.1%}, bar <= 3%)")
    print(f"1 yes {yes}/{len(pos)} (bar 27); 2 false yes {len(fy)}/{len(neg)} (bar 0) {fy[:4]}")
    print(f"tokens/pair in {np.mean([r['input_tokens'] for r in rows]):.0f} out {np.mean([r['output_tokens'] for r in rows]):.0f}, cost/pair ${np.mean([billed(r) for r in rows]):.4f}, "
          f"seconds/request {np.mean([r['seconds'] for r in rows]):.1f}, unsure {sum(ans(r) == 'unsure' for r in rows)}")
    diff = [(k, ans(base[k]), ans(last[k])) for k in last if k in base and ans(base[k]) != ans(last[k])]
    print(f"answers that differ from the API model (H11, 180 px): {len(diff)}", diff[:10])
    print("verdict:", "PASS" if yes >= 27 and not fy and bad / len(pairs) <= 0.03 else "FAIL")


if __name__ == "__main__":
    run() if sys.argv[1] == "run" else report()
