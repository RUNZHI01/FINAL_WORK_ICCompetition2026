# 开发环境 — 集创赛飞腾赛道
# 用途：一键构建完整的 Python 开发环境（liboqs + ML-KEM + 所有依赖）
# 队友只需 Docker + clone 仓库，无需手动编译任何 C 库
#
# 构建:
#   ./docker/dev.sh build
#
# 运行:
#   ./docker/dev.sh pytest mlkem_link/tests/ -v
#   ./docker/dev.sh python scripts/demo_e2e.py
#   ./docker/dev.sh bash

FROM hub.rat.dev/library/ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
RUN sed -i 's|http://archive.ubuntu.com|http://mirrors.aliyun.com|g' /etc/apt/sources.list \
    && sed -i 's|http://security.ubuntu.com|http://mirrors.aliyun.com|g' /etc/apt/sources.list \
    && apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    perl \
    python3 \
    python3-pip \
    python3-venv \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ── 编译 Tongsuo（铜锁，国密 + ML-KEM）──
# 本地子模块已 checkout 到正确 commit (baa1bb2b)
COPY Tongsuo /build/Tongsuo
RUN cd /build/Tongsuo \
    && ./config \
        --prefix=/usr/local/tongsuo \
        --openssldir=/usr/local/tongsuo/ssl \
        enable-ntls \
    && make -j$(nproc) \
    && make install_sw \
    && rm -rf /build/Tongsuo

# ── 编译 Tongsuo KEM 桥接库 ──
COPY docker/tongsuo_kem_bridge.c /build/tongsuo_kem_bridge.c
RUN gcc -shared -fPIC -O2 \
        -o /usr/local/tongsuo/lib64/libtongsuo_kem_bridge.so \
        /build/tongsuo_kem_bridge.c \
        -I/usr/local/tongsuo/include \
        -L/usr/local/tongsuo/lib64 -lcrypto \
        -Wl,-rpath,/usr/local/tongsuo/lib64 \
    && rm /build/tongsuo_kem_bridge.c

# ── 编译 liboqs 0.14.0（备用后端）──
# 本地子模块已 checkout 到正确版本 (0.14.0)
COPY liboqs /build/liboqs
RUN cd /build/liboqs \
    && mkdir -p build && cd build \
    && cmake .. \
        -DCMAKE_INSTALL_PREFIX=/usr/local/liboqs \
        -DOQS_ALGS_ENABLED=ML-KEM \
        -DOQS_BUILD_TESTS=OFF \
        -DOQS_USE_OPENSSL=OFF \
        -DBUILD_SHARED_LIBS=ON \
    && make -j$(nproc) \
    && make install \
    && rm -rf /build/liboqs

# ── Python 依赖（用 venv 避免系统包冲突）──
RUN python3 -m venv /app
ENV PATH=/app/bin:$PATH
RUN pip install --no-cache-dir \
    -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com \
    'cryptography>=46.0' \
    'liboqs-python>=0.14.0' \
    'numpy>=2.0' \
    'Pillow>=12.0' \
    'textual>=8.0' \
    'rich>=14.0' \
    'matplotlib>=3.8' \
    'pytest>=9.0'

# ── 环境变量 ──
ENV OQS_INSTALL_PATH=/usr/local/liboqs
ENV TONGSUO_KEM_BRIDGE=/usr/local/tongsuo/lib64/libtongsuo_kem_bridge.so
ENV LD_LIBRARY_PATH=/usr/local/tongsuo/lib64:/usr/local/liboqs/lib

WORKDIR /workspace

CMD ["bash"]
