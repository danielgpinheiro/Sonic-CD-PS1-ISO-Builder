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

/* Port additions: the MDEC without DMA (PIO), bounded waits (hblanks), fault recovery. */
#define DECDCT_STAT_OUT_EMPTY 0x80000000u // MDEC1: data-out FIFO empty
#define DECDCT_STAT_IN_FULL   0x40000000u // MDEC1: data-in FIFO full (or last word received)
#define DECDCT_STAT_BUSY      0x20000000u // MDEC1: command busy
static inline uint32_t DecDCTStatus(void) { return *(volatile uint32_t *)0xBF801824u; }
static inline void     DecDCTPutWord(uint32_t w) { *(volatile uint32_t *)0xBF801820u = w; }
static inline uint32_t DecDCTGetWord(void) { return *(volatile uint32_t *)0xBF801820u; }
int  DecDCTCommandPIO(uint32_t command);                  // waits for "busy" to clear; 0 / -1 timeout
int  DecDCTParamsPIO(const uint32_t *data, size_t words); // word by word, waiting for input FIFO room
int  DecDCTResetPIO(const DECDCTENV *env);                // reset, DMA requests off, tables by the CPU
void DecDCTAbort(uint32_t control);                       // stop both MDEC DMAs, reset (tables kept), MDEC1 = control
void DecDCTControl(uint32_t control);                     // MDEC1 (control): DMA request enables, bits 30 (in) / 29 (out)
void DecDCTSnapshot(uint32_t out[8]);                     // MDEC1, DMA0 MADR/BCR/CHCR, DMA1 MADR/BCR/CHCR, DPCR

/* VLC decode (pure C, BS v1/v2; the 34 KB table is built by DecDCTvlcBuild). */
int  DecDCTvlcStart2(VLC_Context *ctx, uint32_t *buf, size_t max_size, const uint32_t *bs);
int  DecDCTvlcContinue2(VLC_Context *ctx, uint32_t *buf, size_t max_size);
void DecDCTvlcBuild(DECDCTTAB *table);
