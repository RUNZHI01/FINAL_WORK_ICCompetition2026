import { useCryptoStatus } from '../../../hooks/useCryptoStatus'
import { postCryptoReset, postCryptoTest, postCryptoToggle } from '../../../api/client'
import { resolveAuthDisplayState } from './authDisplayState'
import s from './CryptoStatusPanel.module.css'
import { useEffect, useState, type ReactNode } from 'react'
import type { BenchmarkMetric } from '../../../api/types/crypto'

const STATE_LABEL: Record<string, { label: string; tone: string }> = {
  idle: { label: '空闲', tone: 'neutral' },
  handshaking: { label: '握手中', tone: 'warn' },
  ready: { label: '已建立', tone: 'ok' },
  closed: { label: '已关闭', tone: 'off' },
  disabled: { label: '未启用', tone: 'off' },
}

type MetricTone = 'default' | 'mono' | 'muted' | 'ok' | 'fail'

type MetricItem = {
  label: string
  value: ReactNode
  tone?: MetricTone
  half?: boolean
  wide?: boolean
}

type SecurityAuthConfig = {
  enabled: boolean
  disabled: boolean
  onToggle: (enabled: boolean) => void
}

type CryptoStatusPanelProps = {
  authConfig?: SecurityAuthConfig
}

function ToggleSwitch({
  checked,
  disabled,
  title,
  onToggle,
}: {
  checked: boolean
  disabled?: boolean
  title: string
  onToggle: () => void
}) {
  return (
    <button
      className={`${s.toggle} ${checked ? s.toggleOn : ''}`}
      disabled={disabled}
      onClick={onToggle}
      role="switch"
      aria-checked={checked}
      title={title}
      type="button"
    >
      <span className={s.toggleThumb} />
    </button>
  )
}

function SecuritySwitchRow({
  label,
  caption,
  status,
  checked,
  disabled,
  title,
  onToggle,
}: {
  label: string
  caption: string
  status: string
  checked: boolean
  disabled?: boolean
  title: string
  onToggle: () => void
}) {
  return (
    <div className={s.securitySwitchRow}>
      <div className={s.securitySwitchMain}>
        <div className={s.securitySwitchLabel}>{label}</div>
        <div className={s.securitySwitchCaption}>{caption}</div>
        <div className={s.securitySwitchStatus}>{status}</div>
      </div>
      <div className={s.securitySwitchControl}>
        <ToggleSwitch
          checked={checked}
          disabled={disabled}
          title={title}
          onToggle={onToggle}
        />
      </div>
    </div>
  )
}

