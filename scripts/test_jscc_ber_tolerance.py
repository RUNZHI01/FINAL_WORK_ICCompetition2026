#!/usr/bin/env python3
"""test_jscc_ber_tolerance.py — JSCC 模型对传输误码的容忍度实验

在 float32 latent 的二进制表示中注入随机比特翻转（模拟数字传输误码），
然后送入 TVM Generator 重建图像，测量 PSNR/SSIM 退化。

目的：确定 USRP 传输链路可接受的最大 BER，判断是否可以简化/去掉 FEC。

用法（板端）:
  /home/user/anaconda3/envs/tvm310_safe/bin/python test_jscc_ber_tolerance.py \\
      --artifact /home/user/Downloads/jscc-test/jscc_opus_final_mean4_v7_20260406/tvm_tune_logs/optimized_model.so \\
      --input-dir /home/user/Downloads/jscc-test/简化版latent_npz \\
      --num-images 30 \\
      --output /tmp/ber_results.json
"""

import argparse
import json
import os
import struct
import sys
import time

import numpy as np


# ── 比特误码注入 ──

def inject_bit_errors(data: bytearray, ber: float) -> int:
    """在字节数组中注入随机比特翻转。

    Args:
        data: 原始字节数组（会被原地修改）
        ber: 目标比特误码率（每比特翻转概率）

    Returns:
        实际翻转的比特数
    """
    total_bits = len(data) * 8
    num_flips = np.random.binomial(total_bits, ber)
    if num_flips == 0:
        return 0

    # 随机选择要翻转的比特位置
    positions = np.random.choice(total_bits, size=num_flips, replace=False)
    for pos in positions:
        byte_idx = pos // 8
        bit_idx = pos % 8
        data[byte_idx] ^= (1 << bit_idx)

    return int(num_flips)


# ── PSNR / SSIM 计算（纯 numpy，不依赖 skimage）──

def compute_psnr(img1: np.ndarray, img2: np.ndarray) -> float:
    """计算 PSNR（假设像素值范围 [0, 1]）。"""
    mse = np.mean((img1 - img2) ** 2)
    if mse < 1e-10:
        return float('inf')
    return 10.0 * np.log10(1.0 / mse)


def _gaussian_kernel(size: int = 11, sigma: float = 1.5) -> np.ndarray:
    """生成高斯核。"""
    coords = np.arange(size) - size // 2
    g = np.exp(-(coords ** 2) / (2 * sigma ** 2))
    kernel = np.outer(g, g)
    return kernel / kernel.sum()


def _ssim_channel(img1: np.ndarray, img2: np.ndarray,
                  kernel: np.ndarray) -> float:
    """计算单通道 SSIM。"""
    from scipy.ndimage import convolve

    C1 = (0.01) ** 2
    C2 = (0.03) ** 2

    mu1 = convolve(img1, kernel, mode='reflect')
    mu2 = convolve(img2, kernel, mode='reflect')

    mu1_sq = mu1 ** 2
    mu2_sq = mu2 ** 2
    mu1_mu2 = mu1 * mu2

    sigma1_sq = convolve(img1 ** 2, kernel, mode='reflect') - mu1_sq
    sigma2_sq = convolve(img2 ** 2, kernel, mode='reflect') - mu2_sq
    sigma12 = convolve(img1 * img2, kernel, mode='reflect') - mu1_mu2

    numerator = (2 * mu1_mu2 + C1) * (2 * sigma12 + C2)
    denominator = (mu1_sq + mu2_sq + C1) * (sigma1_sq + sigma2_sq + C2)

    ssim_map = numerator / denominator
    return float(ssim_map.mean())


def compute_ssim(img1: np.ndarray, img2: np.ndarray) -> float:
    """计算多通道 SSIM（CHW 格式）。"""
    try:
        kernel = _gaussian_kernel()
        if img1.ndim == 3:  # [C, H, W]
            ssim_vals = [_ssim_channel(img1[c], img2[c], kernel)
                         for c in range(img1.shape[0])]
            return float(np.mean(ssim_vals))
        else:
            return _ssim_channel(img1, img2, kernel)
    except ImportError:
        # scipy 不可用，返回 NaN
        return float('nan')


# ── Latent 加载（支持量化格式和直接格式）──

