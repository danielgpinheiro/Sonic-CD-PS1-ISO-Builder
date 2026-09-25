#ifndef AUDIO_H
#define AUDIO_H

#include <stdlib.h>

#if RETRO_PLATFORM != RETRO_PS1
#include <vorbis/vorbisfile.h>
#endif

#if RETRO_PLATFORM != RETRO_VITA && RETRO_PLATFORM != RETRO_OSX && RETRO_PLATFORM != RETRO_PS1
#include "SDL.h"
#endif

// PS1 port: no Ogg/SDL at runtime (music is CD-XA, SFX are SPU-ADPCM; docs/28 phase 5). These
// stand-ins keep the data structures and the inline helpers compiling (as in the RSDKv2 port).
#if RETRO_PLATFORM == RETRO_PS1
#include <stdint.h>
typedef int16_t Sint16;
typedef int32_t Sint32;
typedef uint8_t Uint8;
typedef uint16_t Uint16;
typedef struct { int unused; } OggVorbis_File;
#define ov_clear(f) ((void)0)
#endif

#if RETRO_USING_SDL1 || RETRO_USING_SDL2

#define LockAudioDevice()   SDL_LockAudio()
#define UnlockAudioDevice() SDL_UnlockAudio()

#else
#define LockAudioDevice()   ;
#define UnlockAudioDevice() ;
#endif

#define TRACK_COUNT   (0x10)
#if RETRO_PLATFORM == RETRO_PS1
#define SFX_COUNT (0x50) // Sonic CD loads at most 70 (Secrets: 28 global + 42 stage); LoadSfx skips ids past it
#else
#define SFX_COUNT     (0x100)
#endif
#define CHANNEL_COUNT (0x4)
#define SFXDATA_COUNT (0x400000)

#define MAX_VOLUME (100)

#define STREAMFILE_COUNT (2)

#define MIX_BUFFER_SAMPLES (256)

struct TrackInfo {
    char fileName[0x40];
    bool trackLoop;
    uint loopPoint;
};

struct StreamInfo {
    OggVorbis_File vorbisFile;
    int vorbBitstream;
#if RETRO_USING_SDL1
    SDL_AudioSpec spec;
#endif
#if RETRO_USING_SDL2
    SDL_AudioStream *stream;
#endif
    Sint16 buffer[MIX_BUFFER_SAMPLES];
    bool trackLoop;
    uint loopPoint;
    bool loaded;
};

struct SFXInfo {
    char name[0x40];
    Sint16 *buffer;
    size_t length;
    bool loaded;
#if RETRO_PLATFORM == RETRO_PS1
    uint32_t spuAddr; // SPU-ADPCM sample in SPU RAM (build-time .vag, tools/audio/build_sfx.py)
    uint32_t rate;
#endif
};

struct ChannelInfo {
    size_t sampleLength;
    Sint16 *samplePtr;
    int sfxID;
    byte loopSFX;
    sbyte pan;
};

struct StreamFile {
    byte *buffer;
    int fileSize;
    int filePos;
};

enum MusicStatuses {
    MUSIC_STOPPED = 0,
    MUSIC_PLAYING = 1,
    MUSIC_PAUSED  = 2,
    MUSIC_LOADING = 3,
    MUSIC_READY   = 4,
};

extern int globalSFXCount;
extern int stageSFXCount;

extern int masterVolume;
extern int trackID;
extern int sfxVolume;
extern int bgmVolume;
extern bool audioEnabled;

extern int nextChannelPos;
extern bool musicEnabled;
extern int musicStatus;
extern TrackInfo musicTracks[TRACK_COUNT];
extern SFXInfo sfxList[SFX_COUNT];

extern ChannelInfo sfxChannels[CHANNEL_COUNT];

extern int currentStreamIndex;
extern StreamFile streamFile[STREAMFILE_COUNT];
extern StreamInfo streamInfo[STREAMFILE_COUNT];
extern StreamFile *streamFilePtr;
extern StreamInfo *streamInfoPtr;

#if RETRO_USING_SDL1 || RETRO_USING_SDL2
extern SDL_AudioSpec audioDeviceFormat;
#endif

int InitAudioPlayback();
void LoadGlobalSfx();

#if RETRO_USING_SDL1 || RETRO_USING_SDL2
void ProcessMusicStream(void *data, Sint16 *stream, int len);
void ProcessAudioPlayback(void *data, Uint8 *stream, int len);
void ProcessAudioMixing(Sint32 *dst, const Sint16 *src, int len, int volume, sbyte pan);

