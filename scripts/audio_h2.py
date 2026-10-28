"""H2: audio fingerprint as a second channel. Protocol: eval/audio-h2.md (frozen before any audio was fingerprinted).

  python scripts/audio_h2.py build     make A1_swap, A3_swap, B2_swap (picture of X, soundtrack of a donor clip)
  python scripts/audio_h2.py report    fingerprint every clip, score all pairs, check the pass bar
"""
import itertools
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.ndimage import maximum_filter
from scipy.signal import spectrogram

ROOT = Path(__file__).resolve().parents[1]
C = ROOT / "data" / "spark_pile" / "clips"
D = ROOT / "data" / "spark_h2"
SR, NPERSEG, HOP = 8000, 512, 256
FAN, DT_MIN, DT_MAX, BIN, MIN_HASHES = 5, 3, 62, 2, 200  # frame units: 0.1 s .. 2.0 s; offset bin 64 ms
DONORS = ["N2", "N3", "N4", "N5", "N6"]
SWAPS = ["A1", "A3", "B2"]
COMPILATION = "A1N1A3_e4"
HERE = Path(__file__).resolve().parent


def pcm(path):
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
                         capture_output=True).stdout
    return np.frombuffer(out, np.int16).astype(np.float32)


def hashes(path):
    """{hash: [time frames]} for one clip; empty if there is no audio."""
    x = pcm(path)
    if len(x) < NPERSEG * 4:
        return {}
    _, _, s = spectrogram(x, SR, nperseg=NPERSEG, noverlap=NPERSEG - HOP)
    s = np.log(s + 1e-10)
    peaks = (s == maximum_filter(s, size=15)) & (s > np.percentile(s, 80))
    f, t = np.nonzero(peaks)
    order = np.argsort(t)
    f, t = f[order], t[order]
    h = {}
    for i in range(len(t)):
        n = 0
        for j in range(i + 1, len(t)):
            dt = t[j] - t[i]
            if dt > DT_MAX:
                break
            if dt >= DT_MIN:
                h.setdefault((int(f[i]), int(f[j]), int(dt)), []).append(int(t[i]))
                n += 1
                if n == FAN:
                    break
    return h


def count(h):
    return sum(len(v) for v in h.values())


def score(a, b):
    """Votes in the best offset bin over the smaller clip's hash count."""
    votes = Counter()
    for k, ta in a.items():
        if k in b:
            for x in ta:
                for y in b[k]:
                    votes[(y - x) // BIN] += 1
    return max(votes.values()) / min(count(a), count(b)) if votes else 0.0


def rec(c):
    return None if c == COMPILATION else c.replace("_swap", "").split("_")[0]


def build():
    D.mkdir(parents=True, exist_ok=True)
    (D / "clips").mkdir(exist_ok=True)
    donor = next(d for d in DONORS if count(hashes(C / f"{d}.mp4")) >= MIN_HASHES)
    for x in SWAPS:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(C / f"{x}.mp4"), "-i", str(C / f"{donor}.mp4"), "-map", "0:v", "-map", "1:a",
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "64k", "-shortest", str(D / "clips" / f"{x}_swap.mp4")], check=True)
    (D / "donor.txt").write_text(donor)
    print("donor", donor)


