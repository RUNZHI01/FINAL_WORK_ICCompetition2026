# NI USRP-2922 单机双天线 OTA 自环记录

更新时间：2026-04-26

## 当前物理条件

- 设备：`NI USRP-2922 / N210r4`
- 设备 IP：`192.168.10.2`
- TX 口：`TX/RX`
- RX 口：`RX2`
- 连接方式：**两个口都直接接天线**
- 说明：这不是“有线回环”，而是**单机近距离 OTA 自环**。结果可用于 smoke / 初步扫参，不应当直接当作正式链路基线。

## 官方例程

- 使用官方 C++ example：`/usr/libexec/uhd/examples/txrx_loopback_to_file`
- 本地包装脚本：`USRP292x/AntennaLoopbackSmoke.sh`
- 本地分析脚本：`USRP292x/AnalyzeLoopbackCapture.py`

## 设备探测结果

- `serial`: `30D1554`
- `FW Version`: `12.4`
- `FPGA Version`: `11.1`
- `RX antennas`: `TX/RX, RX2, CAL`
- `TX antennas`: `TX/RX, CAL`

## 第一轮 smoke

命令口径：

- `rate=1 Msps`
- `freq=915 MHz`
- `wave_type=SINE`
- `wave_freq=50 kHz`
- `tx_gain=0 dB`
- `rx_gain=0 dB`
- `ampl=0.02`
- `nsamps=200000`

结果：

- 官方例程运行成功，生成 `USRP292x/AntennaLoopbackShort.dat`
- 样本数：`200000 complex samples`
- 非零比：`0.8449`
- `mag_rms ≈ 165.46`
- `avg_power_dbfs_approx ≈ -45.93 dBFS`
- 目标 `50 kHz` 附近存在弱峰，但**最大峰贴近直流**

解释：

- 已经不是“完全收不到”，说明 TX/RX 路径和官方例程至少工作
- 但当前近场 OTA 自环里，**直流/泄漏/环境耦合**比目标音调更强
- 因此这轮只能记作：`official example smoke PASS, tone dominance FAIL`

## 小范围 sweep

### RunA

- `rate=1 Msps`
- `wave_freq=200 kHz`
- `tx_gain=0 dB`
- `rx_gain=0 dB`
- `ampl=0.02`
- `nsamps=100000`

结果：

- `avg_power_dbfs_approx ≈ -42.93 dBFS`
- `strongest_non_dc_hz ≈ -50.8 kHz`
- `strongest_non_dc_over_median_db ≈ 17.07 dB`
- `peak_near_expected_hz ≈ 198.7 kHz`
- `peak_near_expected_over_median_db ≈ 10.57 dB`

### RunB

- `rate=1 Msps`
- `wave_freq=200 kHz`
- `tx_gain=5 dB`
- `rx_gain=5 dB`
- `ampl=0.02`
- `nsamps=100000`

结果：

- `avg_power_dbfs_approx ≈ -42.93 dBFS`
- `strongest_non_dc_hz ≈ 261.9 kHz`
- `strongest_non_dc_over_median_db ≈ 20.54 dB`
- `peak_near_expected_hz ≈ 200.6 kHz`
- `peak_near_expected_over_median_db ≈ 9.82 dB`

### RunC

- `rate=1 Msps`
- `wave_freq=200 kHz`
- `tx_gain=10 dB`
- `rx_gain=10 dB`
- `ampl=0.05`
- `nsamps=100000`

结果：

- `avg_power_dbfs_approx ≈ -42.95 dBFS`
- `strongest_non_dc_hz ≈ -168.1 kHz`
- `strongest_non_dc_over_median_db ≈ 23.93 dB`
- `peak_near_expected_hz ≈ 195.3 kHz`
- `peak_near_expected_over_median_db ≈ 9.70 dB`

## 当前结论

- 在“两个口都直接接天线”的单机近场 OTA 自环条件下，官方例程可以稳定完成收发和抓样。
- 但目标音调在频谱中**不是主峰**，只能看到约 `10 dB` 量级的“目标频点附近可见峰”。
- 这说明当前物理布置更适合做：
  - 设备是否活着
  - 官方例程能否跑通
  - RX/TX 基本口径确认

不适合直接做：

- 干净的本机有线回环基线
- 严格可解释的 SNR / BER 留证
- 后续数据面参数冻结

## 建议下一步

优先级从高到低：

1. 如果要正式做“回环基线”，换成 `TX/RX -> 衰减器 -> RX2` 的**有线回环**
2. 如果暂时只能用天线，至少拉开距离、固定朝向，再重复当前官方例程
3. 先用这台设备继续做 `benchmark_rate`，把 host↔USRP streaming 基线补齐
