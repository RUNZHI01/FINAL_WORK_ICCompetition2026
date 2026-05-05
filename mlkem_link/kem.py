"""
ML-KEM 密钥封装模块

支持的参数集：
- ML-KEM-768（默认，NIST FIPS 203）
- ML-KEM-512（止损备选）

后端（按优先级）：
- TongsuoBackend：铜锁（生产级，ML-KEM + SM4 + AES 内置）
- LibOQSBackend：liboqs（Open Quantum Safe，备选）
"""

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class KEMKeyPair:
    """ML-KEM 密钥对"""
    public_key: bytes
    secret_key: bytes


@dataclass
class KEMEncapsulation:
    """ML-KEM 封装结果"""
    ciphertext: bytes
    shared_secret: bytes


class KEMBackend(ABC):
    """KEM 后端抽象接口"""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def param_set(self) -> str: ...

    @property
    @abstractmethod
    def pk_bytes(self) -> int: ...

    @property
    @abstractmethod
    def sk_bytes(self) -> int: ...

    @property
    @abstractmethod
    def ct_bytes(self) -> int: ...

    @property
    @abstractmethod
    def ss_bytes(self) -> int: ...

    @abstractmethod
    def keygen(self) -> KEMKeyPair: ...

    @abstractmethod
    def encaps(self, public_key: bytes) -> KEMEncapsulation: ...

    @abstractmethod
    def decaps(self, secret_key: bytes, ciphertext: bytes, public_key: bytes = b"") -> bytes: ...


# ── 参数集尺寸表 ──

_KEM_SIZES = {
    "512":  {"pk": 800,  "sk": 1632, "ct": 768,  "ss": 32},
    "768":  {"pk": 1184, "sk": 2400, "ct": 1088, "ss": 32},
    "1024": {"pk": 1568, "sk": 3168, "ct": 1568, "ss": 32},
}

_ALG_NAMES = {
    "512":  "ML-KEM-512",
    "768":  "ML-KEM-768",
    "1024": "ML-KEM-1024",
}


def _detect_oqs_install_path() -> str:
    """解析可用的 liboqs 安装目录。

    注意：Path('') 会被解释为当前工作目录，不能直接拿来判断；
    否则在未设置 OQS_INSTALL_PATH 时会错误地把 repo 根目录当成有效安装目录，
    导致 liboqs-python 回退到 ~/. _oqs 的自动安装逻辑。
    """
    env_path = os.path.expanduser(str(os.environ.get("OQS_INSTALL_PATH", "") or "").strip())
    if env_path and Path(env_path).is_dir():
        return env_path

    auto_candidates = [
        Path(__file__).resolve().parents[1] / "liboqs-dist",
        Path(__file__).resolve().parents[1] / "liboqs" / "liboqs-dist",
    ]
    for candidate in auto_candidates:
        if (candidate / "lib").is_dir() or (candidate / "lib64").is_dir():
            return str(candidate)
    return ""


# ── Tongsuo 后端（通过 C 桥接库） ──

def _find_tongsuo_bridge() -> str:
    """自动搜索 libtongsuo_kem_bridge.so 路径"""
    candidates = [
        # Docker 构建产物
        Path(__file__).resolve().parents[1] / "tongsuo-dist" / "lib64" / "libtongsuo_kem_bridge.so",
        # 板侧安装
        Path("/usr/local/tongsuo/lib64/libtongsuo_kem_bridge.so"),
        Path("/usr/local/tongsuo/lib/libtongsuo_kem_bridge.so"),
    ]
    env_path = os.environ.get("TONGSUO_KEM_BRIDGE")
    if env_path:
        candidates.insert(0, Path(env_path))

    for p in candidates:
        if p.exists():
            return str(p)
    raise ImportError(
        "找不到 libtongsuo_kem_bridge.so。\n"
        "请先编译 Tongsuo + 桥接库: ./docker/docker-build.sh\n"
        "或设置环境变量: export TONGSUO_KEM_BRIDGE=/path/to/libtongsuo_kem_bridge.so"
    )


