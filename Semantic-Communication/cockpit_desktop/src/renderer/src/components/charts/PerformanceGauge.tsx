import ReactEChartsCore from 'echarts-for-react/lib/core'
import * as echarts from 'echarts/core'
import { GaugeChart } from 'echarts/charts'
import { CanvasRenderer } from 'echarts/renderers'
import { COCKPIT_ECHARTS_THEME } from '../../theme/echarts-theme'
import { T } from '../../theme/tokens'
import { EmptyState } from '../shared/EmptyState'

echarts.use([GaugeChart, CanvasRenderer])

type Props = {
  payloadMs?: number
  e2eMs?: number
  maxMs?: number
}

function createGaugeSeries(center: string, value: number, name: string, maxMs: number) {
  return {
    type: 'gauge',
    center: [center, '52%'] as [string, string],
    radius: '75%',
    startAngle: 200,
    endAngle: -20,
    min: 0,
    max: maxMs,
    splitNumber: 5,
    axisLine: {
      lineStyle: {
        width: 14,
        color: [
          [0.5, T.toneSuccess],
          [0.75, T.toneWarning],
          [1, T.toneError],
        ],
      }
    },
    pointer: {
      width: 5,
      length: '70%',
      itemStyle: {
        color: T.accentBlue,
      }
    },
    axisTick: { show: false },
    splitLine: {
      distance: -12,
      length: 12,
      lineStyle: {
        color: T.borderBase,
        width: 1,
      }
    },
    axisLabel: {
      distance: 16,
      color: T.textLabel,
      fontSize: 10,
      fontFamily: "'Inter', sans-serif",
    },
    detail: {
      valueAnimation: true,
      formatter: '{value} ms',
      color: T.textPrimary,
      fontSize: 18,
      fontWeight: 600,
      fontFamily: "'JetBrains Mono', monospace",
      offsetCenter: [0, '78%'],
    },
    title: {
      offsetCenter: [0, '94%'],
      color: T.textLabel,
      fontSize: 12,
      fontFamily: "'Inter', sans-serif",
    },
    data: [{ value, name }],
    progress: {
      show: true,
      roundCap: true,
      width: 14,
    },
  }
}

export function PerformanceGauge({ payloadMs, e2eMs, maxMs = 3000 }: Props) {
  if (payloadMs == null && e2eMs == null) return <EmptyState title="暂无性能数据" />

  const option = {
    series: [
      createGaugeSeries('25%', payloadMs ?? 0, 'Payload', maxMs),
      createGaugeSeries('75%', e2eMs ?? 0, 'E2E', maxMs),
    ],
  }

  return (
    <ReactEChartsCore
      echarts={echarts}
      theme={COCKPIT_ECHARTS_THEME}
      option={option}
      style={{ height: 200, width: '100%' }}
      notMerge
      lazyUpdate
    />
  )
}
