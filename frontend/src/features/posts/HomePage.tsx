import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  ArrowRight,
  ArrowUpRight,
  Check,
  FileText,
  HandHeart,
  Headphones,
  KeyRound,
  MapPin,
  Search,
  ShieldCheck,
  Tag,
  Wallet,
} from 'lucide-react'
import { ItemArtwork } from '../../components/ui/ItemArtwork'
import { EmptyState, SearchBar } from '../../components/ui/shared'
import { ApiFeedback } from '../../components/ui/live'
import { postsApi } from '../../lib/api/system'
import { PostCard } from './PostCard'

const categoryIcons = [KeyRound, FileText, Tag, Headphones, Wallet]

export function HomePage() {
  const categories = useQuery({
    queryKey: ['categories'],
    queryFn: ({ signal }) => postsApi.categories(signal),
  })
  const latest = useQuery({
    queryKey: ['posts', 'latest'],
    queryFn: ({ signal }) => postsApi.latest(signal),
  })
  return (
    <>
      <section className="hero">
        <div className="container hero-grid">
          <div className="hero-copy">
            <div className="hero-kicker">
              <span className="orange-dot" /> Một món đồ trở về. Một niềm vui ở lại.
            </div>
            <h1>
              Tìm lại đồ,
              <br />
              nối lại{' '}
              <span className="joy">
                niềm vui.
                <svg viewBox="0 0 340 15" aria-hidden="true">
                  <path d="M3 9Q163-4 334 7M13 14Q169 3 316 11" />
                </svg>
              </span>
            </h1>
            <p>
              Món đồ của bạn có thể đang được ai đó giữ giúp.
              <br className="desktop-break" /> Để FindBack kết nối những người đang tìm kiếm
              <br className="desktop-break" /> và những người muốn trao lại.
            </p>
            <div className="hero-actions">
              <Link className="button button-primary" to="/dang-tin?loai=lost">
                <Search size={18} />
                Tôi bị mất đồ
                <ArrowUpRight size={18} />
              </Link>
              <Link className="button button-secondary" to="/dang-tin?loai=found">
                <HandHeart size={19} />
                Tôi nhặt được đồ
              </Link>
            </div>
            <div className="hero-footnote">
              <ShieldCheck size={17} />
              <span>Giữ kín thông tin. Xác minh trước khi trao trả.</span>
            </div>
          </div>
          <div className="hero-visual" aria-label="Minh họa hành trình tìm lại đồ vật">
            <div className="orbit orbit-one" />
            <div className="orbit orbit-two" />
            <span className="visual-spark spark-one">✳</span>
            <span className="visual-spark spark-two">+</span>
            <svg className="dotted-route" viewBox="0 0 500 400" aria-hidden="true">
              <path d="M49 292C-1 230 95 195 172 267S415 410 445 246S250 140 366 51" />
            </svg>
            <div className="floating-label label-top">
              <span className="tiny-icon">
                <MapPin size={17} />
              </span>
              Có thể ở rất gần bạn
            </div>
            <div className="hero-object object-main">
              <div className="object-label">
                <span className="tiny-dot" /> MỘT MÓN ĐỒ ĐANG CHỜ
              </div>
              <ItemArtwork kind="headphones" />
              <div className="object-bottom">
                <span>Tai nghe quen thuộc</span>
                <span className="round-arrow">
                  <ArrowUpRight size={19} />
                </span>
              </div>
            </div>
            <div className="hero-object object-wallet">
              <ItemArtwork kind="wallet" />
              <span>Những điều thân quen</span>
            </div>
            <div className="reunion-label">
              <span className="reunion-check">
                <Check size={20} />
              </span>
              <div>
                <strong>Đúng người. Đúng món đồ.</strong>
                <small>Một kết nối, thêm một niềm vui.</small>
              </div>
            </div>
          </div>
        </div>
      </section>
      <section className="search-section container" aria-label="Tìm đồ vật">
        <SearchBar />
        <div className="search-suggestions">
          <span>Thử tìm:</span>
          {['Ví da', 'Tai nghe', 'Thẻ sinh viên'].map((text) => (
            <Link key={text} to={`/kham-pha?q=${encodeURIComponent(text)}`}>
              {text}
              <ArrowUpRight size={12} />
            </Link>
          ))}
        </div>
      </section>
      <section className="container categories-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Bắt đầu từ món đồ của bạn</p>
            <h2>Bạn đang tìm gì?</h2>
          </div>
          <Link className="text-link" to="/kham-pha">
            Khám phá tất cả
            <ArrowRight size={17} />
          </Link>
        </div>
        <ApiFeedback
          pending={categories.isPending}
          error={categories.error}
          retry={() => void categories.refetch()}
        />
        <div className="category-grid">
          {categories.data?.map((category, index) => {
            const Icon = categoryIcons[index] ?? Tag
            return (
              <Link
                className="category-card"
                to={`/kham-pha?danh-muc=${category.id}`}
                key={category.id}
              >
                <span>
                  <Icon size={27} strokeWidth={1.5} />
                </span>
                <strong>{category.name}</strong>
                <ArrowUpRight size={16} />
              </Link>
            )
          })}
        </div>
      </section>
      <section className="recent-section">
        <div className="container">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Mỗi món đồ đều có một câu chuyện</p>
              <h2>Những món đồ đang chờ trở về</h2>
            </div>
            <Link className="text-link" to="/kham-pha">
              Xem bảng tin
              <ArrowRight size={17} />
            </Link>
          </div>
          <ApiFeedback
            pending={latest.isPending}
            error={latest.error}
            retry={() => void latest.refetch()}
          />
          {latest.data?.items.length === 0 && (
            <EmptyState
              title="Chưa có tin đăng"
              action={
                <Link className="button button-primary" to="/dang-tin">
                  Đăng tin
                </Link>
              }
            >
              Các tin được đăng sẽ xuất hiện tại đây.
            </EmptyState>
          )}
          <div className="items-grid live-post-grid">
            {latest.data?.items.map((item) => (
              <PostCard
                key={item.id}
                id={item.id}
                title={item.title}
                type={item.type}
                location={item.location}
                time={item.event_time}
                category={
                  categories.data?.find((category) => category.id === item.category_id)?.name
                }
              />
            ))}
          </div>
        </div>
      </section>
      <section id="cach-hoat-dong" className="container how-section">
        <div className="section-heading centered">
          <p className="eyebrow">Đơn giản hơn bạn nghĩ</p>
          <h2>Ba bước. Một hành trình trở về.</h2>
          <p>Một chút sẻ chia có thể tạo nên một ngày tốt đẹp hơn.</p>
        </div>
        <div className="steps-grid">
          {[
            {
              icon: Search,
              title: 'Tìm kiếm hoặc đăng tin',
              text: 'Tìm món đồ quen thuộc hoặc để lại thông tin về món đồ bạn nhặt được.',
            },
            {
              icon: ShieldCheck,
              title: 'Kết nối và xác minh',
              text: 'Trao đổi đặc điểm riêng qua yêu cầu xác minh để tìm đúng chủ sở hữu.',
            },
            {
              icon: HandHeart,
              title: 'Trao lại niềm vui',
              text: 'Hẹn gặp an toàn và xác nhận đã nhận lại món đồ của mình.',
            },
          ].map((step, i) => (
            <div className="step" key={step.title}>
              <div className="step-top">
                <span className="step-icon">
                  <step.icon size={25} />
                </span>
                <span className="step-number">0{i + 1}</span>
              </div>
              <h3>{step.title}</h3>
              <p>{step.text}</p>
            </div>
          ))}
        </div>
      </section>
      <section className="container">
        <div className="trust-banner">
          <div className="trust-icon">
            <ShieldCheck size={38} strokeWidth={1.5} />
          </div>
          <div>
            <h2>Sự tử tế bắt đầu từ một hành động nhỏ.</h2>
            <p>
              Giữ kín thông tin cá nhân. Không chuyển tiền để nhận lại đồ.
              <br className="desktop-break" /> Luôn xác minh và gặp mặt ở nơi công cộng.
            </p>
          </div>
          <Link to="/huong-dan" className="button button-secondary">
            Trao trả an toàn
            <ArrowUpRight size={17} />
          </Link>
        </div>
      </section>
    </>
  )
}
