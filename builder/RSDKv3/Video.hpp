#ifndef VIDEO_H
#define VIDEO_H

#if RETRO_PLATFORM == RETRO_PS1
// PS1 port: the .ogv videos become MDEC/STR streams at build time (docs/28 phase 6); no Theora at
// runtime. Opaque stand-ins keep the declarations below compiling.
struct THEORAPLAY_Decoder;
struct THEORAPLAY_VideoFrame;
struct THEORAPLAY_AudioPacket;
struct THEORAPLAY_Io {
    void *userdata;
};
#else
#include "theoraplay.h"
#endif

extern int currentVideoFrame;
extern int videoFrameCount;
extern int videoWidth;
extern int videoHeight;
extern float videoAR;

extern THEORAPLAY_Decoder *videoDecoder;
extern const THEORAPLAY_VideoFrame *videoVidData;
extern const THEORAPLAY_AudioPacket *videoAudioData;
extern THEORAPLAY_Io callbacks;

extern byte videoSurface;
extern int videoFilePos;
extern int videoPlaying; // 0 = not playing, 1 = playing OGV, 2 = playing RSV
extern int vidFrameMS;
extern int vidBaseticks;
extern float videoAR;

void PlayVideoFile(char *filepath);
void UpdateVideoFrame();
int ProcessVideo();
void StopVideoPlayback();

void SetupVideoBuffer(int width, int height);
void CloseVideoBuffer();

#endif // !VIDEO_H