def report():
    donor = (D / "donor.txt").read_text()
    paths = {p.stem: p for p in C.glob("*.mp4") if not p.stem.startswith("_")}
    paths.update({p.stem: p for p in (D / "clips").glob("*.mp4")})
    H = {n: hashes(p) for n, p in sorted(paths.items())}
    usable = {n for n, h in H.items() if count(h) >= MIN_HASHES}
    pile = sorted(n for n in H if not n.endswith("_swap"))
    print(f"usable audio (>= {MIN_HASHES} hashes): {len([n for n in pile if n in usable])}/{len(pile)} pile clips; unusable: {[n for n in pile if n not in usable]}")
    S = {frozenset((a, b)): score(H[a], H[b]) for a, b in itertools.combinations(sorted(H), 2) if a in usable and b in usable}
    s = lambda a, b: S.get(frozenset((a, b)))
    swapped = {"A2_e5"}
    sped = lambda a, b: "_e1" in a or "_e1" in b
    natural = [(a, b) for a, b in itertools.combinations(pile, 2) if frozenset((a, b)) in S]
    yes = lambda a, b: rec(a) and rec(a) == rec(b)
    neg = [(a, b) for a, b in natural if not yes(a, b) and COMPILATION not in (a, b)]
    tau = max(s(a, b) for a, b in neg)
    print(f"natural expected-no pairs with usable audio: {len(neg)}, tau = {tau:.4f} (highest)")
    pos = [(a, b) for a, b in natural if yes(a, b) and not sped(a, b) and not (swapped & {a, b})]
    ok = [p for p in pos if s(*p) >= tau]
    print(f"1 copies at or above tau: {len(ok)}/{len(pos)} = {len(ok) / max(1, len(pos)):.0%} (bar 90%)")
    print("  missed:", [(a, b, round(s(a, b), 4)) for a, b in pos if s(a, b) < tau])
    rep = [("A2", "A2_e5")] + [(x, f"{x}_swap") for x in SWAPS]
    print("2 sound replaced, audio below tau:", [(a, b, None if s(a, b) is None else round(s(a, b), 4)) for a, b in rep], "(bar all below)")
    reuse = [(donor, f"{x}_swap") for x in SWAPS]
    print("3 sound reused, audio at or above tau:", [(a, b, None if s(a, b) is None else round(s(a, b), 4)) for a, b in reuse], "(bar all at/above)")
    fam = lambda x: {c for c in pile if rec(c) == x}
    others = [(f"{x}_swap", c, s(f"{x}_swap", c)) for x in SWAPS for c in pile if c not in fam(x) | {donor, COMPILATION} and s(f"{x}_swap", c) is not None]
    print(f"4 swapped clips vs unrelated: max {max(o[2] for o in others):.4f}, at or above tau: {[o for o in others if o[2] >= tau]} (bar none)")
    print("\nreported:")
    print("  speed-changed _e1 pairs:", [(a, b, round(s(a, b), 4)) for a, b in natural if yes(a, b) and sped(a, b)][:8])
    print("  compilation vs sources:", [(c, round(s(COMPILATION, c), 4)) for c in pile if c != COMPILATION and rec(c) in ("A1", "N1", "A3") and s(COMPILATION, c) is not None])
    for name, grp in (("Phoenix cameras A1-A4", ["A1", "A2", "A3", "A4"]), ("Chelyabinsk Y,M,I", ["Y", "M", "I"]), ("Starship C0,C4,MA", ["C0", "C4", "MA"])):
        print(f"  same event different camera {name}:", [(a, b, round(s(a, b), 4)) for a, b in itertools.combinations(grp, 2) if s(a, b) is not None] or "no usable pair")
    print("  top 5 natural negatives:", sorted(((round(s(a, b), 4), a, b) for a, b in neg), reverse=True)[:5])
    json.dump({f"{'|'.join(sorted(k))}": v for k, v in S.items()}, open(D / "scores.json", "w"), indent=1)


def social():
    """Addendum A: real WhatsApp round trips. Families from MAP.csv; every other pair is a negative."""
    import csv
    base = ROOT / "data" / "iphone_by_me"
    allf = sorted(p for p in base.rglob("*") if p.suffix.lower() in (".mov", ".mp4") and "social_copies" not in p.parts)
    sha = lambda p: p.name  # MAP.csv records the same clip stored twice under one name (Addendum A.2)
    canon = {}
    for p in allf:  # duplicates (same name) collapse to the first path
        canon.setdefault(sha(p), p)
    files = sorted(canon.values())
    rel = lambda p: str(p.relative_to(base))
    root = {rel(p): rel(p) for p in files}
    mapped = {}
    for r in csv.DictReader(open(base / "social_copies" / "MAP.csv")):
        c = base / "social_copies" / r["copy"]
        orig = next((f for f in allf if f.name == r["original"]), None)
        if c.exists() and orig:
            root[rel(c)] = rel(canon[sha(orig)])
    H = {n: hashes(base / n) for n in root}
    usable = {n for n, h in H.items() if count(h) >= MIN_HASHES}
    print(f"{len(root)} clips, usable audio {len(usable)}; unusable: {sorted(set(root) - usable)}")
    pairs = [(a, b) for a, b in itertools.combinations(sorted(usable), 2)]
    sc = {(a, b): score(H[a], H[b]) for a, b in pairs}
    pos = [k for k in pairs if root[k[0]] == root[k[1]]]
    neg = [k for k in pairs if root[k[0]] != root[k[1]]]
    tau = max(sc[k] for k in neg)
    ok = [k for k in pos if sc[k] >= tau]
    lo, hi = wilson(len(ok), len(pos))
    print(f"positives with usable audio {len(pos)}, negatives {len(neg)}, tau {tau:.4f}")
    print(f"copies at or above tau {len(ok)}/{len(pos)} = {len(ok) / max(1, len(pos)):.0%}, Wilson 95% {lo:.2f} to {hi:.2f} (bar 90%)")
    print("lowest positives:", sorted((round(sc[k], 4), *k) for k in pos)[:4])
    print("top negatives:", sorted(((round(sc[k], 4), *k) for k in neg), reverse=True)[:5])


def wilson(k, n, z=1.96):
    import math
    if n == 0:
        return 0.0, 1.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


if __name__ == "__main__":
    {"build": build, "report": report, "social": social}[sys.argv[1]]()
