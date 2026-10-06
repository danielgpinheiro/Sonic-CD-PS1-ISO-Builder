# SonicCD-PS1.exe

The PlayStation executable (PS-X EXE, 391168 bytes) that `build_iso.py` puts on the disc as `PSX.EXE`:
Retro Engine v3 (RSDKv3 decompilation) ported to the PS1 with psyqo.

- Built from the RSDKv3-ps1 port at commit `3e38342` (2026-10-06; psyqo from nugget `05b9bc30`), natural boot, retail 2 MB RAM.
- SHA-256 `5d54a691c66d3f1048cc582aef6802e543a67b99ab3e214f4ffc10afd6f11240` (also in `SHA256SUMS`).
- One executable for both languages: it reads the disc's language (`Data/Game/PS1Language.bin`, written by
  the builder's `--lang`).
- It reads the converted assets from the disc (`Data/...`); the converters in `../builder/` must match this
  executable's formats, so use the builder from the same release.
- Real hardware (tested on a PSone, SCPH-101):
  - The CPU drives the MDEC for the videos, because the MDEC's output DMA failed on that console.
  - It guards against CD and DMA interrupts lost by psyqo's interrupt acknowledge.
  - During a video, SELECT shows a diagnostics line at the bottom.
