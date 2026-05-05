import { WorldMapStage } from '../../WorldMapStage'
import { SkeletonCard } from '../../loading'

interface WorldMapCardProps {
  aircraft: any
  chinaTheater: boolean
  setChinaTheater: (v: boolean) => void
}

export function WorldMapCard({ aircraft, chinaTheater, setChinaTheater: _setChinaTheater }: WorldMapCardProps) {
  return (
    <>
      {aircraft.isPending ? (
        <SkeletonCard height={200} />
      ) : (
        <div style={{ width: '100%', height: '100%', position: 'relative' }}>
          <WorldMapStage aircraft={aircraft.data ?? undefined} chinaTheater={chinaTheater} height="100%" />
        </div>
      )}
    </>
  )
}
