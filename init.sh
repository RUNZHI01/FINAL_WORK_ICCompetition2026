#!/usr/bin/env bash
# ── ICCompetition2026 runtime 初始化 ──
# 默认只初始化本机运行时；加 --board 后才会连接板端生成/同步认证资产。
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$REPO_ROOT/.venv"
TONGSUO_SRC="$REPO_ROOT/Tongsuo"
TONGSUO_DIST="$REPO_ROOT/tongsuo-dist"
TONGSUO_BUILD="$REPO_ROOT/build/tongsuo-x86_64"
PERL5_SHIM="$REPO_ROOT/build/perl5"
AUTH_DIR="$REPO_ROOT/artifacts/mlkem_auth"
LOCAL_KEYS_DIR="$AUTH_DIR/peer"

BOARD_HOST="${REMOTE_HOST:-${PHYTIUM_PI_HOST:-100.121.87.73}}"
BOARD_USER="${REMOTE_USER:-${PHYTIUM_PI_USER:-user}}"
BOARD_PORT="${REMOTE_SSH_PORT:-${PHYTIUM_PI_PORT:-22}}"
BOARD_KEYS_DIR="${MLKEM_REMOTE_KEYS_DIR:-/home/user/keys}"
BOARD_PYTHON="${MLKEM_REMOTE_PYTHON:-/home/user/anaconda3/envs/mlkem/bin/python}"
BOARD_OQS="${MLKEM_REMOTE_OQS_INSTALL_PATH:-/home/user/liboqs-dist}"
BOARD_LD="${MLKEM_REMOTE_LD_LIBRARY_PATH:-/home/user/liboqs-dist/lib}"
BOARD_SIG_BRIDGE="${MLKEM_REMOTE_TONGSUO_SIG_BRIDGE:-/home/user/libtongsuo_sig_bridge.so}"
BOARD_KEM_BRIDGE="${MLKEM_REMOTE_TONGSUO_KEM_BRIDGE:-/usr/local/tongsuo/lib/libtongsuo_kem_bridge.so}"
BOARD_RUN_LOGGER_DIR="${MLKEM_REMOTE_RUN_LOGGER_DIR:-/home/user/artifacts/evidence/logs}"
BOARD_STATUS_PORT="${MLKEM_STATUS_PORT:-8080}"
BOARD_USRP_RX_DIR="${REMOTE_USRP_RX_DIR:-/home/user/cockpit_usrp_rx}"

WITH_BOARD=false
SKIP_TONGSUO=false
SKIP_VENV=false
FORCE_KEYS=false

G='\033[0;32m'; Y='\033[0;33m'; R='\033[0;31m'; N='\033[0m'

usage() {
    cat <<'EOF'
用法: ./init.sh [--board] [--force-keys] [--skip-tongsuo] [--skip-venv]

默认:
  初始化本机 .venv、Tongsuo runtime、KEM/SIG bridge，并做本机 SM2 + ML-DSA 自检。

选项:
  --board        通过 SSH 初始化板端认证资产，并把板端公钥同步到 artifacts/mlkem_auth/peer/
  --force-keys   仅配合 --board 使用，允许重新生成板端身份密钥
  --skip-tongsuo 跳过本机 Tongsuo/bridge 构建
  --skip-venv    跳过 .venv 创建和 requirements 安装
EOF
}

log() {
    echo -e "${G}[init] $*${N}"
}

warn() {
    echo -e "${Y}[init] $*${N}"
}

die() {
    echo -e "${R}[init] $*${N}" >&2
    exit 1
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --board)
            WITH_BOARD=true
            ;;
        --force-keys)
            FORCE_KEYS=true
            ;;
        --skip-tongsuo)
            SKIP_TONGSUO=true
            ;;
        --skip-venv)
            SKIP_VENV=true
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            die "不支持的参数: $1"
            ;;
    esac
    shift
done

ensure_venv() {
    if $SKIP_VENV; then
        warn "跳过 .venv 初始化"
        return 0
    fi
    if [ ! -d "$VENV" ]; then
        log "创建 .venv"
        python3 -m venv "$VENV"
    fi
    patch_venv_activate
    # shellcheck source=/dev/null
    source "$VENV/bin/activate"
    export OQS_INSTALL_PATH="$REPO_ROOT/liboqs/liboqs-dist"
    export LD_LIBRARY_PATH="$OQS_INSTALL_PATH/lib64:$OQS_INSTALL_PATH/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    python -m pip install -U pip
    python -m pip install -r "$REPO_ROOT/requirements.txt"
}

