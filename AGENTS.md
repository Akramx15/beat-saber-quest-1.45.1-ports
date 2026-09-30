# Repository maintenance

Read `docs/maintenance/README.md` and `docs/maintenance/PORTING.md` before changing target versions, recipes, dependencies, packaging, or compatibility claims.

- Keep the public installation path and release notes in English. Existing translated documents may remain as secondary references.
- Treat `modpack.json`, `builder/build-lock.json`, source provenance, and artifact hashes as the release's technical contract. A README edit does not promote a local candidate into a release.
- Keep build checks, startup checks, sampled gameplay, full-level completion, local score persistence, and online upload as distinct evidence categories.
- Do not publish private device logs, serials, account identifiers, save files, calibration profiles, conversations, local machine paths, APKs, OBBs, game libraries, or generated game headers. Technical handoff notes must be generic and portable.
- Preserve upstream credit and each component's license. Do not assume the repository license covers third-party binaries.
- Avoid modifying player settings, saves, score eligibility, or a connected headset as part of a documentation or packaging task.
- Do not rewrite a published release's artifact identity to hide changes. New binaries need new provenance, checks, and an explicit release update.

For documentation-only changes, check relative links, actual CLI examples, and consistency with the current manifest. For installer or builder changes, run the corresponding offline checks described in the maintenance guide.
