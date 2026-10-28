"""H1b: crop each clip to its real picture before building the H1 frame sheets. Protocol: eval/spark-h1b.md (frozen before the first call).

  PYTHONPATH=src:scripts python scripts/spark_h1b.py sheets    build the F2 sheets and the crop contact sheet (free)
  PYTHONPATH=src:scripts python scripts/spark_h1b.py run       needs MODEL_API_KEY in my shell; resumes
  PYTHONPATH=src:scripts python scripts/spark_h1b.py report
"""
import base64
import json
import sys
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np

import spark_h1 as h
import spark_pile as q
import spark_pilot2 as p
from indexreel import sscd
from score_clips import features

D = q.ROOT / "data" / "spark_h1b"


def runs(keep, gap=3):
    """Largest run of True values, allowing gaps of up to `gap`."""
    best, start, last = (0, -1, -1), None, None
    for i, k in enumerate(keep):
        if k:
            if start is None or i - last > gap + 1:
                start = i
            last = i
            if last - start > best[2] - best[1]:
                best = (0, start, last)
    return best[1], best[2]


def content_box(frames):
    """(x0, y0, x1, y1): the textured region of a clip, from 8 frames."""
    idx = np.linspace(0, len(frames) - 1, 8).round().astype(int)
    tex = np.mean([np.abs(cv2.Laplacian(cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY), cv2.CV_32F)) for i in idx], axis=0)
    tex = cv2.GaussianBlur(tex, (7, 7), 0)
    on = tex > 0.3 * np.percentile(tex, 95)
    y0, y1 = runs(on.mean(1) >= 0.10)
    x0, x1 = runs(on.mean(0) >= 0.10)
    H, W = tex.shape
    if y1 < 0 or x1 < 0:
        return 0, 0, W, H
    x0, y0, x1, y1 = max(0, x0 - 4), max(0, y0 - 4), min(W, x1 + 5), min(H, y1 + 5)
    return (x0, y0, x1, y1) if (x1 - x0) * (y1 - y0) >= 0.2 * W * H else (0, 0, W, H)


