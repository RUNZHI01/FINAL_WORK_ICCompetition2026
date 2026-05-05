import { LinkDirectorCard } from './LinkDirectorCard';
import { SafetyCard } from './SafetyCard';
import { OperatorCueCard } from './OperatorCueCard';
import { JobManifestCard } from './JobManifestCard';
import { EventSpineCard } from './EventSpineCard';
import s from './SidebarPanel.module.css';

interface SidebarPanelProps {
  system: any;
  onRecover: () => void;
  recoverPending: boolean;
  onSwitchProfile: (profileId: string) => void;
  switchPending: boolean;
}

export function SidebarPanel({
  system,
  onRecover,
  recoverPending,
  onSwitchProfile,
  switchPending,
}: SidebarPanelProps) {
  return (
    <div className={s.panel}>
      <div className={s.topSection}>
        <LinkDirectorCard
          system={system}
          onSwitchProfile={onSwitchProfile}
          switchPending={switchPending}
        />
        <SafetyCard system={system} onRecover={onRecover} recoverPending={recoverPending} />
      </div>
      <div className={s.bottomSection}>
        <OperatorCueCard system={system} />
        <JobManifestCard system={system} />
        <EventSpineCard system={system} />
      </div>
    </div>
  );
}
