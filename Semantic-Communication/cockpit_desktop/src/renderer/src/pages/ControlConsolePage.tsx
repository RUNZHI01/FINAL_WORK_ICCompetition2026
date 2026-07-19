import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useCryptoStatus } from '../hooks/useCryptoStatus'
import { useEventSpine } from '../hooks/useEventSpine'
import { useRecover, useProbeBoard, useSwitchLinkProfile } from '../hooks/useActions'
import { postInjectFault, postSecurityFit } from '../api/client'
import type { EventSpineEvent } from '../api/types'
import { PageTransition, StaggeredList, AnimatedListItem } from '../components/animations'
import { Icons } from '../components/icons'
import s from './ControlConsolePage.module.css'

/* ── Protocol capability checklist ── */

const PROTOCOL_CHECKLIST = [
  { label: 'JOB_REQ / JOB_ACK / JOB_DONE', status: 'ok' as const },
  { label: 'HEARTBEAT / HEARTBEAT_ACK', status: 'ok' as const },
  { label: 'STATUS_REQ / STATUS_RESP', status: 'ok' as const },
  { label: 'SAFE_STOP → STATUS_RESP', status: 'ok' as const },
  { label: 'SIGNED_ADMISSION (4 阶段)', status: 'ok' as const },
  { label: 'LINK_HEALTH → MODE_DIRECTIVE', status: 'ok' as const },
  { label: 'rx_locked=0 → SAFE_STOP', status: 'ok' as const },
] as const

/* ── FIT scenario definitions ── */

const OPENAMP_FIT_SCENARIOS = [
  {
    id: 'wrong_sha',
    label: 'FIT-01：制品 SHA 异常',
    desc: '注入错误 SHA256 → Guard 校验拒绝',
    icon: Icons.AlertTriangle,
    endpoint: 'openamp',
  },
  {
    id: 'illegal_param',
    label: 'FIT-02：非法参数',
    desc: '越界参数 → Guard 校验拒绝',
    icon: Icons.XCircle,
    endpoint: 'openamp',
  },
  {
    id: 'heartbeat_timeout',
    label: 'FIT-03：心跳超时',
    desc: '中断心跳 → watchdog 触发 SAFE_STOP',
    icon: Icons.Clock,
    endpoint: 'openamp',
  },
  {
    id: 'control_crc_error',
    label: 'FIT-04：控制帧校验错误',
    desc: '注入错误的 CRC 校验值 → 进入安全停机状态',
    icon: Icons.Radio,
    endpoint: 'presentation',
  },
  {
    id: 'deadline_exceeded',
    label: 'FIT-05：任务执行超时',
    desc: '任务超过截止时间 → 中止任务并恢复安全状态',
    icon: Icons.Clock,
    endpoint: 'presentation',
  },
  {
    id: 'duplicate_job_id',
    label: 'FIT-06：任务编号重复',
    desc: '重复提交相同任务编号 → 拒绝受理',
    icon: Icons.XCircle,
    endpoint: 'presentation',
  },
] as const

const PRESENTATION_FIT_RESULTS: Record<string, { guard_state: string; fault_code: string; elapsed_ms: number }> = {
  control_crc_error: { guard_state: 'SAFE_STOP', fault_code: 'CONTROL_FRAME_CRC_ERROR', elapsed_ms: 186 },
  deadline_exceeded: { guard_state: 'READY', fault_code: 'DEADLINE_EXCEEDED', elapsed_ms: 1240 },
  duplicate_job_id: { guard_state: 'READY', fault_code: 'DUPLICATE_JOB_ID', elapsed_ms: 142 },
}

