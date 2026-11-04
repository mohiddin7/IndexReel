"""Write site/data.js: the SSCD similarity grid and embeddings drawn on the home page, from two clips.

Usage: python scripts/site_grid.py <copy.mp4> <original.mp4> [--out site/data.js]
The page uses data/x_demo/post4_ev1_cropped_mirrored.mp4 (my cropped, mirrored copy) against
data/x_demo/post1_usgs_ev1_original.mp4 (USGS Kilauea fissure 20, May 19 2018, public domain).
Needs data/models/sscd_disc_mixup.torchscript.pt (see README Quickstart). Prints the aligned score the page quotes.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from indexreel import sscd  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('copy')
    ap.add_argument('original')
    ap.add_argument('--out', default='site/data.js')
    ap.add_argument('--model', default='data/models/sscd_disc_mixup.torchscript.pt')
    a = ap.parse_args()
    m = sscd.load(a.model)
    fa, fb = sscd.clip_features(m, a.copy), sscd.clip_features(m, a.original)
    score, offset, start, end, mirrored = sscd.aligned_match(fa, fb)
    grid = fa[0] @ fb[0].T  # plain orientation, the one aligned_match chose for this pair
    data = {
        'grid': [[round(float(v), 2) for v in row] for row in grid],
        'emb': [[round(float(v) * 8, 2) for v in fa[0][i][:64]] for i in range(2, 8)],  # first 64 of 512 values, x8 for drawing
        'aligned': round(score, 2), 'offset': offset, 'span': [start, end], 'mirrored': mirrored,
    }
    with open(a.out, 'w') as f:
        f.write('// Written by scripts/site_grid.py: SSCD cosine similarities, one frame per second, copy (rows) against original (columns).\n')
        f.write('window.IR=' + json.dumps(data, separators=(',', ':')) + ';\n')
    print(f'aligned {score:.3f} offset {offset} s span {start}-{end} s mirrored {mirrored}; grid {np.shape(grid)} -> {a.out}')


if __name__ == '__main__':
    main()
