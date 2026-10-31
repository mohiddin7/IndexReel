"""Geometric and temporal check that a confirmed copy is the same recording (frozen research verifier, ported).

For a pair A (the input) and B (a candidate) it answers whether A's picture is a 2D edit of B's picture at matching
moments (crop, scale, mirror, small rotation, speed change): SSCD at 1 fps picks candidate frame pairs, SIFT + RANSAC
registers them (similarity against homography), then the moving detail of both clips is correlated frame by frame and
a line tB = slope * tA + offset is searched for. Verdict same / different / cannot tell by THRESH, which was fixed
before any labelled pair was scored. A `different` must never veto a `same` from elsewhere: it is wrong on some true
copies. The thresholds and the logic are unchanged from the frozen version; do not tune them without a new test.
"""
import pathlib
import time

import cv2
import numpy as np

SSCD_PATH = pathlib.Path(__file__).resolve().parents[2] / "data" / "models" / "sscd_disc_mixup.torchscript.pt"

A_FPS, B_FPS = 5, 10          # temporal sampling; B finer so a matching moment is at most 0.05 s away
KEY_SIDE, T_SIDE = 640, 320   # long side for key-frame SIFT, and for per-frame registration
A_MAX_S = 20                  # at most this much of A around its key frame goes into the matrix
SLOPES = (1 / 3, 3.0)         # allowed speed ratios dtB/dtA
ROW_MIN = 15                  # A rows (3 s at 5 fps) a line must cover
THRESH = dict(               # fixed before any labelled pair was scored (README, "Rules set in advance")
    reg_inliers=20,          # similarity inliers for a usable registration
    reg_share=0.6,           # similarity inliers / homography inliers
    rows_min=15,             # valid A rows (3 s at 5 fps) before a 'different' may be said
    motion_min=1.5,          # median std of A's moving-detail residual (grey levels) below this = still scene
    same_support=0.5,        # share of valid rows whose peak lies on the line
    same_z=6.0,              # line contrast against shifted lines
    same_ncc=0.15,           # mean correlation along the line
    diff_z=3.0,              # below this (or support < diff_support) with motion = different
    diff_support=0.25,
)
_sift = {}


def sift(n):
    if n not in _sift:
        _sift[n] = cv2.SIFT_create(nfeatures=n, contrastThreshold=0.02)  # half the default: foggy, rainy, compressed frames (set on n6, disclosed)
    return _sift[n]


def fit(img, side):
    s = side / max(img.shape[:2])
    return cv2.resize(img, (max(1, round(img.shape[1] * s)), max(1, round(img.shape[0] * s))), interpolation=cv2.INTER_AREA)


def decode(path, fps):
    """Upright decode. Returns (key frames at 1 fps BGR KEY_SIDE, their times, grey T_SIDE frames at fps, their times)."""
    cap = cv2.VideoCapture(str(path))
    cap.set(cv2.CAP_PROP_ORIENTATION_AUTO, 1)
    src = cap.get(cv2.CAP_PROP_FPS) or 30.0
    keys, kt, grey, gt = [], [], [], []
    i, nk, ng = 0, 0, 0
    while cap.grab():
        t = i / src
        want_k, want_g = t + 0.5 / src >= nk + 0.5, t + 0.5 / src >= ng / fps
        if want_k or want_g:
            ok, f = cap.retrieve()
            if ok:
                if want_k:
                    keys.append(fit(f, KEY_SIDE)); kt.append(t); nk += 1
                if want_g:
                    grey.append(cv2.cvtColor(fit(f, T_SIDE), cv2.COLOR_BGR2GRAY)); gt.append(t); ng += 1
        i += 1
    if not keys:
        raise ValueError(f"{path}: no frames")
    return keys, np.array(kt), grey, np.array(gt)


_model = None
LAST = {}  # the last pair's matrix and residuals, for debugging
DEC = {}   # decoded clips (4K HEVC takes ~30 s each)
EMB = {}   # SSCD key-frame embeddings per path within one run (the matcher has them already in the pipeline)


