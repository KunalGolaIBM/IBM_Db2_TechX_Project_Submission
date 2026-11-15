import { useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { useTheme } from '../../hooks/useTheme';

export default function HeroSection() {
  const aircraftRef = useRef<SVGCircleElement>(null);
  const pathRef = useRef<SVGPathElement>(null);
  const { theme } = useTheme();

  useEffect(() => {
    const aircraft = aircraftRef.current;
    const path = pathRef.current;
    if (!aircraft || !path) return;

    const length = path.getTotalLength();
    let progress = 0;
    let animationId: number;

    const animate = () => {
      progress += 0.00025;
      if (progress > 1) progress = 0;
      const point = path.getPointAtLength(progress * length);
      aircraft.setAttribute('cx', String(point.x));
      aircraft.setAttribute('cy', String(point.y));
      animationId = requestAnimationFrame(animate);
    };

    animationId = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(animationId);
  }, []);

  return (
    <section
      id="hero"
      className="relative w-full min-h-screen flex items-end overflow-hidden"
    >
      {/* ── Layer 1: theme background ── */}
      <div
        className="absolute inset-0"
        style={{
          backgroundImage: `url(/${theme === 'light' ? 'odyssey2-bg.png' : 'odyssey-bg.png'})`,
          backgroundSize: 'cover',
          backgroundPosition: 'center 30%',
          backgroundRepeat: 'no-repeat',
        }}
      />

      {/* ── Layer 2: Minimal edge overlays — image stays fully visible ── */}
      <div className="hero-edge-overlays absolute inset-0 pointer-events-none">
          {/* Bottom fog — only the very bottom where text sits; image centre stays open */}
        <div
          className="absolute bottom-0 left-0 right-0 h-[50%]"
          style={{
            background: 'linear-gradient(0deg, #050817 0%, rgba(5,8,23,0.65) 28%, rgba(5,8,23,0.1) 55%, transparent 100%)',
          }}
        />

        {/* Top edge — thin fade for nav legibility only */}
        <div
          className="absolute top-0 left-0 right-0 h-[18%]"
          style={{
            background: 'linear-gradient(180deg, rgba(5,8,23,0.45) 0%, transparent 100%)',
          }}
        />

        {/* Outer edge vignette — only the very perimeter, center is untouched */}
        <div
          className="absolute inset-0"
          style={{
            background: 'radial-gradient(ellipse at center, transparent 60%, rgba(5,8,23,0.35) 100%)',
          }}
        />
      </div>

      {/* ── Layer 3: SVG route — subtle route path over image ── */}
      <svg
        className="absolute inset-0 w-full h-full pointer-events-none"
        viewBox="0 0 1440 900"
        preserveAspectRatio="xMidYMid slice"
        aria-hidden="true"
      >
        <defs>
          <linearGradient id="routeGradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%"   stopColor="rgba(49,75,115,0)" />
            <stop offset="20%"  stopColor="rgba(49,75,115,0.4)" />
            <stop offset="65%"  stopColor="rgba(185,111,92,0.35)" />
            <stop offset="100%" stopColor="rgba(229,183,106,0.2)" />
          </linearGradient>
          <filter id="glowFilter">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <filter id="softGlow">
            <feGaussianBlur stdDeviation="2.5" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Route path — gentle arc from lower-left to upper-right */}
        <path
          ref={pathRef}
          d="M 100 720 Q 320 600, 500 530 T 860 390 Q 1060 310, 1220 260 T 1390 210"
          fill="none"
          stroke="url(#routeGradient)"
          strokeWidth="1.2"
          strokeDasharray="5 9"
          opacity="0.7"
        />

        {/* Destination marker — gold glow */}
        <circle
          cx="1355"
          cy="215"
          r="3"
          fill="rgba(229,183,106,0.85)"
          filter="url(#glowFilter)"
        />
        <circle
          cx="1355"
          cy="215"
          r="9"
          fill="none"
          stroke="rgba(229,183,106,0.25)"
          strokeWidth="1"
          style={{ animation: 'landing-pulse-glow 5s ease-in-out infinite' }}
        />
        <circle
          cx="1355"
          cy="215"
          r="18"
          fill="none"
          stroke="rgba(229,183,106,0.08)"
          strokeWidth="0.8"
          style={{ animation: 'landing-pulse-glow 5s ease-in-out infinite 0.6s' }}
        />

        {/* Moving aircraft dot — copper */}
        <circle
          ref={aircraftRef}
          cx="100"
          cy="720"
          r="2.5"
          fill="#B96F5C"
          filter="url(#softGlow)"
          style={{ filter: 'drop-shadow(0 0 5px rgba(185,111,92,0.7))' }}
        />

        {/* Origin marker */}
        <circle cx="103" cy="718" r="1.5" fill="rgba(49,75,115,0.5)" />
      </svg>

      {/* ── Layer 4: Foreground content ── */}
      <div className="relative z-10 w-full max-w-7xl mx-auto px-5 sm:px-8 lg:px-10 pb-28 md:pb-36 pt-32">
        <div
          className="max-w-xl lg:max-w-2xl"
          style={{ animation: 'landing-fade-up 1s cubic-bezier(0.22,1,0.36,1) 0.2s both' }}
        >
          {/* Eyebrow */}
          <p
            className="text-eyebrow mb-5 md:mb-6"
            style={{
              color: 'var(--color-ody-copper)',
              animation: 'landing-fade-up 1s cubic-bezier(0.22,1,0.36,1) 0.1s both',
            }}
          >
            Your next move
          </p>

          {/* Headline */}
          <h1
            className="text-hero mb-6 md:mb-8"
            style={{
              color: 'var(--color-ody-ink)',
              animation: 'landing-fade-up 1s cubic-bezier(0.22,1,0.36,1) 0.3s both',
            }}
          >
            Turn intention
            <br />
            <span
              className="italic"
              style={{ color: 'var(--color-ody-gold)' }}
            >
              into action.
            </span>
          </h1>

          {/* Supporting text */}
          <p
            className="hero-supporting-text text-lg md:text-xl leading-relaxed max-w-lg mb-10 font-normal"
            style={{
              color: '#FFFFFF',
              textShadow: '0 2px 12px rgba(0, 0, 0, 0.8), 0 1px 3px rgba(0, 0, 0, 0.95)',
              animation: 'landing-fade-up 1s cubic-bezier(0.22,1,0.36,1) 0.45s both',
            }}
          >
            Odyssey remembers what matters, helps you decide what to do next,
            and turns every task into part of a journey.
          </p>

          {/* CTAs */}
          <div
            className="flex flex-col sm:flex-row items-start gap-4"
            style={{ animation: 'landing-fade-up 1s cubic-bezier(0.22,1,0.36,1) 0.6s both' }}
          >
            {/* Primary — gold gradient */}
            <Link
              to="/auth"
              className="inline-flex items-center px-7 py-3.5 text-sm font-semibold tracking-wide rounded-lg active:scale-[0.97] transition-all duration-200"
              style={{
                background: 'linear-gradient(135deg, var(--color-ody-copper) 0%, var(--color-ody-gold) 100%)',
                color: '#050817',
                boxShadow: '0 4px 24px -4px rgba(229,183,106,0.4)',
              }}
              onMouseEnter={e => {
                (e.currentTarget as HTMLAnchorElement).style.boxShadow = '0 6px 32px -4px rgba(229,183,106,0.6)';
                (e.currentTarget as HTMLAnchorElement).style.filter = 'brightness(1.08)';
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLAnchorElement).style.boxShadow = '0 4px 24px -4px rgba(229,183,106,0.4)';
                (e.currentTarget as HTMLAnchorElement).style.filter = 'brightness(1)';
              }}
            >
              Try Odyssey
              <svg className="ml-2.5 w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
              </svg>
            </Link>

            {/* Secondary — ghost text */}
            <button
              onClick={() => document.getElementById('how-it-works')?.scrollIntoView({ behavior: 'smooth' })}
              className="inline-flex items-center px-2 py-3.5 text-sm font-medium transition-colors duration-200 cursor-pointer bg-transparent border-none group"
              style={{ color: 'var(--color-ody-ink-muted)' }}
              onMouseEnter={e => (e.currentTarget.style.color = 'var(--color-ody-ink)')}
              onMouseLeave={e => (e.currentTarget.style.color = 'var(--color-ody-ink-muted)')}
            >
              See how it works
              <svg
                className="ml-2 w-4 h-4 transition-transform duration-200 group-hover:translate-y-0.5"
                fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 14l-7 7m0 0l-7-7m7 7V3" />
              </svg>
            </button>
          </div>
        </div>
      </div>

      {/* ── Scroll cue ── */}
      <div
        className="absolute bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2 z-10"
        style={{ animation: 'landing-fade-in 1s ease 1.4s both' }}
        aria-hidden="true"
      >
        <div
          className="w-px h-10"
          style={{
            background: 'linear-gradient(to bottom, transparent, var(--color-ody-border))',
            animation: 'landing-scroll-hint 2.5s ease-in-out infinite',
          }}
        />
        <div
          className="w-1 h-1 rounded-full"
          style={{ backgroundColor: 'var(--color-ody-copper)', opacity: 0.6 }}
        />
      </div>
    </section>
  );
}
