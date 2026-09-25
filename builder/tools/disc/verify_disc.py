#!/usr/bin/env python3
"""Byte-level check of the disc image (phase 9), for emulators, burned discs and ODEs.

Sector format and codes from psx-spx "CDROM Sector Encoding" (cdromformat.md):
- every raw 2352-byte sector: sync pattern, BCD MSF header = its position + 2 s, mode 2;
- Mode 2: the two sub-header copies agree; Form 1 (submode bit 5 clear): EDC over [10h..817h]
  and the P/Q parity (ECC, computed with the header zeroed); Form 2: EDC over [10h..92Bh] when
  stored (0 = none);
- system area: LICENSE.DAT is 12 records of 2336 bytes (sub-header + user data + EDC/ECC area)
  for sectors 0..11; its data must equal the image's (mkpsxiso recomputes EDC/ECC, checked
  above), sectors 12..15 are zero-filled Form 2;
- ISO9660: every file equals its source (build/iso, SYSTEM.CNF, rsdkv3.ps-exe); mixed files
  (CD-XA/STR) compared sector by sector as 2336-byte records (sub-header + data; mkpsxiso fills in
  the EDC/ECC the encoder leaves zero); no source-only file
  (build_disc.SOURCE_ONLY) on the disc; SYSTEM.CNF boots cdrom:\\PSX.EXE;1; PSX.EXE is a PS-X EXE.

Usage: verify_disc.py [BIN] [ISO_ROOT] [EXE] [LICENSE|none]
  defaults: build/game.bin build/iso rsdkv3.ps-exe ../LICENSE.DAT
Exit status 0 = everything checks out.
"""
import os, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
import build_disc  # noqa: E402

RAW = 2352
SYNC = bytes([0] + [0xFF] * 10 + [0])

EDC_TABLE = []
for i in range(256):
    x = i
    for _ in range(8):
        x = (x >> 1) ^ (0xD8018001 if x & 1 else 0)
    EDC_TABLE.append(x)

GF8_LOG, GF8_ILOG = [0] * 256, [0] * 256
x = 1
for i in range(255):
    GF8_LOG[x], GF8_ILOG[i] = i, x
    x <<= 1
    if x & 0x100:
        x ^= 0x11D
GF8_ILOG[255] = 0


def subfunc(a, b):
    if a > 0:
        a = GF8_LOG[a] - b
        if a < 0:
            a += 255
        a = GF8_ILOG[a]
    return a


GF8_PRODUCT = []
for j in range(43):
    xx = GF8_ILOG[44 - j]
    yy = subfunc(xx ^ 1, 0x19)
    xx = subfunc(xx, 0x01)
    xx = subfunc(xx ^ 1, 0x18)
    xx, yy = GF8_LOG[xx], GF8_LOG[yy]
    row = [0] * 256
    for i in range(1, 256):
        a, b = xx + GF8_LOG[i], yy + GF8_LOG[i]
        a -= 255 if a >= 255 else 0
        b -= 255 if b >= 255 else 0
        row[i] = GF8_ILOG[a] | (GF8_ILOG[b] << 8)
    GF8_PRODUCT.append(row)


def edc(data):
    x = 0
    for b in data:
        x = (x >> 8) ^ EDC_TABLE[(x ^ b) & 0xFF]
    return x


def parity(sec, offs, length, j0, step1, step2):
    """psx-spx calc_parity: returns the 4*length parity bytes it would write at 81Ch+offs."""
    out = bytearray(4 * length)
    src, dst, srcmax = 0x0C, 0x81C + offs, 0x81C + offs
    for i in range(length):
        base, x, y = src, 0, 0
        for j in range(j0, 43):
            x ^= GF8_PRODUCT[j][sec[src]]
            y ^= GF8_PRODUCT[j][sec[src + 1]]
            src += step1
            if step1 == 2 * 44 and src >= srcmax:
                src -= 2 * 1118
        out[2 * i + 2 * length], out[2 * i] = x & 0xFF, x >> 8
        out[2 * i + 2 * length + 1], out[2 * i + 1] = y & 0xFF, y >> 8
        src = base + step2
    return bytes(out)


def ecc_ok(sec):
    s = bytearray(sec)
    s[0x0C:0x10] = b'\0\0\0\0'  # the header is zero while computing Mode 2 Form 1 parity
    p = parity(s, 0, 43, 19, 2 * 43, 2)
    s[0x81C:0x81C + len(p)] = p  # Q covers P
    q = parity(s, 43 * 4, 26, 0, 2 * 44, 2 * 43)
    return sec[0x81C:0x81C + 172] == p and sec[0x81C + 172:0x81C + 172 + 104] == q


