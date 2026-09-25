/*
 * Stubs for engine symbols that Script.cpp / Reader.cpp / Object.cpp / Animation.cpp reference but the
 * manifest tool never needs at runtime (drawing, audio, collision, 3D, menus, ...). Variables and
 * function stubs are generated from the linker's undefined-symbol list + the engine headers
 * (regenerate if the engine changes); AddGraphicsFile and LoadStageFile are real (bottom).
 */
#include <stdarg.h>
#include "RetroEngine.hpp"

RetroEngine Engine;

decltype(SCREEN_CENTERX) SCREEN_CENTERX{};
decltype(SCREEN_XSIZE) SCREEN_XSIZE{};
decltype(actID) actID{};
decltype(activePalette) activePalette{};
decltype(activePalette32) activePalette32{};
decltype(activePlayer) activePlayer{};
decltype(activePlayerCount) activePlayerCount{};
decltype(activeStageList) activeStageList{};
decltype(activeTileLayers) activeTileLayers{};
decltype(anyPress) anyPress{};
decltype(bgDeformationData0) bgDeformationData0{};
decltype(bgDeformationData1) bgDeformationData1{};
decltype(bgDeformationData2) bgDeformationData2{};
decltype(bgDeformationData3) bgDeformationData3{};
decltype(bgmVolume) bgmVolume{};
decltype(cameraAdjustY) cameraAdjustY{};
decltype(cameraEnabled) cameraEnabled{};
decltype(cameraShakeX) cameraShakeX{};
decltype(cameraShakeY) cameraShakeY{};
decltype(cameraStyle) cameraStyle{};
decltype(cameraTarget) cameraTarget{};
decltype(collisionMasks) collisionMasks{};
decltype(collisionStorage) collisionStorage{};
decltype(debugMode) debugMode{};
decltype(drawListEntries) drawListEntries{};
decltype(faceBuffer) faceBuffer{};
decltype(faceCount) faceCount{};
decltype(fadeA) fadeA{};
decltype(fadeB) fadeB{};
decltype(fadeG) fadeG{};
decltype(fadeMode) fadeMode{};
decltype(fadeR) fadeR{};
decltype(fullPalette) fullPalette{};
decltype(fullPalette32) fullPalette32{};
decltype(gameMenu) gameMenu{};
decltype(gfxDataPosition) gfxDataPosition{};
decltype(gfxLineBuffer) gfxLineBuffer{};
decltype(gfxSurface) gfxSurface{};
decltype(globalSFXCount) globalSFXCount{};
decltype(globalVariableNames) globalVariableNames{};
decltype(globalVariables) globalVariables{};
decltype(globalVariablesCount) globalVariablesCount{};
decltype(hParallax) hParallax{};
decltype(keyDown) keyDown{};
decltype(keyPress) keyPress{};
decltype(masterVolume) masterVolume{};
decltype(matTemp) matTemp{};
decltype(matView) matView{};
decltype(matWorld) matWorld{};
decltype(musicStatus) musicStatus{};
decltype(newXBoundary1) newXBoundary1{};
decltype(newXBoundary2) newXBoundary2{};
decltype(newYBoundary1) newYBoundary1{};
decltype(newYBoundary2) newYBoundary2{};
decltype(pauseEnabled) pauseEnabled{};
decltype(playerList) playerList{};
decltype(playerListPos) playerListPos{};
decltype(projectionX) projectionX{};
decltype(projectionY) projectionY{};
decltype(renderType) renderType{};
decltype(saveRAM) saveRAM{};
decltype(sfxChannels) sfxChannels{};
decltype(sfxVolume) sfxVolume{};
decltype(stageLayouts) stageLayouts{};
#if RETRO_PLATFORM == RETRO_PS1 // TileLayer::tiles is a pointer on PS1 (Scene.hpp): the same backing as Scene.cpp
static ushort s_hostLayerTiles[LAYER_COUNT][TILELAYER_CHUNK_W * PS1_LAYER0_CHUNK_H];
static struct HostLayerTiles {
    HostLayerTiles() { for (int i = 0; i < LAYER_COUNT; ++i) stageLayouts[i].tiles = s_hostLayerTiles[i]; }
} s_hostLayerTilesInit;
#endif
decltype(stageList) stageList{};
decltype(stageListCount) stageListCount{};
decltype(stageListPosition) stageListPosition{};
decltype(stageMilliseconds) stageMilliseconds{};
decltype(stageMinutes) stageMinutes{};
decltype(stageMode) stageMode{};
decltype(stageSeconds) stageSeconds{};
decltype(tLayerMidPoint) tLayerMidPoint{};
decltype(texPaletteNum) texPaletteNum{};
decltype(textMenuSurfaceNo) textMenuSurfaceNo{};
decltype(tileUVArray) tileUVArray{};
decltype(tiles128x128) tiles128x128{};
decltype(timeEnabled) timeEnabled{};
decltype(titleCardText) titleCardText{};
decltype(titleCardWord2) titleCardWord2{};
decltype(touchDown) touchDown{};
decltype(touchX) touchX{};
decltype(touchY) touchY{};
decltype(touches) touches{};
decltype(trackID) trackID{};
decltype(vParallax) vParallax{};
decltype(vertexBuffer) vertexBuffer{};
decltype(vertexCount) vertexCount{};
decltype(waterLevel) waterLevel{};
decltype(xBoundary1) xBoundary1{};
decltype(xBoundary2) xBoundary2{};
decltype(xScrollA) xScrollA{};
decltype(xScrollB) xScrollB{};
decltype(xScrollOffset) xScrollOffset{};
decltype(yBoundary1) yBoundary1{};
decltype(yBoundary2) yBoundary2{};
decltype(yScrollA) yScrollA{};
decltype(yScrollB) yScrollB{};
decltype(yScrollOffset) yScrollOffset{};

