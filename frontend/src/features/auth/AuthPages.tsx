import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { ArrowRight, Check, KeyRound, LockKeyhole, ShieldCheck } from 'lucide-react'
import { useSession } from './session'
import { Brand } from '../../components/ui/shared'
import { ItemArtwork } from '../../components/ui/ItemArtwork'
import { ApiError } from '../../lib/api'
import { identityApi } from '../../lib/api/system'

export function AuthPage({ register = false }: { register?: boolean }) {
  const { connect, signIn, isConnecting, error, expired, token } = useSession()
  const [draftToken, setDraftToken] = useState('')
  const [formError, setFormError] = useState('')
  const [saving, setSaving] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const returnTo =
    typeof location.state?.from === 'string' &&
    location.state.from.startsWith('/') &&
    !location.state.from.startsWith('//')
      ? location.state.from
      : '/ca-nhan'
  const canConnect = import.meta.env.DEV && import.meta.env.VITE_ENABLE_DEV_SESSION === 'true'
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const email = String(form.get('email')).trim()
    const password = String(form.get('password'))
    setSaving(true)
    setFormError('')
    try {
      if (register) {
        const full_name = String(form.get('full_name')).trim()
        await identityApi.register({ email, password, full_name })
      }
      await signIn({ email, password })
      navigate(returnTo, { replace: true })
    } catch (cause) {
      setFormError(cause instanceof ApiError ? cause.message : 'Không thể xác thực tài khoản.')
    } finally {
      setSaving(false)
    }
  }
  async function connectSession(event: React.FormEvent) {
    event.preventDefault()
    const candidate = draftToken
    setDraftToken('')
    try {
      await connect(candidate)
      navigate(returnTo, { replace: true })
    } catch {
      /* Session provider exposes a sanitized message. */
    }
  }
  return (
    <main className="auth-page">
      <section className="auth-story">
        <Brand />
        <div>
          <p className="eyebrow">Những điều thân quen xứng đáng trở về</p>
          <h1>
            Mất một món đồ.
            <br />
            Đừng mất hy vọng.
          </h1>
          <p>
            Một người đang tìm.
            <br />
            Một người sẵn lòng trao lại.
            <br />
            FindBack kết nối hai câu chuyện ấy.
          </p>
          <div className="auth-art">
            <ItemArtwork kind="bag" />
          </div>
        </div>
        <span>
          <ShieldCheck size={17} />
          Bảo vệ thông tin của bạn trong từng kết nối.
        </span>
      </section>
      <section className="auth-form">
        <Link className="back-link" to="/">
          ← Về trang chủ
        </Link>
        <span className="auth-form-icon">
          <KeyRound size={26} />
        </span>
        <h1>{register ? 'Bắt đầu hành trình cùng FindBack' : 'Chào mừng bạn trở lại'}</h1>
        <p className="muted">
          {register
            ? 'Cùng xây dựng cộng đồng tìm lại và sẻ chia.'
            : 'Mỗi kết nối là một cơ hội tìm lại.'}
        </p>
        {expired && (
          <p className="error-state" role="alert">
            Phiên làm việc đã hết hạn. Vui lòng kết nối lại.
          </p>
        )}
        <form onSubmit={submit} className="auth-fields">
          {formError && (
            <p className="error-state" role="alert">
              {formError}
            </p>
          )}
          <fieldset disabled={saving || isConnecting}>
            {register && (
              <label className="field">
                Họ và tên
                <input name="full_name" autoComplete="name" maxLength={100} required />
              </label>
            )}
            <label className="field">
              Email
              <input name="email" type="email" autoComplete="email" maxLength={320} required />
            </label>
            <label className="field">
              Mật khẩu
              <input
                type="password"
                name="password"
                autoComplete={register ? 'new-password' : 'current-password'}
                minLength={register ? 8 : 1}
                maxLength={72}
                required
              />
              {register && (
                <small>Ít nhất 8 ký tự, có chữ hoa, chữ thường, số và ký tự đặc biệt.</small>
              )}
            </label>
            <button className="button button-primary full-width" type="submit">
              {saving ? 'Đang xử lý…' : register ? 'Tạo tài khoản' : 'Đăng nhập'}
              <ArrowRight size={17} />
            </button>
          </fieldset>
        </form>
        <p className="auth-switch">
          {register ? 'Đã có tài khoản?' : 'Chưa có tài khoản?'}{' '}
          <Link to={register ? '/dang-nhap' : '/dang-ky'} state={{ from: returnTo }}>
            {register ? 'Đăng nhập' : 'Đăng ký'}
          </Link>
        </p>
        {token && (
          <Link className="button button-secondary full-width" to={returnTo}>
            <Check size={17} />
            Tiếp tục phiên hiện tại
          </Link>
        )}
        {canConnect && (
          <details className="dev-session">
            <summary>
              <LockKeyhole size={16} />
              Kết nối phiên phát triển
            </summary>
            <p className="muted small">
              Dành cho kiểm thử local. Nhập JWT do backend cấp. Phiên chỉ được giữ trong bộ nhớ và
              sẽ mất khi tải lại trang.
            </p>
            <form onSubmit={connectSession}>
              <label className="field">
                JWT truy cập
                <input
                  type="password"
                  autoComplete="off"
                  value={draftToken}
                  onChange={(e) => setDraftToken(e.target.value)}
                  spellCheck={false}
                  required
                  aria-describedby={error ? 'session-error' : undefined}
                />
              </label>
              {error && (
                <p id="session-error" className="error-state" role="alert">
                  {error}
                </p>
              )}
              <button
                className="button button-secondary full-width"
                disabled={isConnecting || !draftToken.trim()}
              >
                {isConnecting ? 'Đang xác thực…' : 'Xác thực với backend'}
                <ArrowRight size={16} />
              </button>
            </form>
          </details>
        )}
        <p className="auth-privacy">
          <ShieldCheck size={15} />
          Không chia sẻ thông tin đăng nhập hoặc mã truy cập.
        </p>
      </section>
    </main>
  )
}
