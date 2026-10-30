"""Same moment, different camera: the scorer of eval/samemoment.md (frozen with it). Media is read as data only.

  .venv/bin/python -I scripts/samemoment.py claps        propose each clip's clap time (largest sound onset in its last 8 s)
  .venv/bin/python -I scripts/samemoment.py controls     make the constructed control clips
  .venv/bin/python -I scripts/samemoment.py score        S0, S1, S2 and P on every pair; bars 1 to 3
  MODEL_API_KEY=... .venv/bin/python -I scripts/samemoment.py spark    M on its 64 pairs, at most $1.50; writes the anchor cards
  .venv/bin/python -I scripts/samemoment.py report       bar 4 from the checked cards, and the whole verdict
  .venv/bin/python -I scripts/samemoment.py selftest     synthetic checks, no media, no network

Data: data/samemoment/ (manifest.csv, raw/, whatsapp/, music/); outputs go to data/samemoment/out/.
"""
import base64
import csv
import hashlib
import itertools
import json
import math
import random
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.ndimage import median_filter
from scipy.signal import correlate, stft

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from indexreel import audio, verify  # noqa: E402

D = ROOT / "data" / "samemoment"
OUT = D / "out"
HZ, SR, FPS = 100, 8000, 25
TRIM_S, END_S = 1.0, 2.0  # window: 1 s after the start to 2 s before the clap
SOUND_Z, PICTURE_Z, LAG_AGREE_S, LAG_TRUTH_S = 8, 5, 0.5, 0.2
LANDMARK = 0.03
SIFT_BAR = 16
TRACK = ("Musopen_-_In_the_Hall_Of_The_Mountain_King.ogg", "3bfa7424d3a148f1482a44688b77eb9138a7cea6cff7474799f1329181ab3342")
SPARK_CAP, SPARK_SIZE, SPARK_MAX_OUT = 1.50, 240, 4000
CONTROLS = [  # (control clip, its picture source, its sound source, the clip it is paired with)
    ("swap_street", "street_t2_iphone", "street_t1_iphone", "street_t1_glasses"),
    ("swap_talk", "talk_t2_iphone", "talk_t1_iphone", "talk_t1_glasses"),
    ("swap_crossing", "crossing_t2_iphone", "crossing_t1_iphone", "crossing_t1_glasses"),  # Amendment 2: replaces swap_talk
]
MUSIC = [("park_t1_iphone", 0.0, "street2_t1_glasses", 5.0), ("talk_t1_glasses", 0.0, "crossing_t2_iphone", 5.0)]

PROMPT = """You are shown two short videos, A and B. They may come from different cameras or different moments. Answer with JSON only, no other text. Ignore captions, stickers or titles an editor laid over the picture; signs and text that are part of the scene count.
First list checkable details, then answer. Only list a thing if you can point to it in both videos.
anchors: fixed things visible in both (buildings, skyline shapes, signs with their exact text, distinctive objects), each with its time in A and in B.
transients: specific moving things or sounds present in both (the same vehicle, person, aircraft, performer, a bang or a song), each with its time in A and in B.
contradictions: fixed things or conditions that differ (place, light, weather, season, time of day).
Questions, each answered yes, no or unsure:
same_place: yes only with at least two anchors; no if contradictions show a different place; otherwise unsure.
same_occasion: same place and the same day, within about an hour? yes only if same_place is yes and light, weather and transients agree; no if they contradict; otherwise unsure.
same_moment: do the recordings overlap in time? yes only with at least one transient at matching times; otherwise unsure or no.
Return {"anchors": [{"what": "...", "time_a_s": n, "time_b_s": n}], "transients": [{"what": "...", "time_a_s": n, "time_b_s": n}], "contradictions": ["..."],
"same_place": ..., "same_occasion": ..., "same_moment": ..., "because": "..."}."""


# --- manifest and pairs ---

def manifest(path=None):
    """{clip id: row} with clip id = file stem; clap_s as float."""
    rows = list(csv.DictReader(open(path or D / "manifest.csv", newline="")))
    out = {}
    for r in rows:
        r["clap_s"] = float(r["clap_s"]) if (r.get("clap_s") or "").strip() else None
        out[Path(r["file"]).stem] = r
    return out


def take_key(r):
    return r["scene"], r["take"]


