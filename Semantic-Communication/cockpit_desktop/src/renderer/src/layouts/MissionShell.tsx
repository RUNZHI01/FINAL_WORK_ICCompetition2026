import { useEffect, useRef } from 'react'
import { Layout } from 'antd'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useHealth } from '../hooks/useHealth'
import { useAppStore } from '../stores/appStore'
import { Icons } from '../components/icons'
import s from './MissionShell.module.css'

const { Header, Content } = Layout

const NAV_TABS = [
  { key: '/', label: '仪表盘' },
  { key: '/console', label: '控制台' },
] as const

function SystemClock() {
  const ref = useRef<HTMLSpanElement>(null)

  useEffect(() => {
    const update = () => {
      if (ref.current) {
        ref.current.textContent = new Date().toLocaleTimeString('zh-CN', { hour12: false })
      }
    }
    update()
    const id = setInterval(update, 1000)
    return () => clearInterval(id)
  }, [])

  return <span ref={ref} className={s.systemClock} aria-live="off" />
}

export function MissionShell() {
  const appTitle = useAppStore((s) => s.appTitle)
  const health = useHealth()
  const location = useLocation()
  const navigate = useNavigate()
  const activeTab = location.pathname === '/console' ? '/console' : '/'

  const linkOk = health.isSuccess && health.data?.status === 'ok'

  const handleFullscreen = () => {
    if (document.fullscreenElement) {
      document.exitFullscreen()
    } else {
      document.documentElement.requestFullscreen()
    }
  }

  return (
    <Layout style={{ minHeight: '100vh', background: 'var(--color-bg-primary)', border: 'none' }}>
      <Header className={s.header} role="banner">
        <div className={s.titleGroup}>
          <Icons.Radar size={16} className={s.logoIcon} aria-hidden="true" />
          <h1 className={s.title}>{appTitle}</h1>
        </div>

        <nav className={s.navTabs} aria-label="主导航">
          {NAV_TABS.map((tab) => (
            <button
              key={tab.key}
              className={activeTab === tab.key ? s.navTabActive : s.navTab}
              onClick={() => navigate(tab.key)}
              aria-current={activeTab === tab.key ? 'page' : undefined}
            >
              {tab.label}
            </button>
          ))}
        </nav>

        <div className={s.rightSection}>
          <div className={s.statusInline}>
            <span
              className={`${s.healthDot} ${linkOk ? s.healthOk : s.healthErr}`}
              role="status"
              aria-label={linkOk ? '系统在线' : '系统离线'}
            />
            <span className={s.healthLabel}>{linkOk ? '在线' : '离线'}</span>
          </div>
          <div className={s.divider} aria-hidden="true" />
          <SystemClock />
          <div className={s.divider} aria-hidden="true" />
          <button
            className={s.iconBtn}
            onClick={handleFullscreen}
            title="全屏"
            aria-label="切换全屏模式"
          >
            <Icons.Maximize size={14} aria-hidden="true" />
          </button>
        </div>
      </Header>
      <Content className={s.content} role="main">
        <Outlet />
      </Content>
    </Layout>
  )
}
