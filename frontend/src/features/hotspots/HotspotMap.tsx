import { Fragment, useEffect, useState } from 'react'
import { latLngBounds, type LatLngTuple } from 'leaflet'
import {
  CircleMarker,
  MapContainer,
  Polygon,
  Popup,
  TileLayer,
  Tooltip,
  useMap,
  useMapEvents,
} from 'react-leaflet'
import simpleheat from 'simpleheat'
import { density, regionCenter, regionZoom } from './geography'
import type { Cluster, Point } from './api'
import vietnamBoundary from './vietnam-boundary.json'
import 'leaflet/dist/leaflet.css'
import './hotspots.css'

const tileUrl =
  import.meta.env.VITE_HOTSPOT_TILE_URL || 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
const attribution =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
const worldBounds = latLngBounds([
  [-85, -180],
  [85, 180],
])
const vietnamRings = vietnamBoundary.rings as LatLngTuple[][]
// Extend the overview to the southeastern extent of Trường Sa.
// https://dulichso.khanhhoa.gov.vn/article/bia-chu-quyen-quan-dao-truong-sa-tai-dao-song-tu-tay-va-dao-nam-yet-980
const vietnamBounds = latLngBounds(vietnamRings.flat()).extend([6.8333, 117.3333])
const vietnamMask: LatLngTuple[][] = [
  [
    [-85, -180],
    [-85, 180],
    [85, 180],
    [85, -180],
  ],
  ...vietnamRings,
]
// Label anchors and selected islands from the published Vietnamese gazetteer.
// https://www.mae.gov.vn/noidung/Lists/VBQPPL/Attachments/514/1_DanhMuc_TT_DiaDanh_BanHanh.pdf
const archipelagos: { name: string; label: LatLngTuple; islands: LatLngTuple[] }[] = [
  {
    name: 'Quần đảo Hoàng Sa',
    label: [16.4667, 112.225],
    islands: [
      [16.5356, 111.6061], // Hoàng Sa
      [15.7858, 111.1975], // Tri Tôn
      [16.8367, 112.3333], // Phú Lâm
      [16.6717, 112.7267], // Linh Côn
    ],
  },
  {
    name: 'Quần đảo Trường Sa',
    label: [8.8083, 114.005],
    islands: [
      [8.6467, 111.9183], // Trường Sa
      [11.43, 114.3297], // Song Tử Tây
      [10.18, 114.365], // Nam Yết
      [9.8858, 114.3292], // Sinh Tồn
      [8.9769, 113.7072], // Phan Vinh
      [7.8933, 112.9197], // An Bang
    ],
  },
]

function VietnamOverview() {
  return (
    <>
      <Polygon
        positions={vietnamMask}
        interactive={false}
        className="hotspot-vietnam-mask"
        pathOptions={{
          fillColor: '#eef3f6',
          fillOpacity: 1,
          fillRule: 'evenodd',
          stroke: false,
        }}
      />
      {archipelagos.map(({ name, label, islands }) => (
        <Fragment key={name}>
          {islands.map((position) => (
            <CircleMarker
              key={position.join(',')}
              center={position}
              interactive={false}
              radius={2.3}
              pathOptions={{ stroke: false, fillColor: '#337087', fillOpacity: 0.9 }}
            />
          ))}
          <CircleMarker
            center={label}
            interactive={false}
            radius={0}
            pathOptions={{ stroke: false, fill: false }}
          >
            <Tooltip
              permanent
              direction="bottom"
              offset={[0, 6]}
              opacity={1}
              className="hotspot-archipelago-label"
            >
              {name}
            </Tooltip>
          </CircleMarker>
        </Fragment>
      ))}
    </>
  )
}

function Basemap() {
  const [failed, setFailed] = useState(false)
  return (
    <>
      <TileLayer
        url={tileUrl}
        attribution={attribution}
        maxZoom={19}
        eventHandlers={{ tileerror: () => setFailed(true), tileload: () => setFailed(false) }}
      />
      {failed && (
        <p className="hotspot-tile-error" role="status">
          Bản đồ nền tạm thời không tải được.
        </p>
      )}
    </>
  )
}

function FitMap({
  points,
  region,
  vietnamOnly,
}: {
  points: Point[]
  region: string
  vietnamOnly: boolean
}) {
  const map = useMap()
  useEffect(() => {
    if (!vietnamOnly) return
    const fitVietnam = () => {
      map.setMinZoom(0)
      map.setMaxBounds(vietnamBounds.pad(0.12))
      map.fitBounds(vietnamBounds, { padding: [24, 24], animate: false })
      map.setMinZoom(map.getZoom())
    }
    fitVietnam()
    map.on('resize', fitVietnam)
    return () => {
      map.off('resize', fitVietnam)
    }
  }, [map, vietnamOnly])

  useEffect(() => {
    if (vietnamOnly) return
    map.setMinZoom(0)
    map.setMaxBounds(worldBounds)
    if (points.length) {
      const bounds = points.map(({ latitude, longitude }): LatLngTuple => [latitude, longitude])
      map.fitBounds(bounds, { padding: [34, 34], maxZoom: 15, animate: false })
    } else {
      map.setView(regionCenter(region), region ? regionZoom(region) : 6, { animate: false })
    }
  }, [map, points, region, vietnamOnly])
  return null
}

