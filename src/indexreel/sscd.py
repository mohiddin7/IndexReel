"""Clip matching on SSCD embeddings (Meta's copy-detection model); same scoring as the Oct 22 spike."""
import cv2
import numpy as np
import torch

MEAN = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
STD = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)


def load(path):
    return torch.jit.load(str(path)).eval()


def embed(model, frames, batch=32):
    """L2-normalised SSCD embeddings (n, d) for BGR uint8 frames; shorter side resized to 224 px."""
    xs = []
    for f in frames:
        h, w = f.shape[:2]
        s = 224 / min(h, w)
        f = cv2.resize(f, (max(1, round(w * s)), max(1, round(h * s))), interpolation=cv2.INTER_AREA)
        xs.append(torch.from_numpy(cv2.cvtColor(f, cv2.COLOR_BGR2RGB)).permute(2, 0, 1).float() / 255)
    out = np.zeros((len(xs), 512), np.float32)
    with torch.no_grad():
        for shape in {tuple(x.shape) for x in xs}:  # one batch per frame size
            idx = [i for i, x in enumerate(xs) if tuple(x.shape) == shape]
            for j in range(0, len(idx), batch):
                part = idx[j:j + batch]
                b = (torch.stack([xs[i] for i in part]) - MEAN) / STD
                out[part] = torch.nn.functional.normalize(model(b), dim=1).numpy()
    return out


def frames_per_second(path):
    """The frame at the middle of each second of a video (OpenCV applies the rotation tag)."""
    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    kept, i, k = [], 0, 0
    while cap.grab():
        if i == round((k + 0.5) * fps):
            ok, f = cap.retrieve()
            if ok:
                kept.append(f)
            k += 1
        i += 1
    return kept


def clip_features(model, path):
    """(plain, mirrored) embeddings of a clip's one-frame-per-second sample."""
    fr = frames_per_second(path)
    return embed(model, fr), embed(model, [np.ascontiguousarray(f[:, ::-1]) for f in fr])


def _directed(q, r):
    return float((q @ r.T).max(1).mean())


def score(a, b):
    """Symmetric clip similarity in [-1, 1]; a and b are (plain, mirrored) pairs from clip_features."""
    (ap, af), (bp, bf) = a, b
    return max(_directed(ap, bp), _directed(bp, ap), _directed(af, bp), _directed(bp, af))


def _best_diagonal(s, min_overlap):
    """Highest mean of s along any diagonal at least min_overlap long; -1 when none is."""
    means = [d.mean() for k in range(-s.shape[0] + 1, s.shape[1]) if len(d := np.diagonal(s, offset=k)) >= min_overlap]
    return float(max(means)) if means else -1.0


def aligned_score(a, b):
    """Like score(), but matched frames must line up at one constant time offset (1 frame per second).

    ponytail: constant offset only, so speed changes are missed; a short clip slid along a long one tries many
    offsets, which favours false matches. Upgrade to a monotone alignment (DTW) if copies with changed speed matter.
    """
    (ap, af), (bp, _) = a, b
    n = min(len(ap), len(bp))
    need = min(n, max(3, -(-n // 2)))
    return max(_best_diagonal(ap @ bp.T, need), _best_diagonal(af @ bp.T, need))
