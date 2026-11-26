import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Activity, ChartNoAxesColumn, Download, Layers, MapPin, RefreshCw } from 'lucide-react'
import { ApiFeedback } from '../../components/ui/live'
import { EmptyState, PageHeading } from '../../components/ui/shared'
import { postsApi } from '../../lib/api/system'
import {
  hotspotApi,
  type Analysis,
  type AlgorithmConfig,
  type Count,
  type Filters,
  type GroupBy,
} from './api'
import { density, regions, zones } from './geography'
import './hotspots.css'

const HotspotMap = lazy(() =>
  import('./HotspotMap').then((module) => ({ default: module.HotspotMap })),
)
const emptyPoints = [] as Analysis['heatmap']
const initialFilters: Filters = {
  period: '',
  category_id: '',
  location_id: '',
  zone: '',
  start_date: '',
  end_date: '',
  group_by: 'day',
}
const periods = [
  ['', 'Kỳ mặc định'],
  ['7', '7 ngày'],
  ['30', '30 ngày'],
  ['90', '90 ngày'],
]
const densityEntries = Object.entries(density)

const formatter = new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 1 })
const displayDate = (label: string) => label.split('-').reverse().join('/')
const signedPercent = (number: number) => `${number > 0 ? '+' : ''}${formatter.format(number)}%`
const fold = (text: string) =>
  text.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase().replaceAll('đ', 'd')

export function PublicHotspotsPage() {
  return (
    <div className="container page-container">
      <PageHeading
        title="Bản đồ thất lạc"
        description="Xem các khu vực có nhiều báo cáo mất đồ theo dữ liệu FindBack."
      />
      <HotspotDashboard />
    </div>
  )
}

