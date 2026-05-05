import React from 'react';
import { Progress as AntProgress, ProgressProps as AntProgressProps } from 'antd';
import { T } from '../../theme/tokens';

export interface IOSProgressProps extends Omit<AntProgressProps, 'strokeColor'> {
  variant?: 'primary' | 'success' | 'warning' | 'danger';
  showAnimation?: boolean;
}

const VARIANT_GRADIENTS: Record<string, { from: string; to: string }> = {
  primary: { from: T.accentBlue, to: T.accentIndigo },
  success: { from: T.toneSuccess, to: T.accentTeal },
  warning: { from: T.toneWarning, to: T.toneError },
  danger:  { from: T.toneError, to: T.toneError },
};

export const IOSProgress: React.FC<IOSProgressProps> = ({
  variant = 'primary',
  showAnimation = true,
  percent,
  style,
  ...props
}) => {
  const gradient = VARIANT_GRADIENTS[variant] ?? VARIANT_GRADIENTS.primary;

  return (
    <AntProgress
      percent={percent}
      strokeColor={{ '0%': gradient.from, '100%': gradient.to }}
      trailColor={T.bgSection}
      strokeWidth={4}
      showInfo={false}
      style={style}
      strokeLinecap="round"
      className={showAnimation ? 'progress-animated' : undefined}
      {...props}
    />
  );
};
