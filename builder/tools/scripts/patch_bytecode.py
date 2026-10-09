#!/usr/bin/python3
"""PS1 edits to Sonic CD's script bytecode, applied to the disc tree at build time (docs/28, user test
fixes 2026-09-25). The engine runs the scripts unchanged; only their data changes here.

Help & Options (user decision 2026-09-25: no HOW TO PLAY, no CONTROLS). The PC build's HELP & OPTIONS
button (Menu Button, PS001.bin) opens `Options Menu C`: HOW TO PLAY / CONTROLS / SETTINGS / STAFF
CREDITS, whose entries call native PC dialogs through engine callbacks. The stage also carries the
console version, `Options Menu`: INSTRUCTIONS / SETTINGS / STAFF CREDITS / ABOUT, all in-script (its
SETTINGS window sets music / SFX volume and the spin dash style; INSTRUCTIONS loads the Help stage). On
PS1 the button opens `Options Menu`, without INSTRUCTIONS:
  - Menu Button: ResetObjectEntity 62, <Options Menu C> -> <Options Menu>;
  - Options Menu main: cursor wraps over 3 entries (the constants 3 -> 2); the switches on the entry
    (OBJECTVALUE1: music stop, the entry's action, the stage it loads) see entry k + 1 of the original;
  - its entry labels (sprite frames 10-13, highlighted 14-17) move up one, so entry k shows label k + 1;
  - draw: the 4th entry slot is moved off screen (its `Add OBJECTYPOS, 40` -> -1000).
Special stages (docs/28 special-stage speed): Special Setup's draw sub, a bubble sort of draw list 3 in
script, becomes one PS1SortDrawList instruction (a PS1 engine opcode running the same loop natively); SS5's
BGEffects deformation ramp loop becomes PS1DeformRamp; R11A's 3DRamp parallax ramp loop becomes PS1ParallaxRamp (only
its WLower opcode changes: speed pass 2).
Every edit is found by its instruction pattern and checked (count and operands); anything unexpected
stops the build. Already patched files are recognised and left alone.

Usage: patch_bytecode.py DATA_DIR
"""
import os, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
import bytecode_scan as bs  # noqa: E402
import bytecode_dis as bd  # noqa: E402


def rstr(b, i):
    n = b[i]
    return b[i + 1:i + 1 + n].decode('latin1'), i + 1 + n


def object_index(data, stage, name):
    b = open(os.path.join(data, 'Stages', stage, 'StageConfig.bin'), 'rb').read()
    i = 1 + 96
    n = b[i]
    i += 1
    names = []
    for _ in range(n):
        s, i = rstr(b, i)
        names.append(s)
    return names.index(name), names


def encode(values):
    """RSDKv3 bytecode block encoding (LoadBytecode): header h, n = h & 0x7F values, 4 bytes each if
    h >= 0x80 else 1 byte each (0..255)."""
    out = bytearray(struct.pack('<I', len(values)))
    i = 0
    while i < len(values):
        small = 0 <= values[i] <= 255
        j = i
        while j < len(values) and j - i < 127 and (0 <= values[j] <= 255) == small:
            j += 1
        out.append(j - i if small else 0x80 | (j - i))
        for v in values[i:j]:
            out += bytes([v]) if small else struct.pack('<i', v)
        i = j
    return bytes(out)


def instructions(code, start, names, vars_):
    """(position, name, operands) from `start` to the sub's End; operand = (kind, value, position of
    the value): kind 'var' (value = (name, array flag)), 'int' or 'str'."""
    out, p = [], start
    while p < len(code):
        at, op = p, code[p]
        p += 1
        name, size = names[op]
        ops = []
        for _ in range(size):
            t = code[p]
            p += 1
            if t == 1:
                arr = code[p]
                p += 1
                idx = None
                if arr in (1, 2, 3):
                    idx = (code[p], code[p + 1])  # (1 = array position register, else constant), value
                    p += 2
                ops.append(('var', (vars_[code[p]].replace('VAR_', ''), arr) if idx is None else
                            (vars_[code[p]].replace('VAR_', ''), arr, idx), p))
                p += 1
            elif t == 2:
                ops.append(('int', code[p], p))
                p += 1
            else:
                p += code[p] // 4 + 2
                ops.append(('str', None, p))
        out.append((at, name, ops))
        if name in ('End', 'EndFunction'):
            break
    return out


def one(items, what):
    if len(items) != 1:
        sys.exit('ERROR patch_bytecode: expected one %s, found %d' % (what, len(items)))
    return items[0]


