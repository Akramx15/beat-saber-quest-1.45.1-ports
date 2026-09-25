# Installer commands

Use Python 3.10 or newer. On Windows the wrapper supports Windows PowerShell 5.1. Android platform-tools (`adb`) must be available for **install**; plan, download and verify do not contact a headset.

Run from the extracted repository directory:

```powershell
.\Manage-Modpack.ps1 -Command plan -Profile recommended
.\Manage-Modpack.ps1 -Command download -Profile recommended
```

`plan` is also the default when no command is supplied. `download` fetches only HTTPS artifacts pinned in the manifest and reports which packages require local builds. It cannot replace local build outputs with unrelated downloaded binaries.

After following BUILDING.md, place the generated QMODs and their `build-receipt.json` in the same `qmods` directory as the downloaded packages. The receipt must match this manifest's pinned build inputs. Then verify everything before connecting the install step:

```powershell
.\Manage-Modpack.ps1 -Command verify -Profile recommended -BuildReceipt .\qmods\build-receipt.json
adb devices
.\Manage-Modpack.ps1 -Command install -Profile recommended -BuildReceipt .\qmods\build-receipt.json -Serial 'YOUR_AUTHORIZED_QUEST_SERIAL'
```

Equivalent Python syntax, including custom paths:

```text
python manage_modpack.py verify --profile recommended --qmods qmods --build-receipt qmods/build-receipt.json
python manage_modpack.py install --profile recommended --qmods qmods --build-receipt qmods/build-receipt.json --serial YOUR_AUTHORIZED_QUEST_SERIAL --adb adb --backups private-backups
```

Select one of the profile names printed in `modpack.json`. Selecting a profile also includes its dependencies. An installed native outside the selected set causes a refusal before any device changes; this installer does not silently remove unrelated mods.

Install verifies the exact game version, the installed APK's Scotland2 marker and pinned ARM64 bootstrap, and the pinned external loader. The owner must already have patched their own installed game. This tool never installs an APK, changes Android permissions, or modifies songs, player saves, runtime settings or accounts.

Before writing, it saves and SHA256-verifies every file it may replace or remove under a unique `private-backups` directory. It uploads into a temporary directory, verifies the uploads, then commits individual files. Older registrations of the selected package IDs are replaced. If a transfer or commit fails, it attempts to restore all changed files from that verified backup. A concurrent file change is preserved and reported instead of overwritten. The backup's `receipt.json` records completed work, rollback failures and cleanup issues. Keep that directory private; do not upload it to an issue.

A power loss, terminated process or disconnected device can prevent automatic recovery. A receipt marked `rollback_incomplete` requires inspecting its listed paths before another installation. Do not delete the backup or assume a failed install was rolled back.

Run offline tests with `python -m unittest discover -s tests -v`. The GitHub workflow runs these same tests on Windows and Ubuntu, plus the Windows PowerShell 5 wrapper's read-only plan. It does not contact a headset or download/install mods.
