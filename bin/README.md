# SonicCD-PS1.exe

The PlayStation executable (PS-X EXE, 415744 bytes) that `build_iso.py` puts on the disc as `SONICCD.EXE`:
Retro Engine v3 (RSDKv3 decompilation) ported to the PS1 with psyqo.

- Built from the RSDKv3-ps1 port at commit `b8bf139` (2026-10-18), natural boot (`make`), retail 2 MB RAM.
- SHA-256 `a38964c329b9896fd8cc7d0f97f56f75c632c8c511fc0f55d92933f3f1d88dfa` (also in `SHA256SUMS`).
- One executable for both languages: it reads the disc's language (`Data/Game/PS1Language.bin`, written by
  the builder's `--lang`).
- It reads the converted assets from the disc (`Data/...`); the converters in `../builder/` must match this
  executable's formats, so use the builder from the same release.
- Real hardware (tested on a PSone, SCPH-101):
  - The CPU drives the MDEC for the videos, because the MDEC's output DMA failed on that console.
  - It guards against CD and DMA interrupts lost by psyqo's interrupt acknowledge.
  - During a video, SELECT shows a diagnostics line at the bottom.
