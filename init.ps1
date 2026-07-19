param(
    [switch]$CheckOnly,
    [switch]$ForceNodeInstall,
    [switch]$ForceDockerBuild
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ProjectRoot = (Resolve-Path $PSScriptRoot).Path
$VenvDir = Join-Path $ProjectRoot ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$CockpitDir = Join-Path $ProjectRoot "Semantic-Communication\cockpit_desktop"
$NodeModulesMarker = Join-Path $CockpitDir "node_modules\.bin\electron-vite"
$DockerImage = "iccomp-usrp-tx:latest"
$SampleLatentArchive = Join-Path $ProjectRoot "board_deps\inputs\places365-latents.tar.gz"
$SampleLatentDir = Join-Path $ProjectRoot "host_pic_to_latent\encoder_outputs"
$LatentCandidates = @(
    (Join-Path $ProjectRoot "Semantic-Communication\session_bootstrap\tmp\pytorch_board_runtime_20260717\showcase_usrp_final_300"),
    (Join-Path $ProjectRoot "host_pic_to_latent\encoder_outputs_top300"),
    $SampleLatentDir
)

function Write-Step {
    param([Parameter(Mandatory = $true)][string]$Message)
    Write-Host "[init] $Message"
}

function Assert-Command {
    param([Parameter(Mandatory = $true)][string]$Name)
    $Command = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $Command) {
        throw "缺少命令：$Name"
    }
    return $Command.Source
}

function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [string[]]$Arguments = @(),
        [Parameter(Mandatory = $true)][string]$Step
    )
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Step 失败，退出码 $LASTEXITCODE"
    }
}

function Resolve-PythonLauncher {
    $Py = Get-Command "py" -ErrorAction SilentlyContinue
    if ($Py) {
        & $Py.Source -3 -c "import sys; print(sys.executable)" *> $null
        if ($LASTEXITCODE -eq 0) {
            return [pscustomobject]@{
                Command = $Py.Source
                Prefix = @("-3")
            }
        }
    }

    $Python = Get-Command "python" -ErrorAction SilentlyContinue
    if ($Python) {
        & $Python.Source -c "import sys; print(sys.executable)" *> $null
        if ($LASTEXITCODE -eq 0) {
            return [pscustomobject]@{
                Command = $Python.Source
                Prefix = @()
            }
        }
    }

    throw "缺少 Python 3。"
}

function Assert-DockerReady {
    $Docker = Assert-Command "docker"
    & $Docker info *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker 服务未就绪，请先启动 Docker Desktop。"
    }
    return $Docker
}

function Test-DockerImage {
    param(
        [Parameter(Mandatory = $true)][string]$Docker,
        [Parameter(Mandatory = $true)][string]$Image
    )
    & $Docker image inspect $Image *> $null
    return $LASTEXITCODE -eq 0
}

function Get-AvailableLatentCount {
    foreach ($Candidate in $LatentCandidates) {
        if (-not (Test-Path -LiteralPath $Candidate -PathType Container)) {
            continue
        }
        $Count = @(
            Get-ChildItem -LiteralPath $Candidate -File -ErrorAction SilentlyContinue |
                Where-Object { $_.Extension -in @(".pt", ".npz", ".npy") }
        ).Count
        if ($Count -gt 0) {
            return $Count
        }
    }
    return 0
}

function Test-PythonModule {
    param(
        [Parameter(Mandatory = $true)][string]$Python,
        [Parameter(Mandatory = $true)][string]$Module
    )
    & $Python -c "import $Module" *> $null
    return $LASTEXITCODE -eq 0
}

function Assert-CheckoutReady {
    param([Parameter(Mandatory = $true)][string]$Docker)

    $Missing = @()
    if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) {
        $Missing += ".venv\Scripts\python.exe"
    }
    if (-not (Test-Path -LiteralPath $NodeModulesMarker -PathType Leaf)) {
        $Missing += "Semantic-Communication\cockpit_desktop\node_modules"
    }
    if (-not (Test-DockerImage -Docker $Docker -Image $DockerImage)) {
        $Missing += "Docker image $DockerImage"
    }
    if ((Get-AvailableLatentCount) -lt 20) {
        $Missing += "至少 20 个上位机 latent 输入"
    }
    if ($Missing.Count -gt 0) {
        throw "初始化尚未完成：`n- $($Missing -join "`n- ")`n请运行 .\init.ps1"
    }
}

