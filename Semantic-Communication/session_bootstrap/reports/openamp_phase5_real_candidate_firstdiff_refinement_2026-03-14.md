# OpenAMP Real-Candidate First-Difference Refinement

> Date: 2026-03-14
> Scope: use the newly captured real-candidate `readelf` / `objdump` / `nm` first-difference artifacts to refine the remaining OpenAMP convergence diagnosis for the real `release_v1.4.0` candidate.

## Bottom Line

The new first-difference capture more strongly supports **rodata/string-pool drift plus linker/build-mechanics drift** than **substantive control-flow/source divergence**.

What it actually revealed is narrower and stronger than the earlier size-only hypothesis set:

- the earliest concrete `.rodata` differences are embedded build-path and compile-timestamp strings
- the earliest true `.text` opcode differences are `main`-level `adrp`/`add` string-address materializations, not startup/interrupt/MMU/RPMsg logic changes
- the visible `.data` differences are rebased pointers into shifted `.rodata` objects
- the only clear text-symbol reordering is a small `metal_*` helper cluster, consistent with function-order or link-layout drift

That pushes the likely cause category toward **build/config/link shaping with string-pool drift**, with only limited evidence for a real behavioral source delta.

## Strongest New Evidence

### 1. `.rodata` now shows direct build-environment drift, immediately at the section start

The first bytes of `.rodata` are not opaque tables. They are embedded source-path and build-banner strings.

- official `.rodata` starts with a long old-tree path under `/home/zero/work/.../phytium-standalone-sdk/.../fgic_v3.c`
- candidate `.rodata` starts with a different release-tree path under `/home/user/phytium-dev/release_v1.4.0/.../fgic_v3.c`
- the embedded compile timestamp also differs:
  - official shows `Oct  9 2024` / `16:58:22`
  - candidate shows `Mar 14 2026` / `03:41:00`

This is direct evidence that the front of `.rodata` is being perturbed by build-path / build-time strings. It strongly explains why downstream `.rodata` symbol addresses slide earlier in the candidate.

### 2. The first real opcode difference in `.text` lands in `main`, and it is string-address setup

After normalizing away objdump formatting differences and comparing address/opcode pairs, the first true opcode mismatch appears in `main` at `0xb0101578`.

The changed instructions are `add` immediates that materialize `.rodata` offsets for banner/version `printf` calls:

- official uses offsets like `#0x205`, `#0x20e`, `#0x21a`
- candidate uses earlier offsets like `#0x1ee`, `#0x1f7`, `#0x203`

The code before that point matches at the opcode level. The first-difference capture therefore does **not** point at an early control-flow fork in vector setup, interrupt entry, or low-level bring-up.

### 3. Sampled `.data` differences are pointer rebases into shifted `.rodata`, not changed scalar state

The first `.data` mismatches at `0xb011a000`, `0xb011a0b0`, `0xb011a160`, and later at `0xb011b270` are pointer-value changes from one set of `.rodata` addresses to another.

Examples:

- `0xb0117511 -> 0xb01174fa`
- `0xb011751f -> 0xb0117508`
- `0xb01199d0/0xb0119930`-style shifts in later pointer tables

The surrounding non-pointer fields in those windows stay the same. This makes the `.data` delta look like initialized references to relocated strings/tables, not changed runtime parameters or protocol state.

### 4. Text-symbol movement is narrow: six named functions move, all in one `metal_*` helper cluster

`nm` comparison shows:

- `355 / 361` single-occurrence text symbols keep the same start address
- only these six move:
  - `metal_init`
  - `metal_finish`
  - `metal_io_init`
  - `metal_io_block_read`
  - `metal_io_block_write`
  - `metal_io_block_set`

The corresponding disassembly shows the same function bodies relocated as a block rather than obviously rewritten. That is consistent with local function-order / object-layout drift inside libmetal, not with broad semantic divergence across the firmware.

## Hypothesis Impact

### Stronger now

- **H1: same firmware family, but non-identical build recipe/config generated different literals and constants**
  - stronger because the first raw `.rodata` bytes are build-path and compile-time strings, and the first `.text` delta is just code that points into those strings
- **H2: linker-script / section-shaping / link-order drift within the same SDK lineage**
  - stronger because the `.end_*` sections remain real, and the moved `metal_*` block looks like localized text-layout drift rather than broad logic churn

### Weaker now

- **H3: substantive control-flow/source divergence**
  - weaker because the first-difference capture did not surface an early logic split in startup, interrupt, MMU, or RPMsg control flow
  - still not eliminated, because `.text` is not globally byte-identical and only a sampled subset of moved functions was inspected closely

## What Is Still Unproven

- This is **not** proof that the two loadable payloads are behaviorally identical.
- The current evidence does **not** fully separate:
  - build-path / timestamp macro drift
  - linker-script symbol/export differences
  - local function-order or object-order drift
  - any small remaining nearby source revision delta

The new capture only says the first observed divergence pattern looks much more like **layout/literal/pointer rebasing** than like **early substantive logic divergence**.

## Refined Conclusion

The first-difference capture now more strongly supports the cause category:

**rodata/string-pool drift plus config/link-build mechanics, with a small localized function-order change, rather than substantive control-flow/source divergence.**

The remaining unproven part is whether there is any small true source delta left after accounting for those mechanical effects.

## Best Next Discriminator

The single best next discriminator after this evidence is the **real candidate final link map** from the `release_v1.4.0` build.

That would directly show whether the remaining `.text`/`.rodata`/`.data` differences come from:

- object/function ordering
- linker-script section exports
- generated config/macros
- or a real object-content delta

## Evidence Files

- `session_bootstrap/reports/old_fw_compare_20260314/real_candidate_firstdiff_20260314/official.readelf_sections.txt`
- `session_bootstrap/reports/old_fw_compare_20260314/real_candidate_firstdiff_20260314/release_v1.4.0.readelf_sections.txt`
- `session_bootstrap/reports/old_fw_compare_20260314/real_candidate_firstdiff_20260314/official.objdump_text.txt`
- `session_bootstrap/reports/old_fw_compare_20260314/real_candidate_firstdiff_20260314/release_v1.4.0.objdump_text.txt`
- `session_bootstrap/reports/old_fw_compare_20260314/real_candidate_firstdiff_20260314/official.objdump_rodata_data.txt`
- `session_bootstrap/reports/old_fw_compare_20260314/real_candidate_firstdiff_20260314/release_v1.4.0.objdump_rodata_data.txt`
- `session_bootstrap/reports/old_fw_compare_20260314/real_candidate_firstdiff_20260314/official.nm.txt`
- `session_bootstrap/reports/old_fw_compare_20260314/real_candidate_firstdiff_20260314/release_v1.4.0.nm.txt`
- `session_bootstrap/reports/openamp_phase5_real_candidate_runtime_mismatch_hypotheses_2026-03-14.md`
- `session_bootstrap/reports/openamp_phase5_firmware_delta_classification_2026-03-14.md`
- `session_bootstrap/reports/old_fw_compare_20260314/live_segment_hash_evidence_2026-03-14.json`
- `session_bootstrap/reports/old_fw_compare_20260314/official_vs_release_v1.4.0.summary.json`
