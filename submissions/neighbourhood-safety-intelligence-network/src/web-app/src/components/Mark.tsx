/** NSIN mark: a roof (home), a rising echo (signal and hope) and a warm light under the roof (someone safe). */
export default function Mark({ className = 'w-10 h-10' }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" className={className} aria-hidden="true">
      <defs>
        <linearGradient id="nsin-mark" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#2A6BFF" />
          <stop offset="1" stopColor="#0B2E8F" />
        </linearGradient>
      </defs>
      <rect width="64" height="64" rx="16" fill="url(#nsin-mark)" />
      <path d="M18 26 32 13l14 13" fill="none" stroke="#fff" strokeOpacity=".42" strokeWidth="4.5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M14 40 32 23l18 17" fill="none" stroke="#fff" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="32" cy="44" r="5" fill="#FFB547" />
    </svg>
  );
}
