# Beat Saber Quest 1.45.1

### Experimental mod ports for standalone Quest

Custom songs, song search, Chroma and Noodle maps, and controller offsets for **Beat Saber 1.45.1_27839**. This project brings together version-pinned packages, local build recipes, and a Windows installation guide.

**[Start here: Windows installation](docs/WINDOWS.md)** · **[Downloads](https://github.com/Akramx15/beat-saber-quest-1.45.1-ports/releases/tag/v0.1.0-experimental.1)** · **[Tested features](docs/VALIDATION.md)** · **[Troubleshooting](docs/TROUBLESHOOTING.md)**

> **Experimental, with limited testing.** Several features have been exercised on Quest 3, but compatibility is not complete. This is an independent porting project, not an official release from the original mod authors. The full Windows → WSL → headset installation flow has not been tested end to end.

## Before you start

| Requirement | This release |
| --- | --- |
| Platform | Standalone Meta Quest; runtime observations are from Quest 3 |
| Game | **1.45.1_27839**, Android version code **3071** |
| Package | `com.beatgames.beatsaber` |
| Mod loader | **Scotland2**, with the exact bootstrap and loader pinned in the manifest |
| Computer | Windows with Python 3.10+, Android Platform Tools, and WSL2/Ubuntu for local builds |
| Root | Not required |
| Game files | Use your own legally obtained installation; APKs and game assets are not included |

This is an advanced installation: **the recommended profile includes 25 packages and dependencies, with 12 local builds**. The Windows kit includes permitted prebuilt packages; other packages are downloaded from pinned sources or built locally. It is not a one-click mod installer.

The downloadable mod set is **v0.1.0-experimental.1**. Newer documentation or development notes do not add unpublished fixes to that release. Use the manifest, recipes, QMODs, and build receipt from the same release.

## What you can install

| Feature | Packages | Validation so far |
| --- | --- | --- |
| Custom songs | SongCore and its dependencies | Custom-level audio and notes confirmed in sampled play |
| Browse and download | Better Song Search, SongDownloader, Better Song List, PlaylistCore | Search, download, sorting, and ordinary song selection checked |
| Extended maps | Chroma, Noodle Extensions, Mapping Extensions, Tracks, CustomJSONData | Selected maps checked; map and event coverage remains limited |
| Controller offsets | CongXinJian | Manual offsets and Auto Pos confirmed; Auto Rot quality needs further testing |
| Practice tools | Optional `practice` profile | Available as an experimental addition |
| Multiplayer | Optional `online-experimental` profile | Online compatibility and score submission are not established |

For exact versions and dependencies, see [modpack.json](modpack.json). For the evidence behind each claim, see [validation notes](docs/VALIDATION.md).

## Install in five stages

1. **Back up your game, saves, and mod data.** Export your own APK before patching. Keep the backup on your computer.
2. **Prepare and verify the Windows kit.** Download its permitted packages, then build the remaining selected mods in WSL2 using your own APK. Keep the generated build receipt alongside the QMODs.
3. **Patch the correct game with QuestPatcher and Scotland2.** Follow the [exact-version instructions](docs/WINDOWS.md); the mod installer itself does not patch or install the game.
4. **Install the verified set.** The installer also checks the headset's game version and patched loader before writing the mod files.
5. **Test gradually.** Start with an ordinary custom song, then search/download, then a known Chroma or Noodle map.

**[Open the complete Windows guide →](docs/WINDOWS.md)**

QuestPatcher is used for patching. Use this project's verified installation path for the package set; importing unrelated dependencies for another game version can create an incompatible mix.

## Choose a profile

| Profile | Intended use |
| --- | --- |
| `core` | SongCore and its dependency set: 9 packages, including 2 local builds |
| `recommended` | Custom songs, browsing, extended maps, and CongXinJian |
| `practice` | Recommended set plus PracticeTweaqs |
| `online-experimental` | Recommended set plus BeatTogether and MultiplayerCore; online behavior is unverified |

Run `py -3 manage_modpack.py plan --profile recommended` from the kit directory to see the resolved package list without changing the headset. All profiles still need their complete dependency set. See the [installer command reference](docs/INSTALLER-CLI.md) for other profiles and options.

Offline `verify` checks your local package set. `install` also checks the headset's game and loader, then closes Beat Saber for the installation; finish playing before running it.

## Controller setup

[CongXinJian](https://github.com/lixiangwuxian/CongXinJian) is the Quest controller-offset option included here. It offers per-hand position and rotation, three slots, Auto Pos, and Auto Rot. Its feature set differs from PC EasyOffset.

Open **Solo → CongXinJian** after installation. Use the [controller guide](docs/CONTROLLER-OFFSETS.md) and keep your own calibration backup; another player's offsets are not included.

## Known limitations

- Sampled gameplay is not complete compatibility testing. Newly rebuilt binaries need their own headset checks.
- Fast repeated song selection can still cause frame drops and substantial memory pressure. Long-session stability is unresolved.
- Local score persistence, online score upload, and multiplayer need separate validation. A saved replay is not proof of an uploaded score.
- Successful compilation and offline installer tests do not prove a successful physical Windows installation.
- A future game update needs a new port and new checks. Changing a QMOD's version label does not update its native code.

See [troubleshooting](docs/TROUBLESHOOTING.md) before retrying a failed installation. Keep installer backups until you have verified the game.

## Credits and source

The original mod authors retain their work and licenses. See [third-party credits](THIRD_PARTY.md), the [source index](source-index.json), and [build instructions](BUILDING.md). This repository's [MIT license](LICENSE) covers its original orchestration scripts and documentation only.

Some binaries are not redistributed because their licensing or complete build provenance is unresolved. The local recipes fetch pinned upstream source and apply the published patches. Review source snapshots are not a promise of complete corresponding source for every historical binary.

Game APKs, OBBs, paid content, custom songs, account files, device identifiers, private logs, and personal calibration profiles are not distributed here.

## Report a problem

[Open an issue](https://github.com/Akramx15/beat-saber-quest-1.45.1-ports/issues) with the headset model, full game version, release/profile, affected mod versions, and reproduction steps. For a map issue, add its public ID and difficulty. Describe what failed and what still worked; remove personal information from any log excerpt.
