#!/usr/bin/env python3
"""Sonic CD's videos (Theora .ogv, 640x368 @ 30 fps, two Vorbis tracks: JP and US soundtrack) -> PS1
MDEC STR streams with CD-XA audio (docs/28 phase 6.1). Golden rule: all conversion here; the PS1 only
Huffman-decodes (VLC) and runs the MDEC, the drive decodes the audio.

One STR per video carries **both** soundtracks (two copies of the video would not fit the disc: ~200 MB
each). The upstream player picks the audio stream by Options.Soundtrack (THEORAPLAY_startDecode: 0 =
first audio track = JP, 1 = second = US); the PS1 player selects XA channel 0 (JP) or 1 (US) with
Setfilter.
Layout, at 2x CD speed (150 sectors/s): psxavenc -t str with 8-bit 37.8 kHz stereo XA reserves 1 sector
in 4 for audio. Those slots are refilled alternately with the JP and US 4-bit XA sectors (each needs 1 in
8), so every soundtrack streams at its full rate and the video keeps 6 sectors in 8 (7-8 per frame at
15 fps). Video: MDEC BS v2, 320x176 (user decision: 320x176 @ 15 fps to start): the 640x368 picture at
306x176 (aspect kept) with 7-pixel black side bars, scaled by ffmpeg (lanczos).

Steps: ffmpeg (video + first audio, raw; the last frame held while a soundtrack is longer than the
picture) -> psxavenc -t str (-b 8: the slot layout); ffmpeg audio track 0
/ 1 -> psxavenc -t xa -b 4 on channel 0 / 1 -> the slots, alternating; unused slots silent; EOF submode
bits cleared; psxavenc's uninitialised padding cleared.
Output: Data/Videos/<Name>.str (2336-byte sectors, mkpsxiso type="mixed") + <Name>.sti:
  'STR2', u32 frames, u32 video (data) sectors, u8 xa file, u8 JP channel, u8 US channel, u8 0,
  u16 width, u16 height, u16 max RLE words (+1 command word) of any frame, u16 max sectors of a frame.
Self-check: the audio slots hold channels 0/1 alternately (1 in 8 each) and every video frame's sectors
are complete and in order.

Usage: build_str.py VIDEOS_DIR DATA_DIR
"""
import glob, os, struct, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'audio'))
import xa_adpcm  # noqa: E402

REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
PSXAVENC = os.environ.get('PSXAVENC') or os.path.join(REPO, '..', 'psxavenc', 'build', 'psxavenc')
FFMPEG = os.environ.get('FFMPEG') or 'ffmpeg'
FFPROBE = os.environ.get('FFPROBE') or 'ffprobe'
S = 2336
XA_FILE = 1
CH_JP, CH_US = 0, 1
WIDTH, HEIGHT = 320, 176
# The picture is scaled here, not by psxavenc: its own "fit within WxH" scaling left stray 8x8 blocks of
# bright colour in flat areas (the same blocks in ffmpeg's STR decode, so in the bitstream). 640x368 keeps
# its aspect ratio: 306x176, centred in 320 with black side bars.
SCALE = 'scale=306:176:flags=lanczos,pad=%d:%d:7:0:black' % (WIDTH, HEIGHT)


def run(cmd):
    subprocess.run(cmd, check=True)


def xa_sectors(path):
    x = open(path, 'rb').read()
    assert len(x) % S == 0, path
    return [bytearray(x[i:i + S]) for i in range(0, len(x), S)]