def pairs(m):
    """[(a, b, kind, form)]: positives (iPhone first), negatives by kind, in raw and copy-copy form, then the controls.
    Copies of one take's two clips are not a positive (eval/samemoment.md, "Excluded")."""
    raw = sorted(c for c, r in m.items() if r["kind"] == "raw" and r["clap_s"] is not None)
    copy_of = {Path(r["original"]).stem: c for c, r in m.items() if r["kind"] == "whatsapp" and r["clap_s"] is not None}
    out = []
    for a, b in itertools.combinations(raw, 2):
        ra, rb = m[a], m[b]
        if take_key(ra) == take_key(rb):
            if {ra["device"], rb["device"]} == {"iphone", "glasses"}:
                out.append((*((a, b) if ra["device"] == "iphone" else (b, a)), "positive", "raw"))
            continue
        kind = ("same_place_other_time" if ra["scene"] == rb["scene"] else
                "lookalike" if ra["place_kind"] == rb["place_kind"] else "cross_scene")
        out.append((a, b, kind, "raw"))
        if a in copy_of and b in copy_of:
            out.append((copy_of[a], copy_of[b], kind, "copy"))
    for name, _, _, partner in CONTROLS:
        if m.get(name, {}).get("kind") == "control" and partner in m:
            out.append((name, partner, "control", "raw"))
    for a, _, b, _ in MUSIC:
        if m.get(f"music_{a}", {}).get("kind") == "control" and m.get(f"music_{b}", {}).get("kind") == "control":
            out.append((f"music_{a}", f"music_{b}", "control", "raw"))
    return out


def path(c, m):
    return D / m[c]["file"]


# --- sound and picture envelopes ---

def detrend(x, secs=1.0):
    return np.clip(x - median_filter(x, size=int(secs * HZ) | 1, mode="nearest"), 0, None)


def sound_env_of(x):
    _, _, Z = stft(x, fs=SR, nperseg=256, noverlap=256 - SR // HZ, boundary=None, padded=False)
    m = np.log1p(np.abs(Z) * 100)
    return detrend(np.clip(np.diff(m, axis=1), 0, None).sum(axis=0))


def picture_env_of(means):
    up = np.repeat(np.clip(np.diff(means, prepend=means[0]), 0, None), HZ // FPS)
    return detrend(up)


def pcm(p):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(p), "-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)


def envelopes(c, m):
    f = OUT / "env" / f"{c}.npz"
    if not f.exists():
        f.parent.mkdir(parents=True, exist_ok=True)
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path(c, m)), "-an", "-vf", f"fps={FPS},scale=16:9,format=gray",
                              "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
        np.savez(f, sound=sound_env_of(pcm(path(c, m))), picture=picture_env_of(np.frombuffer(raw, np.uint8).reshape(-1, 144).mean(axis=1)))
    e = np.load(f)
    return e["sound"], e["picture"]


def window(x, clap_s, trim=TRIM_S):
    return x[int(trim * HZ):max(int(trim * HZ), int((clap_s - END_S) * HZ))]


def zn(x):
    return (x - x.mean()) / (x.std() + 1e-9)


def xcorr(a, b):
    """(peak z, lag in seconds) with a[n + lag] ~ b[n]: the lag is b's start on a's timeline."""
    if len(a) < 2 * HZ or len(b) < 2 * HZ:
        return 0.0, 0.0
    c = correlate(zn(a), zn(b), mode="full", method="fft")
    lags = (np.arange(len(c)) - (len(b) - 1)) / HZ
    i = int(np.argmax(c))
    off = np.abs(lags - lags[i]) > 2
    return float((c[i] - c[off].mean()) / (c[off].std() + 1e-9)), float(lags[i])


def landmark(ha, hb, win_a, win_b):
    """The shipped fingerprint score (indexreel.audio.score) on hashes inside each window, and its best offset as a lag
    in seconds (same convention as xcorr). None when either side has too little sound."""
    frame_s = audio.HOP / audio.SR

    def keep(h, w):
        lo, hi = w
        return {k: [t for t in v if lo <= t * frame_s < hi] for k, v in h.items()}

    a, b = keep(ha, win_a), keep(hb, win_b)
    a, b = {k: v for k, v in a.items() if v}, {k: v for k, v in b.items() if v}
    if audio.count(a) < audio.MIN_HASHES or audio.count(b) < audio.MIN_HASHES:
        return None, None
    votes = Counter()
    for k, ta in a.items():
        for x in ta:
            for y in b.get(k, ()):
                votes[(y - x) // audio.BIN] += 1
    if not votes:
        return 0.0, None
    bin_, n = votes.most_common(1)[0]
    # an event at a's time ta (frames, window-relative) is at b's time ta - lag
    lag = -((bin_ + 0.5) * audio.BIN * frame_s) + (win_a[0] - win_b[0])
    return n / min(audio.count(a), audio.count(b)), lag


def rule_s1(r):
    return r["sound_z"] >= SOUND_Z and r["picture_z"] >= PICTURE_Z and abs(r["sound_lag"] - r["picture_lag"]) <= LAG_AGREE_S


def rule_s2(r):
    fp = (r["landmark"] is not None and r["landmark"] >= LANDMARK and r["landmark_lag"] is not None
          and abs(r["landmark_lag"] - r["picture_lag"]) <= LAG_AGREE_S and r["picture_z"] >= PICTURE_Z)
    return rule_s1(r) or fp


def rule_s0(r):
    return r["s0_sound_z"] >= 20 and r["s0_picture_z"] >= 12 and abs(r["s0_sound_lag"] - r["s0_picture_lag"]) <= 10


def found_lag(r):
    """The lag a same-moment claim rests on: the sound lag under S1, else the fingerprint's under S2."""
    return r["sound_lag"] if rule_s1(r) else r["landmark_lag"] if rule_s2(r) else None


def measure(a, b, m, hashes):
    ea, eb = envelopes(a, m), envelopes(b, m)
    ca, cb = m[a]["clap_s"], m[b]["clap_s"]
    sz, sl = xcorr(window(ea[0], ca), window(eb[0], cb))
    pz, pl = xcorr(window(ea[1], ca), window(eb[1], cb))
    s0 = [xcorr(window(ea[i], ca, 0.0), window(eb[i], cb, 0.0)) for i in (0, 1)]
    lm, ll = landmark(hashes(a), hashes(b), (TRIM_S, ca - END_S), (TRIM_S, cb - END_S))
    return {"sound_z": round(sz, 2), "sound_lag": round(sl, 2), "picture_z": round(pz, 2), "picture_lag": round(pl, 2),
            "landmark": None if lm is None else round(lm, 4), "landmark_lag": None if ll is None else round(ll, 2),
            "s0_sound_z": round(s0[0][0], 2), "s0_sound_lag": round(s0[0][1], 2), "s0_picture_z": round(s0[1][0], 2),
            "s0_picture_lag": round(s0[1][1], 2)}


# --- same place: strict local-feature geometry ---

def sift_frames(c, m, n=5):
    import cv2
    clap = m[c]["clap_s"]
    out = []
    for t in np.linspace(TRIM_S, clap - END_S, n):
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(path(c, m)), "-frames:v", "1",
                              "-vf", "scale='if(gt(iw,ih),640,-2)':'if(gt(iw,ih),-2,640)',format=gray", "-f", "image2pipe",
                              "-vcodec", "png", "-"], capture_output=True, check=True).stdout
        out.append(cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_GRAYSCALE))
    return out


