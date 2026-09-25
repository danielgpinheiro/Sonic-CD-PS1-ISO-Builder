#!/usr/bin/python3
"""Per-stage sprite atlas for the RSDKv3 (Sonic CD) PS1 port (golden rule: build time only).

Copied from the RSDKv2 port's builder (RSDKv2-ps1/tools/atlas); only the input changed. Sonic
CD ships bytecode, not script text, so the frames come from tools/rsdkmanifest: it runs every
stage's object startups with the engine's own code and lists each frame with its sheet
(`frame <sheetID> x y w h obj|ani <name>`). List positions that share a folder are unioned.
A frame that runs past the bottom of its sheet continues into the next loaded sheet of the same
width, as on PC, where all sheets sit back to back in one pixel buffer: the Menu headings address
MenuGfx2_<language> through MenuGfx1 that way. Such frames are split per real sheet.
Frames that overlap merge into clusters (bounding boxes); clusters larger than a texture
page (256x256 texels) are cut at 256. A cluster with <= 15 colours becomes a 4-bit
texture (clusters share 16-entry CLUTs of master-palette indices, entry 0 = transparent),
otherwise 8-bit. Clusters are packed into the free VRAM columns (64 halfwords x 256 lines;
an 8-bit page spans 2 columns) and the 4-bit CLUTs go in the rows under the framebuffers.
(v3 plays videos full-screen, outside the stage renderer: no FMV page is reserved here.)

Output: <Data>/Sprites/Atlas/<Stage>.atl (little-endian):
  header : 'ATL1', u16 sheetCount, clusterCount, clutCount, blockCount,
           u16 fmvX, fmvY (0xFFFF = no FMV reservation), u32 dataOffset
  sheet  : char name[48] (path under Data/Sprites/, lower case), u16 firstCluster,
           clusterCount, width, height                                  (56 B)
  cluster: u16 srcX, srcY, w, h, u8 tpageX, tpageY, depth (4|8), u, v, picture, u16 clut
           (clut = CLUT index for 4-bit, 0xFFFF = master CLUT; picture 0 = resident, n = on-demand
           picture n-1 of <Stage>.pic, tpage/u/v as in slot 0)             (16 B)
  clut   : u16 vramX, vramY, u8 map[16] (master palette index per 4-bit value) (20 B)
  block  : u16 x, y, w, h (VRAM halfwords), u32 offset of w*h u16 at dataOffset + offset
Every frame is decoded back from the atlas and compared with its GIF (must be exact).

On-demand pictures (docs/28 phase 4, user decision 2026-09-24): a stage whose frames don't fit (the
Secrets gallery's full-screen pictures) streams its largest frame groups (merged rects) instead of
keeping them resident: each is a picture of <Stage>.pic, loaded by ps1/sprite_atlas into one of
two VRAM slots (same shape, columns SLOTS) when a draw first needs it, least recently used slot
replaced. The fewest pictures that make the rest fit are chosen, largest first.
<Data>/Sprites/Atlas/<Stage>.pic (little-endian):
  header : 'PIC1', u16 slotCount, pictureCount, blockCount, pad, u32 dataOffset       (16 B)
  slot   : u16 x, y, w, h (VRAM halfword rect), s16 dTpageX, dTpageY (vs slot 0)       (12 B)
  picture: u16 firstBlock, blockCount                                                  (4 B)
  block  : u16 x, y, w, h (slot 0 VRAM halfwords), u32 offset at dataOffset + offset   (12 B)
Each picture's pixel data starts on a sector.

Usage: build_atlas.py DATA_DIR MANIFEST_DIR [--stage NAME] [--cols N] [--report] [--suffix S] [--lang en|jp]
  --suffix S: write <Stage>S.atl (per-player atlases: '' = Sonic, '_t' = Tails; manifests per player)
  --cols N: test budget; --report: feasibility only (pack + self-check, no files written; stages
  that don't fit report their texel needs and how many 4-bit columns they are short)
"""
import os, re, struct, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from object_sheets import object_sheets  # noqa: E402
from PIL import Image