def build(src, out_dir, tmp):
    name = os.path.splitext(os.path.basename(src))[0]
    nut, base = os.path.join(tmp, 'v.nut'), os.path.join(tmp, 'v.str')
    tracks = subprocess.run([FFPROBE, '-v', 'error', '-select_streams', 'a', '-show_entries', 'stream=index', '-of', 'csv=p=0', src],
                            capture_output=True, text=True, check=True).stdout.split()
    audio = {}
    for track, ch in ((0, CH_JP), (1, CH_US)):  # one track only (Pencil_Test): both soundtracks hear it
        wav, xa = os.path.join(tmp, 'a%d.wav' % ch), os.path.join(tmp, 'a%d.xa' % ch)
        run([FFMPEG, '-v', 'error', '-y', '-i', src, '-map', '0:a:%d' % min(track, len(tracks) - 1), '-c:a', 'pcm_s16le', wav])
        run([PSXAVENC, '-q', '-t', 'xa', '-f', '37800', '-b', '4', '-c', '2', '-F', str(XA_FILE), '-C', str(ch), wav, xa])
        audio[ch] = xa_sectors(xa)
    # The soundtracks can run past the last picture (Bad_Ending's US track: 5.7 s), and the Theora streams
    # hold fewer frames than their duration says: the last frame is held until the longer soundtrack
    # ends, as the PC decoder plays both to their end. The hold is measured on the encoded stream and grown
    # until every audio sector has a slot. The layout pass's audio is padded to the same length:
    # psxavenc ends the stream with its shorter input.
    # Deterministic lengths (no -shortest: where it cuts depends on ffmpeg's buffering, so two runs could
    # hold the last frame differently and encode different streams): the picture is decoded first, its
    # frames counted, and the padded audio cut to a fixed duration from that count (-t is sample-exact).
    need = max(len(a) for a in audio.values()) / 18.75
    hold = 0.1
    vid, wav0 = os.path.join(tmp, 'v_only.nut'), os.path.join(tmp, 'a_pad.wav')
    for _ in range(3):
        # One thread for decoding and filtering: threaded decode + scale gave different pixels from run to run
        # (1 in 5 under load), 8 of 8 identical single-threaded.
        run([FFMPEG, '-v', 'error', '-y', '-threads', '1', '-i', src, '-filter_threads', '1', '-map', '0:v',
             '-vf', SCALE + ',tpad=stop_mode=clone:stop_duration=%.3f' % hold, '-c:v', 'rawvideo', '-pix_fmt', 'yuv420p', vid])
        probe = subprocess.run([FFPROBE, '-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_entries',
                                'stream=nb_read_frames,r_frame_rate', '-of', 'csv=p=0', vid],
                               capture_output=True, text=True, check=True).stdout.strip().split(',')
        num, den = (int(x) for x in probe[0].split('/'))
        frames = int(probe[1])
        # audio 1 s longer than the picture: psxavenc stops at its shorter input, so the picture ends the
        # stream with its last frame complete (these audio sectors are replaced below anyway)
        run([FFMPEG, '-v', 'error', '-y', '-i', src, '-map', '0:a:0', '-af', 'apad', '-t', '%.6f' % (frames * den / num + 1.0),
             '-c:a', 'pcm_s16le', wav0])
        run([FFMPEG, '-v', 'error', '-y', '-i', vid, '-i', wav0, '-map', '0:v', '-map', '1:a', '-c', 'copy', nut])
        run([PSXAVENC, '-q', '-t', 'str', '-v', 'v2', '-f', '37800', '-b', '8', '-c', '2', '-F', str(XA_FILE), '-C', str(CH_JP),
             '-s', '%dx%d' % (WIDTH, HEIGHT), '-r', '15', '-x', '2', nut, base])
        secs = xa_sectors(base)
        have = sum(1 for x in secs if x[2] & 0x04) / 2 / 18.75
        if have >= need:
            break
        hold += need - have + 0.1
    secs = xa_sectors(base)
    slots = [i for i, s in enumerate(secs) if s[2] & 0x04]
    assert all(i % 4 == 0 for i in slots), 'audio slots not 1 in 4'
    coding = audio[CH_JP][0][3]
    used = {CH_JP: 0, CH_US: 0}
    for j, i in enumerate(slots):
        ch = CH_JP if j % 2 == 0 else CH_US
        k = j // 2
        if k < len(audio[ch]):
            secs[i] = bytearray(audio[ch][k])
            used[ch] += 1
        else:
            secs[i] = bytearray(bytes([XA_FILE, ch, 0x64, coding] * 2).ljust(S, b'\0'))  # silent XA audio
        secs[i][2] &= 0x7F  # clear EOF
        secs[i][6] &= 0x7F
    for ch in (CH_JP, CH_US):  # audio longer than the video would be cut: at most a sector or two of rounding
        assert len(audio[ch]) - used[ch] <= 2, (name, ch, len(audio[ch]), used[ch])
    out = bytes(xa_adpcm.clear_unused(b''.join(secs)))
    # Self-check.
    video, frames, rle_max, frame_secs = 0, {}, 0, 0
    for i in range(len(out) // S):
        sub = out[i * S:i * S + 8]
        if sub[2] & 0x04:
            j = slots.index(i)
            assert sub[0] == XA_FILE and sub[1] == (CH_JP if j % 2 == 0 else CH_US) and i % 8 == (0 if j % 2 == 0 else 4), (name, i)
            continue
        video += 1
        magic, _, idx, count, fr = struct.unpack_from('<HHHHI', out, i * S + 8)
        assert magic == 0x0160, (name, i)
        frames.setdefault(fr, []).append(idx)
        frame_secs = max(frame_secs, count)
        if idx == 0:
            rle_max = max(rle_max, (struct.unpack_from('<I', out, i * S + 8 + 32)[0] & 0xFFFF) + 1)
    assert sorted(frames) == list(range(1, len(frames) + 1)), name
    for fr, idxs in frames.items():
        assert idxs == list(range(len(idxs))), (name, fr)
    open(os.path.join(out_dir, name + '.str'), 'wb').write(out)
    open(os.path.join(out_dir, name + '.sti'), 'wb').write(struct.pack('<4sIIBBBBHHHH', b'STR2', len(frames), video, XA_FILE, CH_JP,
                                                                       CH_US, 0, WIDTH, HEIGHT, rle_max, frame_secs))
    return '%-12s %6d sectors (%.1f MB), %4d frames (%.1f s), video %d sectors (max %d/frame), audio JP %d + US %d sectors, max RLE %d words' % (
        name, len(out) // S, len(out) / S * 2352 / 1048576, len(frames), len(frames) / 15, video, frame_secs, used[CH_JP], used[CH_US], rle_max)


def main():
    videos, data = sys.argv[1], sys.argv[2]
    out_dir = os.path.join(data, 'Videos')
    os.makedirs(out_dir, exist_ok=True)
    srcs = sorted(glob.glob(os.path.join(videos, '*.ogv')))
    if not srcs:
        sys.exit('ERROR: no .ogv in %s' % videos)
    with tempfile.TemporaryDirectory() as tmp:
        for src in srcs:
            print(build(src, out_dir, tmp), flush=True)


if __name__ == '__main__':
    main()
