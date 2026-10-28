"""H10: judge the H1c pairs at reduced video resolution. Protocol: eval/spark-h10.md (frozen before any call at these sizes).

  PYTHONPATH=src:scripts python scripts/spark_h10.py clips         re-encode every clip at S = 240, 180, 120 (free)
  PYTHONPATH=src:scripts python scripts/spark_h10.py run 240       needs MODEL_API_KEY in my shell; resumes
  PYTHONPATH=src:scripts python scripts/spark_h10.py report
"""
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import numpy as np

import spark_h1c as c
import spark_h8 as h8
import spark_pilot2 as p
import spark_pilot3 as p3

D = c.D
SIZES = (240, 180, 120)


def clips():
    names = sorted({n for a, b, *_ in c.pair_list() for n in (a, b)})
    for s in SIZES:
        (D / f"res{s}").mkdir(exist_ok=True)
        vf = f"scale='if(gt(iw,ih),-2,{s})':'if(gt(iw,ih),{s},-2)'"
        for n in names:
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(c.path(n)), "-vf", vf, "-c:v", "libx264", "-crf", "28", "-c:a", "aac", "-b:a", "64k",
                            "-movflags", "+faststart", str(D / f"res{s}" / f"{n}.mp4")], check=True)
    print(len(names), "clips at", SIZES)


def run(size):
    cli = p.client()
    res = D / f"results_res{size}.jsonl"
    done = {(r["a"], r["b"]) for r in map(json.loads, res.read_text().splitlines())} if res.exists() else set()
    todo = [(a, b) for a, b, *_ in c.pair_list() if (a, b) not in done]
    ids = {}
    for n in sorted({n for x in todo for n in x}):
        with open(D / f"res{size}" / f"{n}.mp4", "rb") as f:
            ids[n] = cli.files.create(purpose="user_data", file=f, expires_after={"anchor": "created_at", "seconds": 86400}).id

    def one(x):
        a, b = x
        content = [{"type": "input_text", "text": p3.PROMPT + "\nVideo A:"}, {"type": "input_file", "file_id": ids[a]},
                   {"type": "input_text", "text": "Video B:"}, {"type": "input_file", "file_id": ids[b]}]
        raw, ans, u, sec = h8.ask(cli, content, "minimal")
        return {"size": size, "a": a, "b": b, "answer": ans, "raw": None if ans else raw, "input_tokens": u.input_tokens,
                "output_tokens": u.output_tokens, "seconds": round(sec, 1)}

    with ThreadPoolExecutor(4) as ex:
        for r in ex.map(one, todo):
            with res.open("a") as fh:
                fh.write(json.dumps(r) + "\n")
            print(size, r["a"], r["b"], (r["answer"] or {}).get("same_footage"), flush=True)


def report():
    pairs = c.pair_list()
    kind = {(a, b): k for a, b, e, y, k in pairs}
    load = lambda f: {(r["a"], r["b"]): r for r in map(json.loads, (D / f).read_text().splitlines())}
    base = {k: r for k, r in load("results.jsonl").items() if r["arm"] == "V"}
    arms = {"default 360": base, "minimal 360": load("results_minimal.jsonl")}
    for s in SIZES:
        if (D / f"results_res{s}.jsonl").exists():
            arms[f"minimal {s}"] = load(f"results_res{s}.jsonl")
    ans = lambda r: (r["answer"] or {}).get("same_footage")
    cost = lambda r: (r["input_tokens"] * 1.25 + r["output_tokens"] * 4.25) / 1e6
    pos = [x for x in pairs if x[3]]
    neg = [x for x in pairs if not x[3]]
    bc = np.mean([cost(r) for r in base.values()])
    for name, rows in arms.items():
        if len(rows) < len(pairs):
            print(name, "incomplete", len(rows))
            continue
        yes = sum(ans(rows[(a, b)]) == "yes" for a, b, *_ in pos)
        fy = [(a, b, kind[(a, b)]) for a, b, *_ in neg if ans(rows[(a, b)]) == "yes"]
        cc = np.mean([cost(r) for r in rows.values()])
        v = "" if "360" in name else ("MEETS BAR" if yes >= 17 and not fy and cc <= 0.5 * bc else "fails")
        print(f"{name:12} yes {yes}/{len(pos)}, false yes {len(fy)}/{len(neg)}, in tokens {np.mean([r['input_tokens'] for r in rows.values()]):.0f}, "
              f"cost/pair ${cc:.4f} ({cc / bc:.0%}), seconds {np.mean([r.get('seconds', float('nan')) for r in rows.values()]):.1f} {v} {fy[:3]}")
        if "360" not in name:
            print("   changes vs default 360:", [(a, b, kind[(a, b)], ans(base[(a, b)]), ans(rows[(a, b)])) for a, b, *_ in pairs if ans(base[(a, b)]) != ans(rows[(a, b)])][:8])


if __name__ == "__main__":
    {"clips": clips, "run": lambda: run(int(sys.argv[2])), "report": report}[sys.argv[1]]()
