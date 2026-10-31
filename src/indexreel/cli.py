"""indexreel match <clips dir> --out <run dir>: write a run directory in the format of eval/run-format.md."""
import argparse
import csv
import datetime
import hashlib
import importlib
import itertools
import json
import math
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

from indexreel import cluster, localise, sscd
from indexreel.match import READER

MERGE_AT = 0.55  # set on dev only, see eval/match-thresholds.md
FLOOR = 0.20
COVER_BAND = 2  # frames around the alignment where cover_spans looks for matches (eval/partial.md, build split)
VIDEO = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}
MODEL = Path(__file__).resolve().parents[2] / "data" / "models" / "sscd_disc_mixup.torchscript.pt"
PAIR_COLUMNS = ["pair_id", "a", "b", "score", "aligned", "mirrored", "offset_s", "a_start_s", "a_end_s", "b_start_s",
                "b_end_s", "band", "evidence", "evidence_a_s", "verify_verdict", "verify_confidence", "verify_reason",
                "verify_cost_usd", "core_a_start_s", "core_a_end_s", "core_b_start_s", "core_b_end_s", "cover_a", "cover_b",
                "cover_a_start_s", "cover_a_end_s", "cover_b_start_s", "cover_b_end_s"]
THUMB = (320, 180)
CACHE = Path.home() / ".cache" / "indexreel" / "match"
STAGES = [("fetch", "indexreel.fetch", "download the videos of posts you name"),
          ("verify", "indexreel.verify", "judge the unresolved pairs of a run"),
          ("claims", "indexreel.claims", "list the claims each post's caption makes about its footage"),
          ("withdraw", "indexreel.withdraw", "list the claims that lose video support when a recording is withdrawn"),
          ("trace", "indexreel.trace", "look for earlier uploads of each recording on the web"),
          ("wall", "indexreel.wall", "open a run in a local browser page"),
          ("bot", "indexreel.bot", "answer posts on X that tag the IndexReel account")]


def thumb(frame):
    """Fit a frame into THUMB, padded, so evidence rows line up whatever the aspect ratio."""
    w, h = THUMB
    s = min(w / frame.shape[1], h / frame.shape[0])
    small = cv2.resize(frame, (max(1, round(frame.shape[1] * s)), max(1, round(frame.shape[0] * s))),
                       interpolation=cv2.INTER_AREA)
    out = np.full((h, w, 3), 24, np.uint8)
    y, x = (h - small.shape[0]) // 2, (w - small.shape[1]) // 2
    out[y:y + small.shape[0], x:x + small.shape[1]] = small
    return out


