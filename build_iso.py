#!/usr/bin/env python3
"""Sonic CD PS1 ISO Builder: your Sonic CD (2011) Data.rsdk + videos -> a PlayStation disc image.

    python3 build_iso.py --data "/path/to/Sonic CD/Data.rsdk" [--lang en|jp] [--license licensea.dat] [--out output]

1. checks the tools (Python packages, psxavenc, ffmpeg/ffprobe, mkpsxiso, a C++17 compiler, make);
2. checks that Data.rsdk and the four videos are the Steam release (SHA-256), unless --force;
3. converts the game's assets for the PlayStation (builder/tools/build_assets.py);
4. lays the files out in the order the game loads them and builds the disc around the prebuilt
   executable (bin/SonicCD-PS1.exe) with mkpsxiso;
5. verifies the image byte by byte (EDC/ECC, license sectors, file index, every file);
6. writes output/SonicCD-PS1-EN.bin + .cue (or -JP) + SHA256SUMS-EN.

No game data is included in this repository: use your own copy of Sonic CD (see README.md).
"""
import argparse, hashlib, os, shutil, subprocess, sys, time

ROOT = os.path.dirname(os.path.abspath(__file__))
BUILDER = os.path.join(ROOT, 'builder')
EXE = os.path.join(ROOT, 'bin', 'SonicCD-PS1.exe')
# Sonic CD (2011), Steam release.
DATA_SHA256 = 'b4c226f0416f918e008c3cec78bb197dfedcc4c04328c7ec5da8ae3fcddf21e4'
VIDEO_SHA256 = {
    'Opening.ogv': 'e6e7e8b6b9dbb760e465f09f52b93f7592d4c52ad34ad75a670db3daf50d3cec',
    'Pencil_Test.ogv': 'cd904b41ebb32b58e3e11cfe7f3ffd8c390da5f31fe22f1c7ae9210768e8e9fe',
    'Good_Ending.ogv': '0716883d3b48de79bc8d3edf7f11cec6def254cec20bdcab3c5a1674da427e9a',
    'Bad_Ending.ogv': 'a00c913c75766ac9939be8624e4e10099905fed2f0f35cd8b398765a3783806f',
}

sys.path.insert(0, os.path.join(BUILDER, 'tools'))
import build_assets  # noqa: E402


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description='Build a Sonic CD PlayStation disc image from your own Data.rsdk and videos.')
    ap.add_argument('--data', required=True, help="Data.rsdk from your Sonic CD (2011) installation")
    ap.add_argument('--videos', help="the game's videos folder (Opening.ogv ...); default: videos/ next to Data.rsdk")
    ap.add_argument('--lang', default='en', choices=('en', 'jp'), help='the disc language (default en)')
    ap.add_argument('--license', help='optional Sony license file (e.g. licensea.dat, NTSC-U) for retail consoles')
    ap.add_argument('--out', default=os.path.join(ROOT, 'output'), help='output folder (default: output/)')
    ap.add_argument('--force', action='store_true', help='accept files that are not the Steam release')
    ap.add_argument('--keep-work', action='store_true', help='keep the intermediate files (output/work)')
    a = ap.parse_args()

    if sys.version_info < (3, 8):
        sys.exit('Python 3.8 or newer is required.')
    if not os.path.isfile(a.data):
        sys.exit('Data.rsdk not found: %s' % a.data)
    if a.license and not os.path.isfile(a.license):
        sys.exit('License file not found: %s' % a.license)
    tools = build_assets.check_tools(need_disc=True)

    wrong = []
    got = sha256(a.data)
    if got != DATA_SHA256:
        wrong.append('Data.rsdk (SHA-256 %s)' % got)
    videos = os.path.abspath(a.videos or os.path.join(os.path.dirname(os.path.abspath(a.data)), 'videos'))
    if os.path.isdir(videos):
        for name, want in VIDEO_SHA256.items():
            p = os.path.join(videos, name)
            if not os.path.isfile(p):
                wrong.append('%s missing from %s' % (name, videos))
            elif sha256(p) != want:
                wrong.append('%s (SHA-256 %s)' % (name, sha256(p)))
    else:
        print('WARNING: no videos folder at %s: the disc will have no videos (opening, endings, pencil test).' % videos)
    if wrong:
        msg = 'These files are not the Steam release of Sonic CD:\n  ' + '\n  '.join(wrong)
        if not a.force:
            sys.exit(msg + '\nUse the unmodified files from your installation, or pass --force to try anyway.')
        print('WARNING: ' + msg + '\nContinuing because of --force.')

    name = 'SonicCD-PS1-' + a.lang.upper()
    out = os.path.abspath(a.out)
    work = os.path.join(out, 'work')
    if os.path.exists(work):
        shutil.rmtree(work)
    os.makedirs(work)
    order = os.path.join(work, 'load_order.txt')
    env = dict(os.environ, PS1_LOAD_ORDER=order, **tools)
    py = sys.executable
    t0 = time.time()
    subprocess.run([py, os.path.join(BUILDER, 'tools', 'build_assets.py'), '--rsdk', os.path.abspath(a.data), '--videos', videos,
                    '--lang', a.lang, '--out', work, '--disc-tools'], env=env, check=True)
    iso = os.path.join(work, 'build', 'iso')
    subprocess.run([py, os.path.join(BUILDER, 'tools', 'disc', 'gen_load_order.py'), os.path.join(iso, 'Data'), order],
                   env=env, check=True)
    prefix = os.path.join(out, name)
    lic = os.path.abspath(a.license) if a.license else 'none'
    print('[disc] mkpsxiso', flush=True)
    subprocess.run([py, os.path.join(BUILDER, 'tools', 'disc', 'build_disc.py'), iso, EXE, lic, prefix], env=env, check=True)
    print('[verify]', flush=True)
    subprocess.run([py, os.path.join(BUILDER, 'tools', 'disc', 'verify_disc.py'), prefix + '.bin', iso, EXE, lic],
                   env=env, check=True)
    sums = os.path.join(out, 'SHA256SUMS-' + a.lang.upper())
    with open(sums, 'w') as f:
        for ext in ('.bin', '.cue'):
            f.write('%s  %s\n' % (sha256(prefix + ext), name + ext))
    if not a.keep_work:
        shutil.rmtree(work)
        shutil.rmtree(os.path.join(out, 'disc'), ignore_errors=True)
    print('\nDone in %d min: %s.cue / .bin%s' % ((time.time() - t0 + 59) // 60, prefix, '' if a.license else
                                                   '\n(no license file: plays in emulators, on ODEs and modded consoles)'))


if __name__ == '__main__':
    main()
