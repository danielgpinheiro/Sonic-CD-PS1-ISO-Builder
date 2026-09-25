# Third-party licenses

This repository contains the builder scripts, part of the RSDKv3 decompilation (for the host tool that reads the
scripts' sprite lists) and a prebuilt PlayStation executable (`bin/SonicCD-PS1.exe`). No game data.

## Covering this repository

| Component | Where | License |
|---|---|---|
| RSDKv3 decompilation (Rubberduckycooly, RMGRich; original RSDK by Christian Whitehead) | `builder/RSDKv3/`, `builder/tools/rsdkmanifest/`, the engine in `bin/SonicCD-PS1.exe` | [../LICENSE.md](../LICENSE.md) — non-commercial, credit the authors, no game assets |
| PS1 port code and builder scripts | `build_iso.py`, `builder/`, the port in `bin/SonicCD-PS1.exe` | [../LICENSE.md](../LICENSE.md) (same terms) |

## Compiled into `bin/SonicCD-PS1.exe`

| Component | Authors | License |
|---|---|---|
| psyqo / nugget (PS1 SDK) | PCSX-Redux authors | MIT — [psyqo-nugget-MIT.txt](psyqo-nugget-MIT.txt) |
| EASTL, EABase (C++ containers, via psyqo) | Electronic Arts | BSD 3-Clause — [EASTL-BSD-3-Clause.txt](EASTL-BSD-3-Clause.txt), [EABase-BSD-3-Clause.txt](EABase-BSD-3-Clause.txt) |
| psxpress MDEC/VLC decoder (ported, modified) | PSn00bSDK contributors | MPL 2.0 — [MPL-2.0.txt](MPL-2.0.txt); the modified source is in [../sources/psxpress/](../sources/psxpress/) as the MPL requires |
| SPU / CD-ROM driver model (ps1-bare-metal) | spicyjpeg | MIT — [ps1-bare-metal-MIT.txt](ps1-bare-metal-MIT.txt) |
| Loading icon ("Sonic Running" GIF, converted to a 4-bit texture) | [Salmon270](https://tenor.com/en-GB/users/salmon270) (Tenor) | credited to its author |

## External tools (installed by you, not included)

| Tool | License |
|---|---|
| [mkpsxiso](https://github.com/Lameguy64/mkpsxiso) | GPL 2.0 or later |
| [psxavenc](https://codeberg.org/WonderfulToolchain/psxavenc) | zlib-style — [psxavenc-license.txt](psxavenc-license.txt) |
| [FFmpeg](https://ffmpeg.org) | LGPL 2.1+ / GPL 2+ (depending on the build) |
| [Pillow](https://python-pillow.org), [NumPy](https://numpy.org) | MIT-CMU / BSD |
