/*
 * PS1 MDEC + VLC driver (ported from PSn00bSDK libpsn00b/psxpress, MPL).
 *
 * mdec.c -> DecDCT* (registers + DMA), vlc2.c -> DecDCTvlc*2 (pure-C BS v1/v2).
 * The only porting change is the register macros: psyqo exposes no MDEC/DMA
 * registers, so they are hardcoded volatile MMIO pointers below (KSEG1).
 */
#include "mdec.hh"

#include <string.h>

#define MMIO32(a) (*(volatile uint32_t *)(a))

#define MDEC0       MMIO32(0xBF801820u)
#define MDEC1       MMIO32(0xBF801824u)
#define DMA_MADR(N) MMIO32(0xBF801080u + 16u * (N))
#define DMA_BCR(N)  MMIO32(0xBF801084u + 16u * (N))
#define DMA_CHCR(N) MMIO32(0xBF801088u + 16u * (N))
#define DMA_DPCR    MMIO32(0xBF8010F0u)

#define DMA_MDEC_IN  0
#define DMA_MDEC_OUT 1

#define DMA_CHUNK_LENGTH 32
#define MDEC_SYNC_TIMEOUT 0x100000

/* Default IDCT matrix and quantization tables (mdec.c) */

#define S0 0x5a82
#define S1 0x7d8a
#define S2 0x7641
#define S3 0x6a6d
#define S4 0x5a82
#define S5 0x471c
#define S6 0x30fb
#define S7 0x18f8

static const DECDCTENV _default_mdec_env __attribute__((aligned(4))) = { // read as words (PIO)
    // MPEG-1 quant table, first value 2 (zigzag order; byte-identical to
    // psxavenc's quant_dec after the zigzag reorder).
    .iq_y = {
        2, 16, 16, 19, 16, 19, 22, 22,
        22, 22, 22, 22, 26, 24, 26, 27,
        27, 27, 26, 26, 26, 26, 27, 27,
        27, 29, 29, 29, 34, 34, 34, 29,
        29, 29, 27, 27, 29, 29, 32, 32,
        34, 34, 37, 38, 37, 35, 35, 34,
        35, 38, 38, 40, 40, 40, 48, 48,
        46, 46, 56, 56, 58, 69, 69, 83
    },
    .iq_c = {
        2, 16, 16, 19, 16, 19, 22, 22,
        22, 22, 22, 22, 26, 24, 26, 27,
        27, 27, 26, 26, 26, 26, 27, 27,
        27, 29, 29, 29, 34, 34, 34, 29,
        29, 29, 27, 27, 29, 29, 32, 32,
        34, 34, 37, 38, 37, 35, 35, 34,
        35, 38, 38, 40, 40, 40, 48, 48,
        46, 46, 56, 56, 58, 69, 69, 83
    },
    .dct = {
        S0,  S0,  S0,  S0,  S0,  S0,  S0,  S0,
        S1,  S3,  S5,  S7, -S7, -S5, -S3, -S1,
        S2,  S6, -S6, -S2, -S2, -S6,  S6,  S2,
        S3, -S7, -S1, -S5,  S5,  S1,  S7, -S3,
        S4, -S4, -S4,  S4,  S4, -S4, -S4,  S4,
        S5, -S1,  S7,  S3, -S3, -S7,  S1, -S5,
        S6, -S2,  S2, -S6, -S6,  S2, -S2,  S6,
        S7, -S5,  S3, -S1,  S1, -S3,  S5, -S7
    }
};

static void setDmaPriority(int dma, int priority) {
    uint32_t dpcr = DMA_DPCR;
    dpcr &= ~(0xfu << (dma * 4));
    if (priority >= 0)
        dpcr |= ((priority & 7) | 8) << (dma * 4);
    DMA_DPCR = dpcr;
}

void DecDCTReset(int mode) {
    // MDEC-in above MDEC-out, as the BIOS default DPCR (07654321h) that ps1-tests' MDEC tests ran with on
    // hardware. PSn00bSDK's 3/3 lets MDEC-out win the tie; on the PSone every MDEC-out DMA then timed out
    // with the CPU starved (docs/28 appendix 12, part 2).
    setDmaPriority(DMA_MDEC_IN, 1);
    setDmaPriority(DMA_MDEC_OUT, 2);
    DMA_CHCR(DMA_MDEC_IN)  = 0x00000201; // Stop DMA
    DMA_CHCR(DMA_MDEC_OUT) = 0x00000200; // Stop DMA

    MDEC1 = 0x80000000; // Reset MDEC
    MDEC1 = 0x60000000; // Enable DMA in/out requests

    if (!mode)
        DecDCTPutEnv(0, 0);
}