def bcd(v):
    return ((v // 10) << 4) | (v % 10)


def main():
    a = sys.argv[1:]
    binp = a[0] if len(a) > 0 else os.path.join(REPO, 'build', 'game.bin')
    iso_root = a[1] if len(a) > 1 else os.path.join(REPO, 'build', 'iso')
    exe = a[2] if len(a) > 2 else os.path.join(REPO, 'rsdkv3.ps-exe')
    lic = a[3] if len(a) > 3 else os.path.join(REPO, '..', 'LICENSE.DAT')
    img = open(binp, 'rb').read()
    n = len(img) // RAW
    errors = []
    err = lambda m: errors.append(m) if len(errors) < 40 else None
    forms = [0, 0, 0]  # form1, form2 with EDC, form2 without
    ecc_checked = 0
    for lba in range(n):
        s = img[lba * RAW:(lba + 1) * RAW]
        a150 = lba + 150
        if s[:12] != SYNC:
            err('sector %d: bad sync' % lba); continue
        if s[12:16] != bytes([bcd(a150 // 4500), bcd(a150 // 75 % 60), bcd(a150 % 75), 2]):
            err('sector %d: header %s' % (lba, s[12:16].hex()))
        if s[16:20] != s[20:24]:
            err('sector %d: sub-header copies differ' % lba)
        if s[18] & 0x20:  # Form 2
            stored = struct.unpack_from('<I', s, 0x92C)[0]
            if stored == 0:
                forms[2] += 1
            else:
                forms[1] += 1
                if edc(s[0x10:0x92C]) != stored:
                    err('sector %d: Form 2 EDC' % lba)
        else:
            forms[0] += 1
            if edc(s[0x10:0x818]) != struct.unpack_from('<I', s, 0x818)[0]:
                err('sector %d: Form 1 EDC' % lba)
            ecc_checked += 1
            if not ecc_ok(s):
                err('sector %d: Form 1 ECC' % lba)
    # License: records 0..11 = sectors 0..11 (Form 1 data at +8); sectors 12..15 zero Form 2.
    no_lic = lic.lower() == 'none'
    L = b'' if no_lic else open(lic, 'rb').read()
    lic_ok = no_lic or len(L) == 12 * 2336 and all(
        img[i * RAW + 24:i * RAW + 24 + 2048] == L[i * 2336 + 8:i * 2336 + 8 + 2048] for i in range(12)) and all(
        img[i * RAW + 18] & 0x20 and not any(img[i * RAW + 24:i * RAW + 24 + 2324]) for i in range(12, 16))
    if not lic_ok:
        err('license sectors 0..15 differ from %s' % os.path.basename(lic))
    lic_text = img[4 * RAW + 24:4 * RAW + 24 + 76].decode('ascii', 'replace').split()
    # ISO9660 tree
    user = lambda lba: img[lba * RAW + 24:lba * RAW + 24 + 2048]
    pvd = user(16)
    if pvd[1:6] != b'CD001':
        err('no primary volume descriptor')
    files = []

    def walk(lba, size, prefix):
        for k in range((size + 2047) // 2048):
            d, o = user(lba + k), 0
            while o < 2048 and d[o]:
                ln = d[o]
                el, sz = struct.unpack_from('<I', d, o + 2)[0], struct.unpack_from('<I', d, o + 10)[0]
                nm = d[o + 33:o + 33 + d[o + 32]]
                if nm not in (b'\0', b'\1'):
                    name = prefix + nm.decode(errors='replace').split(';')[0]
                    if d[o + 25] & 2:
                        walk(el, sz, name + '/')
                    else:
                        files.append((name, el, sz))
                o += ln
    walk(struct.unpack_from('<I', pvd, 158)[0], struct.unpack_from('<I', pvd, 166)[0], '')
    src_files = {f.lower(): f for f in build_disc.disc_files(iso_root)}
    compared = 0
    for name, el, sz in files:
        if build_disc.excluded(name):
            err('source-only file on the disc: %s' % name)
        if name.upper() == build_disc.IDX_NAME:
            table = b''.join(user(el + k) for k in range((sz + 2047) // 2048))[:sz]
            want = build_disc.index_bytes([x for x in files if '/' in x[0]])
            if table != want:
                err('%s does not match the directory tree' % name)
            compared += 1
            continue
        if name.upper() == 'SYSTEM.CNF':
            cnf = user(el)[:sz]
            if b'BOOT = cdrom:\\PSX.EXE;1' not in cnf:
                err('SYSTEM.CNF does not boot cdrom:\\PSX.EXE;1')
            continue
        src = exe if name.upper() == 'PSX.EXE' else (
            os.path.join(iso_root, src_files[name.lower()]) if name.lower() in src_files else None)
        if not src:
            err('%s: no source file' % name); continue
        data = open(src, 'rb').read()
        if build_disc.file_type(src) == 'mixed':
            nsec = (len(data) + 2335) // 2336
            ok = True
            for k in range(nsec):
                rec = data[k * 2336:(k + 1) * 2336].ljust(2336, b'\0')
                n_cmp = 2332 if rec[2] & 0x20 else 2056  # Form 2: up to its EDC; Form 1: up to EDC/ECC
                if img[(el + k) * RAW + 16:(el + k) * RAW + 16 + n_cmp] != rec[:n_cmp]:
                    ok = False
                    break
        else:
            got = b''.join(user(el + k) for k in range((sz + 2047) // 2048))[:sz]
            ok = sz == len(data) and got == data
        compared += 1
        if not ok:
            err('%s differs from %s' % (name, os.path.relpath(src, REPO)))
        if name.upper() == 'PSX.EXE' and data[:8] != b'PS-X EXE':
            err('PSX.EXE is not a PS-X EXE')
    missing = [f for f in src_files.values() if not build_disc.excluded(f) and
               f.replace(os.sep, '/').upper() not in {x[0].upper() for x in files}]
    for f in missing:
        err('%s is not on the disc' % f)
    print('%s: %d sectors (%.1f MB) | Form 1 %d (EDC + ECC, %d checked) | Form 2 %d with EDC, %d without' % (
        os.path.relpath(binp, REPO), n, len(img) / 1048576, forms[0], ecc_checked, forms[1], forms[2]))
    print('license: %s | files: %d on disc, %d compared with their sources' % (
        'none (emulators / modded consoles only)' if no_lic else
        ('sectors 0..15 = %s (%s)' % (os.path.basename(lic), ' '.join(lic_text)) if lic_ok else 'MISMATCH'),
        len(files), compared))
    for e in errors:
        print('ERROR:', e)
    print('OK' if not errors else 'FAILED (%d+ errors)' % len(errors))
    sys.exit(0 if not errors else 1)


if __name__ == '__main__':
    main()
