#include "RetroEngine.hpp"

int objectLoop    = 0;
int curObjectType = 0;
Entity objectEntityList[ENTITY_COUNT];

char typeNames[OBJECT_COUNT][0x40];

int OBJECT_BORDER_X1       = 0x80;
int OBJECT_BORDER_X2       = 0;
const int OBJECT_BORDER_Y1 = 0x100;
const int OBJECT_BORDER_Y2 = SCREEN_YSIZE + 0x100;

void SetObjectTypeName(const char *objectName, int objectID)
{
    int objNameID  = 0;
    int typeNameID = 0;
    while (objectName[objNameID]) {
        if (objectName[objNameID] != ' ')
            typeNames[objectID][typeNameID++] = objectName[objNameID];
        ++objNameID;
    }
    typeNames[objectID][typeNameID] = 0;
    PrintLog("Set Object (%d) name to: %s", objectID, objectName);
}

void ProcessStartupObjects()
{
    scriptFrameCount = 0;
    ClearAnimationData();
    activePlayer               = 0;
    activePlayerCount          = 1;
    scriptEng.arrayPosition[2] = TEMPENTITY_START;
    Entity *entity             = &objectEntityList[TEMPENTITY_START];
    for (int i = 0; i < OBJECT_COUNT; ++i) {
        ObjectScript *scriptInfo    = &objectScriptList[i];
        objectLoop                  = TEMPENTITY_START;
        curObjectType               = i;
        scriptInfo->frameListOffset = scriptFrameCount;
        scriptInfo->spriteSheetID   = 0;
        entity->type                = i;
#if RETRO_PLATFORM == RETRO_PS1
        // Sonic CD's main menu buttons: the mobile, offline set (no LEADERBOARDS / ACHIEVEMENTS; Script.cpp).
        extern int g_ps1PlatformOverride;
        g_ps1PlatformOverride = StrComp(typeNames[i], "MenuButton") ? RETRO_ANDROID : -1;
#endif
        if (scriptCode[scriptInfo->subStartup.scriptCodePtr] > 0)
            ProcessScript(scriptInfo->subStartup.scriptCodePtr, scriptInfo->subStartup.jumpTablePtr, SUB_SETUP);
#if RETRO_PLATFORM == RETRO_PS1
        g_ps1PlatformOverride = -1;
#endif
        scriptInfo->frameCount = scriptFrameCount - scriptInfo->frameListOffset;
    }
    entity->type  = 0;
    curObjectType = 0;
}

