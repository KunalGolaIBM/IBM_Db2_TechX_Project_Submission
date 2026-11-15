import { useEffect, useRef } from 'react';

// ─── Types ────────────────────────────────────────────────────────────────────

interface Star {
  x: number;        // 0-1 (fraction of canvas width)
  y: number;        // 0-1 (fraction of canvas height)
  r: number;        // radius px
  opacity: number;
  color: string;
  twinkleSpeed: number;   // radians/frame added to phase
  twinklePhase: number;   // current phase
  twinkleAmp: number;     // 0–1 amplitude of opacity oscillation
  parallaxFactor: number; // 0 (fixed) – 1 (full scroll shift)
  isSparkle: boolean;     // four-point star shape
  sparkleSize: number;    // arm length for sparkle
}

// ─── Palette ──────────────────────────────────────────────────────────────────

const COLORS = {
  offWhite:  '#E8E7E2',
  coolBlue:  '#7FA7D9',
  gold:      '#E5B76A',
  copper:    '#B96F5C',
};

// Pick a color with probability weighting
function pickColor(): string {
  const r = Math.random();
  if (r < 0.62) return COLORS.offWhite;   // 62% — dominant
  if (r < 0.88) return COLORS.coolBlue;   // 26% — secondary
  if (r < 0.96) return COLORS.gold;       //  8% — sparse gold
  return COLORS.copper;                    //  4% — very rare copper
}

// ─── Star generation ──────────────────────────────────────────────────────────

/**
 * Generate stars in a given vertical band (yMin–yMax as 0-1 fractions)
 * so density can vary per section. sparkleRatio controls how many are
 * four-point sparkles (0–1).
 */
function generateBand(
  count: number,
  yMin: number,
  yMax: number,
  sparkleRatio = 0.04,
): Star[] {
  return Array.from({ length: count }, () => {
    const isSparkle = Math.random() < sparkleRatio;
    const r = isSparkle
      ? 0                            // sparkles are drawn by arm length, not radius
      : Math.random() * 1.2 + 0.3;  // 0.3–1.5 px dots

    return {
      x: Math.random(),
      y: yMin + Math.random() * (yMax - yMin),
      r,
      opacity: Math.random() * 0.45 + 0.15,
      color: pickColor(),
      twinkleSpeed: (Math.random() * 0.008 + 0.002) * (Math.random() < 0.5 ? 1 : -1),
      twinklePhase: Math.random() * Math.PI * 2,
      twinkleAmp: Math.random() * 0.35,  // most stars barely twinkle
      parallaxFactor: Math.random() * 0.18 + 0.02,  // very gentle — 0.02–0.20
      isSparkle,
      sparkleSize: isSparkle ? Math.random() * 3 + 2 : 0,  // 2–5 px arms
    };
  });
}

function buildStarField(): Star[] {
  // Four bands matching the rough section layout; vary count for density feel.
  // Hero  (0–0.32): sparser — image is dominant
  // Core  (0.32–0.55): medium
  // Exp   (0.55–0.80): slightly denser, more depth
  // CTA   (0.80–1.00): sparse again
  return [
    ...generateBand(55,  0,    0.32, 0.035),
    ...generateBand(70,  0.32, 0.55, 0.045),
    ...generateBand(85,  0.55, 0.80, 0.050),
    ...generateBand(45,  0.80, 1.00, 0.030),
  ];
}

// ─── Draw helpers ─────────────────────────────────────────────────────────────

function drawFourPointSparkle(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  size: number,
  opacity: number,
  color: string,
) {
  ctx.save();
  ctx.globalAlpha = opacity;

  // Primary cross arms
  const gradient = ctx.createRadialGradient(cx, cy, 0, cx, cy, size * 1.6);
  gradient.addColorStop(0,   color);
  gradient.addColorStop(0.3, color);
  gradient.addColorStop(1,   'transparent');

  ctx.strokeStyle = gradient;
  ctx.lineCap = 'round';

  // Long arms (vertical + horizontal)
  const longArm = size;
  ctx.lineWidth = 0.8;
  ctx.beginPath();
  ctx.moveTo(cx, cy - longArm);
  ctx.lineTo(cx, cy + longArm);
  ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(cx - longArm, cy);
  ctx.lineTo(cx + longArm, cy);
  ctx.stroke();

  // Diagonal shorter arms — creates the four-point feel
  const shortArm = size * 0.45;
  ctx.lineWidth = 0.5;
  ctx.globalAlpha = opacity * 0.45;
  ctx.beginPath();
  ctx.moveTo(cx - shortArm * 0.7, cy - shortArm * 0.7);
  ctx.lineTo(cx + shortArm * 0.7, cy + shortArm * 0.7);
  ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(cx + shortArm * 0.7, cy - shortArm * 0.7);
  ctx.lineTo(cx - shortArm * 0.7, cy + shortArm * 0.7);
  ctx.stroke();

  // Tiny center dot
  ctx.globalAlpha = opacity * 0.9;
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.arc(cx, cy, 0.7, 0, Math.PI * 2);
  ctx.fill();

  ctx.restore();
}

