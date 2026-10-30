"""Decode a clip and localise a screen or inset on one frame per second, as the gate's OpenCV control does."""
import cv2
import numpy as np

from indexreel import quad
from indexreel.match import open_video

THETA = 0.9     # edge-support cut-off, set on dev (eval/gate.md, Amendment 1)
LONG_SIDE = 640  # frames are scaled to this before localising, the size the quad rule was written for
RATE = 5        # the localiser sees this many frames per second and keeps one in RATE


def _fit(frame):
    s = LONG_SIDE / max(frame.shape[:2])
    return cv2.resize(frame, (round(frame.shape[1] * s), round(frame.shape[0] * s)), interpolation=cv2.INTER_AREA), s


def sample(path, theta=THETA):
    """One localised frame per second of a clip.

    Returns a dict: fps, duration_s, width, height (source), frames (BGR, rectified to 640x360 where a quad was
    accepted, otherwise the whole frame at its own aspect ratio) and quads (source pixels, or None per frame).
    Frame i stands for second i. The frame kept for second i is the third of the five the localiser sees, and its
    motion term compares it with the frame before it, as in the gate.

    ponytail: a portrait re-film of a landscape screen is not handled; the rectified output is always 640x360.
    """
    cap = open_video(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = fps / RATE
    frames, quads, prev = [], [], None
    i = j = n = w = h = 0
    while cap.grab():
        n += 1
        if i == round(j * step):
            ok, f = cap.retrieve()
            if ok:
                if not w:
                    h, w = f.shape[:2]
                small, s = _fit(f)
                g = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
                if j % RATE == RATE // 2:
                    q = quad.pick(quad.edge_candidates(g), g, prev, theta)
                    frames.append(small if q is None else quad.warp(small, q))
                    quads.append(None if q is None else q / s)
                prev = g
            j += 1
        i += 1
    if not frames:
        raise ValueError(f"{path}: no frames decoded (shorter than half a second, or not a video)")
    return {"fps": fps, "duration_s": n / fps, "width": w, "height": h, "frames": frames, "quads": quads}


def median_quad(quads):
    """Median over the frames that had a quad, as a list of four [x, y], or None if none did."""
    got = [q for q in quads if q is not None]
    return np.median(np.stack(got), axis=0).round(1).tolist() if got else None
