"""Second look: an edit-aware re-ask of Muse Spark on three aligned frame pairs, measured on old pairs only.

The judge lists the fixed anchors both frames share (readable text first), then every difference, marks each
difference as one an edit can make or not, and may answer same only when at least 2 anchors match and every
difference is edit-made. The rule is also applied to its answer here, so a `yes` that breaks it is not counted as same.

  python scripts/second_look.py list --out data/second_look
  MODEL_API_KEY=... python scripts/second_look.py run --out data/second_look --max-usd 1.5 [--arm edit]
  python scripts/second_look.py report --out data/second_look

`list` writes pairs.csv: every pair Muse Spark judged in the v2 trace runs and in the same-place run, with its group
and, where known, the truth. `run` asks the pairs in group order until --max-usd would be passed; answers are kept in
results.jsonl and a rerun skips them. Nothing here changes trace or verify.
"""
import argparse
import csv
import glob
import json
import math
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from indexreel import trace, verify  # noqa: E402

SIZE = 360  # shorter side of each frame sent
MAX_OUT = 4000  # output tokens; reasoning shares them, so an answer can be cut off (no answer, counted abstain)
worst_usd = lambda max_out: 0.006 + max_out * verify.PRICE["output"] / 1e6  # one request at most: 6 frames at 360 px, reserved before asking
GROUPS = ["miss", "flagged", "sameplace_neg", "sameplace_pos", "trace_diff", "trace_same"]  # asked in this order
N6 = "youtube_n3vidANS1-c"  # n6's 2016 footage: verify said different, the same recording by eye

PROMPTS = {"edit": """You are shown three pairs of still frames. In each pair, frame A comes from video A and frame B from video B, at moments a frame matcher thinks line up (the alignment may be off by a fraction of a second). Answer with JSON only, no other text.
Question: do A and B come from the same original camera recording, even if one of them was edited?
Work in this order.
1. anchors: list the fixed things that both A and B show in the same places relative to each other. Readable text first (signs, shop names, watermarks, numbers), then buildings, landmarks and terrain. Name each one specifically.
2. differences: list every difference between A and B that you can see.
3. For each difference, edit_made is yes when an edit of the same footage could make it: a crop, pan, zoom, mirror (left-right flip), speed change, overlay, caption, logo or watermark, colour or brightness change, or an object or effect drawn on top (smoke, sky, a funnel cloud, an explosion). It is no when an edit cannot make it: a landmark in a different place relative to the others, a different viewpoint or camera position, or different moving detail at the aligned moment (rain, waves, foliage, people, vehicles, water) that is more than a small timing offset.
4. same_footage: yes only if at least 2 anchors match and every difference is edit_made yes. no if any difference is edit_made no. unsure otherwise.
Two cameras filming the same place, or one camera filming the same place minutes apart, are no: the fixed anchors match but the viewpoint or the moving detail does not.
Return {"anchors": [{"what": "...", "text": "readable text or null"}], "differences": [{"what": "...", "edit_made": "yes" or "no", "kind": "..."}], "same_footage": "yes", "no" or "unsure", "why": "one sentence"}."""}


def decide(ans):
    """same, different or abstain from an answer, with the rule applied: same needs a yes, at least 2 anchors and
    every difference edit-made; any difference not edit-made makes it different."""
    if not isinstance(ans, dict):
        return "abstain"
    diffs = [d for d in ans.get("differences") or [] if isinstance(d, dict)]
    if any(str(d.get("edit_made")).lower() == "no" for d in diffs) or str(ans.get("same_footage")).lower() == "no":
        return "different"
    anchors = [a for a in ans.get("anchors") or [] if a]
    if str(ans.get("same_footage")).lower() == "yes" and len(anchors) >= 2 and all(str(d.get("edit_made")).lower() == "yes" for d in diffs):
        return "same"
    return "abstain"


