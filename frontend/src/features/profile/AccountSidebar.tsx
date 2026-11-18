import { Link, useLocation } from 'react-router-dom'
import {
  Bell,
  CircleHelp,
  ClipboardCheck,
  FileText,
  LayoutDashboard,
  LogOut,
  Sparkles,
  ShieldCheck,
  UserRound,
} from 'lucide-react'
import { useSession } from '../auth/session'
import { useAccount } from '../auth/useAccount'

const accountLinks = [
  { to: '/ca-nhan', icon: LayoutDashboard, label: 'Tổng quan' },
  { to: '/tin-cua-toi', icon: FileText, label: 'Tin của tôi' },
  { to: '/yeu-cau', icon: ClipboardCheck, label: 'Yêu cầu xác minh' },
  { to: '/goi-y', icon: Sparkles, label: 'Gợi ý phù hợp' },
  { to: '/thong-bao', icon: Bell, label: 'Thông báo' },
  { to: '/ho-so', icon: UserRound, label: 'Hồ sơ cá nhân' },
]

export function AccountSidebar() {
  const { pathname } = useLocation()
  const { disconnect } = useSession()
  const { data: user } = useAccount()
  return (
    <aside className="account-sidebar">
      <div className="account-sidebar-heading">
        <span className="avatar">
          <UserRound size={23} />
        </span>
        <div>
          <strong>{user?.full_name || 'Không gian của bạn'}</strong>
          {user?.role === 'ADMIN' && <small>Quản trị viên</small>}
        </div>
      </div>
      <nav aria-label="Điều hướng cá nhân">
        {accountLinks.map((link) => (
          <Link
            key={link.to}
            to={link.to}
            className={
              pathname === link.to || (link.to === '/yeu-cau' && pathname.startsWith('/yeu-cau/'))
                ? 'active'
                : ''
            }
          >
            <link.icon size={19} />
            {link.label}
          </Link>
        ))}
        {user?.role === 'ADMIN' && (
          <Link to="/quan-tri">
            <ShieldCheck size={19} /> Quản trị
          </Link>
        )}
      </nav>
      <Link className="sidebar-help" to="/huong-dan">
        <CircleHelp size={19} />
        Hướng dẫn an toàn
      </Link>
      <button className="sidebar-logout" onClick={disconnect}>
        <LogOut size={18} />
        Đăng xuất
      </button>
    </aside>
  )
}
