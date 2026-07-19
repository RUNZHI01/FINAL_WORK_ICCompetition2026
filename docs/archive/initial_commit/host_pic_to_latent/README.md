# host_pic_to_latent — 上位机图片→张量编码工具

从 `finalWork/` 提取并独立化的 JSCC 编解码管线，用于将图片编码为 latent 张量文件（供 USRP 无线传输）或反向还原验证。

## 自包含

本目录不依赖仓库中其他目录（`finalWork/`、`airfield/`、`Semantic-Communication/` 等），所有代码、模型权重、示例图片均已内置。

## 文件来源

### 我们自己写的

| 文件 | 说明 |
|---|---|
| `encode_latent.py` | 独立编码入口：图片 → JSCC Encoder → 量化 latent .pt |
| `decode_verify.py` | 解码验证入口：latent .pt → JSCC Decoder → 还原图 + PSNR/SSIM |
| `jscc/default_config.py` | 从原 `.pyc` 逆向重构的配置枚举（`ModelTypes`, `ModelModes`, `Args` 等） |
| `jscc/channel_configs.py` | 从原 `.pyc` 逆向重构的子网络通道配置解析 |

### 从 finalWork 复制的（未修改）

| 文件 | 来源 |
|---|---|
| `jscc/src/network/encoder.py` | `finalWork/客户端/jscc-test/jscc/src/network/encoder.py` |
| `jscc/src/network/sub_generator.py` | `finalWork/客户端/jscc-test/jscc/src/network/sub_generator.py` |
| `jscc/src/network/super_modules.py` | `finalWork/客户端/jscc-test/jscc/src/network/super_modules.py` |
| `jscc/src/datasets.py` | `finalWork/客户端/jscc-test/jscc/src/datasets.py` |
| `jscc/src/test_model.py` | `finalWork/客户端/jscc-test/jscc/src/test_model.py` |

### 从 finalWork 复制的（有少量修改）

| 文件 | 修改内容 |
|---|---|
| `jscc/src/utils.py` | 注释掉了 4 行训练用的 import（`src.model`, `src.super_model`, `src.test_model`, `default_config`），编码/解码不需要 |

### 数据文件

| 目录/文件 | 来源 |
|---|---|
| `checkpoint/origin/` | `finalWork/客户端/jscc-test/origin/` — 编码器+元数据权重 |
| `checkpoint/export/` | `finalWork/客户端/jscc-test/export/` — 解码器权重 |
| `airfield/` | `airfield/` — 5000 张示例图片 (.jpg) |

## 用法

```bash
# 编码：图片 → latent .pt
python encode_latent.py --test_num 10

# 解码验证：latent .pt → 还原图 + PSNR
python decode_verify.py --test_num 10

# 纯编解码验证（不加信道噪声）
python decode_verify.py --test_num 10 --no_noise
```

## 依赖

Python 3.8+，需安装：`torch`, `torchvision`, `Pillow`, `numpy`, `natsort`, `tqdm`

## Latent 文件格式

每个 `.pt` 文件包含一个 dict：

```python
{
    'quant':           torch.uint8 tensor [32, 32, 32],  # 量化后的 latent
    'scale':           float tensor,                      # 仿射量化 scale
    'zero_point':      float tensor,                      # 仿射量化 zero_point
    'snr':             int,                                # 编码时 SNR
    'config_str':      str,                                # 子网络配置 (如 '6_6_6_6_6_6_6')
    'checksum':        str (MD5 hex),                      # quant 的校验和
    'original_filename': str,                               # 原始图片文件名
}
```
