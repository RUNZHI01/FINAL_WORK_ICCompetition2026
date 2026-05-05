import { app, BrowserWindow, dialog } from 'electron'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import {
  getBackendRuntimeConfig,
  startPythonBackend,
  stopPythonBackend,
  type BackendRuntimeConfig,
  type RunningBackend,
} from './pythonManager'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
// WSLg often reports 100% scaling; allow an env override to match host DPI better.
const WSL_SCALE = Number(process.env.WSL_SCALE_FACTOR ?? '1.25')

let mainWindow: BrowserWindow | null = null
let backend: RunningBackend | null = null

function createWindow(runtimeConfig: BackendRuntimeConfig): void {
  mainWindow = new BrowserWindow({
    width: 2560,
    height: 1440,
    show: false,
    backgroundColor: '#F0F4F9',
    webPreferences: {
      // electron-vite 在 type:module 下产出 out/preload/index.mjs
      preload: path.join(__dirname, '../preload/index.mjs'),
      contextIsolation: true,
      sandbox: false,
      additionalArguments: [`--cockpit-backend-url=${runtimeConfig.baseUrl}`],
    },
  })

  mainWindow.on('ready-to-show', () => {
    mainWindow?.webContents.setZoomFactor(WSL_SCALE)
    mainWindow?.show()
    if (!app.isPackaged && process.env.COCKPIT_OPEN_DEVTOOLS === '1') {
      mainWindow?.webContents.openDevTools({ mode: 'right' })
    }
  })

  if (process.env.ELECTRON_RENDERER_URL) {
    void mainWindow.loadURL(process.env.ELECTRON_RENDERER_URL)
  } else {
    mainWindow.loadFile(path.join(__dirname, '../renderer/index.html'))
  }
}

// Disable GPU acceleration for WSL compatibility
app.disableHardwareAcceleration()

app.whenReady().then(() => {
  let runtimeConfig: BackendRuntimeConfig
  try {
    runtimeConfig = getBackendRuntimeConfig()
    backend = startPythonBackend(runtimeConfig)
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    console.error('[cockpit-desktop] backend bootstrap failed:', error)
    dialog.showErrorBox('Cockpit Desktop 启动失败', message)
    app.quit()
    return
  }

  createWindow(runtimeConfig)

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow(runtimeConfig)
    }
  })
})

app.on('before-quit', () => {
  stopPythonBackend(backend)
  backend = null
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})
