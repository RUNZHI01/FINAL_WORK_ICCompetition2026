# Same-Day OpenAMP 3-core big.LITTLE Compare (`2026-04-06`)

## Scope

- board: `Phytium-Pi`
- board mode: `OpenAMP 3-core Linux-visible`
- compare window: `2026-04-06 19:16 -> 19:34 +0800`
- affinity pattern: `big_cores = [2]`, `little_cores = [0, 1]`
- all three compares kept `online_cpu_changed_across_compare = False`

## Result

| Line | Compare Run | Artifact SHA | Serial reconstruction median (ms/image) | Pipeline total wall / 300 (ms/image) | Pipeline run median (ms) | Throughput uplift |
|---|---|---|---:|---:|---:|---:|
| `Handwritten mean4 v7 line` | `big_little_compare_20260406_191650` | `bf255cd4...edecb` | `345.609` | `249.393` | `240.885` | `38.706%` |
| `Trusted Current` | `big_little_compare_20260406_192859` | `6f236b07...6dc1` | `347.341` | `257.388` | `248.851` | `34.569%` |
| `ACL integration line` | `big_little_compare_20260406_193231` | `602371c2...edba` | `352.158` | `262.922` | `250.790` | `33.814%` |

## Delta vs `Handwritten mean4 v7 line`

- vs `Trusted Current`
  - serial reconstruction: `-1.732 ms/image`
  - pipeline endpoint: `-7.995 ms/image`
  - pipeline run median: `-7.966 ms`
  - throughput uplift: `+4.137` pct points
- vs `ACL integration line`
  - serial reconstruction: `-6.549 ms/image`
  - pipeline endpoint: `-13.530 ms/image`
  - pipeline run median: `-9.905 ms`
  - throughput uplift: `+4.892` pct points

## Conclusion

On the same day, on the same board mode, and under the same big.LITTLE binding path,
the latest handwritten `mean4 v7` line is now the best of the repo's three active
comparison lines on all three relevant big.LITTLE metrics:

- lowest serial reconstruction median,
- lowest pipeline endpoint,
- highest throughput uplift.

This supersedes the earlier cross-day reading that only proved `v7` against the old
handwritten final and historical `2026-04-04` references.

## Primary Evidence

- `session_bootstrap/reports/daily_20260404_openamp_3core_big_little_followup/big_little_compare_20260406_191650.md`
- `session_bootstrap/reports/daily_20260404_openamp_3core_big_little_followup/big_little_compare_20260406_192859.md`
- `session_bootstrap/reports/daily_20260404_openamp_3core_big_little_followup/big_little_compare_20260406_193231.md`
- `session_bootstrap/reports/daily_20260404_openamp_3core_big_little_followup/openamp3_handwritten_mean4_v7_big_little_current_20260406_191845.md`
- `session_bootstrap/reports/daily_20260404_openamp_3core_big_little_followup/openamp3_trusted_current_big_little_current_20260406_193058.md`
- `session_bootstrap/reports/daily_20260404_openamp_3core_big_little_followup/openamp3_acl_big_little_current_20260406_193428.md`
