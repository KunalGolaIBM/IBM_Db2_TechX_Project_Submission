const stages = [
  {
    key: 'remember',
    label: 'Remember',
    desc: 'Your unfinished work and context, always preserved.',
    accent: 'var(--color-ody-ink-muted)',
    dot: 'rgba(150, 152, 168, 0.8)',
    ring: 'rgba(150, 152, 168, 0.15)',
  },
  {
    key: 'decide',
    label: 'Decide',
    desc: 'Know exactly what matters now.',
    accent: 'var(--color-ody-copper)',
    dot: 'rgba(185, 111, 92, 0.85)',
    ring: 'rgba(185, 111, 92, 0.15)',
  },
  {
    key: 'execute',
    label: 'Execute',
    desc: 'Turn your choice into a concrete mission.',
    accent: 'var(--color-ody-copper)',
    dot: 'rgba(185, 111, 92, 0.85)',
    ring: 'rgba(185, 111, 92, 0.15)',
  },
  {
    key: 'progress',
    label: 'Progress',
    desc: 'Completed work becomes part of your journey.',
    accent: 'var(--color-ody-gold)',
    dot: 'rgba(229, 183, 106, 0.9)',
    ring: 'rgba(229, 183, 106, 0.15)',
  },
];

export default function CoreLoopSection() {
  return (
    <section
      id="how-it-works"
      className="landing-light-section relative w-full overflow-hidden"
      style={{ background: 'rgba(5, 8, 23, 0.82)' }}
    >
      {/* Subtle top separator */}
      <div
        className="absolute top-0 left-0 right-0 h-px"
        style={{ background: 'linear-gradient(90deg, transparent, rgba(49,75,115,0.4), transparent)' }}
      />

      {/* Deep-space ambient glow */}
      <div
        className="landing-atmosphere absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[70vw] h-[40vh] rounded-full blur-3xl pointer-events-none"
        style={{ background: 'radial-gradient(ellipse, rgba(16,26,53,0.8) 0%, transparent 70%)', opacity: 0.6 }}
      />

      <div className="max-w-5xl mx-auto px-5 sm:px-8 lg:px-10 py-24 md:py-36 relative z-10">

        {/* Problem statement */}
        <div className="scroll-reveal max-w-2xl mx-auto text-center mb-20 md:mb-28">
          <p
            className="text-section-heading mb-4 leading-snug"
            style={{ color: 'var(--color-ody-ink)' }}
          >
            Having things to do isn't the hard part.
          </p>
          <p
            className="text-section-heading leading-snug"
            style={{ color: 'var(--color-ody-ink-muted)' }}
          >
            Knowing what to do next
            <span className="italic" style={{ color: 'var(--color-ody-gold)' }}> — and actually starting — </span>
            is.
          </p>
        </div>

        {/* Loop label */}
        <div className="scroll-reveal scroll-reveal-delay-1 text-center mb-14 md:mb-16">
          <span
            className="text-eyebrow tracking-[0.3em]"
            style={{ color: 'var(--color-ody-ink-dim)' }}
          >
            The Odyssey Loop
          </span>
        </div>

        {/* Core loop stages */}
        <div className="scroll-reveal scroll-reveal-delay-2">

          {/* Desktop: horizontal */}
          <div className="hidden md:flex items-start justify-between relative">
            {/* Connecting line */}
            <div
              className="absolute top-[22px] left-[12%] right-[12%] h-px"
              style={{
                background: 'linear-gradient(90deg, rgba(150,152,168,0.3) 0%, rgba(185,111,92,0.4) 50%, rgba(229,183,106,0.5) 100%)',
              }}
            />

            {stages.map((stage, i) => (
              <div key={stage.key} className="flex flex-col items-center text-center flex-1 relative px-2">
                {/* Node */}
                <div
                  className="relative w-11 h-11 rounded-full flex items-center justify-center mb-5"
                  style={{
                    background: `radial-gradient(circle, ${stage.ring} 0%, rgba(16,26,53,0.6) 70%)`,
                    border: `1px solid ${stage.ring.replace('0.15', '0.35')}`,
                    backdropFilter: 'blur(8px)',
                  }}
                >
                  <div
                    className="w-2.5 h-2.5 rounded-full"
                    style={{
                      backgroundColor: stage.dot,
                      boxShadow: `0 0 8px 2px ${stage.ring}`,
                    }}
                  />
                </div>

                <h3
                  className="font-display text-lg font-medium mb-2 tracking-wide"
                  style={{ color: stage.accent }}
                >
                  {stage.label}
                </h3>
                <p
                  className="text-sm leading-relaxed max-w-[175px]"
                  style={{ color: 'var(--color-ody-ink-muted)' }}
                >
                  {stage.desc}
                </p>

                {/* Arrow */}
                {i < stages.length - 1 && (
                  <svg
                    className="absolute top-[14px] -right-3 w-5 h-5"
                    style={{ color: 'rgba(49,75,115,0.5)' }}
                    fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5" />
                  </svg>
                )}
              </div>
            ))}
          </div>

          {/* Mobile: vertical */}
          <div className="md:hidden flex flex-col items-center relative">
            <div
              className="absolute top-6 bottom-6 left-1/2 -translate-x-1/2 w-px"
              style={{
                background: 'linear-gradient(180deg, rgba(150,152,168,0.3), rgba(185,111,92,0.4), rgba(229,183,106,0.5))',
              }}
            />

            {stages.map((stage, i) => (
              <div key={stage.key} className="flex flex-col items-center text-center relative z-10 mb-10 last:mb-0">
                <div
                  className="w-10 h-10 rounded-full flex items-center justify-center mb-4"
                  style={{
                    background: `radial-gradient(circle, ${stage.ring} 0%, rgba(16,26,53,0.6) 70%)`,
                    border: `1px solid ${stage.ring.replace('0.15', '0.35')}`,
                    backdropFilter: 'blur(8px)',
                  }}
                >
                  <div
                    className="w-2 h-2 rounded-full"
                    style={{
                      backgroundColor: stage.dot,
                      boxShadow: `0 0 6px 2px ${stage.ring}`,
                    }}
                  />
                </div>

                <h3
                  className="font-display text-base font-medium mb-1.5"
                  style={{ color: stage.accent }}
                >
                  {stage.label}
                </h3>
                <p
                  className="text-sm leading-relaxed max-w-[220px]"
                  style={{ color: 'var(--color-ody-ink-muted)' }}
                >
                  {stage.desc}
                </p>

                {i < stages.length - 1 && (
                  <svg
                    className="mt-4 w-4 h-4"
                    style={{ color: 'rgba(49,75,115,0.45)' }}
                    fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 5v14m0 0l-5-5m5 5l5-5" />
                  </svg>
                )}
              </div>
            ))}
          </div>
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
