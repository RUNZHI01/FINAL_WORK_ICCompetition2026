import { useCryptoStatus } from '../../../hooks/useCryptoStatus'
import { useSwitchLinkProfile } from '../../../hooks/useActions'
import type { ServiceModeSnapshot } from '../../../api/types/crypto'
import s from './DegradationStatusPanel.module.css'

const MODE_DISPLAY: Record<string, { label: string; dotClass: string; badgeClass: string }> = {
  FULL_FRAME: { label: '全图模式', dotClass: s.dotOk, badgeClass: s.modeFull },
  ROI_ONLY:   { label: 'ROI 模式', dotClass: s.dotWarn, badgeClass: s.modeRoi },
  ALERT_ONLY: { label: '告警模式', dotClass: s.dotDanger, badgeClass: s.modeAlert },
}

const STRATEGY_LABEL: Record<string, string> = {
  full_latent: '完整语义张量',
  roi_latent: 'ROI 裁剪张量',
  alert_metadata: '告警元数据',
}

function formatTransitionReason(reason: string): string {
  const MAP: Record<string, string> = {
    'sustained degradation': '持续劣化',
    'sustained recovery': '持续恢复',
    'burst loss emergency': '突发丢包紧急',
    'link lost (rx_locked=false)': '链路丢失',
  }
  return MAP[reason] ?? reason
}

function modeLabel(mode: string): string {
  return MODE_DISPLAY[mode]?.label ?? mode
}

export function DegradationStatusPanel() {
  const { data, isLoading, isError } = useCryptoStatus()
  const switchMut = useSwitchLinkProfile()
  const serviceMode: ServiceModeSnapshot | null | undefined = data?.service_mode

  if (isError) {
    return (
      <div className={s.card}>
        <div className={s.titleRow}>
          <span className={s.title}>服务模式状态</span>
        </div>
        <div className={s.disabledRow}>
          <span className={`${s.dot} ${s.dotDanger}`} />
          <span className={s.modeAlert}>服务模式状态不可用</span>
        </div>
      </div>
    )
  }

  if (isLoading || !data) {
    return (
      <div className={s.card}>
        <div className={s.titleRow}>
          <span className={s.title}>服务模式状态</span>
        </div>
        <div className={s.disabledRow}>
          <span className={`${s.dot} ${s.dotOff}`} />
          <span className={s.muted}>正在读取服务模式状态...</span>
        </div>
      </div>
    )
  }

  if (!serviceMode || !serviceMode.available) {
    return (
      <div className={s.card}>
        <div className={s.titleRow}>
          <span className={s.title}>服务模式状态</span>
        </div>
        <div className={s.rowGrid}>
          <span className={s.label}>状态来源</span>
          <span className={s.mono}>{serviceMode?.source ?? 'unknown'}</span>

          <span className={s.label}>当前状态</span>
          <span className={s.muted}>未接入</span>
        </div>
        <div className={s.transitionRow}>
          <span>{serviceMode?.note ?? '当前 live 固件尚未暴露服务模式状态。'}</span>
        </div>
      </div>
    )
  }

  const modeInfo = MODE_DISPLAY[serviceMode.current_mode ?? ''] ?? {
    label: serviceMode.current_mode ?? 'UNKNOWN',
    dotClass: s.dotOff,
    badgeClass: '',
  }

  return (
    <div className={s.card}>
      <div className={s.titleRow} style={{ marginBottom: '12px' }}>
        <span className={s.title}>服务模式状态</span>
        <span className={`${s.modeBadge} ${modeInfo.badgeClass}`}>
          <span className={`${s.dot} ${modeInfo.dotClass}`} />
          {modeInfo.label} ({serviceMode.current_mode})
        </span>
      </div>

      <div style={{ display: 'flex', gap: '8px', marginBottom: '20px' }}>
        <button className={s.btnTonal} onClick={() => switchMut.mutate('normal')} disabled={switchMut.isPending}>正常链路 (全图)</button>
        <button className={s.btnTonal} onClick={() => switchMut.mutate('lossy')} disabled={switchMut.isPending}>丢包扰动 (ROI)</button>
        <button className={s.btnTonal} onClick={() => switchMut.mutate('flaky')} disabled={switchMut.isPending}>断连弱网 (告警)</button>
      </div>

      <div className={s.rowGrid}>
        <span className={s.label}>载荷策略</span>
        <span className={s.mono}>
          {serviceMode.payload_strategy ? (STRATEGY_LABEL[serviceMode.payload_strategy] ?? serviceMode.payload_strategy) : '—'}
        </span>

        <span className={s.label}>允许模式</span>
        <span className={s.mono}>{serviceMode.allowed_mode ?? '—'}</span>

        <span className={s.label}>切换次数</span>
        <span className={s.mono}>{serviceMode.mode_transitions > 0 ? `${serviceMode.mode_transitions} 次` : '—'}</span>

        <span className={s.label}>状态来源</span>
        <span className={s.mono}>{serviceMode.source}</span>
      </div>

      {serviceMode.last_transition ? (
        <div className={s.transitionRow}>
          <span>{modeLabel(serviceMode.last_transition.from_mode)}</span>
          <span className={s.transitionArrow}>→</span>
          <span>{modeLabel(serviceMode.last_transition.to_mode)}</span>
          <span>({formatTransitionReason(serviceMode.last_transition.reason)})</span>
        </div>
      ) : (
        <div className={s.transitionRow}>
          <span>{serviceMode.note}</span>
        </div>
      )}
    </div>
  )
}