def aligned_times(p):
    """Three (time in a, time in b) from the matcher: a's core span (else its cover span, else the whole match),
    at 1/6, 1/2 and 5/6, with b's time at the matcher's offset."""
    for kind in ("core", "cover", None):
        s, e = (p.get(f"{kind}_a_start_s"), p.get(f"{kind}_a_end_s")) if kind else (p.get("a_start_s"), p.get("a_end_s"))
        if s not in (None, "") and e not in (None, ""):
            s, e = float(s), float(e)
            break
    else:
        return []
    k = float(p.get("offset_s") or 0)
    return [(s + (e - s) * f, s + (e - s) * f + k) for f in (1 / 6, 1 / 2, 5 / 6)]


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def listing(root=ROOT):
    """Every judged pair as {pair_id, group, truth, run, note, a, b}, deduplicated by pair id."""
    out, seen = [], set()
    # trace: the input against one candidate per pair folder; the explore run holds copies of the v2 test pairs
    for f in sorted(glob.glob(str(root / "data/trace_v2_*/*/trace/r*/pairs/*/run/pairs.csv"))):
        for p in csv.DictReader(open(f, newline="")):
            if not p.get("verify_verdict") or p["pair_id"] in seen:
                continue
            seen.add(p["pair_id"])
            v, ev = p["verify_verdict"], p.get("verify_same_event")
            if N6 in (p["a"], p["b"]):
                group, truth = "miss", "same"
            elif trace.possible_source(p):
                group, truth = "flagged", ""
            else:
                group, truth = ("trace_same", "") if v == "same" else ("trace_diff", "")
            out.append({"pair_id": p["pair_id"], "group": group, "truth": truth, "run": str(Path(f).parent),
                        "note": f"verify {v}, same_event {ev or '-'}", "a": p["a"], "b": p["b"]})
    # same place: one person's camera roll, 6 places, raw clips and their WhatsApp copies (eval/sameplace.md)
    man = root / "data/sameview/my_phone/manifest.csv"
    take = {Path(m["file"]).stem: (m["view"], m["take"]) for m in csv.DictReader(open(man, newline=""))}  # a copy has its raw clip's take
    for p in csv.DictReader(open(root / "data/sameplace_run/pairs.csv", newline="")):
        if not p.get("verify_verdict"):
            continue
        (va, ta), (vb, tb) = take[p["a"]], take[p["b"]]
        if ta == tb:
            group, truth = "sameplace_pos", "same"
        elif va == vb:
            group, truth = "sameplace_neg", "different"
        else:
            continue
        note = "wrong join" if p["verify_verdict"] == "same" and truth == "different" else \
            "merged, demoted by verify" if p["band"] == "merged" and truth == "different" else ""
        out.append({"pair_id": p["pair_id"], "group": group, "truth": truth, "run": str(root / "data/sameplace_run"),
                    "note": note, "a": p["a"], "b": p["b"]})
    return sorted(out, key=lambda r: GROUPS.index(r["group"]))


def frames(run, pair_id):
    """[(ta, tb, jpeg A, jpeg B)] for the pair, or None when a frame cannot be read."""
    import cv2
    p = next(r for r in csv.DictReader(open(Path(run) / "pairs.csv", newline="")) if r["pair_id"] == pair_id)
    path = {c["id"]: c["path"] for c in json.loads((Path(run) / "clips.json").read_text())["clips"]}
    out = []
    for ta, tb in aligned_times(p):
        imgs = []
        for clip, t in ((p["a"], ta), (p["b"], tb)):
            f = trace.frame_at(path[clip], t)
            if f is None:
                return None
            h, w = f.shape[:2]
            s = SIZE / min(h, w)
            imgs.append(cv2.imencode(".jpg", cv2.resize(f, (round(w * s), round(h * s))), [cv2.IMWRITE_JPEG_QUALITY, 85])[1].tobytes())
        out.append((ta, tb, *imgs))
    return out


def content(prompt, fr):
    import base64
    img = lambda b: {"type": "input_image", "image_url": "data:image/jpeg;base64," + base64.b64encode(b).decode()}
    c = [{"type": "input_text", "text": prompt}]
    for i, (ta, tb, a, b) in enumerate(fr, 1):
        c += [{"type": "input_text", "text": f"Pair {i}, frame A at {ta:.1f} s:"}, img(a), {"type": "input_text", "text": f"Pair {i}, frame B at {tb:.1f} s:"}, img(b)]
    return c


