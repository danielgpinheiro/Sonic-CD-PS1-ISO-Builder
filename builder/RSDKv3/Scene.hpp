#ifndef SCENE_H
#define SCENE_H

#define LAYER_COUNT    (9)
#define DEFORM_STORE   (256)
#define DEFORM_SIZE    (320)
#define DEFORM_COUNT   (DEFORM_STORE + DEFORM_SIZE)
#define PARALLAX_COUNT (0x100)

#define TILE_COUNT    (0x400)
#define TILE_SIZE     (0x10)
#define CHUNK_SIZE    (0x80)
#define TILE_DATASIZE (TILE_SIZE * TILE_SIZE)
#define TILESET_SIZE  (TILE_COUNT * TILE_DATASIZE)

#define TILELAYER_CHUNK_W      (0x100) // the row stride (y * 0x100) is hard-coded in the engine: keep it
#if RETRO_PLATFORM == RETRO_PS1
// PS1 (2 MB): regular stages' layers are <= 18 chunks tall (docs/28 phase 1); taller rows (the
// Credits FG, 128) are clamped at load and counted (g_ps1LayerRowsClamped) until handled.
#define TILELAYER_CHUNK_H      (0x14)
// Layer 0 (the FG, also the special stages' 3D floor: 32 x 32 chunks) gets more rows: TileLayer::tiles is
// a pointer on PS1, layer 0 into a taller buffer (Scene.cpp). Rows past it (Credits FG) are still clamped.
#define PS1_LAYER0_CHUNK_H     (0x20)
#else
#define TILELAYER_CHUNK_H      (0x100)
#endif
#define TILELAYER_CHUNK_COUNT  (TILELAYER_CHUNK_W * TILELAYER_CHUNK_H)
#define TILELAYER_SCROLL_COUNT (TILELAYER_CHUNK_H * CHUNK_SIZE)

#define CHUNKTILE_COUNT (0x200 * (8 * 8))

#define CPATH_COUNT (2)

enum StageListNames {
    STAGELIST_PRESENTATION,
    STAGELIST_REGULAR,
    STAGELIST_BONUS,
    STAGELIST_SPECIAL,
    STAGELIST_MAX, // StageList size
};

enum TileLayerTypes {
    LAYER_NOSCROLL,
    LAYER_HSCROLL,
    LAYER_VSCROLL,
    LAYER_3DFLOOR,
    LAYER_3DSKY,
};

enum StageModes {
    STAGEMODE_LOAD,
    STAGEMODE_NORMAL,
    STAGEMODE_PAUSED,
};

enum TileInfo {
    TILEINFO_INDEX,
    TILEINFO_DIRECTION,
    TILEINFO_VISUALPLANE,
    TILEINFO_SOLIDITYA,
    TILEINFO_SOLIDITYB,
    TILEINFO_FLAGSA,
    TILEINFO_ANGLEA,
    TILEINFO_FLAGSB,
    TILEINFO_ANGLEB,
};

enum DeformationModes {
    DEFORM_FG,
    DEFORM_FG_WATER,
    DEFORM_BG,
    DEFORM_BG_WATER,
};

enum CameraStyles {
    CAMERASTYLE_FOLLOW,
    CAMERASTYLE_EXTENDED,
    CAMERASTYLE_EXTENDED_OFFSET_L,
    CAMERASTYLE_EXTENDED_OFFSET_R,
    CAMERASTYLE_HLOCKED,
};

#if RETRO_PLATFORM == RETRO_PS1
// PS1: sized from Sonic CD's GameConfig (lists of 9 / 70 / 8 / 0 stages; folder <= 7, id <= 1,
// name <= 26 chars): 16 KB instead of 197 KB. LoadGameConfig clamps (g_ps1StageListClamped).
#define STAGELIST_ENTRY_COUNT (0x50)
struct SceneInfo {
    char name[0x20];
    char folder[0x10];
    char id[0x10];
    bool highlighted;
};
#else
#define STAGELIST_ENTRY_COUNT (0x100)
struct SceneInfo {
    char name[0x40];
    char folder[0x40];
    char id[0x40];
    bool highlighted;
};
#endif

