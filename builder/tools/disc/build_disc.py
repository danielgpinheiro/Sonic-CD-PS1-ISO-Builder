#!/usr/bin/env python3
"""Build the PS1 disc image with mkpsxiso (phase 5): build/game.bin + build/game.cue.

A MODE2/2352 BIN/CUE is needed for CD-XA music and STR files with XA audio (2336-byte mixed
sectors, which an hdiutil ISO can't carry). The image boots through the BIOS too:
SYSTEM.CNF (BOOT = cdrom:\\PSX.EXE;1) + PSX.EXE (the current rsdkv3.ps-exe) + the Sony
license sectors, taken from the workspace's LICENSE.DAT (never copied into the repo; build/ is
git-ignored).

Tree: every file under ISO_ROOT (build/iso: Data/**), macOS metadata skipped. `.xa` files and
`.str` files whose size is a whole number of 2336-byte sectors are `type="mixed"`; everything
else is data (Form 1, read by ps1/cdrom_fs.cpp as 2048-byte sectors).

Trim: the PC source assets the pipeline converts never go on the disc — SOURCE_ONLY extensions
(.gif sheets/tiles -> atlas/.vram, .wav -> .vag, .ogg -> CD-XA). Per game: Sonic CD reads .txt
files at runtime (help pages, credits) and ships scripts as bytecode, so .txt stays (Nexus
excluded .txt and .raw). On PS1, LoadGIFFile returns before opening anything and the script
compiler is compiled out (RETRO_USE_COMPILER 0). The build fails if tools/disc/load_order.txt (what
the game opens) lists an excluded file. tools/disc/verify_disc.py checks the image afterwards.

Layout (load-time phase): mkpsxiso gives files their LBAs in XML order across the whole tree (a
repeated <dir> reopens the same directory; directory records stay sorted by name). Data files are
laid out in the order the game loads them (tools/disc/load_order.txt, from
tools/load_profile.sh natural --order), then the other data files by path, then the streams, so
cdrom_fs's read-ahead windows usually already hold the next file the game opens.

File index (load-time phase): PS1FILES.IDX at the root lists every file of the tree (FNV-1a 32 hash of
its lowercase path, LBA, size; sorted by hash), so ps1/cdrom_fs.cpp opens files without reading
directory sectors (each directory miss cost a seek and stopped the load stream). The LBAs are only
known after mastering: mkpsxiso runs with a zero-filled index of the final size, the image is walked,
the index is written, and mkpsxiso runs again (same sizes and order = same layout; checked by walking
the second image and reading the index back).

Usage: build_disc.py [ISO_ROOT] [EXE] [LICENSE|none] [OUT_PREFIX]
  LICENSE none = no license data (the disc boots in emulators, on ODEs and modded consoles only)
  defaults: build/iso rsdkv3.ps-exe ../LICENSE.DAT build/game
"""
import os, struct, subprocess, sys
from xml.sax.saxutils import quoteattr

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
MKPSXISO = os.environ.get('MKPSXISO') or os.path.join(REPO, '..', 'mkpsxiso-2.30-Darwin', 'bin', 'mkpsxiso')

SYSTEM_CNF = 'BOOT = cdrom:\\PSX.EXE;1\r\nTCB = 4\r\nEVENT = 10\r\nSTACK = 801FFFF0\r\n'


def file_type(path):
    ext = os.path.splitext(path)[1].lower()
    size = os.path.getsize(path)
    if ext == '.xa' or (ext == '.str' and size % 2336 == 0 and size % 2048 != 0):
        return 'mixed'
    return 'data'


ORDER = os.environ.get('PS1_LOAD_ORDER') or os.path.join(HERE, 'load_order.txt')  # the public builder: its work folder
SOURCE_ONLY = ('.gif', '.wav', '.ogg')
# Fixed timestamps (volume + every entry): the image depends only on its contents, so identical
# inputs give a byte-identical disc (published SHA-256s can be checked).
DISC_DATE = '20260924000000'


def excluded(rel):
    return os.path.splitext(rel)[1].lower() in SOURCE_ONLY


