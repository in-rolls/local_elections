# Integration receipts

This directory records how state-owned inputs entered the pooled dataset. It is
not a state dataset and is excluded from state discovery and generated coverage.

The state repositories own source evidence and parsing. The central repository
records input revisions, checksums, transformations, and integration checks.
Dated receipts describe the build that produced them; they are not declarations
that the current release has passed its checks.

The [UP working-dataset receipt](uttar_pradesh/2026-09-10/working_dataset_receipt.json)
records an earlier integration from a dirty working tree and explicitly sets
`clean_release` to `false`. Preserve it as historical provenance. Its old hashes,
counts, and local backup path must not be substituted for the current release's
[manifest](../../MANIFEST.json) or treated as proof of a reproducible release.

Keep future receipts under the relevant state and build date. Store source
documents and parser outputs in the owning state repository, not here.