struct CollisionMasks {
    sbyte floorMasks[TILE_COUNT * TILE_SIZE];
    sbyte lWallMasks[TILE_COUNT * TILE_SIZE];
    sbyte rWallMasks[TILE_COUNT * TILE_SIZE];
    sbyte roofMasks[TILE_COUNT * TILE_SIZE];
    uint angles[TILE_COUNT];
    byte flags[TILE_COUNT];
};

struct TileLayer {
#if RETRO_PLATFORM == RETRO_PS1
    ushort *tiles; // TILELAYER_CHUNK_W x (layer 0: PS1_LAYER0_CHUNK_H, others TILELAYER_CHUNK_H) rows, Scene.cpp
#else
    ushort tiles[TILELAYER_CHUNK_COUNT];
#endif
    byte lineScroll[TILELAYER_SCROLL_COUNT];
    int parallaxFactor;
    int scrollSpeed;
    int scrollPos;
    int angle;
    int XPos;
    int YPos;
    int ZPos;
    int deformationOffset;
    int deformationOffsetW;
    byte type;
    byte xsize;
    byte ysize;
};

struct LineScroll {
    int parallaxFactor[PARALLAX_COUNT];
    int scrollSpeed[PARALLAX_COUNT];
    int scrollPos[PARALLAX_COUNT];
    int linePos[PARALLAX_COUNT];
    int deform[PARALLAX_COUNT];
    byte entryCount;
};

struct Tiles128x128 {
#if RETRO_PLATFORM != RETRO_PS1 // PS1: derived from tileIndex by the renderer (saves 128 KB)
    int gfxDataPos[CHUNKTILE_COUNT];
#endif
    ushort tileIndex[CHUNKTILE_COUNT];
    byte direction[CHUNKTILE_COUNT];
    byte visualPlane[CHUNKTILE_COUNT];
    byte collisionFlags[CPATH_COUNT][CHUNKTILE_COUNT];
};

extern int stageListCount[STAGELIST_MAX];
extern char stageListNames[STAGELIST_MAX][0x20];
extern SceneInfo stageList[STAGELIST_MAX][STAGELIST_ENTRY_COUNT];

extern int stageMode;

extern int cameraTarget;
extern int cameraStyle;
extern int cameraEnabled;
extern int cameraAdjustY;
extern int xScrollOffset;
extern int yScrollOffset;
extern int yScrollA;
extern int yScrollB;
extern int xScrollA;
extern int xScrollB;
extern int yScrollMove;
extern int cameraShakeX;
extern int cameraShakeY;
extern int cameraLag;
extern int cameraLagStyle;

extern int xBoundary1;
extern int newXBoundary1;
extern int yBoundary1;
extern int newYBoundary1;
extern int xBoundary2;
extern int yBoundary2;
extern int waterLevel;
extern int waterDrawPos;
extern int newXBoundary2;
extern int newYBoundary2;

extern int SCREEN_SCROLL_LEFT;
extern int SCREEN_SCROLL_RIGHT;
#define SCREEN_SCROLL_UP   ((SCREEN_YSIZE / 2) - 16)
#define SCREEN_SCROLL_DOWN ((SCREEN_YSIZE / 2) + 16)

extern int lastXSize;
extern int lastYSize;

extern bool pauseEnabled;
extern bool timeEnabled;
extern bool debugMode;
extern int frameCounter;
extern int stageMilliseconds;
extern int stageSeconds;
extern int stageMinutes;

// Category and Scene IDs
extern int activeStageList;
extern int stageListPosition;
extern char currentStageFolder[0x100];
extern int actID;

extern char titleCardText[0x100];
extern byte titleCardWord2;

