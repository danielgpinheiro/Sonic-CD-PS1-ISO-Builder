#!/usr/bin/env python3
"""Build-time SFX conversion for the RSDKv3 (Sonic CD) PS1 port (docs/28 phase 5.1):
Data/SoundFX/**/*.wav -> *.vag (SPU-ADPCM, psxavenc `-t vag`: 48-byte header with the rate at 0x10,
data padded to 64 bytes, ends with a silent loop-trap block). The PS1 LoadSfx maps `X.wav` to `X.vag`.

The engine loads the global SFX (GameConfig.bin) at boot and keep them; each stage adds its own
(StageConfig.bin) after them. Everything must fit the SPU RAM left for samples (0x1000 .. 0x80000 - 32:
capture buffers below, dummy block above). Sonic CD's 74 sources are 44.1 kHz mono 8-bit; the 27
global ones alone need 849 KB at that rate (phase 1), so one rate is chosen **per file**: every file
starts at its source rate (<= 44.1 kHz) and, while the global set + some stage's set is over budget,
the largest sample of that stage's sets (global or stage) steps down one rate (RATES); short, bright
sounds keep their rate. A file below RATES[-1] is an error. Each .vag is decoded back (header size,
rate, 64-byte padding) and the per-stage totals re-measured from the written files.

Outlier stages (the Secrets sound test loads 42 stage SFX, 917 KB at 44.1 kHz) would drag every shared
file down: stages whose stage set alone is over the whole budget don't take part in the shared rates.
Each gets its own lower-rate copies of its stage SFX, Data/Stages/<Stage>/SFX/<path, '/' -> '_'>.vag
(globals stay shared: they are resident), rated the same way with the globals fixed and two lower rates
allowed (OUTLIER_RATES). The shared rates keep room for it: each outlier stage takes part as a fixed
reserve, its set at 11,025 Hz, so the largest globals step down as far as that needs. It is listed in
Data/Game/PS1SfxStages.bin (u8 count, count x (u8 length, folder name)) for the engine's LoadSfx.

Usage: build_sfx.py DATA_DIR   (e.g. build/iso/Data; needs psxavenc)
"""
import os, struct, subprocess, sys, tempfile

PSXAVENC = os.environ.get('PSXAVENC') or os.path.join(os.path.dirname(__file__), '../../../psxavenc/build/psxavenc')
SPU_SAMPLE_START = 0x1000
SPU_SAMPLE_END = 0x80000 - 32
RATES = (44100, 37800, 32000, 27000, 22050, 18900, 16000, 13000, 11025)
OUTLIER_RATES = RATES + (9450, 8000)


def read_str(d, i):
    n = d[i]
    return d[i + 1:i + 1 + n].decode('latin1'), i + 1 + n


def global_sfx(data):
    """GameConfig.bin (RSDKv3 LoadGlobalSfx): title, data, description, objects (names + script paths),
    variables (name + u32), then the SFX paths."""
    d = open(os.path.join(data, 'Game', 'GameConfig.bin'), 'rb').read()
    i = 0
    for _ in range(3):
        _, i = read_str(d, i)
    n = d[i]; i += 1
    for _ in range(2 * n):
        _, i = read_str(d, i)
    n = d[i]; i += 1
    for _ in range(n):
        _, i = read_str(d, i)
        i += 4
    n = d[i]; i += 1
    names = []
    for _ in range(n):
        s, i = read_str(d, i)
        names.append(s)
    return names


def stage_sfx(path):
    """StageConfig.bin (RSDKv3 LoadStageFiles): load-globals byte, 32 palette colours, objects (names +
    script paths), then the SFX paths."""
    d = open(path, 'rb').read()
    i = 1 + 32 * 3
    n = d[i]; i += 1
    for _ in range(2 * n):
        _, i = read_str(d, i)
    n = d[i]; i += 1
    names = []
    for _ in range(n):
        s, i = read_str(d, i)
        names.append(s)
    return names


def wav_bytes(path):
    d = open(path, 'rb').read()
    return d if d[:4] == b'RIFF' else bytes(b ^ 0xFF for b in d)


def wav_info(d):
    """(frames, rate) by a minimal RIFF walk."""
    i, align, size, rate = 12, 1, 0, 44100
    while i + 8 <= len(d):
        cid, cs = d[i:i + 4], struct.unpack_from('<I', d, i + 4)[0]
        if cid == b'fmt ':
            rate = struct.unpack_from('<I', d, i + 12)[0]
            align = struct.unpack_from('<H', d, i + 20)[0]
        elif cid == b'data':
            size = cs
        i += 8 + cs + (cs & 1)
    return size // align, rate