def patch_options(data):
    names, vars_ = bs.tables()
    path = os.path.join(data, 'Scripts', 'ByteCode', 'PS001.bin')  # presentation stage 1 = Menu
    raw = open(path, 'rb').read()
    code, p = bs.blocks(raw, 0)
    jt, p2 = bs.blocks(raw, p)
    tail = raw[p2:]
    button, objs = object_index(data, 'Menu', 'Menu Button')
    opts, _ = object_index(data, 'Menu', 'Options Menu')
    optsc, _ = object_index(data, 'Menu', 'Options Menu C')
    type_opts, type_optsc = opts + 1, optsc + 1  # object types: 0 = none, then the stage's objects (no globals)
    subs = bs.subs(path)
    _, jptrs = bd.jump_tables(path)

    # Menu Button: HELP & OPTIONS opens Options Menu.
    bmain = instructions(code, subs[button][0], names, vars_)
    reset = [i for i in bmain if i[1] == 'ResetObjectEntity' and [o[1] for o in i[2][:2]] in ([62, type_optsc], [62, type_opts])]
    at, _, ops = one(reset, 'ResetObjectEntity 62, <options>')
    if ops[1][1] == type_opts:
        return 'already patched'
    code[ops[1][2]] = type_opts

    main = instructions(code, subs[opts][0], names, vars_)
    v1 = ('OBJECTVALUE1', 0)
    # Cursor wrap: IfLower .., VALUE1, 0 / Equal VALUE1, 3  and  IfGreater .., VALUE1, 3 / Equal VALUE1, 0.
    low = [main[k + 1] for k in range(len(main) - 1) if main[k][1] == 'IfLower' and main[k][2][1][1] == v1 and main[k][2][2][1] == 0
           and main[k + 1][1] == 'Equal' and main[k + 1][2][0][1] == v1]
    _, _, ops = one(low, 'cursor wrap up')
    assert ops[1][1] == 3, ops
    code[ops[1][2]] = 2
    high = [main[k] for k in range(len(main) - 1) if main[k][1] == 'IfGreater' and main[k][2][1][1] == v1
            and main[k + 1][1] == 'Equal' and main[k + 1][2][0][1] == v1 and main[k + 1][2][1][1] == 0]
    _, _, ops = one(high, 'cursor wrap down')
    assert ops[2][1] == 3, ops
    code[ops[2][2]] = 2
    # Switches on the entry: entry k does what entry k + 1 did.
    sw = [i for i in main if i[1] == 'switch' and i[2][1][0] == 'var' and i[2][1][1] == v1]
    if len(sw) != 3:
        sys.exit('ERROR patch_bytecode: expected 3 switches on OBJECTVALUE1, found %d' % len(sw))
    for _, _, ops in sw:
        j = jptrs[opts][0] + ops[0][1]
        lo, hi, dflt = jt[j], jt[j + 1], jt[j + 2]
        assert (lo, hi) == (0, 3), (lo, hi)
        jt[j + 4:j + 8] = jt[j + 5:j + 8] + [dflt]
    # Labels: frames 10-13 and 14-17 (the startup's SpriteFrame list) move up one.
    frames = [i for i in instructions(code, subs[opts][3], names, vars_) if i[1] == 'SpriteFrame']
    assert len(frames) >= 18, len(frames)
    for base in (10, 14):
        vals = [[o[1] for o in frames[base + k][2]] for k in range(4)]
        for k in range(4):
            for o, v in zip(frames[base + k][2], vals[min(k + 1, 3)]):
                code[o[2]] = v
    # Draw: the 4th slot off screen.
    draw = instructions(code, subs[opts][2], names, vars_)
    adds = [i for i in draw if i[1] == 'Add' and i[2][0][1] == ('OBJECTYPOS', 0) and i[2][1][1] == 40]
    calls = [k for k, i in enumerate(draw) if i[1] == 'CallFunction']
    if len(adds) < 3 or len(calls) < 4:
        sys.exit('ERROR patch_bytecode: Options Menu draw has %d slot steps, %d entry draws' % (len(adds), len(calls)))
    code[adds[2][2][1][2]] = -1000

    open(path, 'wb').write(encode(code) + encode(jt) + tail)
    back = open(path, 'rb').read()
    c2, q = bs.blocks(back, 0)
    j2, q2 = bs.blocks(back, q)
    assert c2 == code and j2 == jt and back[q2:] == tail
    return 'HELP & OPTIONS -> %s (type %d, was %d): SETTINGS / STAFF CREDITS / ABOUT' % (objs[opts], type_opts, type_optsc)


# Special Setup's draw sub in every special stage: sort draw list 3 by OBJECTVALUE5, descending (a bubble
# sort in script, ~45 hblanks a frame) -> PS1SortDrawList 3, 5 (RSDKv3/Script.cpp: the same loop natively,
# down to the temp values and array positions it leaves), then End.
SS_SORT = [
    ('Equal', [('var', ('TEMPVALUE0', 0)), ('int', 0)]),
    ('Equal', [('var', ('TEMPVALUE1', 0)), ('var', ('SCREENDRAWLISTSIZE', 1, (0, 3)))]),
    ('WLower', [('int', 0), ('var', ('TEMPVALUE0', 0)), ('var', ('TEMPVALUE1', 0))]),
    ('Equal', [('var', ('TEMPVALUE2', 0)), ('var', ('TEMPVALUE1', 0))]),
    ('Dec', [('var', ('TEMPVALUE2', 0))]),
    ('WGreater', [('int', 2), ('var', ('TEMPVALUE2', 0)), ('var', ('TEMPVALUE0', 0))]),
    ('Equal', [('var', ('TEMPVALUE3', 0)), ('var', ('TEMPVALUE2', 0))]),
    ('Dec', [('var', ('TEMPVALUE2', 0))]),
    ('GetDrawListEntityRef', [('var', ('ARRAYPOS0', 0)), ('int', 3), ('var', ('TEMPVALUE3', 0))]),
    ('GetDrawListEntityRef', [('var', ('ARRAYPOS1', 0)), ('int', 3), ('var', ('TEMPVALUE2', 0))]),
    ('IfGreater', [('int', 4), ('var', ('OBJECTVALUE5', 1, (1, 0))), ('var', ('OBJECTVALUE5', 1, (1, 1)))]),
    ('SetDrawListEntityRef', [('var', ('ARRAYPOS0', 0)), ('int', 3), ('var', ('TEMPVALUE2', 0))]),
    ('SetDrawListEntityRef', [('var', ('ARRAYPOS1', 0)), ('int', 3), ('var', ('TEMPVALUE3', 0))]),
    ('endif', []),
    ('loop', []),
    ('Inc', [('var', ('TEMPVALUE0', 0))]),
    ('loop', []),
    ('End', []),
]


