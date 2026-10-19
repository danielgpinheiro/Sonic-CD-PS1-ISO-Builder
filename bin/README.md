# SonicCD-PS1.exe

The PlayStation executable (PS-X EXE, 417792 bytes) that `build_iso.py` puts on the disc as `SONICCD.EXE`:
Retro Engine v3 (RSDKv3 decompilation) ported to the PS1 with psyqo.

- Built from the RSDKv3-ps1 port at commit `88949da` (2026-10-18), natural boot (`make`), retail 2 MB RAM.
- SHA-256 `24e4d316f2a95f27e7da84364932e0f308af51cf625d8bdf3b396b67be8f1631` (also in `SHA256SUMS`).
- `VERSION.TXT` (`88949dae`) goes on the disc; the title screen shows it bottom-left.
- One executable for both languages: it reads the disc's language (`Data/Game/PS1Language.bin`, written by
  the builder's `--lang`).
- It reads the converted assets from the disc (`Data/...`); the converters in `../builder/` must match this
  executable's formats, so use the builder from the same release.
- Real hardware (tested on a PSone, SCPH-101):
  - The CPU drives the MDEC for the videos, because the MDEC's output DMA failed on that console.
  - It guards against CD and DMA interrupts lost by psyqo's interrupt acknowledge.
  - During a video, SELECT shows a diagnostics line at the bottom.