void DecDCTPutEnv(const DECDCTENV *env, int mono) {
    DecDCTinSync(0);
    if (!env)
        env = &_default_mdec_env;

    MDEC0 = 0x60000000; // Set IDCT matrix
    DecDCTinRaw((const uint32_t *) env->dct, 32);
    DecDCTinSync(0);

    MDEC0 = 0x40000000 | (mono ? 0 : 1); // Set quantization table(s)
    DecDCTinRaw((const uint32_t *) env->iq_y, mono ? 16 : 32);
    DecDCTinSync(0);
}

void DecDCTin(const uint32_t *data, int mode) {
    uint32_t header = *data;
    DecDCTinSync(0);

    if (mode == DECDCT_MODE_RAW)
        MDEC0 = header;
    else if (mode & DECDCT_MODE_24BPP)
        MDEC0 = 0x30000000 | (header & 0xffff);
    else
        MDEC0 = 0x38000000 | (header & 0xffff) | ((mode & 2) << 24); // Bit 25 = mask

    DecDCTinRaw((const uint32_t *) &(data[1]), header & 0xffff);
}

void DecDCTinRaw(const uint32_t *data, size_t length) {
    if ((length >= DMA_CHUNK_LENGTH) && (length % DMA_CHUNK_LENGTH))
        length += DMA_CHUNK_LENGTH - 1;

    DMA_MADR(DMA_MDEC_IN) = (uint32_t)(uintptr_t) data;
    if (length < DMA_CHUNK_LENGTH)
        DMA_BCR(DMA_MDEC_IN) = 0x00010000 | length;
    else
        DMA_BCR(DMA_MDEC_IN) = DMA_CHUNK_LENGTH | ((length / DMA_CHUNK_LENGTH) << 16);

    DMA_CHCR(DMA_MDEC_IN) = 0x01000201;
}

int DecDCTinSync(int mode) {
    if (mode)
        return (MDEC1 >> 29) & 1;

    for (int i = MDEC_SYNC_TIMEOUT; i; i--) {
        if (!(MDEC1 & (1 << 29)))
            return 0;
    }
    return -1;
}

void DecDCTout(uint32_t *data, size_t length) {
    DecDCToutSync(0);

    if ((length >= DMA_CHUNK_LENGTH) && (length % DMA_CHUNK_LENGTH))
        length += DMA_CHUNK_LENGTH - 1;

    DMA_MADR(DMA_MDEC_OUT) = (uint32_t)(uintptr_t) data;
    if (length < DMA_CHUNK_LENGTH)
        DMA_BCR(DMA_MDEC_OUT) = 0x00010000 | length;
    else
        DMA_BCR(DMA_MDEC_OUT) = DMA_CHUNK_LENGTH | ((length / DMA_CHUNK_LENGTH) << 16);

    DMA_CHCR(DMA_MDEC_OUT) = 0x01000200;
}

int DecDCToutSync(int mode) {
    if (mode)
        return (DMA_CHCR(DMA_MDEC_OUT) >> 24) & 1;

    for (int i = MDEC_SYNC_TIMEOUT; i; i--) {
        if (!(DMA_CHCR(DMA_MDEC_OUT) & (1 << 24)))
            return 0;
    }
    return -1;
}

/* ---------------------------------------------------------------------------
 * Port additions (docs/28 appendix 12, part 2): the MDEC without DMA, bounded waits, fault recovery.
 * PIO follows ps1-tests common/mdec.cpp, whose primitives ran on hardware: a command waits for "command
 * busy" to clear, a parameter word for "data-in FIFO full" to clear, a pixel word for "data-out FIFO
 * empty" to clear (psx-spx macroblockdecodermdec.md, MDEC1 status bits 29-31).
 * ------------------------------------------------------------------------- */

#define COUNTER1 MMIO32(0xBF801110u) // root counter 1: hblanks under psyqo

