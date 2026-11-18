export type ArtworkKind = 'headphones' | 'wallet' | 'keys' | 'bottle' | 'bag' | 'card'

export function ItemArtwork({ kind, className = '' }: { kind: ArtworkKind; className?: string }) {
  return (
    <svg
      className={`item-artwork ${className}`}
      viewBox="0 0 300 230"
      fill="none"
      aria-hidden="true"
    >
      <defs>
        <linearGradient
          id={`${kind}-dark`}
          x1="80"
          y1="50"
          x2="210"
          y2="200"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor="#5D6570" />
          <stop offset="1" stopColor="#202938" />
        </linearGradient>
        <linearGradient
          id={`${kind}-orange`}
          x1="80"
          y1="60"
          x2="220"
          y2="190"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor="#C1845A" />
          <stop offset="1" stopColor="#835136" />
        </linearGradient>
        <filter id={`${kind}-shadow`} x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="9" />
        </filter>
      </defs>
      <ellipse
        cx="150"
        cy="197"
        rx="73"
        ry="9"
        fill="#202938"
        opacity=".12"
        filter={`url(#${kind}-shadow)`}
      />
      {kind === 'headphones' && (
        <g transform="rotate(-13 150 120)">
          <path d="M82 136V104a68 68 0 0 1 136 0v32" stroke="#2C333E" strokeWidth="17" />
          <path d="M88 113v-10a62 62 0 0 1 124 0v10" stroke="#626A74" strokeWidth="4" />
          <rect x="68" y="112" width="39" height="76" rx="18" fill={`url(#${kind}-dark)`} />
          <rect x="76" y="117" width="17" height="65" rx="8" fill="#7F8791" />
          <rect x="193" y="112" width="39" height="76" rx="18" fill={`url(#${kind}-dark)`} />
          <rect x="205" y="118" width="17" height="63" rx="8" fill="#171F2A" />
          <path d="M75 149h13m123 0h13" stroke="#A7ADB3" strokeWidth="1" />
        </g>
      )}
      {kind === 'wallet' && (
        <g transform="rotate(-14 150 120)">
          <rect x="62" y="58" width="173" height="118" rx="14" fill="#69452F" />
          <rect x="67" y="67" width="168" height="115" rx="13" fill={`url(#${kind}-orange)`} />
          <rect
            x="75"
            y="76"
            width="150"
            height="96"
            rx="8"
            stroke="#E4B98F"
            strokeDasharray="3 4"
            opacity=".7"
          />
          <path d="M186 106h53v38h-53a19 19 0 0 1 0-38" fill="#9B6845" stroke="#794B30" />
          <circle cx="194" cy="125" r="6" fill="#DDBA80" />
          <path d="M89 148h30" stroke="#73482F" strokeWidth="3" />
          <path d="M85 65V51h72v14" fill="#E8E1CA" />
          <path d="M100 51V42h72v23" fill="#AEC0B2" />
        </g>
      )}
      {kind === 'keys' && (
        <g transform="rotate(-27 150 120)">
          <circle cx="150" cy="72" r="30" stroke="#B6BDC5" strokeWidth="9" />
          <circle cx="150" cy="72" r="30" stroke="#E7EAED" strokeWidth="3" />
          <path
            d="M131 92v90h17v-13h13v-15h-13v-62"
            fill="#C5A46B"
            stroke="#A18555"
            strokeWidth="3"
          />
          <rect x="159" y="96" width="49" height="70" rx="14" fill="#394553" />
          <rect x="165" y="103" width="37" height="56" rx="9" stroke="#67717B" />
          <circle cx="182" cy="123" r="7" fill="#87919A" />
        </g>
      )}
      {kind === 'bottle' && (
        <g transform="rotate(14 150 120)">
          <rect x="125" y="29" width="50" height="27" rx="7" fill="#434E47" />
          <rect x="112" y="53" width="76" height="140" rx="24" fill="#8CA88D" />
          <path d="M125 70v100" stroke="#BDD0B4" strokeWidth="7" strokeLinecap="round" />
          <path d="M111 149h78" stroke="#6C8A70" strokeWidth="2" />
          <circle cx="150" cy="110" r="12" stroke="#DDE5D4" strokeWidth="2" />
        </g>
      )}
      {kind === 'bag' && (
        <g transform="rotate(-8 150 120)">
          <path d="M120 70V56a30 30 0 0 1 60 0v14" stroke="#C5AA79" strokeWidth="9" />
          <rect x="89" y="66" width="122" height="128" rx="31" fill="#D9C49F" />
          <path d="M104 82q46-18 91 0" stroke="#AE956B" strokeWidth="3" />
          <rect x="106" y="124" width="88" height="54" rx="15" fill="#C8AF80" />
          <path d="M119 139h63" stroke="#9C8159" strokeWidth="3" />
          <rect x="144" y="92" width="15" height="10" rx="2" fill="#8A7353" />
        </g>
      )}
      {kind === 'card' && (
        <g transform="rotate(-13 150 120)">
          <rect x="63" y="61" width="174" height="117" rx="12" fill="#FCFCF8" stroke="#CBD4DC" />
          <path d="M63 73a12 12 0 0 1 12-12h150a12 12 0 0 1 12 12v20H63" fill="#ED8549" />
          <rect x="78" y="107" width="45" height="51" rx="5" fill="#DAE2E7" />
          <circle cx="100" cy="122" r="9" fill="#A8B5BF" />
          <path d="M84 150a16 16 0 0 1 32 0" fill="#A8B5BF" />
          <path
            d="M137 113h74m-74 16h54m-54 16h65"
            stroke="#BAC3CB"
            strokeWidth="5"
            strokeLinecap="round"
          />
        </g>
      )}
    </svg>
  )
}