def inliers(fa, fb):
    """Best strict inlier count over all frame pairs: SIFT 1,500, ratio 0.7, mutual nearest neighbours, MAGSAC 3 px."""
    import cv2
    sift, bf, best = cv2.SIFT_create(1500), cv2.BFMatcher(), 0
    ka = [sift.detectAndCompute(f, None) for f in fa]
    kb = [sift.detectAndCompute(f, None) for f in fb]
    for (k1, d1), (k2, d2) in itertools.product(ka, kb):
        if d1 is None or d2 is None or len(k1) < 8 or len(k2) < 8:
            continue
        mm = [p[0] for p in bf.knnMatch(d1, d2, k=2) if len(p) == 2 and p[0].distance < 0.7 * p[1].distance]
        back = {x[0].queryIdx: x[0].trainIdx for x in bf.knnMatch(d2, d1, k=1) if x}
        mm = [x for x in mm if back.get(x.trainIdx) == x.queryIdx]
        if len(mm) < 8:
            continue
        H, mask = cv2.findHomography(np.float32([k1[x.queryIdx].pt for x in mm]), np.float32([k2[x.trainIdx].pt for x in mm]),
                                     cv2.USAC_MAGSAC, 3.0)
        if H is not None:
            best = max(best, int(mask.sum()))
    return best


# --- commands ---

def claps():
    """Propose each clip's clap: the largest sound onset in its last 8 s. A person confirms each by ear."""
    rows = []
    for folder in ("raw", "whatsapp"):
        for p in sorted((D / folder).glob("*")):
            if p.suffix.lower() not in (".mov", ".mp4", ".m4v"):
                continue
            s = sound_env_of(pcm(p))
            lo = max(0, len(s) - 8 * HZ)
            t = (lo + int(np.argmax(s[lo:]))) / HZ
            rows.append({"file": f"{folder}/{p.name}", "proposed_clap_s": round(t, 2)})
            print(f"{folder}/{p.name}: clap at {t:.2f} s?")
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "claps_proposed.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["file", "proposed_clap_s"])
        w.writeheader()
        w.writerows(rows)