PAGE = 256
# Free VRAM columns (64 halfwords wide) per page row: X 320-575 and 832-1023 (tiles use
# 576-831, the framebuffers 0-319). Adjacent pairs host 8-bit pages.
COLUMNS = [5, 6, 7, 8, 13, 14, 15]
PAIRS = [(5, 6), (7, 8), (13, 14)]
FMV_RESERVED = {(5, 1), (6, 1), (7, 1), (8, 1)}  # (column, pageY) -> 15-bit video page
FMV_XY = (320, 256)
# On-demand picture slots: (8-bit pair, lone column, pageY); same shape, so a picture packed for slot 0
# moves to slot k by a whole-column offset. 320 texels wide (256 in the pair + 64 in the lone column).
SLOTS = [((13, 14), 15, 1), ((5, 6), 7, 1)]
# 4-bit CLUT slots (16 halfwords): row 240 right of the master CLUT, rows 241-255 and 496-503
# (rows 504-511 hold the runtime INK_BLEND CLUTs, Drawing.cpp PS1_BLEND_*)
CLUT_SLOTS = [(x, 240) for x in range(256, 320, 16)] + \
             [(x, y) for y in list(range(241, 256)) + list(range(496, 504)) for x in range(0, 320, 16)]


class AtlasError(Exception):
    pass


LANG_TAGS = {'en': 'EN', 'jp': 'JP', 'fr': 'FR', 'de': 'DE', 'es': 'ES', 'it': 'IT'}
LANG = 'en'  # --lang: the disc's language (docs/28 phase 4: one disc per language)


def _data_path(data, path):
    return os.path.join(data, path[5:] if path.lower().startswith('data/') else path)


def text_chars(data, texts):
    """Characters of the disc language's UTF-16 text files (upstream LoadTextFile); files tagged for
    another language (EN_Help/..._EN.txt) are skipped, untagged ones kept."""
    tags = set(LANG_TAGS.values())
    mine = LANG_TAGS[LANG]
    chars = set()
    for t in texts:
        found = {g for g in tags if '/%s_' % g in t or t.endswith('_%s.txt' % g)}
        if (found and mine not in found) or not t.lower().endswith('.txt'):
            continue
        f = _data_path(data, t)
        if os.path.exists(f):
            b = open(f, 'rb').read()
            if b[:2] == b'\xff\xfe':
                chars |= {c for c in b[2:].decode('utf-16-le', 'replace') if c not in '\r\n'}
    return {ord(c) for c in chars}


def font_rects(data, path, chars=None):
    """Glyph rects (x, y, w, h) of a font file (upstream LoadFontFile: 20-byte records {u32 id, u16 x, y,
    w-1, h-1, ...}); with `chars`, only the glyphs whose id is one of those code points (LoadTextFile
    maps each character to the font entry with that id)."""
    f = _data_path(data, path)
    if not os.path.exists(f):
        return []
    d, out = open(f, 'rb').read(), []
    for p in range(0, len(d) - 19, 20):
        cid = struct.unpack_from('<I', d, p)[0]
        if chars is not None and cid not in chars:
            continue
        x, y = d[p + 4] | d[p + 5] << 8, d[p + 6] | d[p + 7] << 8
        w, h = d[p + 8] + 1 + (d[p + 9] << 8), d[p + 10] + 1 + (d[p + 11] << 8)
        out.append((x, y, w, h))
    return out


def whole_texture(im):
    H, W = im.shape
    if H * W <= 256 * 256:
        return True
    return H <= 512 and W <= 512 and all(len(set(np.unique(im[y:y + PAGE, x:x + PAGE]).tolist()) - {0}) <= 15
                                         for y in range(0, H, PAGE) for x in range(0, W, PAGE))


