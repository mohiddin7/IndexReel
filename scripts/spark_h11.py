"""H11: confirm minimal effort at 240 and 180 px on the 129 H1 pairs. Protocol: eval/spark-h11.md (frozen before any call).

  PYTHONPATH=src:scripts python scripts/spark_h11.py clips
  PYTHONPATH=src:scripts python scripts/spark_h11.py run 240|180    needs MODEL_API_KEY in my shell; resumes
  PYTHONPATH=src:scripts python scripts/spark_h11.py report
"""
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import numpy as np

import spark_h1 as h
import spark_h8 as h8
import spark_pile as q
import spark_pilot2 as p
import spark_pilot3 as p3

D = q.ROOT / "data" / "spark_h11"
SIZES = (240, 180)


def clips():
    names = sorted({n for a, b, _ in h.pair_list() for n in (a, b)})
    for s in SIZES:
        (D / f"res{s}").mkdir(parents=True, exist_ok=True)
        vf = f"scale='if(gt(iw,ih),-2,{s})':'if(gt(iw,ih),{s},-2)'"
        for n in names:
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(q.C / f"{n}.mp4"), "-vf", vf, "-c:v", "libx264", "-crf", "28", "-c:a", "aac",
                            "-b:a", "64k", "-movflags", "+faststart", str(D / f"res{s}" / f"{n}.mp4")], check=True)
    print(len(names), "clips at", SIZES)


def run(size):
    cli = p.client()
    res = D / f"results_res{size}.jsonl"
    done = {(r["a"], r["b"]) for r in map(json.loads, res.read_text().splitlines())} if res.exists() else set()
    todo = [(a, b) for a, b, _ in h.pair_list() if (a, b) not in done]
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
    pairs = h.pair_list()
    base = {(a, b): r for a, b, r in pairs}
    pos = [(a, b) for a, b, _ in pairs if h.truth(a, b)]
    neg = [(a, b) for a, b, _ in pairs if not h.truth(a, b)]
    ans = lambda r: (r["answer"] or {}).get("same_footage")
    cost = lambda r: (r["input_tokens"] * 1.25 + r["output_tokens"] * 4.25) / 1e6
    bc = np.mean([cost(r) for r in base.values()])
    print(f"baseline: yes {sum(ans(base[k]) == 'yes' for k in pos)}/{len(pos)}, false yes {sum(ans(base[k]) == 'yes' for k in neg)}/{len(neg)}, cost/pair ${bc:.4f}")
    for s in SIZES:
        f = D / f"results_res{s}.jsonl"
        if not f.exists():
            continue
        rows = {(r["a"], r["b"]): r for r in map(json.loads, f.read_text().splitlines())}
        if len(rows) < len(pairs):
            print(s, "incomplete", len(rows))
            continue
        yes = sum(ans(rows[k]) == "yes" for k in pos)
        fy = [k for k in neg if ans(rows[k]) == "yes"]
        cc = np.mean([cost(r) for r in rows.values()])
        v = "MEETS BAR" if yes >= 27 and not fy and cc <= 0.5 * bc else "fails"
        print(f"{s}px: yes {yes}/{len(pos)}, false yes {len(fy)}/{len(neg)}, in tokens {np.mean([r['input_tokens'] for r in rows.values()]):.0f}, cost/pair ${cc:.4f} ({cc / bc:.0%}), "
              f"seconds {np.mean([r['seconds'] for r in rows.values()]):.1f}, unsure {sum(ans(r) == 'unsure' for r in rows.values())} {v} {fy[:4]}")
        print("   changes vs baseline:", [(a, b, ans(base[(a, b)]), ans(rows[(a, b)])) for a, b, _ in pairs if ans(base[(a, b)]) != ans(rows[(a, b)])][:10])


if __name__ == "__main__":
    {"clips": clips, "run": lambda: run(int(sys.argv[2])), "report": report}[sys.argv[1]]()