def game_stage_lists(data):
    sys.path.insert(0, os.path.join(HERE, '..', 'disc'))
    import gen_load_order
    return gen_load_order.game_config(data)[2]


def patch_ss_sort(data):
    names, vars_ = bs.tables()
    op = [n for n, _ in names].index('PS1SortDrawList')
    done, already = [], []
    for pos, (folder, _) in enumerate(game_stage_lists(data)[3]):  # the special stage list: SS000.bin...
        path = os.path.join(data, 'Scripts', 'ByteCode', 'SS%03d.bin' % pos)
        obj, _ = object_index(data, folder, 'Special Setup')
        raw = open(path, 'rb').read()
        code, p = bs.blocks(raw, 0)
        rest = raw[p:]
        start = bs.subs(path)[obj][2]
        if code[start] == op:
            already.append(folder)
            continue
        got = [(n, [(o[0], o[1]) for o in ops]) for _, n, ops in instructions(code, start, names, vars_)]
        if got != SS_SORT:
            sys.exit('ERROR patch_bytecode: %s Special Setup draw sub is not the expected draw-list sort' % folder)
        code[start:start + 6] = [op, 2, 3, 2, 5, 0]  # PS1SortDrawList 3, 5 / End
        open(path, 'wb').write(encode(code) + rest)
        c2, q = bs.blocks(open(path, 'rb').read(), 0)
        assert c2 == code
        done.append(folder)
    return 'draw-list sort native in %s%s' % (' '.join(done) or '-', ' (already: %s)' % ' '.join(already) if already else '')


# Special stage BGEffects draw subs ending in a deformation ramp loop (SS5): -> PS1DeformRamp first, start,
# parallax entry, shift (RSDKv3/Script.cpp: the same loop natively), then End. Constants taken from the code.
def ramp_pattern(k):
    """The loop's instructions with its constants as placeholders (None = any int, checked after)."""
    return [
        ('Equal', [('var', ('ARRAYPOS0', 0)), ('int', k['first'])]),
        ('Equal', [('var', ('TEMPVALUE2', 0)), ('int', k['start'])]),
        ('Equal', [('var', ('TEMPVALUE3', 0)), ('int', 0)]),
        ('WGreater', [('int', k['j']), ('var', ('ARRAYPOS0', 0)), ('int', -1)]),
        ('Equal', [('var', ('TEMPVALUE4', 0)), ('var', ('HPARALLAXSCROLLPOS', 1, (0, k['p'])))]),
        ('Mul', [('var', ('TEMPVALUE4', 0)), ('var', ('TEMPVALUE2', 0))]),
        ('ShR', [('var', ('TEMPVALUE4', 0)), ('int', k['shift'])]),
        ('Equal', [('var', ('STAGEDEFORMATIONDATA2', 1, (1, 0))), ('var', ('TEMPVALUE4', 0))]),
        ('Sub', [('var', ('TEMPVALUE2', 0)), ('var', ('TEMPVALUE3', 0))]),
        ('Inc', [('var', ('TEMPVALUE3', 0))]),
        ('Dec', [('var', ('ARRAYPOS0', 0))]),
        ('loop', []),
        ('End', []),
    ]


def patch_ss_ramp(data):
    names, vars_ = bs.tables()
    op = [n for n, _ in names].index('PS1DeformRamp')
    done, already = [], []
    for pos, (folder, _) in enumerate(game_stage_lists(data)[3]):
        path = os.path.join(data, 'Scripts', 'ByteCode', 'SS%03d.bin' % pos)
        try:
            obj, _ = object_index(data, folder, 'BGEffects')
        except ValueError:
            continue
        raw = open(path, 'rb').read()
        code, p = bs.blocks(raw, 0)
        rest = raw[p:]
        ins = instructions(code, bs.subs(path)[obj][2], names, vars_)
        if any(n == 'PS1DeformRamp' for _, n, _ in ins):
            already.append(folder)
            continue
        for k in range(len(ins) - 12):
            at, n, ops = ins[k]
            if n != 'Equal' or ops[0][1] != ('ARRAYPOS0', 0) or ops[1][0] != 'int':
                continue
            seq = ins[k:k + 13]
            try:
                c = {'first': seq[0][2][1][1], 'start': seq[1][2][1][1], 'j': seq[3][2][0][1],
                     'p': seq[4][2][1][1][2][1], 'shift': seq[6][2][1][1]}
            except (IndexError, TypeError):
                continue
            got = [(nn, [(o[0], o[1]) for o in oo]) for _, nn, oo in seq]
            if got != ramp_pattern(c):
                continue
            code[at:at + 10] = [op, 2, c['first'], 2, c['start'], 2, c['p'], 2, c['shift'], 0]  # ... / End
            open(path, 'wb').write(encode(code) + rest)
            assert bs.blocks(open(path, 'rb').read(), 0)[0] == code
            done.append('%s (%d lines, factor %d, parallax %d, >> %d)' % (folder, c['first'] + 1, c['start'], c['p'], c['shift']))
            break
    return 'deformation ramp native in %s%s' % (', '.join(done) or '-', ' (already: %s)' % ' '.join(already) if already else '')


