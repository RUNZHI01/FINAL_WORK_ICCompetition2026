import { useMemo } from 'react';
import { useSystemStatus } from '../hooks/useSystemStatus';
import { useDemoSnapshot } from '../hooks/useSnapshot';
import { useAircraftPosition } from '../hooks/useAircraftPosition';
import { useInferenceProgressPoll } from '../hooks/useInferenceProgress';
import { useAppStore } from '../stores/appStore';
import {
  useProbeBoard,
  useRunInference,
  useRunBaseline,
  useInjectFault,
  useRecover,
  useSwitchLinkProfile,
  useRunInferenceBatch,
} from '../hooks/useActions';
import { FlightPanel } from '../components/dashboard/FlightPanel';
import { SidebarPanel } from '../components/dashboard/SidebarPanel';
import { ExecutionModeCard } from '../components/dashboard/MissionStagePanel/ExecutionModeCard';
import { BoardTelemetryCard } from '../components/dashboard/MissionStagePanel/BoardTelemetryCard';
import { SnapshotStatsCard } from '../components/dashboard/MissionStagePanel/SnapshotStatsCard';
import { InferenceProgressCard } from '../components/dashboard/MissionStagePanel/InferenceProgressCard';
import { ComparisonCard } from '../components/dashboard/MissionStagePanel/ComparisonCard';
import { ActionToolbar } from '../components/dashboard/ActionToolbar';
import { PageTransition, StaggeredList, AnimatedListItem } from '../components/animations';
import s from './DashboardPage.module.css';

export function DashboardPage() {
  const system = useSystemStatus();
  const snapshot = useDemoSnapshot();
  const aircraft = useAircraftPosition();
  const inferenceProgress = useInferenceProgressPoll();

  const activeJobId = useAppStore((s) => s.activeJobId);
  const chinaTheater = useAppStore((s) => s.chinaTheater);
  const setChinaTheater = useAppStore((s) => s.setChinaTheater);

  const probeMut = useProbeBoard();
  const inferenceMut = useRunInference();
  const baselineMut = useRunBaseline();
  const faultMut = useInjectFault();
  const recoverMut = useRecover();
  const linkMut = useSwitchLinkProfile();
  const batchMut = useRunInferenceBatch();

  const handleRunInference = useMemo(
    () => () => inferenceMut.mutate({ imageIndex: 0, variant: 'current' }),
    [inferenceMut],
  );
  const handleRunBaseline = useMemo(
    () => () => baselineMut.mutate({ imageIndex: 0 }),
    [baselineMut],
  );

  return (
    <PageTransition className={s.root}>
      {/* Left Panel: Sidebar */}
      <div className={s.leftPanel}>
        <StaggeredList staggerDelay={0.06}>
          <AnimatedListItem>
            <SidebarPanel
              system={system}
              onRecover={() => recoverMut.mutate()}
              recoverPending={recoverMut.isPending}
              onSwitchProfile={(id) => linkMut.mutate(id)}
              switchPending={linkMut.isPending}
            />
          </AnimatedListItem>
        </StaggeredList>
      </div>

      {/* Center Area: Map + Bottom Cards */}
      <div className={s.centerArea}>
        <div className={s.mapArea}>
          <FlightPanel aircraft={aircraft} chinaTheater={chinaTheater} setChinaTheater={setChinaTheater} />
        </div>
        <div className={s.centerBottom}>
          <SnapshotStatsCard snapshot={snapshot} />
          <ComparisonCard system={system} />
        </div>
      </div>

      {/* Right Panel: Mission Stage Cards */}
      <div className={s.rightPanel}>
        <StaggeredList staggerDelay={0.08}>
          <AnimatedListItem>
            <ExecutionModeCard system={system} />
          </AnimatedListItem>
          <AnimatedListItem>
            <BoardTelemetryCard system={system} />
          </AnimatedListItem>
          <AnimatedListItem>
            <InferenceProgressCard
              activeJobId={activeJobId}
              inferenceProgress={inferenceProgress}
              system={system}
            />
          </AnimatedListItem>
        </StaggeredList>
      </div>

      {/* Bottom Action Bar */}
      <div className={s.actionBar}>
        <ActionToolbar
          system={system}
          activeJobId={activeJobId}
          onProbe={() => probeMut.mutate()}
          probePending={probeMut.isPending}
          onRunInference={handleRunInference}
          inferencePending={inferenceMut.isPending}
          onRunBaseline={handleRunBaseline}
          baselinePending={baselineMut.isPending}
          onInjectFault={(faultType) => faultMut.mutate(faultType)}
          faultPending={faultMut.isPending}
          onRecover={() => recoverMut.mutate()}
          recoverPending={recoverMut.isPending}
          onRunBatch={() => batchMut.mutate({})}
          batchPending={batchMut.isPending}
        />
      </div>
    </PageTransition>
  );
}
