#!/usr/bin/python3
"""Pre-scaled, antialiased bitmap-font glyphs for the RSDKv3 (Sonic CD) PS1 port (docs/28 phase 4).

Sonic CD's Help pages draw a large font (Game/HelpText.bin + Menu/HelpText.gif) with DrawText at 22 %
(body) and 37.5 % (headings). Upstream's software renderer samples that nearest-neighbour and thin
strokes vanish; the PC's GL renderer filters it. User decision (2026-09-24): render every glyph the
disc language uses at every scale the scripts use, here at build time, with area averaging, and draw
them 1:1 on the PS1 (ps1/render.cpp DrawBitmapText).

Per font used by DrawText in some stage (tools/atlas/object_sheets.py: fonts, texts, scales,
palettes of the stage):
  - glyphs: the font entries whose id is a character of the language's text files (LoadTextFile maps a
    character to the entry with that id);
  - size and placement exactly as upstream DrawBitmapText -> DrawSpriteScaled(-pivot, scale): width
    w * 4 * scale >> 11, offset -((-pivot * 4 * scale) >> 11);
  - pixels: source texels area-averaged; coverage < 25 % -> transparent (index 0), else the average
    text colour blended with the page background by coverage, snapped to the nearest palette entry
    (with a chroma penalty: no hue the text and page don't have) that has the same colour in every
    bank the stage loads (the Help pages switch banks);
  - glyphs shelf-packed into <sheet dir>/<font>_ps1.gif (pixel values = palette indices, as every
    sprite sheet; build-time only, the atlas puts it in VRAM) and a table Data/Game/<font>_ps1.bin:
      'PSF1', u16 scaleCount, char[64] sheet path (under Data/Sprites/), then per scale:
      u16 scale, u16 count, count x {u16 fontIndex, u16 x, y, w, h, s16 dx, dy} (little endian).
Self-check: the table is read back and every glyph's rect lies inside the written sheet.

Usage: prescale_font.py DATA_DIR [--lang en|jp]
"""
import os, struct, sys
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'atlas'))
sys.path.insert(0, os.path.join(HERE, '..'))
import build_atlas  # noqa: E402  (text_chars, LANG)
from object_sheets import object_sheets  # noqa: E402

# The page each stage's text is drawn on (its dominant colour is the antialiasing background).
PAGE_BACKGROUND = {'Help': 'Menu/HelpBG.gif'}
SHEET_W = 256


def game_lists(data):
    b = open(os.path.join(data, 'Game', 'GameConfig.bin'), 'rb').read()
    p = [0]

    def u8():
        p[0] += 1
        return b[p[0] - 1]

    def s():
        n = u8()
        p[0] += n
        return b[p[0] - n:p[0]].decode('latin1')
    s(), s(), s()
    n = u8()
    [s() for _ in range(n)], [s() for _ in range(n)]
    for _ in range(u8()):
        s()
        p[0] += 4
    [s() for _ in range(u8())], [s() for _ in range(u8())]
    lists = [[], [], [], []]
    for c in range(4):
        cat = {2: 3, 3: 2}.get(c, c)  # file order P, R, S, B -> engine lists (LoadGameConfig)
        lists[cat] = [(s(), s(), s(), u8())[0] for _ in range(u8())]
    return lists


def font_entries(path):
    """Upstream LoadFontFile: 20-byte records -> [(id, x, y, w, h, pivotX, pivotY)]."""
    d = open(path, 'rb').read()

    def signed(lo, hi):
        return lo + ((hi - 0x80) << 8) - 0x8000 if hi > 0x80 else lo + (hi << 8)
    out = []
    for p in range(0, len(d) - 19, 20):
        cid = struct.unpack_from('<I', d, p)[0]
        x, y = d[p + 4] | d[p + 5] << 8, d[p + 6] | d[p + 7] << 8
        w, h = d[p + 8] + 1 + (d[p + 9] << 8), d[p + 10] + 1 + (d[p + 11] << 8)
        out.append((cid, x, y, w, h, signed(d[p + 12], d[p + 13]), signed(d[p + 14], d[p + 15])))
    return out


def load_act(data, name):
    b = open(os.path.join(data, 'Palettes', name), 'rb').read()
    return np.frombuffer(b[:768], np.uint8).reshape(256, 3).astype(np.int32)


def scaled_glyph(src, rgb, w, h, W, H, bg, pal_ok, pal):
    """Area-average the glyph (w x h source indices, 0 = transparent) down to W x H palette indices."""
    out = np.zeros((H, W), np.uint8)
    for j in range(H):
        y0, y1 = j * h / H, (j + 1) * h / H
        for i in range(W):
            x0, x1 = i * w / W, (i + 1) * w / W
            cov, acc, area = 0.0, np.zeros(3), 0.0
            for sy in range(int(y0), min(h, int(np.ceil(y1)))):
                fy = min(y1, sy + 1) - max(y0, sy)
                for sx in range(int(x0), min(w, int(np.ceil(x1)))):
                    a = fy * (min(x1, sx + 1) - max(x0, sx))
                    area += a
                    if src[sy, sx]:
                        cov += a
                        acc += a * rgb[src[sy, sx]]
            if area <= 0 or cov / area < 0.25:
                continue
            k = cov / area
            colour = (acc / cov) * k + bg * (1 - k)
            # nearest entry, with a chroma penalty: an edge shade must not pick up a hue the text and the
            # page don't have (the palettes have few neutral greys)
            cand = pal[pal_ok]
            chroma = cand.max(1) - cand.min(1)
            want = colour.max() - colour.min()
            d = ((cand - colour) ** 2).sum(1) + 4.0 * (chroma - want) ** 2
            out[j, i] = pal_ok[int(d.argmin())]
    return out


