# Changelog

Updates to the Sonic CD PS1 ISO Builder, newest first. To get an update, rebuild your disc image with the new
version of the builder (same steps as in the [README](README.md)).

## Loading icon protection (October 2026)

- **The loading icon now waits while a stage load is copying graphics into video memory.** Two copies at the same time
  stop the game; in the Sonic 1 port this froze the end credits on a black screen in the PCSX-ReARMed emulator. It never
  happened in Sonic CD, but Sonic CD had the same weak spot, so it gets the same fix. Nothing else changes.
- The title screen shows the new build, `v ff4d78c5` (the RSDKv3-ps1 port's commit `ff4d78c`).
- Checked with the port's automated tests in PCSX-Redux and DuckStation. The image's SHA-256 changes (the new value is
  in the README's Output section).

## Sonic's sprite no longer shifts while looking up facing left (October 2026)

- **Looking up while facing left, part of Sonic's sprite (his leg) moved between the animation's frames.** One frame
  sat at the left edge of a texture page in video memory, and a mirrored sprite there was drawn from one column too
  few (one column doubled, the rest shifted by a pixel). The disc builder now moves the player's sprites off that edge
  into free room, without moving anything else; a few may still sit there in crowded stages.
- The title screen shows the new build, `v 6e0098f4` (the RSDKv3-ps1 port's commit `6e0098f`).
- Checked with the port's automated tests in PCSX-Redux and DuckStation (a new test checks the look-up frames in every
  stage). The image's SHA-256 changes (the new value is in the README's Output section).

## Flip-bit sprites on newer consoles (October 2026)

- **On consoles with the newer GPU (every PSone, most later PlayStations), mirrored sprites drawn at their own size
  are now drawn with the GPU's own flip feature** (Sonic facing left included), as mirrored level tiles already were,
  instead of as textured four-corner shapes: less GPU work. Rotated and scaled sprites are drawn as before.
- The start-up check is stricter: the game first asks the GPU its version (nocash's GPU detection; the earliest
  consoles' GPU lacks the flip feature and never uses it), then keeps the existing test drawing read back from video
  memory, so an emulator that reports a newer GPU but doesn't draw the flips (some versions of PCSX ReARMed) still
  gets the old drawing. The previous check could, in a rare case, misread an old GPU's answer.
- The picture is the same either way: checked frame by frame in the DuckStation preview build, which draws the flip
  feature, against the old way of drawing (Palmtree Panic, Tidal Tempest). Not yet tested on a console.
- The title screen shows the new build, `v e6c25db3` (the RSDKv3-ps1 port's commit `e6c25db`).
- Checked with the port's automated tests in PCSX-Redux and DuckStation. The image's SHA-256 changes (the new value is
  in the README's Output section).

## Build stamp on the title screen (October 2026)

- **The title screen shows which build you are playing:** a small grey line in its bottom-left corner, e.g.
  `v 88949dae`. It is the commit of the RSDKv3-ps1 port the executable was built from, so a screenshot or a quick look
  tells which version runs in DuckStation, PCSX-Redux or on a console. It appears only on the title screen and fades
  in and out with it.
- The builder writes it to a small `VERSION.TXT` file at the root of the disc (from `bin/VERSION.TXT`, which comes
  with each update together with the executable). A disc without that file shows `v unknown`.
- Checked with the port's automated tests in PCSX-Redux and DuckStation (the title's frame time stays within its
  limits). Not yet tested on a console.
- The image's SHA-256 changes (the new value is in the README's Output section).

## Rotated and mirrored sprites: no stray lines at their edges (October 2026)

- **No more stray lines next to Sonic:** a thin line (often white or yellow) could appear along one edge of Sonic's
  sprite when he faced left, ran through loops and quarter pipes, or was upside down. It came from the pixels just
  outside his picture in the console's texture memory. Rotated and mirrored sprites now stay inside their own picture.
  When Sonic faces left without turning, he is now drawn as an exact mirror image. Before, he was shifted by one
  column, and the outside column showed at his edge.
- **Steadier rotated sprites:** the picture of a rotated sprite no longer bends slightly along its diagonal (it moved
  with every angle).
- Checked for every frame of Sonic's, Tails's and Metal Sonic's animations at every angle, facing left and right, with
  the port's automated tests, and on screen at 32 angles in both directions. Not yet tested on a console.
- The image's SHA-256 changes (the new value is in the README's Output section).

## Memory fix: no freeze at Quartz Quadrant's time warp (October 2026)

- **Fixed a freeze that could happen while time-traveling** (found in Quartz Quadrant 1 Present, warping to the Bad
  Future): the game's memory for loading could be placed where the processor keeps its working data (the stack), and
  the load then corrupted the game's memory list and froze. Whether it happened depended on what had been loaded
  before, so most playthroughs never hit it.
- The game now keeps that working data in a separate, fixed area, so loads can no longer run into it. When memory is
  tight, a load now falls back to slower reads instead of corrupting memory.
- This uses 16 KB of the console's 2 MB RAM; the port's memory checks (zones, special stages, loads, videos) still pass.
- Checked with the port's automated tests in PCSX-Redux and DuckStation, including a boot through a retail NTSC-U BIOS.
  Not yet tested on a console.
- The image's SHA-256 changes (the new value is in the README's Output section).

