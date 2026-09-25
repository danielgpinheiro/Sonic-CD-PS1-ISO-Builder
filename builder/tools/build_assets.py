#!/usr/bin/python3
"""Build-time asset pipeline for the RSDKv3 (Sonic CD) PS1 port: game data -> the disc's Data/ tree.

Steps (golden rule: nothing is decoded at runtime; every converter checks its own output):
  1. data     tools/extract_rsdk.py Data.rsdk -> loose tree (or copy an extracted Data/ tree)
  2. manifest tools/rsdkmanifest (host build of the engine's bytecode VM) -> build/manifest/*.txt
  3. atlas    tools/atlas/build_atlas.py -> Data/Sprites/Atlas/<Stage>.atl (per-stage VRAM sprites)
  4. tiles    tools/tiles/convert_tiles.py -> Data/Stages/*/16x16Tiles.vram (VRAM tile pages)
  5. strips   tools/bgstrips/build_bgstrips.py -> Data/Stages/*/BGStrips[_t].bin (BG line strips, per player)
     floor    tools/floor/build_floor.py -> Data/Stages/SS*/Floor.vram (special stages' far floor)
  6. sfx      tools/audio/build_sfx.py -> Data/SoundFX/**/*.vag (SPU-ADPCM, one rate per file) +
              Data/Stages/Secrets/SFX/ (its own lower-rate copies), Data/Game/PS1SfxStages.bin
  7. music    tools/audio/build_music.py -> Data/Music/Music.xa + Music.bin (CD-XA, 68 tracks, 8 channels)
  8. video    tools/fmv/build_str.py videos/*.ogv -> Data/Videos/<Name>.str + .sti (MDEC STR, JP + US XA audio)
The PC source files stay in the tree (.gif .wav .ogg); tools/disc/build_disc.py leaves them off the
disc.

Output: OUT/build/iso/Data/** and OUT/build/manifest/ (OUT = the repo by default, so `make disc`
works on it). External tools, found on PATH or through these environment variables: PSXAVENC, FFMPEG,
FFPROBE, CXX (a C++17 compiler for tools/rsdkmanifest), make, MKPSXISO (with --disc-tools: the public
builder checks it here too). Python: Pillow + numpy. Missing tools are listed before anything runs.

Usage: build_assets.py (--rsdk PATH/Data.rsdk | --data PATH/Data) [--videos DIR] [--out DIR] [--lang en|jp]
"""
import argparse, importlib.util, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..'))
PY = sys.executable
# Stages whose sprites don't fit the VRAM sprite area (the build continues without their atlas). None
# since phase 4: the Secrets gallery streams its biggest pictures on demand (<Stage>.pic).
ATLAS_KNOWN_OVER = set()
LANG_IDS = {'en': 0, 'jp': 5}  # RetroEngine.hpp RetroLanguages
WORKSPACE_TOOLS = {  # the development workspace's builds, used when nothing else is configured
    'PSXAVENC': os.path.join(REPO, '..', 'psxavenc', 'build', 'psxavenc'),
    'MKPSXISO': os.path.join(REPO, '..', 'mkpsxiso-2.30-Darwin', 'bin', 'mkpsxiso'),
}


def find_tool(env, name):
    path = os.environ.get(env) or shutil.which(name)
    if not path and os.path.exists(WORKSPACE_TOOLS.get(env, '')):
        path = WORKSPACE_TOOLS[env]
    return path


def check_tools(need_disc=False):
    """The external tools (as environment variables for the converters); exits with a list if any is missing."""
    tools, missing = {}, []
    wanted = [('PSXAVENC', 'psxavenc'), ('FFMPEG', 'ffmpeg'), ('FFPROBE', 'ffprobe')]
    if need_disc:
        wanted.append(('MKPSXISO', 'mkpsxiso'))
    for env, name in wanted:
        p = find_tool(env, name)
        (tools.__setitem__(env, os.path.abspath(p)) if p else missing.append('%s (or set %s)' % (name, env)))
    cxx = os.environ.get('CXX') or shutil.which('clang++') or shutil.which('g++') or shutil.which('c++')
    (tools.__setitem__('CXX', cxx) if cxx else missing.append('a C++17 compiler: clang++ or g++ (or set CXX)'))
    if not shutil.which('make'):
        missing.append('make')
    for mod, pkg in (('PIL', 'Pillow'), ('numpy', 'numpy')):
        if importlib.util.find_spec(mod) is None:
            missing.append('Python package %s (pip install %s)' % (pkg, pkg))
    if missing:
        sys.exit('Missing tools:\n  ' + '\n  '.join(missing))
    return tools


