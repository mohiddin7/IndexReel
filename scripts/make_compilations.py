"""Synthetic compilations and single-source controls for the compilation test (eval/compilation.md).

  python scripts/make_compilations.py build|test     write data/compilation/<split>/<id>.mp4 and truth.csv

Sources are the 8 dev originals (data/gate_run/in/dev/*__orig.mp4: blocks b01-b04, families T01-T04 and N01-N04,
640x360, 5 fps, 10 s, silent). Each split has its own seed; clip ids are shuffled so they say nothing about the truth.
"""
import csv
import random
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "gate_run" / "in" / "dev"
FAMILIES = [f"{k}0{i}" for k in "TN" for i in range(1, 5)]
SRC_S = 10.0
W, H, FPS = 640, 360, 5
VARIATIONS = ["plain", "caption", "letterbox", "inset", "crossfade", "letterbox+caption"]
CONTROL_VARIATIONS = ["plain", "caption", "letterbox", "inset"]
SPLITS = {"build": (1, 12, 4), "test": (2, 24, 8)}  # seed, compilations, controls of each kind (trim, jump cut)
XFADE = 0.4  # two frames


def q(x):
    """Snap a time to the 5 fps frame grid, so the truth spans are exact."""
    return round(round(x * FPS) / FPS, 2)


def compilation_plan(rng, i):
    n = 2 + (i // len(VARIATIONS)) % 3
    if i % 4 == 0:  # a target and its own look-alike back to back: same block, same kind of scene
        k = rng.randint(1, 4)
        fams = [f"T0{k}", f"N0{k}"] + rng.sample([f for f in FAMILIES if f[1:] != f"0{k}"], n - 2)
    else:
        fams = rng.sample(FAMILIES, n)
    segs = []
    for f in fams:
        d = q(rng.uniform(3.0, 6.0))
        segs.append((f, q(rng.uniform(0, SRC_S - d - XFADE)), d))
    return segs


def trim_plan(rng):
    f = rng.choice(FAMILIES)
    d = q(rng.uniform(4.0, 8.0))
    return [(f, q(rng.uniform(0, SRC_S - d)), d)]


def jump_plan(rng):
    """Two non-adjacent pieces of one original: a gap in the source, but one recording."""
    f = rng.choice(FAMILIES)
    d1, gap, d2 = q(rng.uniform(2.6, 3.4)), q(rng.uniform(1.0, 2.0)), q(rng.uniform(2.6, 3.4))
    s1 = q(rng.uniform(0, SRC_S - d1 - gap - d2))
    return [(f, s1, d1), (f, q(s1 + d1 + gap), d2)]


def finish(variation):
    """Filter applied to the joined clip [v]; ends in [out]."""
    caption = f"subtitles={CAPTION}:force_style='Fontsize=22,BorderStyle=3,Outline=1'"
    if variation == "letterbox" or variation == "letterbox+caption":
        cap = f",{caption}" if variation == "letterbox+caption" else ""
        return (f"[v]split[a][b];[a]scale={H}:{H * 16 // 9},boxblur=20:2[bg];[b]scale={H}:-2[fg];"
                f"[bg][fg]overlay=0:(H-h)/2{cap},setsar=1[out]")
    if variation == "caption":
        return f"[v]{caption}[out]"
    if variation == "inset":
        return f"color=c=0x404040:s={W}x{H}:r={FPS}[bg];[v]scale=256:144[fg];[bg][fg]overlay=40:32:shortest=1,setsar=1[out]"
    return "[v]null[out]"


def render(segs, variation, out):
    args, chains = [], []
    for j, (f, s, d) in enumerate(segs):
        e = s + d + (XFADE if variation == "crossfade" and j < len(segs) - 1 else 0)
        args += ["-i", str(SRC / f"{f}__orig.mp4")]
        chains.append(f"[{j}:v]trim=start_frame={round(s * FPS)}:end_frame={round(e * FPS)},setpts=PTS-STARTPTS,"
                      f"scale={W}:{H},setsar=1,format=yuv420p[s{j}]")
    if variation == "crossfade" and len(segs) > 1:
        prev, t = "s0", 0.0
        for j in range(1, len(segs)):
            t += segs[j - 1][2]
            nxt = "v" if j == len(segs) - 1 else f"x{j}"
            chains.append(f"[{prev}][s{j}]xfade=transition=fade:duration={XFADE}:offset={t:.2f}[{nxt}]")
            prev = nxt
    else:
        chains.append("".join(f"[s{j}]" for j in range(len(segs))) + f"concat=n={len(segs)}:v=1:a=0[v]")
    graph = ";".join(chains + [finish(variation)])
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args, "-filter_complex", graph, "-map", "[out]", "-an",
                    "-c:v", "libx264", "-crf", "20", "-preset", "veryfast", "-pix_fmt", "yuv420p", str(out)], check=True)


def spans(segs, variation):
    """Where each segment sits in the output clip (crossfades overlap the next segment by XFADE)."""
    t, out = 0.0, []
    for f, s, d in segs:
        out.append(f"{f}:{s:.2f}-{s + d:.2f}@{t:.2f}-{t + d + (XFADE if variation == 'crossfade' and len(out) < len(segs) - 1 else 0):.2f}")
        t += d
    return ";".join(out)


def make(split):
    seed, n_comp, n_ctrl = SPLITS[split]
    rng = random.Random(seed)
    items = [("compilation", VARIATIONS[i % len(VARIATIONS)], compilation_plan(rng, i)) for i in range(n_comp)]
    items += [("control_trim", CONTROL_VARIATIONS[i % 4], trim_plan(rng)) for i in range(n_ctrl)]
    items += [("control_jumpcut", CONTROL_VARIATIONS[i % 4], jump_plan(rng)) for i in range(n_ctrl)]
    rng.shuffle(items)
    out = ROOT / "data" / "compilation" / split
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for k, (kind, variation, segs) in enumerate(items, 1):
        cid = f"c{split[0]}{k:02d}"
        render(segs, variation, out / f"{cid}.mp4")
        rows.append({"clip": cid, "split": split, "kind": kind, "variation": variation,
                     "families": ";".join(dict.fromkeys(f for f, _, _ in segs)), "segments": spans(segs, variation)})
        print(cid, kind, variation, rows[-1]["segments"], flush=True)
    with open(out / "truth.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as tmp:
        CAPTION = Path(tmp) / "caption.srt"
        CAPTION.write_text("1\n00:00:00,000 --> 00:01:00,000\nWATCH: what happened today\n")
        make(sys.argv[1])
