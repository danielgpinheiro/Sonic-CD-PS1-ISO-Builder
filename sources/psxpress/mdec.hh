/*
 * PS1 MDEC + VLC driver (ported from PSn00bSDK libpsn00b/psxpress, MPL).
 *
 * The MDEC does RLE-decode + IDCT + YUV->RGB in silicon; the CPU only DMAs the
 * bitstream in (DMA0/MDECin) and the pixels out (DMA1/MDECout). The VLC part
 * (DecDCTvlc*2) Huffman-decodes a BS v1/v2 bitstream (an STR frame) into the raw
 * run-length codes the MDEC consumes. This is the standard PS1 FMV pipeline —
 * the golden rule (no runtime decode) applies to sprites/assets, not to the
 * MDEC/SPU hardware path.
 */
#pragma once

#include <stdint.h>
#include <stddef.h>

typedef struct {
    uint8_t iq_y[64]; // luma quant table, zigzag order
    uint8_t iq_c[64]; // chroma quant table, zigzag order
    int16_t dct[64];  // inverse DCT matrix (2.14 fixed-point)
} DECDCTENV;

typedef struct {
    uint32_t ac[8192], ac00[512];
} DECDCTTAB;

typedef enum {
    DECDCT_MODE_24BPP       = 1,
    DECDCT_MODE_16BPP       = 0,
    DECDCT_MODE_16BPP_BIT15 = 2,
    DECDCT_MODE_RAW         = -1
} DECDCTMODE;

typedef struct {
    const uint32_t *input;
    uint32_t window, next_window, remaining;
    int8_t   is_v3, bit_offset, block_index, coeff_index;
    uint16_t quant_scale;
    int16_t  last_y, last_cr, last_cb;
} VLC_Context;

typedef struct {
    uint32_t mdec0_header;
    uint16_t quant_scale;
    uint16_t version;
} BS_Header;

/* MDEC driver */
void DecDCTReset(int mode);
void DecDCTPutEnv(const DECDCTENV *env, int mono);
void DecDCTin(const uint32_t *data, int mode);
void DecDCTinRaw(const uint32_t *data, size_t length);
int  DecDCTinSync(int mode);
void DecDCTout(uint32_t *data, size_t length);
int  DecDCToutSync(int mode);

/* VLC decode (pure C, BS v1/v2; the 34 KB table is built by DecDCTvlcBuild). */
int  DecDCTvlcStart2(VLC_Context *ctx, uint32_t *buf, size_t max_size, const uint32_t *bs);
int  DecDCTvlcContinue2(VLC_Context *ctx, uint32_t *buf, size_t max_size);
void DecDCTvlcBuild(DECDCTTAB *table);