def run(step, cmd, **kw):
    print('[%s] %s' % (step, ' '.join(os.path.relpath(c, REPO) if os.path.isabs(c) else c for c in cmd)), flush=True)
    return subprocess.run(cmd, check=kw.pop('check', True), **kw)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument('--rsdk', help="Sonic CD's Data.rsdk (Steam)")
    src.add_argument('--data', help='an already extracted Data/ directory')
    ap.add_argument('--out', default=REPO, help='output root (gets build/iso/Data and build/manifest)')
    ap.add_argument('--videos', help="Sonic CD's videos/*.ogv (default: videos/ next to Data.rsdk or Data/)")
    ap.add_argument('--lang', default='en', choices=('en', 'jp'),
                    help="the disc's language (one disc per language, docs/28 phase 4)")
    ap.add_argument('--disc-tools', action='store_true', help='also require mkpsxiso (the disc step that follows)')
    a = ap.parse_args()
    os.environ.update(check_tools(need_disc=a.disc_tools))  # the converters read PSXAVENC / FFMPEG / ... from here
    out = os.path.abspath(a.out)
    iso, manifest = os.path.join(out, 'build', 'iso'), os.path.join(out, 'build', 'manifest')
    for d in (iso, manifest):
        if os.path.exists(d):
            shutil.rmtree(d)
    os.makedirs(iso)

    if a.rsdk:
        run('1 data', [PY, os.path.join(HERE, 'extract_rsdk.py'), os.path.abspath(a.rsdk), iso])
    else:
        print('[1 data] copy %s' % a.data, flush=True)
        shutil.copytree(a.data, os.path.join(iso, 'Data'), ignore=shutil.ignore_patterns('.DS_Store'))
    data = os.path.join(iso, 'Data')
    # PS1 edits to the script bytecode (Help & Options without HOW TO PLAY / CONTROLS: docs/28).
    r = run('1 scripts', [PY, os.path.join(HERE, 'scripts', 'patch_bytecode.py'), data], capture_output=True, text=True)
    print('[1 scripts] ' + r.stdout.strip())

    cxx = os.environ['CXX']
    run('2 manifest', ['make', '-s', '-C', os.path.join(HERE, 'rsdkmanifest'), 'CXX=' + cxx])
    run('3 fonts', [PY, os.path.join(HERE, 'font', 'prescale_font.py'), data, '--lang', a.lang])
    # One manifest + atlas set per selectable player (docs/28 3.2: Sonic and Tails don't fit one atlas):
    # player list position 0 = Sonic -> <Stage>.atl, 1 = Tails -> <Stage>_t.atl (the act's placed
    # Player Object loads the player's .ani; ps1/sprite_atlas picks the file by playerListPos).
    for player, suffix in ((0, ''), (1, '_t')):
        mdir = manifest + suffix
        if os.path.exists(mdir):
            shutil.rmtree(mdir)
        run('2 manifest', [os.path.join(HERE, 'rsdkmanifest', 'rsdkmanifest'), iso, mdir, str(player)], stdout=subprocess.DEVNULL,
            env=dict(os.environ, RSDK_LANGUAGE=str(LANG_IDS[a.lang])))
        r = run('3 atlas', [PY, os.path.join(HERE, 'atlas', 'build_atlas.py'), data, mdir, '--suffix', suffix, '--lang', a.lang],
                check=False, capture_output=True, text=True)
        errors = [l for l in r.stdout.splitlines() if l.startswith('ERROR')]
        unexpected = [l for l in errors if l.split()[1].rstrip(':') not in ATLAS_KNOWN_OVER]  # 'ERROR <stage>: ...'
        atl = len([f for f in os.listdir(os.path.join(data, 'Sprites', 'Atlas')) if f.endswith(suffix + '.atl')
                   and (suffix or not f.endswith('_t.atl'))])
        pics = [l.split()[0] for l in r.stdout.splitlines() if 'on-demand pictures' in l]
        print('[3 atlas] player %d: %d %s.atl written; on-demand pictures: %s; known over budget: %s' % (
            player, atl, '<Stage>' + suffix, ', '.join(pics) or '-', ', '.join(sorted(ATLAS_KNOWN_OVER)) or '-'))
        if unexpected or (r.returncode and not errors):
            sys.exit('atlas failed:\n' + '\n'.join(unexpected or [r.stdout[-2000:], r.stderr[-2000:]]))

    run('4 tiles', [PY, os.path.join(HERE, 'tiles', 'convert_tiles.py'), data])
    # The exe reads the disc's language at boot (RetroEngine::Init on PS1): one byte, RETRO_EN / RETRO_JP.
    open(os.path.join(data, 'Game', 'PS1Language.bin'), 'wb').write(bytes([LANG_IDS[a.lang]]))
    print('[4 lang] Data/Game/PS1Language.bin = %s' % a.lang)
    r = run('5 bgstrips', [PY, os.path.join(HERE, 'bgstrips', 'build_bgstrips.py'), data], capture_output=True, text=True)
    print('[5 bgstrips] %d files (self-checked), per player' % sum(1 for l in r.stdout.splitlines() if ' regions ' in l and ' regions  0 ' not in l))
    r = run('5 floor', [PY, os.path.join(HERE, 'floor', 'build_floor.py'), data], capture_output=True, text=True)
    print('[5 floor] %d special stages: far-floor textures' % len(r.stdout.splitlines()))
    r = run('6 sfx', [PY, os.path.join(HERE, 'audio', 'build_sfx.py'), data], capture_output=True, text=True)
    print('[6 sfx] ' + ' '.join(l for l in r.stdout.splitlines() if l.startswith('sfx ')))
    r = run('7 music', [PY, os.path.join(HERE, 'audio', 'build_music.py'), data], capture_output=True, text=True)
    print('[7 music] ' + ' '.join(l for l in r.stdout.splitlines() if l.startswith('Music.xa')))
    videos = a.videos or os.path.join(os.path.dirname(os.path.abspath(a.rsdk or a.data.rstrip('/'))), 'videos')
    if os.path.isdir(videos):
        r = run('8 video', [PY, os.path.join(HERE, 'fmv', 'build_str.py'), videos, data], capture_output=True, text=True)
        for l in r.stdout.splitlines():
            print('[8 video] ' + l)
    else:
        print('[8 video] no videos folder (%s): the disc plays no FMV' % videos)
    print('assets ready in %s' % data)


if __name__ == '__main__':
    main()