class TongsuoBackend(KEMBackend):
    """基于铜锁（Tongsuo）的 ML-KEM 后端

    通过 C 桥接库（libtongsuo_kem_bridge.so）调用 Tongsuo 的 EVP API。
    桥接库将复杂的 EVP_PKEY 生命周期封装为 3 个简单 C 函数，
    Python 端只需处理原始字节。
    """

    def __init__(self, param_set: str = "768", bridge_path: str = None):
        if param_set not in _KEM_SIZES:
            raise ValueError(f"不支持的参数集: {param_set}，可选: {list(_KEM_SIZES)}")
        self._param = param_set
        self._alg = _ALG_NAMES[param_set]
        self._sizes = _KEM_SIZES[param_set]

        # 加载桥接库
        path = bridge_path or _find_tongsuo_bridge()
        self._lib = self._load_bridge(path)

    @staticmethod
    def _load_bridge(path: str):
        """加载 C 桥接库并设置 ctypes 函数签名

        注意：Tongsuo 的 libcrypto.so.3 与系统 OpenSSL 的同名库冲突，
        无法在同一进程内通过 LD_LIBRARY_PATH 或 RTLD_GLOBAL 共存。
        在本地开发环境中，优先使用 liboqs 后端（无此冲突）；
        Tongsuo 后端仅在 Docker 或独立进程中使用。
        """
        import ctypes
        from ctypes import c_int, c_char_p, c_void_p, POINTER

        lib = ctypes.CDLL(path)

        # int tongsuo_kem_keygen(const char *alg,
        #     unsigned char *out_pk, int *out_pk_len,
        #     unsigned char *out_sk, int *out_sk_len,
        #     int pk_buf_size, int sk_buf_size)
        lib.tongsuo_kem_keygen.argtypes = [
            c_char_p, c_void_p, POINTER(c_int), c_void_p, POINTER(c_int),
            c_int, c_int,
        ]
        lib.tongsuo_kem_keygen.restype = c_int

        # int tongsuo_kem_encaps(const char *alg,
        #     const unsigned char *pk, int pk_len,
        #     unsigned char *out_ct, int *out_ct_len,
        #     unsigned char *out_ss, int *out_ss_len,
        #     int ct_buf_size, int ss_buf_size)
        lib.tongsuo_kem_encaps.argtypes = [
            c_char_p, c_char_p, c_int,
            c_void_p, POINTER(c_int), c_void_p, POINTER(c_int),
            c_int, c_int,
        ]
        lib.tongsuo_kem_encaps.restype = c_int

        # int tongsuo_kem_decaps(const char *alg,
        #     const unsigned char *sk, int sk_len,
        #     const unsigned char *pk, int pk_len,
        #     const unsigned char *ct, int ct_len,
        #     unsigned char *out_ss, int *out_ss_len,
        #     int ss_buf_size)
        lib.tongsuo_kem_decaps.argtypes = [
            c_char_p, c_char_p, c_int, c_char_p, c_int, c_char_p, c_int,
            c_void_p, POINTER(c_int), c_int,
        ]
        lib.tongsuo_kem_decaps.restype = c_int

        return lib

    @property
    def name(self) -> str:
        return f"tongsuo-{self._alg}"

    @property
    def param_set(self) -> str:
        return self._param

    @property
    def pk_bytes(self) -> int:
        return self._sizes["pk"]

    @property
    def sk_bytes(self) -> int:
        return self._sizes["sk"]

    @property
    def ct_bytes(self) -> int:
        return self._sizes["ct"]

    @property
    def ss_bytes(self) -> int:
        return self._sizes["ss"]

    def keygen(self) -> KEMKeyPair:
        import ctypes
        from ctypes import c_int, byref, create_string_buffer

        pk_buf = create_string_buffer(self.pk_bytes)
        sk_buf = create_string_buffer(self.sk_bytes)
        pk_len = c_int()
        sk_len = c_int()

        rc = self._lib.tongsuo_kem_keygen(
            self._alg.encode(), pk_buf, ctypes.byref(pk_len),
            sk_buf, ctypes.byref(sk_len),
            self.pk_bytes, self.sk_bytes,
        )
        if rc != 0:
            raise RuntimeError(f"Tongsuo ML-KEM keygen 失败: rc={rc}")

        return KEMKeyPair(
            public_key=pk_buf.raw[:pk_len.value],
            secret_key=sk_buf.raw[:sk_len.value],
        )

    def encaps(self, public_key: bytes) -> KEMEncapsulation:
        import ctypes
        from ctypes import c_int, byref, create_string_buffer

        ct_buf = create_string_buffer(self.ct_bytes)
        ss_buf = create_string_buffer(self.ss_bytes)
        ct_len = c_int()
        ss_len = c_int()

        rc = self._lib.tongsuo_kem_encaps(
            self._alg.encode(),
            public_key, len(public_key),
            ct_buf, ctypes.byref(ct_len),
            ss_buf, ctypes.byref(ss_len),
            self.ct_bytes, self.ss_bytes,
        )
        if rc != 0:
            raise RuntimeError(f"Tongsuo ML-KEM encaps 失败: rc={rc}")

        return KEMEncapsulation(
            ciphertext=ct_buf.raw[:ct_len.value],
            shared_secret=ss_buf.raw[:ss_len.value],
        )

    def decaps(self, secret_key: bytes, ciphertext: bytes, public_key: bytes = b"") -> bytes:
        import ctypes
        from ctypes import c_int, byref, create_string_buffer

        ss_buf = create_string_buffer(self.ss_bytes)
        ss_len = c_int()

        rc = self._lib.tongsuo_kem_decaps(
            self._alg.encode(),
            secret_key, len(secret_key),
            public_key, len(public_key),
            ciphertext, len(ciphertext),
            ss_buf, ctypes.byref(ss_len),
            self.ss_bytes,
        )
        if rc != 0:
            raise RuntimeError(f"Tongsuo ML-KEM decaps 失败: rc={rc}")

        return ss_buf.raw[:ss_len.value]


