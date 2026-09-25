#!/usr/bin/env python3
"""Static scan of RSDKv3 (Sonic CD, BYTECODE_PC) script bytecode for PS1 sizing (docs/28).

Decodes Scripts/ByteCode/*.bin exactly as LoadBytecode does (RSDKv3/Script.cpp: u32 int count,
then blocks: header byte, n = h & 0x7F values of 4 bytes if h >= 0x80 else 1 byte), then walks the
opcode stream as ProcessScript reads it: opcode, then per operand a type (1 = variable: array
type [+ array flag + index] + variable id; 2 = int constant; 3 = string: length + len/4 + 1 ints).
Function and variable tables are parsed from RSDKv3/Script.cpp (FunctionInfo list, ScrVariable).

Reports, per bytecode file: uses of the functions/variables named with --find, and the int
constants assigned to variables named with --values (e.g. VAR_3DSCENENOVERTICES).

With --where FILE: attribute each --values write in that bytecode file (e.g. RS000.bin) to its
object sub ("<object #>.<sub>", object numbers in load order within the file).

Usage: bytecode_scan.py DATA_DIR [--find NAME ...] [--values VAR ...] [--where FILE]
"""
import glob, os, re, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT_CPP = os.path.join(HERE, '..', 'RSDKv3', 'Script.cpp')


def tables():
    src = open(SCRIPT_CPP).read()
    funcs = [(n, int(c)) for n, c in re.findall(r'FunctionInfo\("(\w+)",\s*(\d+)\)', src)]
    body = src[src.index('enum ScrVariable {'):]
    body = body[:body.index('};')]
    vars_ = re.findall(r'^\s*(VAR_\w+)', body, re.M)
    return funcs, vars_


def blocks(d, p):
    n, = struct.unpack_from('<I', d, p)
    p += 4
    out = []
    while len(out) < n:
        h = d[p]; p += 1
        for _ in range(h & 0x7F):
            if h >= 0x80:
                out.append(struct.unpack_from('<i', d, p)[0]); p += 4
            else:
                out.append(d[p]); p += 1
    return out, p


def ints(path):
    return blocks(open(path, 'rb').read(), 0)[0]


def subs(path):
    """Per object: (main, playerInteraction, draw, startup) code offsets as stored (absolute
    scriptCode positions: a stage file's offsets start after the global code)."""
    d = open(path, 'rb').read()
    _, p = blocks(d, 0)
    _, p = blocks(d, p)
    count, = struct.unpack_from('<H', d, p)
    p += 2
    return [struct.unpack_from('<4i', d, p + 16 * i) for i in range(count)]


WRITES = []  # (var, opcode name, constant, code position) of the last scan


def scan(code, funcs, vars_, find, values):
    uses, vals, p = {}, {}, 0
    while p < len(code):
        at = p
        op = code[p]; p += 1
        if op >= len(funcs):
            uses['<bad opcode %d>' % op] = uses.get('<bad opcode %d>' % op, 0) + 1
            break
        name, size = funcs[op]
        if name in find:
            uses[name] = uses.get(name, 0) + 1
        operands = []
        for _ in range(size):
            t = code[p]; p += 1
            if t == 1:
                arr = code[p]; p += 1
                if arr in (1, 2, 3):
                    p += 2
                v = vars_[code[p]] if code[p] < len(vars_) else '?'; p += 1
                if v in find:
                    uses[v] = uses.get(v, 0) + 1
                operands.append(('var', v))
            elif t == 2:
                operands.append(('int', code[p])); p += 1
            elif t == 3:
                p += code[p] // 4 + 2
                operands.append(('str', None))
        if len(operands) >= 2 and operands[0][0] == 'var' and operands[0][1] in values and operands[1][0] == 'int':
            vals.setdefault(operands[0][1], set()).add((name, operands[1][1]))
            WRITES.append((operands[0][1], name, operands[1][1], at))
    return uses, vals


def main():
    a = sys.argv[1:]
    data = a[0]
    find = set(a[a.index('--find') + 1:]) if '--find' in a else set()
    values = set(a[a.index('--values') + 1:]) if '--values' in a else set()
    find = {x for x in find if not x.startswith('--')}
    values = {x for x in values if not x.startswith('--')}
    find.discard('--values'); values.discard('--find')
    funcs, vars_ = tables()
    if '--where' in a:
        where = a[a.index('--where') + 1]
        values.discard(where); find.discard(where)
        bc = os.path.join(data, 'Scripts', 'ByteCode')
        base = 0 if where.startswith('GS') else len(ints(os.path.join(bc, 'GS000.bin')))
        path = os.path.join(bc, where)
        del WRITES[:]
        scan(ints(path), funcs, vars_, find, values)
        starts = sorted((off - base, '%d.%s' % (i, n)) for i, t in enumerate(subs(path))
                        for off, n in zip(t, ('main', 'player', 'draw', 'startup')) if off - base >= 0)
        for var, op, val, at in WRITES:
            owner = [n for off, n in starts if off <= at]
            print('%s %s %d at %d in %s' % (var, op, val, at, owner[-1] if owner else '?'))
        return
    for path in sorted(glob.glob(os.path.join(data, 'Scripts', 'ByteCode', '*.bin'))):
        uses, vals = scan(ints(path), funcs, vars_, find, values)
        if uses or vals:
            print('%-10s %s %s' % (os.path.basename(path), ' '.join('%s=%d' % kv for kv in sorted(uses.items())),
                                   ' '.join('%s:%s' % (k, sorted(v)) for k, v in vals.items())))


if __name__ == '__main__':
    main()