patch_venv_activate() {
    local activate="$VENV/bin/activate"
    [ -f "$activate" ] || return 0
    python3 - <<'PY' "$activate"
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
start = text.find("# ── liboqs 环境变量（ML-KEM 后端）──")
if start == -1:
    block = """
# ── liboqs 环境变量（ML-KEM 后端）──
_PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export OQS_INSTALL_PATH="$_PROJECT_ROOT/liboqs/liboqs-dist"
export LD_LIBRARY_PATH="$_PROJECT_ROOT/liboqs/liboqs-dist/lib64:$_PROJECT_ROOT/liboqs/liboqs-dist/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
"""
    marker = "# unset PYTHONHOME if set"
    idx = text.find(marker)
    text = text[:idx] + block + "\n" + text[idx:] if idx != -1 else text + block
else:
    end = text.find("# unset PYTHONHOME if set", start)
    if end == -1:
        end = start
    block = """# ── liboqs 环境变量（ML-KEM 后端）──
_PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export OQS_INSTALL_PATH="$_PROJECT_ROOT/liboqs/liboqs-dist"
export LD_LIBRARY_PATH="$_PROJECT_ROOT/liboqs/liboqs-dist/lib64:$_PROJECT_ROOT/liboqs/liboqs-dist/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

"""
    text = text[:start] + block + text[end:]
path.write_text(text, encoding="utf-8")
PY
}

ensure_perl_shims() {
    mkdir -p "$PERL5_SHIM/IPC" "$PERL5_SHIM/File" "$PERL5_SHIM/Time"
    cat > "$PERL5_SHIM/FindBin.pm" <<'EOF'
package FindBin;
use strict;
use warnings;
use Cwd qw(abs_path);
use File::Basename qw(dirname basename);
our $Bin;
our $RealBin;
our $Script;
our $RealScript;
BEGIN {
    my $script = $0;
    my $path = abs_path($script) || $script;
    $Bin = dirname($path);
    $RealBin = $Bin;
    $Script = basename($script);
    $RealScript = $Script;
}
1;
EOF
    cat > "$PERL5_SHIM/lib.pm" <<'EOF'
package lib;
use strict;
use warnings;
sub import {
    shift;
    for my $path (reverse @_) {
        next if !defined $path || $path eq "";
        unshift @INC, $path if -d $path;
    }
}
sub unimport {
    shift;
    my %remove = map { $_ => 1 } @_;
    @INC = grep { !$remove{$_} } @INC;
}
1;
EOF
    cat > "$PERL5_SHIM/IPC/Cmd.pm" <<'EOF'
package IPC::Cmd;
use strict;
use warnings;
use Exporter qw(import);
use File::Spec;
our @EXPORT_OK = qw(can_run);
sub can_run {
    my ($cmd) = @_;
    return undef if !defined $cmd || $cmd eq "";
    return $cmd if File::Spec->file_name_is_absolute($cmd) && -x $cmd;
    for my $dir (split /:/, $ENV{PATH} || "") {
        next if $dir eq "";
        my $candidate = File::Spec->catfile($dir, $cmd);
        return $candidate if -x $candidate && !-d $candidate;
    }
    return undef;
}
1;
EOF
    cat > "$PERL5_SHIM/File/Compare.pm" <<'EOF'
package File::Compare;
use strict;
use warnings;
use Exporter qw(import);
our @EXPORT = qw(compare compare_text);
sub _open_handle {
    my ($value) = @_;
    return $value if ref($value);
    open my $fh, "<", $value or return undef;
    binmode $fh;
    return $fh;
}
sub compare {
    my ($left, $right, $buffer_size) = @_;
    $buffer_size ||= 8192;
    my $left_fh = _open_handle($left);
    return -1 if !$left_fh;
    my $right_fh = _open_handle($right);
    return -1 if !$right_fh;
    while (1) {
        my $left_read = read($left_fh, my $left_buf, $buffer_size);
        my $right_read = read($right_fh, my $right_buf, $buffer_size);
        return -1 if !defined $left_read || !defined $right_read;
        return 1 if $left_read != $right_read || $left_buf ne $right_buf;
        return 0 if $left_read == 0;
    }
}
sub compare_text {
    return compare(@_);
}
1;
EOF
    cat > "$PERL5_SHIM/Time/Piece.pm" <<'EOF'
package Time::Piece;
use strict;
use warnings;
use Exporter qw(import);
use POSIX ();
use Time::Local qw(timelocal);
our @EXPORT = qw(localtime gmtime);
sub new {
    my ($class, $epoch, $is_gmt) = @_;
    return bless { epoch => $epoch, is_gmt => $is_gmt ? 1 : 0 }, $class;
}
sub localtime {
    my ($epoch) = @_;
    $epoch = CORE::time() if !defined $epoch;
    return __PACKAGE__->new($epoch, 0);
}
sub gmtime {
    my ($epoch) = @_;
    $epoch = CORE::time() if !defined $epoch;
    return __PACKAGE__->new($epoch, 1);
}
sub strptime {
    my ($class, $value, $format) = @_;
    die "unsupported format" if !defined $format || $format ne "%d %b %Y";
    my %month = (
        Jan => 0, Feb => 1, Mar => 2, Apr => 3, May => 4, Jun => 5,
        Jul => 6, Aug => 7, Sep => 8, Oct => 9, Nov => 10, Dec => 11,
    );
    my ($day, $mon, $year) = $value =~ /^(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})$/;
    die "unsupported date" if !defined $day || !exists $month{$mon};
    return $class->new(timelocal(0, 0, 0, int($day), $month{$mon}, int($year) - 1900), 0);
}
sub strftime {
    my ($self, $format) = @_;
    my @parts = $self->{is_gmt} ? CORE::gmtime($self->{epoch}) : CORE::localtime($self->{epoch});
    return POSIX::strftime($format, @parts);
}
1;
EOF
}