def sheets():
    (D / "sheets").mkdir(parents=True, exist_ok=True)
    model = sscd.load(q.MODEL)
    emb = {n: features(model, q.C / f"{n}.mp4", q.D / "sscd_cache") for n in q.names()}
    fr, box = {}, {}
    pairs = h.pair_list()
    for a, b, _ in pairs:
        for n in (a, b):
            if n not in fr:
                fr[n] = sscd.frames_per_second(q.C / f"{n}.mp4")
                x0, y0, x1, y1 = content_box(fr[n])
                box[n] = (x0, y0, x1, y1, fr[n][0].shape[1], fr[n][0].shape[0])
    json.dump(box, open(D / "boxes.json", "w"), indent=1)
    crop = {n: [f[b[1]:b[3], b[0]:b[2]] for f in fr[n]] for n, b in box.items()}
    for a, b, _ in pairs:
        (ap, af), (bp, _b) = emb[a], emb[b]
        sim = np.maximum(ap @ bp.T, af @ bp.T)
        cv2.imwrite(str(D / "sheets" / f"F2_{a}__{b}.jpg"), h.sheet(crop[a], crop[b], h.pick(sim), "A", "B"), [cv2.IMWRITE_JPEG_QUALITY, 85])
    changed = {n: b for n, b in box.items() if (b[2] - b[0]) * (b[3] - b[1]) < 0.95 * b[4] * b[5]}
    print(len(pairs), "sheets;", len(changed), "of", len(box), "clips cropped by more than 5% of the area")
    for n, b in sorted(changed.items()):
        print(f"  {n}: box {b[:4]} of {b[4]}x{b[5]} ({(b[2] - b[0]) * (b[3] - b[1]) / (b[4] * b[5]):.0%})")
    names = sorted(changed)[:12]
    tiles = []
    for n in names:
        f = crop[n][len(crop[n]) // 2]
        t = cv2.resize(f, (round(f.shape[1] * 180 / f.shape[0]), 180))
        cv2.putText(t, n, (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        tiles.append(t)
    if tiles:
        wmax = max(t.shape[1] for t in tiles)
        tiles = [cv2.copyMakeBorder(t, 0, 0, 0, wmax - t.shape[1], cv2.BORDER_CONSTANT) for t in tiles]
        rows = [np.hstack(tiles[i:i + 4] + [np.zeros_like(tiles[0])] * (4 - len(tiles[i:i + 4]))) for i in range(0, len(tiles), 4)]
        cv2.imwrite(str(D / "crops.jpg"), np.vstack(rows))


def run():
    cli = p.client()
    res = D / "results.jsonl"
    done = {(r["a"], r["b"]) for r in map(json.loads, res.read_text().splitlines())} if res.exists() else set()
    todo = [(a, b) for a, b, _ in h.pair_list() if (a, b) not in done]

    def one(x):
        a, b = x
        url = "data:image/jpeg;base64," + base64.b64encode((D / "sheets" / f"F2_{a}__{b}.jpg").read_bytes()).decode()
        content = [{"type": "input_text", "text": h.PROMPT}, {"type": "input_image", "image_url": url}]
        raw, ans, u = p.ask(cli, content)
        return {"arm": "F2", "a": a, "b": b, "answer": ans, "raw": None if ans else raw, "input_tokens": u.input_tokens, "output_tokens": u.output_tokens}

    with ThreadPoolExecutor(4) as ex:
        for r in ex.map(one, todo):
            with res.open("a") as fh:
                fh.write(json.dumps(r) + "\n")
            print(r["a"], r["b"], (r["answer"] or {}).get("same_footage"), flush=True)


def report():
    pairs = h.pair_list()
    ans = lambda r: (r["answer"] or {}).get("same_footage")
    f2 = {(r["a"], r["b"]): r for r in map(json.loads, (D / "results.jsonl").read_text().splitlines())}
    f = {(r["a"], r["b"]): r for r in map(json.loads, (h.D / "results.jsonl").read_text().splitlines()) if r["arm"] == "F"}
    V = {(a, b): r for a, b, r in pairs}
    pos = [(a, b) for a, b, _ in pairs if h.truth(a, b)]
    neg = [(a, b) for a, b, _ in pairs if not h.truth(a, b)]
    ok = [k for k in pos if ans(f2[k]) == "yes"]
    fy = [k for k in neg if ans(f2[k]) == "yes"]
    c = lambda rs: sum(r["input_tokens"] * 1.25 + r["output_tokens"] * 4.25 for r in rs) / 1e6 / len(rs)
    print(f"{len(pairs)} pairs ({len(pos)} yes, {len(neg)} no); unparsed {sum(r['answer'] is None for r in f2.values())}")
    print(f"F2: yes {len(ok)}/{len(pos)}, false yes {len(fy)}/{len(neg)}, unsure {sum(ans(r) == 'unsure' for r in f2.values())}, "
          f"tokens/pair {np.mean([r['input_tokens'] for r in f2.values()]):.0f}, cost/pair ${c(list(f2.values())):.4f}")
    print("   missed:", [k for k in pos if k not in ok], "| false yes:", fy)
    print(f"1 F2 yes {len(ok) / len(pos):.0%} (bar 90%), V 28/28 (within 1: {len(ok) >= 27})")
    print(f"2 F2 false yes {len(fy)} (bar 0)")
    print(f"3 F2 cost / V cost = {c(list(f2.values())) / c(list(V.values())):.0%} (bar <=50%)")
    box = json.load(open(D / "boxes.json"))
    small = [(a, b) for a, b in V if min((box[n][3] - box[n][1]) for n in (a, b)) < 120]
    print("pairs with a tile under 120 px high in original pixels:", len(small), small[:6])
    print("\nF2 differs from F:")
    for k in V:
        if ans(f2[k]) != ans(f[k]):
            print(" ", k, "truth", "yes" if h.truth(*k) else "no", "F", ans(f[k]), "F2", ans(f2[k]), "|", (f2[k]["answer"] or {}).get("unsure_because") or (f2[k]["answer"] or {}).get("observations"))


if __name__ == "__main__":
    {"sheets": sheets, "run": run, "report": report}[sys.argv[1]]()
