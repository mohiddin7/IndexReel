"""Clip matching on PDQ hashes (the gate's primary matcher; docs of the frozen rules are in eval/gate.md)."""
import cv2
import numpy as np
import pdqhash

SAMPLE_EVERY = 10  # the gate writes 10 fps by duplicating 5 fps frames, so this is 1 frame per second
MAX_HAMMING = 31   # PDQ's usual match distance


def hashes(frames):
    """PDQ bits (n, 256) for the given BGR frames, and the same for the mirrored frames."""
    plain, flipped = [], []
    for f in frames:
        rgb = cv2.cvtColor(f, cv2.COLOR_BGR2RGB)
        plain.append(pdqhash.compute(rgb)[0])
        flipped.append(pdqhash.compute(np.ascontiguousarray(rgb[:, ::-1]))[0])
    return np.array(plain).astype(bool), np.array(flipped).astype(bool)


READER = 2  # frame-reader version, part of the match cache key: 2 = rotation tag applied (1 read phone clips sideways)


def open_video(path):
    """cv2.VideoCapture with the rotation tag applied (OpenCV's FFMPEG backend leaves phone clips sideways otherwise)."""
    cap = cv2.VideoCapture(str(path))
    cap.set(cv2.CAP_PROP_ORIENTATION_AUTO, 1)
    return cap


def sampled_hashes(path):
    """hashes() of every SAMPLE_EVERY-th decoded frame of a video."""
    cap = open_video(path)
    kept, i = [], 0
    while True:
        ok, f = cap.read()
        if not ok:
            break
        if i % SAMPLE_EVERY == 0:
            kept.append(f)
        i += 1
    return hashes(kept)


def _directed(q, r):
    """Share of query frames with a reference frame within MAX_HAMMING, plus a small closeness tie-break."""
    d = (q[:, None, :] != r[None, :, :]).sum(-1).min(1)
    return float((d <= MAX_HAMMING).mean() + 0.001 * (1 - d / 256).mean())


def score(a, b):
    """Symmetric clip similarity; a and b are (plain, flipped) pairs from sampled_hashes."""
    (ap, af), (bp, bf) = a, b
    return max(_directed(ap, bp), _directed(bp, ap), _directed(af, bp), _directed(bp, af))
