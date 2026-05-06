#!/usr/bin/env python3
"""
SM2 + ML-DSA 双身份密钥对生成工具

生成服务端身份密钥对，用于 ML-KEM 认证握手。
输出到指定目录：
  server_sm2_identity.key / .pub   (SM2: sk 32B, pk 65B)
  server_mldsa_identity.key / .pub (ML-DSA-65: sk 4032B, pk 1952B)
  .gitignore 排除 *.key

用法:
  # 生成到默认目录 keys/
  python scripts/gen_identity_keys.py

  # 指定输出目录
  python scripts/gen_identity_keys.py --dir /path/to/keys

  # 仅生成 ML-DSA（SM2 需要 Tongsuo）
  python scripts/gen_identity_keys.py --mldsa-only

  # 仅生成 SM2
  python scripts/gen_identity_keys.py --sm2-only
"""

import argparse
import os
import stat
import sys

# 允许从项目根目录直接运行
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def write_key(path: str, data: bytes, private: bool = True) -> None:
    """写入密钥文件，私钥设 600 权限"""
    with open(path, 'wb') as f:
        f.write(data)
    if private:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)


def write_gitignore(directory: str) -> None:
    """在目录下创建 .gitignore 排除私钥文件"""
    gitignore_path = os.path.join(directory, '.gitignore')
    content = '# 私钥文件，禁止提交\n*.key\n'
    if os.path.exists(gitignore_path):
        with open(gitignore_path, 'r') as f:
            if '*.key' in f.read():
                return
    with open(gitignore_path, 'w') as f:
        f.write(content)


def gen_sm2(directory: str) -> None:
    """生成 SM2 身份密钥对"""
    from mlkem_link.auth import get_sm2_backend
    backend = get_sm2_backend()

    pk, sk = backend.keygen()

    sk_path = os.path.join(directory, 'server_sm2_identity.key')
    pk_path = os.path.join(directory, 'server_sm2_identity.pub')
    write_key(sk_path, sk, private=True)
    write_key(pk_path, pk, private=False)
    print(f'SM2 密钥对已生成:')
    print(f'  私钥: {sk_path} ({len(sk)} bytes)')
    print(f'  公钥: {pk_path} ({len(pk)} bytes)')


def gen_mldsa(directory: str) -> None:
    """生成 ML-DSA-65 身份密钥对"""
    from mlkem_link.auth import get_mldsa_backend
    backend = get_mldsa_backend()

    pk, sk = backend.keygen()

    sk_path = os.path.join(directory, 'server_mldsa_identity.key')
    pk_path = os.path.join(directory, 'server_mldsa_identity.pub')
    write_key(sk_path, sk, private=True)
    write_key(pk_path, pk, private=False)
    print(f'ML-DSA 密钥对已生成:')
    print(f'  私钥: {sk_path} ({len(sk)} bytes)')
    print(f'  公钥: {pk_path} ({len(pk)} bytes)')


def main():
    parser = argparse.ArgumentParser(
        description='生成 SM2 + ML-DSA 双身份密钥对',
    )
    parser.add_argument(
        '--dir', default='keys',
        help='输出目录 (默认: keys/)',
    )
    parser.add_argument(
        '--sm2-only', action='store_true',
        help='仅生成 SM2 密钥对',
    )
    parser.add_argument(
        '--mldsa-only', action='store_true',
        help='仅生成 ML-DSA 密钥对',
    )
    args = parser.parse_args()

    os.makedirs(args.dir, exist_ok=True)

    do_sm2 = not args.mldsa_only
    do_mldsa = not args.sm2_only

    if do_sm2:
        try:
            gen_sm2(args.dir)
        except (ImportError, NotImplementedError) as e:
            print(f'SM2 密钥生成跳过: {e}', file=sys.stderr)
            print('  提示: SM2 需要 Tongsuo C bridge 支持', file=sys.stderr)

    if do_mldsa:
        try:
            gen_mldsa(args.dir)
        except (ImportError, RuntimeError, SystemExit) as e:
            print(f'ML-DSA 密钥生成跳过: {e}', file=sys.stderr)
            print('  提示: ML-DSA 需要 liboqs 编译时启用 ML-DSA', file=sys.stderr)

    write_gitignore(args.dir)
    print(f'\n.gitignore 已更新: {os.path.join(args.dir, ".gitignore")}')


if __name__ == '__main__':
    main()
