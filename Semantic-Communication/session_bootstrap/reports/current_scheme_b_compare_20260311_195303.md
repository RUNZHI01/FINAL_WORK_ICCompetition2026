# Current-only Scheme B Compare

- mode: current-only payload-symmetric compare
- rebuild_only_sha: `2fcf773fa34d6aa69f80740ffedde33faaf265a045cae97b72022ae2c62a8449`
- incremental_sha: `1946b08e6cf20a1259fa43f9e849a06f50ae1230c08d4df7081fba1edae4c644`

## Runs

| profile | archive | median ms | mean ms | min ms | max ms | variance ms^2 | output shape |
|---|---|---:|---:|---:|---:|---:|---|
| rebuild-only current | `/home/user/Downloads/jscc-test/current_scheme_b_compare_20260311_195303_rebuild_only` | 2479.246 | 2480.641 | 2478.028 | 2485.425 | 6.576738 | `[1, 3, 256, 256]` |
| incremental current | `/home/user/Downloads/jscc-test/current_scheme_b_compare_20260311_195303_incremental` | 152.36 | 152.528 | 152.18 | 154.162 | 0.315991 | `[1, 3, 256, 256]` |

## Readout

- incremental vs rebuild-only delta: `-2326.886 ms`
- incremental improvement vs rebuild-only: `93.85%`
- incremental speedup vs rebuild-only: `16.272x`
