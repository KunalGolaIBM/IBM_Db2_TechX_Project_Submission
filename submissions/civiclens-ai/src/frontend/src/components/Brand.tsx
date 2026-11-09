export function BrandMark({ className = 'size-8' }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" className={className} aria-hidden>
      <rect width="64" height="64" rx="14" fill="#1b1d22" />
      <circle cx="29" cy="29" r="14" fill="none" stroke="#cc7233" strokeWidth="5" />
      <path d="M40 40l12 12" stroke="#e39a62" strokeWidth="6" strokeLinecap="round" />
      <circle cx="29" cy="29" r="4" fill="#e39a62" />
    </svg>
  )
}

export function Wordmark() {
  return (
    <span className="flex items-center gap-2.5">
      <BrandMark />
      <span className="text-[17px] leading-none font-semibold tracking-tight text-fg">
        CivicLens <span className="text-copper-400">AI</span>
      </span>
    </span>
  )
}
