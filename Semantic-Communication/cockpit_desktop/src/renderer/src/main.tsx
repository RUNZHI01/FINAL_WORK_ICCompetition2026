import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ConfigProvider } from 'antd'
import App from './App'
import { registerCockpitEChartsTheme } from './theme/echarts-theme'
import { antdThemeConfig } from './theme/antdTheme'
import { injectCSSVariables } from './theme/cssVariables'

import './styles/fonts.css'
import './index.css'

registerCockpitEChartsTheme()
injectCSSVariables()

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5_000,
    },
  },
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <ConfigProvider theme={antdThemeConfig}>
        <App />
      </ConfigProvider>
    </QueryClientProvider>
  </React.StrictMode>,
)