// Waits until (MDEC1 & mask) == 0, at most `limit` hblanks. 0 = ok, -1 = timeout.
static int waitClear(uint32_t mask, uint32_t limit) {
    uint32_t t0 = COUNTER1;
    while (MDEC1 & mask) {
        if (((COUNTER1 - t0) & 0xffff) > limit)
            return -1;
    }
    return 0;
}

#define PIO_WAIT_HBL 1000 // ~64 ms: a macroblock takes ~0.1 ms, a table load far less

int DecDCTCommandPIO(uint32_t command) {
    if (waitClear(1u << 29, PIO_WAIT_HBL) < 0)
        return -1;
    MDEC0 = command;
    return 0;
}

int DecDCTParamsPIO(const uint32_t *data, size_t words) {
    while (words--) {
        if (waitClear(1u << 30, PIO_WAIT_HBL) < 0)
            return -1;
        MDEC0 = *data++;
    }
    return 0;
}

int DecDCTResetPIO(const DECDCTENV *env) {
    if (!env)
        env = &_default_mdec_env;
    DMA_CHCR(DMA_MDEC_IN)  = 0x00000201; // no MDEC DMA in this mode
    DMA_CHCR(DMA_MDEC_OUT) = 0x00000200;
    MDEC1 = 0x80000000; // reset
    MDEC1 = 0x00000000; // DMA requests off: the CPU moves every word
    if (DecDCTCommandPIO(0x60000000) < 0 || DecDCTParamsPIO((const uint32_t *)env->dct, 32) < 0)
        return -1; // MDEC(3): scale table
    if (DecDCTCommandPIO(0x40000001) < 0 || DecDCTParamsPIO((const uint32_t *)env->iq_y, 32) < 0)
        return -1; // MDEC(2): luma + chroma quant tables
    return waitClear(1u << 29, PIO_WAIT_HBL);
}

void DecDCTAbort(uint32_t control) {
    DMA_CHCR(DMA_MDEC_IN)  = 0x00000201; // stop both MDEC DMAs (start bit cleared)
    DMA_CHCR(DMA_MDEC_OUT) = 0x00000200;
    MDEC1 = 0x80000000;                   // abort the command; the tables survive a reset (psx-spx)
    MDEC1 = control;                      // DMA requests of the mode: 60000000h both, 40000000h in only, 0 none
}

void DecDCTControl(uint32_t control) { MDEC1 = control; }

void DecDCTSnapshot(uint32_t out[8]) {
    out[0] = MDEC1;
    out[1] = DMA_MADR(DMA_MDEC_IN);
    out[2] = DMA_BCR(DMA_MDEC_IN);
    out[3] = DMA_CHCR(DMA_MDEC_IN);
    out[4] = DMA_MADR(DMA_MDEC_OUT);
    out[5] = DMA_BCR(DMA_MDEC_OUT);
    out[6] = DMA_CHCR(DMA_MDEC_OUT);
    out[7] = DMA_DPCR;
}

/* ---------------------------------------------------------------------------
 * VLC decode (vlc2.c) — pure C, BS v1/v2, 34 KB lookup table.
 * ------------------------------------------------------------------------- */

#define TABLE_LENGTH 226

