"""H1c: build new layout edits, run V (whole video) and F (frame sheet) on them, score the routing policies. Protocol: eval/spark-h1c.md (frozen before the first call).

  PYTHONPATH=src:scripts python scripts/spark_h1c.py clips     build the 12 edits and the sheets (free)
  PYTHONPATH=src:scripts python scripts/spark_h1c.py run       needs MODEL_API_KEY in my shell; resumes
  PYTHONPATH=src:scripts python scripts/spark_h1c.py report
"""
import base64
import itertools
import json
import random
import sys
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np

import spark_h1 as h
import spark_pile as q
import spark_pilot2 as p
import spark_pilot3 as p3
from indexreel import sscd
from score_clips import features

D = q.ROOT / "data" / "spark_h1c"
CL = D / "clips"
ENC = ["-c:v", "libx264", "-crf", "28", "-c:a", "aac", "-b:a", "64k", "-movflags", "+faststart", "-t", "20"]
EDITS = ([("vz", x, None) for x in ("A2", "A4", "B1")] + [("vb", x, None) for x in ("N1", "N4", "B2")]
         + [("pp", "A2", "N3"), ("pp", "A4", "N1"), ("pp", "B1", "N5")] + [("ss", "B1", "N4"), ("ss", "A2", "N5"), ("ss", "A4", "N3")])
SEED = 2612


def name(k, x, y):
    return f"H_{k}_{x}" + (f"_{y}" if y else "")


def src(n):
    return q.C / f"{n}.mp4"


def build():
    CL.mkdir(parents=True, exist_ok=True)
    for k, x, y in EDITS:
        out = str(CL / f"{name(k, x, y)}.mp4")
        if k == "vz":
            p.ff("-i", str(src(x)), "-vf", "crop=ih*9/16:ih,scale=360:640", *ENC, out)
        elif k == "vb":
            p.ff("-i", str(src(x)), "-filter_complex",
                 "[0:v]split[a][b];[a]scale=360:640:force_original_aspect_ratio=increase,crop=360:640,boxblur=20:2[bg];[b]scale=270:-2[fg];"
                 "[bg][fg]overlay=(W-w)/2:(H-h)/2,drawbox=y=ih-70:w=iw:h=70:color=black@0.8:t=fill,drawbox=x=20:y=60:w=200:h=30:color=white@0.9:t=fill",
                 *ENC, out)
        elif k == "pp":
            p.ff("-i", str(src(y)), "-i", str(src(x)), "-filter_complex",
                 "[0:v]scale=640:360[bg];[1:v]scale=240:-2[fg];[bg][fg]overlay=W-w-16:H-h-16[v]", "-map", "[v]", "-map", "1:a?", "-shortest", *ENC, out)
        else:
            p.ff("-i", str(src(x)), "-i", str(src(y)), "-filter_complex",
                 "[0:v]scale=320:360:force_original_aspect_ratio=increase,crop=320:360[l];[1:v]scale=320:360:force_original_aspect_ratio=increase,crop=320:360[r];[l][r]hstack[v]",
                 "-map", "[v]", "-map", "0:a?", "-shortest", *ENC, out)
    print(len(list(CL.glob("*.mp4"))), "clips")


def path(n):
    return CL / f"{n}.mp4" if n.startswith("H_") else src(n)


def pair_list():
    rng = random.Random(SEED)
    pile = q.names()
    out = []
    for k, x, y in EDITS:
        e = name(k, x, y)
        srcs = [x] + ([y] if y else [])
        rec = {q.rec(s) for s in srcs}
        excl = {c for c in pile if q.rec(c) in rec or c == q.COMPILATION}
        hard = [c for c in pile if c not in excl and (
            (any(s.startswith("A") for s in srcs) and q.rec(c) in ("A1", "A2", "A3", "A4")) or
            (any(s.startswith("B") for s in srcs) and q.rec(c) in ("B1", "B2")) or
            (any(s.startswith("N") for s in srcs) and (q.rec(c) or "").startswith("N")))]
        hard = sorted({q.rec(c) for c in hard} - {None})
        rng.shuffle(hard)
        hard = hard[:3]
        rest = sorted({q.rec(c) for c in pile if c not in excl} - set(hard) - {None})
        rng.shuffle(rest)
        for c, yes in [(s, True) for s in srcs] + [(c, False) for c in hard + rest[:3]]:
            a, b = (c, e) if rng.random() < 0.5 else (e, c)
            out.append((a, b, e, yes, k))
    return out


def sheets():
    (D / "sheets").mkdir(parents=True, exist_ok=True)
    model = sscd.load(q.MODEL)
    emb, fr = {}, {}
    for a, b, *_ in pair_list():
        for n in (a, b):
            if n not in emb:
                emb[n] = features(model, path(n), D / "sscd_cache")
                fr[n] = sscd.frames_per_second(path(n))
    for a, b, *_ in pair_list():
        (ap, af), (bp, _b) = emb[a], emb[b]
        sim = np.maximum(ap @ bp.T, af @ bp.T)
        cv2.imwrite(str(D / "sheets" / f"F_{a}__{b}.jpg"), h.sheet(fr[a], fr[b], h.pick(sim), "A", "B"), [cv2.IMWRITE_JPEG_QUALITY, 85])
    print(len(pair_list()), "pairs")


