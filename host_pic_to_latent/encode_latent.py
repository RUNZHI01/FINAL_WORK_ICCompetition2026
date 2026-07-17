#!/usr/bin/env python3
"""
encode_latent.py — 上位机图片→张量(latent)编码工具

从 finalWork/客户端/jscc-test/ 提取并简化的独立编码脚本。
功能：加载 JSCC 编码器 checkpoint，将图片目录中的 .jpg/.png 编码为
量化 latent .pt 文件，供后续 USRP 无线传输或板端解码使用。

用法:
    python encode_latent.py \
        --ckpt_dir ../finalWork/客户端/jscc-test \
        --image_dir ../airfield \
        --output_dir ./encoder_outputs \
        --snr 10 \
        --config_str 6_6_6_6_6_6_6 \
        --test_num 10
"""

import argparse
import glob
import hashlib
import json
import os
import sys
import time
import traceback
from pathlib import Path

import numpy as np
import torch
from natsort import natsorted
from tqdm.auto import tqdm

# ── 将 jscc 包目录加入 sys.path ──
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def resolve_jscc_root():
    return os.path.abspath(
        os.environ.get('HOST_PIC_TO_LATENT_JSCC_ROOT')
        or os.path.join(SCRIPT_DIR, 'jscc')
    )


JSCC_ROOT = resolve_jscc_root()
sys.path.insert(0, JSCC_ROOT)