## Faster title screen and acts (October 2026)

- **The title screen keeps up:** the 3D title (Sonic over Little Planet) took about 1.07 frames of time per frame in
  DuckStation; it now runs at full speed (1.00). Faces of the planet that are entirely off screen are no longer sent to
  the GPU, and the lookup behind its textures is faster.
- **Every act is a little faster** (about 1-4 % less CPU time a frame): the HUD, the rings' touch check and, in
  Tidal Tempest, the water and its palette effect now run as native code instead of the game's script.
- **Tidal Tempest 1** (all four time periods), the act that ran below full speed, needs about 11 fewer of the
  frame's 262 scanlines of CPU time (about 4 %).
- **Only controller port 1 is read:** the game uses one controller; port 2 was polled too and, when empty, its time-out
  was waited out every frame.
- **Flipped level tiles as mirrored sprites:** where the console's GPU can mirror a sprite (every PSone has such a GPU),
  flipped tiles are drawn as smaller mirrored sprites instead of reversed quads. A self-test at boot checks it and keeps
  the previous way elsewhere, including emulators that don't mirror sprites. On those GPUs this saves Tidal Tempest 1
  about 11 more scanlines a frame (measured in DuckStation with the path forced; not yet measured on a console).
- The game looks and plays the same: each change was checked frame by frame against the previous build.
- The image's SHA-256 changes (the new value is in the README's Output section).

## The disc's executable is named after the game (October 2026)

- The disc now boots **`SONICCD.EXE`** instead of `PSX.EXE` (the `BOOT` line of `SYSTEM.CNF`).
  Emulators and optical drive emulators that show a disc's executable name now show the game's. Nothing in the
  game itself changes.
- The image's SHA-256 changes with it (the new value is in the README's Output section).

## D.A. Garden and the special stages in Time Attack open, sprite glitches fixed (October 2026)

- **D.A. Garden is open from the start** (Extras), next to Visual Mode. Sound Test and Stage Select keep their
  original conditions.
- **Time Attack's special stages are open from the start**: press Down past the zones to reach Special Zones 1-7.
  Both also open with an existing save.
- **Tidal Tempest: no stray strip of water surface** in the looping vertical shafts of act 2.
- **Metallic Madness: no stray "platforms"** (pieces of doors and bombs from elsewhere in the act) showing up with no
  collision, most often seen when flying as Tails.

  Both were sprites far away from the screen being drawn on it: the PS1's GPU wraps coordinates about 2,000 pixels
  out. The game now skips any sprite that is off screen, as the PC version does.

## Videos show their picture in PCSX-ReARMed (October 2026)

- In RetroArch's PCSX-ReARMed the videos showed a flat gray picture while their audio played. They now show the
  picture from the first frame. Real consoles and the other emulators already played them and are not affected.

## Time Attack and Visual Mode open, JP vocal videos (October 2026)

- **Time Attack's seven rounds are open from the start**, and **Visual Mode** (Extras: watch the opening, the endings
  and the pencil test) no longer needs a time attack record.
- **Optional: the Japanese soundtrack's videos with their vocal songs.** If you have the videos with the Japanese vocal
  audio (a folder like `videos JPN`, whose first audio track is the Japanese soundtrack), pass `--jp-videos folder`:
  with the JP soundtrack selected, the opening and the endings play that audio over the Steam picture. Without the
  option nothing changes.
- **No freeze if the CD drive stops answering:** in the pause menu or at the end of a video, the game used to wait for
  the drive forever; it now asks again after a few seconds and carries on.

## Tails from the start, smoother and faster (October 2026)

- **Tails is playable from the start.** When you start a new game, the *Player Select* screen lets you pick
  Sonic or Tails right away; you no longer have to finish the game first.

The game now runs at or very close to full speed almost everywhere (measured in emulators):

- **All special stages run at full speed (60 fps).** Before, they ran at roughly 75–95 % speed.
- **The ending credits run at full speed.** They used to crawl along at about a fifth of the normal speed.
- **The short freeze when you travel in time is much shorter** (less than half as long as before).
- **Almost every zone now holds 60 fps.** Collision Chaos, Stardust Speedway and the others no longer slow down, and
  Palmtree Panic, whose busy parts used to slow down a lot, now runs at full speed all the way.
- **Tidal Tempest is much smoother.** Its first act, the heaviest part of the game (the layered underwater
  background and the air bubbles), went from about two thirds of full speed to about 90 %.
- **The title screen, the menus, Time Attack and the D.A. Garden run at full speed too.**
- **Nothing else looks or plays any differently**: apart from Tails, the game was only made faster, and every change was checked against the
  previous version, picture by picture and frame by frame.

Just rebuild your disc image with this version of the builder (same steps as before) to get the update.
