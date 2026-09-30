# Porting and release workflow

Use this workflow when changing a mod, rebuilding a release, or targeting another Beat Saber version. The [maintenance index](README.md) records the release boundary and open work. Build commands and prerequisites belong to the [builder guide](../../builder/README.md).

## Establish the target and baseline

Read `modpack.json`, `builder/build-lock.json`, the relevant patch and QMOD manifest, and the validation reports before editing. Record both the QMOD SHA256 and every native-library SHA256: repackaging can change the archive without changing its executable code. Preserve the previous artifact and symbols for comparison.

The current target is Quest **1.45.1_27839**, version code **3071**, **ARM64**, **Scotland2**. The generator adaptations cover IL2CPP metadata **39**; the game uses Unity **6000.3.19f1**. Derive any future target from its actual APK and metadata rather than carrying these values forward.

The manifest pins the Scotland2 loader and APK bootstrap hashes. Verify that contract independently from the mod dependency graph. Changing a QMOD's declared game version cannot establish loader or native compatibility.

Keep three identities separate:

1. The published release: manifest, locked recipes and downloadable artifacts.
2. A rebuilt output: its actual inputs, toolchain, header digest and receipt.
3. A runtime-tested output: the exact native hash that executed and the specific behavior observed.

Do not infer the contents of any headset from this repository. When runtime work is authorized, inspect the actual installed and loaded binaries; package registration alone may differ from the loaded copy.

## Reconstruct the build

The current portable toolchain uses Android NDK **r27c / 27.2.12479018**, Clang **22.1.8**, Android API **24**, and the NDK Android runtime. Tracks additionally uses pinned Rust **nightly-2026-09-24** for `aarch64-linux-android`. Keep the compiler launcher: a host compiler frontend must not silently introduce a host C++ runtime or omit the required Android unwind library.

The builder imports the exact pinned beatsaber-hook and SongCore native dependencies. It reconstructs other dependencies from the lock without running an unconstrained QPM restore. Respect generated-header overlays and native dependency hashes together; matching a semantic version is insufficient for an ABI-dependent port.

Use the runner's default target order. Its main dependency chains are:

- BSML and MetaCore, followed by MetaCoreBS, PlaylistCore, BetterSongList and SongDownloader.
- CustomJSONData, followed by Tracks, then NoodleExtensions and Chroma.

UnicodeQuest and the controller-offset target are also part of the default set. These chains describe important prerequisites, not the complete graph; the checked-in dependency declarations and runner remain authoritative. Selecting individual targets requires preparing their prerequisites first.

Generate the API from a lawfully obtained, unmodified exact-target APK. The lock checks the metadata and IL2CPP input hashes and the entire generated header tree. The published validation obtained identical 45,820-file trees in two runs. A few matching headers cannot substitute for the full-tree check. Keep APK contents, generated game headers and proprietary libraries out of commits and release assets.

Reused source and dependency caches must pass integrity checks. Diagnose dirty source, a changed patch, an unexpected symlink or a hash mismatch before proceeding. For an intentional recipe update, review the new inputs and regenerate the corresponding fingerprints and receipts as one release change; do not weaken verification to make an old receipt pass.

## Check API and ABI separately

Generated headers establish method signatures and layouts for the selected metadata. They do not prove that every linked native dependency uses the same ABI. Retain layout assertions and inspect relevant constructors, overloads, generic instantiations, hook targets and enum serialization when signatures or game behavior change. For uncertain semantics, compare the exact target's native implementation with the generated declarations.

Keep strict linking enabled. Exclude unintended debug libraries through the reviewed build configuration; do not mask missing symbols with permissive linker flags. Inspect ARM64 architecture, `DT_NEEDED`, SONAMEs, exported APIs and consumers of any changed exports. Distinguish declared package dependencies from actual native references.

The public closure report checks direct dependency names and declared versions. It explicitly does **not** establish all undefined-symbol resolution, C++ ABI compatibility, dynamically looked-up symbols or runtime hook correctness. Report additional checks only when actually performed.

## Design bounded fixes

