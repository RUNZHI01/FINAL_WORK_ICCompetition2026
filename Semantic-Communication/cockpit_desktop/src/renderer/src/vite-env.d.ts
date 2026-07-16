/// <reference types="vite/client" />

export type CockpitPreload = {
  platform: NodeJS.Platform
  backendUrl: string
  openExternal: (url: string) => Promise<void>
}

declare global {
  interface Window {
    cockpit?: CockpitPreload
  }
}

export {}