def sscd(frames):
    import torch
    global _model
    if _model is None:
        torch.set_num_threads(4)
        _model = torch.jit.load(str(SSCD_PATH)).eval()
    mean = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
    std = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)
    xs = []
    for f in frames:
        s = 224 / min(f.shape[:2])
        f = cv2.resize(f, (max(1, round(f.shape[1] * s)), max(1, round(f.shape[0] * s))), interpolation=cv2.INTER_AREA)
        xs.append(torch.from_numpy(cv2.cvtColor(f, cv2.COLOR_BGR2RGB)).permute(2, 0, 1).float() / 255)
    with torch.no_grad():
        out = [torch.nn.functional.normalize(_model((torch.stack(xs[k:k + 32]) - mean) / std), dim=1)
               for k in range(0, len(xs), 32)]
    return torch.cat(out).numpy()


def kp(img, n=2000):
    g = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    k, d = sift(n).detectAndCompute(g, None)
    return np.float32([p.pt for p in k]).reshape(-1, 2), d


def matches(fa, fb, ratio=0.8):
    (pa, da), (pb, db) = fa, fb
    if da is None or db is None or len(da) < 3 or len(db) < 3:
        return np.zeros((0, 2), np.float32), np.zeros((0, 2), np.float32)
    m = cv2.BFMatcher(cv2.NORM_L2).knnMatch(da, db, k=2)
    good = [x[0] for x in m if len(x) == 2 and x[0].distance < ratio * x[1].distance]
    return pa[[g.queryIdx for g in good]], pb[[g.trainIdx for g in good]]


def register(fa, fb, thr=3.0):
    """Similarity and homography RANSAC from A to B on SIFT matches. thr in pixels of the key size."""
    a, b = matches(fa, fb)
    out = dict(n=len(a), sim_in=0, h_in=0, M=None)
    if len(a) < 6:
        return out
    M, inl = cv2.estimateAffinePartial2D(a, b, method=cv2.RANSAC, ransacReprojThreshold=thr, maxIters=3000, confidence=0.999)
    H, hin = cv2.findHomography(a, b, cv2.RANSAC, thr, maxIters=3000, confidence=0.999)
    out["h_in"] = int(hin.sum()) if hin is not None else 0
    if M is None:
        return out
    out.update(sim_in=int(inl.sum()), M=M)
    # residual split: similarity residuals of the homography inliers (or the similarity's own at 3x thr), top vs bottom
    sel = hin.ravel().astype(bool) if hin is not None and hin.sum() >= 8 else (
        np.linalg.norm(a @ M[:, :2].T + M[:, 2] - b, axis=1) < 3 * thr)
    r = np.linalg.norm(a[sel] @ M[:, :2].T + M[:, 2] - b[sel], axis=1)
    y = b[sel, 1]
    if len(r) >= 8:
        mid = np.median(y)
        top, bot = np.median(r[y <= mid]), np.median(r[y > mid])
        out.update(res_med=float(np.median(r)), res_top=float(top), res_bot=float(bot))
    return out


def sim_params(M):
    sc = float(np.hypot(M[0, 0], M[1, 0]))
    return sc, float(np.degrees(np.arctan2(M[1, 0], M[0, 0])))


def h3(M):
    return np.vstack([M, [0, 0, 1]]) if M.shape == (2, 3) else M


def chain(frames, ref, step_ok=8):
    """Similarity mapping each grey frame to frames[ref] (None where it fails). Direct to ref when that works, else
    composed through the neighbour nearer ref, so a pan that leaves the key frame's view stays registered."""
    feats = [kp(f, 600) for f in frames]

    def reg(i, j):
        a, b = matches(feats[i], feats[j])
        if len(a) < 8:
            return None
        M, inl = cv2.estimateAffinePartial2D(a, b, method=cv2.RANSAC, ransacReprojThreshold=2.0)
        return None if M is None or inl.sum() < step_ok else h3(M)

    out = [None] * len(frames)
    out[ref] = np.eye(3)
    for order in (range(ref + 1, len(frames)), range(ref - 1, -1, -1)):
        prev = ref
        for k in order:
            M = reg(k, ref)
            if M is None and out[prev] is not None:
                step = reg(k, prev)
                M = None if step is None else out[prev] @ step
            out[k] = M
            prev = k
    return out


def shot(grey, k):
    """(lo, hi) indices of the shot holding frame k: cut where the mean change between frames is over 5x the median."""
    th = [cv2.resize(g, (80, 45), interpolation=cv2.INTER_AREA).astype(np.float32) for g in grey]
    d = np.array([0.0] + [np.abs(th[n] - th[n - 1]).mean() for n in range(1, len(th))])
    cut = d > max(20.0, 5 * np.median(d[1:]) if len(d) > 1 else 0)
    lo = k
    while lo > 0 and not cut[lo]:
        lo -= 1
    hi = k + 1
    while hi < len(grey) and not cut[hi]:
        hi += 1
    return lo, hi


