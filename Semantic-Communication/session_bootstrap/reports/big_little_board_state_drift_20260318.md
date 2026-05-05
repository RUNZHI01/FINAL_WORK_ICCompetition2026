# big.LITTLE 板态漂移复盘（2026-03-18）

## 结论

同一条 trusted current artifact lineage（SHA `6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`）、同 `SNR=10` 的 direct current rerun，在同一天内可从 `347.375 ms/image` 恢复到 `239.233 ms/image`。这说明本轮 big.LITTLE / performance-drift 调查里，**板态 / CPU online set 是 primary factor，不应再把较慢结果主要归因为 artifact lineage**。

## 复盘序列

| 场景 | direct current rerun | CPU online | 说明 |
|---|---:|---|---|
| degraded board | `347.375 ms/image` | `0-2` | CPU3 offline 时的新鲜 direct rerun |
| intermediate recovery observation | `295.255 ms/image` | 未在本页单独固化 | 同一恢复调查中的中间观测点 |
| post-reboot healthy board | `239.233 ms/image` | `0-3` | reboot 后 CPU online 恢复完整后的新鲜 direct rerun |

## 关联 reference

- 历史最佳 direct current e2e 参考仍是 `session_bootstrap/reports/inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.md`
  - current median: `230.339 ms/image`
  - `SNR=10`
  - SHA256: `6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`
- 新的健康板态 big.LITTLE apples-to-apples compare 是 `session_bootstrap/reports/big_little_compare_20260318_123300.md`
  - serial current median: `231.522 ms/image`
  - pipeline current median: `134.617 ms/image`
  - throughput uplift: `56.077%`

## 现在应怎样解读 big.LITTLE 结果

- `session_bootstrap/reports/big_little_compare_20260318_123300.md` 应成为默认 big.LITTLE reference，因为它对应的是恢复后的健康板态。
- `session_bootstrap/reports/big_little_compare_20260318_095615.md` 现在应与这份复盘一起解读为 degraded-board 证据，而不是默认 headline。
- 后续任何 rerun / compare 前后，都应显式记录 CPU online set，避免把板态变化误写成 artifact lineage 变化。
