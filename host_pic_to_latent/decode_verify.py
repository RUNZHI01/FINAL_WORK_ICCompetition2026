#!/usr/bin/env python3
"""
decode_verify.py — 张量(latent)还原为图片并计算PSNR

从 encode_latent.py 输出的 .pt 文件反量化后经解码器还原图片，
与原图对比计算 PSNR/SSIM，验证编解码管线的正确性。

用法:
    python decode_verify.py \
        --ckpt_dir ./checkpoint \
        --latent_dir ./encoder_outputs \
        --image_dir ./airfield \
        --output_dir ./reconstructions \
        --config_str 6_6_6_6_6_6_6 \
        --snr 10 \
        --test_num 3
"""

import argparse
import glob
import os
import sys
import time
import traceback

import numpy as np
import torch
from natsort import natsorted
from PIL import Image
from tqdm.auto import tqdm
from torchvision import transforms

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(SCRIPT_DIR, 'jscc'))

import channel_configs
from src.network import sub_generator


class Struct:
    def __init__(self, **entries):
        self.__dict__.update(entries)


def load_decoder(ckpt_dir, config_str, device='cpu'):
    """加载解码器 (SubMobileGenerator) 权重"""
    ckpt_path = os.path.join(ckpt_dir, 'origin',
                             f'1snr_lpips_{config_str}_openimages_gan.pt')
    G_path = os.path.join(ckpt_dir, 'export', 'compressed_gan.pt')

    if not os.path.isfile(ckpt_path):
        raise FileNotFoundError(f"Checkpoint not found: {ckpt_path}")
    if not os.path.isfile(G_path):
        raise FileNotFoundError(f"Generator weights not found: {G_path}")

    checkpoint = torch.load(ckpt_path, map_location=device, weights_only=False)
    G_state = torch.load(G_path, map_location=device, weights_only=False)

    loaded_args_d = checkpoint['args']
    args = Struct(**loaded_args_d)
    args.config_str = config_str

    config = channel_configs.decode_config(config_str)
    gen = sub_generator.SubMobileGenerator(
        args.image_dims, config,
        args.latent_channels, args.g_n_blocks,
    )

    # 过滤掉 thop 统计元数据（total_ops, total_params）
    G_clean = {k: v for k, v in G_state.items()
               if not k.endswith('.total_ops') and not k.endswith('.total_params')}
    gen.load_state_dict(G_clean, strict=False)
    gen = gen.to(device)
    gen.eval()

    return gen, args


def psnr(img1, img2, max_val=1.0):
    mse = np.mean((img1 - img2) ** 2)
    if mse == 0:
        return float('inf')
    return 20 * np.log10(max_val) - 10 * np.log10(mse)


def ssim(img1, img2):
    C1, C2 = 0.01 ** 2, 0.03 ** 2
    mu1, mu2 = img1.mean(), img2.mean()
    sigma1, sigma2 = img1.var(), img2.var()
    sigma12 = ((img1 - mu1) * (img2 - mu2)).mean()
    num = (2 * mu1 * mu2 + C1) * (2 * sigma12 + C2)
    den = (mu1 ** 2 + mu2 ** 2 + C1) * (sigma1 + sigma2 + C2)
    return num / den


def main():
    parser = argparse.ArgumentParser(
        description='将 latent .pt 还原为图片并验证 PSNR',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument('--ckpt_dir', type=str,
                        default=os.path.join(SCRIPT_DIR, 'checkpoint'))
    parser.add_argument('--latent_dir', type=str,
                        default=os.path.join(SCRIPT_DIR, 'encoder_outputs'))
    parser.add_argument('--image_dir', type=str,
                        default=os.path.join(SCRIPT_DIR, 'airfield'))
    parser.add_argument('--output_dir', type=str,
                        default=os.path.join(SCRIPT_DIR, 'reconstructions'))
    parser.add_argument('--snr', type=int, default=10, help='AWGN SNR (dB)')
    parser.add_argument('--config_str', type=str, default='6_6_6_6_6_6_6')
    parser.add_argument('--test_num', type=int, default=-1)
    parser.add_argument('--device', type=str, default='cpu')
    parser.add_argument('--no_noise', action='store_true',
                        help='不加 AWGN 噪声（纯编解码验证）')
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    print('Loading decoder...')
    gen, loaded_args = load_decoder(args.ckpt_dir, args.config_str, args.device)
    print(f'Decoder loaded. image_dims={loaded_args.image_dims}')

    pt_files = natsorted(glob.glob(os.path.join(args.latent_dir, '*.pt')))
    if args.test_num > 0:
        pt_files = pt_files[:args.test_num]
    assert len(pt_files) > 0, f'No .pt files in {args.latent_dir}'

    to_tensor = transforms.ToTensor()
    results = []

    print(f'Decoding {len(pt_files)} latent files...')
    t_start = time.time()

    for pt_path in tqdm(pt_files, desc='Decoding'):
        try:
            data = torch.load(pt_path, map_location=args.device, weights_only=True)
            q = data['quant'].to(args.device)
            scale = data['scale'].to(args.device)
            zp = data['zero_point'].to(args.device)

            y = (q.float() - zp) * scale

            if not args.no_noise:
                with torch.no_grad():
                    pwr = torch.mean(y ** 2, (-3, -2, -1), True) * 2
                    noise_pwr = pwr * 10 ** (-args.snr / 10)
                noise = torch.sqrt(noise_pwr / 2) * torch.randn_like(y)
                y = y + noise

            with torch.no_grad():
                recon = gen(y.unsqueeze(0)).squeeze(0)
            recon = recon.clamp(0, 1)

            safe_name = os.path.splitext(os.path.basename(pt_path))[0]
            save_path = os.path.join(args.output_dir, f'{safe_name}_recon.png')
            torchvision = __import__('torchvision')
            torchvision.utils.save_image(recon, save_path)

            orig_name = data.get('original_filename', '')
            if orig_name:
                for ext in ('.jpg', '.png'):
                    orig_path = os.path.join(args.image_dir, orig_name + ext)
                    if os.path.isfile(orig_path):
                        orig_img = np.array(Image.open(orig_path).convert('RGB')) / 255.0
                        recon_img = np.array(
                            transforms.ToPILImage()(recon.cpu()).convert('RGB')
                        ) / 255.0
                        h = min(orig_img.shape[0], recon_img.shape[1])
                        w = min(orig_img.shape[1], recon_img.shape[1])
                        p = psnr(orig_img[:h, :w], recon_img[:h, :w])
                        s = ssim(orig_img[:h, :w], recon_img[:h, :w])
                        results.append({'file': orig_name, 'psnr': p, 'ssim': s})
                        break

        except Exception as e:
            print(f'Error decoding {pt_path}: {e}')
            traceback.print_exc()

    elapsed = time.time() - t_start

    if results:
        psnrs = [r['psnr'] for r in results]
        ssims = [r['ssim'] for r in results]
        print(f'\n{"="*50}')
        print(f'Results ({len(results)} images, {"no noise" if args.no_noise else f"SNR={args.snr}dB"}):')
        print(f'  PSNR: {np.mean(psnrs):.2f} dB (avg), {np.min(psnrs):.2f}~{np.max(psnrs):.2f}')
        print(f'  SSIM: {np.mean(ssims):.4f} (avg), {np.min(ssims):.4f}~{np.max(ssims):.4f}')
        print(f'  Time: {elapsed:.1f}s ({len(pt_files)/max(elapsed,0.001):.1f} img/s)')
        print(f'  Output: {args.output_dir}')
        print(f'{"="*50}')


if __name__ == '__main__':
    main()
