# Sonic CD PS1 ISO Builder

Build a PlayStation 1 disc image of **Sonic CD** (the 2011 remaster, running on the Retro Engine v3)
from your own copy of the game. The PS1 executable is prebuilt; this repository contains the tools that
convert the game's data for the PlayStation and put the disc together.

**No game data is included.** You need your own copy of Sonic CD (Steam), see [Usage](#usage).

## What does this do / why is it needed?

The PlayStation has 2 MB of RAM, 1 MB of video RAM, 512 KB of sound RAM, no floating point and a 2×
CD-ROM drive. The PC version of Sonic CD decodes GIFs, Ogg music and Theora video while it runs; the PS1
can't afford that. So everything is converted **once, on your computer**, into formats the PS1 hardware
uses directly:

- **Sprites** → one texture atlas per stage and player (4/8-bit VRAM pages + palettes), checked pixel-exact;
  the Secrets gallery's big pictures are loaded on demand.
- **Tiles and parallax backgrounds** → pre-packed VRAM tile pages and pre-rendered background line strips.
- **Special stages** → a low-resolution far-floor texture for the 3D floor (the near floor is drawn from
  the tiles, projected by the PS1's geometry coprocessor).
- **Text** → the menu and help fonts pre-scaled and antialiased, English or Japanese.
- **Sound effects** → SPU-ADPCM, one sample rate per file so every stage's set fits the sound RAM.
- **Music** → CD-XA audio for **both soundtracks** (US and JP), streamed and decoded by the CD drive, with
  the PC version's loop points.
- **Videos** → MDEC video (STR) with both soundtracks interleaved as CD-XA.
- **Scripts** → the game's own bytecode, with a few PS1 edits (below).
- **Disc layout** → files placed in the order the game loads them, a file index so opening a file needs no
  directory reads, source files left off.

## Usage

1. Find your Sonic CD installation. On Steam: *Library → Sonic CD → Manage → Browse local files*.
   You need `Data.rsdk` and the `videos` folder next to it (unmodified; the builder checks their SHA-256
   against the Steam release). Sonic CD on Steam is a Windows game: copy these files to the computer
   that runs the builder if needed.
2. Install the [requirements](#requirements).
3. Run:
   ```bash
   python3 build_iso.py --data "/path/to/Sonic CD/Data.rsdk"
   ```
   Options:
   - `--lang jp`: a Japanese disc (default: `en`, English). The executable is the same; each disc
     carries one language.
   - `--videos folder`: if the videos aren't in `videos/` next to `Data.rsdk`. Without videos the disc
     is built without them (a warning is shown).
   - `--license licensea.dat` (see [The license file](#the-license-file)), `--out folder`,
     `--keep-work`, `--force` (accept files that aren't the Steam release).
4. The disc image is in `output/` after about 6 minutes on a recent Mac (most of it encoding the music and videos).

## Output

- `output/SonicCD-PS1-EN.cue` + `output/SonicCD-PS1-EN.bin` (or `-JP`): a Mode 2 BIN/CUE image (547 MB).
  It has to be BIN/CUE, not `.iso`: CD-XA music and video use 2336-byte Mode 2 sectors, which a
  2048-byte ISO image can't hold.
- `output/SHA256SUMS-EN` (or `-JP`).

Built from the Steam files **without** a license file and with the tool versions listed under
[Requirements](#requirements), the English image is
`SonicCD-PS1-EN.bin` SHA-256 `fbd70a01ec9ae7aaf4de05d905d01976e425a61b8c455a55141113b2cb0fea84`.
Other versions of FFmpeg or psxavenc may encode the music and videos slightly differently, which changes
the hash but not the game. With a license file the license sectors differ, so the hash does too.

Before writing it, the builder verifies the image byte by byte: sector headers, EDC/ECC of every sector,
the license sectors, the file index, and every file against its source.

## What the PS1 version can do

- The whole game: all zones in every time period, time travel, the special stages, bosses, Secrets,
  Time Attack, the opening and ending videos, the credits.
- Sonic and Tails (as in the 2011 version, after finishing the game).
- **Both soundtracks** (US and JP), switchable in the menu, also in the videos.
- English or Japanese (one disc each).
- Saving on the **memory card in slot 1** (one block, with a Sonic CD icon): save slots, Time Attack
  records. Without a card the game plays normally and doesn't save.
- The special stages' 3D floor and background, projected with the PS1's geometry coprocessor.
- Help & Options: settings (music and effect volume, spin dash style), staff credits, about.
- An animated loading icon while the game reads from the disc.

## What the PS1 version can't do

- No online features: leaderboards and achievements are hidden.
- Help & Options has no *How to play* or *Controls* entries (on PC they open Windows dialogs).
- No dev menu, settings file or mods from the PC version.
- The special stages, the title screen and some busy scenes run below full speed in emulators
  (70–85 % in the special stages): the PS1 draws every frame instead of skipping some.
- Tested in emulators only (PCSX-Redux, including boot through a retail NTSC-U BIOS); not yet on a real
  console.

## Compromises to make this work

- Screen 320 px wide (the 2011 version is widescreen, 424 px).
- Music is 4-bit CD-XA ADPCM at 37.8 kHz stereo (the PS1's streaming format).
- Sound effects are SPU-ADPCM at one rate per file, from 44.1 kHz down to 11 kHz for the largest ones, so
  every stage's set fits the 512 KB of sound RAM; the Secrets sound test uses its own lower-rate copies.
- The videos are 320×176 MDEC at 15 fps (the originals are 640×368 Theora).
- The far part of the special-stage floor is a low-resolution texture (one texel per 16×16 tile).
- Transparency uses the PS1 GPU's 4 fixed blend levels.
- Loads take a few seconds (the drive reads ahead continuously, files are placed in load order); a
  loading icon shows while they run.

## Requirements

Tested on macOS (Apple Silicon) with Python 3.9, Pillow 11, NumPy 2.0, FFmpeg 9, psxavenc (git,
2026-09), mkpsxiso 2.30, clang 22 and make. Linux works the same way; on Windows, use WSL.

| Tool | What for |
|---|---|
| Python 3.8+ with Pillow and NumPy (`pip install -r requirements.txt`) | the converters |
| a C++17 compiler (clang++ or g++) and `make` | builds a small host tool from the engine's source (reads the scripts' sprite lists) |
| FFmpeg (`ffmpeg`, `ffprobe`), with Theora and Vorbis decoding | decodes the game's Ogg audio and Theora videos |
| [psxavenc](https://codeberg.org/WonderfulToolchain/psxavenc) | encodes SPU-ADPCM, CD-XA and STR video |
| [mkpsxiso](https://github.com/Lameguy64/mkpsxiso) | writes the disc image |

The builder finds the tools on your `PATH`, or through the environment variables `PSXAVENC`, `MKPSXISO`,
`FFMPEG`, `FFPROBE` and `CXX`. It stops with a list if anything is missing. Run it with the Python that has
Pillow and NumPy installed.

**macOS** (Homebrew):
```bash
xcode-select --install                      # clang++, make
brew install python ffmpeg meson ninja pkg-config
python3 -m pip install -r requirements.txt
git clone https://codeberg.org/WonderfulToolchain/psxavenc && cd psxavenc
meson setup build && meson compile -C build && cd ..   # then PSXAVENC=$PWD/psxavenc/build/psxavenc
# mkpsxiso: download a release from https://github.com/Lameguy64/mkpsxiso/releases
#           (or build it with CMake) and put `mkpsxiso` on your PATH or in MKPSXISO
```

**Linux** (Debian/Ubuntu):
```bash
sudo apt install python3-pip build-essential ffmpeg meson ninja-build pkg-config \
     libavformat-dev libavcodec-dev libavutil-dev libswresample-dev libswscale-dev cmake
python3 -m pip install -r requirements.txt
# psxavenc and mkpsxiso: as above (meson for psxavenc, CMake or a release for mkpsxiso)
```

## The license file

PlayStation discs carry Sony's license data, which retail consoles check at boot. It can't be distributed,
so by default the image is built **without** it: it plays in emulators (PCSX-Redux, DuckStation, …), on
optical drive emulators and on modded consoles. If you have `licensea.dat` (NTSC-U) from the official SDK,
pass `--license licensea.dat` to make a disc that also boots on retail NTSC-U consoles.

## Playing it

- **Emulator:** open `SonicCD-PS1-EN.cue` in PCSX-Redux or DuckStation. Put a memory card in slot 1 to
  save.
- **Real hardware:** burn the BIN/CUE at the slowest speed on a CD-R, or copy it to an optical drive
  emulator. Not yet tested on a console — reports are welcome.

## How it's made

The executable in `bin/` is built from a PS1 port of the
[RSDKv3 decompilation](https://github.com/RSDKModding/RSDKv3-Decompilation) using
[psyqo](https://github.com/pcsx-redux/nugget/tree/main/psyqo), developed and tested with
[PCSX-Redux](https://github.com/grumpycoders/pcsx-redux). See `bin/README.md` for its version.
`builder/` holds the conversion tools, each documented in its header, and the part of the decompilation
the host tool compiles.

PS1 edits to the game's scripts (applied at build time by `builder/tools/scripts/patch_bytecode.py`, each
checked instruction by instruction):
- Help & Options opens the console version's options window (settings, staff credits, about) instead of
  the PC one, whose entries open Windows dialogs.
- Two loops the special stages run every frame in script (sorting the objects by depth; stage 5's
  background ripple) run natively in the executable, with identical results.

## License & credits

- **Retro Engine (RSDK)** and **Sonic CD (2011)**: Christian "Taxman" Whitehead.
- **RSDKv3 decompilation**: Rubberduckycooly and RMGRich
  ([RSDKModding](https://github.com/RSDKModding/RSDKv3-Decompilation)).
- **psyqo / nugget / PCSX-Redux**: the PCSX-Redux authors. **EASTL / EABase**: Electronic Arts.
- **[ps1-bare-metal](https://github.com/spicyjpeg/ps1-bare-metal)** (sound and CD-ROM driver model):
  spicyjpeg.
- **psxpress** video decoder: [PSn00bSDK](https://github.com/Lameguy64/PSn00bSDK) contributors.
- **[mkpsxiso](https://github.com/Lameguy64/mkpsxiso)**: Lameguy64 and contributors.
  **[psxavenc](https://codeberg.org/WonderfulToolchain/psxavenc)**: Ben "GreaseMonkey" Russell and
  Adrian "asie" Siekierka.
- **[psx-spx](https://psx-spx.consoledev.net/)** hardware documentation: Martin "nocash" Korth and
  contributors.
- **Loading icon**: "Sonic Running" GIF by [Salmon270](https://tenor.com/en-GB/users/salmon270)
  ([source](https://tenor.com/en-GB/view/sonic-running-run-fast-gotta-go-fast-pixel-art-gif-16947491)).

Licensed under the RSDKv3/v4 decompilation license ([LICENSE.md](LICENSE.md)). **Not for commercial use.
No game assets are distributed** — you build the disc from your own copy of the game. Third-party licenses
and the MPL-covered source are in [licenses/](licenses/README.md) and
[sources/](sources/psxpress/README.md). Sonic the Hedgehog and Sonic CD are trademarks of SEGA; this
project is not affiliated with or endorsed by SEGA or Sony.
