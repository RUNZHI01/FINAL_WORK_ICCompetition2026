import type { BoardAccessResponse } from '../api/types'

export type BoardReadinessTone = 'ready' | 'blocked' | 'warn' | 'info'

export type BoardReadinessItem = {
  key: string
  label: string
  value: string
  tone: BoardReadinessTone
  detail: string
}

function text(value: unknown): string {
  return String(value ?? '').trim()
}

function hasText(value: unknown): boolean {
  return text(value).length > 0
}

function normalizeTransportMode(value: unknown): 'tcp' | 'usrp' {
  return text(value).toLowerCase() === 'usrp' ? 'usrp' : 'tcp'
}

function normalizeJsccLinkMode(value: unknown): 'qpsk' | 'iq-direct' {
  const normalized = text(value).toLowerCase()
  return normalized === 'iq-direct' || normalized === 'iq' || normalized === 'analog' ? 'iq-direct' : 'qpsk'
}

function missingFieldsLabel(fields: string[] | undefined): string {
  const values = (fields ?? []).map((field) => text(field)).filter(Boolean)
  return values.length > 0 ? `缺 ${values.join(', ')}` : '待补全'
}

export function buildBoardReadinessItems(boardAccess: BoardAccessResponse | null | undefined): BoardReadinessItem[] {
  const transportMode = normalizeTransportMode(boardAccess?.transport_mode)
  const items: BoardReadinessItem[] = [
    boardAccess?.connection_ready
      ? {
          key: 'session',
          label: '板端会话',
          value: '已就绪',
          tone: 'ready',
          detail: 'SSH 会话字段已补齐。',
        }
      : {
          key: 'session',
          label: '板端会话',
          value: missingFieldsLabel(boardAccess?.missing_connection_fields),
          tone: 'blocked',
          detail: '补齐 SSH 会话后才能执行 live/USRP 推理。',
        },
  ]

  if (transportMode === 'usrp') {
    items.push(
      hasText(boardAccess?.remote_usrp_rx_dir)
        ? {
            key: 'usrp_rx',
            label: 'USRP RX',
            value: '已配置',
            tone: 'ready',
            detail: text(boardAccess?.remote_usrp_rx_dir),
          }
        : {
            key: 'usrp_rx',
            label: 'USRP RX',
            value: '缺 RX 目录',
            tone: 'blocked',
            detail: '设置 REMOTE_USRP_RX_DIR，板端解码后从该目录进入重建。',
          },
    )

    const linkMode = normalizeJsccLinkMode(boardAccess?.jscc_link_mode)
    items.push(
      linkMode === 'iq-direct'
        ? {
            key: 'jscc_link',
            label: 'JSCC 链路',
            value: 'IQ 直传默认',
            tone: 'ready',
            detail: 'latent 直接映射模拟 IQ 波形；QPSK 仍保留为兜底。',
          }
        : {
            key: 'jscc_link',
            label: 'JSCC 链路',
            value: 'QPSK 兜底',
            tone: 'warn',
            detail: '可靠字节链路仍可演示；IQ 直传稳定后应作为默认演示路径。',
          },
    )

    const hasHostInput = hasText(boardAccess?.local_usrp_image_dir) || hasText(boardAccess?.local_usrp_input_dir)
    items.push(
      hasHostInput
        ? {
            key: 'host_input',
            label: '图库输入',
            value: '已发现',
            tone: 'ready',
            detail: 'USRP 模式会按任务数量从原始图像/latent 输入目录取样。',
          }
        : {
            key: 'host_input',
            label: '图库输入',
            value: '未配置',
            tone: 'blocked',
            detail: 'USRP 模式需要上位机原图或 latent 输入目录。',
          },
    )
  } else {
    items.push(
      hasText(boardAccess?.remote_prerecorded_input_dir)
        ? {
            key: 'prerecorded_input',
            label: '预录输入',
            value: '已配置',
            tone: 'ready',
            detail: text(boardAccess?.remote_prerecorded_input_dir),
          }
        : {
            key: 'prerecorded_input',
            label: '预录输入',
            value: '未配置',
            tone: 'blocked',
            detail: '预录模式需要 REMOTE_INPUT_DIR 指向板端 latent 目录。',
          },
    )
  }

  return items
}
