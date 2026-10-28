"""Audio fingerprint: spectrogram peak pairs voted on one time offset (measured in eval/audio-h2-result.md)."""
import subprocess
from collections import Counter

import numpy as np
from scipy.ndimage import maximum_filter
from scipy.signal import spectrogram

SR, NPERSEG, HOP = 8000, 512, 256
FAN, DT_MIN, DT_MAX, BIN, MIN_HASHES = 5, 3, 62, 2, 200  # frame units: 0.1 s .. 2.0 s; offset bin 64 ms


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
    """Votes in the best offset bin over the smaller clip's hash count; None when either clip has too little sound."""
    if count(a) < MIN_HASHES or count(b) < MIN_HASHES:
        return None
    votes = Counter()
    for k, ta in a.items():
        if k in b:
            for x in ta:
                for y in b[k]:
                    votes[(y - x) // BIN] += 1
    return max(votes.values()) / min(count(a), count(b)) if votes else 0.0