build_tongsuo() {
    if $SKIP_TONGSUO; then
        warn "跳过 Tongsuo/bridge 构建"
        return 0
    fi
    [ -x "$TONGSUO_SRC/Configure" ] || die "Tongsuo 子模块不可用，请先运行 git submodule update --init --recursive"

    ensure_perl_shims
    mkdir -p "$TONGSUO_BUILD" "$TONGSUO_DIST/lib64"
    if [ ! -x "$TONGSUO_DIST/bin/openssl" ] || [ ! -f "$TONGSUO_DIST/lib64/libcrypto.so.3" ]; then
        log "构建并安装本机 Tongsuo runtime"
        (
            cd "$TONGSUO_BUILD"
            PERL5LIB="$PERL5_SHIM" "$TONGSUO_SRC/Configure" linux-x86_64 \
                --prefix="$TONGSUO_DIST" \
                --openssldir="$TONGSUO_DIST/ssl" \
                enable-ntls
            PERL5LIB="$PERL5_SHIM" make -j"$(nproc)"
            PERL5LIB="$PERL5_SHIM" make install_sw
        )
    else
        log "复用已有 Tongsuo runtime: $TONGSUO_DIST"
    fi

    log "构建本机 KEM/SIG bridge"
    gcc -shared -fPIC -O2 -Wno-deprecated-declarations \
        -o "$TONGSUO_DIST/lib64/libtongsuo_kem_bridge.so" \
        "$REPO_ROOT/docker/tongsuo_kem_bridge.c" \
        -I"$TONGSUO_DIST/include" -L"$TONGSUO_DIST/lib64" -lcrypto \
        -Wl,-rpath,"$TONGSUO_DIST/lib64"
    gcc -shared -fPIC -O2 -Wno-deprecated-declarations \
        -o "$TONGSUO_DIST/lib64/libtongsuo_sig_bridge.so" \
        "$REPO_ROOT/docker/tongsuo_sig_bridge.c" \
        -I"$TONGSUO_DIST/include" -L"$TONGSUO_DIST/lib64" -lcrypto \
        -Wl,-rpath,"$TONGSUO_DIST/lib64"
}

local_smoke() {
    (
        # shellcheck source=/dev/null
        source "$VENV/bin/activate"
        local oqs_root="$REPO_ROOT/liboqs/liboqs-dist"
        if [ ! -d "$oqs_root" ] && [ -d "$REPO_ROOT/liboqs-dist" ]; then
            oqs_root="$REPO_ROOT/liboqs-dist"
        fi
        export OQS_INSTALL_PATH="$oqs_root"
        export TONGSUO_SIG_BRIDGE="$TONGSUO_DIST/lib64/libtongsuo_sig_bridge.so"
        export TONGSUO_KEM_BRIDGE="$TONGSUO_DIST/lib64/libtongsuo_kem_bridge.so"
        export LD_LIBRARY_PATH="$TONGSUO_DIST/lib64:$oqs_root/lib64:$oqs_root/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

        log "本机 SM2 / ML-DSA / ML-KEM 自检"
        python - <<'PY'
from mlkem_link.auth import get_sm2_backend, get_mldsa_backend
from mlkem_link.kem import get_backend

for name, fn in (("sm2", get_sm2_backend), ("mldsa", get_mldsa_backend)):
    backend = fn()
    pk, sk = backend.keygen()
    msg = b"iccomp-init-smoke"
    sig = backend.sign(sk, msg)
    assert backend.verify(pk, msg, sig)
    assert not backend.verify(pk, msg + b"!", sig)
    print(f"{name}: {backend.name} ok")

kem = get_backend()
kp = kem.keygen()
enc = kem.encaps(kp.public_key)
assert kem.decaps(kp.secret_key, enc.ciphertext, kp.public_key) == enc.shared_secret
print(f"kem: {kem.name} ok")
PY
    )
}

