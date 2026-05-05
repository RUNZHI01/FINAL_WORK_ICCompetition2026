import React from 'react'
import { Switch as AntSwitch } from 'antd'
import { T } from '../../theme/tokens'

export interface CockpitSwitchProps {
  checked?: boolean
  onChange?: (checked: boolean) => void
  size?: 'small' | 'default'
  disabled?: boolean
  /** Show ON/OFF labels inside the switch */
  showLabels?: boolean
  /** Accessible label for screen readers */
  'aria-label'?: string
}

export const CockpitSwitch: React.FC<CockpitSwitchProps> = ({
  checked,
  onChange,
  size = 'small',
  disabled,
  'aria-label': ariaLabel,
}) => {
  return (
    <AntSwitch
      size={size}
      checked={checked}
      onChange={onChange}
      disabled={disabled}
      aria-label={ariaLabel || (checked ? 'Enabled' : 'Disabled')}
      style={{
        backgroundColor: checked ? T.accentBlue : T.borderBase,
        transition: `all ${T.durationNormal}ms ${T.easeSpring}`,
      }}
    />
  )
}