def disc_files(iso_root):
    out = []
    for d, dirs, names in os.walk(iso_root):
        dirs[:] = sorted(x for x in dirs if not x.startswith('.'))
        out += [os.path.relpath(os.path.join(d, n), iso_root) for n in sorted(names) if not n.startswith('.')]
    return sorted(f for f in out if os.sep in f)  # root files: only SYSTEM.CNF + PSX.EXE (added by main)


def layout(iso_root):
    """Data files in load order, then the remaining data files, then the streams."""
    files = [f for f in disc_files(iso_root) if not excluded(f)]
    by_lower = {f.lower(): f for f in files}
    ordered = []
    if os.path.exists(ORDER):
        for line in open(ORDER):
            line = line.strip()
            f = by_lower.get(line.lower())
            if line and not line.startswith('#') and excluded(line):
                sys.exit('ERROR: the game opens %s, a source-only type left off the disc' % line)
            if line and not line.startswith('#') and f and f not in ordered:
                ordered.append(f)
    rest = [f for f in files if f not in ordered]
    data = [f for f in ordered + rest if file_type(os.path.join(iso_root, f)) == 'data']
    return data + [f for f in ordered + rest if f not in data], len(ordered)


IDX_NAME = 'PS1FILES.IDX'


def path_hash(path):
    """FNV-1a 32 of the lowercase '/'-separated path (ps1/cdrom_fs.cpp pathHash)."""
    h = 0x811C9DC5
    for c in path.replace(os.sep, '/').lower().encode('latin1'):
        h = ((h ^ c) * 0x01000193) & 0xFFFFFFFF
    return h