def load_latent(npz_path: str) -> np.ndarray:
    """从 .npz 加载 latent 张量，返回 float32 [1, 32, 32, 32]。"""
    data = np.load(npz_path)
    if 'latent' in data:
        latent = data['latent'].astype(np.float32)
    elif 'quant' in data:
        quant = data['quant']
        scale = float(data['scale'])
        zero_point = float(data['zero_point'])
        latent = (quant.astype(np.float32) - zero_point) * scale
    else:
        raise KeyError(f"npz keys: {list(data.keys())}, "
                       f"需要 'latent' 或 'quant'+'scale'+'zero_point'")

    if latent.ndim == 3:
        latent = latent[np.newaxis]  # [32,32,32] → [1,32,32,32]
    return latent


# ── 主实验 ──

def run_experiment(args) -> dict:
    """运行 BER 容忍度实验。"""

    # 加载 TVM 模型
    import tvm
    from tvm import relax

    dev = tvm.cpu(0)
    lib = tvm.runtime.load_module(args.artifact)
    vm = relax.VirtualMachine(lib, dev)
    fn = vm['main']

    print(f'[experiment] TVM 模型加载完成: {args.artifact}')

    # TVM runtime tensor 创建（兼容不同版本）
    def runtime_tensor(array, dev):
        rt = getattr(tvm, 'runtime', None)
        fn = getattr(rt, 'tensor', None) if rt is not None else None
        if fn is None and rt is not None:
            nd = getattr(rt, 'ndarray', None)
            if nd is not None:
                fn = lambda arr, device: nd.array(arr, device)
        if fn is None:
            raise AttributeError('tvm.runtime has neither tensor nor ndarray.array')
        return fn(array, dev)

    # 收集 latent 文件
    npz_files = sorted([
        os.path.join(args.input_dir, f)
        for f in os.listdir(args.input_dir)
        if f.endswith('.npz')
    ])

    if not npz_files:
        print(f'[error] 未找到 .npz 文件: {args.input_dir}')
        sys.exit(1)

    num_images = min(args.num_images, len(npz_files))
    npz_files = npz_files[:num_images]
    print(f'[experiment] 使用 {num_images} 个 latent 文件')

    # BER 级别
    ber_levels = [0, 1e-6, 1e-5, 1e-4, 3e-4, 1e-3, 3e-3, 1e-2]
    ber_labels = ['0', '1e-6', '1e-5', '1e-4', '3e-4', '1e-3', '3e-3', '1e-2']

    # 先计算干净重建作为参考
    print(f'\n[Phase 1] 计算 {num_images} 张干净重建 ...')
    clean_reconstructions = []
    clean_times = []

    for i, npz_path in enumerate(npz_files):
        latent = load_latent(npz_path)
        t0 = time.perf_counter()
        output = fn(runtime_tensor(latent, dev))
        t1 = time.perf_counter()
        result = output.numpy()[0]  # [3, 256, 256]
        clean_reconstructions.append(result)
        clean_times.append(t1 - t0)
        if (i + 1) % 10 == 0 or i == 0:
            print(f'  [{i+1}/{num_images}] {os.path.basename(npz_path)} '
                  f'{(t1-t0)*1000:.1f}ms shape={result.shape}')

    print(f'  平均推理: {np.mean(clean_times)*1000:.1f} ms')

    # 保存输出目录
    os.makedirs(args.output_dir, exist_ok=True)

    # 对每个 BER 级别测试
    results = {
        'num_images': num_images,
        'latent_shape': list(clean_reconstructions[0].shape),
        'ber_levels': ber_labels,
        'per_image': {},
        'summary': {},
    }

    for ber_idx, (ber, ber_label) in enumerate(zip(ber_levels, ber_labels)):
        print(f'\n[Phase 2] BER = {ber_label} ...')

        psnr_list = []
        ssim_list = []
        actual_ber_list = []

        for i, (npz_path, clean_img) in enumerate(
                zip(npz_files, clean_reconstructions)):

            latent = load_latent(npz_path)

            if ber == 0:
                # 无误码，直接用干净重建
                psnr = float('inf')
                ssim = 1.0
                actual_ber = 0.0
            else:
                # 注入比特误码
                raw_bytes = bytearray(latent.tobytes())
                num_flips = inject_bit_errors(raw_bytes, ber)
                actual_ber = num_flips / (len(raw_bytes) * 8)

                # 反序列化
                corrupted = np.frombuffer(bytes(raw_bytes),
                                          dtype=np.float32).reshape(latent.shape)

                # TVM 推理
                t0 = time.perf_counter()
                output = fn(runtime_tensor(corrupted, dev))
                t1 = time.perf_counter()
                noisy_img = output.numpy()[0]

                # 计算 PSNR/SSIM（vs 干净重建）
                psnr = compute_psnr(clean_img, noisy_img)
                ssim = compute_ssim(clean_img, noisy_img)

            psnr_list.append(psnr)
            ssim_list.append(ssim)
            actual_ber_list.append(actual_ber)

        # 统计
        valid_psnr = [p for p in psnr_list if p != float('inf')]
        valid_ssim = [s for s in ssim_list if not np.isnan(s)]

        summary = {
            'ber_target': ber,
            'ber_actual_mean': float(np.mean(actual_ber_list)),
            'psnr_mean': float(np.mean(valid_psnr)) if valid_psnr else float('inf'),
            'psnr_std': float(np.std(valid_psnr)) if valid_psnr else 0.0,
            'psnr_min': float(np.min(valid_psnr)) if valid_psnr else float('inf'),
            'ssim_mean': float(np.mean(valid_ssim)) if valid_ssim else float('nan'),
            'ssim_std': float(np.std(valid_ssim)) if valid_ssim else 0.0,
            'ssim_min': float(np.min(valid_ssim)) if valid_ssim else float('nan'),
        }
        results['summary'][ber_label] = summary

        print(f'  PSNR: {summary["psnr_mean"]:.2f} ± {summary["psnr_std"]:.2f} dB '
              f'(min {summary["psnr_min"]:.2f})')
        print(f'  SSIM: {summary["ssim_mean"]:.4f} ± {summary["ssim_std"]:.4f} '
              f'(min {summary["ssim_min"]:.4f})')
        print(f'  实际 BER: {summary["ber_actual_mean"]:.2e}')

    # 保存结果
    output_path = args.output
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    print(f'\n[experiment] 结果保存至: {output_path}')

    # 打印汇总表
    print('\n═══ BER vs 重建质量汇总 ═══')
    print(f'{"BER":>10} | {"PSNR (dB)":>20} | {"SSIM":>20}')
    print(f'{"":>10} | {"mean ± std (min)":>20} | {"mean ± std (min)":>20}')
    print('-' * 60)
    for ber_label in ber_labels:
        s = results['summary'][ber_label]
        if s['psnr_mean'] == float('inf'):
            psnr_str = '∞ (clean)'
        else:
            psnr_str = f'{s["psnr_mean"]:.2f} ± {s["psnr_std"]:.2f} ({s["psnr_min"]:.2f})'
        if np.isnan(s['ssim_mean']):
            ssim_str = 'N/A'
        else:
            ssim_str = f'{s["ssim_mean"]:.4f} ± {s["ssim_std"]:.4f} ({s["ssim_min"]:.4f})'
        print(f'{ber_label:>10} | {psnr_str:>20} | {ssim_str:>20}')

    # 设计建议
    print('\n═══ FEC 设计建议 ═══')
    for ber_label in ber_labels:
        s = results['summary'][ber_label]
        psnr = s['psnr_mean']
        if psnr == float('inf'):
            continue
        if psnr > 34.0:
            print(f'  BER ≤ {ber_label}: PSNR {psnr:.1f} > 34 dB → '
                  f'重建质量优秀，可接受')
        elif psnr > 30.0:
            print(f'  BER ≤ {ber_label}: PSNR {psnr:.1f} > 30 dB → '
                  f'重建质量良好')
        elif psnr > 25.0:
            print(f'  BER ≤ {ber_label}: PSNR {psnr:.1f} > 25 dB → '
                  f'重建质量可接受，需轻量 FEC')
        else:
            print(f'  BER ≤ {ber_label}: PSNR {psnr:.1f} < 25 dB → '
                  f'重建质量差，需要强 FEC 或重传')

    return results


def main():
    parser = argparse.ArgumentParser(
        description='JSCC 模型 BER 容忍度实验')
    parser.add_argument('--artifact', required=True,
                        help='TVM optimized_model.so 路径')
    parser.add_argument('--input-dir', required=True,
                        help='latent .npz 文件目录')
    parser.add_argument('--num-images', type=int, default=30,
                        help='测试图片数量 (默认 30)')
    parser.add_argument('-o', '--output', default='/tmp/ber_results.json',
                        help='输出 JSON 路径')
    parser.add_argument('--output-dir', default='/tmp/ber_reconstructions',
                        help='重建图像保存目录')
    args = parser.parse_args()

    # 设置 TVM 环境变量
    os.environ['TVM_FFI_DISABLE_TORCH_C_DLPACK'] = '1'

    run_experiment(args)


if __name__ == '__main__':
    main()
