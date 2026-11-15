import { Link } from 'react-router-dom';

export default function FinalCTASection() {
  return (
    <section
      id="final-cta"
      className="landing-light-section relative w-full overflow-hidden"
      style={{ background: 'rgba(5, 8, 23, 0.82)' }}
    >
      {/* Top separator */}
      <div
        className="absolute top-0 left-0 right-0 h-px"
        style={{ background: 'linear-gradient(90deg, transparent, rgba(49,75,115,0.4), transparent)' }}
      />

      {/* Background depth — subtle radial */}
      <div
        className="landing-atmosphere absolute inset-0 pointer-events-none"
        style={{
          background: 'radial-gradient(ellipse 70% 55% at 50% 60%, rgba(16,26,53,0.6) 0%, transparent 70%)',
        }}
      />

      {/* Gold horizon glow — bottom */}
      <div
        className="absolute bottom-0 left-1/2 -translate-x-1/2 w-[50vw] h-[30vh] pointer-events-none"
        style={{
          background: 'radial-gradient(ellipse at center bottom, rgba(229,183,106,0.07) 0%, transparent 65%)',
        }}
      />

      {/* Copper glow — upper right */}
      <div
        className="absolute top-[10%] right-[5%] w-[25vw] h-[25vw] rounded-full blur-3xl pointer-events-none"
        style={{
          background: 'radial-gradient(circle, rgba(185,111,92,0.08) 0%, transparent 70%)',
        }}
      />

      <div className="max-w-4xl mx-auto px-5 sm:px-8 lg:px-10 py-28 md:py-40 relative z-10">
        <div className="scroll-reveal text-center">

          {/* Eyebrow */}
          <span
            className="text-eyebrow tracking-[0.3em] block mb-6"
            style={{ color: 'var(--color-ody-copper)' }}
          >
            Begin the journey
          </span>

          {/* Headline */}
          <h2
            className="text-section-heading mb-5"
            style={{ color: 'var(--color-ody-ink)' }}
          >
            Your work has somewhere to go.
          </h2>

          {/* Supporting */}
          <p
            className="text-lg mb-12 max-w-sm mx-auto font-light"
            style={{ color: 'var(--color-ody-ink-muted)' }}
          >
            Stop managing tasks. Start moving through them.
          </p>

          {/* CTA */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link
              to="/auth"
              className="inline-flex items-center px-8 py-4 text-sm font-semibold tracking-wide rounded-lg active:scale-[0.97] transition-all duration-200"
              style={{
                background: 'linear-gradient(135deg, var(--color-ody-copper) 0%, var(--color-ody-gold) 100%)',
                color: '#050817',
                boxShadow: '0 4px 28px -4px rgba(229,183,106,0.35)',
              }}
              onMouseEnter={e => {
                (e.currentTarget as HTMLAnchorElement).style.boxShadow = '0 6px 36px -4px rgba(229,183,106,0.55)';
                (e.currentTarget as HTMLAnchorElement).style.filter = 'brightness(1.08)';
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLAnchorElement).style.boxShadow = '0 4px 28px -4px rgba(229,183,106,0.35)';
                (e.currentTarget as HTMLAnchorElement).style.filter = 'brightness(1)';
              }}
            >
              Try Odyssey
              <svg className="ml-2.5 w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
              </svg>
            </Link>
            <Link
              to="/auth"
              className="px-6 py-4 text-sm font-medium tracking-wide transition-colors duration-200"
              style={{ color: 'var(--color-ody-ink-muted)' }}
              onMouseEnter={e => (e.currentTarget.style.color = 'var(--color-ody-ink)')}
              onMouseLeave={e => (e.currentTarget.style.color = 'var(--color-ody-ink-muted)')}
            >
              Sign in to save progress →
            </Link>
          </div>

          {/* Destination marker */}
          <div className="flex justify-center mt-16 md:mt-20">
            <div className="flex flex-col items-center gap-2.5" style={{ opacity: 0.3 }}>
              <div
                className="w-px h-10"
                style={{ background: 'linear-gradient(to bottom, var(--color-ody-border), transparent)' }}
              />
              <div
                className="w-1.5 h-1.5 rounded-full"
                style={{ backgroundColor: 'var(--color-ody-gold)' }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="max-w-7xl mx-auto px-5 sm:px-8 lg:px-10 pb-8 relative z-10">
        <div
          className="pt-6 flex flex-col sm:flex-row justify-between items-center gap-3"
          style={{ borderTop: '1px solid rgba(49,75,115,0.2)' }}
        >
          <span
            className="text-xs tracking-widest font-display"
            style={{ color: 'var(--color-ody-ink-dim)' }}
          >
            ODYSSEY
          </span>
          <span
            className="text-xs tracking-wide"
            style={{ color: 'var(--color-ody-ink-dim)' }}
          >
            © {new Date().getFullYear()} · Your personal execution system.
          </span>
        </div>
      </div>
    </section>
  );
}