def controls(m=None):
    """The constructed controls whose source clips exist (Amendment 2), written to data/samemoment/controls/. They go
    into the manifest with kind `control` and the clap_s given in `controls.csv`; they are scored only in the control pairs."""
    m = m or manifest()
    track = D / "music" / TRACK[0]
    assert hashlib.sha256(track.read_bytes()).hexdigest() == TRACK[1], "music track is not the one named in the protocol"
    out = D / "controls"
    out.mkdir(exist_ok=True)
    rows = []
    have = lambda *cs: all(c in m and m[c]["clap_s"] is not None for c in cs)  # Amendment 2: a take may be missing
    for name, pic, snd, partner in CONTROLS:
        if not have(pic, snd, partner):
            print(f"{name}: not built, a source clip is missing")
            continue
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(path(pic, m)), "-i", str(path(snd, m)), "-map", "0:v:0", "-map", "1:a:0",
                        "-shortest", "-c:v", "libx264", "-crf", "18", "-c:a", "aac", str(out / f"{name}.mp4")], check=True)
        rows.append({"file": f"controls/{name}.mp4", "clap_s": min(m[pic]["clap_s"], m[snd]["clap_s"])})
    for a, sa, b, sb in MUSIC:
        if not have(a, b):
            print(f"music_{a}~music_{b}: not built, a source clip is missing")
            continue
        for c, start in ((a, sa), (b, sb)):
            own = pcm(path(c, m))
            mus = pcm(track)
            gain = 10 ** (-6 / 20) * math.sqrt(np.mean(own ** 2) / (np.mean(mus ** 2) + 1e-12))
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(path(c, m)), "-i", str(track),
                            "-filter_complex", f"[1:a]adelay={int(start * 1000)}|{int(start * 1000)},volume={gain:.6f}[mu];"
                                               f"[0:a][mu]amix=inputs=2:duration=first:normalize=0[a]",
                            "-map", "0:v:0", "-map", "[a]", "-c:v", "libx264", "-crf", "18", "-c:a", "aac",
                            str(out / f"music_{c}.mp4")], check=True)
            rows.append({"file": f"controls/music_{c}.mp4", "clap_s": m[c]["clap_s"]})
    with open(out / "controls.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["file", "clap_s"])
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} control clips in {out}")


def upper95(n):
    return 1 - 0.05 ** (1 / n) if n else 1.0


def score(m=None, log=print, sift=True):
    m = m or manifest()
    cache = {}

    def hashes(c):
        if c not in cache:
            cache[c] = audio.hashes(path(c, m))
        return cache[c]

    rows = []
    for a, b, kind, form in pairs(m):
        r = {"a": a, "b": b, "kind": kind, "form": form, **measure(a, b, m, hashes)}
        r["truth_lag"] = round(m[a]["clap_s"] - m[b]["clap_s"], 2) if kind == "positive" else None
        r["S0"], r["S1"], r["S2"] = rule_s0(r), rule_s1(r), rule_s2(r)
        r["inliers"] = inliers(sift_frames(a, m), sift_frames(b, m)) if sift and form == "raw" and kind != "control" else None
        r["P"] = None if r["inliers"] is None else r["inliers"] >= SIFT_BAR
        rows.append(r)
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "pairs.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    v = verdict(rows)
    (OUT / "score.json").write_text(json.dumps(v, indent=1))
    for k, x in v.items():
        log(f"{k}: {x}")
    return rows, v