board_password() {
    local password="${REMOTE_PASS:-${PHYTIUM_PI_PASSWORD:-}}"
    if [ -n "$password" ]; then
        printf '%s' "$password"
        return 0
    fi
    read -r -s -p "板端 SSH 密码 (${BOARD_USER}@${BOARD_HOST}): " password
    echo >&2
    [ -n "$password" ] || die "未提供板端 SSH 密码"
    printf '%s' "$password"
}

board_ssh() {
    local password="$1"
    shift
    (
        unset LD_LIBRARY_PATH
        SSHPASS="$password" sshpass -e ssh \
            -o StrictHostKeyChecking=no \
            -o UserKnownHostsFile=/dev/null \
            -o ConnectTimeout=8 \
            -p "$BOARD_PORT" \
            "$BOARD_USER@$BOARD_HOST" \
            "$@"
    )
}

board_scp_from() {
    local password="$1"
    local remote_path="$2"
    local local_path="$3"
    (
        unset LD_LIBRARY_PATH
        SSHPASS="$password" sshpass -e scp \
            -o StrictHostKeyChecking=no \
            -o UserKnownHostsFile=/dev/null \
            -P "$BOARD_PORT" \
            "$BOARD_USER@$BOARD_HOST:$remote_path" \
            "$local_path"
    )
}

