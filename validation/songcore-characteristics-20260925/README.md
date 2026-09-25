# SongCore characteristic conversion evidence

The actual Quest **1.45.1_27839** game converts custom enum 101 (Lawless) to `Standard` and its native parser rejects `Lawless` and `Lightshow`. PlayerData saves and loads through these enum/string methods directly; its characteristic-collection lookup hook does not cover that path. The narrow [source patch](source-only.patch) consults the existing custom registry, retaining native precedence for built-in names and native failure behavior for unknown names.

The proposed upstream change is **one existing file, 30 added lines**. The former Python test implemented its own native fallback model; it is excluded from this patch because that model cannot independently reproduce a game failure. The production hook bodies remain the same reviewed implementation. The additional evidence below tests the real build environment and real runtime calls.

## Upstream target and Android compilation

Current upstream main and release v1.3.2 are commit `fa75600323dad78660f52e6f6d45541264806350`. The maintainer's [release is titled BS 1.45](https://github.com/raineaeternal/Quest-SongCore/releases/tag/v1.3.2). Its pinned `bs-cordl 4500.0.0` contains `include/version.txt` identifying **1.45.0_26420**. The manifest's remaining 1.44.3 value is stale target metadata; it was not changed by this patch.

Both the unchanged base and candidate compiled and linked with QPM 1.5.9, NDK r29 (`29.0.14206865`), Android Clang 21, C++26, API 24 and ARM64. The base completed 90 steps. The candidate compiled the changed translation unit with actual generated types and production hook macros, reused unchanged base objects, and relinked the entire library. No API port changes or replacement hook macros were needed. [Validation JSON](validation.json) records dependency source pins and binary hashes.

This matches the toolchain requirements demonstrated by the [successful upstream CI run](https://github.com/raineaeternal/Quest-SongCore/actions/runs/33809147218). That historical CI directory used the suffix `+preview-0`; equal revision numbers do not prove identical historical archive bytes.

Typical build reproduction with that source, lock and installed toolchain:

```sh
qpm restore
cmake -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo -DCMAKE_ANDROID_NDK=/path/to/android-ndk-r29 -B build
cmake --build build -j 1
# Save the baseline result, apply source-only.patch, then build again.
git apply /path/to/source-only.patch
cmake --build build -j 1
```

## Independent device comparison

A separate isolated **1.45.1 port** appended [this diagnostic](device-diagnostic.cpp) to the hook translation unit. It called the actual original trampolines and the generated public methods after the hooks were installed and the three default custom characteristics registered. It used real managed strings, by-reference enum outputs and SongCore's real registry. The diagnostic did not replace native behavior with a mock.

All **34 cases passed**: 11 serialization cases, 14 parsing cases and nine roundtrips, preceded by three registry checks. The [recorded output](native-results.tsv) retains every case; only the process-address row was omitted. Native method RVAs matched the actual game mapping (`0x3998740` and `0x3998944`).

| Operation | Original trampoline | Installed public method |
| --- | --- | --- |
| Serialize 101 | Standard | Lawless |
| Parse Lawless | false, output 0 | true, output 101 |
| Roundtrip 101 | 101 → Standard → 0 | 101 → Lawless → 101 |
| Lightshow 100 | Standard / parser failure | Lightshow / 100 |
| Built-ins 0–5 | Original names and IDs | Same names and IDs |
| Null, empty, unknown or differently cased name | false, output 0 | Same failure and output |

For a diagnostic build, append `device-diagnostic.cpp` to `src/Hooks/CharacteristicsHooks.cpp`, declare `void RunCharacteristicNativeDiagnostic();` in `src/main.cpp`, and call it immediately after `RegisterDefaultCharacteristics();` in `late_load`. Build against the **actual game version being tested**; the upstream 1.45.0 output must not be treated as the tested 1.45.1 port. The file records TSV output under the game's external `Mods/SongCore` directory. Require `BEGIN`, three passing `REGISTRY` rows, all 34 passing case rows, and `COMPLETE 34 0`. Remove the diagnostic after testing. The native test ran in `late_load`; no main-thread execution claim is made.

The diagnostic itself makes no PlayerData calls. Normal game startup can still save automatically. Fresh before/after snapshots retained all **320 current statistics records** and the controller-offset configuration and slots. The sole other profile difference was the `userAgeCategory` field during startup; its values are private. The original SongCore library was restored and the game reopened successfully. Neither this diagnostic binary nor private logs, profile snapshots, game files or account data are distributed here.

Earlier bounded save evidence was independently recomputed: 126 prior records plus 13 Lawless and one Lightshow record were preserved by the patched save, along with the other profile fields. Only one of those 14 custom records had a valid score. Failed earlier DataKeeper sessions are not counted as clean startup evidence; the subsequent clean session supplied the matching game/cache snapshots.

**Limits:** the upstream **1.45.0 target has build validation only**. The **1.45.1 device trial is separate**, and does not establish 1.45.0 runtime behavior. Late registration, duplicate IDs, recovery of old corrupted records and complete mod compatibility remain outside this change. This work remains AI-assisted; the reported Android builds, native calls and file comparisons are actual observations.