from src.network import encoder


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as infile:
        for chunk in iter(lambda: infile.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest_record(source_path, source_root, latent_path):
    source = Path(source_path).resolve()
    root = Path(source_root).resolve()
    latent = Path(latent_path).resolve()
    return {
        'source_image': str(source),
        'source_image_rel': str(source.relative_to(root)),
        'source_image_sha256': file_sha256(source),
        'source_image_size': source.stat().st_size,
        'original_filename': source.stem,
        'latent': str(latent),
        'latent_rel': latent.name,
        'latent_sha256': file_sha256(latent),
        'latent_size': latent.stat().st_size,
    }


def resolve_checkpoint_path(ckpt_dir, config_str):
    ckpt_name = '1snr_lpips_{}_openimages_gan.pt'.format(config_str)
    script_dir = Path(SCRIPT_DIR)
    candidates = [
        Path(ckpt_dir) / 'origin' / ckpt_name,
        script_dir.parent.parent / 'jscc-test' / 'origin' / ckpt_name,
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return str(candidates[0])


def calculate_scale_and_zero_point(tensor, qmin=0, qmax=255):
    min_val = torch.min(tensor).item()
    max_val = torch.max(tensor).item()
    scale = (max_val - min_val) / (qmax - qmin)
    zero_point = qmin - np.round(min_val / scale)
    return torch.tensor(scale), torch.tensor(zero_point)


def quantize(tensor, scale, zero_point, qmin=0, qmax=255):
    q_tensor = torch.round(tensor / scale + zero_point)
    return torch.clamp(q_tensor, qmin, qmax).to(torch.uint8)


def pad_factor(input_image, spatial_dims, factor):
    """Pad input_image (N,C,H,W) such that H and W are divisible by factor."""
    if isinstance(factor, int):
        factor_H = factor
        factor_W = factor_H
    else:
        factor_H, factor_W = factor
    H, W = spatial_dims[0], spatial_dims[1]
    pad_H = (factor_H - (H % factor_H)) % factor_H
    pad_W = (factor_W - (W % factor_W)) % factor_W
    return torch.nn.functional.pad(input_image, pad=(0, pad_W, 0, pad_H), mode='reflect')


def load_encoder(ckpt_dir, config_str, device='cpu'):
    """加载编码器权重，返回 Encoder 模型和 args"""
    ckpt_path = resolve_checkpoint_path(ckpt_dir, config_str)
    if not os.path.isfile(ckpt_path):
        raise FileNotFoundError(
            f"Checkpoint not found: {ckpt_path}\n"
            f"Please copy it from finalWork/客户端/jscc-test/origin/"
        )

    checkpoint = torch.load(ckpt_path, map_location=device, weights_only=False)
    loaded_args_d = checkpoint['args']

    class Struct:
        def __init__(self, **entries):
            self.__dict__.update(entries)

    args = Struct(**loaded_args_d)
    args.config_str = config_str
    args.snr = args.snr if hasattr(args, 'snr') else 10

    enc = encoder.Encoder(
        args.image_dims,
        args.latent_channels,
        args.e_n_blocks,
    )

    state_dict = checkpoint['model_state_dict']
    encoder_state = {}
    for k, v in state_dict.items():
        # 去掉 'Encoder.' 前缀（原始模型中 Encoder 是子模块）
        if k.startswith('Encoder.'):
            encoder_state[k[len('Encoder.'):]] = v
    enc.load_state_dict(encoder_state, strict=True)
    enc = enc.to(device)
    enc.eval()

    return enc, args


def encode_single_image(enc, img_tensor, snr, original_filename):
    """编码单张图片，返回量化后的 dict"""
    x = pad_factor(img_tensor.unsqueeze(0), img_tensor.shape[1:], 2 ** enc.n_downsampling_layers)
    with torch.no_grad():
        y = enc(x)

    y_cpu = y[0].detach().cpu()
    scale, zero_point = calculate_scale_and_zero_point(y_cpu)
    q_tensor = quantize(y_cpu, scale, zero_point)

    checksum = hashlib.md5(q_tensor.numpy().tobytes()).hexdigest()

    return {
        'quant': q_tensor,
        'scale': scale,
        'zero_point': zero_point,
        'snr': snr,
        'config_str': getattr(enc, '_config_str', ''),
        'checksum': checksum,
        'original_filename': original_filename,
    }


def main():
    parser = argparse.ArgumentParser(
        description='将图片编码为 JSCC latent 张量文件 (.pt)',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument('--ckpt_dir', type=str,
                        default=os.path.join(SCRIPT_DIR, 'checkpoint'),
                        help='包含 origin/ 和 export/ 的 checkpoint 目录')
    parser.add_argument('--image_dir', type=str,
                        default=os.path.join(SCRIPT_DIR, 'airfield'),
                        help='输入图片目录（.jpg/.png）')
    parser.add_argument('--output_dir', type=str,
                        default=os.path.join(SCRIPT_DIR, 'encoder_outputs'),
                        help='输出 latent .pt 文件目录')
    parser.add_argument('--snr', type=int, default=10,
                        help='AWGN 信噪比 (dB)')
    parser.add_argument('--config_str', type=str, default='6_6_6_6_6_6_6',
                        help='子网络配置字符串')
    parser.add_argument('--test_num', type=int, default=-1,
                        help='编码图片数量（-1 = 全部）')
    parser.add_argument('--device', type=str, default='cpu',
                        help='计算设备 (cpu/cuda)')
    parser.add_argument('--progress_jsonl', action='store_true',
                        help='逐张输出 JSONL 进度，供主 demo 轮询阶段条使用')
    parser.add_argument('--manifest-name', type=str,
                        default='host_image_to_latent_manifest.json',
                        help='写入 output_dir 的来源映射清单文件名')
    args = parser.parse_args()

    ckpt_dir = os.path.normpath(args.ckpt_dir)
    image_dir = os.path.normpath(args.image_dir)
    output_dir = os.path.normpath(args.output_dir)
    os.makedirs(output_dir, exist_ok=True)

    img_files = natsorted(
        glob.glob(os.path.join(image_dir, '*.jpg')) +
        glob.glob(os.path.join(image_dir, '*.png'))
    )
    assert len(img_files) > 0, f'No .jpg/.png found in {image_dir}'
    if args.test_num > 0:
        img_files = img_files[:args.test_num]

    print(f'Found {len(img_files)} images in {image_dir}')
    print(f'Output dir: {output_dir}')
    print(f'Config: {args.config_str}, SNR: {args.snr}dB, Device: {args.device}')

    print('Loading encoder...')
    enc, loaded_args = load_encoder(ckpt_dir, args.config_str, args.device)
    print(f'Encoder loaded. image_dims={loaded_args.image_dims}, '
          f'latent_channels={loaded_args.latent_channels}, '
          f'e_n_blocks={loaded_args.e_n_blocks}')

    from PIL import Image
    from torchvision import transforms

    to_tensor = transforms.ToTensor()
    t_start = time.time()
    success_count = 0
    manifest_records = []

    for img_path in tqdm(img_files, desc='Encoding'):
        try:
            filename = os.path.splitext(os.path.basename(img_path))[0]
            img = Image.open(img_path).convert('RGB')
            img_tensor = to_tensor(img)

            if img_tensor.min() < 0 or img_tensor.max() > 1:
                print(f'Warning: {img_path} pixel range out of [0,1], skipping')
                continue

            latent_dict = encode_single_image(enc, img_tensor, args.snr, filename)
            latent_dict['config_str'] = args.config_str

            safe_name = f"{hashlib.sha256(filename.encode()).hexdigest()}_latent.pt"
            save_path = os.path.join(output_dir, safe_name)
            torch.save(latent_dict, save_path)
            manifest_records.append(build_manifest_record(img_path, image_dir, save_path))

            success_count += 1
            if args.progress_jsonl:
                print(json.dumps({
                    'event': 'encoded',
                    'completed': success_count,
                    'total': len(img_files),
                    'source': img_path,
                    'output': save_path,
                    'original_filename': filename,
                }, ensure_ascii=False), flush=True)
        except Exception as e:
            print(f'Error encoding {img_path}: {e}')
            if args.progress_jsonl:
                print(json.dumps({
                    'event': 'error',
                    'completed': success_count,
                    'total': len(img_files),
                    'source': img_path,
                    'error': str(e),
                }, ensure_ascii=False), flush=True)
            traceback.print_exc()

    elapsed = time.time() - t_start
    print(f'\nDone. {success_count}/{len(img_files)} images encoded in {elapsed:.1f}s '
          f'({success_count/max(elapsed,0.001):.1f} img/s)')
    print(f'Output: {output_dir}')
    manifest_path = Path(output_dir) / args.manifest_name
    manifest = {
        'schema': 'host_image_to_latent_manifest/v1',
        'generated_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
        'source_dir': str(Path(image_dir).resolve()),
        'output_dir': str(Path(output_dir).resolve()),
        'count': len(manifest_records),
        'snr': args.snr,
        'config_str': args.config_str,
        'device': args.device,
        'jscc_root': JSCC_ROOT,
        'checkpoint_dir': str(Path(ckpt_dir).resolve()),
        'records': manifest_records,
        'command': sys.argv,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )
    print(f'Manifest: {manifest_path}')


if __name__ == '__main__':
    main()