# R11A's 3DRamp: a per-line parallax ramp loop run every frame (docs/28 speed pass 2, ~119 hblanks):
#   WLower j, ARRAYPOS0, end / Equal T1, T0 / Mul T1, T2 / ShR T1, k / Add HPARALLAXSCROLLPOS[pos0], T1 / Inc ARRAYPOS0
#   / Dec T2 / loop  ->  only the WLower opcode becomes PS1ParallaxRamp (RSDKv3/Script.cpp: the same loop natively; same
# operands, the body left in place, so every instruction keeps its position). Found by its full instruction pattern
# anywhere in a stage file's code.
PRAMP = [
    ('WLower', [('int', None), ('var', ('ARRAYPOS0', 0)), ('int', None)]),
    ('Equal', [('var', ('TEMPVALUE1', 0)), ('var', ('TEMPVALUE0', 0))]),
    ('Mul', [('var', ('TEMPVALUE1', 0)), ('var', ('TEMPVALUE2', 0))]),
    ('ShR', [('var', ('TEMPVALUE1', 0)), ('int', None)]),
    ('Add', [('var', ('HPARALLAXSCROLLPOS', 1, (1, 0))), ('var', ('TEMPVALUE1', 0))]),
    ('Inc', [('var', ('ARRAYPOS0', 0))]),
    ('Dec', [('var', ('TEMPVALUE2', 0))]),
    ('loop', []),
]


def patch_parallax_ramp(data):
    names, vars_ = bs.tables()
    nm = [n for n, _ in names]
    op, wlower = nm.index('PS1ParallaxRamp'), nm.index('WLower')
    bc = os.path.join(data, 'Scripts', 'ByteCode')
    done, already = [], []
    for fn in sorted(os.listdir(bc)):
        if not fn.startswith('RS'):
            continue
        path = os.path.join(bc, fn)
        raw = open(path, 'rb').read()
        code, p = bs.blocks(raw, 0)
        rest = raw[p:]
        hits = []
        for at in range(len(code)):
            if code[at] not in (wlower, op):
                continue
            try:
                ins = instructions(code, at, names, vars_)[:len(PRAMP)]
            except (IndexError, KeyError):
                continue
            got = [('WLower' if n == 'PS1ParallaxRamp' else n, [(o[0], o[1] if o[0] == 'var' else None) for o in ops]) for _, n, ops in ins]
            if got != PRAMP:
                continue
            # the body's lengths the engine relies on: Equal at +8, Mul at +15, ShR's constant at +8 + 7 + 7 + 5
            if [a - at for a, _, _ in ins[1:4]] != [8, 15, 22] or ins[3][2][1][2] != at + 27:
                sys.exit('ERROR patch_bytecode: %s @%d parallax ramp with unexpected operand forms' % (fn, at))
            hits.append((at, ins[0][1] == 'PS1ParallaxRamp', ins[0][2][2][1], ins[3][2][1][1]))
        for at, was, end, k in hits:
            if was:
                already.append('%s@%d' % (fn, at))
                continue
            code[at] = op
            done.append('%s@%d (to %d, >> %d)' % (fn, at, end, k))
        if any(not w for _, w, _, _ in hits):
            open(path, 'wb').write(encode(code) + rest)
            assert bs.blocks(open(path, 'rb').read(), 0)[0] == code
    return 'parallax ramp native in %s%s' % (', '.join(done) or '-', ' (already: %s)' % ' '.join(already) if already else '')


