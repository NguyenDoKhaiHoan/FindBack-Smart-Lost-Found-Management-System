import { lazy, Suspense } from 'react'
import { Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom'
import { AppLayout } from '../components/layout/AppLayout'
import { EmptyState } from '../components/ui/shared'
import { HomePage } from '../features/posts/HomePage'
import { PhotoCreditsPage } from '../features/posts/PhotoCreditsPage'
import { AccountSidebar } from '../features/profile/AccountSidebar'
import { useSession } from '../features/auth/session'

const Explore = lazy(() =>
  import('../features/posts/PublicPages').then((m) => ({ default: m.ExplorePage })),
)
const ItemDetail = lazy(() =>
  import('../features/posts/PublicPages').then((m) => ({ default: m.ItemDetailPage })),
)
const CreatePost = lazy(() =>
  import('../features/posts/PublicPages').then((m) => ({ default: m.CreatePostPage })),
)
const Auth = lazy(() => import('../features/auth/AuthPages').then((m) => ({ default: m.AuthPage })))
const Dashboard = lazy(() =>
  import('../features/profile/AccountPages').then((m) => ({ default: m.DashboardPage })),
)
const Profile = lazy(() =>
  import('../features/profile/AccountPages').then((m) => ({ default: m.ProfilePage })),
)
const MyPosts = lazy(() =>
  import('../features/profile/AccountPages').then((m) => ({ default: m.MyPostsPage })),
)
const Matches = lazy(() =>
  import('../features/profile/AccountPages').then((m) => ({ default: m.MatchesPage })),
)
const MatchDetail = lazy(() =>
  import('../features/profile/AccountPages').then((m) => ({ default: m.MatchDetailPage })),
)
const Notifications = lazy(() =>
  import('../features/profile/AccountPages').then((m) => ({ default: m.NotificationsPage })),
)
const Admin = lazy(() =>
  import('../features/admin/AdminPage').then((m) => ({ default: m.AdminPage })),
)
const Guide = lazy(() =>
  import('../features/profile/AccountPages').then((m) => ({ default: m.GuidePage })),
)
const Claims = lazy(() =>
  import('../features/claims_returns/ClaimsPages').then((m) => ({ default: m.ClaimsPage })),
)
const CreateClaim = lazy(() =>
  import('../features/claims_returns/ClaimsPages').then((m) => ({ default: m.CreateClaimPage })),
)
const ClaimDetail = lazy(() =>
  import('../features/claims_returns/ClaimsPages').then((m) => ({ default: m.ClaimDetailPage })),
)

export function RequireSession() {
  const { token } = useSession()
  const location = useLocation()
  return token ? (
    <Outlet />
  ) : (
    <Navigate to="/dang-nhap" state={{ from: location.pathname + location.search }} replace />
  )
}
function AccountLayout() {
  return (
    <div className="container account-layout">
      <AccountSidebar />
      <div className="account-content">
        <Outlet />
      </div>
    </div>
  )
}

export function App() {
  return (
    <Suspense
      fallback={
        <div className="container page-container" role="status" aria-label="Đang tải trang">
          <div className="skeleton" />
          <div className="skeleton" />
          <p>Đang tải…</p>
        </div>
      }
    >
      <Routes>
        <Route element={<AppLayout />}>
          <Route index element={<HomePage />} />
          <Route path="kham-pha" element={<Explore />} />
          <Route path="do-vat/:id" element={<ItemDetail />} />
          <Route path="huong-dan" element={<Guide />} />
          <Route path="nguon-anh" element={<PhotoCreditsPage />} />
          <Route element={<RequireSession />}>
            <Route path="dang-tin" element={<CreatePost />} />
            <Route path="quan-tri/*" element={<Admin />} />
            <Route element={<AccountLayout />}>
              <Route path="ca-nhan" element={<Dashboard />} />
              <Route path="ho-so" element={<Profile />} />
              <Route path="tin-cua-toi" element={<MyPosts />} />
              <Route path="tin-cua-toi/:id/sua" element={<CreatePost />} />
              <Route path="goi-y" element={<Matches />} />
              <Route path="goi-y/:id" element={<MatchDetail />} />
              <Route path="thong-bao" element={<Notifications />} />
              <Route path="yeu-cau" element={<Claims />} />
              <Route path="yeu-cau/moi" element={<CreateClaim />} />
              <Route path="yeu-cau/:id" element={<ClaimDetail />} />
            </Route>
          </Route>
          <Route
            path="*"
            element={
              <div className="container page-container">
                <EmptyState
                  title="Trang này chưa có trên bản đồ"
                  action={
                    <a className="button button-primary" href="/">
                      Về trang chủ
                    </a>
                  }
                >
                  Đường dẫn có thể đã thay đổi. Cùng bắt đầu lại từ trang chủ nhé.
                </EmptyState>
              </div>
            }
          />
        </Route>
        <Route path="dang-nhap" element={<Auth />} />
        <Route path="dang-ky" element={<Auth register />} />
      </Routes>
    </Suspense>
  )
}
