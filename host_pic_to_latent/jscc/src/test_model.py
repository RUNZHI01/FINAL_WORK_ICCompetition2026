import time, os
import itertools
import lpips
from collections import defaultdict, namedtuple
from functools import partial
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.nn.parallel import gather, parallel_apply, replicate
import glob
import torchvision
from natsort import natsorted
from multiprocessing import Pool, get_context
import hashlib
import logging
import numpy as np
from tqdm.auto import tqdm
import sys
import traceback
from typing import List, Tuple
# Custom modules
from src import utils
from src.network import encoder, generator, discriminator, super_generator, sub_generator
from default_config import ModelModes, ModelTypes, Directories, Args
import channel_configs
from src.network.super_modules import SuperConvTranspose2d, SuperConv2d, SuperSeparableConv2d

Intermediates = namedtuple("Intermediates",
                           ["input_image",  # [0, 1] (after scaling from [0, 255])
                            "reconstruction",  # [0, 1]
                            "latents_quantized",  # Latents post-quantization.
                            "n_bpp",  # Differential entropy estimate.
                            "q_bpp"])  # Shannon entropy estimate.

Disc_out = namedtuple("disc_out",
                      ["D_real", "D_gen", "D_real_logits", "D_gen_logits"])


def calculate_scale_and_zero_point(tensor, qmin=0, qmax=255):
    min_val = torch.min(tensor).item()
    max_val = torch.max(tensor).item()
    scale = (max_val - min_val) / (qmax - qmin)
    zero_point = qmin - np.round(min_val / scale)
    return torch.tensor(scale), torch.tensor(zero_point)


