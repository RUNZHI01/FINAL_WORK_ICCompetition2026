import React from 'react';
import { Switch as AntSwitch, SwitchProps as AntSwitchProps } from 'antd';
import { T } from '../../theme/tokens';

export interface IOSSwitchProps extends Omit<AntSwitchProps, 'className'> {
  size?: 'small' | 'default';
}

export const IOSSwitch: React.FC<IOSSwitchProps> = ({
  size = 'default',
  style,
  ...props
}) => {
  return (
    <AntSwitch
      size={size}
      style={{
        backgroundColor: props.checked ? T.toneSuccess : T.borderBase,
        transition: `all ${T.durationNormal}ms ${T.easeStandard}`,
        minWidth: size === 'small' ? 44 : 51,
        height: size === 'small' ? 24 : 28,
        ...style,
      }}
      {...props}
    />
  );
};
