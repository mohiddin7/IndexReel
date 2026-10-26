"""Find the screen or inset quad in a frame.

One rule set serves the OpenCV control and SAM masks, as frozen in docs/eval/gate.md.
"""
import cv2
import numpy as np

W, H = 640, 360


def order_corners(pts):
    """Clockwise, starting at the minimum x+y (ties: x, then y)."""
    pts = np.asarray(pts, np.float32).reshape(4, 2)
    c = pts.mean(axis=0)
    pts = pts[np.argsort(np.arctan2(pts[:, 1] - c[1], pts[:, 0] - c[0]))]  # y points down: ascending angle is clockwise
    first = min(range(4), key=lambda i: (pts[i, 0] + pts[i, 1], pts[i, 0], pts[i, 1]))
    return np.roll(pts, -first, axis=0)


def _valid(approx, shape):
    if len(approx) != 4 or not cv2.isContourConvex(approx):
        return None
    h, w = shape[:2]
    pts = approx.reshape(4, 2).astype(np.float32)
    area = cv2.contourArea(pts) / (w * h)
    edges = np.linalg.norm(pts - np.roll(pts, 1, axis=0), axis=1)
    if not 0.05 <= area <= 0.90 or edges.min() < 16:
        return None
    return order_corners(pts)


def quad_from_contour(cnt, shape):
    hull = cv2.convexHull(cnt)
    eps = 0.02 * cv2.arcLength(hull, True)
    return _valid(cv2.approxPolyDP(hull, eps, True), shape)


def quad_from_mask(mask, shape=None):
    """Largest 8-connected component of a boolean mask, as one quad or None."""
    m = (np.asarray(mask) > 0).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    if n < 2:
        return None
    biggest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    cnts, _ = cv2.findContours((lab == biggest).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return quad_from_contour(max(cnts, key=cv2.contourArea), shape or m.shape) if cnts else None


def edge_map(gray):
    return cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 1), 50, 150)


def edge_candidates(gray, extra=()):
    """OpenCV control: every contour in the closed Canny map through the quad rule, plus fixed rectangles."""
    edges = cv2.morphologyEx(edge_map(gray), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    cnts, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    found = [quad_from_contour(c, gray.shape) for c in cnts if len(c) >= 4]
    found += [_valid(np.asarray(q, np.float32).reshape(-1, 1, 2).astype(np.int32), gray.shape) for q in extra]
    out = []
    for q in found:
        if q is not None and not any(np.abs(q - o).max() < 1 for o in out):
            out.append(q)
    return out


def rank_key(quad, gray, prev, edges):
    """Smaller is better: most motion inside, then edge support on the boundary, then area, then coordinates."""
    poly = quad.astype(np.int32)
    inside = np.zeros(gray.shape, np.uint8)
    cv2.fillConvexPoly(inside, poly, 1)
    ring = np.zeros_like(inside)
    cv2.polylines(ring, [poly], True, 1, 1)
    motion = 0.0 if prev is None else float(np.abs(gray.astype(np.int16) - prev.astype(np.int16))[inside > 0].mean())
    near = cv2.dilate(edges, np.ones((5, 5), np.uint8)) > 0  # within 2 px
    return (-motion, -float(near[ring > 0].mean()), -float(inside.sum()), tuple(quad.ravel().tolist()))


def pick(cands, gray, prev=None):
    if not cands:
        return None
    edges = edge_map(gray)
    return min(cands, key=lambda q: rank_key(q, gray, prev, edges))


def warp(frame, quad):
    """Rectify to W x H. Without a quad, fall back to the full frame (callers log it)."""
    if quad is None:
        return cv2.resize(frame, (W, H), interpolation=cv2.INTER_AREA)
    dst = np.float32([[0, 0], [W - 1, 0], [W - 1, H - 1], [0, H - 1]])
    return cv2.warpPerspective(frame, cv2.getPerspectiveTransform(quad.astype(np.float32), dst), (W, H))