# ── LibOQS 后端（备选） ──

class LibOQSBackend(KEMBackend):
    """基于 liboqs 的后端（备选）

    依赖：pip install liboqs-python
    系统需安装 liboqs C 库：https://github.com/open-quantum-safe/liboqs
    """

    def __init__(self, param_set: str = "768"):
        if param_set not in _ALG_NAMES:
            raise ValueError(f"不支持的参数集: {param_set}，可选: {list(_ALG_NAMES)}")
        self._param = param_set
        self._alg = _ALG_NAMES[param_set]

        try:
            import oqs
        except (ImportError, RuntimeError, SystemExit) as e:
            raise ImportError(
                f"liboqs 导入失败: {e}\n"
                f"请确认已安装 liboqs C 库和 liboqs-python。\n"
                f"编译指南: https://github.com/open-quantum-safe/liboqs/wiki/CMake-build-options"
            ) from e

        enabled_kems = getattr(oqs, "get_enabled_KEM_mechanisms", None) or getattr(oqs, "get_enabled_kem_mechanisms", None)
        if enabled_kems is None:
            raise RuntimeError("liboqs 版本不兼容：找不到 get_enabled_KEM_mechanisms")
        if self._alg not in enabled_kems():
            raise RuntimeError(
                f"liboqs 未启用 {self._alg}。"
                f"当前可用 ML-KEM: "
                f"{[m for m in enabled_kems() if 'ML-KEM' in m]}"
            )
        self._oqs = oqs

    @property
    def name(self) -> str:
        return f"liboqs-{self._alg}"

    @property
    def param_set(self) -> str:
        return self._param

    @property
    def pk_bytes(self) -> int:
        with self._oqs.KeyEncapsulation(self._alg) as kem:
            return kem.details["length_public_key"]

    @property
    def sk_bytes(self) -> int:
        with self._oqs.KeyEncapsulation(self._alg) as kem:
            return kem.details["length_secret_key"]

    @property
    def ct_bytes(self) -> int:
        with self._oqs.KeyEncapsulation(self._alg) as kem:
            return kem.details["length_ciphertext"]

    @property
    def ss_bytes(self) -> int:
        with self._oqs.KeyEncapsulation(self._alg) as kem:
            return kem.details["length_shared_secret"]

    def keygen(self) -> KEMKeyPair:
        with self._oqs.KeyEncapsulation(self._alg) as kem:
            pk = kem.generate_keypair()
            sk = kem.export_secret_key()
        return KEMKeyPair(public_key=pk, secret_key=sk)

    def encaps(self, public_key: bytes) -> KEMEncapsulation:
        with self._oqs.KeyEncapsulation(self._alg) as kem:
            ct, ss = kem.encap_secret(public_key)
        return KEMEncapsulation(ciphertext=ct, shared_secret=ss)

    def decaps(self, secret_key: bytes, ciphertext: bytes, public_key: bytes = b"") -> bytes:
        with self._oqs.KeyEncapsulation(self._alg, secret_key) as kem:
            ss = kem.decap_secret(ciphertext)
        return ss

# ── 后端自动选择 ──

def get_backend(param_set: str = "768") -> KEMBackend:
    """按优先级自动选择可用的 KEM 后端

    优先级：Tongsuo > liboqs

    如果两个可信后端均不可用，直接抛出 RuntimeError 拒绝通信，
    防止不安全降级。
    """
    errors = []

    # 1. Tongsuo（桥接库可能加载成功但运行时不兼容，需验证 keygen）
    try:
        backend = TongsuoBackend(param_set)
        backend.keygen()  # 健康检查：确认 libcrypto 真正支持 ML-KEM
        return backend
    except (ImportError, RuntimeError, OSError) as e:
        errors.append(f"Tongsuo: {e}")

    # 2. liboqs（自动检测项目内 liboqs-dist 目录）
    _oqs_path = _detect_oqs_install_path()
    if _oqs_path:
        os.environ["OQS_INSTALL_PATH"] = _oqs_path
    try:
        return LibOQSBackend(param_set)
    except (ImportError, RuntimeError) as e:
        errors.append(f"liboqs: {e}")

    # 无可信后端可用 → 拒绝通信
    raise RuntimeError(
        "没有可用的可信 KEM 后端（Tongsuo、liboqs 均不可用），拒绝建立不安全会话。\n"
        "请安装其中之一：\n"
        "  - Tongsuo: ./docker/docker-build.sh\n"
        "  - liboqs:  pip install liboqs-python\n"
        + "\n".join(f"  - {e}" for e in errors)
    )
