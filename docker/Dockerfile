# Tongsuo 编译环境 — 集创赛飞腾赛道
# 用途：编译 Tongsuo 密码库，产出 .so 供 Python ctypes 调用
# 支持 multi-arch：x86_64 开发机 + aarch64 飞腾派

ARG BASE_IMAGE=ubuntu:22.04
ARG UV_INSTALL_SCRIPT_URL=https://astral.sh/uv/install.sh
ARG UV_VERSION=0.6.14

FROM ${BASE_IMAGE} AS builder

# 使用 uv 作为 Python 环境管理工具（通过 PyPI 安装，避免额外镜像源依赖）

ENV DEBIAN_FRONTEND=noninteractive
# 使用阿里云镜像源，避免 Ubuntu 官方源 502
RUN sed -i 's|http://archive.ubuntu.com|http://mirrors.aliyun.com|g' /etc/apt/sources.list \
    && sed -i 's|http://security.ubuntu.com|http://mirrors.aliyun.com|g' /etc/apt/sources.list \
    && apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    perl \
    python3 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf ${UV_INSTALL_SCRIPT_URL} | env UV_UNMANAGED_INSTALL=/usr/local/bin UV_VERSION=${UV_VERSION} sh

# 编译 Tongsuo
COPY Tongsuo/ /build/Tongsuo/
WORKDIR /build/Tongsuo

RUN ./config \
    --prefix=/usr/local/tongsuo \
    --openssldir=/usr/local/tongsuo/ssl \
    enable-ntls \
    && make -j$(nproc) \
    && make install_sw

# 验证编译产物
RUN /usr/local/tongsuo/bin/openssl version \
    && /usr/local/tongsuo/bin/openssl list -kem-algorithms | grep -i ml-kem || true

# 编译 KEM C 桥接库（简化 Python ctypes 调用）
COPY docker/tongsuo_kem_bridge.c /build/
RUN gcc -shared -fPIC -O2 -o /usr/local/tongsuo/lib64/libtongsuo_kem_bridge.so \
    /build/tongsuo_kem_bridge.c \
    -I/usr/local/tongsuo/include \
    -L/usr/local/tongsuo/lib64 -lcrypto -Wl,-rpath,/usr/local/tongsuo/lib64

# 编译 SM2 签名 C 桥接库（供认证握手使用）
COPY docker/tongsuo_sig_bridge.c /build/
RUN gcc -shared -fPIC -O2 -o /usr/local/tongsuo/lib64/libtongsuo_sig_bridge.so \
    /build/tongsuo_sig_bridge.c \
    -I/usr/local/tongsuo/include \
    -L/usr/local/tongsuo/lib64 -lcrypto -Wl,-rpath,/usr/local/tongsuo/lib64

# ── 运行时镜像（仅包含编译产物） ──
FROM ${BASE_IMAGE}

ARG ICCOMP_TORCH_VERSION=2.6.0
ARG ICCOMP_INSTALL_TORCH=1

ENV DEBIAN_FRONTEND=noninteractive
RUN sed -i 's|http://archive.ubuntu.com|http://mirrors.aliyun.com|g' /etc/apt/sources.list \
    && sed -i 's|http://security.ubuntu.com|http://mirrors.aliyun.com|g' /etc/apt/sources.list \
    && apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf ${UV_INSTALL_SCRIPT_URL} | env UV_UNMANAGED_INSTALL=/usr/local/bin UV_VERSION=${UV_VERSION} sh

COPY --from=builder /usr/local/tongsuo/ /usr/local/tongsuo/

# uv 安装 Python 依赖
# cryptography 45.0.7 内置 OpenSSL 3.5.0+，wheel 包含 SM4 + AES + ML-KEM 相关 EVP
# 需要 Python >= 3.11（abi3 wheel），uv 管理独立 Python 3.12
RUN uv python install 3.12 \
    && uv venv --python 3.12 /app \
    && uv pip install --python /app/bin/python3 \
        'cryptography==45.0.7' \
                pytest \
        && if [ "${ICCOMP_INSTALL_TORCH}" = "1" ]; then \
                arch="$(dpkg --print-architecture)"; \
                if [ "$arch" = "amd64" ]; then \
                    uv pip install --python /app/bin/python3 \
                        --index-url https://download.pytorch.org/whl/cpu \
                        "torch==${ICCOMP_TORCH_VERSION}+cpu"; \
                else \
                    uv pip install --python /app/bin/python3 \
                        "torch==${ICCOMP_TORCH_VERSION}"; \
                fi; \
            fi

# 确保 Python 能找到 Tongsuo 的 .so
ENV LD_LIBRARY_PATH=/usr/local/tongsuo/lib64:/usr/local/tongsuo/lib
ENV PATH=/app/bin:/usr/local/tongsuo/bin:$PATH
ENV TONGSUO_KEM_BRIDGE=/usr/local/tongsuo/lib64/libtongsuo_kem_bridge.so
ENV TONGSUO_SIG_BRIDGE=/usr/local/tongsuo/lib64/libtongsuo_sig_bridge.so

WORKDIR /workspace

CMD ["python3"]
