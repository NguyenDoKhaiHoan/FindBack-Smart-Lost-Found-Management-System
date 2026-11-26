import type { Density } from './api'

export const regions = [
  ['VN-HN', 'Hà Nội'],
  ['VN-SG', 'TP. Hồ Chí Minh'],
  ['VN-DN', 'Đà Nẵng'],
  ['OTHER', 'Khu vực khác'],
] as const

export const zones = [
  ['LIBRARY', 'Thư viện'],
  ['CAFETERIA', 'Căn tin'],
  ['PARKING', 'Bãi gửi xe'],
  ['CLASSROOM', 'Khu giảng đường'],
  ['SPORTS', 'Khu thể thao'],
  ['DORMITORY', 'Ký túc xá'],
  ['OTHER', 'Địa điểm công cộng khác'],
] as const

const regionCenters: Record<string, [number, number]> = {
  'VN-HN': [21.03, 105.84],
  'VN-SG': [10.78, 106.7],
  'VN-DN': [16.06, 108.22],
}

export const regionCenter = (region: string) => regionCenters[region] ?? [16.2, 107.5]
export const regionZoom = (region: string) => (region in regionCenters ? 13 : 6)

export const density: Record<Density, { name: string; color: string; weight: number }> = {
  low: { name: 'Thấp', color: '#269557', weight: 0.23 },
  medium: { name: 'Trung bình', color: '#eab523', weight: 0.48 },
  high: { name: 'Cao', color: '#f38132', weight: 0.74 },
  very_high: { name: 'Rất cao', color: '#d63d27', weight: 1 },
}
