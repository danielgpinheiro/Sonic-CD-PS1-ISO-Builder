# SonicCD-PS1.exe

The PlayStation executable (PS-X EXE, 419840 bytes) that `build_iso.py` puts on the disc as `SONICCD.EXE`:
Retro Engine v3 (RSDKv3 decompilation) ported to the PS1 with psyqo.

- Built from the RSDKv3-ps1 port at commit `ff4d78c` (2026-10-21), natural boot (`make`), retail 2 MB RAM.
- SHA-256 `aaf578e513a611bb761de14ad2a65d05b538553376af9289690a8f8f7032c088` (also in `SHA256SUMS`).
- `VERSION.TXT` (`ff4d78c5`) goes on the disc; the title screen shows it bottom-left.
- One executable for both languages: it reads the disc's language (`Data/Game/PS1Language.bin`, written by
  the builder's `--lang`).
- It reads the converted assets from the disc (`Data/...`); the converters in `../builder/` must match this
  executable's formats, so use the builder from the same release.
- Real hardware (tested on a PSone, SCPH-101):
  - The CPU drives the MDEC for the videos, because the MDEC's output DMA failed on that console.
  - It guards against CD and DMA interrupts lost by psyqo's interrupt acknowledge.
  - During a video, SELECT shows a diagnostics line at the bottom.