Prefer a small patch tied to a reproducible defect. Preserve event order, map schema semantics, save contents and score eligibility unless the intended change specifically requires otherwise.

| Hazard | Review requirement |
| --- | --- |
| Managed pointers in native containers | Establish managed reachability across allocations. A `std::vector` of pointers is not automatically a GC root, but a borrowed vector whose objects remain rooted elsewhere is not automatically defective either. Inspect sorting temporary buffers and nested construction as well as the final destination. |
| Managed field updates | Use the appropriate managed API/write-barrier contract. Verify the target runtime before attributing a fix to incremental collection behavior. |
| Scene teardown and callbacks | Release the owned references at the correct lifecycle boundary. Check additive scenes, duplicate unloads and callbacks that reenter scene loading before cleanup returns. |
| Unity textures and sprites | Track separate object ownership and main-thread destruction. Destroy only newly owned objects on pre-transfer failure; cleanup after cache adoption must not invalidate retained data or borrowed UI references. |
| Asynchronous selection | Check stale completion, cancellation, request overlap and cache eviction. A selection-refresh log is not proof of a full parse or a unique selected map. |
| Save replacement | Separate safe copying from which copy should win. Atomic replacement alone does not prevent stale restoration or guarantee power-loss durability. |
| Shutdown crashes | Distinguish destructor/unload faults from startup failures and gameplay faults before changing a shared dependency. |

Use a focused regression when it can reproduce the defect meaningfully. Extracted production code with a failing baseline is stronger than a test that restates the replacement implementation. Label simulated GC, Unity or asynchronous behavior as a host model. It cannot prove actual IL2CPP reachability, native texture reclamation or headset performance.

## Validate and release in stages

1. **Review source and reconstruction.** Apply the patch to the pinned base, preserve licenses, inspect the complete resulting diff and verify that the exported patch reconstructs it. Keep a new candidate separate from release outputs.
2. **Run relevant host checks.** Run the affected regression and existing required checks. The repository's offline suites are `python -m unittest discover -s tests -v` and `python -m unittest discover -s builder -p test_builder.py -v`. These do not contact a headset. Syntax-only success is not a native build.
3. **Build and inspect.** Use the exact generated API, pinned dependencies and strict linker. Save compiler inputs, output hashes and symbols. Compare required exports and dependency closure against the prior artifact.
4. **Verify packaging.** Check target/version declarations, unique native registration, licenses, source provenance, dependencies and the build receipt. Run the existing package verifier for each affected profile. Keep a candidate's evidence status truthful in its metadata.
5. **Validate runtime when authorized.** Start with bounded initialization, then the affected feature, scene transition and restart where relevant. Use explicit stop conditions for pressure tests. Measure memory after idle as well as at peak, distinguish native/managed/graphics allocations, and avoid driving a device into exhaustion. Test an eligible completed score through local persistence and any claimed online service separately.
6. **Promote exact reviewed artifacts.** Update the manifest, recipe fingerprints, provenance and validation scope together. Do not replace a tested binary with a fresh rebuild while retaining its runtime claim. Preserve a rollback artifact and state any interrupted or uncompleted test.
7. **Publish only the reviewed set.** Audit licensing and source obligations, scan text and archive members for private data and game-derived payloads, and run the repository's CI for the intended commit. Re-download published assets and compare their hashes with the approved set. Record publication only after verifying it.

A new game target needs new input pins, API generation, ABI review, builds and runtime evidence. Preserve the old target's reproducible release rather than relabelling its binaries or editing its receipts. Installation, device testing and publication are separate actions from preparing a patch; follow the authorization for the current task.

## Leave a usable handoff

Record the problem and trigger, source base and patch hash, target/toolchain, dependency hashes, native and QMOD hashes, tests actually completed, unresolved findings and the next specific check. Use status words precisely: **source-reviewed**, **host-tested**, **syntax-checked**, **built**, **runtime-observed**, and **published** are different milestones.

Keep public evidence relative to the repository or a distributable artifact. Summarize private observations without uploading account data, personal settings, device identifiers, recordings or raw logs. A future maintainer should be able to reconstruct the public build without access to a previous session or private workstation.
