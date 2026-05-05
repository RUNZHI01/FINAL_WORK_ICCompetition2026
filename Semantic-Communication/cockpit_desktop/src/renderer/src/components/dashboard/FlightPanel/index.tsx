import { WorldMapCard } from './WorldMapCard';
import { CockpitSwitch } from '../../ios/CockpitSwitch';
import s from './FlightPanel.module.css';

interface FlightPanelProps {
  aircraft: any;
  chinaTheater: boolean;
  setChinaTheater: (v: boolean) => void;
}

export function FlightPanel({ aircraft, chinaTheater, setChinaTheater }: FlightPanelProps) {
  const ap = aircraft.data;

  return (
    <div className={s.container}>
      <div className={s.mapWrap}>
        <WorldMapCard
          aircraft={aircraft}
          chinaTheater={chinaTheater}
          setChinaTheater={setChinaTheater}
        />
        {/* China theater toggle overlay */}
        <div className={s.mapControls} role="group" aria-label="Map theater selection">
          <span className={s.controlLabel}>中国战区</span>
          <CockpitSwitch
            checked={chinaTheater}
            onChange={setChinaTheater}
            size="small"
            aria-label={chinaTheater ? 'Disable China theater map' : 'Enable China theater map'}
          />
        </div>
        {/* Telemetry Overlay Bar */}
        {ap && (
          <div className={s.telemetryOverlay}>
            <div className={s.telemetryItem}>
              <span className={s.telemetryLabel}>位置源</span>
              <span className={s.telemetryValue}>{(ap.source_label ?? '上位机位置').replace('百度IP', '百度北斗高精度定位')}</span>
            </div>
            <div className={s.telemetryItem}>
              <span className={s.telemetryLabel}>经纬</span>
              <span className={s.telemetryValue}>
                {ap.position?.latitude != null && ap.position?.longitude != null
                  ? `${ap.position.latitude.toFixed(4)}, ${ap.position.longitude.toFixed(4)}`
                  : '—'}
              </span>
            </div>
            <div className={s.telemetryItem}>
              <span className={s.telemetryLabel}>航向</span>
              <span className={s.telemetryValue}>
                {ap.kinematics?.heading_deg != null
                  ? `${Number(ap.kinematics.heading_deg).toFixed(1)}°`
                  : '—'}
              </span>
            </div>
            <div className={s.telemetryItem}>
              <span className={s.telemetryLabel}>高度</span>
              <span className={s.telemetryValue}>
                {ap.kinematics?.altitude_m != null
                  ? `${Number(ap.kinematics.altitude_m).toFixed(1)} m`
                  : '—'}
              </span>
            </div>
            <div className={s.telemetryItem}>
              <span className={s.telemetryLabel}>速度</span>
              <span className={s.telemetryValue}>
                {ap.kinematics?.ground_speed_kph != null
                  ? `${Number(ap.kinematics.ground_speed_kph).toFixed(1)} kph`
                  : '—'}
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
