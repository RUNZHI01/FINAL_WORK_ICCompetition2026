"""default_config.py — 从 finalWork 客户端 pyc 逆向重构

原文件仅以 .pyc 形式存在于 finalWork/客户端/jscc-test/jscc/__pycache__/。
此处根据代码中的 import 和使用方式重构。
"""

from enum import Enum


class ModelTypes(str, Enum):
    BASE = 'base'


class ModelModes(str, Enum):
    TRAINING = 'training'
    EVALUATION = 'evaluation'


class Datasets(str, Enum):
    OPENIMAGES = 'openimages'
    EVALUATION = 'evaluation'


class DatasetPaths:
    pass


class Directories:
    pass


class Args:
    """默认参数，会被 checkpoint 中保存的 args 覆盖"""
    image_dims = (3, 256, 256)
    latent_channels = 32
    e_n_blocks = 5
    g_n_blocks = 5
    batch_size = 1
    gpu = 0
    snr = 10
    config_str = '6_6_6_6_6_6_6'
    model_type = 'base'
    model_mode = 'evaluation'
    log_interval = 100
    test_num = 300
    image_dir = ''
    learning_rate = 1e-4
    multi_gpu = False
    use_discriminator = True
    name = None