function drawDot(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  r: number,
  opacity: number,
  color: string,
) {
  // Larger stars get a soft glow halo
  if (r > 0.9) {
    const glow = ctx.createRadialGradient(cx, cy, 0, cx, cy, r * 4);
    glow.addColorStop(0,   color);
    glow.addColorStop(0.4, color);
    glow.addColorStop(1,   'transparent');
    ctx.globalAlpha = opacity * 0.15;
    ctx.fillStyle = glow;
    ctx.beginPath();
    ctx.arc(cx, cy, r * 4, 0, Math.PI * 2);
    ctx.fill();
  }

  ctx.globalAlpha = opacity;
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.arc(cx, cy, r, 0, Math.PI * 2);
  ctx.fill();
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function CosmicAtmosphere() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const starsRef  = useRef<Star[]>(buildStarField());
  const rafRef    = useRef<number>(0);
  const scrollYRef = useRef(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Respect reduced-motion: render one static frame only
    const prefersReducedMotion =
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    // ── Resize handler ───────────────────────────────────────────────────────
    const resize = () => {
      const dpr = window.devicePixelRatio || 1;
      const W = window.innerWidth;
      const H = document.documentElement.scrollHeight;
      canvas.width  = W * dpr;
      canvas.height = H * dpr;
      canvas.style.width  = `${W}px`;
      canvas.style.height = `${H}px`;
      ctx.scale(dpr, dpr);
    };

    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(document.documentElement);

    // ── Scroll listener — update ref (no re-render) ──────────────────────────
    const onScroll = () => { scrollYRef.current = window.scrollY; };
    window.addEventListener('scroll', onScroll, { passive: true });

    // ── Animation loop ───────────────────────────────────────────────────────
    const W = () => canvas.width  / (window.devicePixelRatio || 1);
    const H = () => canvas.height / (window.devicePixelRatio || 1);

    const frame = () => {
      const w = W();
      const h = H();
      const scroll = scrollYRef.current;

      ctx.clearRect(0, 0, w, h);

      for (const star of starsRef.current) {
        // Advance twinkle phase (skip when reduced-motion)
        if (!prefersReducedMotion) {
          star.twinklePhase += star.twinkleSpeed;
        }

        // Compute current opacity with gentle sine wave
        const twinkle = Math.sin(star.twinklePhase) * star.twinkleAmp;
        const opacity = Math.max(0.05, Math.min(1, star.opacity + twinkle));

        // Parallax — stars further back (low factor) move less with scroll
        const parallaxShift = scroll * star.parallaxFactor * 0.12;

        const px = star.x * w;
        const py = star.y * h - parallaxShift;

        // Skip if scrolled off canvas
        if (py < -20 || py > h + 20) continue;

        if (star.isSparkle) {
          drawFourPointSparkle(ctx, px, py, star.sparkleSize, opacity, star.color);
        } else {
          drawDot(ctx, px, py, star.r, opacity, star.color);
        }
      }

      ctx.globalAlpha = 1;
      rafRef.current = requestAnimationFrame(frame);
    };

    if (prefersReducedMotion) {
      // Static single draw — no animation loop
      const w = W();
      const h = H();
      ctx.clearRect(0, 0, w, h);
      for (const star of starsRef.current) {
        const px = star.x * w;
        const py = star.y * h;
        if (star.isSparkle) {
          drawFourPointSparkle(ctx, px, py, star.sparkleSize, star.opacity, star.color);
        } else {
          drawDot(ctx, px, py, star.r, star.opacity, star.color);
        }
      }
      ctx.globalAlpha = 1;
    } else {
      rafRef.current = requestAnimationFrame(frame);
    }

    return () => {
      cancelAnimationFrame(rafRef.current);
      ro.disconnect();
      window.removeEventListener('scroll', onScroll);
    };
  }, []);

  return (
    <>
      {/* Canvas star field — absolute so it covers full scroll height.
          Faded out over the hero (top ~32vh) so the bg image shines through. */}
      <canvas
        ref={canvasRef}
        aria-hidden="true"
        className="absolute inset-0 pointer-events-none select-none"
        style={{
          zIndex: 0,
          maskImage: 'linear-gradient(to bottom, transparent 0%, transparent 18%, rgba(0,0,0,0.4) 28%, black 40%)',
          WebkitMaskImage: 'linear-gradient(to bottom, transparent 0%, transparent 18%, rgba(0,0,0,0.4) 28%, black 40%)',
        }}
      />

      {/* CSS nebula / depth layers — fixed for performance.
          Also masked at the top so they don't compete with the hero image. */}

      {/* Primary nebula — upper-right warm copper hint */}
      <div
        aria-hidden="true"
        className="fixed pointer-events-none select-none"
        style={{
          inset: 0,
          zIndex: 0,
          background:
            'radial-gradient(ellipse 55% 40% at 78% 18%, rgba(185,111,92,0.055) 0%, transparent 70%)',
          maskImage: 'linear-gradient(to bottom, transparent 0%, black 35%)',
          WebkitMaskImage: 'linear-gradient(to bottom, transparent 0%, black 35%)',
        }}
      />

      {/* Secondary nebula — mid-left cool blue cloud */}
      <div
        aria-hidden="true"
        className="fixed pointer-events-none select-none"
        style={{
          inset: 0,
          zIndex: 0,
          background:
            'radial-gradient(ellipse 50% 35% at 15% 55%, rgba(127,167,217,0.05) 0%, transparent 65%)',
        }}
      />

      {/* Deep core glow — very subtle center-bottom warmth */}
      <div
        aria-hidden="true"
        className="fixed pointer-events-none select-none"
        style={{
          inset: 0,
          zIndex: 0,
          background:
            'radial-gradient(ellipse 60% 30% at 50% 85%, rgba(229,183,106,0.04) 0%, transparent 70%)',
        }}
      />

      {/* Faint deep-blue depth fill — reinforces the cosmic void */}
      <div
        aria-hidden="true"
        className="fixed pointer-events-none select-none"
        style={{
          inset: 0,
          zIndex: 0,
          background:
            'radial-gradient(ellipse 80% 60% at 50% 40%, rgba(16,26,53,0.35) 0%, transparent 75%)',
          maskImage: 'linear-gradient(to bottom, transparent 0%, black 40%)',
          WebkitMaskImage: 'linear-gradient(to bottom, transparent 0%, black 40%)',
        }}
      />
    </>
  );
}
