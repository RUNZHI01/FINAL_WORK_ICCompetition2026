import test from 'node:test'
import assert from 'node:assert/strict'

import { buildBoardReadinessItems } from './boardReadiness.js'

test('usrp iq-direct readiness exposes missing session and rx blockers', () => {
  const items = buildBoardReadinessItems({
    connection_ready: false,
    missing_connection_fields: ['password'],
    transport_mode: 'usrp',
    jscc_link_mode: 'iq-direct',
    local_usrp_image_dir: 'E:\\Main\\Career\\集创赛\\原始图像',
    remote_usrp_rx_dir: '',
  })

  assert.deepEqual(items, [
    {
      key: 'session',
      label: '板端会话',
      value: '缺 password',
      tone: 'blocked',
      detail: '补齐 SSH 会话后才能执行 live/USRP 推理。',
    },
    {
      key: 'usrp_rx',
      label: 'USRP RX',
      value: '缺 RX 目录',
      tone: 'blocked',
      detail: '设置 REMOTE_USRP_RX_DIR，板端解码后从该目录进入重建。',
    },
    {
      key: 'jscc_link',
      label: 'JSCC 链路',
      value: 'IQ 直传默认',
      tone: 'ready',
      detail: 'latent 直接映射模拟 IQ 波形；QPSK 仍保留为兜底。',
    },
    {
      key: 'host_input',
      label: '图库输入',
      value: '已发现',
      tone: 'ready',
      detail: 'USRP 模式会按任务数量从原始图像/latent 输入目录取样。',
    },
  ])
})

test('tcp prerecorded readiness reports prerecorded input path', () => {
  const items = buildBoardReadinessItems({
    connection_ready: true,
    transport_mode: 'tcp',
    remote_prerecorded_input_dir: '/home/user/Downloads/jscc-test/简化版latent',
  })

  assert.deepEqual(items, [
    {
      key: 'session',
      label: '板端会话',
      value: '已就绪',
      tone: 'ready',
      detail: 'SSH 会话字段已补齐。',
    },
    {
      key: 'prerecorded_input',
      label: '预录输入',
      value: '已配置',
      tone: 'ready',
      detail: '/home/user/Downloads/jscc-test/简化版latent',
    },
  ])
})
