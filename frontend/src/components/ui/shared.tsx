import type { ReactNode } from 'react'
import { ArrowRight, Search, ShieldCheck } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { useState } from 'react'

export function Brand({ light = false }: { light?: boolean }) {
  return (
    <Link
      to="/"
      className={`brand${light ? ' brand-light' : ''}`}
      aria-label="FindBack — Trang chủ"
    >
      <span className="brand-mark">
        <svg viewBox="0 0 40 40" aria-hidden="true">
          <path d="M29 13a11 11 0 1 0 1 11M29 6v8h-8" />
          <circle cx="20" cy="21" r="2.5" />
        </svg>
      </span>
      <span>
        find<span className="brand-accent">back</span>
        <span className="brand-dot">.</span>
      </span>
    </Link>
  )
}

export function PageHeading({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    <div className="page-heading">
      <div>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1>{title}</h1>
        {description && <p className="muted">{description}</p>}
      </div>
      {action}
    </div>
  )
}

export function EmptyState({
  title,
  children,
  action,
}: {
  title: string
  children: ReactNode
  action?: ReactNode
}) {
  return (
    <div className="empty-state">
      <span className="empty-icon">
        <Search size={30} />
      </span>
      <h2>{title}</h2>
      <p>{children}</p>
      {action}
    </div>
  )
}

export function SearchBar({
  initial = '',
  onSearch,
  compact = false,
}: {
  initial?: string
  onSearch?: (value: string) => void
  compact?: boolean
}) {
  const [value, setValue] = useState(initial)
  const navigate = useNavigate()
  return (
    <form
      className={`search-bar${compact ? ' compact' : ''}`}
      onSubmit={(event) => {
        event.preventDefault()
        if (onSearch) onSearch(value)
        else navigate(`/kham-pha?q=${encodeURIComponent(value)}`)
      }}
      role="search"
    >
      <Search size={21} aria-hidden="true" />
      <label className="sr-only" htmlFor="item-search">
        Bạn đang tìm món đồ gì?
      </label>
      <input
        id="item-search"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Bạn đang tìm món đồ gì?"
        type="search"
      />
      <button className="button button-primary" type="submit" aria-label="Tìm kiếm">
        <span>Tìm kiếm</span>
        <ArrowRight size={18} />
      </button>
    </form>
  )
}

export function SafetyNote() {
  return (
    <div className="safety-note">
      <ShieldCheck size={22} />
      <p>
        <strong>An tâm trên hành trình tìm lại.</strong>
        <br />
        Giữ kín đặc điểm riêng của món đồ. Xác minh trước khi trao trả và chọn nơi công cộng để gặp
        mặt.
      </p>
    </div>
  )
}