// Run-length-compressed Huffman table; DecDCTvlcBuild() decompresses it.
static const uint32_t _compressed_table[TABLE_LENGTH] = {
    0x03e00000, 0x000d000b, 0x000d03f5, 0x000d2002, 0x000d23fe, 0x000d1003,
    0x000d13fd, 0x000d000a, 0x000d03f6, 0x000d0804, 0x000d0bfc, 0x000d1c02,
    0x000d1ffe, 0x000d5402, 0x000d57fe, 0x000d5001, 0x000d53ff, 0x000d0009,
    0x000d03f7, 0x000d4c01, 0x000d4fff, 0x000d4801, 0x000d4bff, 0x000d0405,
    0x000d07fb, 0x000d0c03, 0x000d0ffd, 0x000d0008, 0x000d03f8, 0x000d1802,
    0x000d1bfe, 0x000d4401, 0x000d47ff, 0x006b4001, 0x006b43ff, 0x006b1402,
    0x006b17fe, 0x006b0007, 0x006b03f9, 0x006b0803, 0x006b0bfd, 0x006b0404,
    0x006b07fc, 0x006b3c01, 0x006b3fff, 0x006b3801, 0x006b3bff, 0x006b1002,
    0x006b13fe, 0x0fe00000, 0x03e80802, 0x03e80bfe, 0x03e82401, 0x03e827ff,
    0x03e80004, 0x03e803fc, 0x03e82001, 0x03e823ff, 0x07e71c01, 0x07e71fff,
    0x07e71801, 0x07e71bff, 0x07e70402, 0x07e707fe, 0x07e71401, 0x07e717ff,
    0x01e93401, 0x01e937ff, 0x01e90006, 0x01e903fa, 0x01e93001, 0x01e933ff,
    0x01e92c01, 0x01e92fff, 0x01e90c02, 0x01e90ffe, 0x01e90403, 0x01e907fd,
    0x01e90005, 0x01e903fb, 0x01e92801, 0x01e92bff, 0x0fe60003, 0x0fe603fd,
    0x0fe61001, 0x0fe613ff, 0x0fe60c01, 0x0fe60fff, 0x1fe50002, 0x1fe503fe,
    0x1fe50801, 0x1fe50bff, 0x3fe40401, 0x3fe407ff, 0xffe2fe00, 0x7fe30001,
    0x7fe303ff, 0x03e00000, 0x00110412, 0x001107ee, 0x00110411, 0x001107ef,
    0x00110410, 0x001107f0, 0x0011040f, 0x001107f1, 0x00111803, 0x00111bfd,
    0x00114002, 0x001143fe, 0x00113c02, 0x00113ffe, 0x00113802, 0x00113bfe,
    0x00113402, 0x001137fe, 0x00113002, 0x001133fe, 0x00112c02, 0x00112ffe,
    0x00117c01, 0x00117fff, 0x00117801, 0x00117bff, 0x00117401, 0x001177ff,
    0x00117001, 0x001173ff, 0x00116c01, 0x00116fff, 0x00300028, 0x003003d8,
    0x00300027, 0x003003d9, 0x00300026, 0x003003da, 0x00300025, 0x003003db,
    0x00300024, 0x003003dc, 0x00300023, 0x003003dd, 0x00300022, 0x003003de,
    0x00300021, 0x003003df, 0x00300020, 0x003003e0, 0x0030040e, 0x003007f2,
    0x0030040d, 0x003007f3, 0x0030040c, 0x003007f4, 0x0030040b, 0x003007f5,
    0x0030040a, 0x003007f6, 0x00300409, 0x003007f7, 0x00300408, 0x003007f8,
    0x006f001f, 0x006f03e1, 0x006f001e, 0x006f03e2, 0x006f001d, 0x006f03e3,
    0x006f001c, 0x006f03e4, 0x006f001b, 0x006f03e5, 0x006f001a, 0x006f03e6,
    0x006f0019, 0x006f03e7, 0x006f0018, 0x006f03e8, 0x006f0017, 0x006f03e9,
    0x006f0016, 0x006f03ea, 0x006f0015, 0x006f03eb, 0x006f0014, 0x006f03ec,
    0x006f0013, 0x006f03ed, 0x006f0012, 0x006f03ee, 0x006f0011, 0x006f03ef,
    0x006f0010, 0x006f03f0, 0x00ee2802, 0x00ee2bfe, 0x00ee2402, 0x00ee27fe,
    0x00ee1403, 0x00ee17fd, 0x00ee0c04, 0x00ee0ffc, 0x00ee0805, 0x00ee0bfb,
    0x00ee0407, 0x00ee07f9, 0x00ee0406, 0x00ee07fa, 0x00ee000f, 0x00ee03f1,
    0x00ee000e, 0x00ee03f2, 0x00ee000d, 0x00ee03f3, 0x00ee000c, 0x00ee03f4,
    0x00ee6801, 0x00ee6bff, 0x00ee6401, 0x00ee67ff, 0x00ee6001, 0x00ee63ff,
    0x00ee5c01, 0x00ee5fff, 0x00ee5801, 0x00ee5bff
};

static const DECDCTTAB *_vlc_huffman_table2 = 0;

#define _get_bits_unsigned(length) (((uint32_t) window) >> (32 - (length)))
#define _advance_window(num)       \
    window <<= (num);              \
    bit_offset -= (num);

