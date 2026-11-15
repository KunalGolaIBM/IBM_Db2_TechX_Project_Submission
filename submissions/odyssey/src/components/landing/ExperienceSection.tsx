const steps = [
  {
    label: 'Your chaos',
    desc: 'Scattered tasks, forgotten threads, half-finished ideas — everything pulling you in different directions.',
    accent: 'var(--color-ody-ink-muted)',
    icon: (
      <svg viewBox="0 0 32 32" fill="none" className="w-6 h-6">
        <path d="M6 16c3-8 8 4 12-4s6 8 8 0" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" opacity="0.8" />
        <path d="M8 22c2-6 6 2 10-2s4 6 6 0" stroke="currentColor" strokeWidth="1" strokeLinecap="round" opacity="0.45" />
      </svg>
    ),
  },
  {
    label: 'Odyssey finds what matters',
    desc: 'Context is remembered. Priorities surface. The noise fades and the signal becomes clear.',
    accent: 'var(--color-ody-copper)',
    icon: (
      <svg viewBox="0 0 32 32" fill="none" className="w-6 h-6">
        <circle cx="16" cy="16" r="8" stroke="currentColor" strokeWidth="1.5" opacity="0.55" />
        <circle cx="16" cy="16" r="3" fill="currentColor" opacity="0.8" />
      </svg>
    ),
  },
  {
    label: 'You choose your path',
    desc: 'Not a ranked list — a considered decision. You pick what you will actually do, right now.',
    accent: 'var(--color-ody-copper)',
    icon: (
      <svg viewBox="0 0 32 32" fill="none" className="w-6 h-6">
        <path d="M8 24L16 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" opacity="0.85" />
        <path d="M16 8L24 20" stroke="currentColor" strokeWidth="1" strokeLinecap="round" opacity="0.35" strokeDasharray="3 3" />
        <circle cx="16" cy="8" r="2.5" fill="currentColor" opacity="0.75" />
      </svg>
    ),
  },
  {
    label: 'Your task becomes a mission',
    desc: 'A concrete scope. A clear objective. Something you can complete — not just "work on."',
    accent: 'var(--color-ody-gold)',
    icon: (
      <svg viewBox="0 0 32 32" fill="none" className="w-6 h-6">
        <rect x="9" y="10" width="14" height="12" rx="2" stroke="currentColor" strokeWidth="1.5" opacity="0.55" />
        <path d="M13 16h6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" opacity="0.85" />
        <path d="M13 19h4" stroke="currentColor" strokeWidth="1" strokeLinecap="round" opacity="0.5" />
      </svg>
    ),
  },
  {
    label: 'You execute',
    desc: 'No distractions. One thing in front of you. Start, work, finish.',
    accent: 'var(--color-ody-gold)',
    icon: (
      <svg viewBox="0 0 32 32" fill="none" className="w-6 h-6">
        <path d="M10 22L16 10L22 22" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" opacity="0.75" />
        <circle cx="16" cy="10" r="2" fill="currentColor" opacity="0.65" />
      </svg>
    ),
  },
  {
    label: 'Your progress becomes part of the journey',
    desc: "Completed work isn't just checked off. It's mapped, remembered, and part of a path you're building.",
    accent: 'var(--color-ody-gold)',
    icon: (
      <svg viewBox="0 0 32 32" fill="none" className="w-6 h-6">
        <path d="M6 26Q12 12 16 16T26 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" opacity="0.75" />
        <circle cx="26" cy="6" r="2.5" fill="var(--color-ody-gold)" opacity="0.9" />
        <circle cx="16" cy="16" r="1.5" fill="currentColor" opacity="0.5" />
      </svg>
    ),
  },
];

export default function ExperienceSection() {
  return (
    <section
      className="landing-light-section relative w-full overflow-hidden"
      style={{ background: 'rgba(13, 22, 40, 0.88)' }}
    >
      {/* Atmospheric depth gradient */}
      <div
        className="landing-atmosphere absolute inset-0 pointer-events-none"
        style={{
          background: 'radial-gradient(ellipse 80% 60% at 50% 50%, rgba(16,26,53,0.4) 0%, transparent 70%)',
        }}
      />

      {/* Top separator */}
      <div
        className="absolute top-0 left-0 right-0 h-px"
        style={{ background: 'linear-gradient(90deg, transparent, rgba(49,75,115,0.35), transparent)' }}
      />

      <div className="max-w-3xl mx-auto px-5 sm:px-8 lg:px-10 py-24 md:py-36 relative z-10">

        {/* Section label */}
        <div className="scroll-reveal text-center mb-16 md:mb-20">
          <span
            className="text-eyebrow tracking-[0.3em] block mb-5"
            style={{ color: 'var(--color-ody-ink-dim)' }}
          >
            The Experience
          </span>
          <h2
            className="text-section-heading"
            style={{ color: 'var(--color-ody-ink)' }}
          >
            From scattered to
            <br />
            <span className="italic" style={{ color: 'var(--color-ody-gold)' }}>somewhere.</span>
          </h2>
        </div>

        {/* Vertical narrative */}
        <div className="relative">
          {/* Rail line */}
          <div
            className="absolute left-[26px] md:left-[30px] top-4 bottom-4 w-px"
            style={{
              background: 'linear-gradient(180deg, rgba(150,152,168,0.2), rgba(185,111,92,0.35) 40%, rgba(229,183,106,0.45) 75%, rgba(229,183,106,0.15))',
            }}
          />

          {steps.map((step, i) => (
            <div
              key={i}
              className={`scroll-reveal scroll-reveal-delay-${Math.min(i + 1, 4)} relative flex items-start gap-5 md:gap-7 ${
                i < steps.length - 1 ? 'mb-10 md:mb-14' : ''
              }`}
            >
              {/* Node — glass circle */}
              <div
                className="relative z-10 flex-shrink-0 w-[52px] h-[52px] md:w-[60px] md:h-[60px] rounded-full flex items-center justify-center"
                style={{
                  background: 'rgba(16, 26, 53, 0.7)',
                  border: '1px solid rgba(49, 75, 115, 0.4)',
                  backdropFilter: 'blur(10px)',
                  WebkitBackdropFilter: 'blur(10px)',
                  color: step.accent,
                  boxShadow: '0 2px 12px rgba(5,8,23,0.4)',
                }}
              >
                {step.icon}
              </div>

              {/* Content */}
              <div className="pt-2.5 md:pt-3.5">
                <h3
                  className="font-display text-lg md:text-xl font-medium mb-1.5"
                  style={{ color: step.accent }}
                >
                  {step.label}
                </h3>
                <p
                  className="text-sm md:text-[0.9375rem] leading-relaxed max-w-sm"
                  style={{ color: 'var(--color-ody-ink-muted)' }}
                >
                  {step.desc}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Bottom separator */}
      <div
        className="absolute bottom-0 left-0 right-0 h-px"
        style={{ background: 'linear-gradient(90deg, transparent, rgba(49,75,115,0.3), transparent)' }}
      />
    </section>
  );
}