class TestModel(nn.Module):
    def __init__(self, args, logger, storage_train=defaultdict(list), storage_test=defaultdict(list),
                 model_mode=ModelModes.TRAINING, model_type=ModelTypes.BASE):
        super(TestModel, self).__init__()

        self.project_root = os.path.normpath("/home/user/Downloads/jscc-test") # build path
        self.encoder_output_dir = os.path.join(self.project_root, "encoder_outputs")

        self.args = args
        self.model_mode = model_mode
        self.model_type = model_type
        self.logger = logger
        self.log_interval = args.log_interval
        self.storage_train = storage_train
        self.storage_test = storage_test
        self.step_counter = 0

        # Configure logger to output to stderr to avoid interfering with tqdm on stdout
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(logging.INFO)
        self.logger.addHandler(handler)

        if not hasattr(ModelTypes, self.model_type.upper()):
            raise ValueError("Invalid model_type: [{}]".format(self.model_type))
        if not hasattr(ModelModes, self.model_mode.upper()):
            raise ValueError("Invalid model_mode: [{}]".format(self.model_mode))

        self.image_dims = self.args.image_dims
        self.batch_size = self.args.batch_size
        self.gpu = args.gpu

        self.Encoder = encoder.Encoder(self.image_dims, self.args.latent_channels, self.args.e_n_blocks)
        self.latent_dims = (self.args.latent_channels, 32, 32)

        self.configs = channel_configs.decode_config(args.config_str)

        self.C_generator = sub_generator.SubMobileGenerator(self.image_dims, self.configs, self.args.latent_channels,
                                                                self.args.g_n_blocks)

    def AWGNChannel(self, y, snr):
        with torch.no_grad():
            pwr = torch.mean(y ** 2, (-3, -2, -1), True) * 2
            noise_pwr = pwr * 10 ** (-snr / 10)
        noise = torch.sqrt(noise_pwr / 2) * torch.randn_like(y)
        y_noisy = y + noise
        return y_noisy

    def _save_encoder_output(self, y: torch.Tensor, filenames: List[str], output_dir: str = None) -> None:
        """增强数据保存的完整性检查"""
        try:
            os.makedirs(self.encoder_output_dir, exist_ok=True)
            assert os.access(self.encoder_output_dir, os.W_OK), f"Directory not writable: {self.encoder_output_dir}"

            for idx in range(y.size(0)):
                original_name = filenames[idx]
                try:
                    # 生成安全文件名
                    safe_name = self.validate_filename_security(original_name)
                    save_path = os.path.join(self.encoder_output_dir, safe_name)

                    # 数据完整性检查
                    tensor_slice = y[idx].detach().cpu()
                    if torch.isnan(tensor_slice).any():
                        raise ValueError("Tensor contains NaN values")

                    # 量化过程验证
                    y_cpu = tensor_slice.cpu()
                    scale, zero_point = utils.calculate_scale_and_zero_point(y_cpu)
                    if scale <= 0:
                        raise ValueError(f"Invalid scale value: {scale.item()}")

                    q_tensor = utils.quantize(tensor_slice, scale, zero_point)
                    if (q_tensor < 0).any() or (q_tensor > 255).any():
                        raise ValueError("Quantized tensor values out of [0,255] range")

                    # 保存元数据校验信息
                    checksum = hashlib.md5(q_tensor.numpy().tobytes()).hexdigest()

                    torch.save({
                        'latent': y_cpu.float(),
                        'quant': q_tensor,
                        'scale': scale,
                        'zero_point': zero_point,
                        'snr': self.args.snr,
                        'config_str': self.args.config_str,
                        'checksum': checksum,
                        'original_filename': original_name  # 保留原始文件名用于审计
                    }, save_path)

                    # 保存后验证文件完整性
                    with open(save_path, 'rb') as f:
                        saved_data = torch.load(f, map_location='cpu', weights_only=True)
                        if saved_data['checksum'] != checksum:
                            raise IOError("File checksum mismatch after saving")

                    self.logger.info(f"Successfully saved latent: {save_path}")

                except Exception as e:
                    self.logger.error(f"Failed to save {original_name}: {str(e)}\n{traceback.format_exc()}")
                    continue

        except Exception as e:
            self.logger.critical(f"Critical error in save_encoder_output: {str(e)}")
            raise

    def validate_filename_security(self, filename: str) -> str:
        """生成安全哈希文件名并验证路径安全性"""
        # 防止路径遍历攻击
        if '../' in filename or '~' in filename:
            raise ValueError(f"Invalid filename contains path traversal characters: {filename}")

        # 生成安全哈希文件名
        filename_bytes = filename.encode('utf-8')
        file_hash = hashlib.sha256(filename_bytes).hexdigest()
        safe_name = f"{file_hash}_latent.pt"

        # 验证输出路径在允许的目录内
        output_path = os.path.abspath(os.path.join(self.encoder_output_dir, safe_name))
        if not output_path.startswith(os.path.abspath(self.encoder_output_dir)):
            raise PermissionError(f"Attempted to write to unauthorized location: {output_path}")

        return safe_name

    def _load_encoder_output(self, output_dir: str, device: torch.device) -> torch.Tensor:
        """增强数据加载的完整性验证"""
        validated_dir = self._get_valid_output_dir(output_dir)
        y_list = []

        try:
            pt_files = natsorted(glob.glob(os.path.join(validated_dir, "*.pt")))
            if not pt_files:
                raise FileNotFoundError(f"No valid latent files found in {validated_dir}")

            for latent_path in pt_files:
                try:
                    # 基础文件检查
                    if not os.path.isfile(latent_path):
                        raise FileNotFoundError(f"Latent file not found: {latent_path}")
                    if os.path.getsize(latent_path) < 100:
                        raise ValueError(f"Suspiciously small file: {latent_path}")

                    # 安全加载
                    with open(latent_path, 'rb') as f:
                        data = torch.load(f, map_location="cpu", weights_only=True)

                    # 数据完整性验证
                    required_keys = {'quant', 'scale', 'zero_point', 'checksum'}
                    missing_keys = required_keys - set(data.keys())
                    if missing_keys:
                        raise KeyError(f"Missing keys {missing_keys} in {latent_path}")

                    # 校验和验证
                    current_checksum = hashlib.md5(data['quant'].numpy().tobytes()).hexdigest()
                    if current_checksum != data['checksum']:
                        raise ValueError(f"Checksum mismatch in {latent_path}")

                    # 数值范围验证
                    if data['scale'] <= 0:
                        raise ValueError(f"Invalid scale {data['scale']} in {latent_path}")
                    if not (0 <= data['zero_point'] <= 255):
                        raise ValueError(f"Invalid zero_point {data['zero_point']} in {latent_path}")

                    # 设备转移
                    q_tensor = data['quant'].to(device, non_blocking=True)
                    scale = data['scale'].to(device)
                    zero_point = data['zero_point'].to(device)

                    # 反量化验证
                    y_dequant = (q_tensor.float() - zero_point) * scale
                    if torch.isnan(y_dequant).any():
                        raise ValueError(f"NaN values detected after dequantization in {latent_path}")

                    y_list.append(y_dequant)

                except Exception as e:
                    self.logger.error(f"Skipping corrupted latent {latent_path}: {str(e)}")
                    continue

            if not y_list:
                raise RuntimeError("No valid latent tensors loaded")

            return torch.stack(y_list)

        except Exception as e:
            self.logger.critical(f"Critical error in load_encoder_output: {str(e)}")
            raise

    def _get_valid_output_dir(self, output_dir):
        candidates = [
            self.encoder_output_dir,
            os.path.join(self.project_root, "encoder_outputs/encoder_outputs")
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
        raise FileNotFoundError("No valid encoder output directory found")

    def _validate_latent_file(self, path):
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Latent file {path} not found")
        if os.path.getsize(path) < 100:
            raise ValueError(f"Corrupted file: {path} size abnormal")

    def _save_reconstruction(self, reconstruction, base_name, output_dir):
        save_path = os.path.join(output_dir, "reconstructions", f"{base_name}.png")
        torchvision.utils.save_image(
            reconstruction.unsqueeze(0).detach().cpu(),
            save_path,
            format='PNG'
        )

    def _get_valid_filenames(self, output_dir):
        validated_dir = self._get_valid_output_dir(output_dir)
        pt_files = natsorted(glob.glob(os.path.join(validated_dir, "*.pt")))
        filenames = []
        for f in pt_files:
            try:
                base = os.path.basename(f)
                name_part = base.split('_latent')[0]
                filenames.append(name_part)
            except Exception as e:
                self.logger.error(f"Filename parsing failed: {f} - {str(e)}")
        if not filenames:
            raise ValueError(f"No valid filenames generated from {validated_dir}")
        return filenames

    def _process_single_file(self, latent_path: str, original_filename: str, snr: float, output_dir: str) -> Tuple[bool, torch.Tensor]:
        """增强单文件处理异常处理"""
        try:
            t_start = time.time()
            self.logger.info(f"Processing {latent_path}")

            # 输入验证
            if not os.path.exists(latent_path):
                raise FileNotFoundError(f"Latent file not found: {latent_path}")

            # 安全加载
            with open(latent_path, 'rb') as f:
                data = torch.load(f, map_location="cpu", weights_only=True)

            # 设备转移
            device = next(self.C_generator.parameters()).device
            q_tensor = data['quant'].to(device)
            scale = data['scale'].to(device)
            zero_point = data['zero_point'].to(device)

            # 反量化验证
            y_dequant = (q_tensor.float() - zero_point) * scale
            if torch.isnan(y_dequant).any():
                raise ValueError("NaN values in dequantized tensor")

            channel_mode = os.environ.get("JSCC_CHANNEL_MODE", "sim-awgn").strip().lower()
            if channel_mode in ("real-usrp", "none"):
                latent_tensor = data.get('latent')
                if latent_tensor is not None:
                    y_input = latent_tensor.to(device).float()
                    y_noisy = y_input if y_input.ndim == 4 else y_input.unsqueeze(0)
                else:
                    y_noisy = y_dequant.unsqueeze(0)
            else:
                # 添加仿真噪声；真实 USRP 模式下不要再次注入 AWGN
                y_noisy = self.AWGNChannel(y_dequant.unsqueeze(0), snr)

            # 生成过程
            with torch.inference_mode():
                recon = self.C_generator(y_noisy).squeeze(0)


            # 安全保存
            safe_name = self.validate_filename_security(original_filename)
            self._save_reconstruction(recon, f"{safe_name}_recon", output_dir)

            if 'f' in locals():
                f.close()  # 显式关闭句柄

            # 资源清理
            del data, q_tensor, y_dequant, y_noisy

            # 安全清理 CUDA 缓存
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

            t_end = time.time()
            self.logger.info(f"Successfully processed {latent_path} in {t_end - t_start:.2f}s")
            return True, recon

        except Exception as e:
            self.logger.error(f"Failed to process {latent_path}: {str(e)}\n{traceback.format_exc()}")
            return False, None

    def forward(self, img: torch.Tensor, snr: float, filenames: List[str] = None,
                output_dir: str = None, writeout: bool = True, save_latent: bool = False) -> Tuple[torch.Tensor, tuple]:
        """增强前向传播的异常处理并添加动态进度条"""
        try:
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

            if self.model_mode == ModelModes.EVALUATION and not self.training:
                if save_latent:
                    # 输入验证
                    if img.min() < 0 or img.max() > 1:
                        raise ValueError("Input image values out of [0,1] range")

                    # 编码过程
                    with torch.no_grad():
                        x = utils.pad_factor(img, img.size()[2:], 2 ** self.Encoder.n_downsampling_layers)
                        y = self.Encoder(x)

                    # 保存验证
                    if output_dir and filenames:
                        self._save_encoder_output(y, filenames, output_dir)

                    return None, (time.time() - t1, 0.0)

                else:
                    # 文件列表验证
                    if not filenames and output_dir:
                        filenames = self._get_valid_filenames(output_dir)
                        self.logger.info(f"Auto-generated {len(filenames)} filenames")

                    pt_files = natsorted(glob.glob(os.path.join(
                        self._get_valid_output_dir(output_dir), "*.pt"
                    )))

                    if len(pt_files) != len(filenames):
                        raise ValueError(f"Mismatch: {len(pt_files)} latent files vs {len(filenames)} filenames")

                    # 使用多进程池和动态进度条
                    with get_context("spawn").Pool(processes=2) as pool:
                        results = [pool.apply_async(self._process_single_file_wrapper, (pt_file, filename, snr, output_dir))
                                   for pt_file, filename in zip(pt_files, filenames)]

                        # 显示动态进度条
                        pbar = tqdm(total=len(pt_files), desc="Processing files", file=sys.stdout)
                        while len(results) > 0:
                            done = [r for r in results if r.ready()]
                            for r in done:
                                success, recon = r.get()
                                if success:
                                    pbar.update(1)
                                results.remove(r)
                            time.sleep(0.1)  # 降低主进程对于子进程状态轮询的频率（用于更新进度条），降低cpu的占用，对于后台的子进程（实际推理进程）无影响
                        pbar.close()

                    # 收集成功的重构
                    processed_recons = [r.get()[1] for r in results if r.get()[0]]
                    success_count = len(processed_recons)

                    if processed_recons:
                        recon = torch.cat(processed_recons, dim=0)
                        return recon, (success_count, len(pt_files))
                    return None, (0, len(pt_files))

        except Exception as e:
            self.logger.critical(f"Forward pass failed: {str(e)}\n{traceback.format_exc()}")
            raise RuntimeError("Critical error during forward pass") from e

    def _process_single_file_wrapper(self, *args):
        """用于多进程的异常处理包装器"""
        try:
            return self._process_single_file(*args)
        except Exception as e:
            self.logger.error(f"Child process error: {str(e)}")
            return False, None