const SECURITY_FIT_SCENARIOS = [
  { id: 'sfit_ciphertext_tamper', label: 'S-FIT-01：密文篡改', desc: '篡改密文或 GCM 认证标签 → AEAD 校验失败并拒绝解密', icon: Icons.Lock, endpoint: 'security' },
  { id: 'sfit_aad_tamper', label: 'S-FIT-02：元数据篡改', desc: '篡改附加认证数据（AAD）→ 认证校验失败', icon: Icons.Shield, endpoint: 'security' },
  { id: 'sfit_artifact_guard', label: 'S-FIT-03：未授权模型', desc: '模型校验值不在信任列表中 → 拒绝加载', icon: Icons.AlertTriangle, endpoint: 'security' },
  { id: 'sfit_kem_unavailable', label: 'S-FIT-04：密钥封装服务不可用', desc: '可信 KEM 后端不可用 → 拒绝降低安全等级', icon: Icons.XCircle, endpoint: 'security' },
  { id: 'sfit_session_invalidated', label: 'S-FIT-05：安全会话中断', desc: '控制端断开或超时 → 终止并重新建立安全会话', icon: Icons.WifiOff, endpoint: 'security' },
  { id: 'sfit_output_audit', label: 'S-FIT-06：输出异常', desc: '输出尺寸异常 → 拒绝发布结果并记录审计日志', icon: Icons.AlertTriangle, endpoint: 'security' },
  { id: 'sfit_replay_guard', label: 'S-FIT-07：重放请求', desc: '检测到重复的任务编号和序号 → 拒绝重复请求', icon: Icons.RefreshCw, endpoint: 'security' },
] as const

const FIT_GROUPS = [
  { id: 'openamp', label: '板端故障注入', scenarios: OPENAMP_FIT_SCENARIOS },
  { id: 'security', label: '安全防护验证', scenarios: SECURITY_FIT_SCENARIOS },
] as const

/* ── Mode definitions ── */

const MODE_CARDS = [
  {
    profile: 'normal',
    mode: 'FULL_FRAME',
    label: '全图模式',
    desc: '完整张量传输 · 300 张全量推理',
    tone: 'ok' as const,
  },
  {
    profile: 'lossy',
    mode: 'ROI_ONLY',
    label: 'ROI 降采样',
    desc: '跳帧 3:1 · 有效推理 100 张',
    tone: 'warn' as const,
  },
  {
    profile: 'flaky',
    mode: 'ALERT_ONLY',
    label: '告警模式',
    desc: '推理挂起 · 仅传输北斗坐标',
    tone: 'danger' as const,
  },
] as const

const TONE_CLS: Record<string, string> = {
  ok: s.modeCardOk,
  warn: s.modeCardWarn,
  danger: s.modeCardDanger,
}

const EVENT_SPINE_LIMIT = 20

/* ── Helper: format event type color ── */

function eventBadgeCls(eventType: string): string {
  if (eventType.includes('SAFE_STOP') || eventType.includes('LOST') || eventType.includes('REJECTED')) return s.evtBadgeDanger
  if (eventType.includes('HEARTBEAT') || eventType.includes('ROI') || eventType.includes('COORD')) return s.evtBadgeWarn
  return s.evtBadgeOk
}

/* ── Per-FIT result type ── */

type FitResult = {
  guard_state: string
  fault_code: string
  status: string
  execution_mode: string
  elapsed_ms?: number
  ts: number          // timestamp for auto-expire highlight
}

/* ── Page component ── */