def manifest_frames(data, path, images):
    """{sheet path: set of (x, y, w, h)} for one stage manifest (all its `stage` blocks)."""
    frames, sheets = {}, {}

    def add_frame(sid, x, y, w, h):
        while w > 0 and h > 0 and sid in sheets and size(sheets[sid]) is not None:
            H, W = size(sheets[sid])
            if y >= H:  # past the bottom: the next loaded sheet of the same width
                nxt = sheets.get(sid + 1)
                if nxt is None or size(nxt) is None or size(nxt)[1] != W:
                    break
                sid, y = sid + 1, y - H
                continue
            part = min(h, H - y)
            frames.setdefault(sheets[sid], set()).add((x, y, w, part))
            y, h = y + part, h - part

    def size(sheet):
        if sheet not in images:
            f = os.path.join(data, 'Sprites', sheet)
            images[sheet] = np.array(Image.open(f)) if os.path.exists(f) else None
        im = images[sheet]
        return None if im is None else im.shape  # (H, W)

    objsheets = {}  # this stage block: object name -> sheets its subs may load (tools/atlas/object_sheets)
    whole3d = set()  # sheets sampled by Draw3DScene faces (lower-case paths)
    fontglyphs = {}  # lower-case sheet path -> glyph rects of the fonts DrawText uses with it
    prescaled = set()  # font sheets whose glyphs come pre-scaled (<sheet>_ps1.gif)
    for line in open(path):
        t = line.split()
        if t[0] == 'stage':
            sheets = {}
            objsheets = {}
            for k, v in object_sheets(data, int(t[1]), int(t[2]), t[3]).items():
                if k == ('*', 'text'):  # pre-scaled glyphs (tools/font/prescale_font.py): the whole sheet
                    for sheet in v['sheets']:
                        ps = os.path.splitext(sheet)[0] + '_ps1.gif'
                        if size(ps) is not None:
                            H, W = size(ps)
                            frames.setdefault(ps, set()).add((0, 0, W, H))
                            prescaled.add(sheet.lower())
                elif isinstance(k, tuple) and k[1] == 'font':  # DrawText: the fonts' glyphs on the object's sheets
                    chars = text_chars(data, v[2])      # only those the disc language's texts use
                    for sheet in v[0]:
                        fontglyphs.setdefault(sheet.lower(), set()).update(r for f in v[1] for r in font_rects(data, f, chars))
                elif isinstance(k, tuple):  # (name, '3d'): Draw3DScene faces sample these sheets whole
                    for p in v:
                        whole3d.add(p.lower())
                else:
                    objsheets[k.replace(' ', '').lower()] = v
        elif t[0] == 'sheet':
            sheets[int(t[1])] = t[2]
            if t[2].lower() not in prescaled:  # pre-scaled glyphs replace the original ones
                for r in fontglyphs.get(t[2].lower(), ()):
                    add_frame(int(t[1]), *r)
            # A 3D object's texture sheet: all of it when it is texture-sized (<= 256x256, e.g. the title's
            # clouds) or a <= 512x512 texture cheap in VRAM (every 256x256 quarter 4-bit: SS1's animated
            # background SSBG1). Big sheets (the menu's) rely on their frames; faces outside the atlas are
            # counted at runtime (g_ps1FaceTexMiss).
            if t[2].lower() in whole3d and size(t[2]) is not None and whole_texture(images[t[2]]):
                H, W = size(t[2])
                frames.setdefault(t[2], set()).add((0, 0, W, H))
        elif t[0] == 'frame':
            sid, x, y, w, h = map(int, t[1:6])
            sids = [sid]
            if t[6] == 'obj':  # also every other sheet of this stage the object may switch to
                name = ''.join(t[7:]).lower()  # engine typeNames have no spaces
                loaded = {p.lower(): i for i, p in sheets.items()}
                sids += [loaded[p.lower()] for p in objsheets.get(name, ()) if p.lower() in loaded and loaded[p.lower()] != sid]
            for sid in sids:
                add_frame(sid, x, y, w, h)
    return frames



