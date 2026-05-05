import { Button, Dropdown } from 'antd';
import { ScaleOnHover } from '../../animations';
import { Icons } from '../../icons';
import s from './ActionToolbar.module.css';

interface ActionToolbarProps {
  system: any;
  activeJobId: string | null;
  onProbe: () => void;
  probePending: boolean;
  onRunInference: () => void;
  inferencePending: boolean;
  onRunBaseline: () => void;
  baselinePending: boolean;
  onInjectFault: (faultType: string) => void;
  faultPending: boolean;
  onRecover: () => void;
  recoverPending: boolean;
  onRunBatch: () => void;
  batchPending: boolean;
}

export function ActionToolbar({
  system,
  activeJobId,
  onProbe,
  probePending,
  onRunInference,
  inferencePending,
  onRunBaseline,
  baselinePending,
  onInjectFault,
  faultPending,
  onRecover,
  recoverPending,
  onRunBatch,
  batchPending,
}: ActionToolbarProps) {
  const gate = system.data?.job_manifest_gate;
  const gateAllow = gate?.verdict === 'allow';

  return (
    <div className={s.toolbar} role="toolbar" aria-label="操作工具栏">
      {/* Probe group */}
      <ScaleOnHover>
        <Button
          size="small"
          loading={probePending}
          onClick={onProbe}
          icon={<Icons.Search size={14} aria-hidden="true" />}
          aria-label="探板 - 查看板卡状态"
        >
          探板
        </Button>
      </ScaleOnHover>

      <div className={s.separator} role="separator" aria-orientation="vertical" />

      {/* Inference group */}
      <ScaleOnHover>
        <Button
          size="small"
          type="primary"
          loading={inferencePending}
          disabled={!gateAllow || !!activeJobId}
          onClick={onRunInference}
          icon={<Icons.Play size={14} aria-hidden="true" />}
          className={s.primaryAction}
          aria-label={gateAllow ? '运行推理 current 版本' : '推理当前版本 - 闸机未开启'}
        >
          推理 (current)
        </Button>
      </ScaleOnHover>
      <ScaleOnHover>
        <Button
          size="small"
          loading={baselinePending}
          disabled={!!activeJobId}
          onClick={onRunBaseline}
          icon={<Icons.RotateCcw size={14} aria-hidden="true" />}
          aria-label="运行推理 baseline 版本"
        >
          推理 (baseline)
        </Button>
      </ScaleOnHover>

      <ScaleOnHover>
        <Button
          size="small"
          loading={batchPending}
          disabled={!gateAllow || !!activeJobId || batchPending}
          onClick={onRunBatch}
          icon={<Icons.Play size={14} aria-hidden="true" />}
          aria-label="批量加密推理 300 张"
        >
          批量推理 (300)
        </Button>
      </ScaleOnHover>

      <div className={s.separator} role="separator" aria-orientation="vertical" />

      {/* Fault group */}
      <Dropdown
        menu={{
          items: [
            { key: 'wrong_sha', label: 'wrong_sha', onClick: () => onInjectFault('wrong_sha') },
            { key: 'illegal_param', label: 'illegal_param', onClick: () => onInjectFault('illegal_param') },
            { key: 'heartbeat_timeout', label: 'heartbeat_timeout', onClick: () => onInjectFault('heartbeat_timeout') },
          ],
        }}
      >
        <ScaleOnHover>
          <Button
            size="small"
            loading={faultPending}
            icon={<Icons.AlertTriangle size={14} aria-hidden="true" />}
            aria-label="故障注入菜单"
          >
            故障注入
          </Button>
        </ScaleOnHover>
      </Dropdown>

      <div className={s.separator} role="separator" aria-orientation="vertical" />

      {/* Recovery group */}
      <ScaleOnHover>
        <Button
          size="small"
          danger
          loading={recoverPending}
          onClick={onRecover}
          icon={<Icons.Power size={14} aria-hidden="true" />}
          aria-label="安全停止并收口"
        >
          SAFE_STOP 收口
        </Button>
      </ScaleOnHover>
    </div>
  );
}