function HeatLayer({ points }: { points: Point[] }) {
  const map = useMap()
  useEffect(() => {
    const overlay = map.getPane('overlayPane')
    const canvas = document.createElement('canvas')
    if (!overlay || !canvas.getContext('2d', { willReadFrequently: true })) return
    canvas.className = 'hotspot-heat'
    canvas.setAttribute('aria-hidden', 'true')
    overlay.appendChild(canvas)
    const heat = new simpleheat(canvas).radius(32, 27).max(1).gradient({
      0.2: density.low.color,
      0.48: density.medium.color,
      0.74: density.high.color,
      1: density.very_high.color,
    })
    let frame = 0
    const draw = () => {
      const { x, y } = map.getSize()
      if (!x || !y) return
      const topLeft = map.containerPointToLayerPoint([0, 0])
      canvas.style.left = `${topLeft.x}px`
      canvas.style.top = `${topLeft.y}px`
      if (canvas.width !== x || canvas.height !== y) {
        canvas.width = x
        canvas.height = y
      }
      const positions = points.map(({ latitude, longitude, density_level }) => {
        const position = map.latLngToContainerPoint([latitude, longitude])
        return [position.x, position.y, density[density_level].weight] as [number, number, number]
      })
      heat.data(positions).draw(0.08)
    }
    const redraw = () => {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(draw)
    }
    const hide = () => {
      canvas.style.visibility = 'hidden'
    }
    const reveal = () => {
      canvas.style.visibility = ''
      redraw()
    }
    map.on('movestart', hide)
    map.on('moveend resize', reveal)
    redraw()
    return () => {
      map.off('movestart', hide)
      map.off('moveend resize', reveal)
      cancelAnimationFrame(frame)
      canvas.remove()
    }
  }, [map, points])
  return null
}

export function HotspotMap({
  points,
  clusters,
  region,
  vietnamOnly,
  selected,
  showHeat,
  showMarkers,
  onSelect,
}: {
  points: Point[]
  clusters: Cluster[]
  region: string
  vietnamOnly: boolean
  selected: string | null
  showHeat: boolean
  showMarkers: boolean
  onSelect: (id: string) => void
}) {
  return (
    <MapContainer
      center={regionCenter(region)}
      zoom={6}
      className="hotspot-map"
      aria-label="Bản đồ nhiệt thất lạc"
      scrollWheelZoom={false}
      zoomAnimation={false}
      zoomSnap={0.25}
      fadeAnimation={false}
      maxBoundsViscosity={1}
      maxBounds={worldBounds}
    >
      <Basemap />
      {vietnamOnly && <VietnamOverview />}
      <FitMap points={points} region={region} vietnamOnly={vietnamOnly} />
      {showHeat && <HeatLayer points={points} />}
      {showMarkers &&
        clusters.map((cluster) => (
          <CircleMarker
            key={cluster.cluster_id}
            center={[cluster.latitude, cluster.longitude]}
            pathOptions={{
              color: cluster.cluster_id === selected ? '#541f0e' : 'white',
              fillColor: density[cluster.density_level].color,
              fillOpacity: 0.9,
              weight: 3,
            }}
            radius={9}
          >
            <Popup>
              <strong>{cluster.location_name}</strong>
              <p>
                {cluster.event_count} báo cáo · {density[cluster.density_level].name}
              </p>
              {cluster.top_categories.length > 0 && (
                <p>{cluster.top_categories.map((item) => item.label).join(', ')}</p>
              )}
              {cluster.peak_time && <p>Khung giờ {cluster.peak_time.label}</p>}
              <button
                type="button"
                className="text-link"
                onClick={() => onSelect(cluster.cluster_id)}
              >
                Xem bài đăng liên quan
              </button>
            </Popup>
          </CircleMarker>
        ))}
    </MapContainer>
  )
}

function ChoosePin({ onChoose }: { onChoose: (position: LatLngTuple) => void }) {
  const map = useMapEvents({
    click: ({ latlng }) => onChoose([latlng.lat, latlng.lng]),
  })
  return (
    <button
      type="button"
      className="button button-secondary hotspot-pin-center"
      onClick={() => {
        const { lat, lng } = map.getCenter()
        onChoose([lat, lng])
      }}
    >
      Dùng tâm bản đồ
    </button>
  )
}

export function PinMap({
  region,
  pin,
  onChoose,
}: {
  region: string
  pin: LatLngTuple | null
  onChoose: (position: LatLngTuple) => void
}) {
  return (
    <MapContainer
      key={region}
      center={pin ?? regionCenter(region)}
      zoom={pin ? 15 : regionZoom(region)}
      className="hotspot-map hotspot-pin-map"
      aria-label="Bản đồ chọn nơi thất lạc"
      scrollWheelZoom={false}
    >
      <Basemap />
      {pin && (
        <CircleMarker
          center={pin}
          radius={10}
          pathOptions={{ color: '#a64319', fillOpacity: 0.8 }}
        />
      )}
      <ChoosePin onChoose={onChoose} />
    </MapContainer>
  )
}