extern byte activeTileLayers[4];
extern byte tLayerMidPoint;
extern TileLayer stageLayouts[LAYER_COUNT];

extern int bgDeformationData0[DEFORM_COUNT];
extern int bgDeformationData1[DEFORM_COUNT];
extern int bgDeformationData2[DEFORM_COUNT];
extern int bgDeformationData3[DEFORM_COUNT];

extern LineScroll hParallax;
extern LineScroll vParallax;

extern Tiles128x128 tiles128x128;
extern CollisionMasks collisionMasks[2];

#if RETRO_PLATFORM != RETRO_PS1 // PS1: tile pixels live only in VRAM (phase 3), never in RAM
extern byte tilesetGFXData[TILESET_SIZE];
#endif

#if RETRO_PLATFORM != RETRO_PS1 // PS1: software 3D floor buffer; the GTE floor is phase 7
extern ushort tile3DFloorBuffer[0x100 * 0x100];
#endif
extern bool drawStageGFXHQ;

void InitFirstStage();
void ProcessStage();

void ResetBackgroundSettings();
inline void ResetCurrentStageFolder() { strcpy(currentStageFolder, ""); }
inline bool CheckCurrentStageFolder(int stage)
{
    if (strcmp(currentStageFolder, stageList[activeStageList][stage].folder) == 0) {
        return true;
    }
    else {
        strcpy(currentStageFolder, stageList[activeStageList][stage].folder);
        return false;
    }
}

void LoadStageFiles();
int LoadActFile(const char *ext, int stageID, FileInfo *info);
int LoadStageFile(const char *filePath, int stageID, FileInfo *info);

void LoadActLayout();
void LoadStageBackground();
void LoadStageChunks();
void LoadStageCollisions();
void LoadStageGIFFile(int stageID);
void LoadStageGFXFile(int stageID);

#if RETRO_PLATFORM != RETRO_PS1
inline void Init3DFloorBuffer(int layerID)
{
    for (int y = 0; y < TILELAYER_CHUNK_H; ++y) {
        for (int x = 0; x < TILELAYER_CHUNK_W; ++x) {
            int c                           = stageLayouts[layerID].tiles[(x >> 3) + (y >> 3 << 8)] << 6;
            int tx                          = x & 7;
            tile3DFloorBuffer[x + (y << 8)] = c + tx + ((y & 7) << 3);
        }
    }
}

#endif

inline void Copy16x16Tile(ushort dest, ushort src)
{
#if RETRO_PLATFORM == RETRO_PS1
    void PS1Copy16x16Tile(int dest, int src); // ps1/render.cpp: VRAM-to-VRAM copy in the tile pages
    PS1Copy16x16Tile(dest, src);
    return;
#endif
#if RETRO_PLATFORM != RETRO_PS1
    if (renderType == RENDER_SW) {
        byte *destPtr = &tilesetGFXData[TILELAYER_CHUNK_W * dest];
        byte *srcPtr  = &tilesetGFXData[TILELAYER_CHUNK_W * src];
        int cnt       = TILE_DATASIZE;
        while (cnt--) *destPtr++ = *srcPtr++;
    }
    else
#endif
    if (renderType == RENDER_HW) {
        tileUVArray[4 * dest + 0] = tileUVArray[4 * src + 0];
        tileUVArray[4 * dest + 1] = tileUVArray[4 * src + 1];
        tileUVArray[4 * dest + 2] = tileUVArray[4 * src + 2];
        tileUVArray[4 * dest + 3] = tileUVArray[4 * src + 3];
    }
}

void SetLayerDeformation(int selectedDef, int waveLength, int waveType, int deformType, int YPos, int waveSize);

void SetPlayerScreenPosition(Player *player);
void SetPlayerScreenPositionCDStyle(Player *player);
void SetPlayerHLockedScreenPosition(Player *player);
void SetPlayerLockedScreenPosition(Player *player);

#endif // !SCENE_H
