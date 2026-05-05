# OpenAMP Real-Candidate Runtime-Mismatch Hypotheses

> Date: 2026-03-14  
> Scope: rank the most plausible causes of the remaining runtime mismatch between the board-shipped official `openamp_core0.elf` and the real remote `release_v1.4.0` candidate.  
> Strict correction: the earlier local `/tmp/.../pe2204_aarch64_phytiumpi_openamp_core0.elf` is **not** treated as the candidate here. `/tmp/phytium-standalone-sdk` is used only for build-mechanics context.

## Confirmed Facts From Durable Evidence

- The compared binaries are:
  - official: `session_bootstrap/reports/old_fw_compare_20260314/openamp_core0_official.elf`, size `1650448`
  - real candidate: remote `release_v1.4.0` path recorded in `official_vs_release_v1.4.0.summary.json`, size `1627224`
- The remaining file-size gap is `23224` bytes.
- Both `PT_LOAD` file-resident sizes match exactly:
  - `load0 filesz = 114688`
  - `load1 filesz = 4096`
- `.resource_table` matches byte-for-byte:
  - size `4096`
  - identical SHA-256 `1b2083096dcd01a3a0855015c37b7e6d50dc71f4336d5c68d7c99236ff379794`
- The runtime payload is still not byte-identical:
  - `load0` hash differs
  - `.text` hash differs, but size stays `92800`
  - `.data` hash differs, but size stays `8192`
  - `.rodata` hash differs, and size changes from official `11217` to candidate `10801`
- Section shape differs even though the load envelope matches:
  - official has `23` section headers
  - candidate has `26`
  - candidate adds `.end_text`, `.end_rodata`, `.end_ram`
  - official instead shows `.le_shell` size `0x400`, while candidate `.le_shell` is size `0`
- The official ELF definitely contains runtime strings for compile/version banners and the demo RPMsg service name, so `.rodata` is not just opaque tables.
- Fresh live remote access is blocked in this sandbox. Durable capture already in the repo shows `socket: Operation not permitted` / `ssh: connect to host 100.121.87.73 port 22: failure` in `session_bootstrap/reports/openamp_fw_delta_compare_20260314/candidate_fetch_error.txt`.

Evidence used:

- `session_bootstrap/reports/old_fw_compare_20260314/official_vs_release_v1.4.0.summary.json`
- `session_bootstrap/reports/old_fw_compare_20260314/live_segment_hash_evidence_2026-03-14.json`
- `session_bootstrap/reports/old_fw_compare_20260314/official.sections.txt`
- `session_bootstrap/reports/old_fw_compare_20260314/release_v1.4.0.sections.txt`
- `session_bootstrap/reports/old_fw_compare_20260314/official.segments.txt`
- `session_bootstrap/reports/old_fw_compare_20260314/release_v1.4.0.segments.txt`
- `session_bootstrap/reports/openamp_phase5_firmware_delta_classification_2026-03-14.md`

## Supporting Context From `/tmp` Mechanics Only

This subsection is mechanism-only context, not identity evidence for the real candidate.

- The local SDK default linker script `tools/build/ld/aarch64_ram.ld` emits `.end_text`, `.end_rodata`, `.end_ram`, and `.le_shell`.
- The local OpenAMP build map shows many archives linked under `--whole-archive`, including `libuser.a`, platform libs, `lib_openamp.a`, and libc/newlib pieces.
- The same local map shows `.data` and `.rodata` are populated by more than just the RPMsg demo itself: they also hold platform descriptors, MMU tables, ops tables, string pools, and libc/newlib initialized state.

This makes config-generated constants, linker-script section shaping, string-pool drift, and archive/link-order sensitivity credible mechanisms for a close-but-not-identical runtime payload.

## Inferences / Ranked Hypotheses

### H1. Most plausible: same firmware family, but a non-identical build recipe/config generated different runtime constants and literals

Why this ranks first:

- The remoteproc contract looks aligned: same `PT_LOAD` sizes, same load addresses, same `.resource_table`.
- Yet `.text` and `.data` differ in content without changing size, and `.rodata` differs with only a small size delta (`416` bytes).
- That pattern fits a nearby build recipe more naturally than a different platform image:
  - generated config headers or board constants
  - logging/banner/string-pool differences
  - initialized descriptor/table values in `.data`
  - small constant-folding changes that perturb instruction bytes while preserving section size

This is still an inference, not a proof.

### H2. Plausible: linker-script / section-shaping / archive-order drift within the same SDK lineage

Why this ranks second:

- The real candidate has `.end_text`, `.end_rodata`, `.end_ram`, while the official file does not.
- The official file instead exposes a non-zero `.le_shell`, while the candidate does not.
- `/tmp` build mechanics show these section names come from the default linker script, and the build pulls in many archives under `--whole-archive`.

That combination can perturb:

- padding and section boundaries
- symbol values derived from region ends
- literal-pool placement
- object/function ordering inside `.text`
- initialized pointer/table bytes inside `.data`

without changing the overall `PT_LOAD` file sizes.

### H3. Plausible, but less constrained: a small source/library revision delta near `openamp_for_linux` or its platform glue

Why it remains plausible:

- Simultaneous differences in `.text`, `.rodata`, and `.data` can also come from one or a few nearby source changes rather than from pure build mechanics.
- Because `.resource_table` is exact, the likely source delta would be outside the remoteproc ABI contract itself, not a different memory-map definition.

This ranks below H1/H2 because the current durable evidence does not yet show whether the first runtime diffs land in banner strings and tables, or in substantive control-flow code.

### Deprioritized / Not Ranked Higher

- Large runtime/resource-layout mismatch is not a good explanation:
  - contradicted by matching `PT_LOAD` sizes and identical `.resource_table`
- Pure debug-only drift is not sufficient:
  - contradicted by differing `load0`, `.text`, `.data`, and `.rodata`
- Compiler-version drift is intentionally not ranked here:
  - per task context, the real candidate already matched the official `10.3` comment

## Recommended Next Discriminator(s)

### First discriminator to request when real-candidate access is available

Capture section-local diffs from the **real remote `release_v1.4.0` candidate only**, not from the local `/tmp` ELF:

```bash
readelf -SW phytiumpi_aarch64_firefly_openamp_core0.elf
objdump -drwC -j .text phytiumpi_aarch64_firefly_openamp_core0.elf
objdump -s -j .rodata -j .data phytiumpi_aarch64_firefly_openamp_core0.elf
nm -n phytiumpi_aarch64_firefly_openamp_core0.elf
```

Most useful interpretation:

- If the first diffs cluster in banner strings, string pools, ops tables, or initialized descriptors, H1/H2 gets stronger.
- If the first diffs spread through startup, MMU, interrupt, or RPMsg control-flow code, H3 gets stronger.

### Second discriminator if build artifacts can be captured

Ask for the real candidate's:

- generated `sdkconfig`
- actual linker script path/content
- final link line or `.map`

That is the cleanest way to separate:

- config-generated constant drift
- linker-script / archive-order drift
- actual source/object revision drift

## Current Best Next Step

The best next step is **not** another size-only comparison. It is a first-difference capture for `.text`, `.rodata`, and `.data` from the real `release_v1.4.0` candidate, because that is the smallest discriminator that can tell whether the remaining mismatch is mostly build-mechanical or truly source-semantic.
