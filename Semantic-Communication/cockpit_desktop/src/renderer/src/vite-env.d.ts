/// <reference types="vite/client" />

export type CockpitPreload = {
  platform: NodeJS.Platform
  backendUrl: string
}

declare global {
  interface Window {
    cockpit?: CockpitPreload
  }
}

export {}
