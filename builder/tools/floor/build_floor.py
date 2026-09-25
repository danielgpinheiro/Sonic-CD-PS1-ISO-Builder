#!/usr/bin/python3
"""Far-floor textures for Sonic CD's special stages (docs/28 phase 7): the 3D floor seen far away.

The special stages draw their floor (layout layer 0, 32 x 32 chunks = 4096 x 4096 px) with upstream
Draw3DSkyLayer / Draw3DFloorLayer: a perspective walk over the tiles per screen line. The PS1 renderer
(ps1/render.cpp PS1Draw3DFloor) draws the near floor as projected 16x16 tile quads and the far lines, where
a screen pixel covers several floor pixels, as one textured line each, from this texture: the whole floor
at 1/16 scale (one texel per 16 x 16 tile), 8-bit master-palette indices (so palette animation still
applies), each texel the most frequent visible colour of its tile area (0 = transparent when most of it is).

Home in VRAM: tile page 3 (X 704-831, Y 256-511), free in every special stage (their tile sets end below
tile 768: checked here). Output Data/Stages/<Stage>/Floor.vram: 'FLR1', u16 width, u16 height (texels),
u16 scale (world px per texel), u16 0, then width x height index bytes. Self-check: read back and compared.

Usage: build_floor.py DATA_DIR
"""
import os, struct, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'bgstrips'))
from build_bgstrips import load_tiles  # noqa: E402  (16x16Tiles.vram pixels + 128x128Tiles.bin)

SCALE = 16
STAGES = ['SS%d' % i for i in range(1, 9)]


def act_file(sdir):
    """The stage's act layout: each special stage has one, named after its number (SS2 -> Act2.bin)."""
    acts = sorted(f for f in os.listdir(sdir) if f.startswith('Act') and f.endswith('.bin'))
    return os.path.join(sdir, acts[0]) if acts else None


def floor_layout(sdir):
    """Layer 0 of the act (upstream LoadActLayout): chunk ids, big-endian, xsize x ysize."""
    a = open(act_file(sdir), 'rb').read()
    i = 1 + a[0] + 5  # title, activeTileLayers[4], midpoint
    xs, ys = a[i], a[i + 1]
    i += 2
    rows = []
    for y in range(ys):
        rows.append([(a[i + 2 * x] << 8) | a[i + 2 * x + 1] for x in range(xs)])
        i += 2 * xs
    return xs, ys, rows


def build(data, st):
    sdir = os.path.join(data, 'Stages', st)
    gfx, tiles = load_tiles(sdir)
    used = [t for t in range(1024) if gfx[t].any()]
    if used and max(used) >= 768:
        raise SystemExit('ERROR %s: tiles reach %d: tile page 3 is not free for the floor texture' % (st, max(used)))
    xs, ys, rows = floor_layout(sdir)
    W, H = xs * 8, ys * 8  # texels: one per 16x16 tile
    tex = np.zeros((H, W), np.uint8)
    # Upstream reads every tile regardless of its plane (tile3DFloorBuffer).
    for ty in range(H):
        for tx in range(W):
            ch = rows[ty >> 3][tx >> 3]
            tile, d, _ = tiles[(ch << 6) + (tx & 7) + 8 * (ty & 7)]
            px = gfx[tile]
            if d & 1:
                px = px[:, ::-1]
            if d & 2:
                px = px[::-1, :]
            vals, counts = np.unique(px, return_counts=True)
            opaque = counts[vals != 0].sum()
            if opaque * 2 < px.size:
                continue
            vis = vals != 0
            tex[ty, tx] = vals[vis][counts[vis].argmax()]
    assert W <= 256 and H <= 256, (st, W, H)
    out = struct.pack('<4sHHHH', b'FLR1', W, H, SCALE, 0) + tex.tobytes()
    path = os.path.join(sdir, 'Floor.vram')
    open(path, 'wb').write(out)
    back = open(path, 'rb').read()
    assert back[:4] == b'FLR1' and np.array_equal(np.frombuffer(back[12:], np.uint8).reshape(H, W), tex), st
    return '%s: floor %dx%d chunks -> %dx%d texels (1/%d), %d%% opaque, tiles used up to %d' % (
        st, xs, ys, W, H, SCALE, 100 * (tex != 0).mean(), max(used) if used else -1)


def main():
    data = sys.argv[1]
    for st in STAGES:
        if os.path.isdir(os.path.join(data, 'Stages', st)) and act_file(os.path.join(data, 'Stages', st)):
            print(build(data, st))


if __name__ == '__main__':
    main()
