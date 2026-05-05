import { UseQueryResult } from '@tanstack/react-query'
import type { SystemStatusResponse } from '../../../api/types'
import { Icons } from '../../icons'
import s from './MinimalStatusPanel.module.css'

function aircraftPositionStatusLabel(rawStatus: unknown): string {
  const status = String(rawStatus ?? '').trim().toLowerCase()
  if (status === 'live') return 'LIVE'
  if (status === 'stale') return 'STALE'
  if (status === 'stub') return 'STUB'
  if (status === 'fallback') return 'FALLBACK'
  if (status === 'absent') return 'ABSENT'
  return status ? status.toUpperCase() : 'UNKNOWN'
}

function CircularGauge({ value, color, label }: { value: number, color: string, label: string }) {
  const radius = 14;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (value / 100) * circumference;

  return (
    <div className={s.gaugeContainer}>
      <svg width="36" height="36" viewBox="0 0 36 36" className={s.gaugeSvg}>
        <circle cx="18" cy="18" r={radius} fill="none" stroke="var(--color-border-light)" strokeWidth="3" />
        <circle 
          cx="18" cy="18" r={radius} 
          fill="none" 
          stroke={color} 
          strokeWidth="3" 
          strokeDasharray={circumference} 
          strokeDashoffset={strokeDashoffset} 
          strokeLinecap="round" 
          transform="rotate(-90 18 18)"
          style={{ transition: 'stroke-dashoffset 500ms ease-in-out' }}
        />
      </svg>
      <div className={s.gaugeValue} style={{ color }}>{Math.round(value)}</div>
      <div className={s.gaugeLabel}>{label}</div>
    </div>
  );
}

function Waveform({ active }: { active: boolean }) {
  return (
    <div className={`${s.waveform} ${active ? s.waveformActive : ''}`}>
      <div className={s.waveBar} />
      <div className={s.waveBar} />
      <div className={s.waveBar} />
      <div className={s.waveBar} />
    </div>
  );
}

interface MinimalStatusPanelProps {
  system: UseQueryResult<SystemStatusResponse>
  inferenceProgress: any
  activeJobId: string | null
}

export function MinimalStatusPanel({ system }: MinimalStatusPanelProps) {
  const status = system.data
  const live = status?.live
  const sp = status?.safety_panel
  const aircraftPosition = status?.aircraft_position as Record<string, unknown> | undefined
  const boardOnline = live?.board_online ?? false
  const telemetry = live?.telemetry
  const computeLabel = telemetry?.compute_label ?? 'CPU'
  const computeUsage = telemetry?.compute_pct ?? 0
  const memUsage = telemetry?.memory_pct ?? 0
  const telemetryStatus = telemetry?.status ?? 'unavailable'
  const memorySummary = telemetry?.memory_used_mb != null && telemetry?.memory_total_mb != null
    ? `${Math.round(telemetry.memory_used_mb)} / ${Math.round(telemetry.memory_total_mb)} MB`
    : '—'
  const loadSummary = telemetry?.loadavg_1m != null
    ? `${telemetry.loadavg_1m.toFixed(2)}`
    : '—'
  const aircraftPositionStatus = aircraftPositionStatusLabel(aircraftPosition?.source_status)

  return (
    <div className={s.container}>
      <div className={s.headerRow}>
        <div className={s.sectionTitle}>
          <Icons.Activity size={13} style={{ color: 'var(--color-primary)' }} />
          <span>Hardware Telemetry</span>
        </div>
        <Waveform active={boardOnline && telemetryStatus === 'ok'} />
      </div>

      <div className={s.gaugesRow}>
        <CircularGauge value={computeUsage} color="var(--color-primary)" label={computeLabel} />
        <CircularGauge value={memUsage} color="var(--color-success)" label="MEM" />
      </div>

      <div className={s.detailList}>
        <div className={s.detailRow}>
          <span className={s.detailLabel}>Link Status</span>
          <span className={s.detailValue}>
            <div className={s.ledMatrix}>
              <span className={`${s.led} ${boardOnline ? s.ledGreen : ''}`} title="PWR" />
              <span className={`${s.led} ${boardOnline ? s.ledGreen : ''}`} title="LINK" />
              <span className={`${s.led} ${boardOnline ? s.ledBlueBlink : ''}`} title="SYNC" />
            </div>
          </span>
        </div>

        <div className={s.detailRow}>
          <span className={s.detailLabel}>Guard State</span>
          <span className={s.detailValueAccent}>{live?.guard_state ?? '—'}</span>
        </div>

        <div className={s.detailRow}>
          <span className={s.detailLabel}>Last Fault</span>
          <span className={sp?.last_fault_code ? s.detailValueWarning : s.detailValue}>
            {sp?.last_fault_code ?? 'None'}
          </span>
        </div>

        <div className={s.detailRow}>
          <span className={s.detailLabel}>Target</span>
          <span className={s.detailValue}>{live?.target ?? '—'}</span>
        </div>

        <div className={s.detailRow}>
          <span className={s.detailLabel}>Memory</span>
          <span className={s.detailValue}>{memorySummary}</span>
        </div>

        <div className={s.detailRow}>
          <span className={s.detailLabel}>Load 1m</span>
          <span className={s.detailValue}>{loadSummary}</span>
        </div>

        <div className={s.detailRow}>
          <span className={s.detailLabel}>Telemetry</span>
          <span className={telemetryStatus === 'ok' ? s.detailValueAccent : s.detailValue}>
            {telemetryStatus.toUpperCase()}
          </span>
        </div>

        <div className={s.detailRow}>
          <span className={s.detailLabel}>本机定位</span>
          <span className={aircraftPositionStatus === 'LIVE' ? s.detailValueAccent : s.detailValue}>
            {aircraftPositionStatus}
          </span>
        </div>
      </div>
    </div>
  )
}
