"""H1: Spark judges 6 aligned frame pairs (picked by SSCD) instead of two whole videos. Protocol: eval/spark-h1.md (frozen before the first call).

  PYTHONPATH=src:scripts python scripts/spark_h1.py sheets      build the F and U sheets (free)
  PYTHONPATH=src:scripts python scripts/spark_h1.py run [--limit 1]   needs MODEL_API_KEY in my shell; resumes
  PYTHONPATH=src:scripts python scripts/spark_h1.py report
"""
import base64
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import numpy as np

import spark_pile as q
import spark_pilot2 as p
from indexreel import sscd
from score_clips import features

D = q.ROOT / "data" / "spark_h1"
ROWS, GAP = 6, 2
PROMPT = """You are shown one image: a sheet of 6 rows. Each row has a frame of video A on the left and a frame of video B on the right, labelled with their times in seconds. Answer with JSON only, no other text. Judge the picture, not any text drawn on it.
same_footage: do the two videos contain footage from the same original camera recording? Frames from one recording have the same viewpoint, the same objects in the same places and the same lighting, even if re-encoded, resized, cropped, mirrored, sped up, overlaid or only partly reused. Two different cameras filming the same event are same_footage no, even if the scene looks similar. If any row shows frames from one recording, answer yes. yes, no or unsure.
Return {"same_footage": ..., "rows_matching": [row numbers whose two frames come from one recording], "observations": [up to 3 short concrete things you saw], "unsure_because": "..."}."""


def truth(a, b):
    comp = {"A1", "N1", "A3"}
    ra, rb = q.rec(a), q.rec(b)
    if q.COMPILATION in (a, b):
        other = rb if a == q.COMPILATION else ra
        return other in comp
    return ra == rb


def pair_list():
    seen = {}
    for f in ("data/spark_pile/results.jsonl", "data/spark_pile/verify.jsonl", "data/spark_pilot3/results.jsonl"):
        for l in (q.ROOT / f).read_text().splitlines():
            r = json.loads(l)
            k = tuple(sorted((r["a"], r["b"])))
            if not r["answer"] or not (q.C / f"{k[0]}.mp4").exists() or not (q.C / f"{k[1]}.mp4").exists():
                continue
            if k not in seen or (f != "data/spark_pilot3/results.jsonl" and seen[k][2] == "p3"):
                seen[k] = (r["a"], r["b"], "p3" if "pilot3" in f else "pile", r)
    out = []
    for k, (a, b, src, r) in sorted(seen.items()):
        if src == "p3":
            a, b = k
            r = next(json.loads(l) for l in (q.ROOT / "data/spark_pilot3/results.jsonl").read_text().splitlines()
                     if (json.loads(l)["a"], json.loads(l)["b"]) == (a, b))
        out.append((a, b, r))
    return out


def pick(sim, n=ROWS, gap=GAP):
    sim = sim.copy()
    cells = []
    for _ in range(n):
        i, j = np.unravel_index(np.argmax(sim), sim.shape)
        if sim[i, j] < -1:
            break
        cells.append((int(i), int(j)))
        sim[max(0, i - gap + 1):i + gap, :] = -2
        sim[:, max(0, j - gap + 1):j + gap] = -2
    return cells


