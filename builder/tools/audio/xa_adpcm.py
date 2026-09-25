"""XA-ADPCM decoder (psx-spx "CDROM XA Audio ADPCM Compression"), 4-bit stereo/mono, for checks."""
import numpy as np

POS = (0, 60, 115, 98)
NEG = (0, 0, -52, -55)


def decode_sectors(sectors, stereo=True):
    """sectors: iterable of 2336-byte XA sectors (8-byte subheader first). Returns (L, R) arrays."""
    out = ([], [])
    hist = [[0, 0], [0, 0]]
    for sec in sectors:
        data = sec[8:8 + 18 * 128]
        for g in range(18):
            grp = data[g * 128:(g + 1) * 128]
            for blk in range(8):
                ch = blk & 1 if stereo else 0
                param = grp[4 + blk]
                shift, flt = param & 0x0F, min((param >> 4) & 3, 3)
                o1, o2 = hist[ch]
                for i in range(28):
                    word = grp[16 + i * 4:16 + i * 4 + 4]
                    nib = (word[blk // 2] >> ((blk & 1) * 4)) & 0xF
                    if nib >= 8:
                        nib -= 16
                    s = ((nib << 12) >> shift) + ((o1 * POS[flt] + o2 * NEG[flt] + 32) >> 6)
                    s = max(-32768, min(32767, s))
                    out[ch].append(s)
                    o2, o1 = o1, s
                hist[ch] = [o1, o2]
    return np.array(out[0], dtype=float), np.array(out[1], dtype=float)


def channel_sectors(xa_bytes, channel, interleave=8):
    n = len(xa_bytes) // 2336
    for i in range(channel, n, interleave):
        s = xa_bytes[i * 2336:(i + 1) * 2336]
        if s[1] == channel and s[2] & 0x04:
            yield s


def clear_unused(buf):
    """Zero what the drive never delivers in 2336-byte Mode 2 records (sub-header + payload):
    Form 2: the 20 bytes after the 18 x 128-byte sound groups (psx-spx: unused, zero) and the EDC;
    Form 1: the EDC/ECC area. psxavenc leaves uninitialised memory there, which makes builds
    irreproducible; mkpsxiso recomputes EDC/ECC on the disc anyway."""
    b = bytearray(buf)
    for k in range(0, len(b), 2336):
        tail = 8 + 2304 if b[k + 2] & 0x20 else 8 + 2048
        b[k + tail:k + 2336] = bytes(2336 - tail)
    return b