void ProcessObjects()
{
    for (int i = 0; i < DRAWLAYER_COUNT; ++i) drawListEntries[i].listSize = 0;

    for (objectLoop = 0; objectLoop < ENTITY_COUNT; ++objectLoop) {
        bool active = false;
        int x = 0, y = 0;
        Entity *entity = &objectEntityList[objectLoop];
#if RETRO_PLATFORM == RETRO_PS1
        // A blank slot does nothing below (the priority switch only decides whether a typed object runs;
        // BOUNDS_DESTROY would blank it again): skipping it saves ~50 hblanks a frame over 1,056 slots.
        // A run of blank slots is passed over by a scan of the type bytes (docs/28 speed pass 2: the loop's own
        // step loads and stores the global objectLoop, 14 instructions a slot); objectLoop ends as the loop leaves it.
        if (entity->type == OBJ_TYPE_BLANKOBJECT) {
            const Entity *e = entity + 1, *end = &objectEntityList[ENTITY_COUNT];
            while (e != end && e->type == OBJ_TYPE_BLANKOBJECT) ++e;
            objectLoop = (int)(e - objectEntityList) - 1;
            continue;
        }
#endif
        switch (entity->priority) {
            case PRIORITY_BOUNDS:
                x      = entity->XPos >> 16;
                y      = entity->YPos >> 16;
                active = x > xScrollOffset - OBJECT_BORDER_X1 && x < OBJECT_BORDER_X2 + xScrollOffset && y > yScrollOffset - OBJECT_BORDER_Y1
                         && y < yScrollOffset + OBJECT_BORDER_Y2;
                break;

            case PRIORITY_ACTIVE:
            case PRIORITY_ALWAYS: active = true; break;

            case PRIORITY_XBOUNDS:
                x      = entity->XPos >> 16;
                active = x > xScrollOffset - OBJECT_BORDER_X1 && x < OBJECT_BORDER_X2 + xScrollOffset;
                break;

            case PRIORITY_BOUNDS_DESTROY:
                x = entity->XPos >> 16;
                y = entity->YPos >> 16;
                if (x <= xScrollOffset - OBJECT_BORDER_X1 || x >= OBJECT_BORDER_X2 + xScrollOffset || y <= yScrollOffset - OBJECT_BORDER_Y1
                    || y >= yScrollOffset + OBJECT_BORDER_Y2) {
                    active       = false;
                    entity->type = OBJ_TYPE_BLANKOBJECT;
                }
                else {
                    active = true;
                }
                break;

            case PRIORITY_INACTIVE: active = false; break;

            default: break;
        }

        if (active && entity->type > OBJ_TYPE_BLANKOBJECT) {
            ObjectScript *scriptInfo = &objectScriptList[entity->type];
            activePlayer             = 0;
            if (scriptCode[scriptInfo->subMain.scriptCodePtr] > 0)
                ProcessScript(scriptInfo->subMain.scriptCodePtr, scriptInfo->subMain.jumpTablePtr, SUB_MAIN);
            if (scriptCode[scriptInfo->subPlayerInteraction.scriptCodePtr] > 0) {
                while (activePlayer < activePlayerCount) {
                    if (playerList[activePlayer].objectInteractions)
                        ProcessScript(scriptInfo->subPlayerInteraction.scriptCodePtr, scriptInfo->subPlayerInteraction.jumpTablePtr,
                                      SUB_PLAYERINTERACTION);
                    ++activePlayer;
                }
            }

            if (entity->drawOrder < DRAWLAYER_COUNT)
                drawListEntries[entity->drawOrder].entityRefs[drawListEntries[entity->drawOrder].listSize++] = objectLoop;
        }
    }
}

void ProcessPausedObjects()
{
    for (int i = 0; i < DRAWLAYER_COUNT; ++i) drawListEntries[i].listSize = 0;

    for (objectLoop = 0; objectLoop < ENTITY_COUNT; ++objectLoop) {
        Entity *entity = &objectEntityList[objectLoop];
#if RETRO_PLATFORM == RETRO_PS1
        if (entity->type == OBJ_TYPE_BLANKOBJECT) { // a run of blank slots (as in ProcessObjects)
            const Entity *e = entity + 1, *end = &objectEntityList[ENTITY_COUNT];
            while (e != end && e->type == OBJ_TYPE_BLANKOBJECT) ++e;
            objectLoop = (int)(e - objectEntityList) - 1;
            continue;
        }
#endif

        if (entity->priority == PRIORITY_ALWAYS && entity->type > OBJ_TYPE_BLANKOBJECT) {
            ObjectScript *scriptInfo = &objectScriptList[entity->type];
            activePlayer             = 0;
            if (scriptCode[scriptInfo->subMain.scriptCodePtr] > 0)
                ProcessScript(scriptInfo->subMain.scriptCodePtr, scriptInfo->subMain.jumpTablePtr, SUB_MAIN);
            if (scriptCode[scriptInfo->subPlayerInteraction.scriptCodePtr] > 0) {
                while (activePlayer < PLAYER_COUNT) {
                    if (playerList[activePlayer].objectInteractions)
                        ProcessScript(scriptInfo->subPlayerInteraction.scriptCodePtr, scriptInfo->subPlayerInteraction.jumpTablePtr,
                                      SUB_PLAYERINTERACTION);
                    ++activePlayer;
                }
            }

            if (entity->drawOrder < DRAWLAYER_COUNT)
                drawListEntries[entity->drawOrder].entityRefs[drawListEntries[entity->drawOrder].listSize++] = objectLoop;
        }
    }
}