#!/usr/bin/env bash
set -euo pipefail

OUT_ROOT="${1:?usage: make-portable-runtime-dirs.sh OUT_ROOT}"
TVM_ENV="${TVM_ENV:-/home/user/anaconda3/envs/tvm310_safe}"
MNN_ENV="${MNN_ENV:-/home/user/anaconda3/envs/MNN}"

copy_site_pkg() {
    local src_sp="$1"
    local dst_sp="$2"
    local item="$3"
    shopt -s nullglob
    local path
    for path in "${src_sp}"/${item}; do
        [ -e "${path}" ] && cp -a "${path}" "${dst_sp}/"
    done
    shopt -u nullglob
}

copy_env_libs() {
    local src="$1"
    local dst="$2"
    find "${src}/lib" -maxdepth 1 \( -type f -o -type l \) \
        \( -name '*.so' -o -name '*.so.*' \) \
        -exec cp -a {} "${dst}/lib/" \;
}

make_tvm_py310() {
    local src="${TVM_ENV}"
    local dst="${OUT_ROOT}/tvm_py310"
    local py="python3.10"

    rm -rf "${dst}"
    mkdir -p "${dst}/bin" "${dst}/lib/${py}/site-packages" "${dst}/lib"
    cp -a "${src}/bin/python" "${dst}/bin/"
    [ -e "${src}/bin/python3" ] && cp -a "${src}/bin/python3" "${dst}/bin/" || true
    [ -e "${src}/bin/python3.10" ] && cp -a "${src}/bin/python3.10" "${dst}/bin/" || true

    copy_env_libs "${src}" "${dst}"
    tar -C "${src}/lib/${py}" --exclude='./site-packages' -cf - . |
        tar -C "${dst}/lib/${py}" -xf -

    local sp="${src}/lib/${py}/site-packages"
    local dsp="${dst}/lib/${py}/site-packages"
    local item
    for item in \
        numpy 'numpy-*.dist-info' numpy.libs \
        PIL 'pillow-*.dist-info' pillow.libs \
        tvm_ffi 'apache_tvm_ffi-*.dist-info' \
        packaging 'packaging-*.dist-info' \
        typing_extensions.py 'typing_extensions-*.dist-info' \
        decorator.py 'decorator-*.dist-info' \
        cloudpickle 'cloudpickle-*.dist-info' \
        psutil 'psutil-*.dist-info' \
        attrs 'attrs-*.dist-info'; do
        copy_site_pkg "${sp}" "${dsp}" "${item}"
    done
}

make_mnn_py312() {
    local src="${MNN_ENV}"
    local dst="${OUT_ROOT}/mnn_py312"
    local py="python3.12"

    rm -rf "${dst}"
    mkdir -p "${dst}/bin" "${dst}/lib/${py}/site-packages" "${dst}/lib"
    cp -a "${src}/bin/python" "${dst}/bin/"
    [ -e "${src}/bin/python3" ] && cp -a "${src}/bin/python3" "${dst}/bin/" || true
    [ -e "${src}/bin/python3.12" ] && cp -a "${src}/bin/python3.12" "${dst}/bin/" || true
    [ -e "${src}/bin/torch_shm_manager" ] && cp -a "${src}/bin/torch_shm_manager" "${dst}/bin/" || true

    copy_env_libs "${src}" "${dst}"
    tar -C "${src}/lib/${py}" --exclude='./site-packages' -cf - . |
        tar -C "${dst}/lib/${py}" -xf -

    local sp="${src}/lib/${py}/site-packages"
    local dsp="${dst}/lib/${py}/site-packages"
    local item
    for item in \
        MNN '_mnncengine*.so' '_tools*.so' mnn.libs \
        numpy 'numpy-*.dist-info' numpy.libs \
        PIL 'pillow-*.dist-info' pillow.libs \
        torch 'torch-*.dist-info' torchgen functorch \
        torchvision 'torchvision-*.dist-info' torchvision.libs \
        filelock 'filelock-*.dist-info' \
        typing_extensions.py 'typing_extensions-*.dist-info' \
        sympy 'sympy-*.dist-info' \
        mpmath 'mpmath-*.dist-info' \
        networkx 'networkx-*.dist-info' \
        jinja2 'jinja2-*.dist-info' \
        markupsafe 'MarkupSafe-*.dist-info' \
        fsspec 'fsspec-*.dist-info' \
        packaging 'packaging-*.dist-info'; do
        copy_site_pkg "${sp}" "${dsp}" "${item}"
    done
}

mkdir -p "${OUT_ROOT}"
make_tvm_py310
make_mnn_py312

echo "portable-runtimes-ready ${OUT_ROOT}"
