# SonicCD-PS1.exe

The PlayStation executable (PS-X EXE, 382976 bytes) that `build_iso.py` puts on the disc as `PSX.EXE`:
Retro Engine v3 (RSDKv3 decompilation) ported to the PS1 with psyqo.

- Built from the RSDKv3-ps1 port at commit `1e583ad` (2026-09-25), natural boot, retail 2 MB RAM.
- SHA-256 `a9d0cd7f78b9afca08768a241ef24ca9e5eee345cb3ac95ed34ef039ce7bba11` (also in `SHA256SUMS`).
- One executable for both languages: it reads the disc's language (`Data/Game/PS1Language.bin`, written by
  the builder's `--lang`).
- It reads the converted assets from the disc (`Data/...`); the converters in `../builder/` must match this
  executable's formats, so use the builder from the same release.