def evidence_frames(ta, tb, core, i0, i1, offset):
    """The three frame pairs the evidence image shows, from the thumbnails the matcher embedded (so a localised clip
    stays rectified): (times in a, thumbnails of a, thumbnails of b, a is mirrored). Times are the start, middle and
    end of the pair's core span, or of the aligned overlap when it has none.

    This differs from trace.evidence_times on purpose: trace widens a core under 6 s to the cover span and takes the
    sharpest frame in each third, and such a frame can fall outside the core and not match (a blank or dark one); here
    three similar frames that match beat a sharp one that does not. The mirror is drawn only when ORB matches that
    survive RANSAC say so (the rule of trace.mirrored, without its pixel-correlation fallback): SSCD's flag hardly tells
    a frame from its mirror image, and on a pair that is no match any decision would be noise. The frames of a come
    back already mirrored."""
    from indexreel import trace  # not at the top: trace imports this module
    a0, a1 = (int(core[0]), max(int(core[0]), math.ceil(core[1]) - 1)) if core else (i0, i1 - 1)  # first and last frame
    idx = sorted({a0, (a0 + a1) // 2, a1})
    idx += [idx[-1]] * (3 - len(idx))
    idx = [min(max(i, 0), len(ta) - 1) for i in idx]
    fas, fbs = [ta[i] for i in idx], [tb[min(max(i + offset, 0), len(tb) - 1)] for i in idx]
    orb, bf = cv2.ORB_create(1000), cv2.BFMatcher(cv2.NORM_HAMMING)
    plain = sum(trace._inliers(f, g, orb, bf) for f, g in zip(fas, fbs))
    flip = sum(trace._inliers(f[:, ::-1].copy(), g, orb, bf) for f, g in zip(fas, fbs))
    mirror = flip >= trace.MIN_INLIERS and flip > plain
    return [i + 0.5 for i in idx], [f[:, ::-1].copy() for f in fas] if mirror else [f.copy() for f in fas], [f.copy() for f in fbs], mirror


def evidence_image(path, a, b, ta, tb, i0, i1, offset, core=None):
    """Three aligned frame pairs, a on the left and b on the right, labelled with their times (see evidence_frames).
    Returns the times in a, joined by ";"."""
    ts, fas, fbs, flip = evidence_frames(ta, tb, core, i0, i1, offset)
    rows = []
    for t, left, right in zip(ts, fas, fbs):
        cv2.putText(left, f"{a} {t:.1f}s", (6, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.putText(right, f"{b} {t + offset:.1f}s", (6, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1,
                    cv2.LINE_AA)
        if flip:
            cv2.putText(left, "mirrored", (6, left.shape[0] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1,
                        cv2.LINE_AA)
        rows.append(np.hstack([left, right]))
    cv2.imwrite(str(path), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 70])
    return ";".join(f"{t:.1f}" for t in ts)


def label(clip, place):
    """What the evidence images call a clip, as the wall page does: "post N" (its place in clips.json, from 1) for a
    clip from a post, else its id, shortened to 22 characters around ".." (the image font has no ellipsis)."""
    if clip.get("source"):
        return f"post {place}"
    i = clip["id"]
    return i if len(i) <= 22 else f"{i[:10]}..{i[-10:]}"


def find_clips(folder):
    clips = sorted(p for p in Path(folder).iterdir() if p.suffix.lower() in VIDEO)
    ids = [p.stem for p in clips]
    if len(set(ids)) != len(ids) or any("~" in i for i in ids):
        raise SystemExit("clip file names (without extension) must be unique and contain no '~'")
    if not clips:
        raise SystemExit(f"no clips in {folder}")
    return clips


def git_commit():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                              cwd=Path(__file__).parent).stdout.strip() or "unknown"
    except OSError:
        return "unknown"


def analyse(path, net, theta, model_sha, cache):
    """Embeddings, evidence thumbnails and quads of one clip; read from the cache when this exact file was seen.

    The cache key holds the file's path, size and modification time, the localiser settings, the frame-reader version
    and the model hash, so changing any of them recomputes.
    """
    f = None
    if cache:
        st = path.stat()
        key = f"{path.resolve()}|{st.st_size}|{st.st_mtime_ns}|{theta}|{localise.LONG_SIDE}|{localise.RATE}|reader{READER}|{model_sha}"
        f = Path(cache) / f"{hashlib.sha1(key.encode()).hexdigest()}.npz"
        if f.exists():
            z = np.load(f)
            return (json.loads(str(z["meta"])), z["plain"], z["mirror"], z["thumbs"],
                    [None if np.isnan(q).any() else q for q in z["quads"]])
    s = localise.sample(path, theta)
    plain = sscd.embed(net, s["frames"])
    mirror = sscd.embed(net, [np.ascontiguousarray(fr[:, ::-1]) for fr in s["frames"]])
    thumbs = np.stack([thumb(fr) for fr in s["frames"]])
    meta = {k: s[k] for k in ("fps", "duration_s", "width", "height")}
    if f:
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_name(f.stem + ".tmp.npz")
        np.savez(tmp, plain=plain, mirror=mirror, thumbs=thumbs, meta=json.dumps(meta),
                 quads=np.stack([np.full((4, 2), np.nan) if q is None else q for q in s["quads"]]))
        tmp.replace(f)
    return meta, plain, mirror, thumbs, s["quads"]


def load_source(path):
    """The sidecar `indexreel fetch` wrote next to a clip (<stem>.source.json), or None for a local file."""
    f = Path(path).with_suffix(".source.json")
    return json.loads(f.read_text()) if f.exists() else None


def match(folder, out, model, merge_at=MERGE_AT, floor=FLOOR, theta=localise.THETA, argv="", cache=CACHE):
    out = Path(out)
    (out / "frames").mkdir(parents=True, exist_ok=True)
    net, model_sha = sscd.load(model), hashlib.sha256(Path(model).read_bytes()).hexdigest()
    clips, feats, thumbs, info = find_clips(folder), {}, {}, []
    for p in clips:
        meta, plain, mirror, thumbs[p.stem], quads = analyse(p, net, theta, model_sha, cache)
        feats[p.stem] = (plain, mirror)
        fallback = sum(q is None for q in quads) / len(quads)
        q = localise.median_quad(quads)
        info.append({"id": p.stem, "path": str(p.resolve()), "duration_s": round(meta["duration_s"], 3),
                     "fps": round(meta["fps"], 3), "width": meta["width"], "height": meta["height"],
                     "frames_sampled": len(quads),
                     "crop": {"method": "opencv" if q else "none", "quad": q, "fallback_share": round(fallback, 3)},
                     **({"source": src} if (src := load_source(p)) else {})})
        print(f"{p.stem}: {len(quads)} frames, localiser fallback {fallback:.0%}", flush=True)
    dur = {c["id"]: c["duration_s"] for c in info}
    name = {c["id"]: label(c, n) for n, c in enumerate(info, 1)}

    rows = []
    for a, b in itertools.combinations(sorted(feats), 2):
        score = sscd.score(feats[a], feats[b])
        al, k, i0, i1, flipped = sscd.aligned_match(feats[a], feats[b])
        core = sscd.core_span(feats[a], feats[b], k, i0, i1, flipped)
        core = [""] * 4 if core is None else [core[0], min(core[1], dur[a]), core[0] + k, round(min(core[1] + k, dur[b]), 3)]
        cov = sscd.cover_spans(feats[a], feats[b], k, flipped, COVER_BAND)
        na, nb = len(feats[a][0]), len(feats[b][0])
        cover = ["0", "0", "", "", "", ""] if cov is None else [
            round((cov[0][1] - cov[0][0]) / na, 3), round((cov[1][1] - cov[1][0]) / nb, 3),
            cov[0][0], min(cov[0][1], dur[a]), cov[1][0], round(min(cov[1][1], dur[b]), 3)]
        pid = cluster.pair_id(a, b)
        bd = cluster.band(al, score, merge_at, floor)
        ev, evt = "", ""
        if bd != "apart":
            ev = f"frames/{pid}.jpg"
            evt = evidence_image(out / ev, name[a], name[b], thumbs[a], thumbs[b], i0, i1, k, core[:2] if core[0] != "" else None)
        rows.append({"pair_id": pid, "a": a, "b": b, "score": round(score, 4), "aligned": round(al, 4),
                     "mirrored": int(flipped), "offset_s": k, "a_start_s": i0, "a_end_s": min(i1, dur[a]),
                     "b_start_s": i0 + k, "b_end_s": round(min(i1 + k, dur[b]), 3), "band": bd, "evidence": ev,
                     "evidence_a_s": evt, "verify_verdict": "", "verify_confidence": "", "verify_reason": "",
                     "verify_cost_usd": "", **dict(zip(PAIR_COLUMNS[-10:-6], core)),
                     **dict(zip(PAIR_COLUMNS[-6:], cover))})
    with open(out / "pairs.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=PAIR_COLUMNS)
        w.writeheader()
        w.writerows(rows)

    th = {"merge_at": merge_at, "floor": floor}
    rec, comps, suggested = cluster.resolve_all([c["id"] for c in info], rows)
    (out / "clips.json").write_text(json.dumps({"version": 1, "clips": info}, indent=1))
    (out / "clusters.json").write_text(json.dumps({"version": 1, "thresholds": {**th, "score_used": "aligned"},
                                                   "recordings": rec, "compilations": comps,
                                                   **({"compilation_suggestions": suggested} if suggested else {})}, indent=1))
    (out / "audit.jsonl").touch()  # human decisions live here; never truncated
    (out / "run.json").write_text(json.dumps({
        "version": 1, "command": argv, "created_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": git_commit(), "n_clips": len(info), "sample": "1 frame per second", "thresholds": th,
        "localiser": {"method": "opencv", "theta": theta},
        "sscd_model_sha256": model_sha}, indent=1))
    return rows, rec


def show(rows, rec):
    print(f"\n{'pair':34s} {'score':>6s} {'aligned':>7s} {'offset':>6s}  {'span in a':>11s}  {'span in b':>11s}  band")
    for r in sorted(rows, key=lambda r: -r["aligned"]):
        if r["band"] != "apart":
            print(f"{r['pair_id']:34s} {r['score']:6.3f} {r['aligned']:7.3f} {r['offset_s']:5.0f}s  "
                  f"{r['a_start_s']:4.0f}-{r['a_end_s']:4.0f} s  {r['b_start_s']:4.0f}-{r['b_end_s']:4.0f} s  {r['band']}")
    n = {b: sum(r["band"] == b for r in rows) for b in ("merged", "unresolved", "apart")}
    print(f"\n{len(rows)} pairs: {n['merged']} merged, {n['unresolved']} unresolved, {n['apart']} apart")
    print(f"{len(rec)} recordings: " + ", ".join(f"{r['id']}[{len(r['members'])}{'?' if r['status'] == 'unresolved' else 'C' if r['status'] == 'compilation' else ''}]" for r in rec))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="indexreel")
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("match", help="count the distinct recordings behind a folder of clips")
    m.add_argument("clips", help="folder of video clips")
    m.add_argument("--out", required=True, help="run directory to write")
    m.add_argument("--sscd-model", default=str(MODEL), help="SSCD torchscript file")
    m.add_argument("--merge-at", type=float, default=MERGE_AT)
    m.add_argument("--floor", type=float, default=FLOOR)
    m.add_argument("--theta", type=float, default=localise.THETA, help="localiser edge-support cut-off")
    m.add_argument("--cache", default=str(CACHE), help="where per-clip embeddings are kept between runs")
    m.add_argument("--no-cache", action="store_true")
    for name, _, text in STAGES:  # listed for --help only; each stage parses its own arguments
        sub.add_parser(name, add_help=False, help=text)
    argv = sys.argv[1:] if argv is None else list(argv)
    for name, module, _ in STAGES:
        if argv[:1] == [name]:
            return importlib.import_module(module).main(argv[1:])
    a = ap.parse_args(argv)
    rows, rec = match(a.clips, a.out, a.sscd_model, a.merge_at, a.floor, a.theta, argv="indexreel " + " ".join(argv),
                      cache=None if a.no_cache else a.cache)
    show(rows, rec)


if __name__ == "__main__":
    main()