init_board_auth() {
    $WITH_BOARD || return 0
    command -v sshpass >/dev/null 2>&1 || die "缺少 sshpass，无法自动初始化板端"

    local password
    password="$(board_password)"
    local force_flag="0"
    $FORCE_KEYS && force_flag="1"

    log "检查并初始化板端认证资产: ${BOARD_USER}@${BOARD_HOST}:${BOARD_PORT}"
    board_ssh "$password" "BOARD_KEYS_DIR='$BOARD_KEYS_DIR' BOARD_PYTHON='$BOARD_PYTHON' BOARD_OQS='$BOARD_OQS' BOARD_LD='$BOARD_LD' BOARD_SIG_BRIDGE='$BOARD_SIG_BRIDGE' FORCE_KEYS='$force_flag' bash -s" <<'REMOTE'
set -euo pipefail
need_files=(
  "$BOARD_KEYS_DIR/server_sm2_identity.key"
  "$BOARD_KEYS_DIR/server_sm2_identity.pub"
  "$BOARD_KEYS_DIR/server_mldsa_identity.key"
  "$BOARD_KEYS_DIR/server_mldsa_identity.pub"
)
missing=0
for path in "${need_files[@]}"; do
  [ -s "$path" ] || missing=1
done
if [ "$FORCE_KEYS" = "1" ]; then
  missing=1
fi
mkdir -p "$BOARD_KEYS_DIR"
chmod 700 "$BOARD_KEYS_DIR"
if [ "$missing" = "1" ]; then
  if [ "$FORCE_KEYS" != "1" ]; then
    echo "生成缺失的板端身份密钥，不覆盖已存在完整密钥集"
  else
    echo "强制重新生成板端身份密钥"
    rm -f "$BOARD_KEYS_DIR"/server_sm2_identity.* "$BOARD_KEYS_DIR"/server_mldsa_identity.*
  fi
  OQS_INSTALL_PATH="$BOARD_OQS" \
  LD_LIBRARY_PATH="$BOARD_LD${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
  TONGSUO_SIG_BRIDGE="$BOARD_SIG_BRIDGE" \
  "$BOARD_PYTHON" /home/user/gen_identity_keys.py --dir "$BOARD_KEYS_DIR"
fi
for path in "${need_files[@]}"; do
  test -s "$path"
done
chmod 600 "$BOARD_KEYS_DIR"/*.key
chmod 644 "$BOARD_KEYS_DIR"/*.pub
OQS_INSTALL_PATH="$BOARD_OQS" \
LD_LIBRARY_PATH="$BOARD_LD${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
TONGSUO_SIG_BRIDGE="$BOARD_SIG_BRIDGE" \
"$BOARD_PYTHON" - <<'PY'
from mlkem_link.auth import get_sm2_backend, get_mldsa_backend
for name, fn in (("sm2", get_sm2_backend), ("mldsa", get_mldsa_backend)):
    backend = fn()
    pk, sk = backend.keygen()
    msg = b"board-init-smoke"
    sig = backend.sign(sk, msg)
    assert backend.verify(pk, msg, sig)
    print(f"{name}: {backend.name} ok")
PY
REMOTE

    mkdir -p "$LOCAL_KEYS_DIR"
    board_scp_from "$password" "$BOARD_KEYS_DIR/server_sm2_identity.pub" "$LOCAL_KEYS_DIR/server_sm2_identity.pub"
    board_scp_from "$password" "$BOARD_KEYS_DIR/server_mldsa_identity.pub" "$LOCAL_KEYS_DIR/server_mldsa_identity.pub"
    chmod 644 "$LOCAL_KEYS_DIR"/*.pub
    log "已同步板端公钥到 $LOCAL_KEYS_DIR"

    log "初始化板端运行目录"
    board_ssh "$password" "BOARD_USRP_RX_DIR='$BOARD_USRP_RX_DIR' BOARD_RUN_LOGGER_DIR='$BOARD_RUN_LOGGER_DIR' bash -s" <<'REMOTE'
set -euo pipefail
mkdir -p "$BOARD_USRP_RX_DIR" "$BOARD_RUN_LOGGER_DIR"
chmod 700 "$BOARD_USRP_RX_DIR"
REMOTE
}

write_env_hint() {
    mkdir -p "$AUTH_DIR"
    cat > "$AUTH_DIR/runtime.env.example" <<EOF
# 可 source 后启动 ./start.sh；init.sh --board 会生成 peer/*.pub。
export OQS_INSTALL_PATH=$REPO_ROOT/liboqs/liboqs-dist
export LD_LIBRARY_PATH=$TONGSUO_DIST/lib64:\$OQS_INSTALL_PATH/lib64:\$OQS_INSTALL_PATH/lib:\${LD_LIBRARY_PATH:-}
export TONGSUO_KEM_BRIDGE=$TONGSUO_DIST/lib64/libtongsuo_kem_bridge.so
export TONGSUO_SIG_BRIDGE=$TONGSUO_DIST/lib64/libtongsuo_sig_bridge.so
export MLKEM_LOCAL_TONGSUO_KEM_BRIDGE=$TONGSUO_DIST/lib64/libtongsuo_kem_bridge.so
export MLKEM_LOCAL_LD_LIBRARY_PATH=$TONGSUO_DIST/lib64:\$OQS_INSTALL_PATH/lib64:\$OQS_INSTALL_PATH/lib
export MLKEM_REMOTE_OQS_INSTALL_PATH=$BOARD_OQS
export MLKEM_REMOTE_LD_LIBRARY_PATH=$BOARD_LD
export MLKEM_REMOTE_TONGSUO_KEM_BRIDGE=$BOARD_KEM_BRIDGE
export MLKEM_REMOTE_TONGSUO_SIG_BRIDGE=$BOARD_SIG_BRIDGE
export MLKEM_REMOTE_RUN_LOGGER_DIR=$BOARD_RUN_LOGGER_DIR
export MLKEM_REMOTE_PYTHON=$BOARD_PYTHON
export MLKEM_STATUS_PORT=$BOARD_STATUS_PORT
export MLKEM_AUTH_ENABLED=1
export MLKEM_AUTH_SIG_POLICY=DUAL_REQUIRED
export MLKEM_AUTH_SERVER_ID=phytium-board
export MLKEM_AUTH_PEER_SM2_PUB=$LOCAL_KEYS_DIR/server_sm2_identity.pub
export MLKEM_AUTH_PEER_MLDSA_PUB=$LOCAL_KEYS_DIR/server_mldsa_identity.pub
export MLKEM_AUTH_SERVER_SM2_KEY=$BOARD_KEYS_DIR/server_sm2_identity.key
export MLKEM_AUTH_SERVER_SM2_PUB=$BOARD_KEYS_DIR/server_sm2_identity.pub
export MLKEM_AUTH_SERVER_MLDSA_KEY=$BOARD_KEYS_DIR/server_mldsa_identity.key
export MLKEM_AUTH_SERVER_MLDSA_PUB=$BOARD_KEYS_DIR/server_mldsa_identity.pub
export REMOTE_USRP_RX_DIR=$BOARD_USRP_RX_DIR
export OPENAMP_DEMO_INPUT_SOURCE_MODE=prerecorded
EOF
    log "运行时环境参考已写入 $AUTH_DIR/runtime.env.example"
}

ensure_venv
build_tongsuo
local_smoke
init_board_auth
write_env_hint

log "初始化完成"
