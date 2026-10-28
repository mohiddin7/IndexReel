"""Clip matching on SSCD embeddings (Meta's copy-detection model); same scoring as the Oct 22 spike."""
import cv2
import numpy as np
import torch

MIRROR_MARGIN = 0.02  # the flipped alignment must beat the plain one by this much (eval/match-thresholds.md, Amendment 2)
CORE_COS = 0.4        # a frame belongs to the core span when its cosine along the alignment is at least this

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
    """(mean, offset, start, length) of the diagonal of s with the highest mean among those at least min_overlap long."""
    best = (-1.0, 0, 0, 0)
    for k in range(-s.shape[0] + 1, s.shape[1]):
        d = np.diagonal(s, offset=k)
        if len(d) >= min_overlap and d.mean() > best[0]:
            best = (float(d.mean()), k, max(0, -k), len(d))
    return best


def aligned_match(a, b):
    """Aligned score of two clips, with where it was found.

    Returns (score, offset, start, end, mirrored): frame i of a lines up with frame i + offset of b for i in
    [start, end); with one frame per second these are seconds. mirrored is True when a had to be mirrored, which needs the flipped
    alignment to beat the plain one by MIRROR_MARGIN: SSCD is nearly flip-invariant, so smaller differences are noise.

    ponytail: constant offset only, so speed changes are missed; a short clip slid along a long one tries many
    offsets, which favours false matches. Upgrade to a monotone alignment (DTW) if copies with changed speed matter.
    """
    (ap, af), (bp, _) = a, b
    n = min(len(ap), len(bp))
    need = min(n, max(3, -(-n // 2)))
    plain, mirror = _best_diagonal(ap @ bp.T, need), _best_diagonal(af @ bp.T, need)
    best, flipped = (mirror, True) if mirror[0] > plain[0] + MIRROR_MARGIN else (plain, False)
    return best[0], best[1], best[2], best[2] + best[3], flipped


def aligned_score(a, b):
    """Like score(), but matched frames must line up at one constant time offset."""
    return aligned_match(a, b)[0]


def core_span(a, b, offset, start, end, flipped):
    """Where the alignment really matches: the longest run of consecutive frames along it with cosine >= CORE_COS.

    a and b are clip_features pairs, (offset, start, end, flipped) come from aligned_match. Returns (start, end) in
    seconds of a (frame i covers [i, i + 1)), or None when no frame reaches CORE_COS. The aligned overlap is at least
    half the shorter clip, so for a short segment inside a longer clip it is wider than the segment; this is not.
    """
    x = (a[1] if flipped else a[0])[start:end]
    cos = np.einsum("ij,ij->i", x, b[0][start + offset:end + offset])
    best, first = (0, 0), None
    for j, ok in enumerate(cos >= CORE_COS):
        first = (j if first is None else first) if ok else None
        if first is not None and j + 1 - first > best[1] - best[0]:
            best = (first, j + 1)
    return (start + best[0], start + best[1]) if best[1] > best[0] else None


def cover_spans(a, b, offset, flipped, band):
    """Where each clip has frames matching the other: ((a start, a end), (b start, b end)) or None.

    The offset used is the one with the most frames at CORE_COS or more along it (closest to `offset`, the aligned
    one, on ties): on a nearly static scene the aligned score can prefer a shorter diagonal. A frame of a counts when
    it reaches CORE_COS against a frame of b within `band` frames of that offset, and the other way round, so dips
    and jump cuts do not cut a span short. Each clip's span is the shorter of its own counted frames' extent and the
    other clip's extent moved by the offset: in slow footage the frames just outside a shared stretch still match
    within the band, which widens the first by up to `band` frames on each side.
    """
    x = a[1] if flipped else a[0]
    s = x @ b[0].T
    na, nb = s.shape
    k = max(range(-na + 1, nb), key=lambda d: (int((np.diagonal(s, d) >= CORE_COS).sum()), -abs(d - offset)))
    i, j = np.indices(s.shape)
    ok = (s >= CORE_COS) & (np.abs(j - i - k) <= band)
    ra, rb = np.flatnonzero(ok.any(1)), np.flatnonzero(ok.any(0))
    if not len(ra):
        return None
    own_a, own_b = (int(ra[0]), int(ra[-1]) + 1), (int(rb[0]), int(rb[-1]) + 1)
    moved = lambda sp, d, n: (max(0, sp[0] + d), min(n, sp[1] + d))
    short = lambda p, q: p if p[1] - p[0] <= q[1] - q[0] else q
    return short(own_a, moved(own_b, -k, na)), short(own_b, moved(own_a, k, nb))
