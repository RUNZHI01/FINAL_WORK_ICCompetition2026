import { ExecutionModeCard } from './ExecutionModeCard';
import { BoardTelemetryCard } from './BoardTelemetryCard';
import { InferenceProgressCard } from './InferenceProgressCard';
import s from './MissionStagePanel.module.css';

interface MissionStagePanelProps {
  system: any;
  inferenceProgress: any;
  activeJobId: string | null;
}

/**
 * Right panel content: Execution mode, board telemetry, inference progress.
 * SnapshotStatsCard and ComparisonCard are now in the center bottom area.
 */
export function MissionStagePanel({
  system,
  inferenceProgress,
  activeJobId,
}: MissionStagePanelProps) {
  return (
    <div className={s.panel}>
      <div className={s.primarySection}>
        <ExecutionModeCard system={system} />
      </div>
      <div className={s.secondarySection}>
        <BoardTelemetryCard system={system} />
        <InferenceProgressCard
          activeJobId={activeJobId}
          inferenceProgress={inferenceProgress}
          system={system}
        />
      </div>
    </div>
  );
}
