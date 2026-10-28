"""H8: reasoning effort on the whole-video judge. Protocol: eval/spark-h8.md (frozen before any call at a non-default effort).

  PYTHONPATH=src:scripts python scripts/spark_h8.py run minimal|low|high   needs MODEL_API_KEY in my shell; resumes
  PYTHONPATH=src:scripts python scripts/spark_h8.py report
"""
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np

import spark_h1c as c
import spark_pilot2 as p
import spark_pilot3 as p3

D = c.D
EFFORTS = ("minimal", "low", "high")


def ask(cli, content, effort):
    for attempt in range(3):  # transport failures only; an answer is never re-asked
        try:
            text = []
            t0 = time.time()
            with cli.responses.stream(model="muse-spark-1.3", max_output_tokens=8000, reasoning={"effort": effort},
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


def run(effort):
    cli = p.client()
    res = D / f"results_{effort}.jsonl"
    done = {(r["a"], r["b"]) for r in map(json.loads, res.read_text().splitlines())} if res.exists() else set()
    todo = [(a, b) for a, b, *_ in c.pair_list() if (a, b) not in done]
    ids = {}
    for n in sorted({n for x in todo for n in x}):
        with open(c.path(n), "rb") as f:
            ids[n] = cli.files.create(purpose="user_data", file=f, expires_after={"anchor": "created_at", "seconds": 86400}).id

    def one(x):
        a, b = x
        content = [{"type": "input_text", "text": p3.PROMPT + "\nVideo A:"}, {"type": "input_file", "file_id": ids[a]},
                   {"type": "input_text", "text": "Video B:"}, {"type": "input_file", "file_id": ids[b]}]
        raw, ans, u, sec = ask(cli, content, effort)
        return {"effort": effort, "a": a, "b": b, "answer": ans, "raw": None if ans else raw, "input_tokens": u.input_tokens,
                "output_tokens": u.output_tokens, "seconds": round(sec, 1)}

    with ThreadPoolExecutor(4) as ex:
        for r in ex.map(one, todo):
            with res.open("a") as fh:
                fh.write(json.dumps(r) + "\n")
            print(effort, r["a"], r["b"], (r["answer"] or {}).get("same_footage"), r["seconds"], flush=True)


def report():
    pairs = c.pair_list()
    base = {(r["a"], r["b"]): r for r in map(json.loads, (D / "results.jsonl").read_text().splitlines()) if r["arm"] == "V"}
    arms = {"default": base}
    for e in EFFORTS:
        f = D / f"results_{e}.jsonl"
        if f.exists():
            arms[e] = {(r["a"], r["b"]): r for r in map(json.loads, f.read_text().splitlines())}
    ans = lambda r: (r["answer"] or {}).get("same_footage")
    ev = lambda r: (r["answer"] or {}).get("same_event")
    cost = lambda r: (r["input_tokens"] * 1.25 + r["output_tokens"] * 4.25) / 1e6
    pos = [x for x in pairs if x[3]]
    neg = [x for x in pairs if not x[3]]
    bc = np.mean([cost(r) for r in base.values()])
    for e, rows in arms.items():
        if len(rows) < len(pairs):
            print(e, "incomplete", len(rows))
            continue
        yes = sum(ans(rows[(a, b)]) == "yes" for a, b, *_ in pos)
        fy = [(a, b) for a, b, *_ in neg if ans(rows[(a, b)]) == "yes"]
        cc = np.mean([cost(r) for r in rows.values()])
        secs = np.mean([r.get("seconds", float("nan")) for r in rows.values()])
        verdict = "" if e in ("default", "high") else ("MEETS BAR" if yes >= 17 and not fy and cc <= 0.7 * bc else "fails")
        print(f"{e:8} yes {yes}/{len(pos)}, false yes {len(fy)}/{len(neg)}, out tokens {np.mean([r['output_tokens'] for r in rows.values()]):.0f}, "
              f"cost/pair ${cc:.4f} ({cc / bc:.0%}), seconds {secs:.1f}, unsure {sum(ans(r) == 'unsure' for r in rows.values())} {verdict} {fy[:3]}")
        if e != "default":
            ch = [(a, b, ans(base[(a, b)]), ans(rows[(a, b)])) for a, b, *_ in pairs if ans(base[(a, b)]) != ans(rows[(a, b)])]
            evc = [(a, b, ev(base[(a, b)]), ev(rows[(a, b)])) for a, b, *_ in neg if ev(base[(a, b)]) != ev(rows[(a, b)])]
            print("   same_footage changes vs default:", ch[:6], "| same_event changes on expected-no:", len(evc))


if __name__ == "__main__":
    run(sys.argv[2]) if sys.argv[1] == "run" else report()