inline void FreeMusInfo()
{
    LockAudioDevice();

#if RETRO_USING_SDL2
    if (streamInfo[currentStreamIndex].stream)
        SDL_FreeAudioStream(streamInfo[currentStreamIndex].stream);
#endif
    ov_clear(&streamInfo[currentStreamIndex].vorbisFile);
#if RETRO_USING_SDL2
    streamInfo[currentStreamIndex].stream = nullptr;
#endif
    if (streamFile[currentStreamIndex].buffer)
        free(streamFile[currentStreamIndex].buffer);
    streamFile[currentStreamIndex].buffer = NULL;

    UnlockAudioDevice();
}
#else
// inline: defined in a header (upstream had plain definitions here, one per including file).
inline void ProcessMusicStream() {}
inline void ProcessAudioPlayback() {}
inline void ProcessAudioMixing() {}

#if RETRO_PLATFORM == RETRO_PS1
void PS1MusicStop(); // stops the CD-XA track (ps1/xa_music)
void PS1MusicPause(bool pause);
inline void FreeMusInfo()
{
    streamInfo[currentStreamIndex].loaded = false;
    PS1MusicStop();
}
#else
inline void FreeMusInfo() { ov_clear(&streamInfo[currentStreamIndex].vorbisFile); }
#endif
#endif

#if RETRO_USE_MOD_LOADER
extern char globalSfxNames[SFX_COUNT][0x40];
extern char stageSfxNames[SFX_COUNT][0x40];
void SetSfxName(const char *sfxName, int sfxID, bool global);
#endif

void LoadMusic();
void SetMusicTrack(char *filePath, byte trackID, bool loop, uint loopPoint);
bool PlayMusic(int track);
inline void StopMusic()
{
    musicStatus = MUSIC_STOPPED;
    FreeMusInfo();
}

void LoadSfx(char *filePath, byte sfxID);
void PlaySfx(int sfx, bool loop);
#if RETRO_PLATFORM == RETRO_PS1
// RSDK sfx channel c plays on an SPU voice (ps1/spu); SPU RAM is a bump allocator: global sfx, then
// the stage's (released when the stage folder changes).
void PS1SfxChannelStop(int channel);
void PS1SfxReleaseStage();
void PS1SfxReleaseGlobal();
void PS1AudioUpdate();     // once per frame: frees channels whose sample ended (PC mixer semantics), music volume
void PS1SpuDebugService(); // GDB: g_ps1SpuDumpAddr/Len -> SPU RAM copied into a heap buffer
#endif
inline void StopSfx(int sfx)
{
    for (int i = 0; i < CHANNEL_COUNT; ++i) {
        if (sfxChannels[i].sfxID == sfx) {
#if RETRO_PLATFORM == RETRO_PS1
            PS1SfxChannelStop(i);
#endif
            MEM_ZERO(sfxChannels[i]);
            sfxChannels[i].sfxID = -1;
        }
    }
}
void SetSfxAttributes(int sfx, int loopCount, sbyte pan);

inline void SetMusicVolume(int volume)
{
    if (volume < 0)
        volume = 0;
    if (volume > MAX_VOLUME)
        volume = MAX_VOLUME;
    masterVolume = volume;
}

inline bool PauseSound()
{
    if (musicStatus == MUSIC_PLAYING) {
        musicStatus = MUSIC_PAUSED;
#if RETRO_PLATFORM == RETRO_PS1
        PS1MusicPause(true);
#endif
        return true;
    }
    return false;
}

inline void ResumeSound()
{
    if (musicStatus == MUSIC_PAUSED) {
        musicStatus = MUSIC_PLAYING;
#if RETRO_PLATFORM == RETRO_PS1
        PS1MusicPause(false);
#endif
    }
}

inline void StopAllSfx()
{
    for (int i = 0; i < CHANNEL_COUNT; ++i) {
#if RETRO_PLATFORM == RETRO_PS1
        PS1SfxChannelStop(i);
#endif
        sfxChannels[i].sfxID = -1;
    }
}
inline void ReleaseGlobalSfx()
{
    StopAllSfx();
    for (int i = globalSFXCount - 1; i >= 0; --i) {
        if (sfxList[i].loaded) {
            StrCopy(sfxList[i].name, "");
            free(sfxList[i].buffer);
            sfxList[i].length = 0;
            sfxList[i].loaded = false;
        }
    }
    globalSFXCount = 0;
#if RETRO_PLATFORM == RETRO_PS1
    PS1SfxReleaseGlobal();
#endif
}
inline void ReleaseStageSfx()
{
    for (int i = stageSFXCount + globalSFXCount; i >= globalSFXCount; --i) {
        if (sfxList[i].loaded) {
            StrCopy(sfxList[i].name, "");
            free(sfxList[i].buffer);
            sfxList[i].length = 0;
            sfxList[i].loaded = false;
        }
    }
    stageSFXCount = 0;
#if RETRO_PLATFORM == RETRO_PS1
    PS1SfxReleaseStage();
#endif
}

inline void ReleaseAudioDevice()
{
    StopMusic();
    StopAllSfx();
    ReleaseStageSfx();
    ReleaseGlobalSfx();
}

#endif // !AUDIO_H
