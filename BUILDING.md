# Building the local packages

Follow the [pinned Linux / Windows WSL build guide](builder/README.md). Start with its prerequisites and generate the headers from your own exact-version APK, then build the selected packages in dependency order.

The build output contains QMODs and `build-receipt.json`. Copy both to your Windows installation folder. Use the receipt with the [package verifier and installer](docs/INSTALLER-CLI.md). An incomplete set is rejected before any device changes.

The [validation notes](docs/VALIDATION.md) distinguish original mod runtime observations from newly rebuilt binaries. The builder's own `validation.json` records which portable build stages were actually exercised.
