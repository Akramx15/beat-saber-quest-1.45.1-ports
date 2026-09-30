# Maintenance notes

This directory is the technical starting point for maintaining the experimental Quest ports, including work assisted by coding agents. Installation instructions remain in the [main README](../../README.md); the porting workflow is in [PORTING.md](PORTING.md).

Start with the checked-out repository and the artifacts being investigated. Record the commit, dirty files, release tag, package versions, QMOD hashes and native-library hashes. A package installed elsewhere, a similarly named candidate, or an earlier successful run is not evidence about these bytes.

## Sources of truth

| Question | Repository evidence |
| --- | --- |
| What does this release offer? | [modpack.json](../../modpack.json): target, profiles, package sources, hashes and local-build fingerprints. |
| How is a local package reconstructed? | [builder/build-lock.json](../../builder/build-lock.json), its referenced patches and manifests, and the [builder guide](../../builder/README.md). |
| What did a particular build produce? | Its `build-receipt.json`, compared with the manifest and locked inputs. |
| Which checks were completed? | [Public validation notes](../VALIDATION.md), [portable-build validation](../../builder/validation.json), and any narrowly scoped reports under `validation/`. |
| How does installation behave? | [Installer reference](../INSTALLER-CLI.md) and the checked-in installer implementation/tests. |

The lock contains historical preparation-state labels. The dated validation report describes completed build work; neither changes the locked inputs or certifies runtime behavior. A newer upstream version also does not establish compatibility with this exact game build.

## Release boundary

As of September 30, 2026, the checked-in manifest identifies `v0.1.0-experimental.1`, targeting **standalone Quest Beat Saber 1.45.1_27839**, version code **3071**, with **Scotland2**. It lists 28 packages and 12 local build recipes. Recheck these facts when continuing from a later commit.

The public portable-build report records successful compilation and strict linking for all 12 recipes. Its final archive check covered 28 QMODs and 29 ARM64 libraries across four profiles. These are build and packaging results. Runtime observations of earlier local binaries do not transfer automatically to newly rebuilt outputs.

Later engineering work is summarized below to prevent it being mistaken for shipped functionality. These follow-ups are **not incorporated into this manifest or its pinned recipes**. Private artifacts are not required to build the public release, and are not linked here.

| Follow-up reviewed by September 30 | Recorded scope and remaining limit |
| --- | --- |
| PlayerDataKeeper checked temporary copy and atomic replacement | A later local build passed restore, save and restart checks. Stale-cache selection and power-loss durability remain separate problems. PlayerDataKeeper is not listed in this public manifest. |
| CustomJSONData legacy-event managed rooting | A later local build exercised the legacy conversion path, brief gameplay and return to selection. This is not long-term stability proof; the published recipe remains the earlier version. |
| CustomJSONData v3 managed rooting | Private source candidate, focused host checks and target syntax check; no linked runtime candidate validated. Sorting and collection-time lifetime questions remain. |
| JDFixer conditional-rule identity and priority | Private build and host regression checks passed; device behavior remains untested. JDFixer is not listed in this public manifest. |
| PlaylistCore temporary cover ownership | Private source candidate passed target syntax and host checks; no native build or device validation. |
| BetterSongSearch stale cover callbacks | Private build and host review completed; device validation remains pending. |

## Open validation work

- **Memory under rapid selection:** severe pressure was observed. A later bounded run stayed above its stop thresholds without a new fix, but did not reproduce a controlled identical workload or identify allocation ownership. Do not describe RAM exhaustion as fixed or assign it to a mod without further evidence.
- **Score eligibility and persistence:** an eligible completed result still needs matching local-save and online-submission evidence. A generic submission-blocked log does not identify the responsible setting or mod. Preserve existing eligibility checks.
- **Save restoration:** a safe copy can still restore an obsolete cache. Review conflict selection separately from copy integrity, serialization and the game's normal save behavior.
- **Remaining runtime coverage:** CJD v3 and shutdown lifetime, cover/texture ownership, online features, and full Windows/WSL installation coverage remain limited. Source findings and host models do not establish an incident's runtime cause.

Keep future public handoffs self-contained: summarize the exact tested behavior and its limits, cite distributable artifacts, and omit personal data, private recordings, raw device logs and machine-specific paths.