def warp_stack(frames, maps, size):
    w, h = size
    X = np.full((len(frames), h, w), np.nan, np.float32)
    for k, (f, W) in enumerate(zip(frames, maps)):
        if W is None:
            continue
        g = cv2.warpAffine(cv2.GaussianBlur(f, (0, 0), 1.0).astype(np.float32), W[:2], (w, h), flags=cv2.INTER_LINEAR,
                           borderMode=cv2.BORDER_CONSTANT, borderValue=np.nan)
        X[k] = g
    return X


def residual(X):
    """Subtract each pixel's temporal median (static content); pixels seen in too few frames are dropped."""
    valid = ~np.isnan(X)
    keep = valid.sum(0) >= max(5, 0.1 * len(X))  # a pan sees each pixel in only some frames
    med = np.nanmedian(np.where(keep, X, np.nan), axis=0) if keep.any() else np.zeros(X.shape[1:])
    R = X - med
    R[:, ~keep] = np.nan
    return R - np.nanmean(R, axis=(1, 2), keepdims=True)  # zero mean per frame: a global brightness change is not a match


def change(R, k):
    """Central difference over k frames each side (0.4 s for both clips at their rates): what changed, not what is.
    ponytail: assumes a speed ratio near 1 for the difference span; at 0.5x or 2x the spans differ by 2x (weaker peak)."""
    D = np.full_like(R, np.nan)
    D[k:-k] = R[2 * k:] - R[:-2 * k]
    return D - np.nanmean(D, axis=(1, 2), keepdims=True)


def corr_matrix(RA, RB):
    ma, mb = ~np.isnan(RA.reshape(len(RA), -1)), ~np.isnan(RB.reshape(len(RB), -1))
    ra, rb = np.nan_to_num(RA.reshape(len(RA), -1)), np.nan_to_num(RB.reshape(len(RB), -1))
    ma, mb = ma.astype(np.float32), mb.astype(np.float32)
    num = ra @ rb.T
    den = np.sqrt((ra ** 2) @ mb.T * (ma @ (rb ** 2).T)) + 1e-6
    ov = ma @ mb.T
    S = num / den
    need = 0.3 * ma.sum(1, keepdims=True).clip(1)
    S[(ov < need) | (ov < 200)] = np.nan
    return S


def ridge(S, ta, tb):
    """Hough search over lines tB = slope * tA + offset (slope in SLOPES, log steps; offset in 0.05 s steps).

    A line's score is the mean correlation over the A rows it maps inside B (at least ROW_MIN of them and 30% of A).
    ridge_z compares the best line with every line whose offset is at least 1 s away at A's middle (robust z).
    support: share of the line's rows whose own peak lies within 0.3 s of it.
    """
    res = dict(rows=0, support=0.0, ridge_z=0.0, line_ncc=float("nan"), slope=float("nan"), offset=float("nan"))
    ok_rows = np.isfinite(S).sum(1) >= 10
    if ok_rows.sum() < 4:
        return res
    Sz = np.where(np.isfinite(S), S, np.nan)
    need = max(ROW_MIN, int(0.3 * ok_rows.sum()))
    mid = (ta[0] + ta[-1]) / 2
    dtb = np.median(np.diff(tb)) if len(tb) > 1 else 0.1
    scores = []
    for a in np.exp(np.linspace(np.log(SLOPES[0]), np.log(SLOPES[1]), 121)):
        for c in np.arange(tb[0], tb[-1] + 1e-6, 0.05):  # c = tB at A's middle
            t = c + a * (ta - mid)
            inside = ok_rows & (t >= tb[0] - dtb / 2) & (t <= tb[-1] + dtb / 2)
            if inside.sum() < need:
                continue
            j = np.round(np.interp(t[inside], tb, np.arange(len(tb)))).astype(int)  # B times are not evenly spaced
            v = Sz[np.flatnonzero(inside), j]
            v = v[np.isfinite(v)]
            if len(v) >= need:
                scores.append((float(v.mean()), a, c, len(v)))
    if not scores:
        return res
    sc = np.array(scores)
    k = int(sc[:, 0].argmax())
    best, a, c, n = sc[k]
    null = sc[np.abs(sc[:, 2] - c) >= 1.0, 0]
    if len(null) < 10:
        return res
    med = np.median(null)
    z = (best - med) / (1.4826 * np.median(np.abs(null - med)) + 1e-6)
    t = c + a * (ta - mid)
    on = ok_rows & (t >= tb[0]) & (t <= tb[-1])
    peaks = tb[np.nanargmax(np.where(np.isfinite(S[on]), S[on], -9), axis=1)]
    res.update(rows=int(n), support=float(np.mean(np.abs(peaks - t[on]) <= 0.3)), ridge_z=float(z), line_ncc=float(best),
               slope=float(a), offset=float(c - a * mid))
    return res