export function CryptoStatusPanel({ authConfig }: CryptoStatusPanelProps) {
  const { data, isLoading, isError, refetch } = useCryptoStatus()
  const [testing, setTesting] = useState(false)
  const [resetting, setResetting] = useState(false)
  const [testResult, setTestResult] = useState<{ ok: boolean; msg: string } | null>(null)

  const enabled = data?.enabled ?? false
  const boardConfigured = data?.board_configured ?? false

  useEffect(() => {
    setTestResult(null)
  }, [enabled, boardConfigured])

  function errorMessage(error: unknown): string {
    if (error instanceof Error) {
      return error.message
    }
    return String(error)
  }

  async function handleToggle() {
    setTestResult(null)
    try {
      await postCryptoToggle(!enabled)
      refetch()
    } catch { /* ignore */ }
  }

  async function handleTest() {
    setTesting(true)
    setTestResult(null)
    try {
      const r = await postCryptoTest()
      if (r.status === 'ok') {
        setTestResult({
          ok: true,
          msg: `握手 ${r.handshake_ms?.toFixed(1) ?? '?'}ms | 总耗时 ${r.wall_ms?.toFixed(0) ?? '?'}ms`,
        })
      } else {
        setTestResult({ ok: false, msg: r.message?.trim() || 'unknown error' })
      }
      refetch()
    } catch (e) {
      setTestResult({ ok: false, msg: errorMessage(e) })
    } finally {
      setTesting(false)
    }
  }

  async function handleReset() {
    setResetting(true)
    setTestResult(null)
    try {
      const r = await postCryptoReset(true)
      setTestResult({ ok: true, msg: r.message?.trim() || '安全信道已重置' })
      refetch()
    } catch (e) {
      setTestResult({ ok: false, msg: errorMessage(e) })
    } finally {
      setResetting(false)
    }
  }

  function renderSecurityControls(encryptionStatus: string, encryptionDisabled = false) {
    return (
      <div className={s.securitySwitchGroup}>
        <SecuritySwitchRow
          label="加密: ML-KEM + SM4"
          caption="ML-KEM 协商会话密钥，SM4 保护控制面数据，降低明文暴露风险。"
          status={encryptionStatus}
          checked={enabled}
          disabled={encryptionDisabled}
          title={encryptionDisabled ? '请先输入板卡密码' : enabled ? '关闭加密通道' : '启用加密通道'}
          onToggle={handleToggle}
        />
        {authConfig && (
          <SecuritySwitchRow
            label="认证: ML-DSA + SM2"
            caption="ML-DSA 与 SM2 双重签名确认对端身份，降低冒充与中间人风险。"
            status={authConfig.enabled ? '已启用' : '未启用'}
            checked={authConfig.enabled}
            disabled={authConfig.disabled}
            title={authConfig.enabled ? '关闭身份认证' : '启用身份认证'}
            onToggle={() => authConfig.onToggle(!authConfig.enabled)}
          />
        )}
      </div>
    )
  }

  // 1) Board not configured — show prompt
  if (!boardConfigured && !enabled) {
    return (
      <div className={s.card}>
        <div className={s.titleRow}>
          <span className={s.title}>安全信道</span>
        </div>
        {renderSecurityControls('等待板卡密码', true)}
        <div className={s.disabledRow}>
          <span className={`${s.dot} ${s.dotOff}`} />
          <span className={s.muted}>请先在上方输入板卡密码</span>
        </div>
      </div>
    )
  }

  // 2) Toggle OFF (board configured)
  if (!enabled) {
    return (
      <div className={s.card}>
        <div className={s.titleRow}>
          <span className={s.title}>安全信道</span>
        </div>
        {renderSecurityControls('未启用')}
      </div>
    )
  }

  // 3) Toggle ON — error state
  if (isError) {
    return (
      <div className={s.card}>
        <div className={s.titleRow}>
          <span className={s.title}>安全信道</span>
        </div>
        {renderSecurityControls('通道未连接')}
        <div className={s.errorRow}>
          <span className={`${s.dot} ${s.dotOff}`} />
          <span className={s.errorText}>后量子加密通道未连接</span>
        </div>
      </div>
    )
  }

  // 4) Toggle ON — loading
  if (isLoading || !data) {
    return (
      <div className={s.card}>
        <div className={s.titleRow}>
          <span className={s.title}>安全信道</span>
        </div>
        {renderSecurityControls('检测中')}
        <div className={s.loadingRow}>
          <span className={s.spinner} />
          <span className={s.muted}>正在检测...</span>
        </div>
      </div>
    )
  }

  // 5) Toggle ON — normal display
  const st = STATE_LABEL[data.channel_state] ?? { label: data.channel_state, tone: 'neutral' }
  const settingsItems: MetricItem[] = [
    { label: 'KEM 后端', value: data.kem_backend, tone: 'mono' },
    { label: '密码套件', value: data.cipher_suite, tone: 'mono' },
  ]
  const authDisplay = resolveAuthDisplayState(authConfig?.enabled, data.auth_enabled)

  if (data.security_scope_label) {
    settingsItems.push({
      label: '作用范围',
      value: data.security_scope_label,
      tone: 'mono',
    })
  }

  if (authDisplay.known) {
    settingsItems.push({
      label: '认证面',
      value: authDisplay.label,
      tone: 'mono',
    })
  }

  const runtimeItems: MetricItem[] = [
    { label: '通道状态', value: st.label },
  ]
  const showTcpPayloadTimings = data.security_scope !== 'control_gate'

  if (data.handshake_ms != null) {
    runtimeItems.push({ label: '握手耗时', value: `${data.handshake_ms.toFixed(1)} ms`, tone: 'mono' })
  }
  if (data.bytes_sent != null || data.bytes_received != null) {
    runtimeItems.push({
      label: '加密流量',
      value: `↑${data.bytes_sent ?? 0}B / ↓${data.bytes_received ?? 0}B`,
      tone: 'mono',
      half: true,
    })
  }
  if (showTcpPayloadTimings && data.encrypt_ms != null) {
    runtimeItems.push({ label: '加密发送', value: `${data.encrypt_ms.toFixed(1)} ms`, tone: 'mono' })
  }
  if (showTcpPayloadTimings && data.decrypt_ms != null) {
    runtimeItems.push({ label: '结果等待/接收', value: `${data.decrypt_ms.toFixed(1)} ms`, tone: 'mono' })
  }
  if (showTcpPayloadTimings && data.inference_ms != null) {
    runtimeItems.push({ label: 'TVM 推理', value: `${data.inference_ms.toFixed(1)} ms`, tone: 'mono' })
  }
  if (data.last_sha256_match != null) {
    runtimeItems.push({
      label: 'SHA256',
      value: data.last_sha256_match ? '✓ 匹配' : '✗ 不匹配',
      tone: data.last_sha256_match ? 'ok' : 'fail',
    })
  }
  if (data.session_count != null && data.session_count > 0) {
    runtimeItems.push({ label: '累计会话', value: data.session_count, tone: 'mono' })
  }
  if (data.batch_status === 'running') {
    runtimeItems.push({
      label: '批量推理',
      value: `${data.batch_completed ?? 0} / ${data.batch_total ?? '?'} 运行中...`,
      tone: 'mono',
      wide: true,
    })
  }

  const infoItems: MetricItem[] = []
  if (testResult) {
    infoItems.push({
      label: testResult.ok ? '本次操作' : '测试结果',
      value: testResult.msg,
      tone: testResult.ok ? 'ok' : 'fail',
      wide: true,
    })
  }
  if (data.error) {
    infoItems.push({
      label: '错误信息',
      value: data.error,
      tone: 'fail',
      wide: true,
    })
  }

  function metricValueClass(tone: MetricTone = 'default'): string {
    if (tone === 'mono') return `${s.metricValue} ${s.metricMono}`
    if (tone === 'muted') return `${s.metricValue} ${s.metricMuted}`
    if (tone === 'ok') return `${s.metricValue} ${s.metricOk}`
    if (tone === 'fail') return `${s.metricValue} ${s.metricFail}`
    return s.metricValue
  }

  return (
    <div className={s.card}>
      <div className={s.titleRow}>
        <span className={s.title}>安全信道</span>
      </div>

      {renderSecurityControls(`通道状态: ${st.label}`)}

      <div className={s.subSection}>
        <div className={s.subSectionTitle}>配置项</div>
        <div className={`${s.metricGrid} ${s.settingsGrid}`}>
          {settingsItems.map((item) => (
            <div
              key={item.label}
              className={`${s.metricCard}${item.wide ? ` ${s.metricWide}` : ''}`}
            >
              <div className={s.metricLabel}>{item.label}</div>
              <div className={metricValueClass(item.tone)}>{item.value}</div>
            </div>
          ))}
        </div>
      </div>

      <div className={s.subSection}>
        <div className={s.subSectionTitle}>运行状态</div>
        <div className={`${s.metricGrid} ${s.runtimeGrid}`}>
          {runtimeItems.map((item) => (
            <div
              key={item.label}
              className={`${s.metricCard}${item.half ? ` ${s.metricHalf}` : ''}${item.wide ? ` ${s.metricWide}` : ''}`}
            >
              <div className={s.metricLabel}>{item.label}</div>
              <div className={metricValueClass(item.tone)}>{item.value}</div>
            </div>
          ))}
        </div>
      </div>

      <div className={s.testSection}>
        <div className={s.actionRow}>
          <button
            className={s.testBtn}
            onClick={handleTest}
            disabled={testing || resetting}
          >
            {testing ? <span className={s.spinner} /> : '测试加密通道'}
          </button>
          <button
            className={s.secondaryBtn}
            onClick={handleReset}
            disabled={testing || resetting}
          >
            {resetting ? <span className={s.spinner} /> : '重置安全信道'}
          </button>
        </div>
      </div>

      {/* Batch benchmark results */}
      {data.batch_status === 'done' && (data.batch_benchmark || data.batch_transport_benchmark || data.batch_inference_benchmark || data.batch_iq_stage_benchmark) && (() => {
        const inferenceBm = data.batch_inference_benchmark ?? data.batch_benchmark
        const transportBm = data.batch_transport_benchmark
        const iqStageBm = data.batch_iq_stage_benchmark
        const rows: { label: string; metric: BenchmarkMetric }[] = []
        if (transportBm?.radio_airtime_ms) rows.push({ label: '无线空口', metric: transportBm.radio_airtime_ms })
        if (transportBm?.decode_ms) rows.push({ label: '板端解码', metric: transportBm.decode_ms })
        if (transportBm?.merge_ms) rows.push({ label: '文件合并', metric: transportBm.merge_ms })
        if (transportBm?.total_ms) rows.push({ label: '传输/解包总计', metric: transportBm.total_ms })
        if (iqStageBm?.rx_arm_ms) rows.push({ label: '接收就绪', metric: iqStageBm.rx_arm_ms })
        if (iqStageBm?.rx_session_open_ms) rows.push({ label: '接收会话', metric: iqStageBm.rx_session_open_ms })
        if (iqStageBm?.rx_capture_command_ms) rows.push({ label: '采集命令', metric: iqStageBm.rx_capture_command_ms })
        if (iqStageBm?.rx_capture_ms) rows.push({ label: '接收采集', metric: iqStageBm.rx_capture_ms })
        if (iqStageBm?.rx_wait_ms) rows.push({ label: '接收等待', metric: iqStageBm.rx_wait_ms })
        if (iqStageBm?.rx_arm_control_overhead_ms) rows.push({ label: '接收就绪控制', metric: iqStageBm.rx_arm_control_overhead_ms })
        if (iqStageBm?.rx_wait_response_overhead_ms) rows.push({ label: '等待响应', metric: iqStageBm.rx_wait_response_overhead_ms })
        if (iqStageBm?.remote_decode_response_overhead_ms) rows.push({ label: '解码响应', metric: iqStageBm.remote_decode_response_overhead_ms })
        if (inferenceBm?.inference_ms) rows.push({ label: '推理重建', metric: inferenceBm.inference_ms })
        if (inferenceBm?.total_ms && inferenceBm.total_ms !== inferenceBm.inference_ms) rows.push({ label: '推理侧总计', metric: inferenceBm.total_ms })
        const validRows = rows.filter((row) => row.metric != null)
        if (validRows.length === 0) return null
        return (
          <div className={s.benchSection}>
            <div className={s.benchTitle}>
              批量 Benchmark（传输与推理分开，{inferenceBm?.total_ms?.n ?? inferenceBm?.inference_ms?.n ?? data.batch_completed ?? '?'} 张）
            </div>
            <table className={s.benchTable}>
              <thead>
                <tr>
                  <th>阶段</th>
                  <th>均值</th>
                  <th>中位</th>
                  <th>p95</th>
                </tr>
              </thead>
              <tbody>
                {validRows.map(({ label, metric }) => {
                  const m = metric!
                  const emphasized = label === '传输/解包总计' || label === '推理侧总计'
                  return (
                    <tr key={label} className={emphasized ? s.benchRowEmphasis : undefined}>
                      <td>{label}</td>
                      <td>{m.mean_ms} ms</td>
                      <td>{m.median_ms} ms</td>
                      <td>{m.p95_ms != null ? `${m.p95_ms} ms` : '-'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )
      })()}

      {infoItems.length > 0 && (
        <div className={s.infoSection}>
          <div className={s.subSectionTitle}>信息项</div>
          <div className={s.metricGrid}>
            {infoItems.map((item) => (
              <div
                key={item.label}
                className={`${s.metricCard} ${s.metricWide}${item.tone === 'fail' ? ` ${s.metricCardFail}` : ''}${item.tone === 'ok' ? ` ${s.metricCardOk}` : ''}`}
              >
                <div className={s.metricLabel}>{item.label}</div>
                <div className={metricValueClass(item.tone)}>{item.value}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
