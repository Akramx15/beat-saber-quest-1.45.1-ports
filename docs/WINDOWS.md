# Install on Windows and Quest

[Back to the project](../README.md) · [العربية](WINDOWS.ar.md) · [Installer reference](INSTALLER-CLI.md)

This guide targets **standalone Quest Beat Saber 1.45.1_27839, version code 3071**, package `com.beatgames.beatsaber`, using **Scotland2**. You must already own and have that exact game version installed. The kit does not supply, install or downgrade the game.

**This is an experimental release.** Some packages are downloaded; others must be built locally using WSL2/Ubuntu. Native builds passed on Linux and offline installer tests passed on Windows and Linux. The complete WSL setup and a physical Windows-to-headset installation have **not** been validated end to end. See [validation scope](VALIDATION.md).

## 1. Prepare Windows and back up your game

You need a USB data cable, Developer Mode enabled on your Quest, [Python 3.10 or newer for Windows](https://www.python.org/downloads/windows/) with the Python Launcher, and [Android Platform Tools](https://developer.android.com/tools/releases/platform-tools). Extract Platform Tools somewhere such as `C:\Tools\platform-tools`. Root is not required.

Connect the Quest, unlock it and accept its USB debugging prompt. In **PowerShell**:

```powershell
py -3 --version
$adb = 'C:\Tools\platform-tools\adb.exe'
& $adb devices
& $adb shell dumpsys package com.beatgames.beatsaber | Select-String 'versionName=|versionCode='
```

Use your actual ADB path. Continue only when the headset appears as `device` and the version matches the target above. These examples assume one connected headset; disconnect other Android devices during backup and patching.

Close Beat Saber and export your APK before patching. Keep this PowerShell window open so the variables remain available:

```powershell
& $adb shell am force-stop com.beatgames.beatsaber
if ($LASTEXITCODE -ne 0) { throw 'Could not stop Beat Saber.' }
$backupDir = Join-Path $env:USERPROFILE ('Documents\BeatSaber-backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $backupDir -ErrorAction Stop | Out-Null
$apkLines = @(& $adb shell pm path com.beatgames.beatsaber)
if ($LASTEXITCODE -ne 0) { throw 'Could not read the installed APK path.' }
$apkPaths = @($apkLines | Where-Object { $_.StartsWith('package:') } | ForEach-Object { $_.Substring(8).Trim() })
if ($apkPaths.Count -ne 1) { throw 'Expected one APK. Stop and inspect the package paths.' }
$apkCopy = Join-Path $backupDir 'BeatSaber.apk'
& $adb pull $apkPaths[0] $apkCopy
if ($LASTEXITCODE -ne 0) { throw 'APK backup failed.' }
& $adb pull '/sdcard/Android/data/com.beatgames.beatsaber/files' (Join-Path $backupDir 'game-files')
if ($LASTEXITCODE -ne 0) { throw 'Game data backup failed. Do not patch yet.' }
Get-Item -LiteralPath $apkCopy | Select-Object FullName, Length
```

Also back up these directories **if present**. The first contains existing mod data, including custom content; the second contains game expansion files. A fresh installation may not have `ModData` yet. Check that a missing directory is genuinely absent, rather than inaccessible:

```powershell
& $adb shell ls -ld '/sdcard/ModData/com.beatgames.beatsaber'
& $adb shell ls -ld '/sdcard/Android/obb/com.beatgames.beatsaber'
```

For each existing directory, run its backup block:

```powershell
& $adb pull '/sdcard/ModData/com.beatgames.beatsaber' (Join-Path $backupDir 'mod-data')
if ($LASTEXITCODE -ne 0) { throw 'Mod data backup failed. Do not patch yet.' }
```

```powershell
& $adb pull '/sdcard/Android/obb/com.beatgames.beatsaber' (Join-Path $backupDir 'obb')
if ($LASTEXITCODE -ne 0) { throw 'Expansion data backup failed. Do not patch yet.' }
```

Inspect the copied files before continuing. **QuestPatcher uninstalls and reinstalls the APK during patching**, so its own backup attempt is not a substitute for your verified copy. Keep the backup and your APK private. The builder needs your own exact-version APK; its input hashes reject mismatched game files.

## 2. Download one complete release

From [the experimental release](https://github.com/Akramx15/beat-saber-quest-1.45.1-ports/releases/tag/v0.1.0-experimental.1), download **`quest-1.45.1-windows-kit-v0.1.0-experimental.1-english.zip`** and **`ENGLISH-KIT-SHA256.txt`**. This documentation refresh uses the same mod packages and build pins as the original release. GitHub's automatic source archive is not the Windows kit.

In PowerShell, compare the ZIP's SHA256 with the value in `ENGLISH-KIT-SHA256.txt` before extracting it:

```powershell
Get-FileHash "$env:USERPROFILE\Downloads\quest-1.45.1-windows-kit-v0.1.0-experimental.1-english.zip" -Algorithm SHA256
Get-Content "$env:USERPROFILE\Downloads\ENGLISH-KIT-SHA256.txt"
```

Use your actual download directory if different. The hexadecimal hashes must match; letter case does not matter. Extract the ZIP's `beat-saber-quest-1.45.1-ports` folder and rename or move it to a path such as `C:\Users\YourName\Downloads\ports`.

`manage_modpack.py`, `modpack.json` and `builder` must be directly inside `ports`. Keep the manifest, scripts, recipes and packages from the same release. In **PowerShell**, replacing `YourName` with your Windows account folder:

```powershell
Set-Location 'C:\Users\YourName\Downloads\ports'
py -3 manage_modpack.py plan --profile recommended
py -3 manage_modpack.py download --profile recommended
```

`download` fetches pinned packages into `qmods` and lists those requiring a local build. That message is expected: this release does not distribute every mod as a ready-made binary. `recommended` includes custom songs, search/download tools, Chroma, Noodle Extensions, Mapping Extensions and CongXinJian, with their dependencies.

## 3. Build the remaining packages in Ubuntu

Use an **x64 Windows PC** with approximately **35 GB** of free space; the supplied compiler bootstrap uses Linux x64 archives. Follow [Microsoft's WSL installation instructions](https://learn.microsoft.com/en-us/windows/wsl/install). For a new installation, run this in **PowerShell as administrator**, restart Windows if requested, then finish Ubuntu's first-run account setup:

```powershell
wsl --install -d Ubuntu-24.04
```

The following commands run in **Ubuntu**, not PowerShell. Install the prerequisites:

```sh
sudo apt update
sudo apt install git curl ca-certificates cmake ninja-build build-essential pkg-config libssl-dev python3 unzip xz-utils
```

Install `rustup` **inside Ubuntu** using the command from the [official Rust instructions](https://rust-lang.org/tools/install/). Complete its prompts before selecting the required toolchain:

```sh
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source "$HOME/.cargo/env"
rustup toolchain install nightly-2026-09-24 --profile minimal
rustup target add aarch64-linux-android --toolchain nightly-2026-09-24
```

Copy the extracted release to a **new Linux home directory**. Build there, rather than under `/mnt/c`. Replace `YourName` and the source path as needed:

```sh
mkdir -p "$HOME/bs1451" &&
mkdir "$HOME/bs1451/ports" &&
cp -a "/mnt/c/Users/YourName/Downloads/ports/." "$HOME/bs1451/ports/" &&
cd "$HOME/bs1451/ports/builder" &&
chmod +x clang_ndk.py
```

If `ports` already exists in Linux, use a different new directory and adjust subsequent paths. Do not merge releases or accidentally create `ports/ports`.

The builder requires **Android NDK r27c (27.2.12479018)** and **Clang 22.1.8**. From the `builder` directory, the following bootstrap downloads the pinned official archives (about 2.6 GB total), checks their hashes and prepares the environment:

```sh
python3 bootstrap.py --ndk --llvm
source "$HOME/.cache/bs1451-tools/environment.sh"
python3 build.py doctor --rust
```

Wait for each command to succeed before continuing. To use existing toolchains instead, follow [the builder guide](../builder/README.md); do not substitute arbitrary versions.

Generate headers from the APK you backed up, replacing the example path below with its actual location, then build:

```sh
python3 build.py generate --apk "/mnt/c/Users/YourName/Documents/BeatSaber-backup-YYYYMMDD-HHmmss/BeatSaber.apk"
python3 build.py build --dependency-qmods "/mnt/c/Users/YourName/Downloads/ports/qmods"
```

The dependency folder must still contain the downloaded `beatsaber-hook` and `songcore` QMODs. The builder checks their exact native hashes. Game-derived headers stay on your computer; do not upload them or your APK.

After a successful build, copy its QMODs **and receipt** back to Windows:

```sh
cp "$HOME/.cache/bs1451-builder/output/"*.qmod "/mnt/c/Users/YourName/Downloads/ports/qmods/"
cp "$HOME/.cache/bs1451-builder/output/build-receipt.json" "/mnt/c/Users/YourName/Downloads/ports/qmods/"
```

Keep the downloaded packages in that same folder. In **PowerShell**, verify the completed set before patching or installing anything:

```powershell
Set-Location 'C:\Users\YourName\Downloads\ports'
py -3 manage_modpack.py verify --profile recommended --build-receipt .\qmods\build-receipt.json
if ($LASTEXITCODE -ne 0) { throw 'Package verification failed. Stop here.' }
```

`plan`, `download`, the build and `verify` do not access the headset.

## 4. Patch the game with QuestPatcher

Download **QuestPatcher 2.10.0** from [its official release](https://github.com/Lauriethefish/QuestPatcher/releases/tag/2.10.0). Use `QuestPatcher-windows.exe` or extract `QuestPatcher-windows-standalone.zip`. This was the latest stable release when checked on **30 September 2026**.

1. Connect and unlock the Quest. Open QuestPatcher with a working internet connection and select **`com.beatgames.beatsaber`**. Use **Tools → Change App** if another app is selected. Confirm `1.45.1_27839`.
2. On the patching screen, select **Scotland2** in the mod loader dropdown, then click **Patch my App!**. Leave optional patching features at their defaults. For an already-patched installation that needs a loader change, use **Tools → Repatch App**, select **Scotland2** in that dialog and confirm; take the backup first. If it already has this release's pinned loaders, proceed directly to installation.
3. For this exact version, the official unstripped-Unity index had **no matching entry** when checked. Choose **Continue Anyway** on that specific missing-unstripped-Unity prompt to retain the APK's original `libunity.so`. Do not import a library from another game version. If the message reports another error, stop and inspect it.
4. Let patching finish, then close QuestPatcher before running the pack installer. Do not import a separate 1.40.8 core-mod set into this installation.

QuestPatcher checks its unstripped index by app ID and exact version; when the matching library is unavailable and you continue, its [patching implementation](https://github.com/Lauriethefish/QuestPatcher/blob/2.10.0/QuestPatcher.Core/Patching/PatchingManager.cs) leaves Unity unchanged. See the [official index](https://github.com/Lauriethefish/QuestUnstrippedUnity/blob/main/index.json).

This pack requires the following exact files; the installer verifies them automatically:

| Component | Location | SHA256 |
| --- | --- | --- |
| [LibMainLoader v0.2.0](https://github.com/sc2ad/LibMainLoader/releases/tag/v0.2.0) | `lib/arm64-v8a/libmain.so` inside the patched APK | `5e3ef9701b89ae911113b0adad8f5d5b58f644867cdcd18f8a51ac807df60119` |
| [Scotland2 v0.1.7](https://github.com/sc2ad/scotland2/releases/tag/v0.1.7) | `/sdcard/ModData/com.beatgames.beatsaber/Modloader/libsl2.so` | `3c34627ede42c9281a0d28147bc222424c5dc451263a14c7a9ab6a88331890fe` |

QuestPatcher's [online download index](https://github.com/Lauriethefish/QuestPatcher/blob/main/QuestPatcher.Core/Resources/file-downloads.json) currently selects these versions. Its bundled offline fallback contains older loaders, so **QuestPatcher 2.10.0 alone does not guarantee matching files**. If the installer reports a loader mismatch, resolve the patching/download problem before retrying; keep the manifest's integrity checks enabled.

## 5. Install and try a small test

Keep Beat Saber closed. In **PowerShell inside `ports`**, define `$adb` again if this is a new window:

```powershell
$adb = 'C:\Tools\platform-tools\adb.exe'
& $adb devices
py -3 manage_modpack.py install --profile recommended --build-receipt .\qmods\build-receipt.json --adb "$adb"
```

If you intentionally have multiple devices connected, add `--serial 'YOUR_QUEST_SERIAL'` using the serial shown by `adb devices` for your headset.

The installer checks the exact game and loader, validates dependencies, and backs up replaced mod files under `private-backups` before writing. It does not install an APK or change songs, player saves, calibration or accounts. It refuses unknown installed native mods rather than silently combining incompatible sets. See [transaction and recovery behavior](INSTALLER-CLI.md).

Start Beat Saber from the headset, open **Solo**, and try an ordinary custom song. Then test song search/download and a known Chroma/Noodle map. Record the map name, difficulty and exact symptom if something fails. For saber adjustment, use the [CongXinJian guide](CONTROLLER-OFFSETS.md).

## If a step fails

| Symptom | Next step |
| --- | --- |
| `unauthorized`, `offline` or no ADB device | Unlock the headset, accept USB debugging and check the USB data connection. |
| Wrong game version or loader hash | Check the installed app and QuestPatcher results. This installer does not downgrade or repair the APK. |
| Missing QMOD or invalid build receipt | Complete the local build and copy both its QMODs and receipt into the same release's `qmods` folder. |
| Unknown installed native mod | Review and back up the existing mod set before reconciling it with the selected profile. Do not delete your entire `ModData` directory. |
| Transfer failure or `rollback_incomplete` | Keep `private-backups` and inspect the transaction's `receipt.json` before retrying; disconnection can prevent automatic recovery. |
| Build succeeds but a mod fails in game | Report the release, mod, map/difficulty and reproduction steps. A build pass does not establish full runtime compatibility. |

Share only relevant, redacted error text. APKs, personal backups, device serials and account information do not belong in public issues.
