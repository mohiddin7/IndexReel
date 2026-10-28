"""Synthetic partial copies and single-recording controls for the partial-copy test (eval/partial.md).

  python scripts/make_partials.py build|test     write data/partial/<split>/<id>.mp4 and truth.csv

A partial copy is a segment of one dev original joined to filler: footage from my own phone clips, which are never
clips of the run, so the rest of the copy is a recording the run does not hold. Controls are trims and jump cuts of
one original (as in eval/compilation.md) and containers (a whole original plus filler, reported only). The dev
originals are data/gate_run/in/dev/*__orig.mp4 (640x360, 5 fps, 10 s, silent). Each split has its own seed and its
own filler takes, and every filler piece comes from a take no other clip of the split uses, so no two generated
clips share footage. Clip ids are shuffled so they say nothing about the truth.
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
AIR, FW, AF = "airshow09262026/", "july4_250fireworks/", "july4airforce/"
FILLER = {  # paths under data/iphone_by_me, except the USGS volcano recordings (test only, public domain)
    "build": ["IMG_2851.MOV", "IMG_2854.MOV", "IMG_2858.MOV", "IMG_3647.MOV", "IMG_3800.MOV", "IMG_3821.MOV",
              "IMG_4018.MOV", AIR + "IMG_4019.MOV", AIR + "video-5620_singular_display.mov",
              AIR + "video-5629_singular_display.mov", FW + "IMG_2974.MOV", FW + "video-2925_singular_display.mov",
              AF + "IMG_2948.MOV", AF + "IMG_2951.MOV"],
    "test": ["IMG_4084.MOV", "IMG_4138.MOV", "IMG_4436.MOV", "IMG_6171.MOV", "IMG_7309.MOV", "IMG_9427.MOV",
             "IMG_9458.MOV", "ccaed24b-7caa-4e1a-a163-55b50668a9f2.mp4", "video-2268_singular_display.mov",
             AIR + "IMG_4020.MOV", AIR + "video-5638_singular_display.mov", AIR + "video-5650_singular_display.mov",
             AIR + "video-5719_singular_display.mov", AIR + "video-5725_singular_display.mov",
             FW + "od_video-2912_singular_display.mov", FW + "video-2935_singular_display.mov",
             FW + "video-2947_singular_display.mov", FW + "video-2949_singular_display.mov", AF + "IMG_2946.MOV",
             AF + "IMG_2949.MOV", AF + "IMG_2952.MOV", AF + "IMG_2953.MOV", AF + "IMG_2954.MOV",
             "../event_volcano/ev1.mp4", "../event_volcano/ev2.mp4", "../event_volcano/ev3.mp4",
             "../event_volcano/ev4.mp4"]}
SPLITS = {"build": (21, 10, 4, 4, 1), "test": (22, 18, 8, 8, 2)}  # seed, partial copies, trims, jump cuts, containers
SEG_S = [3.0, 5.0, 7.0]
POSITIONS = ["after", "before", "both"]  # where the filler goes
VARIATIONS = mc.CONTROL_VARIATIONS  # plain, caption, letterbox, inset
W, H, FPS, q = mc.W, mc.H, mc.FPS, mc.q


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(out)


def partial_plan(rng, i):
    """Pieces of one partial copy; a filler piece is ("filler", None, None, d) until allocate() names its take."""
    fam, d = rng.choice(mc.FAMILIES), SEG_S[i % 3]
    seg = ("orig", fam, q(rng.uniform(0, mc.SRC_S - d)), d)
    pos = POSITIONS[(i // 3) % 3]
    total = q(d * rng.uniform(0.4, 1.6))
    if pos == "both":
        first = q(total * rng.uniform(0.3, 0.7))
        return [("filler", None, None, first), seg, ("filler", None, None, q(total - first))], pos
    piece = ("filler", None, None, total)
    return ([seg, piece] if pos == "after" else [piece, seg]), pos


def container_plan(rng, i):
    piece = ("filler", None, None, q(rng.uniform(3.0, 6.0)))
    seg = ("orig", rng.choice(mc.FAMILIES), 0.0, mc.SRC_S)
    return ([seg, piece] if i % 2 == 0 else [piece, seg]), "after" if i % 2 == 0 else "before"


def allocate(rng, items, pool):
    """Give every filler piece its own take, longest piece first, at a random start inside the take."""
    lengths = {t: duration(OWN / t) for t in pool}
    need = sorted(((p[3], k, j) for k, it in enumerate(items) for j, p in enumerate(it[3]) if p[0] == "filler"), reverse=True)
    if len(need) > len(pool):
        raise SystemExit(f"{len(need)} filler pieces but only {len(pool)} takes")
    free = list(pool)
    for d, k, j in need:
        fits = [t for t in free if lengths[t] >= d + 0.5]
        if not fits:
            raise SystemExit(f"no unused take is long enough for a {d} s filler piece")
        t = rng.choice(fits)
        free.remove(t)
        items[k][3][j] = ("filler", t, q(rng.uniform(0, lengths[t] - d - 0.5)), d)


def render(pieces, variation, out):
    args, chains = [], []
    for j, (kind, name, s, d) in enumerate(pieces):
        src = mc.SRC / f"{name}__orig.mp4" if kind == "orig" else OWN / name
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
        (seg if kind == "orig" else fill).append(f"{Path(name).stem}:{s:.2f}-{s + d:.2f}@{t:.2f}-{t + d:.2f}")
        t += d
    return ";".join(seg), ";".join(fill)


def make(split):
    seed, n_part, n_trim, n_jump, n_cont = SPLITS[split]
    rng = random.Random(seed)
    items = []
    for i in range(n_part):
        pieces, pos = partial_plan(rng, i)
        items.append(("partial", VARIATIONS[i % 4], pos, pieces))
    items += [("control_trim", VARIATIONS[i % 4], "", [("orig", *s) for s in mc.trim_plan(rng)]) for i in range(n_trim)]
    items += [("control_jumpcut", VARIATIONS[i % 4], "", [("orig", *s) for s in mc.jump_plan(rng)]) for i in range(n_jump)]
    for i in range(n_cont):
        pieces, pos = container_plan(rng, i)
        items.append(("container", VARIATIONS[i % 4], pos, pieces))
    allocate(rng, items, FILLER[split])
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
