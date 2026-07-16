param(
  [string]$BoardHost = $(if ($env:REMOTE_HOST) { $env:REMOTE_HOST } else { "100.121.87.73" }),
  [string]$BoardUser = $(if ($env:REMOTE_USER) { $env:REMOTE_USER } else { "user" }),
  [string]$BoardPassword = $(if ($env:REMOTE_PASS) { $env:REMOTE_PASS } else { "user" }),
  [ValidateSet("usrp-tvm", "prerecorded-tvm", "usrp-rx", "custom")]
  [string]$Mode = "usrp-tvm",
  [string]$RemotePath = "",
  [string]$DestinationRoot = "",
  [string]$DockerImage = $(if ($env:ICCOMP_DOCKER_IMAGE) { $env:ICCOMP_DOCKER_IMAGE } else { "iccomp-usrp-tx:latest" }),
  [switch]$ListOnly,
  [switch]$NoOpen,
  [switch]$Serve,
  [int]$Port = 8765
)

$ErrorActionPreference = "Stop"

function Get-RepoRoot {
  return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Quote-Sh {
  param([Parameter(Mandatory = $true)][string]$Value)
  if ($Value.Contains("'")) {
    throw "Single quotes are not supported in shell-quoted values: $Value"
  }
  return "'$Value'"
}

function ConvertTo-DockerPath {
  param([Parameter(Mandatory = $true)][string]$Path)
  $full = [System.IO.Path]::GetFullPath($Path)
  $root = [System.IO.Path]::GetPathRoot($full)
  if (-not $root -or $root.Length -lt 2) {
    throw "Only absolute Windows drive paths are supported: $Path"
  }
  $drive = $root.Substring(0, 1).ToLowerInvariant()
  $rest = $full.Substring($root.Length).Replace("\", "/")
  if ($rest) {
    return "/host/$drive/$rest"
  }
  return "/host/$drive"
}

function Get-DockerDriveMount {
  param([Parameter(Mandatory = $true)][string]$Path)
  $full = [System.IO.Path]::GetFullPath($Path)
  $root = [System.IO.Path]::GetPathRoot($full)
  $drive = $root.Substring(0, 1).ToLowerInvariant()
  return @("-v", "${root}:/host/$drive")
}

function Invoke-DockerCapture {
  param([Parameter(Mandatory = $true)][string[]]$DockerArgs)
  $output = & docker @DockerArgs 2>&1
  $code = $LASTEXITCODE
  if ($code -ne 0) {
    throw (($output | ForEach-Object { "$_" }) -join [Environment]::NewLine)
  }
  return @($output | ForEach-Object { "$_" })
}

function Invoke-BoardSshCapture {
  param([Parameter(Mandatory = $true)][string]$RemoteCommand)
  $target = "${BoardUser}@${BoardHost}"
  $args = @(
    "run", "--rm",
    "-e", "SSHPASS=$BoardPassword",
    $DockerImage,
    "sshpass", "-e", "ssh",
    "-o", "StrictHostKeyChecking=no",
    "-o", "UserKnownHostsFile=/dev/null",
    "-o", "LogLevel=ERROR",
    "-o", "ConnectTimeout=8",
    $target,
    $RemoteCommand
  )
  return Invoke-DockerCapture -DockerArgs $args
}

function Resolve-RemotePath {
  if ($RemotePath.Trim()) {
    return $RemotePath.Trim()
  }
  switch ($Mode) {
    "usrp-tvm" {
      $cmd = "ls -td /home/user/Downloads/jscc-test-usrp/tvm/openamp3_usrp_*_current/reconstructions 2>/dev/null | head -1"
    }
    "prerecorded-tvm" {
      $cmd = "printf '%s\n' /home/user/Downloads/jscc-test/jscc/infer_outputs/openamp3_handwritten_mean4_v7_big_little_current/reconstructions"
    }
    "usrp-rx" {
      $cmd = "ls -td /home/user/cockpit_usrp_rx/cockpit_usrp*_rx 2>/dev/null | head -1"
    }
    default {
      throw "Mode custom requires -RemotePath."
    }
  }
  $lines = Invoke-BoardSshCapture -RemoteCommand $cmd
  $resolved = ($lines | Where-Object { $_.Trim() } | Select-Object -Last 1).Trim()
  if (-not $resolved) {
    throw "No board path found for mode '$Mode'."
  }
  return $resolved
}

function New-GalleryIndex {
  param(
    [Parameter(Mandatory = $true)][string]$Root,
    [Parameter(Mandatory = $true)][string]$RemoteSource
  )
  $imageExts = @(".png", ".jpg", ".jpeg", ".bmp", ".webp")
  $images = @(Get-ChildItem -Path $Root -Recurse -File | Where-Object {
      $imageExts -contains $_.Extension.ToLowerInvariant()
    } | Sort-Object FullName)
  $items = foreach ($img in $images) {
    $rel = [System.IO.Path]::GetRelativePath($Root, $img.FullName).Replace("\", "/")
    $href = [Uri]::EscapeUriString($rel)
    @"
      <a class="card" href="$href" target="_blank">
        <img src="$href" loading="lazy" alt="$rel" />
        <span>$rel</span>
      </a>
"@
  }
  $generatedAt = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
  $html = @"
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Board Image Gallery</title>
  <style>
    body { margin: 0; font-family: Segoe UI, Arial, sans-serif; background: #f7f8fa; color: #1f2937; }
    header { position: sticky; top: 0; background: #ffffff; border-bottom: 1px solid #d7dce2; padding: 12px 18px; z-index: 1; }
    h1 { font-size: 18px; margin: 0 0 4px; }
    .meta { font-size: 12px; color: #5f6b7a; line-height: 1.5; }
    main { padding: 16px; display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); gap: 12px; }
    .card { display: block; text-decoration: none; color: inherit; background: #fff; border: 1px solid #d7dce2; border-radius: 6px; overflow: hidden; }
    .card img { width: 100%; aspect-ratio: 1 / 1; object-fit: contain; background: #111827; display: block; }
    .card span { display: block; padding: 8px; font-size: 11px; color: #475569; overflow-wrap: anywhere; }
    .empty { padding: 24px; color: #7b8794; }
  </style>
</head>
<body>
  <header>
    <h1>Board Image Gallery</h1>
    <div class="meta">Source: $RemoteSource</div>
    <div class="meta">Generated: $generatedAt | Images: $($images.Count)</div>
  </header>
  <main>
    $(if ($items) { $items -join [Environment]::NewLine } else { '<div class="empty">No images found in pulled files.</div>' })
  </main>
</body>
</html>
"@
  $indexPath = Join-Path $Root "index.html"
  Set-Content -Path $indexPath -Value $html -Encoding UTF8
  return @{ Path = $indexPath; ImageCount = $images.Count }
}

$repoRoot = Get-RepoRoot
if (-not $DestinationRoot.Trim()) {
  $DestinationRoot = Join-Path $repoRoot "artifacts\board_images"
}
$DestinationRoot = [System.IO.Path]::GetFullPath($DestinationRoot)

$remote = Resolve-RemotePath
Write-Host "Board source: $remote"
if ($ListOnly) {
  return
}

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$remoteLeaf = Split-Path -Leaf $remote
$remoteParentLeaf = Split-Path -Leaf (Split-Path -Parent $remote)
$namePart = if ($remoteLeaf -eq "reconstructions" -and $remoteParentLeaf) { $remoteParentLeaf } else { $remoteLeaf }
$safeName = ($namePart -replace '[^A-Za-z0-9_.-]', '_')
$dest = Join-Path $DestinationRoot "${stamp}_${Mode}_${safeName}"
New-Item -ItemType Directory -Force -Path $dest | Out-Null

$dockerDest = ConvertTo-DockerPath $dest
$mountArgs = Get-DockerDriveMount $dest
$remoteSpec = "${BoardUser}@${BoardHost}:$remote"
$copyScript = @"
set -e
mkdir -p $(Quote-Sh $dockerDest)
sshpass -e scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -o ConnectTimeout=8 -r $(Quote-Sh $remoteSpec) $(Quote-Sh $dockerDest)/
"@

$dockerArgs = @(
  "run", "--rm",
  "-e", "SSHPASS=$BoardPassword"
) + $mountArgs + @(
  $DockerImage,
  "sh", "-lc", $copyScript.Replace("`r", "")
)

Invoke-DockerCapture -DockerArgs $dockerArgs | Out-Null

$gallery = New-GalleryIndex -Root $dest -RemoteSource $remote
Write-Host "Pulled to: $dest"
Write-Host "Images: $($gallery.ImageCount)"
Write-Host "Gallery: $($gallery.Path)"

if ($Serve) {
  $python = Get-Command python -ErrorAction SilentlyContinue
  if (-not $python) {
    $python = Get-Command py -ErrorAction SilentlyContinue
  }
  if (-not $python) {
    throw "Python was not found; rerun without -Serve or install Python."
  }
  $args = if ($python.Name -eq "py.exe" -or $python.Name -eq "py") {
    @("-m", "http.server", "$Port", "--directory", $dest)
  } else {
    @("-m", "http.server", "$Port", "--directory", $dest)
  }
  Start-Process -FilePath $python.Source -ArgumentList $args -WindowStyle Hidden | Out-Null
  $url = "http://127.0.0.1:$Port/index.html"
  Write-Host "Serving: $url"
  if (-not $NoOpen) {
    Start-Process $url | Out-Null
  }
} elseif (-not $NoOpen) {
  if ($gallery.ImageCount -gt 0) {
    Invoke-Item $gallery.Path
  } else {
    Invoke-Item $dest
  }
}