def build(data, lang):
    build_atlas.LANG = lang
    lists = game_lists(data)
    done = set()
    for lst, folders in enumerate(lists):
        for pos, folder in enumerate(folders):
            info = object_sheets(data, lst, pos, folder).get(('*', 'text'))
            if not info or not info['scales']:
                continue
            for font in info['fonts']:
                for sheet in info['sheets']:
                    if (font, sheet) in done:
                        continue
                    done.add((font, sheet))
                    yield prescale(data, folder, font, sheet, info)


def prescale(data, folder, font, sheet, info):
    chars = build_atlas.text_chars(data, info['texts'])
    fpath = os.path.join(data, font[5:] if font.lower().startswith('data/') else font)
    entries = font_entries(fpath)
    im = Image.open(os.path.join(data, 'Sprites', sheet))
    src = np.array(im)
    rgb_sheet = np.array((im.getpalette() or [0] * 768)[:768], np.int32).reshape(-1, 3)
    pals = [load_act(data, name) for name, bank in sorted(info['palettes'], key=lambda t: t[1])]
    pal = pals[0]
    pal_ok = np.array([i for i in range(1, 256) if all((p[i] == pal[i]).all() for p in pals)], np.int64)
    bgsheet = PAGE_BACKGROUND.get(folder)
    if bgsheet:
        b = np.array(Image.open(os.path.join(data, 'Sprites', bgsheet)))
        vals, counts = np.unique(b[b != 0], return_counts=True)
        bg = pal[vals[counts.argmax()]].astype(np.float64)
    else:
        bg = np.array([0.0, 0.0, 0.0])
    # Text colours: the sheet's own palette (the font GIF carries the colours it was drawn with).
    glyphs = []  # (scale, index, image, dx, dy)
    for scale in sorted(info['scales']):
        sx = 4 * scale
        for i, (cid, x, y, w, h, px, py) in enumerate(entries):
            # entry 0 always: LoadTextFile maps characters the font lacks to it
            if cid not in chars and i != 0:
                continue
            W, H = w * sx >> 11, h * sx >> 11
            if W <= 0 or H <= 0:  # too small at this scale (as upstream: nothing drawn): an empty entry
                glyphs.append((scale, i, np.zeros((0, 0), np.uint8), 0, 0))
                continue
            g = scaled_glyph(src[y:y + h, x:x + w], rgb_sheet, w, h, W, H, bg, pal_ok, pal)
            glyphs.append((scale, i, g, -((-px * sx) >> 11), -((-py * sx) >> 11)))
    # Shelf packing (tallest first) into a 256-wide sheet.
    order = sorted(range(len(glyphs)), key=lambda k: -glyphs[k][2].shape[0])
    placed, x, y, shelf = {}, 0, 0, 0
    for k in order:
        H, W = glyphs[k][2].shape
        if not W or not H:
            placed[k] = (0, 0)
            continue
        if x + W > SHEET_W:
            x, y, shelf = 0, y + shelf, 0
        placed[k] = (x, y)
        x += W
        shelf = max(shelf, H)
    height = y + shelf
    out = np.zeros((max(height, 1), SHEET_W), np.uint8)
    for k, (gx, gy) in placed.items():
        g = glyphs[k][2]
        if g.size:
            out[gy:gy + g.shape[0], gx:gx + g.shape[1]] = g
    base, _ = os.path.splitext(sheet)
    psheet = base + '_ps1.gif'
    img = Image.fromarray(out, 'P')
    img.putpalette([int(v) for v in pal.reshape(-1)])
    img.save(os.path.join(data, 'Sprites', psheet))
    # Table
    fbase = os.path.splitext(os.path.basename(font))[0]
    tpath = os.path.join(os.path.dirname(fpath), fbase + '_ps1.bin')
    blob = bytearray(b'PSF1' + struct.pack('<H', len(info['scales'])) + psheet.encode().ljust(64, b'\0'))
    for scale in sorted(info['scales']):
        ks = [k for k in range(len(glyphs)) if glyphs[k][0] == scale]
        blob += struct.pack('<HH', scale, len(ks))
        for k in ks:
            g = glyphs[k][2]
            gx, gy = placed[k]
            blob += struct.pack('<HHHHHhh', glyphs[k][1], gx, gy, g.shape[1], g.shape[0], glyphs[k][3], glyphs[k][4])
    open(tpath, 'wb').write(blob)
    # Self-check: read the table back, every rect inside the sheet.
    p, n = 70, struct.unpack_from('<H', blob, 4)[0]
    for _ in range(n):
        sc, cnt = struct.unpack_from('<HH', blob, p)
        p += 4
        for _ in range(cnt):
            idx, gx, gy, gw, gh, dx, dy = struct.unpack_from('<HHHHHhh', blob, p)
            p += 14
            assert gx + gw <= SHEET_W and gy + gh <= out.shape[0], (font, idx)
    return '%s: %s on %s -> %s (%d glyphs, scales %s, sheet 256x%d)' % (folder, font, sheet, psheet, len(glyphs),
                                                                       sorted(info['scales']), out.shape[0])


def main():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    lang = a[a.index('--lang') + 1] if '--lang' in a else 'en'
    for report in build(a[0], lang):
        print(report)


if __name__ == '__main__':
    main()
