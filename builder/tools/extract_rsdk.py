#!/usr/bin/env python3
"""Extract a Sonic CD (Retro Engine v3) Data.rsdk into a loose Data/ tree (build time).

Format, from RSDKv3/Reader.cpp (ParseVirtualFileSystem, FileRead):
  u32 headerSize, u16 dirCount,
  dirCount x { u8 len, name[len] (each byte XOR (~len & 0xFF)), u32 offset }   e.g. "Data/Game/"
  at headerSize + offset, the dir's files until the next dir: { u8 len, name[len] (each byte
  inverted), u32 size, data[size] }.
File data is XOR-encrypted as a stream that starts at each file's first byte, keyed by its size:
  no = (size & 0x1FC) >> 2, posB = no % 9 + 1, posA = no % posB + 1, swap = 0
  per byte: b ^= B[posB++] ^ no; if swap: b = nybble-swapped b; b ^= A[posA++]; then
  while one of posA <= 19 / posB <= 11 holds, each overflow resets that pos to 1 and toggles
  swap; once both overflow: no = (no + 1) & 0x7F and the positions restart from no
  (A = "4RaS9D7KaEbxcp2o5r6t", B = "3tRaUxLmEaSn").
The keystream depends only on the size, so it is generated once per starting key and applied with
numpy.

Usage: extract_rsdk.py DATA.rsdk OUT_DIR   (writes OUT_DIR/Data/...)
"""
import os, struct, sys
import numpy as np

KEY_A = b'4RaS9D7KaEbxcp2o5r6t'
KEY_B = b'3tRaUxLmEaSn'
_streams = {}  # starting key -> (xorB, swap, xorA) arrays, extended on demand


def keystream(no0, n):
    s = _streams.get(no0)
    if s is None or len(s[0]) < n:
        m = max(n, 1 << 16)
        xb, sw, xa = np.empty(m, np.uint8), np.empty(m, np.bool_), np.empty(m, np.uint8)
        no = no0
        pb = no % 9 + 1
        pa = no % pb + 1
        swap = False
        for i in range(m):
            xb[i] = KEY_B[pb] ^ no
            sw[i] = swap
            xa[i] = KEY_A[pa]
            pa += 1
            pb += 1
            if pa <= 19 or pb <= 11:
                if pa > 19:
                    pa = 1
                    swap = not swap
                if pb > 11:
                    pb = 1
                    swap = not swap
            else:
                no = (no + 1) & 0x7F
                if swap:
                    swap = False
                    pa = no % 12 + 6
                    pb = no % 5 + 4
                else:
                    swap = True
                    pa = no % 15 + 3
                    pb = no % 7 + 1
        s = _streams[no0] = (xb, sw, xa)
    return s[0][:n], s[1][:n], s[2][:n]


def decrypt(data):
    n = len(data)
    xb, sw, xa = keystream((n & 0x1FC) >> 2, n)
    b = np.frombuffer(data, np.uint8) ^ xb
    b = np.where(sw, ((b & 0x0F) << 4) | (b >> 4), b).astype(np.uint8)
    return (b ^ xa).tobytes()


def read_name(d, p, inv):
    n = d[p]
    raw = d[p + 1:p + 1 + n]
    name = bytes((c ^ inv(n)) & 0xFF for c in raw).decode('latin1')
    return name, p + 1 + n


def entries(d):
    header, dirs = struct.unpack_from('<IH', d, 0)
    p, dl = 6, []
    for _ in range(dirs):
        name, p = read_name(d, p, lambda n: ~n)
        off, = struct.unpack_from('<I', d, p)
        p += 4
        dl.append((name, off))
    for i, (dname, off) in enumerate(dl):
        p = header + off
        end = header + dl[i + 1][1] if i + 1 < len(dl) else len(d)
        while p < end:
            fname, p = read_name(d, p, lambda n: 0xFF)
            size, = struct.unpack_from('<I', d, p)
            p += 4
            yield dname + fname, d[p:p + size]
            p += size


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    d = open(sys.argv[1], 'rb').read()
    out = sys.argv[2]
    count = total = 0
    for path, data in entries(d):
        dst = os.path.join(out, path)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, 'wb') as f:
            f.write(decrypt(data))
        count += 1
        total += len(data)
    print('extracted %d files, %d bytes -> %s' % (count, total, os.path.join(out, 'Data')))


if __name__ == '__main__':
    main()