int AddDebugHitbox(byte type, Entity *entity, int left, int top, int right, int bottom) { return {}; }
void AddTextMenuEntry(TextMenu *menu, const char *text) { }
void BoxCollision(int left, int top, int right, int bottom) { }
void BoxCollision2(int left, int top, int right, int bottom) { }
void BoxCollision3(int left, int top, int right, int bottom) { }
void ClearScreen(byte index) { }
void Draw3DScene(int spriteSheetID) { }
void DrawAdditiveBlendedSprite(int XPos, int YPos, int width, int height, int sprX, int sprY, int alpha, int sheetID) { }
void DrawAlphaBlendedSprite(int XPos, int YPos, int width, int height, int sprX, int sprY, int alpha, int sheetID) { }
void DrawBitmapText(void *menu, int XPos, int YPos, int scale, int spacing, int rowStart, int rowCount) { }
void DrawBlendedSprite(int XPos, int YPos, int width, int height, int sprX, int sprY, int sheetID) { }
void DrawObjectAnimation(void *objScr, void *ent, int XPos, int YPos) { }
void DrawRectangle(int XPos, int YPos, int width, int height, int R, int G, int B, int A) { }
void DrawScaledTintMask(int direction, int XPos, int YPos, int pivotX, int pivotY, int scaleX, int scaleY, int width, int height, int sprX, int sprY,
                        int sheetID) { }
void DrawSprite(int XPos, int YPos, int width, int height, int sprX, int sprY, int sheetID) { }
void DrawSpriteFlipped(int XPos, int YPos, int width, int height, int sprX, int sprY, int direction, int sheetID) { }
void DrawSpriteRotated(int direction, int XPos, int YPos, int pivotX, int pivotY, int sprX, int sprY, int width, int height, int rotation,
                       int sheetID) { }
void DrawSpriteRotozoom(int direction, int XPos, int YPos, int pivotX, int pivotY, int sprX, int sprY, int width, int height, int rotation, int scale,
                        int sheetID) { }
void DrawSpriteScaled(int direction, int XPos, int YPos, int pivotX, int pivotY, int scaleX, int scaleY, int width, int height, int sprX, int sprY,
                      int sheetID) { }
