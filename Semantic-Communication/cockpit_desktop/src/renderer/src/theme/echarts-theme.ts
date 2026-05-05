import * as echarts from 'echarts'
import { T } from './tokens'

export const COCKPIT_ECHARTS_THEME = 'cockpit-pro'

export function registerCockpitEChartsTheme(): void {
  echarts.registerTheme(COCKPIT_ECHARTS_THEME, {
    backgroundColor: 'transparent',
    textStyle: {
      color: T.textSecondary,
      fontFamily: "'Inter Variable', 'Noto Sans SC', sans-serif",
    },
    title: {
      textStyle: {
        color: T.textPrimary,
        fontSize: 13,
        fontWeight: 600,
      },
    },
    legend: {
      textStyle: {
        color: T.textSecondary,
        fontSize: 11,
      },
    },
    tooltip: {
      backgroundColor: '#FFFFFF',
      borderColor: T.borderBase,
      borderWidth: 1,
      textStyle: {
        color: T.textPrimary,
        fontSize: 11,
        fontFamily: "'Inter Variable', 'Noto Sans SC', sans-serif",
      },
      extraCssText: `
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(15,23,42,0.08), 0 2px 4px rgba(15,23,42,0.04);
      `,
      padding: [8, 12],
      axisPointer: {
        type: 'line',
        lineStyle: {
          color: T.borderBase,
          width: 1,
          type: 'dashed',
        },
      },
    },
    categoryAxis: {
      axisLine: {
        lineStyle: {
          color: T.borderBase,
          width: 1,
        },
      },
      axisTick: { show: false },
      axisLabel: {
        color: T.textLabel,
        fontSize: 10,
        fontFamily: "'Inter Variable', 'Noto Sans SC', sans-serif",
      },
      splitLine: {
        show: true,
        lineStyle: {
          color: T.borderLight,
          width: 1,
          type: 'dashed',
        },
      },
    },
    valueAxis: {
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: T.textLabel,
        fontSize: 10,
        fontFamily: "'Inter Variable', 'Noto Sans SC', sans-serif",
      },
      splitLine: {
        lineStyle: {
          color: T.borderLight,
          width: 1,
        },
      },
    },
    color: [
      T.accentBlue,
      T.accentIndigo,
      T.toneSuccess,
      T.toneWarning,
      T.toneError,
      T.accentCyan,
    ],
    animation: true,
    animationDuration: 600,
    animationEasing: 'cubicOut',
    animationDurationUpdate: 400,
    animationEasingUpdate: 'cubicInOut',
    line: {
      smooth: true,
      symbolSize: 4,
      lineStyle: {
        width: 2,
      },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(26,86,219,0.15)' },
            { offset: 1, color: 'rgba(26,86,219,0.01)' },
          ],
        },
      },
      itemStyle: {
        borderWidth: 1,
        borderColor: '#FFFFFF',
      },
      emphasis: {
        focus: 'series',
        lineStyle: { width: 2.5 },
        itemStyle: {
          borderWidth: 2,
        },
      },
    },
    bar: {
      itemStyle: {
        borderRadius: [4, 4, 0, 0],
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: T.accentBlue },
            { offset: 1, color: T.accentIndigo },
          ],
        },
      },
    },
    gauge: {
      axisLine: {
        lineStyle: {
          width: 10,
          color: [
            [0.3, T.toneSuccess],
            [0.7, T.toneWarning],
            [1, T.toneError],
          ],
        },
      },
      splitLine: {
        distance: -8,
        length: 10,
        lineStyle: {
          color: T.borderLight,
          width: 1,
        },
      },
      axisTick: { show: false },
      axisLabel: {
        distance: 14,
        color: T.textLabel,
        fontSize: 9,
        fontFamily: "'Geist Mono', 'JetBrains Mono', monospace",
      },
      detail: {
        valueAnimation: true,
        formatter: '{value} ms',
        color: T.textPrimary,
        fontSize: 14,
        fontWeight: 600,
        fontFamily: "'Geist Mono', 'JetBrains Mono', monospace",
        offsetCenter: [0, '75%'],
      },
      title: {
        offsetCenter: [0, '92%'],
        color: T.textLabel,
        fontSize: 10,
      },
      pointer: {
        width: 4,
        length: '65%',
        itemStyle: {
          color: T.accentBlue,
        },
      },
      progress: {
        show: true,
        roundCap: true,
        width: 10,
        itemStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 1, y2: 0,
            colorStops: [
              { offset: 0, color: T.toneSuccess },
              { offset: 0.5, color: T.toneWarning },
              { offset: 1, color: T.toneError },
            ],
          },
        },
      },
    },
    pie: {
      itemStyle: {
        borderRadius: 6,
        borderColor: '#FFFFFF',
        borderWidth: 2,
      },
    },
  })
}