def iso_walk(binp):
    """(path, lba, size) of every file in a MODE2/2352 image (directory sectors only are read)."""
    f = open(binp, 'rb')

    def user(lba):
        f.seek(lba * 2352 + 24)
        return f.read(2048)
    out = []

    def walk(lba, size, prefix):
        for k in range((size + 2047) // 2048):
            d, o = user(lba + k), 0
            while o < 2048 and d[o]:
                el, sz = struct.unpack_from('<I', d, o + 2)[0], struct.unpack_from('<I', d, o + 10)[0]
                nm = d[o + 33:o + 33 + d[o + 32]]
                if nm not in (b'\0', b'\1'):
                    name = prefix + nm.decode('latin1').split(';')[0]
                    if d[o + 25] & 2:
                        walk(el, sz, name + '/')
                    else:
                        out.append((name, el, sz))
                o += d[o]
    pvd = user(16)
    walk(struct.unpack_from('<I', pvd, 158)[0], struct.unpack_from('<I', pvd, 166)[0], '')
    return out, user


def index_bytes(entries):
    """'FIX1', u32 count, 8 zero bytes, then {u32 hash, u32 lba, u32 size} sorted by hash."""
    rows = sorted((path_hash(n), lba, sz) for n, lba, sz in entries)
    hashes = [r[0] for r in rows]
    if len(set(hashes)) != len(hashes):
        sys.exit('ERROR: file index hash collision')
    return struct.pack('<4sIII', b'FIX1', len(rows), 0, 0) + b''.join(struct.pack('<III', *r) for r in rows)


def master(xml_path, binp, lic):
    """mkpsxiso, then (no license file) sectors 0..15 cleared: mkpsxiso leaves the Form 2 user data of the
    empty license area uninitialised, so two runs differed there (a reproducible image needs zeros; EDC 0 =
    none, as psx-spx allows for Form 2)."""
    subprocess.run([MKPSXISO, '-y', '-q', '-w', xml_path], check=True)
    if lic:
        return
    with open(binp, 'r+b') as f:
        for lba in range(16):
            f.seek(lba * 2352 + 18)
            if f.read(1)[0] & 0x20:  # Form 2
                f.seek(lba * 2352 + 24)
                f.write(bytes(2352 - 24))


def emit_file(rel, iso_root, out, counts):
    parts = rel.split(os.sep)
    full = os.path.join(iso_root, rel)
    t = file_type(full)
    counts[t] = counts.get(t, 0) + 1
    line = '<file name=%s type="%s" source=%s date="%s"/>' % (quoteattr(parts[-1]), t, quoteattr(full), DISC_DATE)
    for d in reversed(parts[:-1]):
        line = '<dir name=%s date="%s">%s</dir>' % (quoteattr(d), DISC_DATE, line)
    out.append('\t\t\t' + line)


def main():
    args = sys.argv[1:]
    iso_root = os.path.abspath(args[0] if len(args) > 0 else os.path.join(REPO, 'build', 'iso'))
    exe = os.path.abspath(args[1] if len(args) > 1 else os.path.join(REPO, 'rsdkv3.ps-exe'))
    lic = args[2] if len(args) > 2 else os.path.join(REPO, '..', 'LICENSE.DAT')
    lic = None if lic.lower() == 'none' else os.path.abspath(lic)  # none: blank license sectors
    out = os.path.abspath(args[3] if len(args) > 3 else os.path.join(REPO, 'build', 'game'))
    work = os.path.join(os.path.dirname(out), 'disc')
    os.makedirs(work, exist_ok=True)
    cnf = os.path.join(work, 'SYSTEM.CNF')
    open(cnf, 'w', newline='').write(SYSTEM_CNF)
    if lic and not os.path.exists(lic):
        sys.exit('ERROR: license file %s not found' % lic)

    counts = {}
    tree = []
    tree.append('\t\t\t<file name="SYSTEM.CNF" source=%s date="%s"/>' % (quoteattr(cnf), DISC_DATE))
    tree.append('\t\t\t<file name="PSX.EXE" source=%s date="%s"/>' % (quoteattr(exe), DISC_DATE))
    files, n_ordered = layout(iso_root)
    idx = os.path.join(work, IDX_NAME)
    open(idx, 'wb').write(bytes(16 + 12 * len(files)))  # placeholder: final size, LBAs after mastering
    tree.append('\t\t\t<file name="%s" source=%s date="%s"/>' % (IDX_NAME, quoteattr(idx), DISC_DATE))
    left_out = [f for f in disc_files(iso_root) if excluded(f)]
    left_bytes = sum(os.path.getsize(os.path.join(iso_root, f)) for f in left_out)
    for rel in files:
        emit_file(rel, iso_root, tree, counts)
    xml = '\n'.join([
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<iso_project image_name=%s cue_sheet=%s>' % (quoteattr(out + '.bin'), quoteattr(out + '.cue')),
        '\t<track type="data">',
        '\t\t<identifiers system="PLAYSTATION" application="PLAYSTATION" volume="RSDKV3PS1" volume_set="RSDKV3PS1"'
        ' publisher="RSDKV3PS1" data_preparer="MKPSXISO" creation_date="%s00" modification_date="%s00"/>' % (
            DISC_DATE, DISC_DATE),
    ] + (['\t\t<license file=%s/>' % quoteattr(lic)] if lic else []) + [
        '\t\t<directory_tree>',
    ] + tree + [
        '\t\t</directory_tree>',
        '\t</track>',
        '</iso_project>',
        '',
    ])
    xml_path = os.path.join(work, 'disc.xml')
    open(xml_path, 'w').write(xml)
    master(xml_path, out + '.bin', lic)
    entries = [e for e in iso_walk(out + '.bin')[0] if '/' in e[0]]
    if len(entries) != len(files):
        sys.exit('ERROR: %d files in the image, %d laid out' % (len(entries), len(files)))
    table = index_bytes(entries)
    open(idx, 'wb').write(table)
    master(xml_path, out + '.bin', lic)
    again, user = iso_walk(out + '.bin')
    if sorted(e for e in again if '/' in e[0]) != sorted(entries):
        sys.exit('ERROR: the layout changed between the two mastering passes')
    ie = [e for e in again if e[0] == IDX_NAME][0]
    if b''.join(user(ie[1] + k) for k in range((ie[2] + 2047) // 2048))[:ie[2]] != table:
        sys.exit('ERROR: %s on the disc differs from the table' % IDX_NAME)
    size = os.path.getsize(out + '.bin')
    print('disc %s.bin/.cue: %.1f MB (%d sectors) | files: %s (%d in load order, indexed) | left out %d source files '
          '(%.1f MB) | license %s' % (
        out, size / 1048576, size // 2352, ', '.join('%s %d' % kv for kv in sorted(counts.items())), n_ordered,
        len(left_out), left_bytes / 1048576, os.path.basename(lic) if lic else 'none (emulators / modded consoles only)'))


if __name__ == '__main__':
    main()