# The Credits' TextFont1-3 draw subs: a character-by-character text loop (docs/28 speed pass 2, ~800 hblanks a frame).
# Only the loop's WGreater opcode becomes PS1TextLoop (RSDKv3/Script.cpp runs the loop natively); the whole shape is
# checked here: the instructions below, the switch's jump table (default right after the switch, exit after
# endswitch, every case target either the default or a 'DrawSpriteXY k, TEMPVALUE2, OBJECTYPOS / break' body) and the
# loop's exit after its 'loop'.
V = lambda n: ('var', (n, 0))
TEXT_HEAD = [
    ('WGreater', [('int', None), V('TEMPVALUE1'), ('int', 0)]),
    ('GetTextInfo', [V('TEMPVALUE0'), ('int', 0), ('int', 0), V('OBJECTVALUE1'), V('ARRAYPOS0')]),
    ('switch', [('int', None), V('TEMPVALUE0')]),
    ('Equal', [V('OBJECTFRAME'), ('int', 0)]),
    ('IfGreater', [('int', None), V('TEMPVALUE0'), ('int', 64)]),
    ('IfLower', [('int', None), V('TEMPVALUE0'), ('int', 91)]),
    ('Equal', [V('OBJECTFRAME'), V('TEMPVALUE0')]),
    ('Sub', [V('OBJECTFRAME'), ('int', 64)]),
    ('endif', []), ('endif', []),
    ('IfGreater', [('int', None), V('TEMPVALUE0'), ('int', 96)]),
    ('IfLower', [('int', None), V('TEMPVALUE0'), ('int', 123)]),
    ('Equal', [V('OBJECTFRAME'), V('TEMPVALUE0')]),
    ('Sub', [V('OBJECTFRAME'), ('int', 96)]),
    ('endif', []), ('endif', []),
    ('IfGreater', [('int', None), V('OBJECTFRAME'), ('int', 0)]),
    ('DrawSpriteXY', [V('OBJECTFRAME'), V('TEMPVALUE2'), V('OBJECTYPOS')]),
    ('endif', []),
    ('break', []),
]
TEXT_CASE = [('DrawSpriteXY', [('int', None), V('TEMPVALUE2'), V('OBJECTYPOS')]), ('break', [])]
TEXT_TAIL = [('endswitch', []), ('Inc', [V('ARRAYPOS0')]), ('Dec', [V('TEMPVALUE1')]), ('Add', [V('TEMPVALUE2'), ('int', 524288)]),
             ('loop', [])]


def matches(ins, template):
    """ins (instructions()) against a template: names and operand kinds equal, values equal unless the template's is None."""
    if len(ins) != len(template):
        return False
    for (_, n, ops), (tn, tops) in zip(ins, template):
        if n != tn or len(ops) != len(tops):
            return False
        for o, (tk, tv) in zip(ops, tops):
            if o[0] != tk or (tv is not None and o[1] != tv):
                return False
    return True


def patch_text_loops(data):
    names, vars_ = bs.tables()
    nm = [n for n, _ in names]
    op, wgreater = nm.index('PS1TextLoop'), nm.index('WGreater')
    bc = os.path.join(data, 'Scripts', 'ByteCode')
    graw = open(os.path.join(bc, 'GS000.bin'), 'rb').read()
    gcode, gp = bs.blocks(graw, 0)
    gjt, _ = bs.blocks(graw, gp)
    done, already = [], []
    for fn in sorted(os.listdir(bc)):
        if not fn.startswith('PS'):
            continue
        path = os.path.join(bc, fn)
        raw = open(path, 'rb').read()
        fcode, p = bs.blocks(raw, 0)
        fjt, _ = bs.blocks(raw, p)
        code, jtab = list(gcode) + list(fcode), list(gjt) + list(fjt)  # sub / jump pointers count from GS000's start
        subs = [(c, j) for cs, js in zip(bs.subs(path), bd.jump_tables(path)[1]) for c, j in zip(cs, js) if 0 <= c < len(code)]
        hits = []
        for at in range(len(gcode), len(code)):
            if code[at] not in (wgreater, op):
                continue
            try:
                head = instructions(code, at, names, vars_)[:len(TEXT_HEAD)]
            except (IndexError, KeyError):
                continue
            if not matches([(a, 'WGreater' if n == 'PS1TextLoop' else n, o) for a, n, o in head], TEXT_HEAD):
                continue
            start, jstart = max((c, j) for c, j in subs if c <= at)  # the sub holding the loop
            jw, sw = head[0][2][0][1], head[2][2][0][1]
            lo, hi, dflt, end = jtab[jstart + sw:jstart + sw + 4]
            err = lambda m: sys.exit('ERROR patch_bytecode: %s @%d text loop: %s' % (fn, at, m))
            if start + dflt != head[3][0]:
                err('switch default is not after the switch')
            pos = head[-1][0] + 1
            cases = set()
            while code[pos] == nm.index('DrawSpriteXY'):
                c = instructions(code, pos, names, vars_)[:2]
                if not matches(c, TEXT_CASE):
                    err('case body at %d' % pos)
                cases.add(pos - start)
                pos = c[1][0] + 1
            tail = instructions(code, pos, names, vars_)[:len(TEXT_TAIL)]
            if not matches(tail, TEXT_TAIL):
                err('loop tail')
            if start + end != tail[1][0] or start + jtab[jstart + jw + 1] != tail[-1][0] + 1 or start + jtab[jstart + jw] != at:
                err('switch exit / loop jump entries')
            for k in range(hi - lo + 1):
                tgt = jtab[jstart + sw + 4 + k]
                if tgt != dflt and tgt not in cases:
                    err('case %d target %d' % (lo + k, tgt))
            # the default body's if offsets the engine reads (dc[8], dc[16], dc[39], dc[47], dc[70]) are the ifs' entries
            d0 = head[3][0]
            if [head[i][0] - d0 for i in (4, 5, 10, 11, 16)] != [6, 14, 37, 45, 68] or head[2][0] != at + 22:
                err('instruction offsets')
            hits.append((at, head[0][1] == 'PS1TextLoop'))
        new = [a for a, w in hits if not w]
        already += ['%s@%d' % (fn, a - len(gcode)) for a, w in hits if w]
        if new:
            for a in new:
                code[a] = op
            fcode2 = code[len(gcode):]
            open(path, 'wb').write(encode(fcode2) + raw[p:])
            assert bs.blocks(open(path, 'rb').read(), 0)[0] == fcode2
            done += ['%s@%d' % (fn, a - len(gcode)) for a in new]
    return 'text loops native in %s%s' % (', '.join(done) or '-', ' (already: %s)' % ' '.join(already) if already else '')


