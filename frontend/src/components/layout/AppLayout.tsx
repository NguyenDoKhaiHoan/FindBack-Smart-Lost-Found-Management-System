import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { ArrowUpRight, Bell, Menu, Plus, X } from 'lucide-react'
import { Brand } from '../ui/shared'
import { useSession } from '../../features/auth/session'
import { ChatWidget } from '../../features/ai/ChatWidget'

export function AppLayout() {
  const [open, setOpen] = useState(false)
  const menuButton = useRef<HTMLButtonElement>(null)
  const { token, disconnect } = useSession()
  const { pathname } = useLocation()
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'instant' })
  }, [pathname])
  return (
    <>
      <a className="skip-link" href="#main-content">
        Đến nội dung chính
      </a>
      <header className="app-header">
        <div className="container header-inner">
          <Brand />
          <nav className="desktop-nav" aria-label="Điều hướng chính">
            <NavLink to="/" end>
              Trang chủ
            </NavLink>
            <NavLink to="/kham-pha">Khám phá đồ thất lạc</NavLink>
            <NavLink to="/huong-dan">Cách hoạt động</NavLink>
          </nav>
          <div className="header-actions">
            {token ? (
              <>
                <Link className="icon-button" to="/thong-bao" aria-label="Thông báo">
                  <Bell size={20} />
                </Link>
                <Link className="login-link" to="/ca-nhan">
                  Cá nhân
                </Link>
              </>
            ) : (
              <Link className="login-link" to="/dang-nhap">
                Đăng nhập
              </Link>
            )}
            <Link className="button button-primary header-post" to="/dang-tin">
              <Plus size={17} />
              Đăng tin
            </Link>
            <button
              ref={menuButton}
              className="icon-button mobile-menu-button"
              aria-label={open ? 'Đóng menu' : 'Mở menu'}
              aria-expanded={open}
              aria-controls="mobile-navigation"
              onClick={() => setOpen(!open)}
            >
              {open ? <X /> : <Menu />}
            </button>
          </div>
        </div>
        {open && (
          <nav
            id="mobile-navigation"
            className="mobile-navigation"
            aria-label="Điều hướng di động"
            onKeyDown={(e) => {
              if (e.key === 'Escape') {
                setOpen(false)
                menuButton.current?.focus()
              }
            }}
          >
            <NavLink to="/" onClick={() => setOpen(false)}>
              Trang chủ
            </NavLink>
            <NavLink to="/kham-pha" onClick={() => setOpen(false)}>
              Khám phá đồ thất lạc
            </NavLink>
            <NavLink to="/huong-dan" onClick={() => setOpen(false)}>
              Cách hoạt động
            </NavLink>
            <NavLink to={token ? '/ca-nhan' : '/dang-nhap'} onClick={() => setOpen(false)}>
              {token ? 'Không gian cá nhân' : 'Đăng nhập'}
            </NavLink>
            <NavLink to="/yeu-cau" onClick={() => setOpen(false)}>
              Yêu cầu xác minh
            </NavLink>
            {token && (
              <button
                className="mobile-logout"
                onClick={() => {
                  disconnect()
                  setOpen(false)
                }}
              >
                Đăng xuất
              </button>
            )}
          </nav>
        )}
      </header>
      <main id="main-content" tabIndex={-1}>
        <Outlet />
      </main>
      <footer className="app-footer">
        <div className="container footer-main">
          <div>
            <Brand />
            <p>
              Kết nối những món đồ thất lạc
              <br />
              với người đang mong tìm lại.
            </p>
          </div>
          <div className="footer-links">
            <div>
              <strong>Khám phá</strong>
              <Link to="/kham-pha">Bảng tin đồ thất lạc</Link>
              <Link to="/dang-tin?loai=found">Tôi nhặt được đồ</Link>
              <Link to="/dang-tin?loai=lost">Tôi bị mất đồ</Link>
            </div>
            <div>
              <strong>Cùng FindBack</strong>
              <Link to="/huong-dan">Hướng dẫn an toàn</Link>
              <Link to="/nguon-anh">Nguồn ảnh</Link>
              <Link to="/yeu-cau">Yêu cầu xác minh</Link>
              <Link to="/ho-so">
                Tài khoản của tôi
                <ArrowUpRight size={13} />
              </Link>
            </div>
          </div>
        </div>
        <div className="container footer-bottom">
          <span>© {new Date().getFullYear()} FindBack. Tìm lại đồ, nối lại niềm vui.</span>
          <span>Được tạo nên từ sự sẻ chia.</span>
        </div>
      </footer>
      <ChatWidget />
    </>
  )
}