export function HotspotDashboard({ admin = false }: { admin?: boolean }) {
  const [filters, setFilters] = useState(initialFilters)
  const [dates, setDates] = useState({ start_date: '', end_date: '' })
  const [area, setArea] = useState('')
  const [selected, setSelected] = useState<string | null>(null)
  const [showHeat, setShowHeat] = useState(true)
  const [showMarkers, setShowMarkers] = useState(true)
  const detailsSection = useRef<HTMLElement>(null)
  const queryClient = useQueryClient()
  const queryKey = ['hotspots', admin, filters] as const
  const analysis = useQuery({
    queryKey,
    queryFn: ({ signal }) => hotspotApi.analyze(admin, filters, signal),
    staleTime: 60_000,
  })
  const catalog = useQuery({
    queryKey: ['categories'],
    queryFn: ({ signal }) => postsApi.categories(signal),
  })
  const areaQuery = fold(area.trim())
  const clusters = useMemo(
    () =>
      analysis.data?.clusters.filter((cluster) =>
        fold(cluster.location_name).includes(areaQuery),
      ) ?? [],
    [analysis.data, areaQuery],
  )
  const chosen = clusters.find((cluster) => cluster.cluster_id === selected)
  const chosenId = chosen?.cluster_id
  useEffect(() => {
    if (chosenId) {
      detailsSection.current?.focus({ preventScroll: true })
      detailsSection.current?.scrollIntoView?.({ block: 'start' })
    }
  }, [chosenId])
  const detail = useQuery({
    queryKey: ['hotspots', admin, filters, 'detail', chosen?.cluster_id],
    queryFn: ({ signal }) => hotspotApi.detail(admin, chosen!.cluster_id, filters, signal),
    enabled: Boolean(chosen),
  })
  const refresh = useMutation({
    mutationFn: hotspotApi.recalculate,
    onSuccess: async (data, recalculated) => {
      setSelected(null)
      queryClient.setQueryData(['hotspots', true, recalculated], data)
      await queryClient.invalidateQueries({ queryKey: ['hotspots', false] })
    },
  })
  const download = useMutation({
    mutationFn: hotspotApi.export,
    onSuccess: (blob) => {
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = 'findback-hotspots.csv'
      link.click()
      window.setTimeout(() => URL.revokeObjectURL(url), 1000)
    },
  })

  function change<Key extends keyof Filters>(key: Key, value: Filters[Key]) {
    setSelected(null)
    setFilters((current) => ({ ...current, [key]: value }))
  }

  return (
    <div className="hotspot-dashboard">
      <section className="panel hotspot-filters" aria-label="Bộ lọc thất lạc">
        <label className="field">
          Khoảng thời gian
          <select
            value={filters.period}
            onChange={(event) => {
              setSelected(null)
              setDates({ start_date: '', end_date: '' })
              setFilters({
                ...filters,
                period: event.currentTarget.value,
                start_date: '',
                end_date: '',
              })
            }}
          >
            {periods.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Danh mục đồ vật
          <select
            value={filters.category_id}
            onChange={(event) => change('category_id', event.currentTarget.value)}
          >
            <option value="">Tất cả danh mục</option>
            {catalog.data?.map((row) => (
              <option value={row.id} key={row.id}>
                {row.name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Khu vực
          <select
            value={filters.location_id}
            onChange={(event) => change('location_id', event.currentTarget.value)}
          >
            <option value="">Tất cả khu vực</option>
            {regions.map(([id, label]) => (
              <option key={id} value={id}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Loại địa điểm
          <select
            value={filters.zone}
            onChange={(event) => change('zone', event.currentTarget.value)}
          >
            <option value="">Tất cả địa điểm</option>
            {zones.map(([id, label]) => (
              <option key={id} value={id}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <ApiFeedback error={catalog.error} retry={() => void catalog.refetch()} />
        {admin && (
          <form
            className="hotspot-dates"
            onSubmit={(event) => {
              event.preventDefault()
              setSelected(null)
              setFilters({ ...filters, ...dates, period: '' })
            }}
          >
            <label className="field">
              Từ ngày
              <input
                type="date"
                required
                min="2000-01-01"
                max={dates.end_date || '2199-12-31'}
                value={dates.start_date}
                onChange={(event) => setDates({ ...dates, start_date: event.currentTarget.value })}
              />
            </label>
            <label className="field">
              Đến hết ngày
              <input
                type="date"
                required
                min={dates.start_date || '2000-01-01'}
                max="2199-12-31"
                value={dates.end_date}
                onChange={(event) => setDates({ ...dates, end_date: event.currentTarget.value })}
              />
            </label>
            <button className="button button-secondary" type="submit">
              Áp dụng ngày
            </button>
          </form>
        )}
      </section>
      {(analysis.isPending || analysis.error) && (
        <section className="panel live-stack" aria-label="Trạng thái phân tích">
          <ApiFeedback
            pending={analysis.isPending}
            error={analysis.error}
            retry={() => void analysis.refetch()}
          />
          {analysis.isPending && <div className="hotspot-map-placeholder skeleton" />}
        </section>
      )}
      {analysis.data && (
        <>
          <div className="hotspot-context">
            <p className="muted">
              {displayDate(analysis.data.period.start_date)} –{' '}
              {displayDate(analysis.data.period.end_date)} · Giờ Việt Nam
            </p>
            {analysis.data.is_demo && <strong className="hotspot-demo">Dữ liệu giả lập</strong>}
            {analysis.data.truncated && (
              <p className="muted">
                Đã giới hạn số báo cáo hoặc điểm nóng xử lý. Thu hẹp bộ lọc để xem chi tiết.
              </p>
            )}
          </div>
          <Metrics analysis={analysis.data} admin={admin} />
          <div className="hotspot-main">
            <section className="panel hotspot-map-panel">
              <div className="hotspot-panel-heading">
                <h2>
                  <MapPin size={20} aria-hidden="true" /> Bản đồ mật độ
                </h2>
                <div className="hotspot-toggles">
                  <label className="hotspot-check">
                    <input
                      type="checkbox"
                      checked={showHeat}
                      onChange={(event) => setShowHeat(event.currentTarget.checked)}
                    />{' '}
                    Bản đồ nhiệt
                  </label>
                  <label className="hotspot-check">
                    <input
                      type="checkbox"
                      checked={showMarkers}
                      onChange={(event) => setShowMarkers(event.currentTarget.checked)}
                    />{' '}
                    Điểm nóng
                  </label>
                </div>
              </div>
              <Suspense
                fallback={
                  <div
                    className="hotspot-map-placeholder skeleton"
                    role="status"
                    aria-label="Đang tải bản đồ"
                  />
                }
              >
                <HotspotMap
                  points={areaQuery ? clusters : (analysis.data?.heatmap ?? emptyPoints)}
                  clusters={clusters}
                  selected={selected}
                  region={filters.location_id}
                  showHeat={showHeat}
                  showMarkers={showMarkers}
                  onSelect={setSelected}
                />
              </Suspense>
              <div className="hotspot-legend" aria-label="Chú giải mật độ">
                {densityEntries.map(([id, level]) => (
                  <span key={id}>
                    <i style={{ backgroundColor: level.color }} aria-hidden="true" /> {level.name}
                  </span>
                ))}
              </div>
              <p className="muted hotspot-note">
                Màu phản ánh số báo cáo quá khứ trong kỳ. Tâm cụm được làm tròn để bảo vệ vị trí
                từng báo cáo.
              </p>
            </section>
            <aside className="panel hotspot-list" aria-label="Danh sách điểm nóng">
              <h2>
                <Layers size={20} aria-hidden="true" /> Điểm nóng
              </h2>
              <label className="field">
                Tìm khu vực trên bản đồ
                <input
                  type="search"
                  placeholder="Ví dụ: thư viện"
                  value={area}
                  onChange={(event) => setArea(event.currentTarget.value)}
                />
              </label>
              {!clusters.length && (
                <EmptyState
                  title={area ? 'Không có khu vực khớp từ khóa' : 'Chưa có cụm đủ dữ liệu'}
                  action={
                    !admin && !area ? (
                      <Link className="text-link" to="/dang-tin?loai=lost">
                        Đăng tin mất đồ
                      </Link>
                    ) : undefined
                  }
                >
                  {area
                    ? 'Thử tên địa điểm hoặc thành phố khác.'
                    : 'Thử mở rộng khoảng thời gian hoặc bỏ bớt bộ lọc.'}
                </EmptyState>
              )}
              <ul className="hotspot-ranked">
                {clusters.map((cluster) => (
                  <li key={cluster.cluster_id}>
                    <button
                      type="button"
                      aria-pressed={selected === cluster.cluster_id}
                      onClick={() => setSelected(cluster.cluster_id)}
                    >
                      <i
                        style={{ backgroundColor: density[cluster.density_level].color }}
                        aria-hidden="true"
                      />
                      <span>
                        {cluster.location_name}
                        <small>{density[cluster.density_level].name} · Xem tin liên quan</small>
                      </span>
                      <strong>{formatter.format(cluster.event_count)}</strong>
                    </button>
                  </li>
                ))}
              </ul>
            </aside>
          </div>
          {chosen && (
            <section
              className="panel hotspot-related"
              aria-label="Bài đăng liên quan"
              ref={detailsSection}
              tabIndex={-1}
            >
              <h2>{chosen.location_name}</h2>
              <p className="muted">
                {chosen.event_count} báo cáo · {density[chosen.density_level].name}
                {chosen.peak_time && ` · Khung giờ ${chosen.peak_time.label}`}
              </p>
              {chosen.top_categories.length > 0 && (
                <p>
                  Danh mục phổ biến{' '}
                  {chosen.top_categories.map((category) => category.label).join(', ')}
                </p>
              )}
              {chosen.trend && (
                <p>So với cụm cùng khu vực kỳ trước {signedPercent(chosen.trend.change_percent)}</p>
              )}
              {chosen.timeline.length > 0 && (
                <Timeline title="Báo cáo theo kỳ trong cụm" values={chosen.timeline} />
              )}
              <ApiFeedback
                pending={detail.isPending}
                error={detail.error}
                retry={() => void detail.refetch()}
              />
              {detail.data && (
                <ul className="hotspot-related-list">
                  {detail.data.related_posts.map((post) => (
                    <li key={post.id}>
                      <Link className="text-link" to={`/do-vat/${post.id}`}>
                        {post.title}
                      </Link>
                      <small className="muted">{displayDate(post.event_day)}</small>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}
          {admin && (
            <Charts
              analysis={analysis.data}
              groupBy={filters.group_by}
              onGroup={(group) => change('group_by', group)}
            />
          )}
        </>
      )}
      {admin && (
        <>
          <section className="panel hotspot-actions" aria-label="Tác vụ phân tích">
            <button
              type="button"
              className="button button-primary"
              disabled={refresh.isPending}
              onClick={() => refresh.mutate(filters)}
            >
              <RefreshCw size={17} aria-hidden="true" />{' '}
              {refresh.isPending ? 'Đang phân tích…' : 'Phân tích lại'}
            </button>
            <button
              type="button"
              className="button button-secondary"
              disabled={download.isPending || !analysis.data}
              onClick={() => download.mutate(filters)}
            >
              <Download size={17} aria-hidden="true" /> Xuất CSV
            </button>
            {refresh.isSuccess && <p role="status">Đã cập nhật kết quả phân tích.</p>}
            <ApiFeedback error={refresh.error ?? download.error} />
          </section>
          <ConfigPanel />
        </>
      )}
    </div>
  )
}

function Metrics({ analysis, admin }: { analysis: Analysis; admin: boolean }) {
  const stats = analysis.statistics
  const entries = [
    [admin ? 'Báo cáo có vị trí' : 'Báo cáo trong các cụm', formatter.format(stats.total_events)],
    ['Điểm nóng', formatter.format(stats.total_hotspots)],
    ['Cụm mật độ cao hoặc rất cao', formatter.format(stats.high_density_areas)],
  ]
  if (admin)
    entries.push(
      ['Khu vực nhiều báo cáo nhất', stats.top_areas[0]?.label ?? '—'],
      ['Danh mục nhiều báo cáo nhất', stats.categories[0]?.label ?? '—'],
      [
        'So với kỳ trước',
        stats.trend ? signedPercent(stats.trend.change_percent) : 'Chưa đủ dữ liệu',
      ],
    )
  return (
    <dl className="hotspot-metrics">
      {entries.map(([label, value]) => (
        <div className="panel hotspot-metric" key={label}>
          <dt>{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  )
}

function Bars({ title, values }: { title: string; values: Count[] }) {
  const maximum = Math.max(1, ...values.map((row) => row.count))
  return (
    <section className="panel hotspot-chart">
      <h3>{title}</h3>
      {values.length ? (
        <ul className="hotspot-bars">
          {values.map(({ label, count }) => (
            <li key={label}>
              <span>{label}</span>
              <strong>{formatter.format(count)}</strong>
              <div className="hotspot-bar-track" aria-hidden="true">
                <span style={{ width: `${(100 * count) / maximum}%` }} />
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">Chưa có báo cáo trong kỳ.</p>
      )}
    </section>
  )
}

function Timeline({ title, values }: { title: string; values: Count[] }) {
  if (!values.length) return null
  const maximum = Math.max(1, ...values.map((row) => row.count))
  const coordinates = values.map((row, index) => [
    18 + (488 * index) / Math.max(1, values.length - 1),
    90 - (67 * row.count) / maximum,
  ])
  return (
    <div className="hotspot-timeline">
      <h3>{title}</h3>
      <svg viewBox="0 0 524 102" aria-hidden="true">
        <path d="M18 23H506 M18 56H506 M18 90H506" stroke="#e9e1db" fill="none" />
        <polyline
          points={coordinates.map((point) => point.join(',')).join(' ')}
          fill="none"
          stroke="#ce581d"
          strokeWidth="2.5"
        />
        {coordinates.map(([x, y], index) => (
          <circle
            key={values[index].label}
            cx={x}
            cy={y}
            r={values.length > 60 ? 1 : 2.8}
            fill="#bf4d16"
          >
            <title>
              {displayDate(values[index].label)} · {values[index].count} báo cáo
            </title>
          </circle>
        ))}
      </svg>
      <div className="hotspot-timeline-dates muted">
        <span>{displayDate(values[0].label)}</span>
        <span>{displayDate(values[values.length - 1].label)}</span>
      </div>
      <details>
        <summary>Xem bảng số liệu</summary>
        <table>
          <thead>
            <tr>
              <th>Mốc thời gian</th>
              <th>Báo cáo</th>
            </tr>
          </thead>
          <tbody>
            {values.map((row) => (
              <tr key={row.label}>
                <td>{displayDate(row.label)}</td>
                <td>{row.count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  )
}

function Charts({
  analysis,
  groupBy,
  onGroup,
}: {
  analysis: Analysis
  groupBy: GroupBy
  onGroup: (group: GroupBy) => void
}) {
  const stats = analysis.statistics
  return (
    <>
      <section className="panel hotspot-chart">
        <div className="hotspot-panel-heading">
          <h2>
            <Activity size={20} aria-hidden="true" /> Xu hướng thất lạc
          </h2>
          <label className="field">
            Gộp theo
            <select
              value={groupBy}
              onChange={(event) => onGroup(event.currentTarget.value as GroupBy)}
            >
              <option value="day">Ngày</option>
              <option value="week">Tuần</option>
              <option value="month">Tháng</option>
            </select>
          </label>
        </div>
        <Timeline title="Số báo cáo qua thời gian" values={stats.timeline} />
        <p className="muted">
          Kỳ so sánh {displayDate(analysis.previous_period.start_date)} –{' '}
          {displayDate(analysis.previous_period.end_date)} · {stats.noise_events ?? 0} báo cáo ngoài
          cụm.
        </p>
      </section>
      <div className="hotspot-charts-grid">
        <Bars title="5 khu vực có nhiều báo cáo" values={stats.top_areas} />
        <Bars title="Danh mục đồ vật" values={stats.categories} />
        <Bars
          title="Phân bố theo khung giờ"
          values={[...stats.hours].sort((a, b) => a.label.localeCompare(b.label))}
        />
        <Bars title="So sánh theo khu vực" values={stats.regions} />
      </div>
      <section className="panel hotspot-chart">
        <h2>
          <ChartNoAxesColumn size={20} aria-hidden="true" /> Nhận xét từ dữ liệu
        </h2>
        {analysis.insights.length ? (
          <ul className="hotspot-insights">
            {analysis.insights.map((insight) => (
              <li key={insight}>{insight}</li>
            ))}
          </ul>
        ) : (
          <p className="muted">Chưa có đủ dữ liệu để nhận xét.</p>
        )}
      </section>
    </>
  )
}

const configFields = [
  ['eps_meters', 'Bán kính (m)', 50, 1000],
  ['min_samples', 'Báo cáo tối thiểu', 3, 50],
  ['period_days', 'Kỳ mặc định (ngày)', 7, 90],
  ['medium_count', 'Mức trung bình từ', 4, 500],
  ['high_count', 'Mức cao từ', 5, 750],
  ['very_high_count', 'Mức rất cao từ', 6, 1000],
] as const

function ConfigPanel() {
  const queryClient = useQueryClient()
  const config = useQuery({
    queryKey: ['hotspots', 'config'],
    queryFn: ({ signal }) => hotspotApi.config(signal),
  })
  const [invalid, setInvalid] = useState(false)
  const save = useMutation({
    mutationFn: hotspotApi.update,
    onSuccess: async (data) => {
      queryClient.setQueryData(['hotspots', 'config'], data)
      await queryClient.invalidateQueries({ queryKey: ['hotspots'] })
    },
  })
  return (
    <details className="panel hotspot-config">
      <summary>Cấu hình thuật toán DBSCAN</summary>
      <p className="muted">
        Ngưỡng mật độ phải tăng dần và từ mức báo cáo tối thiểu trở lên. Bản đồ công khai luôn yêu
        cầu ít nhất năm người báo cáo khác nhau.
      </p>
      <ApiFeedback
        pending={config.isPending}
        error={config.error}
        retry={() => void config.refetch()}
      />
      {config.data && (
        <form
          className="hotspot-config-form"
          key={JSON.stringify(config.data)}
          onSubmit={(event) => {
            event.preventDefault()
            const data = new FormData(event.currentTarget)
            const next = Object.fromEntries(
              configFields.map(([key]) => [key, Number(data.get(key))]),
            ) as unknown as AlgorithmConfig
            const valid =
              next.min_samples <= next.medium_count &&
              next.medium_count < next.high_count &&
              next.high_count < next.very_high_count
            setInvalid(!valid)
            if (valid) save.mutate(next)
          }}
        >
          {configFields.map(([key, label, min, max]) => (
            <label className="field" key={key}>
              {label}
              <input
                type="number"
                name={key}
                min={min}
                max={max}
                step={1}
                required
                defaultValue={config.data[key]}
              />
            </label>
          ))}
          <button type="submit" className="button button-primary" disabled={save.isPending}>
            Lưu cấu hình
          </button>
        </form>
      )}
      {invalid && (
        <p role="alert" className="error-state">
          Kiểm tra ngưỡng mật độ và số báo cáo tối thiểu.
        </p>
      )}
      <ApiFeedback error={save.error} />
      {save.isSuccess && <p role="status">Đã lưu cấu hình DBSCAN.</p>}
    </details>
  )
}
