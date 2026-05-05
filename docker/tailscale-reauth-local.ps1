[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"

$containerName = "iccomp-tailscale-reauth-{0}" -f (Get-Date -Format "HHmmss")

Write-Host "Starting Tailscale forced re-auth container: $containerName"
Write-Host "Open the printed login URL and select the correct Tailscale account."
Write-Host ""

docker run --rm -it --name $containerName `
  --cap-add=NET_ADMIN `
  --cap-add=NET_RAW `
  --device=/dev/net/tun `
  -v "iccomp-tailscale-state:/var/lib/tailscale" `
  iccomp-ubuntu-minimal `
  bash -lc @'
set -euo pipefail
mkdir -p /var/run/tailscale
tailscaled \
  --socket=/var/run/tailscale/tailscaled.sock \
  --state=/var/lib/tailscale/tailscaled.state \
  --tun=tailscale0 \
  >/tmp/tailscaled-reauth.log 2>&1 &

for i in $(seq 1 30); do
  if tailscale --socket=/var/run/tailscale/tailscaled.sock version >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

echo "Clearing the previous Tailscale login in this Docker volume..."
tailscale --socket=/var/run/tailscale/tailscaled.sock logout >/dev/null 2>&1 || true

echo
echo "Starting Tailscale login. Open the URL printed below:"
tailscale --socket=/var/run/tailscale/tailscaled.sock up \
  --hostname=iccomp-demo \
  --accept-dns=false \
  --accept-routes=true

echo
echo "Tailscale status after login:"
tailscale --socket=/var/run/tailscale/tailscaled.sock status
echo
echo "Done. You can close this window."
read -r -p "Press Enter to close..." _
'@