def verdict(rows, spark=None):
    neg = [r for r in rows if r["kind"] != "positive"]
    pos = [r for r in rows if r["kind"] == "positive" and r["form"] == "raw"]
    false_s = [f"{r['a']}~{r['b']}" for r in neg if r["S1"] or r["S2"]]
    false_m = [p for p, a in (spark or {}).items() if a.get("truth") != "positive" and str(a.get("same_moment")) == "yes"]
    found = [r for r in pos if found_lag(r) is not None and abs(found_lag(r) - r["truth_lag"]) <= LAG_TRUTH_S]
    wrong_lag = [f"{r['a']}~{r['b']}" for r in pos if found_lag(r) is not None and r not in found]
    look = [r for r in rows if r["kind"] == "lookalike" and r["form"] == "raw"]
    need = math.ceil(0.75 * len(pos))  # 9 of 12, 7 of 9
    return {
        "bar1_false_same_moment": {"S1_or_S2": false_s, "M": false_m, "negatives": len(neg),
                                   "upper95": round(upper95(len(neg)), 4), "pass": not false_s and not false_m},
        "bar2_recall": {"found": len(found), "of": len(pos), "need": need, "wrong_lag": wrong_lag, "pass": len(found) >= need},
        "bar3_same_place_on_lookalikes": {"P_yes": [f"{r['a']}~{r['b']}" for r in look if r["P"]], "of": len(look),
                                          "pass": not any(r["P"] for r in look)},
        "S0_found": sum(1 for r in pos if r["S0"]), "S0_false": sum(1 for r in neg if r["S0"]),
        "copies_found": sum(1 for r in rows if r["kind"] == "positive" and r["form"] == "copy"),
    }


# --- M: Muse Spark, split prompt ---

def spark_pairs(rows):
    raw = [r for r in rows if r["form"] == "raw"]
    pick = [r for r in raw if r["kind"] in ("positive", "same_place_other_time", "lookalike", "control")]
    cross = sorted((r for r in raw if r["kind"] == "cross_scene"), key=lambda r: (r["a"], r["b"]))
    return pick + random.Random(29).sample(cross, min(12, len(cross)))


def encode240(c, m):
    out = OUT / "enc" / f"{c}.mp4"
    if not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        vf = f"scale='if(gt(iw,ih),-2,{SPARK_SIZE})':'if(gt(iw,ih),{SPARK_SIZE},-2)'"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(path(c, m)), "-map_metadata", "-1", "-map_chapters", "-1", "-map", "0:v:0",
                        "-map", "0:a:0?", "-vf", vf, "-c:v", "libx264", "-crf", "28", "-c:a", "aac", "-b:a", "64k", "-movflags", "+faststart",
                        str(out)], check=True)
    return out


class Spark:
    """One streamed request, asked once; the final event is read here (an answer cut off or failed is no answer)."""

    def __init__(self):
        self.cli, self.ids = None, {}

    def video(self, p):
        if self.cli is None:
            self.cli = verify.SparkJudge(OUT / "upload").cli
        if p not in self.ids:
            with open(p, "rb") as f:
                self.ids[p] = self.cli.files.create(purpose="user_data", file=f, expires_after={"anchor": "created_at", "seconds": 86400}).id
        return {"type": "input_file", "file_id": self.ids[p]}

    def ask(self, content):
        out, final = [], None
        with self.cli.responses.stream(model=verify.MODEL, input=[{"type": "message", "role": "user", "content": content}],
                                       max_output_tokens=SPARK_MAX_OUT, reasoning={"effort": "minimal"}) as s:
            for ev in s:
                if ev.type == "response.output_text.delta":
                    out.append(ev.delta)
                elif ev.type in ("response.completed", "response.incomplete", "response.failed"):
                    final = ev.response
        if final is None:
            return None, None, "no final event"
        u = final.usage
        cost = None if u is None else ((u.input_tokens - ((u.input_tokens_details.cached_tokens or 0) if u.input_tokens_details else 0))
                                       * verify.PRICE["input"] + ((u.input_tokens_details.cached_tokens or 0) if u.input_tokens_details else 0)
                                       * verify.PRICE["cached"] + u.output_tokens * verify.PRICE["output"]) / 1e6
        return (verify.parse("".join(out)) if final.status == "completed" else None), cost, final.status


WORST_USD = (2 * 5000 + len(PROMPT) / 2) * verify.PRICE["input"] / 1e6 + SPARK_MAX_OUT * verify.PRICE["output"] / 1e6


