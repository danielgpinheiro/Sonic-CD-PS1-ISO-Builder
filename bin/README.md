# SonicCD-PS1.exe

The PlayStation executable (PS-X EXE, 415744 bytes) that `build_iso.py` puts on the disc as `SONICCD.EXE`:
Retro Engine v3 (RSDKv3 decompilation) ported to the PS1 with psyqo.

- Built from the RSDKv3-ps1 port at commit `99e1063` (2026-10-17), natural boot (`make`), retail 2 MB RAM.
- SHA-256 `8a18280f25040be66ee9b113132521943118801ab4153b593776339180979a6c` (also in `SHA256SUMS`).
- One executable for both languages: it reads the disc's language (`Data/Game/PS1Language.bin`, written by
  the builder's `--lang`).
- It reads the converted assets from the disc (`Data/...`); the converters in `../builder/` must match this
  executable's formats, so use the builder from the same release.
- Real hardware (tested on a PSone, SCPH-101):
  - The CPU drives the MDEC for the videos, because the MDEC's output DMA failed on that console.
  - It guards against CD and DMA interrupts lost by psyqo's interrupt acknowledge.
  - During a video, SELECT shows a diagnostics line at the bottom.