def merge(rects):
    """Merge overlapping rects into bounding boxes until none overlap."""
    rects = [list(r) for r in rects]
    changed = True
    while changed:
        changed = False
        out = []
        for r in rects:
            for o in out:
                if r[0] < o[0] + o[2] and o[0] < r[0] + r[2] and r[1] < o[1] + o[3] and o[1] < r[1] + r[3]:
                    x0, y0 = min(r[0], o[0]), min(r[1], o[1])
                    x1, y1 = max(r[0] + r[2], o[0] + o[2]), max(r[1] + r[3], o[1] + o[3])
                    o[:] = [x0, y0, x1 - x0, y1 - y0]
                    changed = True
                    break
            else:
                out.append(r)
        rects = out
    return [tuple(r) for r in rects]


def split(r):
    x, y, w, h = r
    return [(x + i, y + j, min(PAGE, w - i), min(PAGE, h - j)) for j in range(0, h, PAGE) for i in range(0, w, PAGE)]


class Bin:
    """One texture page (256 x 256 texels): skyline packer."""
    def __init__(self, tpx, tpy, depth, width, cols):
        self.tpx, self.tpy, self.depth, self.width, self.cols = tpx, tpy, depth, width, cols
        self.sky = [0] * width

    def place(self, w, h):
        best = None
        for u in range(0, self.width - w + 1):
            v = max(self.sky[u:u + w])
            if v + h <= PAGE and (best is None or v < best[1] or (v == best[1] and u < best[0])):
                best = (u, v)
        if best:
            u, v = best
            for i in range(u, u + w):
                self.sky[i] = v + h
        return best