def spark(m=None, rows=None, client=None, cap=SPARK_CAP, log=print):
    m = m or manifest()
    rows = rows or list(csv.DictReader(open(OUT / "pairs.csv", newline="")))
    client = client or Spark()
    cache = verify.Cache(OUT / "spark_cache")
    spent, answers = 0.0, {}
    for r in spark_pairs(rows):
        pa, pb = encode240(r["a"], m), encode240(r["b"], m)
        key = hashlib.sha256(json.dumps([verify.MODEL, PROMPT, SPARK_SIZE, SPARK_MAX_OUT, verify.sha(pa), verify.sha(pb)]).encode()).hexdigest()
        hit = cache.get(key)
        if hit is None:
            if spent + WORST_USD > cap:
                log(f"spark: stopped before {r['a']}~{r['b']}: spent ${spent:.4f}, cap ${cap:.2f}")
                break
            content = [{"type": "input_text", "text": PROMPT + "\nVideo A:"}, client.video(pa), {"type": "input_text", "text": "Video B:"}, client.video(pb)]
            ans, cost, status = client.ask(content)
            spent += WORST_USD if cost is None else cost
            log(f"spark {r['a']}~{r['b']}: {status}, total ${spent:.4f}")
            hit = {"answer": ans if status == "completed" else None, "status": status, "cost": cost}
            if status == "completed":
                cache.put(key, hit)
        answers[f"{r['a']}~{r['b']}"] = {**(hit["answer"] or {}), "truth": r["kind"], "status": hit["status"]}
    (OUT / "spark.json").write_text(json.dumps(answers, indent=1, ensure_ascii=False))
    cards(answers, m)
    log(f"spark: spent ${spent:.4f} now (cap ${cap:.2f})")
    return spent, answers