void DrawSubtractiveBlendedSprite(int XPos, int YPos, int width, int height, int sprX, int sprY, int alpha, int sheetID) { }
void DrawTextMenu(void *menu, int XPos, int YPos) { }
void DrawTintRectangle(int XPos, int YPos, int width, int height) { }
void EditTextMenuEntry(TextMenu *menu, const char *text, int rowID) { }
void EnemyCollision(int left, int top, int right, int bottom) { }
void LoadFontFile(const char *filePath) { }
void LoadPalette(const char *filePath, int paletteID, int startPaletteIndex, int startIndex, int endIndex) { }
void LoadTextFile(TextMenu *menu, const char *filePath, byte mapCode) { }
void MatrixMultiply(Matrix *matrixA, Matrix *matrixB) { }
void MatrixRotateX(Matrix *matrix, int rotationX) { }
void MatrixRotateXYZ(Matrix *matrix, int rotationX, int rotationY, int rotationZ) { }
void MatrixRotateY(Matrix *matrix, int rotationY) { }
void MatrixRotateZ(Matrix *matrix, int rotationZ) { }
void MatrixScaleXYZ(Matrix *matrix, int scaleX, int scaleY, int scaleZ) { }
void MatrixTranslateXYZ(Matrix *Matrix, int x, int y, int z) { }
void ObjectEntityGrip(int direction, int extendBottomCol, int effect) { }
void ObjectFloorCollision(int xOffset, int yOffset, int cPath) { }
void ObjectFloorGrip(int xOffset, int yOffset, int cPath) { }
void ObjectLWallCollision(int xOffset, int yOffset, int cPath) { }
void ObjectLWallGrip(int xOffset, int yOffset, int cPath) { }
void ObjectRWallCollision(int xOffset, int yOffset, int cPath) { }
void ObjectRWallGrip(int xOffset, int yOffset, int cPath) { }
void ObjectRoofCollision(int xOffset, int yOffset, int cPath) { }
void ObjectRoofGrip(int xOffset, int yOffset, int cPath) { }
void PlatformCollision(int left, int top, int right, int bottom) { }
bool PlayMusic(int track) { return {}; }
void PlaySfx(int sfx, bool loop) { }
void PlayVideoFile(char *filepath) { }
void PrintLog(const char *msg, ...) { }
void ProcessPlayerControl(Player *player) { }
void ProcessPlayerTileCollisions(Player *player) { }
bool ReadSaveRAMData() { return {}; }
void ReadUserdata() { }
void RemoveGraphicsFile(const char *filePath, int sheetID) { }
void RetroEngine::Callback(int callbackID) { }
void SetAchievement(int achievementID, int achievementDone) { }
void SetIdentityMatrix(Matrix *matrix) { }
void SetLayerDeformation(int selectedDef, int waveLength, int waveType, int deformType, int YPos, int waveSize) { }
void SetLeaderboard(int leaderboardID, int result) { }
void SetLimitedFade(byte paletteID, byte R, byte G, byte B, ushort alpha, int startIndex, int endIndex) { }
void SetMusicTrack(char *filePath, byte trackID, bool loop, uint loopPoint) { }
void SetSfxAttributes(int sfx, int loopCount, sbyte pan) { }
// PS1 audio hooks (Audio.hpp inline helpers call them; RSDKv3/Audio.cpp is not in this host build).
void PS1MusicStop() { }
void PS1MusicPause(bool pause) { }
void PS1SfxChannelStop(int channel) { }
void PS1SfxReleaseStage() { }
void PS1SfxReleaseGlobal() { }
int currentStreamIndex = 0;
StreamInfo streamInfo[STREAMFILE_COUNT];
void SetupTextMenu(TextMenu *menu, int rowCount) { }
void Sort3DDrawList() { }
void TouchCollision(int left, int top, int right, int bottom) { }
void TransformVertexBuffer() { }
void TransformVerticies(Matrix *matrix, int startIndex, int endIndex) { }
void UpdateVideoFrame() { }
bool WriteSaveRAMData() { return {}; }

// Real: register a sheet name (like Sprite.cpp AddGraphicsFile), never decode the image.
int AddGraphicsFile(const char *filePath) {
    char sheetPath[0x100];
    StrCopy(sheetPath, "Data/Sprites/");
    StrAdd(sheetPath, filePath);
    int sheetID = 0;
    while (StrLength(gfxSurface[sheetID].fileName) > 0) {
        if (StrComp(gfxSurface[sheetID].fileName, sheetPath))
            return sheetID;
        if (++sheetID == SURFACE_COUNT)
            return 0;
    }
    StrCopy(gfxSurface[sheetID].fileName, sheetPath);
    return sheetID;
}

// Real: Scene.cpp LoadStageFile (Data/Stages/<folder>/<file>).
int LoadStageFile(const char *filePath, int stageID, FileInfo *info) {
    char dest[0x40];
    StrCopy(dest, "Data/Stages/");
    StrAdd(dest, stageList[activeStageList][stageID].folder);
    StrAdd(dest, "/");
    StrAdd(dest, filePath);
    return LoadFile(dest, info);
}

// PS1 profiling clock (ps1/video.cpp) used by Script.cpp's Draw3DScene profile.
uint32_t PS1Hblanks() { return 0; }
uint32_t PS1HblanksSince(uint32_t) { return 0; }

// Renderer hook (ps1/render.cpp): a script changed a chunk tile.
void PS1TileChanged(int) {}

// Renderer hook (ps1/render.cpp): upstream Copy16x16Tile on PS1 copies tile pixels in VRAM.
void PS1Copy16x16Tile(int, int) {}
