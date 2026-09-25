#!/usr/bin/python3
"""Stage tile sets for the RSDKv3 (Sonic CD) PS1 port: 16x16Tiles.gif -> 16x16Tiles.vram (build time).

What upstream LoadStageGIFFile (RSDKv3/Scene.cpp) does at runtime, done here once:
  - decode the 16x16384 GIF (1024 tiles of 16x16, 8-bit master-palette indices);
  - pixels equal to the first pixel's value become 0 (transparent), as its loop over TILESET_SIZE;
  - the GIF's colour table: entries 0x80-0xFF are copied into the active palette
    (SetPaletteEntry(-1, c, r, g, b)); the PS1 load path applies them from the .vram header.
.vram layout (the RSDKv2 port's format, PS1UploadTileSet): u16 BE width 256, u16 BE height 1024,
768-byte palette (the GIF's, 256 x RGB), then 4 texture pages of 256x256 8-bit texels (65,536 B
each, row-major); page p holds tiles 256p..256p+255 in a 16x16 grid, tile n at texel
(16*(n%16), 16*(n/16)): one DMA per page (128 halfwords x 256 lines), no CPU re-pack at runtime.
Self-check: every page is unpacked back to the tile strip and compared with the fixed-up GIF pixels.

Usage: convert_tiles.py DATA_DIR    (every DATA_DIR/Stages/*/16x16Tiles.gif)
"""
import glob, os, struct, sys
import numpy as np
from PIL import Image

PAGES, TILES_PER_PAGE = 4, 256


def load(path):
    im = Image.open(path)
    if im.mode != 'P' or im.size != (16, 16 * PAGES * TILES_PER_PAGE):
        raise ValueError('%s: expected a 16x16384 paletted GIF, got %s %s' % (path, im.mode, im.size))
    px = np.frombuffer(im.tobytes(), np.uint8).copy()
    px[px == px[0]] = 0  # upstream: transparent = tilesetGFXData[0]
    pal = bytes((im.getpalette() or [])[:768]).ljust(768, b'\0')
    return px, pal


def pack(px):
    # strip: tile t = rows 16t..16t+15; page p, tile n = t - 256p at (n%16, n//16) in the page
    strip = px.reshape(PAGES * TILES_PER_PAGE, 16, 16)
    pages = np.zeros((PAGES, 256, 256), np.uint8)
    for t in range(PAGES * TILES_PER_PAGE):
        p, n = divmod(t, TILES_PER_PAGE)
        tx, ty = (n % 16) * 16, (n // 16) * 16
        pages[p, ty:ty + 16, tx:tx + 16] = strip[t]
    return pages


def unpack(pages):
    out = np.zeros((PAGES * TILES_PER_PAGE, 16, 16), np.uint8)
    for t in range(PAGES * TILES_PER_PAGE):
        p, n = divmod(t, TILES_PER_PAGE)
        tx, ty = (n % 16) * 16, (n // 16) * 16
        out[t] = pages[p, ty:ty + 16, tx:tx + 16]
    return out.reshape(-1)


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    n = 0
    for gif in sorted(glob.glob(os.path.join(sys.argv[1], 'Stages', '*', '16x16Tiles.gif'))):
        px, pal = load(gif)
        pages = pack(px)
        if not np.array_equal(unpack(pages), px):
            sys.exit('self-check failed: %s' % gif)
        blob = struct.pack('>HH', 256, 256 * PAGES) + pal + pages.tobytes()
        back = np.frombuffer(blob[4 + 768:], np.uint8).reshape(PAGES, 256, 256)
        if blob[4:4 + 768] != pal or not np.array_equal(unpack(back), px):
            sys.exit('self-check (file) failed: %s' % gif)
        open(os.path.join(os.path.dirname(gif), '16x16Tiles.vram'), 'wb').write(blob)
        n += 1
    print('tiles: %d stages -> 16x16Tiles.vram (%d bytes each), self-check exact' % (n, 4 + 768 + PAGES * 65536))


if __name__ == '__main__':
    main()