def last_tile(data, stage):
    """Highest non-empty tile of the stage's 16x16Tiles.gif (-1: none)."""
    f = os.path.join(data, 'Stages', stage, '16x16Tiles.gif')
    if not os.path.exists(f):
        return 1023
    a = np.array(Image.open(f))
    used = [t for t in range(a.shape[0] // 16) if a[t * 16:t * 16 + 16].any()]
    return max(used) if used else -1


def build_stage(data, manifest, name, cols_limit=None, virtual=0, stream=0):
    """virtual > 0 (feasibility): that many extra 64-halfword columns beyond real VRAM, per page row.
    stream > 0: the `stream` largest merged rects become on-demand pictures (<Stage>.pic)."""
    images = {}
    frames = manifest_frames(data, manifest, images)
    video = False
    images = {k: v for k, v in images.items() if k in frames}
    clusters = []  # dict(sheet, rect, depth, colors, clut, tpx, tpy, u, v, pic)
    merged = []    # (area, sheet, rect) of every merged rect: on-demand picture candidates
    for sheet in sorted(frames):
        im = images[sheet]
        H, W = im.shape
        rects = []
        for (x, y, w, h) in frames[sheet]:
            x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
            if x1 > x0 and y1 > y0:
                rects.append((x0, y0, x1 - x0, y1 - y0))
        for r in merge(rects):
            merged.append((r[2] * r[3], sheet, r))
            for piece in split(r):
                x, y, w, h = piece
                cols = set(np.unique(im[y:y + h, x:x + w]).tolist()) - {0}
                clusters.append(dict(sheet=sheet, rect=piece, colors=cols, depth=4 if len(cols) <= 15 else 8,
                                     group=(sheet, r), pic=None))
    pictures = [(sh, r) for _, sh, r in sorted(merged, key=lambda m: (-m[0], m[1], m[2]))[:stream]]
    for c in clusters:
        if c['group'] in pictures:
            c['pic'] = pictures.index(c['group'])
    if pictures and video:
        raise AtlasError('%s: on-demand pictures and the FMV page both want columns 5-7' % name)

    # CLUT groups for 4-bit clusters (greedy: biggest colour sets first, least growth).
    groups = []
    for c in sorted((c for c in clusters if c['depth'] == 4), key=lambda c: -len(c['colors'])):
        best = None
        for gi, g in enumerate(groups):
            u = g | c['colors']
            if len(u) <= 15 and (best is None or len(u) - len(g) < best[1]):
                best = (gi, len(u) - len(g))
        if best:
            groups[best[0]] |= c['colors']
            c['clut'] = best[0]
        else:
            groups.append(set(c['colors']))
            c['clut'] = len(groups) - 1
    clut_slots = CLUT_SLOTS + [(0, 1000 + i) for i in range(virtual * 64)]
    if len(groups) > len(clut_slots):
        raise AtlasError('%s: %d CLUTs > %d slots' % (name, len(groups), len(CLUT_SLOTS)))
    clut_maps = [[0] + sorted(g) + [0] * (15 - len(g)) for g in groups]

    # Columns available (column, pageY); FMV page reserved when the stage plays a video; the picture
    # slots when the stage streams pictures.
    vcols = [100 + i for i in range(virtual)]
    pairs = PAIRS + [(vcols[i], vcols[i + 1]) for i in range(0, len(vcols) - 1, 2)]
    free = [(c, py) for py in (0, 1) for c in COLUMNS + vcols]
    # Special stages (docs/28 phase 7): a tile page their tile set leaves empty joins the atlas, last (page 3
    # is the far floor's): SS1's animated 3D background needs 4 more columns than the sprite area has.
    if re.match(r'SS\d+$', name):
        if last_tile(data, name) < 512:
            free += [(9, 1), (10, 1)]
            pairs = pairs + [(9, 10)]
    if video:
        free = [cp for cp in free if cp not in FMV_RESERVED]
    if pictures:
        slot_cols = {(c, py) for (a, b), lone, py in SLOTS for c in (a, b, lone)}
        free = [cp for cp in free if cp not in slot_cols]
    if cols_limit is not None:
        free = free[:cols_limit]

    def pack(todo_clusters, free, pairs, what):
        bins = []

        def new_bin(depth):
            if depth == 8:
                for a, b in pairs:
                    for py in (0, 1):
                        if (a, py) in free and (b, py) in free:
                            free.remove((a, py)); free.remove((b, py))
                            return Bin(a, py, 8, PAGE, [(a, py), (b, py)])
                for cp in list(free):  # a lone column: an 8-bit page with u < 128
                    free.remove(cp)
                    return Bin(cp[0], cp[1], 8, 128, [cp])
                return None
            if free:
                cp = free.pop(0)
                return Bin(cp[0], cp[1], 4, PAGE, [cp])
            return None

        for depth in (8, 4):
            todo = sorted((c for c in todo_clusters if c['depth'] == depth), key=lambda c: (-c['rect'][3], -c['rect'][2]))
            for c in todo:
                w, h = c['rect'][2], c['rect'][3]
                spot = None
                for b in bins:
                    if b.depth == depth and w <= b.width:
                        spot = b.place(w, h)
                        if spot:
                            break
                if not spot:
                    b = new_bin(depth)
                    while b is not None and w > b.width:  # a half-width 8-bit page can't take it
                        b = new_bin(depth)
                    if b is None:
                        raise AtlasError('%s: out of VRAM placing %s %s (%d-bit)%s' % (name, c['sheet'], c['rect'], depth, what))
                    bins.append(b)
                    spot = b.place(w, h)
                c['tpx'], c['tpy'], (c['u'], c['v']) = b.tpx, b.tpy, spot
        return bins

    bins = pack([c for c in clusters if c['pic'] is None], free, pairs, '')
    pic_bins = []  # per picture: its bins in slot 0
    if pictures:
        (a, b), lone, py = SLOTS[0]
        for i, (sh, r) in enumerate(pictures):
            pic_bins.append(pack([c for c in clusters if c['pic'] == i], [(a, py), (b, py), (lone, py)], [(a, b)],
                                 ' (picture %d %s %s does not fit a slot)' % (i, sh, r)))

    # Render the VRAM image of the sprite columns (resident clusters) and one per picture (slot 0).
    vram_w = 1024 + 64 * (100 + virtual) if virtual else 1024
    vram = np.zeros((512, vram_w), np.uint16)
    pic_vram = [np.zeros((512, vram_w), np.uint16) for _ in pictures]
    used_lines = {}
    pic_lines = [{} for _ in pictures]
    for c in clusters:
        img, lines_of = (vram, used_lines) if c['pic'] is None else (pic_vram[c['pic']], pic_lines[c['pic']])
        x, y, w, h = c['rect']
        idx = images[c['sheet']][y:y + h, x:x + w].astype(np.uint16)
        X0, Y0 = c['tpx'] * 64, c['tpy'] * 256 + c['v']
        if c['depth'] == 8:
            if c['u'] % 2 or w % 2:  # keep whole halfwords: pad with transparent texels
                idx = np.pad(idx, ((0, 0), (c['u'] % 2, (c['u'] + w) % 2)))
            hx = X0 + c['u'] // 2
            words = idx[:, 0::2] | (idx[:, 1::2] << 8)
        else:
            lut = {v: i for i, v in enumerate(clut_maps[c['clut']])}
            lut[0] = 0
            q = np.vectorize(lambda v: lut[v])(idx).astype(np.uint16) if idx.size else idx
            lead, trail = c['u'] % 4, (-(c['u'] + w)) % 4
            q = np.pad(q, ((0, 0), (lead, trail)))
            hx = X0 + c['u'] // 4
            words = q[:, 0::4] | (q[:, 1::4] << 4) | (q[:, 2::4] << 8) | (q[:, 3::4] << 12)
        region = img[Y0:Y0 + h, hx:hx + words.shape[1]]
        region |= words  # padding texels are 0, neighbours never overlap real texels
        key = (c['tpx'], c['tpy'])
        lines_of[key] = max(lines_of.get(key, 0), c['v'] + h)

    def bin_blocks(bins, lines_of):
        out = []
        for b in bins:
            lines = lines_of.get((b.tpx, b.tpy), 0)
            if lines:
                out.append((b.tpx * 64, b.tpy * 256, 64 * len(b.cols), lines))
        return out
    blocks = bin_blocks(bins, used_lines)
    pic_blocks = [bin_blocks(pb, pl) for pb, pl in zip(pic_bins, pic_lines)]

    # Self-check: decode every cluster from the VRAM image + CLUT maps into a reconstructed
    # sheet, then every frame region must equal the GIF (and be fully covered).
    recon = {sh: np.full(im.shape, -1, np.int32) for sh, im in images.items()}
    for c in clusters:
        vram_c = vram if c['pic'] is None else pic_vram[c['pic']]
        x, y, w, h = c['rect']
        X0, Y0 = c['tpx'] * 64, c['tpy'] * 256 + c['v']
        if c['depth'] == 8:
            words = vram_c[Y0:Y0 + h, X0 + c['u'] // 2:X0 + (c['u'] + w + 1) // 2 + 1].astype(np.int32)
            tex = np.stack([words & 0xFF, words >> 8], -1).reshape(h, -1)[:, c['u'] % 2:c['u'] % 2 + w]
        else:
            words = vram_c[Y0:Y0 + h, X0 + c['u'] // 4:X0 + (c['u'] + w + 3) // 4 + 1].astype(np.int32)
            nib = np.stack([(words >> s_) & 0xF for s_ in (0, 4, 8, 12)], -1).reshape(h, -1)[:, c['u'] % 4:c['u'] % 4 + w]
            tex = np.array(clut_maps[c['clut']], np.int32)[nib]
        recon[c['sheet']][y:y + h, x:x + w] = tex
    checked = 0
    for sheet, rects in frames.items():
        im, rc_ = images[sheet], recon[sheet]
        H, W = im.shape
        for (x, y, w, h) in rects:
            x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
            if x1 <= x0 or y1 <= y0:
                continue
            a, b = rc_[y0:y1, x0:x1], im[y0:y1, x0:x1].astype(np.int32)
            if (a < 0).any():
                raise AtlasError('%s: %s frame %s not fully in the atlas' % (name, sheet, (x, y, w, h)))
            if (a != b).any():
                yy, xx = np.argwhere(a != b)[0]
                raise AtlasError('%s: %s frame %s texel (%d,%d) atlas %d != gif %d' % (
                    name, sheet, (x, y, w, h), x0 + xx, y0 + yy, a[yy, xx], b[yy, xx]))
            checked += a.size

    # Write the file.
    sheets = sorted(frames)
    order = sorted(clusters, key=lambda c: (sheets.index(c['sheet']), c['rect'][1], c['rect'][0]))
    out = bytearray()
    sheet_tab, cl_tab = bytearray(), bytearray()
    for s in sheets:
        mine = [i for i, c in enumerate(order) if c['sheet'] == s]
        H, W = images[s].shape
        sheet_tab += struct.pack('<48sHHHH', s.lower().encode()[:47], mine[0], len(mine), W, H)
    for c in order:
        x, y, w, h = c['rect']
        cl_tab += struct.pack('<HHHHBBBBBBH', x, y, w, h, c['tpx'], c['tpy'], c['depth'], c['u'], c['v'],
                              0 if c['pic'] is None else c['pic'] + 1,
                              c['clut'] if c['depth'] == 4 else 0xFFFF)
    clut_tab = bytearray()
    for i, m in enumerate(clut_maps):
        clut_tab += struct.pack('<HH', *clut_slots[i]) + bytes(m)
    blk_tab, pixels = bytearray(), bytearray()
    for (x, y, w, h) in blocks:
        blk_tab += struct.pack('<HHHHI', x, y, w, h, len(pixels))
        pixels += vram[y:y + h, x:x + w].astype('<u2').tobytes()
    head_len = 20 + len(sheet_tab) + len(cl_tab) + len(clut_tab) + len(blk_tab)
    data_off = (head_len + 2047) // 2048 * 2048  # pixel data starts on a sector
    fx, fy = FMV_XY if video else (0xFFFF, 0xFFFF)
    out += struct.pack('<4sHHHHHHI', b'ATL1', len(sheets), len(order), len(clut_maps), len(blocks), fx, fy, data_off)
    out += sheet_tab + cl_tab + clut_tab + blk_tab
    out += bytes(data_off - len(out)) + pixels

    pic = None
    if pictures:
        slot_tab = bytearray()
        (a0, _), _, py0 = SLOTS[0]
        for (a, b), lone, py in SLOTS:
            x0 = min(a, lone) * 64
            slot_tab += struct.pack('<HHHHhh', x0, py * 256, (max(b, lone) + 1) * 64 - x0, 256, a - a0, py - py0)
        pic_tab, pblk_tab, ppix = bytearray(), bytearray(), bytearray()
        nblk = 0
        for i, pb in enumerate(pic_blocks):
            pic_tab += struct.pack('<HH', nblk, len(pb))
            ppix += bytes((-len(ppix)) % 2048)  # each picture on a sector
            for (x, y, w, h) in pb:
                pblk_tab += struct.pack('<HHHHI', x, y, w, h, len(ppix))
                ppix += pic_vram[i][y:y + h, x:x + w].astype('<u2').tobytes()
                nblk += 1
        head = 16 + len(slot_tab) + len(pic_tab) + len(pblk_tab)
        poff = (head + 2047) // 2048 * 2048
        pic = bytearray(struct.pack('<4sHHHHI', b'PIC1', len(SLOTS), len(pictures), nblk, 0, poff))
        pic += slot_tab + pic_tab + pblk_tab
        pic += bytes(poff - len(pic)) + ppix
        pic = bytes(pic)

    n4 = sum(c['rect'][2] * c['rect'][3] for c in clusters if c['depth'] == 4)
    n8 = sum(c['rect'][2] * c['rect'][3] for c in clusters if c['depth'] == 8)
    report = ('%-7s sheets %2d clusters %3d (4-bit %3d / 8-bit %3d) texels 4-bit %6d 8-bit %6d | pages 8-bit %d 4-bit %d '
              '| VRAM %6d hw | CLUTs %2d | FMV %s | file %6d B | self-check %d texels OK' % (
                  name, len(sheets), len(order), sum(c['depth'] == 4 for c in clusters),
                  sum(c['depth'] == 8 for c in clusters), n4, n8,
                  sum(b.depth == 8 for b in bins), sum(b.depth == 4 for b in bins),
                  sum(w * h for (_, _, w, h) in blocks), len(clut_maps), 'reserved' if video else '-', len(out), checked))
    if pictures:
        report += ' | on-demand pictures %d (%s), %d slots, .pic %d B' % (
            len(pictures), ', '.join('%s %dx%d' % (os.path.basename(sh), r[2], r[3]) for sh, r in pictures), len(SLOTS), len(pic))
    over = sum(1 for b in bins for (c, _) in b.cols if c >= 100)
    over_cluts = max(0, len(clut_maps) - len(CLUT_SLOTS))
    return bytes(out), report, over, over_cluts, pic


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        print(__doc__)
        return 2
    data, mdir = args[0], args[1]
    only = args[args.index('--stage') + 1] if '--stage' in args else None
    cols = int(args[args.index('--cols') + 1]) if '--cols' in args else None
    feas = '--report' in args
    suffix = args[args.index('--suffix') + 1] if '--suffix' in args else ''
    global LANG
    LANG = args[args.index('--lang') + 1] if '--lang' in args else 'en'
    outdir = os.path.join(data, 'Sprites', 'Atlas')
    if not feas:
        os.makedirs(outdir, exist_ok=True)
    rc, short = 0, []
    for f in sorted(os.listdir(mdir)):
        if not f.endswith('.txt'):
            continue
        name = f[:-4]
        if only and name != only:
            continue
        pic = None
        try:
            blob, report, _, _, pic = build_stage(data, os.path.join(mdir, f), name, cols)
        except AtlasError as e:
            # Doesn't fit: stream the fewest largest frame groups as on-demand pictures.
            err, blob = e, None
            for k in range(1, 17):
                try:
                    blob, report, _, _, pic = build_stage(data, os.path.join(mdir, f), name, cols, stream=k)
                    break
                except AtlasError as e2:
                    err = e2
            if blob is None and not feas:
                print('ERROR', e, '| with on-demand pictures:', err)
                rc = 1
                continue
            if blob is None:
                blob, report, over, over_cluts, _ = build_stage(data, os.path.join(mdir, f), name, None, virtual=32)
                short.append(name)
                report += ' | DOES NOT FIT: %d page-columns over (64 hw x 256), %d CLUTs over' % (over, over_cluts)
        if not feas and cols is None:
            open(os.path.join(outdir, name + suffix + '.atl'), 'wb').write(blob)
            ppath = os.path.join(outdir, name + suffix + '.pic')
            if pic:
                open(ppath, 'wb').write(pic)
            elif os.path.exists(ppath):
                os.remove(ppath)
        print(report)
    if feas:
        print('stages that do not fit the VRAM sprite area: %d %s' % (len(short), ' '.join(short)))
    return rc


if __name__ == '__main__':
    sys.exit(main())
