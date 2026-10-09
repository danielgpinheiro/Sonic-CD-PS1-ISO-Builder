#!/usr/bin/python3
"""Disassemble one object's subs from a Sonic CD bytecode file (debug aid, docs/28 phase 4).

Usage: bytecode_dis.py DATA_DIR FILE OBJECT_INDEX|fFUNCTION [GLOBALS]   (OBJECT_INDEX: 0-based within the
file; GLOBALS = 1 if the stage loads GS000 first, so offsets are absolute after it)
"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bytecode_scan as bs


def jump_tables(path):
    """The file's jump table and each object's per-sub jump table pointers (after the code pointers)."""
    d = open(path, 'rb').read()
    _, p = bs.blocks(d, 0)
    jt, p = bs.blocks(d, p)
    count, = struct.unpack_from('<H', d, p)
    p += 2 + 16 * count
    return jt, [struct.unpack_from('<4i', d, p + 16 * i) for i in range(count)]


def functions(path):
    """(code pointer, jump table pointer) of each script function in the file."""
    d = open(path, 'rb').read()
    _, p = bs.blocks(d, 0)
    _, p = bs.blocks(d, p)
    count, = struct.unpack_from('<H', d, p)
    p += 2 + 32 * count
    n, = struct.unpack_from('<H', d, p)
    p += 2
    code = struct.unpack_from('<%di' % n, d, p)
    jump = struct.unpack_from('<%di' % n, d, p + 4 * n)
    return list(zip(code, jump))


def dis(code, start, names, vars_, limit=100000, jt=None, jstart=0):
    p = start
    n = 0
    while 0 <= p < len(code) and n < limit:
        at = p
        op = code[p]
        p += 1
        if op >= len(names):
            print('%6d ??? %d' % (at, op))
            break
        name, size = names[op]
        ops = []
        for _ in range(size):
            t = code[p]
            p += 1
            if t < 0:  # a PS1 direct operand rewritten at load (RSDKv3/Script.cpp PS1DirectOperand; dumped RAM code)
                kind, ln = t & 7, (t >> 4) & 7
                ops.append(str(code[p]) if kind == 4 else '%s:%s' % (('abs', 'absB', 'ent', 'entB')[kind], hex(code[p] & 0xFFFFFFFF) if kind < 2 else code[p]))
                p += ln - 1
                continue
            if t == 1:
                arr = code[p]
                p += 1
                idx = ''
                if arr in (1, 2, 3):
                    idx = '[%s%s%d]' % ('+' if arr == 2 else '-' if arr == 3 else '', 'pos' if code[p] == 1 else '', code[p + 1])
                    p += 2
                ops.append(vars_[code[p]].replace('VAR_', '') + idx)
                p += 1
            elif t == 2:
                ops.append(str(code[p]))
                p += 1
            elif t == 3:
                ln = code[p]
                ops.append('"%s"' % ''.join(chr((code[p + 1 + c // 4] >> (24 - 8 * (c % 4))) & 0xFF) for c in range(ln)))
                p += ln // 4 + 2
        line = '%6d %s %s' % (at, name, ', '.join(ops))
        if name == 'switch' and jt is not None and code[at + 1] == 2:  # int jump table index
            j = jstart + code[at + 2]
            lo, hi, dflt, end = jt[j:j + 4]
            cases = ' '.join('%d->%d' % (lo + k, start + jt[j + 4 + k]) for k in range(hi - lo + 1))
            line += '   [%s | default->%d end->%d]' % (cases, start + dflt, start + end)
        print(line)
        n += 1
        if name == 'End':
            break


def main():
    data, fn = sys.argv[1], sys.argv[2]
    if sys.argv[3].startswith('f'):  # fN: script function N
        bc = os.path.join(data, 'Scripts', 'ByteCode')
        names, vars_ = bs.tables()
        jt, _ = jump_tables(os.path.join(bc, fn))
        off, jstart = functions(os.path.join(bc, fn))[int(sys.argv[3][1:])]
        print('--- function %s @%d (jump table @%d)' % (sys.argv[3][1:], off, jstart))
        dis(bs.ints(os.path.join(bc, fn)), off, names, vars_, jt=jt, jstart=jstart)
        return
    obj = int(sys.argv[3])
    glob = len(sys.argv) > 4 and sys.argv[4] == '1'
    bc = os.path.join(data, 'Scripts', 'ByteCode')
    code = (bs.ints(os.path.join(bc, 'GS000.bin')) if glob else []) + bs.ints(os.path.join(bc, fn))
    names, vars_ = bs.tables()
    subs = bs.subs(os.path.join(bc, fn))[obj]
    jt, jptrs = jump_tables(os.path.join(bc, fn))
    for label, off, jstart in zip(('main', 'playerInteraction', 'draw', 'startup'), subs, jptrs[obj]):
        if off == 0x3FFFF:
            continue
        print('--- %s @%d (jump table @%d)' % (label, off, jstart))
        dis(code, off, names, vars_, jt=jt, jstart=jstart)


if __name__ == '__main__':
    main()
