# Experimental Quest 1.45.1 local builder

Build these experimental ports on your own computer from pinned public upstream sources plus narrow patches. This folder contains no game APK, generated game headers, mod binaries, private logs, or headset information. A successful build is **not** a claim that every mod works. The local ports have limited Quest3 runtime checks; upstream-supported game versions have not been retested with these changes.

The exact target is **Beat Saber Quest 1.45.1_27839**, Scotland2. Other APK builds are rejected by hashes of the two inputs used by the generator. Keep your APK and generated headers private.

## Windows using WSL2

1. Install Ubuntu24.04 under WSL2 (`wsl --install -d Ubuntu-24.04` from Windows Terminal, then complete Ubuntu account setup). Build inside the Linux home directory, not `/mnt/c`, for performance and reliable symlinks. Reserve approximately35GB of free space for sources, generated headers, compilers and build outputs.
2. In Ubuntu install the host prerequisites:

   ```sh
   sudo apt update
   sudo apt install git curl ca-certificates cmake ninja-build build-essential pkg-config libssl-dev python3 unzip xz-utils
   ```

3. Install Rust using the [official Rust installation instructions](https://www.rust-lang.org/tools/install), then pin the toolchain used here:

   ```sh
   source "$HOME/.cargo/env"
   rustup toolchain install nightly-2026-09-24 --profile minimal
   rustup target add aarch64-linux-android --toolchain nightly-2026-09-24
   ```

4. Keep the exact extracted release at `C:\Users\YourName\Downloads\ports`. Copy that release into a **new** Linux home directory, so the recipe and installer manifest remain from the same release. Replace `YourName` with your Windows account folder name:

   ```sh
   mkdir -p "$HOME/bs1451"
   cp -a "/mnt/c/Users/YourName/Downloads/ports" "$HOME/bs1451/ports"
   cd "$HOME/bs1451/ports/builder"
   chmod +x clang_ndk.py
   ```

   Do not substitute a newer unpinned Git checkout. Supply Android NDKr27c and Clang22.1.8. The optional bootstrap downloads approximately0.66GB +1.94GB from the official Android and LLVM release servers, verifies pinned SHA256, and installs into your home directory:

   ```sh
   python3 bootstrap.py --ndk --llvm
   source "$HOME/.cache/bs1451-tools/environment.sh"
   python3 build.py doctor --rust
   ```

   Existing installations can be used instead:

   ```sh
   export BEAT_SABER_NDK="$HOME/tools/android-ndk-r27c"
   export BEAT_SABER_CLANG="$HOME/tools/LLVM-22.1.8-Linux-X64/bin/clang"
   export BEAT_SABER_CLANGXX="$HOME/tools/LLVM-22.1.8-Linux-X64/bin/clang++"
   export BEAT_SABER_LLVM_AR="$HOME/tools/LLVM-22.1.8-Linux-X64/bin/llvm-ar"
   export BEAT_SABER_LLVM_RANLIB="$HOME/tools/LLVM-22.1.8-Linux-X64/bin/llvm-ranlib"
   ```

   The launcher uses the Clang22 frontend and linker with **NDKr27c headers and Android runtime**, including its unwind library. It does not substitute a host C++ runtime. NDK revision must be27.2.12479018. User-supplied toolchains are checked by version/revision; this is not a claim of bitwise identity to the optional official archive. The bootstrap also records and rechecks extracted toolchain trees. QPM is not required: the runner creates CMake dependency metadata from the pinned QPM lock information without executing upstream restore scripts.

5. Keep the release's sanitized `beatsaber-hook` and `songcore` QMODs in its Windows `qmods` folder. They are the two exact-build binary dependencies imported by this recipe. Their native hashes must match the lock; arbitrary releases are rejected. Other dependencies are fetched automatically with commit or SHA256 pins.
6. Generate headers from **your own unmodified exact-version APK**. Replace the example path with your local APK:

   ```sh
   python3 build.py generate --apk "/mnt/c/Users/YourName/Downloads/BeatSaber.apk"
   ```

   This builds the pinned metadata39-compatible `cordl` generator and its `brocolib` dependency, extracts only the metadata and IL2CPP library locally, and checks the complete generated API tree against its pinned digest. It never uploads APK contents. Cpp2IL is not needed by this pipeline. If you already generated the exact headers, `--headers /your/codegen/include` can be used instead.
7. Build the available targets in dependency order (one native compiler job at a time):

   ```sh
   python3 build.py build --dependency-qmods "/mnt/c/Users/YourName/Downloads/ports/qmods"
   ```

   The default work directory is `$HOME/.cache/bs1451-builder`. Its `output` directory contains the QMODs and `build-receipt.json`. Use these with the pack manager's explicit local-build receipt option. The receipt records the actual complete header-tree digest and binds package versions and hashes to the release's pinned recipe fingerprint. Keep the receipt with the QMODs. Copy both back into the same Windows release folder:

   ```sh
   cp "$HOME/.cache/bs1451-builder/output/"*.qmod "/mnt/c/Users/YourName/Downloads/ports/qmods/"
   cp "$HOME/.cache/bs1451-builder/output/build-receipt.json" "/mnt/c/Users/YourName/Downloads/ports/qmods/"
   ```

A different workspace can be selected consistently with `--work-dir "$HOME/bs1451-build"`. To build selected targets, list their names after `build`; prerequisites must already have been built/imported. `python3 build.py list` shows the current available/held targets. CongXinJian v5 is included as experimental: its frozen local build passed a bounded startup check, while physical automatic-calibration validation remains pending. Building does not install anything on a headset.

## What is pinned and what has been tested

`build-lock.json` pins upstream commits, external native release hashes, per-dependency patch hashes, exact game input hashes, generator sources, toolchain versions and output manifests. Each target has `inputs_sha256`, computed from the whole locked recipe and executable recipe file hashes. The runner validates the fingerprint, every tracked source against its Git base or reviewed patch, extra source files, extracted dependency trees, external links, and dependency native hashes before compiling. Reused generated headers must match the complete tree digest. Altering a recipe requires a new trusted release fingerprint; do not edit the lock to bypass a failed integrity check.

The source reconstruction report covers every exported changed file against its pinned upstream base. See `validation.json` for actual clean-build checks and remaining gaps. Initial local port testing and a fresh portable build are distinct: compiler output may differ because of compiler patch level and anonymized source paths. Freshly rebuilt QMODs still require local runtime testing.

WSL setup and the full optional compiler bootstrap have not been tested end-to-end on Windows; the Linux native build results are listed explicitly in the validation report.

The full default pack includes upstream libraries that are downloaded separately by the pack manager. This folder is a build recipe, not a complete offline dependency archive. If a pinned source or release disappears, the build stops rather than silently selecting another version.

## Attribution and source boundaries

Source is fetched directly from the repositories listed in `build-lock.json`. Existing upstream copyright and license files remain in those checkouts. Patches are zero-context changes relative to those sources, not a relicensing of upstream projects. Where binary redistribution permission has not been established, the pack asks the recipient to build locally; this recipe makes no new claim of redistribution permission.

The clean CMake adaptations retain the original local port code, use runtime targets only, and omit opt-in device integration-test modules. No test module is installed. The source snapshots and patches are experimental review material. Keep game-derived generated headers and build intermediates out of public uploads.
