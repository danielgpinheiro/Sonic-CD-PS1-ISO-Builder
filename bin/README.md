# SonicCD-PS1.exe

The PlayStation executable (PS-X EXE, 417792 bytes) that `build_iso.py` puts on the disc as `SONICCD.EXE`:
Retro Engine v3 (RSDKv3 decompilation) ported to the PS1 with psyqo.

- Built from the RSDKv3-ps1 port at commit `6e0098f` (2026-10-20), natural boot (`make`), retail 2 MB RAM.
- SHA-256 `ece22d4c8bfc6fc4ac70c8c1d5e628075a93433e7c0c058d18d15cc371f1a448` (also in `SHA256SUMS`).
- `VERSION.TXT` (`6e0098f4`) goes on the disc; the title screen shows it bottom-left.
- One executable for both languages: it reads the disc's language (`Data/Game/PS1Language.bin`, written by
  the builder's `--lang`).
- It reads the converted assets from the disc (`Data/...`); the converters in `../builder/` must match this
  executable's formats, so use the builder from the same release.
- Real hardware (tested on a PSone, SCPH-101):
  - The CPU drives the MDEC for the videos, because the MDEC's output DMA failed on that console.
  - It guards against CD and DMA interrupts lost by psyqo's interrupt acknowledge.
  - During a video, SELECT shows a diagnostics line at the bottom.
