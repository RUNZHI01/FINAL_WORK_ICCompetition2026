export type AuthDisplayState = {
  known: boolean
  enabled: boolean
  label: string
}

export function resolveAuthDisplayState(
  controlEnabled: boolean | undefined,
  statusEnabled: boolean | null | undefined,
): AuthDisplayState {
  const source = controlEnabled ?? statusEnabled
  const known = source != null
  const enabled = Boolean(source)
  return {
    known,
    enabled,
    label: enabled ? 'ML-DSA + SM2' : '未启用',
  }
}
