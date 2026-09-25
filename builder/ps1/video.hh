/*
 * PS1 STR video playback (MDEC + VLC).
 *
 * Streams a psxavenc `-t strv` file (BS v2, 2048-byte sectors, 10 sectors/frame)
 * via the CD-ROM asynchronously (double-buffered), Huffman-decodes each frame
 * with DecDCTvlcStart2, then the MDEC hardware does RLE+IDCT+YUV->RGB into a
 * 15bpp BGR555 buffer.
 */
#pragma once

#include <stdint.h>

bool      PS1VideoInit();                 // MDEC reset + VLC table build (once)
bool      PS1VideoOpen(const char *path, int audio = 0); // open the STR, start the async read (audio: XA channel 0 / 1 of an STR2)
int       PS1VideoNextFrame();            // 1 = decoded a frame, 0 = still reading, -1 = EOF
void      PS1VideoClose();
uint16_t *PS1VideoPixels();               // w*h BGR555 buffer
int       PS1VideoWidth();
int       PS1VideoHeight();

// Game-side playback (RSDK LoadVideo / NextVideoFrame). The engine asks for frames at its
// own pace; PS1VideoService() runs once per game frame, keeps the CD stream fed and decodes
// one requested frame when its sectors have arrived.
bool PS1VideoIsOpen();
int  PS1VideoFrameCount();   // frames in the open STR
uint32_t PS1VideoDataSectors(); // data (video) sectors the open STR delivers
void PS1VideoRequestFrame(); // one more frame wanted (NextVideoFrame)
int  PS1VideoService();      // 1 = hand over PS1VideoPixels() now, 0 = nothing new, -1 = closed
int  PS1VideoDecode(uint32_t t0); // decode ahead until the frame budget (counted from t0) is spent; -1 = EOF/error
int  PS1VideoDecodeTo(uint32_t t0, int x, int y); // full-screen STR2: 1 = a new picture written to VRAM (x, y), 0 = none, -1 = end

// Timing helpers (root counter 1 = hblanks, 16-bit wrap ~4 s).
uint32_t PS1Hblanks();
uint32_t PS1HblanksSince(uint32_t t0);