def sheet(fa, fb, cells, la, lb):
    rows = []
    for k, (i, j) in enumerate(cells, 1):
        pair = []
        for f, t, lab in ((fa[i], i, la), (fb[j], j, lb)):
            h, w = f.shape[:2]
            f = cv2.resize(f, (round(w * 180 / h), 180), interpolation=cv2.INTER_AREA)
            cv2.putText(f, f"{k} {lab} t={t + 0.5:.1f}s", (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
            cv2.putText(f, f"{k} {lab} t={t + 0.5:.1f}s", (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
            pair.append(f)
        rows.append(pair)
    wl = max(r[0].shape[1] for r in rows)
    wr = max(r[1].shape[1] for r in rows)
    pad = lambda f, w: cv2.copyMakeBorder(f, 0, 0, 0, w - f.shape[1], cv2.BORDER_CONSTANT, value=(40, 40, 40))
    return np.vstack([np.hstack([pad(a, wl), pad(b, wr)]) for a, b in rows])


def sheets():
    (D / "sheets").mkdir(parents=True, exist_ok=True)
    model = sscd.load(q.MODEL)
    emb = {n: features(model, q.C / f"{n}.mp4", q.D / "sscd_cache") for n in q.names()}
    fr = {}
    meta = []
    for a, b, _ in pair_list():
        for n in (a, b):
            if n not in fr:
                fr[n] = sscd.frames_per_second(q.C / f"{n}.mp4")
        (ap, af), (bp, _b) = emb[a], emb[b]
        sim = np.maximum(ap @ bp.T, af @ bp.T)
        n1, n2 = len(fr[a]), len(fr[b])
        u = lambda n: [min(n - 1, int(n * (2 * k + 1) / 12)) for k in range(ROWS)]
        for arm, cells in (("F", pick(sim)), ("U", list(zip(u(n1), u(n2))))):
            cv2.imwrite(str(D / "sheets" / f"{arm}_{a}__{b}.jpg"), sheet(fr[a], fr[b], cells, "A", "B"), [cv2.IMWRITE_JPEG_QUALITY, 85])
        meta.append((a, b))
    print(len(meta), "pairs,", 2 * len(meta), "sheets")


def run(limit):
    cli = p.client()
    res = D / "results.jsonl"
    done = {(r["arm"], r["a"], r["b"]) for r in map(json.loads, res.read_text().splitlines())} if res.exists() else set()
    todo = [(arm, a, b) for a, b, _ in pair_list() for arm in ("F", "U") if (arm, a, b) not in done][:limit]

    def one(x):
        arm, a, b = x
        url = "data:image/jpeg;base64," + base64.b64encode((D / "sheets" / f"{arm}_{a}__{b}.jpg").read_bytes()).decode()
        content = [{"type": "input_text", "text": PROMPT}, {"type": "input_image", "image_url": url}]
        raw, ans, u = p.ask(cli, content)
        return {"arm": arm, "a": a, "b": b, "answer": ans, "raw": None if ans else raw, "input_tokens": u.input_tokens, "output_tokens": u.output_tokens}

    with ThreadPoolExecutor(4) as ex:
        for r in ex.map(one, todo):
            with res.open("a") as fh:
                fh.write(json.dumps(r) + "\n")
            print(r["arm"], r["a"], r["b"], (r["answer"] or {}).get("same_footage"), r["input_tokens"], flush=True)


def cost(rows):
    return sum(r["input_tokens"] * 1.25 + r["output_tokens"] * 4.25 for r in rows) / 1e6


def report():
    pairs = pair_list()
    res = [json.loads(l) for l in (D / "results.jsonl").read_text().splitlines()]
    by = {(r["arm"], r["a"], r["b"]): r for r in res}
    V = {(a, b): r for a, b, r in pairs}
    pos = [(a, b) for a, b, _ in pairs if truth(a, b)]
    neg = [(a, b) for a, b, _ in pairs if not truth(a, b)]
    ans = lambda r: (r["answer"] or {}).get("same_footage")
    print(f"{len(pairs)} pairs: {len(pos)} expected yes, {len(neg)} expected no; unparsed F {sum(by[('F', a, b)]['answer'] is None for a, b in V if ('F', a, b) in by)}")
    stat = {}
    for arm in ("V", "F", "U"):
        get = (lambda a, b: V[(a, b)]) if arm == "V" else (lambda a, b: by.get((arm, a, b)))
        ok = [(a, b) for a, b in pos if get(a, b) and ans(get(a, b)) == "yes"]
        fy = [(a, b) for a, b in neg if get(a, b) and ans(get(a, b)) == "yes"]
        uns = sum(1 for a, b in V if get(a, b) and ans(get(a, b)) == "unsure")
        rs = [get(a, b) for a, b in V if get(a, b)]
        stat[arm] = (len(ok), len(fy), rs)
        print(f"arm {arm}: yes on expected-yes {len(ok)}/{len(pos)}, false yes {len(fy)}/{len(neg)}, unsure {uns}, "
              f"tokens/pair {sum(r['input_tokens'] for r in rs) / max(1, len(rs)):.0f}, cost/pair ${cost(rs) / max(1, len(rs)):.4f}")
        if arm != "V":
            print("   missed:", [(a, b) for a, b in pos if (a, b) not in ok][:12])
            print("   false yes:", fy)
    v, f = stat["V"], stat["F"]
    print(f"\n1 F yes {f[0]}/{len(pos)} = {f[0] / len(pos):.0%} (bar 90%), V {v[0]} (F within 1: {f[0] >= v[0] - 1})")
    print(f"2 F false yes {f[1]} (bar 0)")
    print(f"3 F cost per pair / V cost per pair = {(cost(f[2]) / len(f[2])) / (cost(v[2]) / len(v[2])):.0%} (bar <=50%)")
    print("\nV vs F disagreements:")
    for a, b, r in pairs:
        x = by.get(("F", a, b))
        if x and ans(r) != ans(x):
            print(" ", a, b, "truth", "yes" if truth(a, b) else "no", "V", ans(r), "F", ans(x), "|", (x["answer"] or {}).get("unsure_because") or (x["answer"] or {}).get("observations"))


if __name__ == "__main__":
    if sys.argv[1] == "sheets":
        sheets()
    elif sys.argv[1] == "run":
        run(int(sys.argv[3]) if len(sys.argv) > 3 else 9999)
    else:
        report()
