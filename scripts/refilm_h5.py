"""H5: the judge on real phone re-films. Protocol: eval/refilm-h5.md (frozen before any model ran on a re-film clip).

  PYTHONPATH=src:scripts python scripts/refilm_h5.py prep            re-encode the 96 re-film clips and 16 originals to 360 and 180 px (free)
  PYTHONPATH=src:scripts python scripts/refilm_h5.py run 360|180     Spark Open on Modal; needs ENDPOINT_URL and MODAL_PROXY_TOKEN_* in my shell; resumes
  PYTHONPATH=src:scripts python scripts/refilm_h5.py local           SSCD, PDQ and audio fingerprint on the same pairs (free)
  PYTHONPATH=src:scripts python scripts/refilm_h5.py report
"""
import base64
import csv
import json
import random
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from openai import RateLimitError

import spark_open_h16 as so
import spark_pilot3 as p3

ROOT = Path(__file__).resolve().parents[1]
CL = ROOT / "data" / "refilmed" / "clips"
ORIG = ROOT / "data" / "gate"
D = ROOT / "data" / "refilm_h5"
IDS = [f"b0{i}_{s}" for i in range(1, 9) for s in "TN"]
STOP_USD = 35.0


def refilms():
    """[(name, clip_id, framing, style, playlist)] from the cut manifest."""
    out = []
    for r in csv.DictReader(open(CL / "clips_manifest.csv")):
        name = Path(r.get("file") or f"{Path(r['take_file']).stem}_{r['clip_id']}.mp4").stem
        out.append((name, r["clip_id"], r["framing"], r["style"], r["playlist_played"]))
    return out


def pairs():
    return [(f"o_{o}", name, cid == o, cid, o) for name, cid, *_ in refilms() for o in IDS]


def src(n):
    return ORIG / f"{n[2:]}.mp4" if n.startswith("o_") else CL / f"{n}.mp4"


def prep():
    names = [f"o_{o}" for o in IDS] + [r[0] for r in refilms()]
    for s in (360, 180):
        (D / f"res{s}").mkdir(parents=True, exist_ok=True)
        vf = f"scale='if(gt(iw,ih),-2,{s})':'if(gt(iw,ih),{s},-2)'"
        for n in names:
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src(n)), "-vf", vf, "-c:v", "libx264", "-crf", "28", "-c:a", "aac", "-b:a", "64k",
                            "-movflags", "+faststart", str(D / f"res{s}" / f"{n}.mp4")], check=True)
    print(len(names), "clips at 360 and 180 px")


def cost(r):
    return so.billed(r)


def run(size):
    cli = so.client()
    res = D / f"results_{size}.jsonl"
    rows = [json.loads(l) for l in res.read_text().splitlines()] if res.exists() else []
    done = {(r["a"], r["b"]) for r in rows if r["answer"] is not None}
    spent = sum(cost(r) for p in (360, 180) if (D / f"results_{p}.jsonl").exists() for r in map(json.loads, (D / f"results_{p}.jsonl").read_text().splitlines()))
    todo = [(a, b) for a, b, *_ in pairs() if (a, b) not in done]
    vid = lambda n: {"type": "video_url", "video_url": {"url": "data:video/mp4;base64," + base64.b64encode((D / f"res{size}" / f"{n}.mp4").read_bytes()).decode()}}

    def one(x):
        a, b = x
        content = [{"type": "text", "text": p3.PROMPT + "\nVideo A:"}, vid(a), {"type": "text", "text": "Video B:"}, vid(b)]
        for attempt in range(6):
            try:
                t0 = time.time()
                r = cli.chat.completions.create(model=so.MODEL, messages=[{"role": "user", "content": content}], max_tokens=4000, reasoning_effort="low")
                raw = r.choices[0].message.content or ""
                m = re.search(r"\{.*\}", raw, re.S)
                try:
                    ans = json.loads(m.group(0)) if m else None
                except json.JSONDecodeError:
                    ans = None
                u = r.usage
                cached = getattr(getattr(u, "prompt_tokens_details", None), "cached_tokens", 0) or 0
                return {"size": size, "a": a, "b": b, "answer": ans, "raw": None if ans else raw, "input_tokens": u.prompt_tokens,
                        "cached_tokens": cached, "output_tokens": u.completion_tokens, "seconds": round(time.time() - t0, 1)}
            except RateLimitError:
                time.sleep(min(60, 2 ** attempt + random.random()))
            except Exception as e:  # transport or server error; an answered pair is never re-asked
                if attempt == 5:
                    return {"size": size, "a": a, "b": b, "answer": None, "raw": f"ERROR {type(e).__name__}: {str(e)[:200]}",
                            "input_tokens": 0, "cached_tokens": 0, "output_tokens": 0, "seconds": 0}
                time.sleep(2 ** attempt)

    with ThreadPoolExecutor(4) as ex:
        for r in ex.map(one, todo):
            spent += cost(r)
            with res.open("a") as fh:
                fh.write(json.dumps(r) + "\n")
            print(size, r["a"], r["b"], (r["answer"] or {}).get("same_footage"), f"${spent:.2f}", flush=True)
            if spent > STOP_USD:
                print("STOP: spend passed", STOP_USD)
                ex.shutdown(cancel_futures=True)
                break