def run():
    cli = p.client()
    res = D / "results.jsonl"
    done = {(r["arm"], r["a"], r["b"]) for r in map(json.loads, res.read_text().splitlines())} if res.exists() else set()
    todo = [(arm, a, b) for a, b, *_ in pair_list() for arm in ("F", "V") if (arm, a, b) not in done]
    ids = {}
    vids = {n for arm, a, b in todo if arm == "V" for n in (a, b)}
    for n in sorted(vids):
        with open(path(n), "rb") as f:
            ids[n] = cli.files.create(purpose="user_data", file=f, expires_after={"anchor": "created_at", "seconds": 86400}).id

    def one(x):
        arm, a, b = x
        if arm == "F":
            url = "data:image/jpeg;base64," + base64.b64encode((D / "sheets" / f"F_{a}__{b}.jpg").read_bytes()).decode()
            content = [{"type": "input_text", "text": h.PROMPT}, {"type": "input_image", "image_url": url}]
        else:
            content = [{"type": "input_text", "text": p3.PROMPT + "\nVideo A:"}, {"type": "input_file", "file_id": ids[a]},
                       {"type": "input_text", "text": "Video B:"}, {"type": "input_file", "file_id": ids[b]}]
        raw, ans, u = p.ask(cli, content)
        return {"arm": arm, "a": a, "b": b, "answer": ans, "raw": None if ans else raw, "input_tokens": u.input_tokens, "output_tokens": u.output_tokens}

    with ThreadPoolExecutor(4) as ex:
        for r in ex.map(one, todo):
            with res.open("a") as fh:
                fh.write(json.dumps(r) + "\n")
            print(r["arm"], r["a"], r["b"], (r["answer"] or {}).get("same_footage"), flush=True)


def report():
    pairs = pair_list()
    rows = {(r["arm"], r["a"], r["b"]): r for r in map(json.loads, (D / "results.jsonl").read_text().splitlines())}
    ans = lambda r: (r["answer"] or {}).get("same_footage")
    cost = lambda r: (r["input_tokens"] * 1.25 + r["output_tokens"] * 4.25) / 1e6
    portrait = lambda n: (lambda c: c.get(cv2.CAP_PROP_FRAME_HEIGHT) > c.get(cv2.CAP_PROP_FRAME_WIDTH))(cv2.VideoCapture(str(path(n))))
    pos = [x for x in pairs if x[3]]
    neg = [x for x in pairs if not x[3]]
    print(f"{len(pairs)} pairs: {len(pos)} expected yes, {len(neg)} expected no; unparsed {sum(r['answer'] is None for r in rows.values())}")
    Vc = np.mean([cost(rows[('V', a, b)]) for a, b, *_ in pairs])

    def policy(name):
        fin, spent, tovid = {}, 0.0, 0
        for a, b, *_ in pairs:
            F, V = rows[("F", a, b)], rows[("V", a, b)]
            if name == "V":
                fin[(a, b)], spent, tovid = ans(V), spent + cost(V), tovid + 1
            elif name == "F":
                fin[(a, b)], spent = ans(F), spent + cost(F)
            elif name == "R":
                if portrait(a) or portrait(b):
                    fin[(a, b)], spent, tovid = ans(V), spent + cost(V), tovid + 1
                else:
                    fin[(a, b)], spent = ans(F), spent + cost(F)
            elif name == "C":
                spent += cost(F)
                if ans(F) in ("yes", "unsure"):
                    fin[(a, b)], spent, tovid = ans(V), spent + cost(V), tovid + 1
                else:
                    fin[(a, b)] = ans(F)
            else:  # RC
                if portrait(a) or portrait(b):
                    fin[(a, b)], spent, tovid = ans(V), spent + cost(V), tovid + 1
                else:
                    spent += cost(F)
                    if ans(F) in ("yes", "unsure"):
                        fin[(a, b)], spent, tovid = ans(V), spent + cost(V), tovid + 1
                    else:
                        fin[(a, b)] = ans(F)
        yes = sum(fin[(a, b)] == "yes" for a, b, _, y, _ in pos)
        fy = [(a, b) for a, b, _, y, _ in neg if fin[(a, b)] == "yes"]
        c = spent / len(pairs) / Vc
        ok = yes / len(pos) >= 0.9 and not fy and c <= 0.70
        print(f"{name:3} yes {yes}/{len(pos)}, false yes {len(fy)}/{len(neg)}, to video {tovid}/{len(pairs)}, cost {c:.0%} of V -> {'MEETS BAR' if ok else 'fails'}  {fy[:4]}")

    for n in ("V", "F", "R", "C", "RC"):
        policy(n)
    print("\narm F alone per edit type (yes on expected-yes / false yes on expected-no):")
    for k in ("vz", "vb", "pp", "ss"):
        p_ = [x for x in pos if x[4] == k]
        n_ = [x for x in neg if x[4] == k]
        print(f"  {k}: yes {sum(ans(rows[('F', a, b)]) == 'yes' for a, b, *_ in p_)}/{len(p_)}, false yes {sum(ans(rows[('F', a, b)]) == 'yes' for a, b, *_ in n_)}/{len(n_)};"
              f" V yes {sum(ans(rows[('V', a, b)]) == 'yes' for a, b, *_ in p_)}/{len(p_)}, false yes {sum(ans(rows[('V', a, b)]) == 'yes' for a, b, *_ in n_)}/{len(n_)}")
    print("\nfalse yes detail:")
    for arm in ("F", "V"):
        for a, b, e, y, k in neg:
            r = rows[(arm, a, b)]
            if ans(r) == "yes":
                print(" ", arm, k, a, b, "|", (r["answer"] or {}).get("observations"))
    print("\nmissed expected-yes:")
    for arm in ("F", "V"):
        for a, b, e, y, k in pos:
            r = rows[(arm, a, b)]
            if ans(r) != "yes":
                print(" ", arm, k, a, b, ans(r), "|", (r["answer"] or {}).get("unsure_because"))


if __name__ == "__main__":
    {"clips": lambda: (build(), sheets()), "run": run, "report": report}[sys.argv[1]]()
