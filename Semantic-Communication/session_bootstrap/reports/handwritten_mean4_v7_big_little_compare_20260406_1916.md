# Handwritten `mean4 v7` big.LITTLE Compare (`2026-04-06`)

> Update: this report captures the first handwritten-only big.LITTLE follow-up.
> A later same-day three-line compare now supersedes the cross-day comparison
> reading here:
> `session_bootstrap/reports/handwritten_mean4_v7_vs_trusted_current_acl_big_little_compare_20260406_1935.md`.

## Scope

- board: `Phytium-Pi`
- board mode: `OpenAMP 3-core Linux-visible`
- compare runner: `session_bootstrap/scripts/run_big_little_compare.sh`
- compare run id: `big_little_compare_20260406_191650`
- pipeline run id: `openamp3_handwritten_mean4_v7_big_little_current_20260406_191845`
- env: `session_bootstrap/tmp/openamp_3core_handwritten_mean4_v7_big_little_20260406.env`
- artifact sha: `bf255cd4bb29408b30b50bce2ad8713a260c5e45efc2d0e831bd293eec9edecb`

## Board State

- `hostname=Phytium-Pi`
- `nproc=3`
- `On-line CPU(s) list=0-2`
- `remoteproc0=running`
- compare snapshots stayed stable at `online_cpu_changed_across_compare = False`
- affinity suggestion remained `big_cores = [2]`, `little_cores = [0, 1]`

## Result

| Line | Artifact SHA | Serial reconstruction median (ms/image) | Pipeline total wall / 300 (ms/image) | Pipeline run median (ms) | Throughput uplift |
|---|---|---:|---:|---:|---:|
| `Handwritten mean4 v7 line` | `bf255cd4...edecb` | `345.609` | `249.393` | `240.885` | `38.706%` |
| `2026-04-04 Handwritten final` | `2aa25d2b...e216` | `342.927` | `252.584` | `243.550` | `35.489%` |
| `2026-04-04 Trusted Current` | `6f236b07...6dc1` | `360.218` | `251.913` | `242.498` | `44.102%` |
| `2026-04-04 ACL integration line` | `602371c2...edba` | `349.374` | `258.933` | `249.829` | `34.705%` |

## Interpretation

- Relative to the old handwritten final, `v7` makes the handwritten line's serial reconstruction slightly slower (`+2.682 ms/image`), but improves the actual big.LITTLE endpoint from `252.584` to `249.393 ms/image`, and lifts throughput uplift from `35.489%` to `38.706%`.
- Relative to trusted current, `v7` still does not exceed the old trusted-current uplift ratio (`38.706%` vs `44.102%`), but the new handwritten endpoint is now faster in absolute pipeline throughput terms: `249.393 ms/image` vs `251.913 ms/image`.
- Relative to the ACL line, `v7` is better on both absolute pipeline endpoint (`-9.540 ms/image`) and uplift (`+4.001` pct points).

## Conclusion

The latest handwritten `mean4 v7` line should now be treated as:

- the current best documented handwritten `mean4` branch for serial payload,
- a better big.LITTLE endpoint than the old handwritten final,
- and the current best documented OpenAMP 3-core pipeline endpoint among the repo's three comparison lines,

while still not matching trusted current's historical uplift ratio.

## Primary Evidence

- `session_bootstrap/reports/daily_20260404_openamp_3core_big_little_followup/big_little_compare_20260406_191650.md`
- `session_bootstrap/reports/daily_20260404_openamp_3core_big_little_followup/big_little_compare_20260406_191650.json`
- `session_bootstrap/reports/daily_20260404_openamp_3core_big_little_followup/openamp3_handwritten_mean4_v7_big_little_current_20260406_191845.md`
- `session_bootstrap/reports/daily_20260404_openamp_3core_big_little_followup/openamp3_handwritten_mean4_v7_big_little_current_20260406_191845.json`