def local():
    from indexreel import match, sscd
    from score_clips import features
    import audio_h2 as au
    import spark_pile as sp
    model = sscd.load(sp.MODEL)
    names = [f"o_{o}" for o in IDS] + [r[0] for r in refilms()]
    f = {n: features(model, src(n), D / "sscd_cache") for n in names}
    h = {n: match.sampled_hashes(src(n)) for n in names}
    a = {n: au.hashes(src(n)) for n in names}
    out = {}
    for o, r, *_ in pairs():
        out[f"{o}|{r}"] = {"sscd": sscd.aligned_score(f[o], f[r]), "pdq": match.score(h[o], h[r]),
                           "audio": au.score(a[o], a[r]) if au.count(a[o]) >= au.MIN_HASHES and au.count(a[r]) >= au.MIN_HASHES else None}
    (D / "local.json").write_text(json.dumps(out, indent=1))
    print(len(out), "pairs scored locally")


def report():
    P = pairs()
    meta = {r[0]: r for r in refilms()}
    ans = lambda r: (r["answer"] or {}).get("same_footage")
    for size in (360, 180):
        f = D / f"results_{size}.jsonl"
        if not f.exists():
            continue
        rows = {}
        for r in map(json.loads, f.read_text().splitlines()):
            if r["answer"] is not None or (r["a"], r["b"]) not in rows:
                rows[(r["a"], r["b"])] = r
        if len(rows) < len(P):
            print(f"{size}px incomplete {len(rows)}/{len(P)}")
        pos = [x for x in P if x[2] and (x[0], x[1]) in rows]
        neg = [x for x in P if not x[2] and (x[0], x[1]) in rows]
        yes = [x for x in pos if ans(rows[(x[0], x[1])]) == "yes"]
        fy = [x for x in neg if ans(rows[(x[0], x[1])]) == "yes"]
        look = [x for x in neg if x[3][:3] == x[4][:3]]
        fyl = [x for x in look if ans(rows[(x[0], x[1])]) == "yes"]
        bad = sum(rows[(x[0], x[1])]["answer"] is None for x in P if (x[0], x[1]) in rows)
        allr = list(rows.values())
        print(f"\n{size}px: answered {len(rows) - bad}/{len(P)}, failed {bad}; cost ${sum(cost(r) for r in allr):.2f}, seconds/request {np.mean([r['seconds'] for r in allr]):.1f}, unsure {sum(ans(r) == 'unsure' for r in allr)}")
        print(f"  1 own original yes {len(yes)}/{len(pos)} (bar 72/96)")
        print(f"  2 false yes {len(fy)}/{len(neg)} (bar 0), of which look-alike {len(fyl)}/{len(look)}: {[(x[1], x[4]) for x in fy[:6]]}")
        for key, idx in (("framing", 2), ("style", 3), ("playlist", 4)):
            groups = {}
            for x in pos:
                g = meta[x[1]][idx]
                groups.setdefault(g, [0, 0])
                groups[g][1] += 1
                groups[g][0] += ans(rows[(x[0], x[1])]) == "yes"
            print(f"  by {key}:", {g: f"{a}/{b}" for g, (a, b) in sorted(groups.items())})
        print("  missed:", [(x[1], ans(rows[(x[0], x[1])]), ((rows[(x[0], x[1])]["answer"] or {}).get("unsure_because") or "")[:80]) for x in pos if x not in yes][:10])
        print("  verdict:", "PASS" if len(yes) >= 72 and not fy else "FAIL")
    lf = D / "local.json"
    if lf.exists():
        L = json.loads(lf.read_text())
        for m in ("sscd", "pdq"):
            top1 = 0
            margins = []
            for name, cid, *_ in refilms():
                sc = {o: L[f"o_{o}|{name}"][m] for o in IDS}
                best = max(sc, key=sc.get)
                top1 += best == cid
                margins.append(sc[cid] - max(v for o, v in sc.items() if o != cid))
            print(f"\n{m}: true original ranked first for {top1}/{len(refilms())}; lowest margin {min(margins):.3f}, median {np.median(margins):.3f}")
        au_pos = [L[f"o_{cid}|{name}"]["audio"] for name, cid, *_ in refilms()]
        au_neg = [v["audio"] for k, v in L.items() if v["audio"] is not None and k.split("|")[0][2:] != meta[k.split("|")[1]][1]]
        print(f"audio: usable on {sum(x is not None for x in au_pos)}/{len(au_pos)} own-original pairs; own-original scores min {min([x for x in au_pos if x is not None], default=float('nan')):.4f}; "
              f"highest other-original score {max(au_neg, default=float('nan')):.4f}")


if __name__ == "__main__":
    {"prep": prep, "run": lambda: run(int(sys.argv[2])), "local": local, "report": report}[sys.argv[1]]()