def cards(answers, m):
    """For every M yes: one card per cited anchor or transient, with the two cited frames. The checker sees cards.csv and
    the images only, with no clip names and no truth; key.json maps cards to pairs and stays with the scorer."""
    import cv2
    rows, key, n = [], {}, 0
    for p, a in answers.items():
        if not any(str(a.get(q)) == "yes" for q in ("same_place", "same_occasion", "same_moment")):
            continue
        ca, cb = p.split("~")
        for kind in ("anchors", "transients"):
            for item in a.get(kind) or []:
                if not isinstance(item, dict):
                    continue
                n += 1
                ims = []
                for c, t in ((ca, item.get("time_a_s")), (cb, item.get("time_b_s"))):
                    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{float(t or 0):.2f}", "-i", str(path(c, m)), "-frames:v", "1",
                                          "-vf", "scale=-2:360", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
                    im = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR) if raw else np.zeros((360, 360, 3), np.uint8)
                    ims.append(im)
                (OUT / "cards").mkdir(parents=True, exist_ok=True)
                cv2.imwrite(str(OUT / "cards" / f"card{n:03d}.jpg"), cv2.hconcat(ims))
                rows.append({"card": n, "kind": kind[:-1], "what": item.get("what"), "present": ""})
                key[n] = p
    if rows:
        with open(OUT / "cards.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["card", "kind", "what", "present"])
            w.writeheader()
            w.writerows(rows)
    (OUT / "cards_key.json").write_text(json.dumps(key))


def report():
    rows = list(csv.DictReader(open(OUT / "pairs.csv", newline="")))
    for r in rows:
        for k in ("sound_z", "sound_lag", "picture_z", "picture_lag", "s0_sound_z", "s0_sound_lag", "s0_picture_z", "s0_picture_lag"):
            r[k] = float(r[k])
        for k in ("landmark", "landmark_lag", "truth_lag", "inliers"):
            r[k] = float(r[k]) if r[k] not in ("", "None") else None
        for k in ("S0", "S1", "S2", "P"):
            r[k] = r[k] == "True"
    answers = json.loads((OUT / "spark.json").read_text())
    v = verdict(rows, answers)
    checked = list(csv.DictReader(open(OUT / "cards.csv", newline=""))) if (OUT / "cards.csv").exists() else []
    real = sum(c["present"].strip().lower() == "yes" for c in checked)
    unchecked = sum(not c["present"].strip() for c in checked)
    look_yes = [p for p, a in answers.items() if a["truth"] == "lookalike" and str(a.get("same_place")) == "yes"]
    v["bar4_model_evidence"] = {"same_place_yes_on_lookalikes": look_yes, "cards": len(checked), "present": real, "unchecked": unchecked,
                                "pass": not look_yes and not unchecked and (not checked or real / len(checked) >= 0.9)}
    v["pass"] = all(v[k]["pass"] for k in v if k.startswith("bar"))
    (OUT / "verdict.json").write_text(json.dumps(v, indent=1))
    for k, x in v.items():
        print(f"{k}: {x}")


# --- self-test (synthetic, no media, no network) ---

def selftest():
    rng = np.random.default_rng(0)
    # sign convention: b starts 3 s into a's timeline
    ev = np.zeros(60 * HZ)
    ev[rng.choice(len(ev), 80, replace=False)] = 1
    a, b = ev[500:4500] + 0.05 * rng.random(4000), ev[800:4800] + 0.05 * rng.random(4000)
    z, lag = xcorr(a, b)
    assert z > SOUND_Z and abs(lag - 3.0) < 0.02 and abs(xcorr(b, a)[1] + 3.0) < 0.02, (z, lag)
    assert xcorr(a, (rng.random(4000) < 0.02).astype(float))[0] < SOUND_Z

    # sound envelope from samples: clicks 3 s later in b give lag +3 (b[n] = a[n + 3 s])
    t = np.arange(40 * SR) / SR
    clicks = np.zeros_like(t)
    for s in rng.uniform(1, 39, 40):
        clicks[int(s * SR):int(s * SR) + 40] = rng.normal(0, 1, 40)
    noise = lambda: 0.01 * rng.normal(0, 1, len(t) - 3 * SR)
    sa, sb = sound_env_of((clicks[:len(t) - 3 * SR] + noise()).astype(np.float32)), sound_env_of((clicks[3 * SR:] + noise()).astype(np.float32))
    assert abs(xcorr(sa, sb)[1] - 3.0) < 0.05, xcorr(sa, sb)

    # window: trimmed start and 2 s before the clap
    assert len(window(np.zeros(30 * HZ), 20.0)) == 17 * HZ and len(window(np.zeros(30 * HZ), 2.5)) == 0

    # landmark lag convention: hashes of b are a's shifted 3 s earlier (b[n] = a[n + 3 s])
    fs = audio.HOP / audio.SR
    ha = {(i % 50, i % 7, i % 11): [int((5 + 0.07 * i) / fs)] for i in range(400)}
    hb = {k: [v[0] - int(3.0 / fs)] for k, v in ha.items()}
    sc, ll = landmark(ha, hb, (0, 99), (0, 99))
    assert sc > 0.9 and abs(ll - 3.0) < 0.1, (sc, ll)

    # rules
    base = {"sound_z": 9, "sound_lag": 4.0, "picture_z": 6, "picture_lag": 4.3, "landmark": None, "landmark_lag": None}
    assert rule_s1(base) and not rule_s1({**base, "picture_lag": 4.6}) and not rule_s1({**base, "sound_z": 7.9})
    assert rule_s2({**base, "sound_z": 3, "landmark": 0.05, "landmark_lag": 4.1}) and not rule_s2({**base, "sound_z": 3, "landmark": 0.02, "landmark_lag": 4.1})
    assert found_lag({**base, "sound_z": 3, "landmark": 0.05, "landmark_lag": 4.1}) == 4.1

    # pairs from a full manifest: 12 positives, 264 negatives per form (20 same place, 16 lookalike), 5 controls
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "m.csv"
        rows = []
        takes = [(s, k, s) for s in ("street", "talk", "park", "crossing", "indoor") for k in ("1", "2")] + [("street2", "1", "street"), ("park2", "1", "park")]
        for scene, take, kind in takes:
            for dev in ("iphone", "glasses"):
                stem = f"{scene}_t{take}_{dev}"
                rows.append({"file": f"raw/{stem}.mov", "scene": scene, "place_kind": kind, "take": take, "device": dev, "kind": "raw", "original": "", "clap_s": "30"})
                rows.append({"file": f"whatsapp/{stem}_whatsapp.mp4", "scene": scene, "place_kind": kind, "take": take, "device": dev,
                             "kind": "whatsapp", "original": f"raw/{stem}.mov", "clap_s": "30"})
        for name, *_ in CONTROLS:
            rows.append({"file": f"controls/{name}.mp4", "scene": "control", "place_kind": "control", "take": name, "device": "control",
                         "kind": "control", "original": "", "clap_s": "30"})
        for x in [c for a, _, b, _ in MUSIC for c in (a, b)]:
            rows.append({"file": f"controls/music_{x}.mp4", "scene": "control", "place_kind": "control", "take": f"music_{x}", "device": "control",
                         "kind": "control", "original": "", "clap_s": "30"})
        with open(f, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        ps = pairs(manifest(f))
    raw = [p for p in ps if p[3] == "raw" and p[2] != "control"]
    kinds = Counter(p[2] for p in raw)
    assert kinds["positive"] == 12 and sum(v for k, v in kinds.items() if k != "positive") == 264, kinds
    assert kinds["same_place_other_time"] == 20 and kinds["lookalike"] == 16, kinds
    assert sum(1 for p in ps if p[3] == "copy") == 264 and sum(1 for p in ps if p[2] == "control") == len(CONTROLS) + len(MUSIC)
    assert all(p[0].endswith("_iphone") for p in ps if p[2] == "positive")

    # Amendment 2 layout: 5 takes with both clips, street2's iPhone clip alone, no copies, the 3 controls that can be built
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "m.csv"
        clips = [(sc, t, sc, d) for sc, t in (("street", "1"), ("street", "2"), ("crossing", "1"), ("crossing", "2"), ("talk", "1"))
                 for d in ("iphone", "glasses")] + [("street2", "1", "street", "iphone")]
        with open(f, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["file", "scene", "place_kind", "take", "device", "kind", "original", "clap_s"])
            w.writeheader()
            w.writerows({"file": f"raw/{sc}_t{t}_{d}.mov", "scene": sc, "place_kind": pk, "take": t, "device": d, "kind": "raw",
                         "original": "", "clap_s": "30"} for sc, t, pk, d in clips)
            built = ["swap_street", "swap_crossing", "music_talk_t1_glasses", "music_crossing_t2_iphone"]  # what controls() can build
            w.writerows({"file": f"controls/{c}.mp4", "scene": "control", "place_kind": "control", "take": c, "device": "control",
                         "kind": "control", "original": "", "clap_s": "30"} for c in built)
        kinds = Counter(p[2] for p in pairs(manifest(f)))
    assert kinds == {"positive": 5, "same_place_other_time": 8, "lookalike": 4, "cross_scene": 38, "control": 3}, kinds
    # controls pair with each other or their partner, never with real clips of a control's own picture take
    assert ("swap_street", "street_t1_glasses", "control", "raw") in ps

    # verdict: a false claim fails bar 1; recall counts only lags within 0.2 s
    def row(kind, s1, lag=None, truth=None, form="raw", p=False):
        return {"a": "x", "b": "y", "kind": kind, "form": form, "S0": False, "S1": s1, "S2": s1, "P": p, "sound_lag": lag, "landmark_lag": None,
                "truth_lag": truth, "sound_z": 9 if s1 else 0, "picture_z": 6 if s1 else 0, "picture_lag": lag if s1 else 0, "landmark": None}
    good = [row("positive", True, 4.0, 4.1) for _ in range(9)] + [row("positive", False) for _ in range(3)] + [row("cross_scene", False) for _ in range(10)]
    v = verdict(good)
    assert v["bar1_false_same_moment"]["pass"] and v["bar2_recall"]["found"] == 9 and v["bar2_recall"]["pass"]
    assert not verdict(good + [row("lookalike", True, 1.0)])["bar1_false_same_moment"]["pass"]
    assert not verdict(good + [row("lookalike", False, p=True)])["bar3_same_place_on_lookalikes"]["pass"]
    off = [row("positive", True, 4.0, 4.5)] + good[1:]
    assert verdict(off)["bar2_recall"]["found"] == 8 and len(verdict(off)["bar2_recall"]["wrong_lag"]) == 1
    assert not verdict(good, {"x~y": {"truth": "cross_scene", "same_moment": "yes"}})["bar1_false_same_moment"]["pass"]

    # spark: cap stops before the worst case could pass it; seeded cross-scene draw is stable
    class Fake:
        def __init__(self):
            self.n = 0

        def video(self, p):
            return {"type": "input_file", "file_id": str(p)}

        def ask(self, content):
            self.n += 1
            return {"same_place": "no", "same_occasion": "no", "same_moment": "no"}, 0.01, "completed"

    global OUT
    real_out = OUT
    with tempfile.TemporaryDirectory() as tmp:
        OUT = Path(tmp)
        fake_rows = [{"a": f"a{i}", "b": f"b{i}", "kind": "cross_scene", "form": "raw"} for i in range(30)]
        assert [r["a"] for r in spark_pairs(fake_rows)] == [r["a"] for r in spark_pairs(list(reversed(fake_rows)))]
        (OUT / "enc").mkdir()
        mm = {}
        for r in fake_rows:
            for c in (r["a"], r["b"]):
                (OUT / "enc" / f"{c}.mp4").write_bytes(c.encode())
                mm[c] = {"file": f"{c}.mp4"}
        fk, logs = Fake(), []
        spent, ans = spark(mm, fake_rows, fk, cap=WORST_USD + 0.035, log=logs.append)
        assert fk.n == 4 and spent <= WORST_USD + 0.035 and any(x.startswith("spark: stopped") for x in logs), (fk.n, spent)
        fk2 = Fake()
        spark(mm, fake_rows, fk2, cap=10, log=logs.append)
        assert fk2.n == 8  # the 4 answered before are cached; 12 drawn pairs in all
    OUT = real_out
    print("selftest ok")


if __name__ == "__main__":
    {"claps": claps, "controls": controls, "score": score, "spark": spark, "report": report, "selftest": selftest}[sys.argv[1]]()
