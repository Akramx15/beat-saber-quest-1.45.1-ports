# Beat Saber Quest 1.45.1 — experimental ports

**Experimental release:** use the matching [release assets](https://github.com/Akramx15/beat-saber-quest-1.45.1-ports/releases) and read the validation limits below.

حزمة تجريبية لمودات **Beat Saber على Quest المستقل، الإصدار 1.45.1_27839**. بعض الوظائف جُرّبت على Quest 3، لكن هذه ليست نسخة رسمية مدعومة أو ضمانًا بأن كل المودات تعمل بالكامل. التفاصيل في [حالة الاختبارات](docs/VALIDATION.md).

**لصاحب ويندوز:** اتبع [دليل التثبيت](docs/WINDOWS.ar.md). بعض المودات ملفات QMOD جاهزة، وبعضها يُبنى محليًا من مصدر صاحبه باستخدام WSL. ستحتاج نسختك الخاصة من اللعبة لتوليد ملفات البناء؛ ملفات اللعبة غير مرفوعة هنا.

The package pins dependencies for this exact game build. It includes the tested beatsaber-hook directory fix and recipes for the experimental custom-song, map-extension, menu and controller-offset ports. See [validation limits](docs/VALIDATION.md), [build instructions](BUILDING.md), and the per-package manifest before installing.

## Controller offsets

The Quest alternative is **[CongXinJian](https://github.com/lixiangwuxian/CongXinJian)**. It provides per-hand position/rotation, three slots, and Auto Pos/Auto Rot. It is not the complete PC [EasyOffset](https://github.com/Reezonate/EasyOffset) feature set. The calibration tools are in the **Solo → CongXinJian** tab. [طريقة المعايرة بالعربي](docs/CONTROLLER-OFFSETS.ar.md).

## Installation model

1. Keep a backup of your game data and your own APK. Patch your installed copy with Scotland2 using [QuestPatcher 2.10.0](https://github.com/Lauriethefish/QuestPatcher/releases/tag/2.10.0).
2. Download the pinned permitted QMODs and build the remaining selected packages locally. A successful build creates a receipt identifying the inputs and output hashes.
3. Run the package verifier, then install the complete selected set. Root is not required. The installer checks the actual game version, APK bootstrap and loader before modifying the external mod folders.

The installer backs up the mod files it replaces and keeps songs, saves, account files and controller settings outside its transaction. It does not patch or uninstall the game. Do not mix these exact-target libraries with automatic dependency downloads for an older Beat Saber version.

## For mod authors

These are experimental changes offered for review. Compilation, startup, synthetic regression checks and user gameplay observations are recorded separately. A green build is not a claim of complete mod compatibility. Third-party authors retain credit and their original licenses; the [repository license](LICENSE) covers the original orchestration scripts and documentation only.

Some upstream repositories do not state redistribution terms, and some binary/source build closures are still incomplete. Those binaries are not mirrored here; the recipes retrieve pinned upstream source and apply the reviewed changes locally. Licensed review source snapshots are identified as snapshots, not automatically as complete Corresponding Source for every historical binary.

This repository does not distribute APKs, game libraries, OBBs, paid content, custom songs, private logs, device identifiers or personal calibration profiles.
