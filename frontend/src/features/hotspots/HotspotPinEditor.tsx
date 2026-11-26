import { lazy, Suspense, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { LatLngTuple } from 'leaflet'
import { ApiFeedback } from '../../components/ui/live'
import { hotspotApi, type HotspotPin } from './api'
import { zones } from './geography'
import './hotspots.css'

const PinMap = lazy(() => import('./HotspotMap').then((module) => ({ default: module.PinMap })))

export function HotspotPinEditor({
  postId,
  region,
  onChange,
}: {
  postId?: string
  region: string
  onChange: (pin: HotspotPin | null | 'choosing') => void
}) {
  const saved = useQuery({
    queryKey: ['hotspots', 'my-pin', postId],
    queryFn: ({ signal }) => hotspotApi.pin(postId!, signal),
    enabled: Boolean(postId),
  })
  if (postId && !saved.isSuccess) {
    return (
      <ApiFeedback
        pending={saved.isPending}
        error={saved.error}
        retry={() => void saved.refetch()}
      />
    )
  }
  return <PinControls initial={saved.data ?? null} region={region} onChange={onChange} />
}

function PinControls({
  initial,
  region,
  onChange,
}: {
  initial: HotspotPin | null
  region: string
  onChange: (pin: HotspotPin | null | 'choosing') => void
}) {
  const [enabled, setEnabled] = useState(Boolean(initial))
  const [pin, setPin] = useState<LatLngTuple | null>(
    initial ? [initial.latitude, initial.longitude] : null,
  )
  const [zone, setZone] = useState(initial?.hotspot_zone ?? 'OTHER')
  function update(hotspot_zone: string, point: LatLngTuple | null) {
    onChange(point ? { hotspot_zone, latitude: point[0], longitude: point[1] } : 'choosing')
  }
  return (
    <div className="hotspot-pin-editor live-stack">
      <label className="hotspot-check">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(event) => {
            const checked = event.currentTarget.checked
            setEnabled(checked)
            if (checked) update(zone, pin)
            else onChange(null)
          }}
        />
        Góp vị trí gần đúng vào Bản đồ thất lạc
      </label>
      {enabled && (
        <>
          <p className="muted">
            Chọn một địa điểm công cộng gần nơi mất đồ. Vị trí được làm tròn và chỉ hiển thị theo
            nhóm báo cáo.
          </p>
          <label className="field">
            Loại địa điểm
            <select
              value={zone}
              onChange={(event) => {
                const next = event.currentTarget.value
                setZone(next)
                update(next, pin)
              }}
            >
              {zones.map(([id, label]) => (
                <option key={id} value={id}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <Suspense
            fallback={
              <div
                className="skeleton hotspot-map-placeholder"
                role="status"
                aria-label="Đang tải bản đồ"
              />
            }
          >
            <PinMap
              region={region}
              pin={pin}
              onChoose={([latitude, longitude]) => {
                const rounded: LatLngTuple = [
                  Number(latitude.toFixed(3)),
                  Number(longitude.toFixed(3)),
                ]
                setPin(rounded)
                update(zone, rounded)
              }}
            />
          </Suspense>
          <p className="muted" role="status">
            {pin
              ? 'Đã chọn vị trí gần đúng.'
              : 'Nhấn trên bản đồ hoặc dùng tâm bản đồ để đặt vị trí.'}
          </p>
        </>
      )}
    </div>
  )
}
