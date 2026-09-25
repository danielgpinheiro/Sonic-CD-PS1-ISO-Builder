#!/usr/bin/python3
"""Which sprite sheets each object of a stage may draw with (phase 4, docs/28).

A script frame is a rect, drawn with whatever sheet the object holds at draw time: objects call
LoadSpriteSheet in their main / draw subs too (the menu heading switches back to MenuGfx1), so the
sheet an object ends its startup with (what rsdkmanifest records) is not the only one. This walks
every object's subs in the stage's bytecode (GS000 + the list position's file, as LoadBytecode loads
them; CallFunction followed into script functions) and collects LoadSpriteSheet's string arguments.

object_sheets(data, list, pos, folder) -> {object name: set of sheet paths under Data/Sprites/}
Objects that call DrawText are reported under (name, 'font') -> (their sheets, the font paths and
the text files any object of the stage loads): DrawText draws the glyph rects from the caller's sheet. Objects that call Draw3DScene are also
reported under the key (name, '3d'): their faces sample the
sheet by vertex UVs set at runtime (no sprite frames), so the atlas must hold those sheets whole.
"""
import os, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
import bytecode_scan as bs  # noqa: E402

LIST_PREFIX = 'PRBS'  # engine stage lists 0-3 -> ByteCode file prefix (Script.cpp listIDs)
_TABLES = None


def _tables():
    global _TABLES
    if _TABLES is None:
        _TABLES = bs.tables()
    return _TABLES


def _read_str(r):
    n = r.d[r.p]
    r.p += 1
    s = r.d[r.p:r.p + n].decode('latin1')
    r.p += n
    return s


class _R:
    def __init__(self, path):
        self.d, self.p = open(path, 'rb').read(), 0


def _global_names(data):
    r = _R(os.path.join(data, 'Game', 'GameConfig.bin'))
    _read_str(r), _read_str(r), _read_str(r)
    n = r.d[r.p]
    r.p += 1
    return [_read_str(r) for _ in range(n)]


def _stage_config(data, folder):
    r = _R(os.path.join(data, 'Stages', folder, 'StageConfig.bin'))
    globals_ = r.d[r.p]
    r.p += 1 + 96
    n = r.d[r.p]
    r.p += 1
    return bool(globals_), [_read_str(r) for _ in range(n)]


def _functions(path):
    """Script function code offsets of a bytecode file (as LoadBytecode reads them)."""
    d = open(path, 'rb').read()
    _, p = bs.blocks(d, 0)
    _, p = bs.blocks(d, p)
    count, = struct.unpack_from('<H', d, p)
    p += 2 + 32 * count
    fn, = struct.unpack_from('<H', d, p)
    p += 2
    return list(struct.unpack_from('<%di' % fn, d, p))


def _walk(code, start, funcs, fptrs, seen, flags=None):
    """LoadSpriteSheet strings reachable from `start` (until End), following CallFunction consts.
    flags (a set) gets '3d' if Draw3DScene is reachable."""
    names, vars_ = _tables()
    out = set()
    p = start
    while 0 <= p < len(code):
        op = code[p]
        p += 1
        if op >= len(names):
            break
        name, size = names[op]
        ops = []
        for _ in range(size):
            t = code[p]
            p += 1
            if t == 1:
                arr = code[p]
                p += 1
                if arr in (1, 2, 3):
                    p += 2
                p += 1
                ops.append(None)
            elif t == 2:
                ops.append(code[p])
                p += 1
            elif t == 3:
                n = code[p]
                ops.append(''.join(chr((code[p + 1 + c // 4] >> (24 - 8 * (c % 4))) & 0xFF) for c in range(n)))
                p += n // 4 + 2
        if name == 'LoadSpriteSheet' and isinstance(ops[0], str):
            out.add(ops[0])
        elif name == 'Draw3DScene' and flags is not None:
            flags.add('3d')
        elif name == 'LoadTextFont' and flags is not None and isinstance(ops[0], str):
            flags.add(('font', ops[0]))
        elif name == 'DrawText' and flags is not None:
            flags.add('text')
            if isinstance(ops[3], int):
                flags.add(('scale', ops[3]))
        elif name == 'LoadPalette' and flags is not None and isinstance(ops[0], str) and isinstance(ops[1], int):
            flags.add(('palette', ops[0], ops[1]))
        elif name == 'LoadTextFile' and flags is not None and isinstance(ops[1], str):
            flags.add(('textfile', ops[1]))
        elif name == 'CallFunction' and isinstance(ops[0], int) and 0 <= ops[0] < len(fptrs) and ops[0] not in seen:
            seen.add(ops[0])
            out |= _walk(code, fptrs[ops[0]], funcs, fptrs, seen, flags)
        elif name == 'End':
            break
    return out


def object_sheets(data, lst, pos, folder):
    bc = os.path.join(data, 'Scripts', 'ByteCode')
    path = os.path.join(bc, '%sS%03d.bin' % (LIST_PREFIX[lst], pos))
    gpath = os.path.join(bc, 'GS000.bin')
    if not os.path.exists(path):
        return {}
    load_globals, stage_names = _stage_config(data, folder)
    # Offsets are absolute scriptCode positions: a stage that loads the globals has its code after
    # GS000's, one that doesn't starts at 0 (LoadBytecode never rebases).
    code = (bs.ints(gpath) if load_globals else []) + bs.ints(path)
    fptrs = _functions(path)      # the stage file's table holds the functions (global ones included)
    result = {}
    objs = []
    if load_globals:
        objs += list(zip(_global_names(data), bs.subs(gpath)))
    objs += list(zip(stage_names, bs.subs(path)))
    fonts, texts, texters, scales, palettes = set(), set(), [], set(), set()
    for name, subs in objs:
        sheets, flags = set(), set()
        for off in subs:
            if 0 <= off < len(code) and off != 0x3FFFF:
                sheets |= _walk(code, off, None, fptrs, set(), flags)
        if sheets:
            result.setdefault(name, set()).update(sheets)
            if '3d' in flags:
                result.setdefault((name, '3d'), set()).update(sheets)
        fonts |= {f[1] for f in flags if isinstance(f, tuple) and f[0] == 'font'}
        texts |= {f[1] for f in flags if isinstance(f, tuple) and f[0] == 'textfile'}
        scales |= {f[1] for f in flags if isinstance(f, tuple) and f[0] == 'scale'}
        palettes |= {f[1:] for f in flags if isinstance(f, tuple) and f[0] == 'palette'}
        if 'text' in flags:
            texters.append((name, sheets))
    # DrawText draws glyphs of the fonts loaded in the stage (by any object) from the calling object's
    # sheet (ps1 DrawBitmapText, textMenuSurfaceNo = its sheet).
    for name, sheets in texters:
        if fonts and sheets:
            result[(name, 'font')] = (sheets, fonts, texts)
    if fonts and texters:  # stage-wide text drawing facts (tools/font/prescale_font.py)
        result[('*', 'text')] = dict(fonts=fonts, texts=texts, scales=scales, palettes=palettes,
                                     sheets=set().union(*(s for _, s in texters)))
    return result


if __name__ == '__main__':
    d, lst, pos, folder = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
    for k, v in sorted(object_sheets(d, lst, pos, folder).items(), key=str):
        print('%-24s %s' % (k, v))