# The special stages' UFO-type objects: the floor-camera transform block in their main subs (docs/28 speed pass 2): only
# its first opcode (Equal TEMPVALUE0, OBJECTXPOS) becomes PS1UfoView (RSDKv3/Script.cpp runs the 20 instructions
# natively and continues after their 148 words). k: the object values receiving the result (k, k + 1).
def ufo_view(k):
    L = lambda n: ('var', (n, 1, (0, 0)))
    T = lambda i: V('TEMPVALUE%d' % i)
    O = lambda i: V('OBJECTVALUE%d' % i)
    return [('Equal', [T(0), V('OBJECTXPOS')]), ('Sub', [T(0), L('TILELAYERXPOS')]), ('ShR', [T(0), ('int', 8)]),
            ('Equal', [T(1), V('OBJECTYPOS')]), ('Sub', [T(1), L('TILELAYERZPOS')]), ('ShR', [T(1), ('int', 8)]),
            ('Sin', [T(2), L('TILELAYERANGLE')]), ('Mul', [T(2), T(1)]), ('Cos', [T(3), L('TILELAYERANGLE')]), ('Mul', [T(3), T(0)]),
            ('Equal', [O(k), T(2)]), ('Sub', [O(k), T(3)]), ('ShR', [O(k), ('int', 9)]),
            ('Cos', [T(2), L('TILELAYERANGLE')]), ('Mul', [T(2), T(1)]), ('Sin', [T(3), L('TILELAYERANGLE')]), ('Mul', [T(3), T(0)]),
            ('Equal', [O(k + 1), T(2)]), ('Add', [O(k + 1), T(3)]), ('ShR', [O(k + 1), ('int', 9)])]


def patch_ufo_view(data):
    names, vars_ = bs.tables()
    nm = [n for n, _ in names]
    op, equal = nm.index('PS1UfoView'), nm.index('Equal')
    bc = os.path.join(data, 'Scripts', 'ByteCode')
    done, already = [], []
    for fn in sorted(os.listdir(bc)):
        if not fn.startswith('SS'):
            continue
        path = os.path.join(bc, fn)
        raw = open(path, 'rb').read()
        code, p = bs.blocks(raw, 0)
        new = []
        for at in range(len(code)):
            if code[at] not in (equal, op):
                continue
            try:
                ins = instructions(code, at, names, vars_)[:20]
            except (IndexError, KeyError):
                continue
            ins = [(a, 'Equal' if (a == at and n == 'PS1UfoView') else n, o) for a, n, o in ins]
            k = next((kk for kk in range(7) if matches(ins, ufo_view(kk))), None)
            if k is None:
                continue
            if ins[10][0] - at != 76 or ins[-1][0] + 6 - at != 148:
                sys.exit('ERROR patch_bytecode: %s @%d UFO view block with unexpected lengths' % (fn, at))
            if code[at] == op:
                already.append('%s@%d' % (fn, at))
            else:
                new.append((at, k))
        if new:
            for at, _ in new:
                code[at] = op
            open(path, 'wb').write(encode(code) + raw[p:])
            assert bs.blocks(open(path, 'rb').read(), 0)[0] == code
            done += ['%s@%d (values %d-%d)' % (fn, at, k, k + 1) for at, k in new]
    return 'UFO view blocks native in %s%s' % (', '.join(done) or '-', ' (already: %s)' % ' '.join(already) if already else '')


# Script function 46 (GS000), called by every time warp: its loop over objects 32-1055 recording which are gone in
# SAVERAM 7168-8191 (docs/28 speed pass 2: ~10,000 VM instructions in one frame, a 9-vsync freeze). Only the loop's
# WLower opcode becomes PS1SaveObjects (RSDKv3/Script.cpp: the same loop natively); the whole loop is checked here,
# including the ifs' jump entries the engine reproduces (2-14) and the loop's own jump entries.
def save_objects():
    A = lambda n, a: ('var', (n, 1, a))
    P24 = A('OBJECTPROPERTYVALUE', (0, 24))
    TY, ST, SR = A('OBJECTTYPE', (1, 0)), A('OBJECTSTATE', (1, 0)), A('SAVERAM', (1, 1))
    I = lambda v: ('int', v)
    SB = lambda b, v: ('SetBit', [SR, b, I(v)])
    return [('WLower', [I(0), V('ARRAYPOS0'), I(1056)]),
            ('IfEqual', [I(2), TY, I(0)]), SB(P24, 1), ('else', []),
            ('IfEqual', [I(4), TY, I(12)]), SB(P24, 1), ('else', []),
            ('IfEqual', [I(6), TY, I(16)]), ('IfEqual', [I(8), ST, I(2)]), SB(P24, 1), ('else', []), SB(P24, 0), ('endif', []),
            ('else', []),
            ('IfEqual', [I(10), TY, I(17)]), ('IfEqual', [I(12), ST, I(2)]), SB(P24, 1), ('else', []), SB(P24, 0), ('endif', []),
            ('else', []), SB(P24, 0),
            ('IfEqual', [I(14), TY, A('GLOBAL', (0, 51))]), SB(V('TEMPVALUE1'), 1), ('else', []), SB(V('TEMPVALUE1'), 0),
            ('endif', []), ('endif', []), ('endif', []), ('endif', []), ('endif', []),
            ('Inc', [V('ARRAYPOS0')]), ('Inc', [V('ARRAYPOS1')]), ('loop', []), ('EndFunction', [])]


