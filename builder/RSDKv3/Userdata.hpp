#ifndef USERDATA_H
#define USERDATA_H

#define GLOBALVAR_COUNT (0x100)

#define ACHIEVEMENT_COUNT (0x40)
#define LEADERBOARD_COUNT (0x80)

#define MOD_COUNT (0x100)

#if RETRO_PLATFORM == RETRO_PS1
// Sonic CD's scripts use save RAM at 0..~300 (slots, options, time attack: the saved part) and 7168..8191
// (Stage Setup's per-stage scratch, cleared at every stage start). The PS1 keeps 2048 ints (was 32 KB):
// indices 0..1023 as they are, 7168..8191 at 1024..2047 (PS1SaveRamIndex); other script accesses read 0 /
// are dropped and counted (Script.cpp, g_ps1SaveRamOutOfRange). The card file holds 0..1023.
#define SAVEDATA_SIZE (0x800)
inline int PS1SaveRamIndex(int i) { return (uint)i < 0x400 ? i : (uint)(i - 0x1C00) < 0x400 ? i - 0x1800 : -1; }
#else
#define SAVEDATA_SIZE (0x2000)
#endif

enum OnlineMenuTypes {
    ONLINEMENU_ACHIEVEMENTS = 0,
    ONLINEMENU_LEADERBOARDS = 1,
};

struct Achievement {
    char name[0x40];
    int status;
};

struct LeaderboardEntry {
    int score;
};

extern int globalVariablesCount;
extern int globalVariables[GLOBALVAR_COUNT];
extern char globalVariableNames[GLOBALVAR_COUNT][0x20];

extern char gamePath[0x100];
extern int saveRAM[SAVEDATA_SIZE];
extern Achievement achievements[ACHIEVEMENT_COUNT];
extern LeaderboardEntry leaderboards[LEADERBOARD_COUNT];

extern int controlMode;
extern bool disableTouchControls;
extern int disableFocusPause;
extern int disableFocusPause_Config;

#if RETRO_USE_MOD_LOADER || !RETRO_USE_ORIGINAL_CODE
extern bool forceUseScripts;
extern bool forceUseScripts_Config;
#endif

inline int GetGlobalVariableByName(const char *name)
{
    for (int v = 0; v < globalVariablesCount; ++v) {
        if (StrComp(name, globalVariableNames[v]))
            return globalVariables[v];
    }
    return 0;
}

inline void SetGlobalVariableByName(const char *name, int value)
{
    for (int v = 0; v < globalVariablesCount; ++v) {
        if (StrComp(name, globalVariableNames[v])) {
            globalVariables[v] = value;
            break;
        }
    }
}

inline int GetGlobalVariableID(const char *name)
{
    for (int v = 0; v < globalVariablesCount; ++v) {
        if (StrComp(name, globalVariableNames[v]))
            return v;
    }
    return 0xFF;
}

extern bool useSGame;
bool ReadSaveRAMData();
bool WriteSaveRAMData();

void InitUserdata();
void WriteSettings();
void ReadUserdata();
void WriteUserdata();

void AwardAchievement(int id, int status);
void SetAchievement(int achievementID, int achievementDone);
void SetLeaderboard(int leaderboardID, int result);
inline void LoadAchievementsMenu() { ReadUserdata(); }
inline void LoadLeaderboardsMenu() { ReadUserdata(); }

#endif //! USERDATA_H
