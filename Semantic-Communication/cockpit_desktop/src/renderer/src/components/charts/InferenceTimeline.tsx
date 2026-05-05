import ReactEChartsCore from 'echarts-for-react/lib/core'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, MarkLineComponent, MarkPointComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { COCKPIT_ECHARTS_THEME } from '../../theme/echarts-theme'
import { T } from '../../theme/tokens'
import { EmptyState } from '../shared/EmptyState'

echarts.use([LineChart, GridComponent, TooltipComponent, CanvasRenderer, MarkLineComponent, MarkPointComponent])

type ResultEntry = { timings?: { total_ms?: number | null } }

type Props = {
  results?: Record<string, ResultEntry> | null
}

export function InferenceTimeline({ results }: Props) {
  if (!results || Object.keys(results).length === 0) return <EmptyState title="暂无推理时间线" />

  const variants = Object.keys(results)
  const data = variants.map((v) => ({
    name: v,
    value: results[v]?.timings?.total_ms ?? null,
  }))

  const validValues = data.map((d) => d.value).filter((v): v is number => v !== null)
  const minValue = validValues.length > 0 ? Math.min(...validValues) : 0
  const maxValue = validValues.length > 0 ? Math.max(...validValues) : 0
  const avgValue = validValues.length > 0 ? validValues.reduce((a, b) => a + b, 0) / validValues.length : 0

  const option = {
    grid: { left: 50, right: 16, top: 40, bottom: 24 },
    tooltip: {
      trigger: 'axis' as const,
      formatter: (params: any) => {
        const p = params[0]
        const baseline = results['baseline']?.timings?.total_ms
        const diffNum = baseline && p.value ? (p.value - baseline) / baseline * 100 : null
        const diff = diffNum !== null ? diffNum.toFixed(1) : null
        let tooltip = `${p.name}<br/><span style="color:${T.accentBlue}">●</span> ${p.value?.toFixed(2) ?? '—'} ms`
        if (diff !== null && diffNum !== null) {
          const diffStr = diffNum > 0 ? `+${diff}%` : `${diff}%`
          const color = diffNum > 10 ? T.toneError : diffNum < -10 ? T.toneSuccess : T.toneWarning
          tooltip += `<br/><span style="color:${color}">vs baseline: ${diffStr}</span>`
        }
        return tooltip
      }
    },
    xAxis: {
      type: 'category' as const,
      data: data.map((d) => d.name),
      axisLabel: {
        fontSize: 12,
        fontFamily: "'Inter', sans-serif",
      },
    },
    yAxis: {
      type: 'value' as const,
      min: (value: { min: number }) => Math.max(0, value.min - 100),
      max: (value: { max: number }) => value.max + 100,
      axisLabel: {
        formatter: '{value} ms',
        fontSize: 12,
        fontFamily: "'Inter', sans-serif",
      },
    },
    series: [
      {
        type: 'line',
        data: data.map((d) => d.value),
        smooth: true,
        smoothMonotone: 'x',
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: {
          color: T.accentBlue,
          width: 2,
        },
        itemStyle: {
          color: T.accentBlue,
          borderColor: T.bgCard,
          borderWidth: 2,
        },
        emphasis: {
          itemStyle: {
            color: T.accentBlue,
            borderColor: T.bgCard,
            borderWidth: 2,
          },
        },
        areaStyle: {
          color: {
            type: 'linear' as const,
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(26,86,219,0.15)' },
              { offset: 1, color: 'rgba(26,86,219,0.01)' },
            ],
          },
        },
        markLine: {
          silent: true,
          symbol: 'none',
          label: {
            show: true,
            position: 'end',
            formatter: '{c} ms',
            fontSize: 10,
            color: T.textLabel,
          },
          lineStyle: {
            type: 'dashed',
            color: T.borderBase,
            opacity: 0.8,
          },
          data: [
            { yAxis: avgValue, label: { formatter: `平均: ${avgValue.toFixed(2)} ms` } },
          ],
        },
        markPoint: {
          symbol: 'circle',
          symbolSize: 50,
          label: {
            show: true,
            formatter: (params: any) => {
              if (params.dataType === 'min') return `最小: ${minValue.toFixed(2)} ms`
              if (params.dataType === 'max') return `最大: ${maxValue.toFixed(2)} ms`
              return ''
            },
            fontSize: 10,
            color: T.textPrimary,
          },
          data: [
            { type: 'max', name: '最大值', itemStyle: { color: T.toneError } },
            { type: 'min', name: '最小值', itemStyle: { color: T.toneSuccess } },
          ],
        },
      },
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