def patch_save_objects(data):
    names, vars_ = bs.tables()
    nm = [n for n, _ in names]
    op, wlower = nm.index('PS1SaveObjects'), nm.index('WLower')
    path = os.path.join(data, 'Scripts', 'ByteCode', 'GS000.bin')
    raw = open(path, 'rb').read()
    code, p = bs.blocks(raw, 0)
    jtab, _ = bs.blocks(raw, p)
    funcs = bd.functions(path)
    tmpl = save_objects()
    starts = sorted(set(c for c, _ in funcs if 0 <= c < len(code))) + [len(code)]
    for fi, (start, jstart) in enumerate(funcs):
        if not 0 <= start < len(code):
            continue
        nxt = min(c for c in starts if c > start)  # the function's own code only
        for at in range(start, min(start + 200, nxt)):
            if code[at] not in (wlower, op):
                continue
            try:
                ins = instructions(code, at, names, vars_)[:len(tmpl)]
            except (IndexError, KeyError):
                continue
            ins = [(a, 'WLower' if (a == at and n == 'PS1SaveObjects') else n, o) for a, n, o in ins]
            if not matches(ins, tmpl):
                continue
            loop_at = ins[-2][0]
            if start + jtab[jstart] != at or start + jtab[jstart + 1] != loop_at + 1:
                sys.exit('ERROR patch_bytecode: GS000 function %d: the save loop\'s jump entries' % fi)
            if code[at] == op:
                return 'object save loop native in - (already: GS000 function %d)' % fi
            code[at] = op
            open(path, 'wb').write(encode(code) + raw[p:])
            assert bs.blocks(open(path, 'rb').read(), 0)[0] == code
            return 'object save loop native in GS000 function %d @%d' % (fi, at)
    return 'object save loop native in - (not found)'


# The Title's Background draw sub: its water-strip loop (docs/28 speed pass 2). Only the WLower opcode becomes
# PS1TitleWater (RSDKv3/Script.cpp); the whole loop is checked, including the IfGreater entry the engine writes (2).
def title_water():
    A = lambda n: ('var', (n, 1, (1, 0)))  # OBJECTXPOS[pos0]
    I = lambda v: ('int', v)
    return [('WLower', [I(0), V('TEMPVALUE0'), I(39)]), ('Add', [A('OBJECTXPOS'), V('TEMPVALUE1')]),
            ('IfGreater', [I(2), A('OBJECTXPOS'), I(33554432)]), ('Sub', [A('OBJECTXPOS'), I(33554432)]), ('endif', []),
            ('Equal', [V('TEMPVALUE2'), A('OBJECTXPOS')]), ('ShR', [V('TEMPVALUE2'), I(16)]), ('Inc', [V('ARRAYPOS0')]),
            ('DrawSpriteScreenXY', [V('TEMPVALUE0'), V('TEMPVALUE2'), I(0)]), ('Inc', [V('TEMPVALUE0')]),
            ('DrawSpriteScreenXY', [V('TEMPVALUE0'), V('TEMPVALUE2'), I(0)]), ('Inc', [V('TEMPVALUE0')]),
            ('Add', [V('TEMPVALUE1'), I(8192)]), ('loop', [])]


def patch_title_water(data):
    names, vars_ = bs.tables()
    nm = [n for n, _ in names]
    op, wlower = nm.index('PS1TitleWater'), nm.index('WLower')
    path = os.path.join(data, 'Scripts', 'ByteCode', 'PS000.bin')  # presentation stage 0 = the Title
    raw = open(path, 'rb').read()
    code, p = bs.blocks(raw, 0)
    tmpl = title_water()
    hits = []
    for at in range(len(code)):
        if code[at] not in (wlower, op):
            continue
        try:
            ins = instructions(code, at, names, vars_)[:len(tmpl)]
        except (IndexError, KeyError):
            continue
        ins = [(a, 'WLower' if (a == at and n == 'PS1TitleWater') else n, o) for a, n, o in ins]
        if matches(ins, tmpl):
            hits.append(at)
    if len(hits) != 1:
        sys.exit('ERROR patch_bytecode: PS000 Title water loop: %d matches' % len(hits))
    at = hits[0]
    if code[at] == op:
        return 'Title water loop native in - (already: PS000.bin@%d)' % at
    code[at] = op
    open(path, 'wb').write(encode(code) + raw[p:])
    assert bs.blocks(open(path, 'rb').read(), 0)[0] == code
    return 'Title water loop native in PS000.bin@%d' % at