def run(pairs, out, judge, arm="edit", max_usd=1.5, workers=4, frames_of=frames, log=print, retry_cut=False, max_out=MAX_OUT):
    """Ask each pair not yet answered for this arm, in order, while the reserve for one more request fits under
    max_usd. With retry_cut, a pair whose answer was cut off (none came back) is asked again; the last answer counts.
    Returns the money spent by this arm so far."""
    res = Path(out) / "results.jsonl"
    done = [json.loads(x) for x in res.read_text().splitlines()] if res.exists() else []
    spent = [sum(r["cost"] for r in done if r["arm"] == arm)]
    last = {r["pair_id"]: r for r in done if r["arm"] == arm}
    asked = {p for p, r in last.items() if not (retry_cut and r["answer"] is None and r["verdict"] != "no_frames")}
    reserve = worst_usd(max_out)
    lock = threading.Lock()

    def one(r):
        with lock:
            if spent[0] + reserve > max_usd:
                return
            spent[0] += reserve  # reserved until the real cost is known
        fr = frames_of(r["run"], r["pair_id"])
        ans, cost = judge._ask(content(PROMPTS[arm], fr), max_output_tokens=max_out) if fr else (None, 0.0)
        row = {"arm": arm, **{k: r[k] for k in ("pair_id", "group", "truth", "note")},
               "verdict": decide(ans) if fr else "no_frames", "answer": ans, "cost": cost, "max_out": max_out}
        with lock:
            spent[0] += cost - reserve
            with res.open("a") as f:
                f.write(json.dumps(row) + "\n")
        log(f"second_look: {r['group']} {r['pair_id']} {row['verdict']} ${cost:.4f} (${spent[0]:.3f} so far)")

    Path(out).mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(workers) as ex:
        list(ex.map(one, [r for r in pairs if r["pair_id"] not in asked]))
    return spent[0]


def report(out, arm="edit"):
    rows = [json.loads(x) for x in (Path(out) / "results.jsonl").read_text().splitlines()]
    rows = [r for r in rows if r["arm"] == arm]
    cost = sum(r["cost"] for r in rows)
    rows = list({r["pair_id"]: r for r in rows}.values())  # the last answer of each pair
    lines = [f"arm {arm}: {len(rows)} pairs, ${cost:.4f}", "| group | same | k of n | Wilson 95% |", "|---|---|---|---|"]
    for g in GROUPS:
        rs = [r for r in rows if r["group"] == g]
        if rs:
            k = sum(r["verdict"] == "same" for r in rs)
            lo, hi = wilson(k, len(rs))
            others = ", ".join(f"{v} {sum(r['verdict'] == v for r in rs)}" for v in ("different", "abstain", "no_frames") if any(r["verdict"] == v for r in rs))
            lines.append(f"| {g} | {k} | {k}/{len(rs)} ({others}) | {lo:.2f} to {hi:.2f} |")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["list", "run", "report"])
    ap.add_argument("--out", type=Path, default=ROOT / "data/second_look")
    ap.add_argument("--arm", default="edit")
    ap.add_argument("--max-usd", type=float, default=1.5)
    ap.add_argument("--max-out", type=int, default=MAX_OUT)
    ap.add_argument("--retry-cut", action="store_true", help="ask again the pairs whose answer was cut off")
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    if a.cmd == "list":
        rows = listing()
        with open(a.out / "pairs.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        print(f"second_look: {len(rows)} pairs, " + ", ".join(f"{g} {sum(r['group'] == g for r in rows)}" for g in GROUPS))
    elif a.cmd == "run":
        pairs = list(csv.DictReader(open(a.out / "pairs.csv", newline="")))
        spent = run(pairs, a.out, verify.SparkJudge(a.out / "clips"), a.arm, a.max_usd, retry_cut=a.retry_cut, max_out=a.max_out)
        print(f"second_look: spent ${spent:.4f} on arm {a.arm}")
    else:
        print(report(a.out, a.arm))


if __name__ == "__main__":
    main()
