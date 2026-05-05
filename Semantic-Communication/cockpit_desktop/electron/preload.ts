import { contextBridge } from 'electron'

function readArgument(prefix: string): string {
  const match = process.argv.find((arg) => arg.startsWith(prefix))
  return match ? match.slice(prefix.length) : ''
}

const backendUrl =
  readArgument('--cockpit-backend-url=') ||
  process.env.COCKPIT_BACKEND_URL ||
  `http://${process.env.COCKPIT_BACKEND_HOST ?? '127.0.0.1'}:${process.env.COCKPIT_BACKEND_PORT ?? '8079'}`

contextBridge.exposeInMainWorld('cockpit', {
  platform: process.platform,
  backendUrl,
})
