# Changelog

Updates to the Sonic CD PS1 ISO Builder, newest first. To get an update, rebuild your disc image with the new
version of the builder (same steps as in the [README](README.md)).

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
