$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ImageName = if ($env:IMAGE_NAME) { $env:IMAGE_NAME } else { "iccomp-ubuntu-minimal" }
$RemoteHost = if ($env:REMOTE_HOST) { $env:REMOTE_HOST } elseif ($env:PHYTIUM_PI_HOST) { $env:PHYTIUM_PI_HOST } else { "100.121.87.73" }
$RemoteUser = if ($env:REMOTE_USER) { $env:REMOTE_USER } elseif ($env:PHYTIUM_PI_USER) { $env:PHYTIUM_PI_USER } else { "user" }
$RemotePass = if ($env:REMOTE_PASS) { $env:REMOTE_PASS } elseif ($env:PHYTIUM_PI_PASSWORD) { $env:PHYTIUM_PI_PASSWORD } else { "" }
$StateVolume = if ($env:TAILSCALE_STATE_VOLUME) { $env:TAILSCALE_STATE_VOLUME } else { "iccomp-tailscale-state" }
$PingTarget = if ($env:TAILSCALE_PING_TARGET) { $env:TAILSCALE_PING_TARGET } else { $RemoteHost }
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = (Resolve-Path (Join-Path $ScriptDir "..")).Path
$OutDir = if ($env:OUT_DIR) { $env:OUT_DIR } else { Join-Path $ProjectRoot "board_deps" }

if (-not $RemotePass) {
    throw "Set REMOTE_PASS or PHYTIUM_PI_PASSWORD before pulling board dependencies."
}

