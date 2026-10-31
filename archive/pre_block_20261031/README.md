# Historical source snapshot

These sources, configurations, notebooks and tests belong to the protocol before
the daily block-window experiment. They are preserved as reference, with their
original bytes. Their command entrypoints are no longer supported. The active
package and test discovery exclude this directory.

`migration.json` records the old path, new path, size and SHA-256 of every moved
file. Historical calculated artifacts are under `outputs/archive/`, not inputs
for the revised protocol. Internal paths inside immutable artifacts can be
resolved through the manifest.

The current guide is `docs/decisions/daily-code-organization.md` at repository root.
