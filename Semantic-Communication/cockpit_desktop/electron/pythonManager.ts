import { spawn, spawnSync, type ChildProcess } from 'node:child_process'
import { existsSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const SERVER_RELATIVE_PATH = path.join(
  'session_bootstrap',
  'demo',
  'openamp_control_plane_demo',
  'server.py',
)
const DEFAULT_BACKEND_HOST = '127.0.0.1'
const DEFAULT_BACKEND_PORT = 8079
const DEFAULT_AIRCRAFT_POSITION_ENV_RELATIVE_PATH = path.join(
  'session_bootstrap',
  'tmp',
  'aircraft_position_baidu_ip.local.env',
)

export type BackendOptions = {
  host?: string
  port?: number
}

export type BackendRuntimeConfig = {
  host: string
  port: number
  baseUrl: string
  skipPython: boolean
  aircraftPositionEnv?: string
  pythonCommand?: string
  repoRoot?: string
  serverScript?: string
  cwd?: string
}

export type RunningBackend = {
  process: ChildProcess
  config: BackendRuntimeConfig
}

function parsePort(rawPort: string | undefined, fallback: number): number {
  const trimmed = rawPort?.trim()
  if (!trimmed) {
    return fallback
  }
  const parsed = Number(trimmed)
  if (!Number.isInteger(parsed) || parsed < 1 || parsed > 65535) {
    throw new Error(`无效的后端端口: ${trimmed}`)
  }
  return parsed
}

function walkAncestors(seed: string, maxDepth = 6): string[] {
  const candidates: string[] = []
  let current = path.resolve(seed)
  for (let depth = 0; depth <= maxDepth; depth += 1) {
    candidates.push(current)
    const parent = path.dirname(current)
    if (parent === current) {
      break
    }
    current = parent
  }
  return candidates
}

function uniquePaths(values: string[]): string[] {
  const seen = new Set<string>()
  const unique: string[] = []
  for (const value of values) {
    const resolved = path.resolve(value)
    if (seen.has(resolved)) {
      continue
    }
    seen.add(resolved)
    unique.push(resolved)
  }
  return unique
}

function resolveServerScriptFromRepoRoot(repoRoot: string): string {
  return path.join(repoRoot, SERVER_RELATIVE_PATH)
}

function resolveAircraftPositionEnv(repoRoot: string): string | undefined {
  const requested = process.env.COCKPIT_AIRCRAFT_POSITION_ENV?.trim()
  if (requested) {
    const resolved = path.resolve(requested)
    if (!existsSync(resolved)) {
      throw new Error(`COCKPIT_AIRCRAFT_POSITION_ENV 指向的文件不存在: ${resolved}`)
    }
    return resolved
  }

  const defaultPath = path.join(repoRoot, DEFAULT_AIRCRAFT_POSITION_ENV_RELATIVE_PATH)
  if (existsSync(defaultPath)) {
    return defaultPath
  }
  return undefined
}

function resolveServerLocation(): { repoRoot: string; serverScript: string; cwd: string } {
  const envServerScript = process.env.COCKPIT_SERVER_SCRIPT?.trim()
  if (envServerScript) {
    const serverScript = path.resolve(envServerScript)
    if (!existsSync(serverScript)) {
      throw new Error(`COCKPIT_SERVER_SCRIPT 指向的文件不存在: ${serverScript}`)
    }
    return {
      repoRoot: path.resolve(path.dirname(serverScript), '../../..'),
      serverScript,
      cwd: path.dirname(serverScript),
    }
  }

  const repoRootSeeds = uniquePaths(
    [
      process.env.COCKPIT_REPO_ROOT?.trim(),
      process.cwd(),
      path.resolve(__dirname, '../../..'),
      path.resolve(__dirname, '../..'),
    ]
      .filter(Boolean)
      .flatMap((seed) => walkAncestors(String(seed))),
  )

  for (const repoRoot of repoRootSeeds) {
    const serverScript = resolveServerScriptFromRepoRoot(repoRoot)
    if (existsSync(serverScript)) {
      return {
        repoRoot,
        serverScript,
        cwd: path.dirname(serverScript),
      }
    }
  }

  throw new Error(
    '找不到 Python 后端脚本（未找到 session_bootstrap/demo/openamp_control_plane_demo/server.py）。' +
      '请确保运行的是完整仓库，或设置 COCKPIT_REPO_ROOT / COCKPIT_SERVER_SCRIPT。',
  )
}

function resolvePythonCommand(): string {
  const requested = process.env.COCKPIT_PYTHON?.trim()
  const candidates = requested
    ? [requested]
    : process.platform === 'win32'
      ? ['py', 'python', 'python3']
      : ['python3', 'python']

  for (const candidate of candidates) {
    const args =
      candidate === 'py'
        ? ['-3', '-c', 'import sys; print(sys.executable)']
        : ['-c', 'import sys; print(sys.executable)']
    const result = spawnSync(candidate, args, {
      encoding: 'utf-8',
      stdio: ['ignore', 'pipe', 'pipe'],
    })
    if (!result.error && result.status === 0) {
      return candidate
    }
  }

  throw new Error(
    '找不到可用的 Python 解释器。请安装 python3，或设置环境变量 COCKPIT_PYTHON 指向可执行文件。',
  )
}

export function getBackendRuntimeConfig(options: BackendOptions = {}): BackendRuntimeConfig {
  const host = options.host ?? process.env.COCKPIT_BACKEND_HOST ?? DEFAULT_BACKEND_HOST
  const port = options.port ?? parsePort(process.env.COCKPIT_BACKEND_PORT, DEFAULT_BACKEND_PORT)
  const baseUrl = `http://${host}:${port}`
  const skipPython = process.env.COCKPIT_SKIP_PYTHON === '1'

  if (skipPython) {
    return {
      host,
      port,
      baseUrl,
      skipPython,
    }
  }

  const { repoRoot, serverScript, cwd } = resolveServerLocation()
  const pythonCommand = resolvePythonCommand()
  const aircraftPositionEnv = resolveAircraftPositionEnv(repoRoot)

  return {
    host,
    port,
    baseUrl,
    skipPython,
    aircraftPositionEnv,
    pythonCommand,
    repoRoot,
    serverScript,
    cwd,
  }
}

export function startPythonBackend(runtimeConfig: BackendRuntimeConfig): RunningBackend | null {
  if (runtimeConfig.skipPython) {
    console.warn('[cockpit-desktop] COCKPIT_SKIP_PYTHON=1，跳过启动 Python 后端')
    return null
  }

  const args = [
    runtimeConfig.serverScript as string,
    '--host',
    runtimeConfig.host,
    '--port',
    String(runtimeConfig.port),
  ]
  if (runtimeConfig.aircraftPositionEnv) {
    args.push('--aircraft-position-env', runtimeConfig.aircraftPositionEnv)
  }

  const child = spawn(
    runtimeConfig.pythonCommand as string,
    args,
    {
      cwd: runtimeConfig.cwd,
      stdio: 'inherit',
      env: { ...process.env },
    },
  )

  child.on('error', (err) => {
    console.error('[cockpit-desktop] Python 后端进程 error:', err)
  })

  return {
    process: child,
    config: runtimeConfig,
  }
}

export function stopPythonBackend(backend: RunningBackend | null): void {
  if (!backend?.process || backend.process.killed) {
    return
  }
  backend.process.kill('SIGTERM')
}
