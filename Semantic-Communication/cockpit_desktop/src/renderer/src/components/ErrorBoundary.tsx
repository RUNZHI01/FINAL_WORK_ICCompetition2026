import { Component, ErrorInfo, ReactNode } from 'react'
import { Button, Result } from 'antd'
import { T } from '../theme/tokens'
import { Icons } from './icons'

interface Props {
  children: ReactNode
  fallback?: ReactNode
  onError?: (error: Error, errorInfo: ErrorInfo) => void
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo)
    this.props.onError?.(error, errorInfo)
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback
      }

      return (
        <div style={{ padding: '40px', height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Result
            status="error"
            title="应用程序遇到错误"
            subTitle="抱歉，应用程序遇到了意外错误。您可以尝试刷新页面或重置应用状态。"
            extra={[
              <Button type="primary" key="reset" onClick={this.handleReset} icon={<Icons.RotateCcw size={14} />}>
                重置状态
              </Button>,
              <Button key="reload" onClick={() => window.location.reload()}>
                刷新页面
              </Button>,
            ]}
          >
            {this.state.error && (
              <div style={{ marginTop: 24, padding: 16, background: T.error.container, borderRadius: 8, border: `1px solid ${T.error.main}33` }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: T.toneError, marginBottom: 8, letterSpacing: '0.08em' }}>
                  错误详情
                </div>
                <pre style={{ fontSize: 12, color: T.textSecondary, margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                  {this.state.error.message}
                </pre>
              </div>
            )}
          </Result>
        </div>
      )
    }

    return this.props.children
  }
}
