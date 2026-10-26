import cv2
import numpy as np

from indexreel import quad

RECT = np.array([[100, 60], [500, 70], [490, 300], [110, 290]], np.int32)  # a slightly skewed screen


def frame_with_screen(seed=0):
    rng = np.random.default_rng(seed)
    img = np.full((360, 640, 3), 30, np.uint8)
    img = np.clip(img + rng.normal(0, 4, img.shape), 0, 255).astype(np.uint8)
    cv2.fillConvexPoly(img, RECT, (200, 190, 180))
    cv2.circle(img, (300, 180), 50, (40, 40, 200), -1)
    return img


def corner_error(q):
    return float(np.abs(q - quad.order_corners(RECT)).max())


def test_order_is_clockwise_from_top_left():
    q = quad.order_corners([[500, 70], [110, 290], [100, 60], [490, 300]])
    assert np.allclose(q, quad.order_corners(RECT))
    assert q[0].tolist() == [100, 60]


def test_mask_gives_the_screen():
    mask = np.zeros((360, 640), np.uint8)
    cv2.fillConvexPoly(mask, RECT, 1)
    assert corner_error(quad.quad_from_mask(mask)) < 4


def test_edge_control_finds_the_screen():
    gray = cv2.cvtColor(frame_with_screen(), cv2.COLOR_BGR2GRAY)
    best = quad.pick(quad.edge_candidates(gray), gray)
    assert best is not None and corner_error(best) < 8


def test_rejects_tiny_huge_and_thin():
    for pts in ([[10, 10], [60, 10], [60, 40], [10, 40]],          # about 2% of the frame
                [[2, 2], [637, 2], [637, 357], [2, 357]],          # about 98%
                [[100, 100], [112, 100], [112, 300], [100, 300]]):  # one edge under 16 px
        mask = np.zeros((360, 640), np.uint8)
        cv2.fillConvexPoly(mask, np.array(pts, np.int32), 1)
        assert quad.quad_from_mask(mask) is None


def test_warp_rectifies_and_falls_back():
    img = frame_with_screen()
    out = quad.warp(img, quad.order_corners(RECT))
    assert out.shape == (360, 640, 3) and abs(int(out[10, 10, 0]) - 200) < 10
    assert quad.warp(img, None).shape == (360, 640, 3)


def test_min_support_rejects_a_rectangle_with_no_edge():
    plain = np.full((360, 640), 90, np.uint8)  # nothing there, like a fixed inset on a street scene
    cand = quad.order_corners([[30, 80], [318, 80], [318, 242], [30, 242]])
    assert quad.pick([cand], plain, None, min_support=0.0) is not None
    assert quad.pick([cand], plain, None, min_support=0.5) is None
