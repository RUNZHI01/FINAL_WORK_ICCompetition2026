import ReactEChartsCore from 'echarts-for-react/lib/core'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { COCKPIT_ECHARTS_THEME } from '../../theme/echarts-theme'

echarts.use([LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

type ResultEntry = { timings?: { total_ms?: number | null } }

type Props = {
  results?: Record<string, ResultEntry> | null
}

export function InferenceTimeline({ results }: Props) {
  if (!results || Object.keys(results).length === 0) return null

  const variants = Object.keys(results)
  const data = variants.map((v) => ({
    name: v,
    value: results[v]?.timings?.total_ms ?? null,
  }))

  const option = {
    grid: { left: 50, right: 16, top: 20, bottom: 24 },
    tooltip: { trigger: 'axis' as const },
    legend: { show: false },
    xAxis: { type: 'category' as const, data: data.map((d) => d.name), axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value' as const, axisLabel: { formatter: '{value} ms', fontSize: 10 } },
    series: [
      {
        type: 'line',
        data: data.map((d) => d.value),
        smooth: true,
        symbol: 'circle',
        symbolSize: 8,
        lineStyle: { color: '#5ab7ff', width: 2 },
        itemStyle: { color: '#8fe6ff' },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(90,183,255,0.25)' },
              { offset: 1, color: 'rgba(90,183,255,0.02)' },
            ],
          } as any,
        },
      },
    ],
  }

  return (
    <ReactEChartsCore
      echarts={echarts}
      theme={COCKPIT_ECHARTS_THEME}
      option={option}
      style={{ height: 180, width: '100%' }}
      notMerge
      lazyUpdate
    />
  )
}
