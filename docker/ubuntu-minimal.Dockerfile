FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    VIRTUAL_ENV=/opt/iccomp-venv

ARG NODE_MAJOR=20
ARG NODESOURCE_BASE=https://deb.nodesource.com
ARG UBUNTU_MIRROR=http://mirrors.tuna.tsinghua.edu.cn/ubuntu

WORKDIR /workspace

COPY --from=ghcr.io/astral-sh/uv:0.9.13 /uv /usr/local/bin/uv
COPY --from=ghcr.io/astral-sh/uv:0.9.13 /uvx /usr/local/bin/uvx

RUN sed -i \
        -e "s|http://archive.ubuntu.com/ubuntu/|${UBUNTU_MIRROR}/|g" \
        -e "s|http://security.ubuntu.com/ubuntu/|${UBUNTU_MIRROR}/|g" \
        /etc/apt/sources.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        build-essential \
        ca-certificates \
        cmake \
        curl \
        fontconfig \
        git \
        gnupg \
        libasound2 \
        libatk-bridge2.0-0 \
        libatk1.0-0 \
        libcups2 \
        libdrm2 \
        libgbm1 \
        libgtk-3-0 \
        libnss3 \
        libx11-xcb1 \
        libxcomposite1 \
        libxdamage1 \
        libxfixes3 \
        libxkbcommon0 \
        libxrandr2 \
        libxss1 \
        openssh-client \
        python3 \
        python3-venv \
        sshpass \
        xauth \
        xvfb \
    && rm -rf /var/lib/apt/lists/*

RUN install -d -m 0755 /etc/apt/keyrings \
    && curl -fsSL "${NODESOURCE_BASE}/gpgkey/nodesource-repo.gpg.key" \
        | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] ${NODESOURCE_BASE}/node_${NODE_MAJOR}.x nodistro main" \
        > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY liboqs /tmp/liboqs

RUN test -f /tmp/liboqs/CMakeLists.txt \
    && cmake -S /tmp/liboqs -B /tmp/liboqs/build \
        -DCMAKE_INSTALL_PREFIX=/opt/liboqs \
        -DOQS_ALGS_ENABLED=STD \
        -DOQS_BUILD_TESTS=OFF \
        -DOQS_USE_OPENSSL=OFF \
        -DBUILD_SHARED_LIBS=ON \
    && cmake --build /tmp/liboqs/build --parallel "$(nproc)" \
    && cmake --install /tmp/liboqs/build \
    && rm -rf /tmp/liboqs

ENV OQS_INSTALL_PATH=/opt/liboqs \
    LD_LIBRARY_PATH=/opt/liboqs/lib:/opt/liboqs/lib64

COPY requirements.txt /tmp/requirements.txt
COPY docker/check_deps.py /tmp/check_deps.py

RUN uv venv "${VIRTUAL_ENV}" \
    && uv pip install --python "${VIRTUAL_ENV}/bin/python" pip setuptools wheel \
    && uv pip install --python "${VIRTUAL_ENV}/bin/python" -r /tmp/requirements.txt \
    && "${VIRTUAL_ENV}/bin/python" /tmp/check_deps.py --python-only

ENV PATH="/opt/iccomp-venv/bin:${PATH}"

COPY --from=tailscale/tailscale:stable /usr/local/bin/tailscale /usr/local/bin/tailscale
COPY --from=tailscale/tailscale:stable /usr/local/bin/tailscaled /usr/local/bin/tailscaled

COPY Semantic-Communication/cockpit_desktop/package.json /tmp/cockpit_desktop/package.json
COPY Semantic-Communication/cockpit_desktop/package-lock.json /tmp/cockpit_desktop/package-lock.json

RUN cd /tmp/cockpit_desktop \
    && npm ci \
    && npm cache clean --force

COPY README.md requirements.txt /workspace/
COPY docker /workspace/docker
COPY mlkem_link /workspace/mlkem_link
COPY scripts /workspace/scripts
COPY Semantic-Communication /workspace/Semantic-Communication

RUN ln -sfn /opt/iccomp-venv /workspace/.venv \
    && ln -sfn /opt/liboqs /workspace/liboqs-dist \
    && sed -i 's/\r$//' /workspace/docker/*.sh \
    && find /workspace/Semantic-Communication -type f -name '*.sh' -exec sed -i 's/\r$//' {} + \
    && chmod +x /workspace/docker/*.sh \
    && mkdir -p /usr/local/share/fonts/iccomp-cockpit \
    && cp /workspace/Semantic-Communication/cockpit_desktop/src/renderer/src/assets/fonts/*.ttf /usr/local/share/fonts/iccomp-cockpit/ \
    && fc-cache -f

RUN cd /workspace/Semantic-Communication/cockpit_desktop \
    && rm -rf node_modules \
    && cp -a /tmp/cockpit_desktop/node_modules ./node_modules \
    && npm run build \
    && test -f out/main/index.js \
    && test -f out/renderer/index.html \
    && python /workspace/docker/check_deps.py

CMD ["/bin/bash"]
