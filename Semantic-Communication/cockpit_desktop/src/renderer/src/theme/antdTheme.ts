import { theme } from 'antd'
import { T } from './tokens'

/**
 * Ant Design theme config — Premium Tech Dashboard aesthetic.
 * Derived from the single source of truth (tokens.ts).
 */
export const antdThemeConfig = {
  algorithm: theme.defaultAlgorithm,
  token: {
    colorPrimary: T.accentBlue,
    colorInfo: T.accentBlue,
    colorWarning: T.toneWarning,
    colorError: T.toneError,
    colorSuccess: T.toneSuccess,
    colorBgLayout: T.bgPrimary,
    colorBgContainer: T.bgCard,
    colorBgElevated: '#FFFFFF',
    colorBorder: T.borderBase,
    colorBorderSecondary: T.borderLight,
    colorText: T.textPrimary,
    colorTextSecondary: T.textSecondary,
    colorTextTertiary: T.textLabel,
    borderRadius: T.radiusMd,
    fontFamily:
      "'Inter Variable', 'Noto Sans SC', system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
    fontSize: 14,
    lineHeight: 1.7,
  },
  components: {
    Button: {
      borderRadius: T.radiusMd,
      controlHeight: 40,
      fontSize: 14,
    },
    Table: {
      colorBgContainer: 'transparent',
      headerBg: 'rgba(26,86,219,0.04)',
      headerColor: T.textLabel,
      rowHoverBg: 'rgba(26,86,219,0.04)',
      borderColor: T.borderLight,
      fontSize: 13,
    },
    Descriptions: {
      labelColor: T.textLabel,
      contentColor: T.textSecondary,
      fontSize: 13,
    },
    Steps: {
      colorPrimary: T.accentBlue,
      dotSize: 6,
      fontSize: 13,
    },
    Tabs: {
      colorPrimary: T.accentBlue,
      colorText: T.textSecondary,
      colorTextDisabled: T.textMuted,
      horizontalItemPadding: '6px 12px',
      fontSize: 13,
      horizontalMargin: '0 8px 0 0',
    },
    Tag: {
      borderRadiusSM: 6,
    },
    Progress: {
      remainingColor: '#E8EDF3',
    },
    Statistic: {
      contentFontSize: 16,
      titleFontSize: 13,
    },
  },
}