def vag_size(frames, src_rate, rate):
    samples = -(-frames * rate // src_rate)
    blocks = -(-samples // 28) + 2  # + leading dummy block + trailing loop-trap block
    return -(-blocks * 16 // 64) * 64


def choose_rates(groups, info, budget, rate=None, fixed=(), rates=RATES, reserve=None):
    """Per-file rate index into RATES (see the module doc); files in `fixed` keep their rate; `reserve`:
    {group: bytes} added to that group's total (outlier stages in the shared solve, their names empty)."""
    reserve = reserve or {}
    if rate is None:
        rate = {n: next(k for k, r in enumerate(rates) if r <= info[n][1]) for n in info}
    rate = dict(rate)

    def size(n):
        return vag_size(info[n][0], info[n][1], rates[rate[n]])

    while True:
        over = None
        for k, names in groups.items():
            if k == 'global':
                continue
            total = sum(size(n) for n in groups['global'] + names) + reserve.get(k, 0)
            if total > budget and (over is None or total > over[0]):
                over = (total, k)
        if over is None:
            return rate
        cand = [n for n in set(groups['global'] + groups[over[1]]) if rate[n] + 1 < len(rates) and n not in fixed]
        if not cand:
            sys.exit('ERROR: %s does not fit SPU RAM even at %d Hz' % (over[1], rates[-1]))
        n = max(cand, key=lambda n: (size(n), n))
        rate[n] += 1


def encode(src_wav, out, r, tmp):
    wav = os.path.join(tmp, 'in.wav')
    open(wav, 'wb').write(wav_bytes(src_wav))
    subprocess.run([PSXAVENC, '-q', '-t', 'vag', '-f', str(r), wav, out], check=True)
    v = open(out, 'rb').read()
    assert v[:4] == b'VAGp', out
    size = struct.unpack_from('>I', v, 12)[0]
    vrate = struct.unpack_from('>I', v, 16)[0]
    assert vrate == r and len(v) - 48 >= size and (len(v) - 48) % 64 == 0, out
    return len(v) - 48


def main():
    data = sys.argv[1]
    sfx_root = os.path.join(data, 'SoundFX')
    groups = {'global': global_sfx(data)}
    for st in sorted(os.listdir(os.path.join(data, 'Stages'))):
        p = os.path.join(data, 'Stages', st, 'StageConfig.bin')
        if os.path.exists(p):
            groups[st] = stage_sfx(p)
    info = {}
    for names in groups.values():
        for n in names:
            if n not in info:
                info[n] = wav_info(wav_bytes(os.path.join(sfx_root, n)))
    budget = SPU_SAMPLE_END - SPU_SAMPLE_START
    full = lambda names: sum(vag_size(info[n][0], info[n][1], 44100) for n in names)
    outliers = sorted(k for k, names in groups.items() if k != 'global' and full(names) > budget)
    shared = {k: v for k, v in groups.items() if k not in outliers}
    shared.update({k: [] for k in outliers})
    rate = choose_rates(shared, info, budget,
                        reserve={k: sum(vag_size(info[n][0], info[n][1], 11025) for n in groups[k]) for k in outliers})
    total = {}
    own = {}  # outlier stage -> {name: bytes}
    with tempfile.TemporaryDirectory() as tmp:
        for n in sorted(info):
            src = os.path.join(sfx_root, n)
            total[n] = encode(src, os.path.splitext(src)[0] + '.vag', RATES[rate[n]], tmp)
        for st in outliers:
            srate = choose_rates({'global': groups['global'], st: groups[st]}, info, budget, rate, fixed=set(groups['global']),
                                 rates=OUTLIER_RATES)
            d = os.path.join(data, 'Stages', st, 'SFX')
            os.makedirs(d, exist_ok=True)
            own[st] = {}
            for n in sorted(set(groups[st])):
                out = os.path.join(d, os.path.splitext(n.replace('/', '_'))[0] + '.vag')
                own[st][n] = encode(os.path.join(sfx_root, n), out, OUTLIER_RATES[srate[n]], tmp)
            print('  %s: own copies of its %d stage sfx, %d B + global %d B of %d B' % (
                st, len(own[st]), sum(own[st][n] for n in groups[st]), sum(total[n] for n in groups['global']), budget))
            assert sum(own[st][n] for n in groups[st]) + sum(total[n] for n in groups['global']) <= budget, st
    tab = bytes([len(outliers)]) + b''.join(bytes([len(st)]) + st.encode() for st in outliers)
    open(os.path.join(data, 'Game', 'PS1SfxStages.bin'), 'wb').write(tab)
    worst = max((sum(total[n] for n in groups['global'] + names), k) for k, names in shared.items() if k != 'global' and k not in outliers)
    assert worst[0] <= budget, worst
    hist = {}
    for n in info:
        hist[RATES[rate[n]]] = hist.get(RATES[rate[n]], 0) + 1
    print('sfx %d files | rates %s | global %d B | global + largest stage (%s) %d of %d B | own copies: %s' % (
        len(info), ', '.join('%d Hz x%d' % (r, hist[r]) for r in sorted(hist, reverse=True)),
        sum(total[n] for n in groups['global']), worst[1], worst[0], budget, ', '.join(outliers) or '-'))
    for n in sorted(info, key=lambda n: -total[n])[:8]:
        print('  %-40s %6d Hz %7d B' % (n, RATES[rate[n]], total[n]))


if __name__ == '__main__':
    main()