int DecDCTvlcContinue2(VLC_Context *ctx, uint32_t *buf, size_t max_size) {
    const uint32_t *input       = ctx->input;
    uint32_t        window      = ctx->window;
    uint32_t        next_window = ctx->next_window;
    uint32_t        remaining   = ctx->remaining;
    int             is_v3       = ctx->is_v3;
    int             bit_offset  = ctx->bit_offset;
    int             block_index = ctx->block_index;
    int             coeff_index = ctx->coeff_index;
    uint16_t        quant_scale = ctx->quant_scale;

    if (!max_size)
        max_size = 0x7fffffff;

    // First output word is the MDEC(1) command (parsed by DecDCTin()).
    max_size   = ((max_size - 1) * 2 < remaining) ? ((max_size - 1) * 2) : remaining;
    remaining -= max_size;

    *buf               = 0x38000000 | (max_size / 2);
    uint16_t *output   = (uint16_t *) &buf[1];

    for (; max_size; max_size--) {
        uint32_t value;

        if (coeff_index) {
            if ((window >> 30) == 0b10) {
                // Prefix 10 = end of block.
                *output = 0xfe00;
                _advance_window(2);
                coeff_index = -1;
                block_index++;
                if (block_index > 5)
                    block_index = 0;
            } else if ((window >> 26) == 0b000001) {
                // Prefix 000001 = escape + full 16-bit MDEC value.
                *output = (uint16_t) _get_bits_unsigned(22);
                _advance_window(22);
            } else if (window >> 24) {
                value = _vlc_huffman_table2->ac[_get_bits_unsigned(13)];
                _advance_window(value >> 16);
                *output = (uint16_t) value;
            } else {
                value = _vlc_huffman_table2->ac00[_get_bits_unsigned(17)];
                _advance_window(value >> 16);
                *output = (uint16_t) value;
            }
        } else {
            if (is_v3) {
                return -1; // v3 unsupported here
            } else {
                value = _get_bits_unsigned(10);
                if (value == 0x1ff)
                    break;
                *output = value | quant_scale;
                _advance_window(10);
            }
        }

        output++;
        coeff_index++;

        if (bit_offset < 0) {
            window      = next_window << (-bit_offset);
            bit_offset += 32;
            next_window = (*input << 16) | (*input >> 16);
            input++;
        }
        window |= next_window >> bit_offset;
    }

    for (; max_size; max_size--)
        *(output++) = 0xfe00;

    if (!remaining)
        return 0;

    ctx->input       = input;
    ctx->window      = window;
    ctx->next_window = next_window;
    ctx->remaining   = remaining;
    ctx->bit_offset  = bit_offset;
    ctx->block_index = block_index;
    ctx->coeff_index = coeff_index;
    return 1;
}

int DecDCTvlcStart2(VLC_Context *ctx, uint32_t *buf, size_t max_size, const uint32_t *bs) {
    const BS_Header *header = (const BS_Header *) bs;
    const uint32_t  *input  = (const uint32_t *) &header[1];

    if (!_vlc_huffman_table2)
        return -1;
    if (header->version > 3)
        return -1;

    ctx->input       = &input[2];
    ctx->window      = (input[0] << 16) | (input[0] >> 16);
    ctx->next_window = (input[1] << 16) | (input[1] >> 16);
    ctx->remaining   = (header->mdec0_header & 0xffff) * 2;
    ctx->is_v3       = (header->version >= 3);
    ctx->bit_offset  = 32;
    ctx->block_index = 0;
    ctx->coeff_index = 0;
    ctx->quant_scale = (header->quant_scale & 63) << 10;
    ctx->last_y      = 0;
    ctx->last_cr     = 0;
    ctx->last_cb     = 0;

    return DecDCTvlcContinue2(ctx, buf, max_size);
}

void DecDCTvlcBuild(DECDCTTAB *table) {
    uint32_t *output = (uint32_t *) table;
    _vlc_huffman_table2 = table;

    for (int i = 0; i < TABLE_LENGTH; i++) {
        uint32_t value = _compressed_table[i] & 0x001fffff;
        for (int j = (_compressed_table[i] >> 21); j >= 0; j--)
            *(output++) = value;
    }
}
