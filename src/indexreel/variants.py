"""Load a clip at gate resolution and make the gate fixtures from it.

The picture-in-picture and simulated re-film ideas come from my pre-window synthetic experiment
(not published). This code was rewritten after the window opened, with a neutral template.
"""
import subprocess

import cv2
import numpy as np

W, H, FPS, SECONDS = 640, 360, 5, 10
PIP_RECT = (30, 80, 318, 242)  # x1, y1, x2, y2 of the inset inside the template


def load(path):
    """First 10 s as 50 BGR frames of 640x360 at 5 fps (centre-cropped to 16:9, never squashed)."""
    vf = f"fps={FPS},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-t", str(SECONDS), "-vf", vf,
                          "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True, check=True).stdout
    frames = np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3)
    if len(frames) != FPS * SECONDS:
        raise ValueError(f"{path}: got {len(frames)} frames, need {FPS * SECONDS}")
    return list(frames)


def write(frames, path, fps=FPS, repeat=1):
    """H.264 mp4. repeat=2 turns 5 fps into 10 fps by duplicating each frame."""
    p = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
                          "-r", str(fps * repeat), "-i", "-", "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p",
                          "-movflags", "+faststart", str(path)], stdin=subprocess.PIPE)
    for f in frames:
        for _ in range(repeat):
            p.stdin.write(np.ascontiguousarray(f).tobytes())
    p.stdin.close()
    if p.wait():
        raise RuntimeError(f"ffmpeg failed for {path}")


def _text(img, s, org, scale, color, thick=2):
    cv2.putText(img, s, org, cv2.FONT_HERSHEY_SIMPLEX, scale, color, thick, cv2.LINE_AA)


def pip(frames, seed):
    """The clip boxed into a studio-style template. Every family in a split shares the template."""
    rng = np.random.default_rng(seed)
    x1, y1, x2, y2 = PIP_RECT
    yy, xx = np.mgrid[0:H, 0:W]
    base = np.dstack([40 + 30 * yy / H, 20 + 20 * xx / W, 10 + 10 * yy / H]).astype(np.uint8)
    out = []
    for i, f in enumerate(frames):
        g = base.copy()
        cv2.rectangle(g, (330, 60), (620, 300), (90, 70, 60), -1)  # presenter block
        cv2.circle(g, (475, 140 + int(3 * np.sin(i / 3))), 45, (120, 140, 170), -1)
        cv2.rectangle(g, (0, 300), (W, 345), (20, 120, 20), -1)
        _text(g, "LIVE  |  VIEWER VIDEO", (12, 330), 0.7, (255, 255, 255))
        g = np.clip(g + rng.normal(0, 3, g.shape), 0, 255).astype(np.uint8)
        g[y1:y2, x1:x2] = cv2.resize(f, (x2 - x1, y2 - y1), interpolation=cv2.INTER_AREA)
        cv2.rectangle(g, (x1 - 2, y1 - 2), (x2 + 1, y2 + 1), (255, 255, 255), 2)
        out.append(g)
    return out


def refilm_sim(frames, seed):
    """Simulated phone re-film of a monitor: bezel, moire, perspective, glare, blur, noise, gamma, shake."""
    rng = np.random.default_rng(seed)
    bez = 14
    sw, sh = W + 2 * bez, H + 2 * bez
    j = rng.uniform(-25, 25, 8)
    dst = np.float32([[70 + j[0], 45 + j[1]], [575 + j[2], 30 + j[3]], [600 + j[4], 330 + j[5]], [50 + j[6], 315 + j[7]]])
    Hm = cv2.getPerspectiveTransform(np.float32([[0, 0], [sw, 0], [sw, sh], [0, sh]]), dst)
    yy, xx = np.mgrid[0:H, 0:W]
    moire = (0.88 + 0.12 * np.sin(2 * np.pi * (xx * 0.31 + yy * 0.07)))[..., None]
    room = np.clip(np.dstack([np.full((H, W), v, np.uint8) for v in (38, 34, 30)]) + rng.normal(0, 8, (H, W, 3)), 0, 255)
    glare = np.zeros((H, W), np.float32)
    cv2.ellipse(glare, (int(W * 0.65), int(H * 0.3)), (110, 60), 20, 0, 360, 1.0, -1)
    glare = cv2.GaussianBlur(glare, (0, 0), 35)[..., None]
    lut = (255 * (np.arange(256) / 255) ** 0.8).astype(np.uint8)
    out = []
    for f in frames:
        scr = np.zeros((sh, sw, 3), np.uint8)
        scr[bez:bez + H, bez:bez + W] = (f * moire).astype(np.uint8)
        M = Hm.copy()
        M[0, 2] += rng.normal(0, 1.5)
        M[1, 2] += rng.normal(0, 1.5)
        warped = cv2.warpPerspective(scr, M, (W, H))
        mask = cv2.warpPerspective(np.full((sh, sw), 255, np.uint8), M, (W, H))[..., None] / 255.0
        g = warped * mask + room * (1 - mask)
        g = g * (1 - 0.35 * glare) + 255 * 0.35 * glare
        g = cv2.GaussianBlur(np.clip(g, 0, 255).astype(np.uint8), (3, 3), 0)
        g = np.clip(g + rng.normal(0, 5, g.shape), 0, 255).astype(np.uint8)
        out.append(cv2.LUT(g, lut))
    return out


VARIANTS = {"orig": lambda fr, seed: fr, "pip": pip, "refilm_sim": refilm_sim}
