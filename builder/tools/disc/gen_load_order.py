#!/usr/bin/python3
"""Disc load order for Sonic CD (docs/28 phase 9): tools/disc/load_order.txt, which build_disc.py lays out first.

Every psyqo CD request costs a seek (~0.2 s in PCSX-Redux) on top of 6.7 ms per sector at 2x, so a load's
time is its request count; the read-ahead windows (ps1/cdrom_fs, fed by the load stream) serve several small files per
request when they sit back to back. The Nexus port recorded one playthrough's opens; Sonic CD has 85 stages,
so this order is derived from the data instead, following what the engine opens (profiled on R11A:
tools/load_profile.sh):
  boot   : PS1Language.bin, GS000.bin, GameConfig.bin, Music.bin, PS1SfxStages.bin, the global SFX (.vag, in
           GameConfig order), MasterPalette.act, the player animations;
  stages : in stage-list order (presentation, regular, special), each stage's files together: StageConfig,
           its bytecode (<P|R|S|B>S<nnn>.bin), its SFX (.vag / Secrets' own copies), 16x16Tiles.vram,
           Floor.vram, <Stage>.atl / .pic, BGStrips.bin, CollisionMasks.bin, Backgrounds.bin,
           128x128Tiles.bin, the act layout, then Tails' atlas and strips (_t);
  then   : the remaining small data (palettes, text, fonts...) in path order.
A file shared by several stages sits at its first use. Paths only (no game data). Regenerate after changing
what the game loads.

Usage: gen_load_order.py DATA_DIR [OUT=tools/disc/load_order.txt]
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def rstr(b, i):
    n = b[i]
    return b[i + 1:i + 1 + n].decode('latin1'), i + 1 + n


def game_config(data):
    b = open(os.path.join(data, 'Game', 'GameConfig.bin'), 'rb').read()
    i = 0
    for _ in range(3):
        _, i = rstr(b, i)
    n = b[i]; i += 1
    for _ in range(2 * n):
        _, i = rstr(b, i)
    n = b[i]; i += 1
    for _ in range(n):
        _, i = rstr(b, i)
        i += 4
    n = b[i]; i += 1
    sfx = []
    for _ in range(n):
        s, i = rstr(b, i)
        sfx.append(s)
    n = b[i]; i += 1
    players = []
    for _ in range(n):
        s, i = rstr(b, i)
        players.append(s)
    lists = [[], [], [], []]
    for c in range(4):
        cat = {2: 3, 3: 2}.get(c, c)  # file order P, R, S, B -> engine lists P, R, B, S (LoadGameConfig)
        n = b[i]; i += 1
        for _ in range(n):
            folder, i = rstr(b, i)
            act, i = rstr(b, i)
            _, i = rstr(b, i)
            i += 1
            lists[cat].append((folder, act))
    return sfx, players, lists


def stage_config(data, folder):
    b = open(os.path.join(data, 'Stages', folder, 'StageConfig.bin'), 'rb').read()
    globals_ = b[0]
    i = 1 + 32 * 3
    n = b[i]; i += 1
    for _ in range(2 * n):
        _, i = rstr(b, i)
    n = b[i]; i += 1
    sfx = []
    for _ in range(n):
        s, i = rstr(b, i)
        sfx.append(s)
    return globals_, sfx


def main():
    data = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, 'load_order.txt')
    have = set()
    for d, _, names in os.walk(data):
        for n in names:
            have.add(os.path.relpath(os.path.join(d, n), os.path.dirname(data)).replace(os.sep, '/'))
    order = []

    def add(p):
        if p in have and p not in order:
            order.append(p)

    def vag(s):
        return 'Data/SoundFX/' + os.path.splitext(s)[0] + '.vag'
    sfx, players, lists = game_config(data)
    for p in ('Data/Game/PS1Language.bin', 'Data/Scripts/ByteCode/GS000.bin', 'Data/Game/GameConfig.bin', 'Data/Music/Music.bin',
              'Data/Game/PS1SfxStages.bin'):
        add(p)
    for s in sfx:
        add(vag(s))
    add('Data/Palettes/MasterPalette.act')
    for p in sorted(have):
        if p.startswith('Data/Animations/'):
            add(p)
    copies = open(os.path.join(data, 'Game', 'PS1SfxStages.bin'), 'rb').read() if 'Data/Game/PS1SfxStages.bin' in have else b'\0'
    own = set()
    i = 1
    for _ in range(copies[0]):
        own.add(copies[i + 1:i + 1 + copies[i]].decode())
        i += 1 + copies[i]
    for lst, stages in enumerate(lists):
        for pos, (folder, act) in enumerate(stages):
            s = 'Data/Stages/%s/' % folder
            if s + 'StageConfig.bin' not in have:
                continue
            add(s + 'StageConfig.bin')
            add('Data/Scripts/ByteCode/%sS%03d.bin' % ('PRBS'[lst], pos))
            _, ssfx = stage_config(data, folder)
            for x in ssfx:
                add(s + 'SFX/' + os.path.splitext(x.replace('/', '_'))[0] + '.vag' if folder in own else vag(x))
            for f in ('16x16Tiles.vram', 'Floor.vram'):
                add(s + f)
            for f in ('%s.atl', '%s.pic'):
                add('Data/Sprites/Atlas/' + f % folder)
            for f in ('BGStrips.bin', 'CollisionMasks.bin', 'Backgrounds.bin', '128x128Tiles.bin', 'Act%s.bin' % act):
                add(s + f)
            for f in ('%s_t.atl', '%s_t.pic'):  # Tails' files after Sonic's: a Sonic load reads the group front to back
                add('Data/Sprites/Atlas/' + f % folder)
            add(s + 'BGStrips_t.bin')
    for p in sorted(have):  # the rest of the small data, after the stages
        if p.lower().endswith(('.act', '.bin', '.txt', '.ani', '.vag')) and not p.startswith('Data/Music/'):
            add(p)
    with open(out_path, 'w') as f:
        f.write('# Disc files in the order the game loads them (tools/disc/gen_load_order.py, docs/28 phase 9).\n'
                '# tools/disc/build_disc.py lays these out first, in this order; then the other data files; CD-XA /\n'
                '# STR streams last. Regenerated by tools/data_disc.sh.\n')
        f.write('\n'.join(order) + '\n')
    print('load order: %d files -> %s' % (len(order), os.path.relpath(out_path)))


if __name__ == '__main__':
    main()
