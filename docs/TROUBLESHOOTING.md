# Troubleshooting

These notes apply to the experimental standalone Quest **1.45.1_27839** package set. Keep a copy of your installation receipt and backup before changing anything else.

## The installer refuses to continue

| Message or symptom | What to check |
| --- | --- |
| ADB shows `unauthorized` | Put on the headset and accept USB debugging for your own computer. Run `adb devices` again. |
| More than one device is connected | Use `--serial` with the intended headset's identifier, or disconnect the others. |
| Game version mismatch | Check the complete installed version, including `_27839` and version code `3071`. These packages do not target another version. |
| Bootstrap or loader mismatch | Check the QuestPatcher/Scotland2 setup in the [Windows guide](WINDOWS.md). Do not replace a hash check with a version-name check. |
| Local QMODs or build receipt missing | Complete the [local build](../BUILDING.md), then copy both the resulting QMODs and `build-receipt.json` into the Windows `qmods` folder. |
| Hash or recipe mismatch | Recheck which release each file came from. Download the matching artifact again or rebuild from the matching recipe; do not edit expected hashes to force acceptance. |
| Unknown installed native libraries | Review the existing mod set. The installer does not silently delete unrelated mods or accept a mixed dependency set. Preserve a backup before changing that installation. |
| `rollback_incomplete` | Stop retrying. Keep `private-backups` and inspect the receipt's listed paths; an interrupted process may need manual recovery. |

The `plan`, `download`, and `verify` commands do not modify the headset. `install` performs the device transaction only after its checks. See the [CLI reference](INSTALLER-CLI.md).

## The game takes a long time to open

Check whether a VPN, firewall, or kill switch is blocking requests the game waits for at startup. A slow launch with blocked networking was observed without root; root is not a requirement for this package set. Do not assume a black screen proves that the mods failed to load.

Compare one launch with a working connection if that fits your network setup. If the delay persists, collect a short, redacted startup log and record how long it took.

## Custom songs or map effects are missing

Open **Solo** and the custom-level collection first. Check that the full selected profile passed verification and that the map's required extensions are installed. A normal custom song, a Chroma map, and a Noodle map test different paths.

For missing notes, walls, or colors, record the public map ID, exact difficulty, and the point in the song. An older map can expose version-specific behavior; this alone does not identify whether the map, game, or mod is responsible.

## Fast scrolling causes stutter or growing memory use

Rapidly changing the selected song can queue preview audio, covers, metadata, and UI work. Menu frame drops and high memory use remain under investigation. Avoid sustained rapid scrolling if the headset becomes unresponsive; stop the game before continuing the comparison.

When reporting this, distinguish selecting songs in the menu from loading and leaving a level. Include whether memory settles after leaving one song selected. A short smooth session does not establish that a memory problem is fixed.

## A score is missing

Check the **local best score** and the **online leaderboard** separately. A replay file on disk does not prove that an online upload succeeded.

Practice modes and mods that change scoring-relevant gameplay can affect score eligibility. In particular, an NJS override changes note movement speed; it is different from changing jump distance or reaction time. Keep score eligibility checks intact. Diagnose a normal eligible Solo completion first, then check the save and the leaderboard's upload result independently.

Some mods mentioned in troubleshooting may be present in an existing installation but are not part of this repository's selected release profile. Consult `modpack.json` for what the installer actually installs.

## Settings return to an older value

If your existing installation uses PlayerDataKeeper, it can restore its own copy of `PlayerData.dat` at startup. Editing only the live file while the game is running may be overwritten by a restore or later game save. Close the game, back up the live save and the mod's backup, and establish which contains the latest progress before any recovery. Do not replace the whole save just to change one preference.

PlayerDataKeeper is not part of the published profiles in this release. This note describes an interaction to check on an already-modded headset, not an instruction to add it.

## Updating Beat Saber

Do not carry the 1.45.1 native package set into a newer game build unchanged. Wait for matching packages or develop and test a new port. Keep your save backup and current installation information so a failed update can be investigated without guessing which files were used.

## What to include in an issue

- Headset model and full game version.
- Release tag, chosen profile, affected package versions, and whether they were locally rebuilt.
- Reproduction steps, expected result, and actual result.
- Public map ID/difficulty when relevant, and a short redacted log excerpt if available.

Do not upload APKs, game libraries, full save files, account tokens, headset serial numbers, or personal calibration exports. Installer receipts and logs can contain local paths or device information; review them before sharing.