Write-Step "检查本机工具"
$null = Assert-Command "git"
$null = Assert-Command "node"
$Npm = Assert-Command "npm"
$Tar = Assert-Command "tar"
$Python = Resolve-PythonLauncher
$Docker = Assert-DockerReady

if ($CheckOnly) {
    Assert-CheckoutReady -Docker $Docker
    Write-Step "本机初始化检查通过"
    exit 0
}

if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) {
    Write-Step "创建 Python 虚拟环境"
    Invoke-Native `
        -Command $Python.Command `
        -Arguments ($Python.Prefix + @("-m", "venv", "--system-site-packages", $VenvDir)) `
        -Step "创建 Python 虚拟环境"
}

Write-Step "安装 Python 依赖"
Invoke-Native `
    -Command $VenvPython `
    -Arguments @("-m", "pip", "install", "--disable-pip-version-check", "-r", (Join-Path $ProjectRoot "requirements.txt")) `
    -Step "安装 Python 依赖"

if (-not (Test-PythonModule -Python $VenvPython -Module "torch")) {
    Write-Step "安装读取 .pt latent 所需的 CPU 版 PyTorch"
    Invoke-Native `
        -Command $VenvPython `
        -Arguments @("-m", "pip", "install", "--index-url", "https://download.pytorch.org/whl/cpu", "torch") `
        -Step "安装 PyTorch"
}

if ((Get-AvailableLatentCount) -lt 20) {
    if (-not (Test-Path -LiteralPath $SampleLatentArchive -PathType Leaf)) {
        throw "缺少随仓库提供的输入包：$SampleLatentArchive"
    }
    Write-Step "解出上位机示例 latent"
    New-Item -ItemType Directory -Force -Path $SampleLatentDir *> $null
    Invoke-Native `
        -Command $Tar `
        -Arguments @("-xzf", $SampleLatentArchive, "-C", $SampleLatentDir, "--strip-components=1") `
        -Step "解出示例 latent"
    if ((Get-AvailableLatentCount) -lt 20) {
        throw "示例 latent 解压后不足 20 个。"
    }
}

if ($ForceNodeInstall -or -not (Test-Path -LiteralPath $NodeModulesMarker -PathType Leaf)) {
    Write-Step "安装 Cockpit 前端依赖"
    Push-Location $CockpitDir
    try {
        Invoke-Native -Command $Npm -Arguments @("ci") -Step "npm ci"
    }
    catch {
        throw "Cockpit 前端依赖安装失败。若 Electron 正在运行，请先关闭 Cockpit 再重试。`n$($_.Exception.Message)"
    }
    finally {
        Pop-Location
    }
}
else {
    Write-Step "复用已有 Cockpit 前端依赖"
}

$ImageExists = Test-DockerImage -Docker $Docker -Image $DockerImage
if ($ForceDockerBuild -or -not $ImageExists) {
    Write-Step "构建 Docker 镜像 $DockerImage；首次构建耗时较长"
    Invoke-Native `
        -Command $Docker `
        -Arguments @(
            "build",
            "-f", (Join-Path $ProjectRoot "docker\ubuntu-minimal.Dockerfile"),
            "-t", $DockerImage,
            "-t", "iccomp-ubuntu-minimal:latest",
            $ProjectRoot
        ) `
        -Step "构建 Docker 镜像"
}
else {
    Write-Step "复用已有 Docker 镜像 $DockerImage"
}

Write-Step "检查 Python 环境"
Invoke-Native `
    -Command $VenvPython `
    -Arguments @("-c", "import cryptography, numpy, PIL, torch; print('python-deps-ok')") `
    -Step "Python 依赖检查"

Write-Step "检查 Docker 环境"
Invoke-Native `
    -Command $Docker `
    -Arguments @("run", "--rm", $DockerImage, "python", "docker/check_deps.py") `
    -Step "Docker 依赖检查"

Assert-CheckoutReady -Docker $Docker
Write-Step "初始化完成。日常启动请运行 .\Semantic-Communication\cockpit_desktop\start-demo.ps1"
