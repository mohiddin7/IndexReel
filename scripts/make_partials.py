"""Synthetic partial copies and single-recording controls for the partial-copy test (eval/partial.md).

  python scripts/make_partials.py build|test     write data/partial/<split>/<id>.mp4 and truth.csv

A partial copy is a segment of one dev original joined to filler: footage from my own phone clips, which are never
clips of the run, so the rest of the copy is a recording the run does not hold. Controls are trims and jump cuts of
one original (as in eval/compilation.md) and containers (a whole original plus filler, reported only). The dev
originals are data/gate_run/in/dev/*__orig.mp4 (640x360, 5 fps, 10 s, silent). Each split has its own seed and its
own filler clips; clip ids are shuffled so they say nothing about the truth.
"""
import csv
import random
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_compilations as mc  # noqa: E402  (same originals, frame grid, variations and renderer settings)

ROOT = mc.ROOT
OWN = ROOT / "data" / "iphone_by_me"
FILLER = {"build": ["IMG_2851", "IMG_2854", "IMG_2858", "IMG_3647", "IMG_3800", "IMG_3821", "IMG_4018"],
          "test": ["IMG_4084", "IMG_4138", "IMG_4436", "IMG_6171", "IMG_7309", "IMG_9427", "IMG_9458"]}
SPLITS = {"build": (11, 12, 4, 4, 2), "test": (12, 24, 8, 8, 4)}  # seed, partial copies, trims, jump cuts, containers
SEG_S = [3.0, 5.0, 7.0]
POSITIONS = ["after", "before", "both"]  # where the filler goes
VARIATIONS = mc.CONTROL_VARIATIONS  # plain, caption, letterbox, inset
W, H, FPS, q = mc.W, mc.H, mc.FPS, mc.q


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(out)


def filler_piece(rng, pool, lengths, d, avoid=()):
    """(clip, start, d): d seconds of one filler clip, never the one in avoid."""
    name = rng.choice([p for p in pool if p not in avoid])
    return (name, q(rng.uniform(0, lengths[name] - d - 0.5)), d)


def partial_plan(rng, i, pool, lengths):
    fam, d = rng.choice(mc.FAMILIES), SEG_S[i % 3]
    seg = ("orig", fam, q(rng.uniform(0, mc.SRC_S - d)), d)
    pos = POSITIONS[(i // 3) % 3]
    total = q(d * rng.uniform(0.4, 1.6))
    if pos == "both":
        first = q(total * rng.uniform(0.3, 0.7))
        p1 = filler_piece(rng, pool, lengths, first)
        p2 = filler_piece(rng, pool, lengths, q(total - first), avoid=(p1[0],))
        return [("filler", *p1), seg, ("filler", *p2)], pos
    piece = ("filler", *filler_piece(rng, pool, lengths, total))
    return ([seg, piece] if pos == "after" else [piece, seg]), pos


def container_plan(rng, i, pool, lengths):
    fam = rng.choice(mc.FAMILIES)
    piece = ("filler", *filler_piece(rng, pool, lengths, q(rng.uniform(3.0, 6.0))))
    seg = ("orig", fam, 0.0, mc.SRC_S)
    return ([seg, piece] if i % 2 == 0 else [piece, seg]), "after" if i % 2 == 0 else "before"


def render(pieces, variation, out):
    args, chains = [], []
    for j, (kind, name, s, d) in enumerate(pieces):
        src = mc.SRC / f"{name}__orig.mp4" if kind == "orig" else OWN / f"{name}.MOV"
        args += ["-ss", f"{s:.2f}", "-t", f"{d:.2f}", "-i", str(src)]
        chains.append(f"[{j}:v]fps={FPS},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,"
                      f"trim=end_frame={round(d * FPS)},setpts=PTS-STARTPTS,format=yuv420p[s{j}]")
    chains.append("".join(f"[s{j}]" for j in range(len(pieces))) + f"concat=n={len(pieces)}:v=1:a=0[v]")
    graph = ";".join(chains + [mc.finish(variation)])
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", *args, "-filter_complex", graph, "-map", "[out]", "-an",
                    "-c:v", "libx264", "-crf", "20", "-preset", "veryfast", "-pix_fmt", "yuv420p", str(out)], check=True)


def spans(pieces):
    """Truth columns: the original's segments and the filler pieces, each `name:src_start-src_end@clip_start-clip_end`."""
    t, seg, fill = 0.0, [], []
    for kind, name, s, d in pieces:
        (seg if kind == "orig" else fill).append(f"{name}:{s:.2f}-{s + d:.2f}@{t:.2f}-{t + d:.2f}")
        t += d
    return ";".join(seg), ";".join(fill)


def make(split):
    seed, n_part, n_trim, n_jump, n_cont = SPLITS[split]
    rng = random.Random(seed)
    pool = FILLER[split]
    lengths = {p: duration(OWN / f"{p}.MOV") for p in pool}
    items = []
    for i in range(n_part):
        pieces, pos = partial_plan(rng, i, pool, lengths)
        items.append(("partial", VARIATIONS[i % 4], pos, pieces))
    items += [("control_trim", VARIATIONS[i % 4], "", [("orig", *s) for s in mc.trim_plan(rng)]) for i in range(n_trim)]
    items += [("control_jumpcut", VARIATIONS[i % 4], "", [("orig", *s) for s in mc.jump_plan(rng)]) for i in range(n_jump)]
    for i in range(n_cont):
        pieces, pos = container_plan(rng, i, pool, lengths)
        items.append(("container", VARIATIONS[i % 4], pos, pieces))
    rng.shuffle(items)
    out = ROOT / "data" / "partial" / split
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for k, (kind, variation, pos, pieces) in enumerate(items, 1):
        cid = f"p{split[0]}{k:02d}"
        render(pieces, variation, out / f"{cid}.mp4")
        seg, fill = spans(pieces)
        rows.append({"clip": cid, "split": split, "kind": kind, "variation": variation, "position": pos,
                     "family": pieces[[p[0] for p in pieces].index("orig")][1], "segments": seg, "filler": fill})
        if split != "test":  # nobody developing the rule sees the test truth before the test run
            print(cid, kind, variation, pos, seg, fill, flush=True)
    with open(out / "truth.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"{split}: {len(rows)} clips in {out}")


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as tmp:
        mc.CAPTION = Path(tmp) / "caption.srt"
        mc.CAPTION.write_text("1\n00:00:00,000 --> 00:01:00,000\nWATCH: what happened today\n")
        make(sys.argv[1])
