#!/usr/bin/python3
"""Build-time BG line strips for the RSDKv3 (Sonic CD) PS1 tile renderer (docs/28 phase 3).

From the RSDKv2 (Nexus) port's builder, adapted to v3 data. A BG tile layer is drawn per line
(upstream DrawHLineScrollLayer): lines that share an X scroll form a band; with tiles a band costs
~21 primitives per 16 lines, and parallax (Sonic CD's R11A has 141 hParallax entries) makes a new X
scroll every 1-2 lines -> ~21 primitives per line, which overflows the chain. This tool pre-renders
layer lines into VRAM the stage's sprite atlas leaves free, as rows of one horizontal period of the layer
(the visual plane of its draw slot and tile flips baked in, index 0 = transparent), so a band of any height
costs 1-3 sprites. A 16-line row with <= 15 colours is stored as 4-bit texels (half the VRAM) through a
16-entry CLUT of master-palette indices (as the atlas's 4-bit clusters: the renderer fills it from the
palette with every bank / fade, so the picture is the same); other rows as 8-bit master-palette indices.

Lines are chosen per 16-line tile row, while the free VRAM lasts, by the tile primitives a row saves per halfword
of VRAM: its bands
(lineScroll runs, or lines on a deforming hParallax entry: a new X every line) times how often the camera shows it
(camera Y uniform over each act's height, the layer's parallaxFactor applied; any row when it scrolls by itself).
Ties: thin rows (runs < 16 lines) first, then the rows nearest to them. Rows left out are drawn with tiles.

Inputs (v3, as upstream Scene.cpp reads them): Backgrounds.bin (u8 layerCount, hParallax and
vParallax lists of 4-byte entries, per layer u8 xsize, ysize, type, u16 parallaxFactor, u8 speed,
RLE lineScroll (0xFF v n = v repeated n-1 times, 0xFF 0xFF ends), xsize*ysize u16 BE chunks),
128x128Tiles.bin (3 bytes per chunk tile: plane bit 4, flip bits 2-3, index bits 0-1 + byte 1),
Act*.bin (active layers + midpoint; acts may differ: union of their (layer, plane) keys), and the tile pixels from 16x16Tiles.vram (tools/tiles).
Per player (the sprite atlases differ, docs/28 3.2): the free VRAM is what <Stage>.atl (Sonic) /
<Stage>_t.atl (Tails) leaves, and the output is BGStrips.bin / BGStrips_t.bin.

Output Data/Stages/<Stage>/BGStrips[_t].bin (little endian):
  char[4] 'BGS3', u16 regionCount, u16 clutCount
  clut (20 B): u16 vramX, vramY, u8 map[16] (master palette index per 4-bit value; map[0] = 0)
  region (64 B): u8 layer, u8 plane, u16 line0, u16 lines (multiple of 16), u16 period (texels),
                 u8 pieceCount, u8 clut (0 = 8-bit, n = 4-bit through clut n - 1),
                 9 x { u16 vramX (halfwords), u16 vramY, u16 width (texels) }
  then per region, per piece: lines rows x width bytes (8-bit indices) or width / 2 bytes (4-bit, the
  first texel in the low nibble), rows top to bottom.
A piece starts at a 64-halfword column (texture page pageX = vramX / 64, u = 0) and stays inside one
256-row page (v = vramY & 255); pieces split the period into <= 256-texel parts. The CLUTs take the
atlas's 4-bit CLUT slots from the end of its list (tools/atlas/build_atlas.py CLUT_SLOTS; the atlas fills
them from the start).
Self-check: the file is decoded back and every stored line compared with the tile render.

Usage: build_bgstrips.py DATA_DIR [--stage NAME]
"""
import os, struct, sys
import numpy as np

ATLAS_COLUMNS = [5, 6, 7, 8, 13, 14, 15]  # tools/atlas/build_atlas.py COLUMNS
SCROLL_MAX = 20 * 128                     # PS1 TILELAYER_SCROLL_COUNT (Scene.hpp: 20 rows)
SCREEN_H = 240                            # SCREEN_YSIZE
MAX_REGIONS = 64
MAX_PIECES = 9  # widest Sonic CD BG period: 2304 texels (R83C/D)
REGION_BYTES = 10 + 6 * MAX_PIECES
PLAYERS = (('', ''), ('_t', '_t'))        # (atlas suffix, strips suffix)
CLUT_SLOTS = [(x, 240) for x in range(256, 320, 16)] + \
             [(x, y) for y in list(range(241, 256)) + list(range(496, 504)) for x in range(0, 320, 16)]  # build_atlas.py