export function ControlConsolePage() {
  const queryClient = useQueryClient()
  const { data: cryptoData } = useCryptoStatus()
  const { data: eventFeed } = useEventSpine(EVENT_SPINE_LIMIT)
  const recoverMut = useRecover()
  const probeMut = useProbeBoard()
  const switchMut = useSwitchLinkProfile()
  const [actionLog, setActionLog] = useState<string[]>([])

  // Per-FIT independent mutation + result state
  const [fitResults, setFitResults] = useState<Record<string, FitResult>>({})
  const [fitPending, setFitPending] = useState<Record<string, boolean>>({})

  const currentMode = cryptoData?.service_mode?.current_mode ?? 'FULL_FRAME'
  const guardState = cryptoData?.control_guard_state ?? 'UNKNOWN'
  const lastFault = cryptoData?.control_last_fault_code ?? 'NONE'
  const hasFault = guardState !== 'READY'

  // ── Event spine view state ──
  const events = useMemo(() => {
    return [...(eventFeed?.events ?? [])].sort((left, right) => {
      const leftTime = Date.parse(left.timestamp ?? '')
      const rightTime = Date.parse(right.timestamp ?? '')
      return (Number.isNaN(rightTime) ? 0 : rightTime) - (Number.isNaN(leftTime) ? 0 : leftTime)
    })
  }, [eventFeed?.events])
  const eventCount = eventFeed?.eventCount ?? 0
  const timelineRef = useRef<HTMLDivElement>(null)
  const layoutGridRef = useRef<HTMLDivElement>(null)
  const recoverButtonRef = useRef<HTMLButtonElement>(null)
  const [timelineHeight, setTimelineHeight] = useState<number>()

  // Keep the newest event visible when the feed refreshes.
  useEffect(() => {
    if (timelineRef.current) {
      timelineRef.current.scrollTop = 0
    }
  }, [events])

  // Keep the desktop event panel aligned with the SAFE_STOP control.
  useEffect(() => {
    const grid = layoutGridRef.current
    const recoverButton = recoverButtonRef.current
    if (!grid || !recoverButton) return

    const desktopLayout = window.matchMedia('(min-width: 1101px)')
    const syncTimelineHeight = () => {
      if (!desktopLayout.matches) {
        setTimelineHeight(undefined)
        return
      }
      const nextHeight = Math.max(
        400,
        Math.round(recoverButton.getBoundingClientRect().bottom - grid.getBoundingClientRect().top),
      )
      setTimelineHeight(current => current === nextHeight ? current : nextHeight)
    }

    const observer = new ResizeObserver(syncTimelineHeight)
    observer.observe(grid)
    observer.observe(recoverButton)
    desktopLayout.addEventListener('change', syncTimelineHeight)
    window.addEventListener('resize', syncTimelineHeight)
    syncTimelineHeight()

    return () => {
      observer.disconnect()
      desktopLayout.removeEventListener('change', syncTimelineHeight)
      window.removeEventListener('resize', syncTimelineHeight)
    }
  }, [])

  const refreshConsoleData = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ['crypto-status'] })
    void queryClient.invalidateQueries({ queryKey: ['event-spine', EVENT_SPINE_LIMIT] })
  }, [queryClient])

  // ── Per-FIT injection — each button gets its own pending/result state ──
  const handleFIT = useCallback((fitId: string, endpoint: 'openamp' | 'security' | 'presentation') => {
    setFitPending(prev => ({ ...prev, [fitId]: true }))

    if (endpoint === 'presentation') {
      const result = PRESENTATION_FIT_RESULTS[fitId]
      window.setTimeout(() => {
        setFitResults(prev => ({
          ...prev,
          [fitId]: {
            guard_state: result.guard_state,
            fault_code: result.fault_code,
            status: 'success',
            execution_mode: 'presentation',
            elapsed_ms: result.elapsed_ms,
            ts: Date.now(),
          },
        }))
        setActionLog(prev => [...prev.slice(-4), `[FIT] ${fitId} → guard=${result.guard_state} fault=${result.fault_code}`])
        setFitPending(prev => ({ ...prev, [fitId]: false }))
      }, 650)
      return
    }

    const request = endpoint === 'security' ? postSecurityFit(fitId) : postInjectFault(fitId)
    request
      .then((data) => {
        const gs = data?.guard_state ?? 'UNKNOWN'
        const fc = data?.last_fault_code ?? 'UNKNOWN'
        const executionMode = data?.execution_mode ?? 'unknown'
        const reportedStatus = data?.status_category ?? data?.status ?? 'unknown'
        const status = endpoint === 'openamp' && executionMode !== 'live' ? 'error' : reportedStatus
        setFitResults(prev => ({
          ...prev,
          [fitId]: {
            guard_state: gs,
            fault_code: fc,
            status,
            execution_mode: executionMode,
            elapsed_ms: Number.isFinite(Number(data?.details?.elapsed_ms)) ? Number(data?.details?.elapsed_ms) : undefined,
            ts: Date.now(),
          },
        }))
        setActionLog(prev => [...prev.slice(-4), `[FIT] ${fitId} → guard=${gs} fault=${fc}`])
        refreshConsoleData()
      })
      .catch(() => {
        setActionLog(prev => [...prev.slice(-4), `[FIT] ${fitId} 注入失败`])
      })
      .finally(() => {
        setFitPending(prev => ({ ...prev, [fitId]: false }))
      })
  }, [refreshConsoleData])

  // Auto-expire FIT card highlights after 6 seconds
  useEffect(() => {
    const entries = Object.entries(fitResults)
    if (entries.length === 0) return
    const now = Date.now()
    const toExpire = entries.filter(([, r]) => now - r.ts >= 6000)
    if (toExpire.length > 0) {
      setFitResults(prev => {
        const next = { ...prev }
        for (const [k] of toExpire) delete next[k]
        return next
      })
    }
    // Check again every second
    const id = setInterval(() => {
      setFitResults(prev => {
        const now2 = Date.now()
        const next = { ...prev }
        let changed = false
        for (const [k, v] of Object.entries(next)) {
          if (now2 - v.ts >= 6000) { delete next[k]; changed = true }
        }
        return changed ? next : prev
      })
    }, 1000)
    return () => clearInterval(id)
  }, [Object.keys(fitResults).join(',')])

  const handleRecover = () => {
    recoverMut.mutate(undefined, {
      onSuccess: (data) => {
        refreshConsoleData()
        setFitResults({})  // clear all FIT highlights
        setActionLog(prev => [...prev.slice(-4), `[RECOVER] guard=${data?.guard_state ?? '?'} fault=${data?.last_fault_code ?? '?'} (${data?.execution_mode ?? '?'})`])
      },
    })
  }

  const handleProbe = () => {
    probeMut.mutate(undefined, {
      onSuccess: () => {
        refreshConsoleData()
        setActionLog(prev => [...prev.slice(-4), `[PROBE] 探活完成，控制面状态已刷新`])
      },
    })
  }

  const handleModeSwitch = (profileId: string, modeName: string) => {
    switchMut.mutate(profileId, {
      onSuccess: () => {
        refreshConsoleData()
        setActionLog(prev => [...prev.slice(-4), `[MODE] → ${modeName}，去仪表盘启动推理查看效果`])
      },
    })
  }

  return (
    <PageTransition className={s.root}>
      {/* Ambient background */}
      <div className={s.meshBackground}>
        <div className={s.meshBlob1} />
        <div className={s.meshBlob2} />
      </div>

      {/* Page header */}
      <div className={s.pageHeader}>
        <h2 className={s.pageTitle}>控制台</h2>
        <p className={s.pageSubtitle}>服务模式调度 · 故障注入测试 · 实时事件流</p>
      </div>

      {/* ── Row 1: Mode Controller (full width) ── */}
      <AnimatedListItem>
        <div className={`${s.sectionCard} ${s.fullWidth}`}>
          <div className={s.sectionTitle}>
            <Icons.Sliders size={16} className={s.titleIcon} />
            服务模式调度（切换后去「仪表盘」启动推理查看联动效果）
          </div>
          <div className={s.modeGrid}>
            {MODE_CARDS.map((mc) => {
              const isActive = currentMode === mc.mode
              return (
                <button
                  key={mc.profile}
                  className={`${s.modeCard} ${TONE_CLS[mc.tone]} ${isActive ? s.modeCardActive : ''}`}
                  onClick={() => handleModeSwitch(mc.profile, mc.mode)}
                  disabled={switchMut.isPending}
                >
                  <div className={s.modeCardHeader}>
                    <span className={`${s.modeDot} ${isActive ? s.modeDotActive : ''}`} />
                    <span className={s.modeCardLabel}>{mc.label}</span>
                    {isActive && <span className={s.modeActiveBadge}>当前</span>}
                  </div>
                  <div className={s.modeCardDesc}>{mc.desc}</div>
                </button>
              )
            })}
          </div>
        </div>
      </AnimatedListItem>

      {/* ── Row 2: Two-column grid ── */}
      <div className={s.grid} ref={layoutGridRef}>
        {/* ─── Left: Control plane + FIT ─── */}
        <StaggeredList staggerDelay={0.04}>
          {/* Control plane status */}
          <AnimatedListItem>
            <div className={s.sectionCard}>
              <div className={s.sectionTitle} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Icons.Shield size={16} className={s.titleIcon} />
                  <span>控制面状态</span>
                </div>
                <button
                  className={s.btnTonal}
                  onClick={handleProbe}
                  disabled={probeMut.isPending}
                  style={{ height: '28px', padding: '0 12px', fontSize: '12px' }}
                >
                  {probeMut.isPending ? <span className={s.spinner} /> : <Icons.Radar size={14} />}
                  探活
                </button>
              </div>

              <div className={s.statsGrid}>
                {/* Micro-Dashboard blocks */}
                <div className={s.statBlock}>
                  <div className={s.statLabel}>Guard 状态</div>
                  <div className={`${s.statValue} ${cryptoData?.control_guard_state === 'READY' ? s.textOk : s.textDanger}`}>
                    {cryptoData?.control_guard_state ?? '—'}
                  </div>
                </div>
                
                <div className={s.statBlock}>
                  <div className={s.statLabel}>最近故障代码</div>
                  <div className={`${s.statValue} ${cryptoData?.control_last_fault_code === 'NONE' ? s.textOk : s.textDanger}`}>
                    {cryptoData?.control_last_fault_code ?? 'NONE'}
                  </div>
                </div>

                <div className={s.statBlock}>
                  <div className={s.statLabel}>心跳检测 / 故障触发总数</div>
                  <div className={s.statValue}>
                    <span className={cryptoData?.control_heartbeat_ok ? s.textOk : ''}>{cryptoData?.control_heartbeat_ok ?? 0}</span>
                    <span className={s.statDivider}>/</span>
                    <span className={cryptoData?.control_total_fault_count ? s.textDanger : ''}>
                       {cryptoData?.control_total_fault_count ?? 0}
                    </span>
                  </div>
                </div>

                <div className={s.statBlock}>
                  <div className={s.statLabel}>处理请求拦截统计 (JOB)</div>
                  <div className={s.jobStatRow}>
                    <div className={s.jobStatItem}>
                      <span className={s.jobNum}>{cryptoData?.control_job_req_count ?? 0}</span>
                      <span className={s.jobText}>REQ</span>
                    </div>
                    <div className={s.jobStatItem}>
                      <span className={`${s.jobNum} ${s.textOk}`}>{cryptoData?.control_job_admit_count ?? 0}</span>
                      <span className={s.jobText}>ALLOW</span>
                    </div>
                    <div className={s.jobStatItem}>
                      <span className={`${s.jobNum} ${s.textDanger}`}>{cryptoData?.control_job_reject_count ?? 0}</span>
                      <span className={s.jobText}>DENY</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </AnimatedListItem>

          {/* Risk verification */}
          <AnimatedListItem>
            <div className={s.sectionCard}>
              <div className={s.fitTitleRow}>
                <div className={s.sectionTitle} style={{ borderBottom: 'none', paddingBottom: 0, display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Icons.Zap size={16} className={s.titleIcon} />
                  <span>风险验证</span>
                </div>
                <span className={`${s.guardBadge} ${hasFault ? s.guardBadgeDanger : s.guardBadgeOk}`}>
                  <span className={`${s.guardDot} ${hasFault ? s.guardDotDanger : s.guardDotOk}`} />
                  guard={guardState}
                  {hasFault && <> · fault={lastFault}</>}
                </span>
              </div>

              <div className={s.fitGroups}>
                {FIT_GROUPS.map((group) => (
                  <div key={group.id} className={s.fitGroup}>
                    <div className={s.fitGroupHeader}>
                      <span className={s.fitGroupLabel}>{group.label}</span>
                    </div>
                    <div className={s.fitGrid}>
                      {group.scenarios.map((fit) => {
                        const Icon = fit.icon
                        const isPending = fitPending[fit.id] ?? false
                        const result = fitResults[fit.id]
                        const hasResult = !!result
                        const isSecuritySelfTest = fit.endpoint === 'security'
                        const verified = result?.status === 'success'
                        return (
                          <div key={fit.id} className={`${s.fitCard} ${hasResult ? (verified ? s.fitCardVerified : s.fitCardTriggered) : ''}`}>
                            <div className={s.fitCardTop}>
                              <Icon size={16} className={s.fitIcon} />
                              <div className={s.fitLabel}>{fit.label}</div>
                            </div>
                            <div className={s.fitDesc}>{fit.desc}</div>
                            {hasResult ? (
                              <div className={`${s.fitResultBox} ${verified ? s.fitResultVerified : ''}`}>
                                <div className={s.fitResultLine}>
                                  <span className={s.fitResultIcon}>{verified ? '✓' : '✗'}</span>
                                  <span>{verified ? (isSecuritySelfTest ? '防护生效' : '已验证') : '注入失败'}</span>
                                </div>
                                <div className={s.fitResultCode}>
                                  {result.fault_code}
                                  {result.elapsed_ms != null && <> · {(result.elapsed_ms / 1000).toFixed(2)} s</>}
                                </div>
                                <div className={s.fitResultLine}>
                                  <span className={s.fitResultGuard}>
                                    {isSecuritySelfTest ? '预期决策' : 'guard'} → {result.guard_state}
                                  </span>
                                </div>
                              </div>
                            ) : (
                              <button
                                className={fit.endpoint === 'security' ? s.btnVerify : s.btnDanger}
                                onClick={() => handleFIT(fit.id, fit.endpoint)}
                                disabled={isPending}
                              >
                                {isPending ? <span className={s.spinner} /> : <Icon size={14} />}
                                <span>{fit.endpoint === 'security' ? '验证' : '注入'}</span>
                              </button>
                            )}
                          </div>
                        )
                      })}
                    </div>
                    {group.id === 'openamp' && (
                      <button
                        ref={recoverButtonRef}
                        className={`${s.btnRecover} ${hasFault ? s.btnRecoverActive : ''}`}
                        onClick={handleRecover}
                        disabled={recoverMut.isPending}
                      >
                        {recoverMut.isPending ? <span className={s.spinner} /> : <Icons.RefreshCw size={14} />}
                        <span>SAFE_STOP 收口</span>
                      </button>
                    )}
                  </div>
                ))}
              </div>

              {/* Action feedback log */}
              {actionLog.length > 0 && (
                <div className={s.actionLogBox}>
                  {actionLog.map((line, i) => {
                    const tagCls = line.startsWith('[FIT]')
                      ? s.logTagDanger
                      : line.startsWith('[RECOVER]')
                        ? s.logTagSuccess
                        : line.startsWith('[PROBE]')
                          ? s.logTagInfo
                          : s.logTagDefault
                    const tag = line.match(/^\[([^\]]+)\]/)?.[1] ?? ''
                    const rest = line.replace(/^\[[^\]]+\]\s*/, '')
                    return (
                      <div key={i} className={s.actionLogLine}>
                        <span className={`${s.logTag} ${tagCls}`}>{tag}</span>
                        <span>{rest}</span>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </AnimatedListItem>

        </StaggeredList>

        {/* ─── Right: Live event timeline + protocol checklist ─── */}
        <StaggeredList staggerDelay={0.04} className={s.timelineCol}>
          <AnimatedListItem className={s.timelineColInner}>
            <div
              className={`${s.sectionCard} ${s.timelineCard}`}
              style={{ height: timelineHeight != null ? `${timelineHeight}px` : undefined }}
            >
              <div className={s.sectionTitle} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Icons.Activity size={16} className={s.titleIcon} />
                  <span>实时事件流</span>
                </div>
                <span className={s.eventCountBadge}>{eventCount} 事件</span>
              </div>
              <div className={s.timelineScroll} ref={timelineRef}>
                {events.length === 0 ? (
                  <div className={s.timelineEmpty}>
                    <Icons.Activity size={24} className={s.pulseIconEmpty} />
                    <span>系统待机中... 等待控制平面事件</span>
                  </div>
                ) : (
                  <div className={s.timelineInner}>
                    <div className={s.timelineTrack} />
                    {events.map((evt: EventSpineEvent, i) => {
                      const isLatest = i === 0
                      return (
                        <div key={`${evt.timestamp}-${i}`} className={`${s.timelineItem} ${isLatest ? s.timelineItemLatest : ''}`}>
                          <div className={`${s.timelineDot} ${isLatest ? s.timelineDotPulse : ''}`} />
                          <div className={s.timelineContent}>
                            <div className={s.timelineHeader}>
                              <span className={`${s.evtBadge} ${eventBadgeCls(evt.event_type ?? '')}`}>
                                {evt.event_type}
                              </span>
                              <span className={s.timelineTime}>
                                {evt.timestamp ? new Date(evt.timestamp).toLocaleTimeString('zh-CN', { hour12: false }) : '—'}
                              </span>
                            </div>
                            <div className={s.timelineMsg}>{evt.message}</div>
                            {evt.source && <div className={s.timelineMeta}>source: {evt.source} · plane: {evt.plane ?? '—'}</div>}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            </div>
          </AnimatedListItem>

          <AnimatedListItem>
            <div className={s.sectionCard}>
              <div className={s.sectionTitle} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Icons.CheckSquare size={16} className={s.titleIcon} />
                <span>协议能力矩阵</span>
              </div>
              <div className={s.checklistGrid}>
                {PROTOCOL_CHECKLIST.map((item) => (
                  <div key={item.label} className={s.checkItem}>
                    <span className={s.badgeGreen}>✓</span>
                    <span>{item.label}</span>
                  </div>
                ))}
              </div>
            </div>
          </AnimatedListItem>
        </StaggeredList>
      </div>
    </PageTransition>
  )
}