docker image inspect "$ImageName" *> $null
if ($LASTEXITCODE -ne 0) {
    docker build `
        -f "$ProjectRoot/docker/ubuntu-minimal.Dockerfile" `
        -t "$ImageName" `
        "$ProjectRoot"
    if ($LASTEXITCODE -ne 0) {
        throw "docker build failed"
    }
}

New-Item -ItemType Directory -Force -Path "$OutDir" | Out-Null

$PullScript = @'
set -euo pipefail
bash /workspace/docker/start-tailscale.sh >/tmp/tailscale-start.log 2>&1
mkdir -p \
  /out/crypto/public_keys \
  /out/tvm/baseline \
  /out/tvm/current \
  /out/tvm/current_legacy \
  /out/tvm/runtime \
  /out/mnn/origin \
  /out/inputs \
  /out/tools \
  /out/openamp/firmware \
  /out/openamp/source \
  /out/openamp/runtime \
  /out/runtime
ssh_common=(sshpass -e ssh -n -o StrictHostKeyChecking=no -o UserKnownHostsFile=/tmp/known_hosts -o ConnectTimeout=20 -o ServerAliveInterval=5 -o ServerAliveCountMax=2 "${REMOTE_USER}@${REMOTE_HOST}")
fetch_stream() {
  local label="$1"
  local remote_cmd="$2"
  local out_file="$3"
  local tmp_file="${out_file}.tmp"
  printf '[board-deps] fetching %s -> %s\n' "$label" "$out_file"
  for attempt in 1 2 3; do
    if "${ssh_common[@]}" "$remote_cmd" > "$tmp_file" && test -s "$tmp_file"; then
      mv "$tmp_file" "$out_file"
      return 0
    fi
    rm -f "$tmp_file"
    printf '[board-deps] retry %s/3 for %s\n' "$attempt" "$label" >&2
    sleep $((attempt * 3))
  done
  printf '[board-deps] failed to fetch %s\n' "$label" >&2
  return 1
}
split_large_file() {
  local file="$1"
  local prefix="${file}.part-"
  if [ -s "$file" ]; then
    rm -f "${prefix}"*
    split -b 90m -d -a 2 "$file" "$prefix"
    rm -f "$file"
  fi
}
fetch_stream "liboqs runtime" "tar -C /home/user -czf - liboqs-dist" "/out/crypto/liboqs-dist-aarch64.tar.gz"
fetch_stream "tongsuo runtime" "tar -C /usr/local -czf - tongsuo" "/out/crypto/tongsuo-runtime-aarch64.tar.gz"
fetch_stream "tongsuo sig bridge" "cat /home/user/libtongsuo_sig_bridge.so" "/out/crypto/libtongsuo_sig_bridge.so"
fetch_stream "TVM baseline optimized_model.so" "p=\$(find /home/user/Downloads -path '*/tvm_tune_logs/optimized_model.so' | grep '/5\\.1TVM' | head -n1); test -n \"\$p\"; cat \"\$p\"" "/out/tvm/baseline/optimized_model.so"
fetch_stream "TVM current optimized_model.so" "cat '/home/user/Downloads/jscc-test/jscc_opus_final_mean4_v7_20260406/tvm_tune_logs/optimized_model.so'" "/out/tvm/current/optimized_model.so"
fetch_stream "TVM legacy current optimized_model.so" "cat '/home/user/Downloads/jscc-test/jscc/tvm_tune_logs/optimized_model.so'" "/out/tvm/current_legacy/optimized_model.so"
fetch_stream "TVM board runtime" "tar -C / -czf - --exclude='**/__pycache__' --exclude='*.pyc' home/user/anaconda3/envs/tvm310_safe/lib/python3.10/site-packages/tvm_ffi home/user/tvm_samegen_safe_20260309/build/lib home/user/tvm_samegen_safe_20260309/build/libtvm_runtime.so home/user/tvm_samegen_safe_20260309/build/libtvm.so home/user/tvm_samegen_20260307/python" "/out/tvm/runtime/tvm310-safe-runtime-aarch64.tar.gz"
fetch_stream "MNN FP32 model" "cat '/home/user/Downloads/MNNversion/origin/model1.mnn'" "/out/mnn/origin/model1.mnn"
fetch_stream "Places365 latent inputs" "d=\$(find /home/user/Downloads/jscc-test -maxdepth 1 -type d -name '*latent' | head -n1); test -n \"\$d\"; tar -C /home/user/Downloads/jscc-test -czf - \"\$(basename \"\$d\")\"" "/out/inputs/places365-latents.tar.gz"
fetch_stream "MNN encoder outputs" "tar -C '/home/user/Downloads/jscc-test' -czf - encoder_outputs" "/out/inputs/mnn-encoder-outputs.tar.gz"
fetch_stream "identity key generator" "cat /home/user/gen_identity_keys.py" "/out/tools/gen_identity_keys.py"
fetch_stream "current OpenAMP firmware ELF" "cat /lib/firmware/openamp_core0.elf" "/out/openamp/firmware/openamp_core0.elf"
fetch_stream "current OpenAMP DTB" "cat /boot/phytium-pi-board-v3-openamp.dtb" "/out/openamp/firmware/phytium-pi-board-v3-openamp.dtb"
fetch_stream "OpenAMP full source" "tar -C /home/user/phytium-dev -czf - --exclude='**/build' --exclude='**/__pycache__' --exclude='*.pyc' --exclude='*.o' --exclude='*.a' --exclude='*.elf' --exclude='*.map' release_v1.4.0-jobdone-v14" "/out/openamp/source/release_v1.4.0-jobdone-v14-openamp-source.tar.gz"
fetch_stream "OpenAMP current build metadata" "BASE=/home/user/phytium-dev/release_v1.4.0-jobdone-v14/example/system/amp/openamp_for_linux; tar -C \"\$BASE\" -czf - phytiumpi_aarch64_firefly_openamp_core0.elf phytiumpi_aarch64_firefly_openamp_core0.map sdkconfig sdkconfig.h configs common inc src/slaver_00_example.c main.c makefile Kconfig ft_openamp.ld README.md" "/out/openamp/source/release_v1.4.0-jobdone-v14-openamp-build-artifacts.tar.gz"
fetch_stream "OpenAMP runtime services" "tar -C /home/user -czf - --exclude='.openamp-demo/board_position_api_service/*.log' --exclude='*/__pycache__' .openamp-demo/board_position_api_service" "/out/openamp/runtime/openamp-demo-runtime-services.tar.gz"
fetch_stream "board public auth keys" "tar -C /home/user/keys -czf - server_sm2_identity.pub server_mldsa_identity.pub .gitignore" "/out/crypto/public_keys/board-auth-public-keys.tar.gz"
fetch_stream "board ML-KEM remote runtime snapshot" "tar -C /home/user -czf - --exclude='*/__pycache__' --exclude='*.pyc' --exclude='*.tmp' tcp_server.py tvm_inference_helper.py artifact_guard.py latent_transport.py replay_guard.py run_logger.py gen_identity_keys.py mlkem_link" "/out/runtime/mlkem-remote-runtime-snapshot.tar.gz"
split_large_file "/out/openamp/source/release_v1.4.0-jobdone-v14-openamp-source.tar.gz"
(
  cd /out
  find . -type f ! -name SHA256SUMS ! -name FILES.txt -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
  find . -type f ! -name SHA256SUMS ! -name FILES.txt -printf '%p\t%s bytes\n' | sort > FILES.txt
)
echo "[board-deps] done"
'@

$PullScript = $PullScript.Replace("`r`n", "`n")
$ScriptB64 = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($PullScript))

docker run --rm `
    --cap-add=NET_ADMIN `
    --cap-add=NET_RAW `
    --device=/dev/net/tun `
    -v "${StateVolume}:/var/lib/tailscale" `
    -v "${ProjectRoot}:/workspace:ro" `
    -v "${OutDir}:/out" `
    -e "TAILSCALE_PING_TARGET=$PingTarget" `
    -e "TS_LOGIN_WAIT_SEC=8" `
    -e "REMOTE_HOST=$RemoteHost" `
    -e "REMOTE_USER=$RemoteUser" `
    -e "SSHPASS=$RemotePass" `
    -e "LOCAL_SCRIPT_B64=$ScriptB64" `
    "$ImageName" `
    bash -lc 'printf "%s" "$LOCAL_SCRIPT_B64" | base64 -d | bash'

if ($LASTEXITCODE -ne 0) {
    throw "pull-board-deps failed"
}