# Tidal Tempest's AirBubble main sub (R4x stages; docs/28 speed pass 2: 30-40 VM instructions per bubble a frame,
# ~17 hblanks in R41A). Only the first IfEqual opcode becomes PS1AirBubble (RSDKv3/Script.cpp: the same sub natively,
# down to the jump stack slots and the operand registers it leaves); the whole sub is checked here, including the
# global variables it compares the player's animation with and sets it to (79, 104, 80, 69).
def air_bubble():
    I = lambda v: ('int', v)
    G = lambda i: ('var', ('GLOBAL', 1, (0, i)))
    O = lambda n: V('OBJECT' + n)
    return [('IfEqual', [I(0), O('STATE'), I(0)]), ('Inc', [O('VALUE0')]),
            ('IfGreater', [I(2), O('VALUE0'), I(15)]), ('Equal', [O('VALUE0'), I(0)]),
            ('IfEqual', [I(4), O('FRAME'), I(6)]), ('Equal', [O('TYPE'), I(0)]), ('endif', []),
            ('IfLower', [I(6), O('FRAME'), O('PROPERTYVALUE')]), ('Inc', [O('FRAME')]), ('endif', []), ('endif', []),
            ('Add', [O('YPOS'), O('VALUE3')]),
            ('IfEqual', [I(8), V('PLAYERANIMATION'), G(79)]),
            ('IfLower', [I(10), O('PROPERTYVALUE'), I(3)]), ('Add', [O('VALUE2'), I(262144)]), ('endif', []), ('endif', []),
            ('IfEqual', [I(12), V('PLAYERANIMATION'), G(104)]),
            ('IfLower', [I(14), O('PROPERTYVALUE'), I(3)]), ('Add', [O('VALUE2'), I(262144)]), ('endif', []), ('endif', []),
            ('IfLower', [I(16), O('FRAME'), I(6)]), ('Sin', [O('XPOS'), O('VALUE1')]), ('ShL', [O('XPOS'), I(9)]),
            ('Add', [O('XPOS'), O('VALUE2')]), ('Add', [O('VALUE1'), I(4)]), ('And', [O('VALUE1'), I(511)]), ('endif', []),
            ('IfLower', [I(18), O('IYPOS'), V('STAGEWATERLEVEL')]),
            ('IfEqual', [I(20), O('PROPERTYVALUE'), I(5)]), ('Equal', [O('FRAME'), I(6)]), ('Equal', [O('PROPERTYVALUE'), I(6)]),
            ('Equal', [O('VALUE0'), I(0)]), ('Equal', [O('VALUE3'), I(0)]), ('else', []),
            ('IfLower', [I(22), O('PROPERTYVALUE'), I(5)]), ('Equal', [O('TYPE'), I(0)]), ('endif', []),
            ('endif', []), ('endif', []), ('else', []),
            ('IfLower', [I(24), O('VALUE0'), I(20)]), ('Inc', [O('VALUE0')]), ('Equal', [V('PLAYERANIMATION'), G(80)]),
            ('else', []), ('Equal', [O('TYPE'), I(0)]), ('Equal', [V('PLAYERANIMATION'), G(69)]),
            ('Equal', [V('PLAYERANIMATIONSPEED'), I(20)]), ('endif', []), ('endif', []),
            ('IfEqual', [I(26), O('OUTOFBOUNDS'), I(1)]), ('Equal', [O('TYPE'), I(0)]), ('endif', []), ('End', [])]


def patch_air_bubble(data):
    names, vars_ = bs.tables()
    nm = [n for n, _ in names]
    op, ifequal = nm.index('PS1AirBubble'), nm.index('IfEqual')
    bc = os.path.join(data, 'Scripts', 'ByteCode')
    tmpl = air_bubble()
    done, already = [], []
    for fn in sorted(os.listdir(bc)):
        if not fn.startswith('RS'):
            continue
        path = os.path.join(bc, fn)
        raw = open(path, 'rb').read()
        code, p = bs.blocks(raw, 0)
        new = []
        for at in range(len(code)):
            if code[at] not in (ifequal, op):
                continue
            try:
                ins = instructions(code, at, names, vars_)
            except (IndexError, KeyError):
                continue
            ins = [(a, 'IfEqual' if (a == at and n == 'PS1AirBubble') else n, o) for a, n, o in ins]
            if not matches(ins, tmpl):
                continue
            if ins[1][0] - at != 8 or ins[-1][0] - at != 278:
                sys.exit('ERROR patch_bytecode: %s @%d AirBubble main with unexpected lengths' % (fn, at))
            (already if code[at] == op else new).append(at if code[at] != op else '%s@%d' % (fn, at))
        if new:
            for at in new:
                code[at] = op
            open(path, 'wb').write(encode(code) + raw[p:])
            assert bs.blocks(open(path, 'rb').read(), 0)[0] == code
            done += ['%s@%d' % (fn, at) for at in new]
    return 'AirBubble main native in %s%s' % (', '.join(done) or '-', ' (already: %s)' % ' '.join(already) if already else '')


def main():
    data = sys.argv[1]
    print('PS001.bin: ' + patch_options(data))
    print('SS*.bin: ' + patch_ss_sort(data))
    print('SS*.bin: ' + patch_ss_ramp(data))
    print('RS*.bin: ' + patch_parallax_ramp(data))
    print('PS*.bin: ' + patch_text_loops(data))
    print('SS*.bin: ' + patch_ufo_view(data))
    print('GS000.bin: ' + patch_save_objects(data))
    print('PS000.bin: ' + patch_title_water(data))
    print('RS*.bin: ' + patch_air_bubble(data))


if __name__ == '__main__':
    main()
