"""channel_configs.py — 从 finalWork 客户端 pyc 逆向重构

原文件仅以 .pyc 形式存在于 finalWork/客户端/jscc-test/jscc/__pycache__/。
config_str 格式: '6_6_6_6_6_6_6'，7 个数字对应子网络各层通道倍率。
decode_config 将其映射为 SubMobileGenerator 所需的 channels 字典。
"""


def decode_config(config_str: str) -> dict:
    """将 config_str (如 '6_6_6_6_6_6_6') 解析为子生成器配置字典"""
    parts = list(map(int, config_str.split('_')))
    return {
        'channels': parts[:6],
        'n_blocks': len(parts),
    }