CLUT_BYTES = 20


class StripError(Exception):
    pass


def load_tiles(sdir):
    """Tile pixels (1024 x 256 bytes, the fixed-up GIF: 0 = transparent) and chunk tiles."""
    v = open(os.path.join(sdir, '16x16Tiles.vram'), 'rb').read()
    pages = np.frombuffer(v[4 + 768:], np.uint8).reshape(4, 256, 256)
    gfx = np.zeros((1024, 16, 16), np.uint8)
    for t in range(1024):
        p, n = divmod(t, 256)
        gfx[t] = pages[p, (n // 16) * 16:(n // 16) * 16 + 16, (n % 16) * 16:(n % 16) * 16 + 16]
    t = open(os.path.join(sdir, '128x128Tiles.bin'), 'rb').read()
    tiles = []
    for i in range(len(t) // 3):
        e0, e1 = t[3 * i] & 0x3F, t[3 * i + 1]
        tiles.append((e1 + ((e0 & 3) << 8), (e0 >> 2) & 3, e0 >> 4))  # index, flip, plane
    return gfx, tiles


def load_backgrounds(sdir):
    b = open(os.path.join(sdir, 'Backgrounds.bin'), 'rb').read()
    j = 0

    def rb():
        nonlocal j
        v = b[j]
        j += 1
        return v
    lc = rb()
    deform = []  # hParallax entry -> deform flag (per-line ripple: every line gets its own X scroll)
    for pl in range(2):  # hParallax, vParallax: 4-byte entries (factor u16, speed, deform)
        n = rb()
        for _ in range(n):
            if pl == 0:
                deform.append(b[j + 3] != 0)
            j += 4
    layers = {}
    for L in range(1, lc + 1):
        xs, ys, ty = rb(), rb(), rb()
        pf = (rb() << 8) | rb()
        speed = rb()
        ls = []
        while True:
            c = rb()
            if c == 0xFF:
                c1 = rb()
                if c1 == 0xFF:
                    break
                ls += [c1] * (rb() - 1)
            else:
                ls.append(c)
        ls = (ls + [0] * SCROLL_MAX)[:SCROLL_MAX]
        grid = [[(rb() << 8) | rb() for _ in range(xs)] for _ in range(ys)]
        layers[L] = dict(xsize=xs, ysize=min(ys, SCROLL_MAX // 128), type=ty, lineScroll=ls, tiles=grid, deform=deform,
                         parallaxFactor=pf, scrollSpeed=speed)
    return layers


def act_layers(sdir):
    """The (activeTileLayers, midpoint) configurations of the stage's Act*.bin files. Strips are keyed
    by (layer, plane), so acts that differ just contribute more keys."""
    cfgs = set()
    for f in sorted(os.listdir(sdir)):
        if f.startswith('Act') and f.endswith('.bin'):
            a = open(os.path.join(sdir, f), 'rb').read()
            i = 1 + a[0]
            cfgs.add((tuple(a[i:i + 4]), a[i + 4]))
    return sorted(cfgs)


def act_heights(sdir):
    """Each Act*.bin's layout height in pixels (title, 4 active layers, midpoint, u8 xsize, u8 ysize chunks)."""
    hs = []
    for f in sorted(os.listdir(sdir)):
        if f.startswith('Act') and f.endswith('.bin'):
            a = open(os.path.join(sdir, f), 'rb').read()
            hs.append(a[1 + a[0] + 6] << 7)
    return hs


def row_visibility(L, full_h, heights):
    """Per 16-line row, the mean share of its lines on screen over camera Y uniform in [0, act height - 240] (upstream
    DrawHLineScrollLayer: line 0 on screen = yScrollOffset * parallaxFactor >> 8, wrapped to the layer height)."""
    w = np.zeros(full_h)
    n = 0
    for h in heights:
        cams = np.arange(0, max(h - SCREEN_H, 0) + 1)
        if L['scrollSpeed']:
            w += len(cams) * min(SCREEN_H, full_h) / full_h
        else:
            for y in (cams * L['parallaxFactor'] >> 8) % full_h:
                w[(np.arange(SCREEN_H) + y) % full_h] += 1
        n += len(cams)
    return w.reshape(-1, 16).mean(1) / max(n, 1)


def period_chunks(L):
    for p in range(1, L['xsize'] + 1):
        if L['xsize'] % p == 0 and all(row[x] == row[x % p] for row in L['tiles'] for x in range(L['xsize'])):
            return p
    return L['xsize']


def render_line(gfx, tiles, L, plane, ly, period):
    cy, ty, ty16 = ly >> 7, (ly & 0x7F) >> 4, ly & 0xF
    out = bytearray(period)
    for t in range(period):
        ch = L['tiles'][cy][t >> 7]
        tile, d, pl = tiles[(ch << 6) + ((t & 0x7F) >> 4) + 8 * ty]
        if pl != plane:
            continue
        tx, tyy = t & 0xF, ty16
        if d & 1:
            tx = 15 - tx
        if d & 2:
            tyy = 15 - tyy
        out[t] = gfx[tile, tyy, tx]
    return bytes(out)


class Grid(np.ndarray):
    pass


def free_grid(atl_path):
    """used[y, x] (halfwords): everything outside the atlas columns, plus the .atl blocks and the
    on-demand picture slots of its .pic (tools/atlas/build_atlas.py)."""
    used = Grid((512, 1024), np.uint8)
    used[:] = 1
    used.atlas_cluts = 0
    for c in ATLAS_COLUMNS:
        used[:, c * 64:c * 64 + 64] = 0
    if os.path.exists(atl_path):
        d = open(atl_path, 'rb').read()
        _, ns, nc, ncl, nb, fx, fy, _ = struct.unpack_from('<4sHHHHHHI', d, 0)
        used.atlas_cluts = ncl
        o = 20 + ns * 56 + nc * 16 + ncl * 20
        for k in range(nb):
            x, y, w, h = struct.unpack_from('<HHHH', d, o + 12 * k)
            used[y:y + h, x:x + w] = 1
    pic_path = atl_path[:-4] + '.pic'
    if os.path.exists(pic_path):
        d = open(pic_path, 'rb').read()
        slots, = struct.unpack_from('<H', d, 4)
        for k in range(slots):
            x, y, w, h = struct.unpack_from('<HHHH', d, 16 + 12 * k)
            used[y:y + h, x:x + w] = 1
    return used


def hw(width, depth):
    """VRAM halfwords of a row of `width` texels at `depth` bits."""
    return width * depth // 16


def fits(used, x, y, w, h):
    return x >= 0 and y >= 0 and x + w <= 1024 and y + h <= 512 and not used[y:y + h, x:x + w].any()


def alloc(used, w_hw, h, prefer=()):
    """A w_hw x h rect at a column start, inside one 256-row page and one texture page."""
    for pr in prefer:
        if fits(used, pr[0], pr[1], w_hw, h) and (pr[1] & 255) + h <= 256:
            return pr
    for py in (1, 0):
        for c in ATLAS_COLUMNS:
            x = c * 64
            if w_hw > 64 and (c + 1) not in ATLAS_COLUMNS:
                continue
            for y in range(py * 256, py * 256 + 256 - h + 1, 16):
                if fits(used, x, y, w_hw, h):
                    return (x, y)
    return None


def build_stage(data, name, atlas_suffix):
    sdir = os.path.join(data, 'Stages', name)
    if not os.path.exists(os.path.join(sdir, 'Backgrounds.bin')):
        return None, '%-7s no Backgrounds.bin' % name
    layers = load_backgrounds(sdir)
    cfgs = act_layers(sdir)
    heights = act_heights(sdir)
    gfx, tiles = load_tiles(sdir)
    atl = os.path.join(data, 'Sprites', 'Atlas', name + atlas_suffix + '.atl')

    jobs = []  # (layer, plane) drawn by the BG slots
    for slot, li, mid in [(slot, li, mid) for active, mid in cfgs for slot, li in enumerate(active)]:
        if 1 <= li < 9 and li in layers and layers[li]['type'] == 1 and layers[li]['xsize'] and layers[li]['ysize']:
            key = (li, 1 if slot >= mid else 0)
            if key not in [(j['layer'], j['plane']) for j in jobs]:
                L = layers[li]
                p = period_chunks(L) * 128
                pieces = [min(256, p - s) for s in range(0, p, 256)]
                if len(pieces) > MAX_PIECES:
                    raise StripError('%s layer %d period %d > %d texels' % (name, li, p, 256 * MAX_PIECES))
                full_h = L['ysize'] * 128
                ls = L['lineScroll'][:full_h]
                thin = set()
                i = 0
                while i < full_h:
                    j = i
                    while j < full_h and ls[j] == ls[i]:
                        j += 1
                    if j - i < 16:
                        thin.update(range(i >> 4, ((j - 1) >> 4) + 1))
                    i = j
                # Lines on a deforming parallax entry get a new X every line (water ripples): as thin.
                df = L['deform']
                thin.update(y >> 4 for y in range(full_h) if ls[y] < len(df) and df[ls[y]])
                bands = [1 + sum(1 for y in range(r * 16 + 1, r * 16 + 16)
                                 if ls[y] != ls[y - 1] or (ls[y] < len(df) and df[ls[y]])) for r in range(full_h >> 4)]
                vis = row_visibility(L, full_h, heights)
                cols = []
                for r in range(full_h >> 4):
                    c = set()
                    for ly in range(r * 16, r * 16 + 16):
                        c.update(render_line(gfx, tiles, L, key[1], ly, p))
                    cols.append(c - {0})
                depth = [4 if len(c) <= 15 else 8 for c in cols]
                jobs.append(dict(layer=li, plane=key[1], L=L, period=p, pieces=pieces, rows=full_h >> 4, thin=thin,
                                 gain=[round(float(v) * b, 6) for v, b in zip(vis, bands)], cols=cols, depth=depth))

    # Select rows: the most primitives saved first (ties: thin ones, then nearest to a thin row), while pieces fit.
    cands = []
    for ji, j in enumerate(jobs):
        for r in range(j['rows']):
            if not j['gain'][r]:  # never on screen: not worth its load time
                continue
            d = 0 if r in j['thin'] else (min(abs(r - t) for t in j['thin']) if j['thin'] else 1000 + r)
            cands.append((-j['gain'][r] * 8 / j['depth'][r], d, ji, r))
    cands.sort()
    used = free_grid(atl)
    selected = set()
    for _, d, ji, r in cands:
        j = jobs[ji]
        spots = []
        for w in j['pieces']:
            s = alloc(used, hw(w, j['depth'][r]), 16)
            if not s:
                break
            used[s[1]:s[1] + 16, s[0]:s[0] + hw(w, j['depth'][r])] = 1
            spots.append((s, w))
        if len(spots) == len(j['pieces']):
            selected.add((ji, r))
        else:
            for (x, y), w in spots:
                used[y:y + 16, x:x + hw(w, j['depth'][r])] = 0

    # Place the selected rows in line order, one piece at a time, so consecutive rows are contiguous.
    used = free_grid(atl)
    placed = {key: [] for key in sorted(selected)}
    for ji, j in enumerate(jobs):
        for k, w in enumerate(j['pieces']):
            for key in [key for key in sorted(selected) if key[0] == ji]:
                if len(placed[key]) != k:
                    continue
                prev = placed.get((ji, key[1] - 1))
                dep = j['depth'][key[1]]
                pref = [(prev[k][0], prev[k][1] + 16)] if prev and len(prev) > k and (prev[k][1] & 255) + 16 < 256 \
                    and j['depth'][key[1] - 1] == dep else []
                s = alloc(used, hw(w, dep), 16, pref)
                if s:
                    used[s[1]:s[1] + 16, s[0]:s[0] + hw(w, dep)] = 1
                    placed[key].append(s)
    chosen = {key: v for key, v in placed.items() if len(v) == len(jobs[key[0]]['pieces'])}

    regions = []  # consecutive rows stored contiguously
    for ji, j in enumerate(jobs):
        r = 0
        while r < j['rows']:
            if (ji, r) not in chosen:
                r += 1
                continue
            start, spots, dep, cols = r, chosen[(ji, r)], j['depth'][r], set(j['cols'][r])
            r += 1
            while (ji, r) in chosen and all(chosen[(ji, r)][k] == (spots[k][0], spots[k][1] + 16 * (r - start)) for k in range(len(spots))) \
                    and all((s[1] & 255) + 16 * (r - start + 1) <= 256 for s in spots) \
                    and j['depth'][r] == dep and (dep == 8 or len(cols | j['cols'][r]) <= 15):
                cols |= j['cols'][r]
                r += 1
            regions.append(dict(job=j, line0=start * 16, lines=(r - start) * 16, spots=spots, depth=dep, cols=cols))
    if len(regions) > MAX_REGIONS:
        raise StripError('%s: %d regions > %d' % (name, len(regions), MAX_REGIONS))

    # 4-bit regions' CLUTs (shared when the maps are equal), from the end of the atlas's CLUT slots.
    maps = []
    for g in regions:
        if g['depth'] == 4:
            m = [0] + sorted(g['cols']) + [0] * (15 - len(g['cols']))
            if m not in maps:
                maps.append(m)
            g['clut'] = maps.index(m)
    slots = CLUT_SLOTS[::-1][:len(maps)]
    if len(maps) + used.atlas_cluts > len(CLUT_SLOTS):
        raise StripError('%s: %d strip CLUTs + %d atlas CLUTs > %d slots' % (name, len(maps), used.atlas_cluts, len(CLUT_SLOTS)))
    out = bytearray(b'BGS3' + struct.pack('<HH', len(regions), len(maps)))
    for m, xy in zip(maps, slots):
        out += struct.pack('<HH', *xy) + bytes(m)
    blob = bytearray()
    for g in regions:
        j = g['job']
        ent = struct.pack('<BBHHHBB', j['layer'], j['plane'], g['line0'], g['lines'], j['period'], len(j['pieces']),
                          g['clut'] + 1 if g['depth'] == 4 else 0)
        for k in range(MAX_PIECES):
            ent += struct.pack('<HHH', *(g['spots'][k] + (j['pieces'][k],))) if k < len(j['pieces']) else struct.pack('<HHH', 0, 0, 0)
        assert len(ent) == REGION_BYTES
        out += ent
        lines = [render_line(gfx, tiles, j['L'], j['plane'], ly, j['period']) for ly in range(g['line0'], g['line0'] + g['lines'])]
        lut = {v: i for i, v in enumerate(maps[g['clut']])} if g['depth'] == 4 else None
        s0 = 0
        for w in j['pieces']:
            for row in lines:
                if lut:
                    blob += bytes(lut[row[t]] | (lut[row[t + 1]] << 4) for t in range(s0, s0 + w, 2))
                else:
                    blob += row[s0:s0 + w]
            s0 += w
    out += blob
    check(bytes(out), regions, gfx, tiles, name)

    summary = []
    for j in jobs:
        rows = sorted(r for (ji, r) in chosen if jobs[ji] is j)
        summary.append('L%d/p%d period %d: %d/%d rows (4-bit %d, thin %d, gain %.2f/%.2f)' % (
            j['layer'], j['plane'], j['period'], len(rows), j['rows'], sum(j['depth'][r] == 4 for r in rows), len(j['thin']),
            sum(j['gain'][r] for r in rows), sum(j['gain'])))
    vram = sum(g['lines'] * sum(hw(w, g['depth']) for w in g['job']['pieces']) for g in regions)
    return bytes(out), '%-7s regions %2d | CLUTs %2d | %s | VRAM %6d hw | file %6d B' % (
        name, len(regions), len(maps), '; '.join(summary) or 'no HScroll BG', vram, len(out))


def check(blob, regions, gfx, tiles, name):
    """Decode the file back and compare every stored line with the tile render."""
    count, nclut = struct.unpack_from('<HH', blob, 4)
    maps = [blob[8 + CLUT_BYTES * c + 4:8 + CLUT_BYTES * (c + 1)] for c in range(nclut)]
    base = 8 + nclut * CLUT_BYTES
    off = base + count * REGION_BYTES
    for i, g in enumerate(regions):
        e = blob[base + i * REGION_BYTES:base + (i + 1) * REGION_BYTES]
        layer, plane, line0, lines, period, npieces, clut = struct.unpack_from('<BBHHHBB', e, 0)
        widths = [struct.unpack_from('<HHH', e, 10 + 6 * k)[2] for k in range(npieces)]
        rows = [bytearray() for _ in range(lines)]
        for w in widths:
            for r in range(lines):
                if clut:
                    m = maps[clut - 1]
                    for b in blob[off:off + w // 2]:
                        rows[r] += bytes((m[b & 15], m[b >> 4]))
                    off += w // 2
                else:
                    rows[r] += blob[off:off + w]
                    off += w
        j = g['job']
        for r in range(lines):
            if bytes(rows[r]) != render_line(gfx, tiles, j['L'], plane, line0 + r, period):
                raise StripError('%s: self-check failed (layer %d line %d)' % (name, layer, line0 + r))


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    data = args[0]
    names = [args[args.index('--stage') + 1]] if '--stage' in args else sorted(os.listdir(os.path.join(data, 'Stages')))
    for name in names:
        for atlas_suffix, out_suffix in PLAYERS:
            try:
                blob, report = build_stage(data, name, atlas_suffix)
            except StripError as e:
                print('ERROR', e)
                sys.exit(1)
            print(report.replace(name, name + out_suffix, 1) if report else report)
            path = os.path.join(data, 'Stages', name, 'BGStrips%s.bin' % out_suffix)
            if blob and len(blob) > 8:
                open(path, 'wb').write(blob)
            elif os.path.exists(path):
                os.remove(path)


if __name__ == '__main__':
    main()
