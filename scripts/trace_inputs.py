"""Make the input clips of the trace test (eval/trace.md, Inputs) from a manifest, before any part of trace runs.

  python scripts/trace_inputs.py <manifest.csv> --out <clips dir>

Manifest columns: case, kind (a, b or none), source, claimed_date, caption, flipped, start_s, end_s.
- kind a: `source` is a live post of the footage made on or after the claimed date; it is fetched with
  `indexreel fetch` and used as fetched.
- kind b: `source` is the earlier upload named by the fact-check (a post URL or a local file); the part from start_s to
  end_s is re-encoded at 720 px on the long side, flipped when `flipped` is 1 (the fact-check says the viral clip was),
  and then given the next edit of EDITS in test-id order.
- kind none: no input could be made; the case is listed and scored as not found.
Every clip gets <case>.source.json with the caption as the fact-check quotes it and, for kind b, the claimed date as
posted_at. The script writes <out>/claimed_dates.csv and <out>/inputs.csv (case, kind, edit, file) and prints both.
"""
import argparse
import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from indexreel import fetch  # noqa: E402

EDITS = ["flip", "slow", "zoom", "compilation"]
# Filler for the compilation edit: 6 s of ffmpeg's synthetic Game of Life pattern on each side, so that no search
# can find real uploads of the filler (eval/trace-v2.md, Inputs).
FILLER = ["life=s=640x360:rate=25:seed=2910:mold=10", "life=s=640x360:rate=25:seed=2911:mold=10"]
SCALE = "scale='if(gt(iw,ih),720,-2)':'if(gt(iw,ih),-2,720)'"
HOSTS = ["www.youtube.com", "youtube.com", "youtu.be", "www.tiktok.com", "www.instagram.com", "www.facebook.com",
         "www.reddit.com", "vimeo.com"]


def edits_for(rows):
    """{case: edit} for the kind b rows, EDITS in turn in case order."""
    b = sorted((r["case"] for r in rows if r["kind"] == "b"), key=lambda c: (c.rstrip("0123456789"), int("0" + c.lstrip("abcdefghijklmnopqrstuvwxyz"))))  # t2 before t11
    return {c: EDITS[i % len(EDITS)] for i, c in enumerate(b)}


def vf(edit, flipped):
    f = [SCALE] + (["hflip"] if flipped or edit == "flip" else [])  # a flip edit on a flipped copy flips it once, not back
    if edit == "slow":
        f.append("setpts=2*PTS")
    elif edit == "zoom":
        f += ["crop=iw*0.7:ih*0.7", SCALE]
    return ",".join(f)


def ffmpeg(*args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *map(str, args)], check=True)


def local_source(src, work):
    """A local file for a kind b source: the path itself, or the post fetched at up to 720 px."""
    if Path(src).exists():
        return Path(src)
    out = work / "src"
    cmd = fetch.ytdlp_cmd(src, out)
    i = cmd.index("--")
    subprocess.run(cmd[:i] + ["-S", "res:720"] + cmd[i:], check=True, capture_output=True)
    return next(p for p in sorted(out.iterdir()) if p.suffix in {".mp4", ".webm", ".mkv"} and not p.name.endswith(".part"))


def make_b(row, edit, out, work):
    src = local_source(row["source"], work / row["case"])
    part = work / f"{row['case']}_part.mp4"
    ffmpeg("-ss", row["start_s"], "-to", row["end_s"], "-i", src, "-vf", vf(edit, row["flipped"] == "1"), "-an",
           "-c:v", "libx264", "-crf", 23, "-pix_fmt", "yuv420p", "-r", 25, part)
    dest = out / f"{row['case']}.mp4"
    if edit != "compilation":
        part.rename(dest)
        return dest
    pieces = []
    for k, src in enumerate(FILLER):
        p = work / f"{row['case']}_filler{k}.mp4"
        ffmpeg("-f", "lavfi", "-i", src, "-t", 6, "-vf", SCALE, "-an", "-c:v", "libx264", "-crf", 23, "-pix_fmt", "yuv420p",
               "-r", 25, p)
        pieces.append(p)
    # the copy goes between the two fillers, all scaled to the copy's frame size
    w, h = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                           "-of", "csv=p=0", str(part)], capture_output=True, text=True, check=True).stdout.strip().split(",")
    fit = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1"
    ffmpeg("-i", pieces[0], "-i", part, "-i", pieces[1], "-filter_complex",
           f"[0:v]{fit}[x];[1:v]{fit}[y];[2:v]{fit}[z];[x][y][z]concat=n=3:v=1:a=0[v]", "-map", "[v]",
           "-c:v", "libx264", "-crf", 23, "-pix_fmt", "yuv420p", dest)
    return dest


def make_a(row, out, work):
    tmp = work / row["case"] / "a"
    ok, _, failed = fetch.fetch([row["source"]], tmp)
    if not ok:
        return None
    video = next(p for p in sorted(tmp.iterdir()) if not p.name.endswith(".json"))
    info = json.loads(next(tmp.glob("*.source.json")).read_text())
    dest = out / f"{row['case']}{video.suffix}"
    video.rename(dest)
    return dest, info


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("manifest", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    rows = list(csv.DictReader(open(a.manifest, newline="")))
    edit = edits_for(rows)
    a.out.mkdir(parents=True, exist_ok=True)
    done = []
    with tempfile.TemporaryDirectory() as t:
        work = Path(t)
        for r in rows:
            info, f = {}, None
            if r["kind"] == "a":
                got = make_a(r, a.out, work)
                if got:
                    f, info = got
            elif r["kind"] == "b":
                f = make_b(r, edit[r["case"]], a.out, work)
            if f:
                side = {k: info.get(k) for k in ("platform", "url", "post_id", "account", "posted_at", "fetched_utc")}
                side.update(caption=r["caption"], posted_at=info.get("posted_at") or r["claimed_date"])
                (a.out / f"{r['case']}.source.json").write_text(json.dumps(side, indent=1, ensure_ascii=False))
            done.append({"case": r["case"], "kind": r["kind"] if f else "none", "edit": edit.get(r["case"], ""),
                         "file": f.name if f else ""})
    with open(a.out / "claimed_dates.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["clip", "claimed_date"])
        w.writerows([d["case"], r["claimed_date"]] for d, r in zip(done, rows) if d["file"])
    with open(a.out / "inputs.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["case", "kind", "edit", "file"])
        w.writeheader()
        w.writerows(done)
    for d in done:
        print(f"trace_inputs: {d['case']} {d['kind']} {d['edit'] or '-'} {d['file'] or '-'}")


if __name__ == "__main__":
    main()