def verify(path_a, path_b):
    t0 = time.time()
    for p in (path_a, path_b):
        if str(p) not in DEC:
            DEC[str(p)] = decode(p, B_FPS)
    for p in list(DEC)[:-6]:  # ponytail: tiny cache, enough for pairs listed clip by clip
        if p not in (str(path_a), str(path_b)):
            DEC.pop(p)
    for p in list(EMB):  # a long-running bot: embeddings go with their decoded clip
        if p not in DEC:
            EMB.pop(p)
    ka, kta, ga, gta = DEC[str(path_a)]
    step = B_FPS // A_FPS
    ga, gta = ga[::step], gta[::step]
    kb, ktb, gb, gtb = DEC[str(path_b)]
    t_dec = time.time() - t0
    if str(path_a) not in EMB:
        EMB[str(path_a)] = sscd(ka), sscd([np.ascontiguousarray(f[:, ::-1]) for f in ka])
    if str(path_b) not in EMB:
        EMB[str(path_b)] = sscd(kb), sscd([np.ascontiguousarray(f[:, ::-1]) for f in kb])
    (ea, em), (eb, _) = EMB[str(path_a)], EMB[str(path_b)]
    t_sscd = time.time() - t0 - t_dec
    t1 = time.time()
    C = np.maximum(ea @ eb.T, em @ eb.T)
    # candidates: best cell of the 5 best A seconds (at least 2 s apart)
    order = np.argsort(-C.max(1))
    cand = []
    for i in order:
        if all(abs(i - c[0]) >= 2 for c in cand):
            cand.append((int(i), int(C[i].argmax())))
        if len(cand) == 5:
            break
    fb_cache, best = {}, None
    for i, j in cand:
        if j not in fb_cache:
            fb_cache[j] = kp(kb[j])
        for flip in (False, True):
            a_img = np.ascontiguousarray(ka[i][:, ::-1]) if flip else ka[i]
            r = register(kp(a_img), fb_cache[j])
            r.update(i=i, j=j, flip=flip)
            if best is None or r["sim_in"] > best["sim_in"]:
                best = r
    out = dict(sscd_best=round(float(C.max()), 3), flip=best["flip"], sim_inliers=best["sim_in"], h_inliers=best["h_in"],
               matches=best["n"], key_a_s=round(float(kta[best["i"]]), 2), key_b_s=round(float(ktb[best["j"]]), 2))
    reg_ok = best["M"] is not None and 0.05 <= sim_params(best["M"])[0] <= 20 and best["sim_in"] >= THRESH["reg_inliers"] and \
        best["sim_in"] >= THRESH["reg_share"] * max(best["h_in"], 1)
    if best["M"] is not None:
        sc, rot = sim_params(best["M"])
        hA, wA = ka[best["i"]].shape[:2]
        hB, wB = kb[best["j"]].shape[:2]
        box = cv2.transform(np.float32([[[0, 0], [wA, 0], [wA, hA], [0, hA]]]), best["M"])[0]
        x0, y0 = box.min(0) / [wB, hB]
        x1, y1 = box.max(0) / [wB, hB]
        out.update(scale=round(sc, 3), rot_deg=round(rot, 1), box_b=[round(float(v), 3) for v in (x0, y0, x1, y1)],
                   res_med=round(best.get("res_med", np.nan), 2), res_top=round(best.get("res_top", np.nan), 2),
                   res_bot=round(best.get("res_bot", np.nan), 2))
    out["reg_ok"] = bool(reg_ok)
    S = None
    if reg_ok:
        # temporal: A window of at most A_MAX_S s around its key, B window from the allowed slopes
        ia = int(np.argmin(np.abs(gta - kta[best["i"]])))
        slo, shi = shot(ga, ia)
        lo, hi = max(slo, ia - A_MAX_S * A_FPS // 2), min(shi, ia + A_MAX_S * A_FPS // 2)
        ta = gta[lo:hi]
        tbk = ktb[best["j"]]
        # the key pair is a place match, not a time match (on a still shot SSCD's best B second is arbitrary), so B gets
        # its whole shot, capped at what the fastest allowed speed could cover either side of the key
        span = (SLOPES[1] * (ta[-1] - ta[0]) + 1,) * 2
        jb = int(np.argmin(np.abs(gtb - tbk)))
        blo, bhi = shot(gb, jb)
        sel = (gtb >= tbk - span[0]) & (gtb <= tbk + span[1]) & (np.arange(len(gtb)) >= blo) & (np.arange(len(gtb)) < bhi)
        tb = gtb[sel]
        GA = [np.ascontiguousarray(g[:, ::-1]) if best["flip"] else g for g in ga[lo:hi]]
        GB = [g for g, s in zip(gb, sel) if s]
        ra = ia - lo
        rb = int(np.argmin(np.abs(tb - tbk)))
        mapA, mapB = chain(GA, ra), chain(GB, rb)
        # key-size similarity A->B to grey size B->A, then into a half-size canvas of A's key frame
        sA, sB = T_SIDE / KEY_SIDE, T_SIDE / KEY_SIDE
        M = h3(best["M"])
        M_t = np.diag([sB, sB, 1]) @ M @ np.diag([1 / sA, 1 / sA, 1])
        canvas = np.diag([0.5, 0.5, 1])
        hA, wA = GA[ra].shape
        size = (wA // 2, hA // 2)
        WA = [None if m is None else canvas @ m for m in mapA]
        WB = [None if m is None else canvas @ np.linalg.inv(M_t) @ m for m in mapB]
        XA, XB = warp_stack(GA, WA, size), warp_stack(GB, WB, size)
        RA, RB = change(residual(XA), 1), change(residual(XB), B_FPS // A_FPS)
        motion = float(np.nanmedian([np.nanstd(r) for r in RA if np.isfinite(r).any()])) if np.isfinite(RA).any() else 0.0
        S = corr_matrix(RA, RB)
        rd = ridge(S, ta, tb)
        LAST.update(S=S, ta=ta, tb=tb, RA=RA, RB=RB)
        out.update(motion=round(motion, 2), a_rows=rd["rows"], support=round(rd["support"], 2), ridge_z=round(rd["ridge_z"], 1),
                   line_ncc=round(rd["line_ncc"], 3), slope=round(rd["slope"], 3), offset_s=round(rd["offset"], 2),
                   a_reg=f"{sum(m is not None for m in mapA)}/{len(mapA)}", b_reg=f"{sum(m is not None for m in mapB)}/{len(mapB)}")
    out["verdict"], out["reason"] = decide(out)
    out["t_verify_s"] = round(time.time() - t1, 2)
    out["t_decode_s"], out["t_sscd_s"] = round(t_dec, 2), round(t_sscd, 2)
    return out


def decide(o):
    T = THRESH
    if not o["reg_ok"]:
        return "cannot tell", f"no similarity registration ({o['sim_inliers']} similarity / {o['h_inliers']} homography inliers)"
    if o.get("motion", 0) < T["motion_min"]:
        return "cannot tell", f"registered, but almost nothing moves in A (motion {o.get('motion')}): still scene"
    if o["support"] >= T["same_support"] and o["ridge_z"] >= T["same_z"] and o["line_ncc"] >= T["same_ncc"]:
        return "same", (f"registered ({'mirrored, ' if o['flip'] else ''}scale {o['scale']}) and moving detail lines up: "
                        f"tB = {o['slope']} tA + {o['offset_s']} s, ridge z {o['ridge_z']}, support {o['support']}")
    if o["a_rows"] >= T["rows_min"] and (o["ridge_z"] < T["diff_z"] or o["support"] < T["diff_support"]):
        return "different", (f"static content registers but moving detail never lines up "
                             f"(ridge z {o['ridge_z']}, support {o['support']}, {o['a_rows']} rows)")
    return "cannot tell", f"in between (ridge z {o.get('ridge_z')}, support {o.get('support')}, rows {o.get('a_rows')})"
