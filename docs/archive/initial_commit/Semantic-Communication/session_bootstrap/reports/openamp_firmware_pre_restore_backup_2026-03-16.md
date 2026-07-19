# OpenAMP firmware pre-restore backup — 2026-03-16

## Purpose

Before any live firmware replacement, preserve the currently deployed board firmware so a later rollback is trivial and evidence-backed.

## Board

- host: `100.121.87.73`
- user: `user`
- checked at: `2026-03-16 07:38 CST`

## Current live firmware captured

- live path: `/lib/firmware/openamp_core0.elf`
- live SHA-256: `c5391855db2f30cd906fb7b8534d9858e6eee61fd034bfff04954f25b8d6536c`
- live size: `895384`
- live mtime: `2026-03-15 23:35:10.275973931 +0800`

## Backup artifact created on board

- backup path: `/tmp/openamp_core0.elf.pre_restore.20260316_073858`
- backup SHA-256: `c5391855db2f30cd906fb7b8534d9858e6eee61fd034bfff04954f25b8d6536c`
- backup size: `895384`

## Verification

The backup SHA matches the currently deployed live firmware SHA exactly.

## Notes

This step is intentionally non-destructive.
No live firmware replacement has been performed yet.
The known-good candidate still available on board for possible later restore is:

- candidate path: `/home/user/phytium-dev/release_v1.4.0-jobdone-v14/example/system/amp/openamp_for_linux/phytiumpi_aarch64_firefly_openamp_core0.elf`
- candidate SHA-256: `afa9679f24f0d9d4ccd4c35e0c779e72573bfe839799d7f95586706977b23803`
- candidate size: `1649896`
