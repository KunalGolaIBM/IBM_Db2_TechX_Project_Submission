import { useMemo } from 'react';
import { useTheme } from '../hooks/useTheme';

interface Particle {
  id: number;
  x: number;
  y: number;
  size: number;
  duration: number;
  delay: number;
  opacity: number;
}

function generateParticles(count: number): Particle[] {
  const particles: Particle[] = [];
  for (let i = 0; i < count; i++) {
    particles.push({
      id: i,
      x: Math.random() * 100,
      y: Math.random() * 100,
      size: Math.random() * 1.8 + 0.6,
      duration: Math.random() * 4 + 2.5,
      delay: Math.random() * 5,
      opacity: Math.random() * 0.4 + 0.15,
    });
  }
  return particles;
}

export default function AtmosphericBackground() {
  const { theme } = useTheme();
  const isLight = theme === 'light';
  const particles = useMemo(() => generateParticles(isLight ? 45 : 80), [isLight]);

  if (isLight) {
    return (
      <div
        className="atmospheric-background fixed inset-0 -z-10 overflow-hidden pointer-events-none select-none"
        style={{
          background: 'linear-gradient(180deg, #E6ECEB 0%, #E0EAE9 30%, #DDE6DC 65%, #D8E5E3 100%)',
        }}
      >
        {/* Soft morning sun / orbital celestial glow — top right (matching odyssey2-bg.png) */}
        <div
          className="absolute top-0 right-0 rounded-full"
          style={{
            width: '55vw',
            height: '55vw',
            background: 'radial-gradient(circle at 75% 25%, rgba(213, 166, 83, 0.18) 0%, rgba(201, 130, 104, 0.1) 40%, transparent 75%)',
            transform: 'translate(10%, -15%)',
            filter: 'blur(30px)',
          }}
        />

        {/* Soft mountain mist / sage atmosphere — bottom left (matching odyssey2-bg.png) */}
        <div
          className="absolute bottom-0 left-0 rounded-full"
          style={{
            width: '65vw',
            height: '55vw',
            background: 'radial-gradient(circle at 30% 70%, rgba(221, 230, 220, 0.75) 0%, rgba(216, 229, 227, 0.45) 45%, transparent 75%)',
            transform: 'translate(-15%, 15%)',
            filter: 'blur(40px)',
          }}
        />

        {/* Pale sky horizon wash — center */}
        <div
          className="absolute inset-0"
          style={{
            background: 'radial-gradient(ellipse 90% 60% at 50% 40%, rgba(220, 231, 232, 0.6) 0%, transparent 80%)',
          }}
        />

        {/* Light sunlit dust particles */}
        {particles.map((p) => (
          <div
            key={p.id}
            className="absolute rounded-full star-twinkle"
            style={{
              left: `${p.x}%`,
              top: `${p.y}%`,
              width: `${p.size}px`,
              height: `${p.size}px`,
              backgroundColor: p.id % 4 === 0 ? '#D5A653' : p.id % 4 === 1 ? '#C98268' : '#7A8F9E',
              opacity: p.opacity * 0.85,
              '--duration': `${p.duration}s`,
              animationDelay: `${p.delay}s`,
            } as React.CSSProperties}
          />
        ))}

        {/* Subtle geometric cartography grid */}
        <div
          className="absolute inset-0"
          style={{
            backgroundImage:
              'linear-gradient(to right, rgba(38, 56, 74, 0.03) 1px, transparent 1px), ' +
              'linear-gradient(to bottom, rgba(38, 56, 74, 0.03) 1px, transparent 1px)',
            backgroundSize: '6rem 6rem',
          }}
        />
      </div>
    );
  }

  return (
    <div
      className="atmospheric-background fixed inset-0 -z-10 overflow-hidden pointer-events-none select-none"
      style={{ backgroundColor: 'var(--color-app-bg)' }}
    >
      {/* Deep space gradient layers */}
      <div
        className="absolute inset-0"
        style={{
          background:
            'radial-gradient(ellipse at 20% 50%, rgba(8,25,60,0.6) 0%, transparent 60%), ' +
            'radial-gradient(ellipse at 80% 20%, rgba(12,30,70,0.4) 0%, transparent 50%)',
        }}
      />

      {/* Subtle bronze mission glow — top right */}
      <div
        className="absolute top-0 right-0 rounded-full"
        style={{
          width: '40vw',
          height: '40vw',
          background: 'radial-gradient(circle, rgba(184,122,85,0.04) 0%, transparent 70%)',
          transform: 'translate(15%, -15%)',
        }}
      />

      {/* Subtle deep blue atmosphere — bottom left */}
      <div
        className="absolute bottom-0 left-0 rounded-full"
        style={{
          width: '55vw',
          height: '45vw',
          background: 'radial-gradient(circle, rgba(10,40,90,0.35) 0%, transparent 70%)',
          transform: 'translate(-20%, 20%)',
        }}
      />

      {/* Stars */}
      {particles.map((star) => (
        <div
          key={star.id}
          className="absolute rounded-full star-twinkle"
          style={{
            left: `${star.x}%`,
            top: `${star.y}%`,
            width: `${star.size}px`,
            height: `${star.size}px`,
            backgroundColor: star.id % 7 === 0 ? '#D6A84F' : '#E8E2D9',
            opacity: star.opacity,
            '--duration': `${star.duration}s`,
            animationDelay: `${star.delay}s`,
          } as React.CSSProperties}
        />
      ))}

      {/* Extremely faint nav grid overlay */}
      <div
        className="absolute inset-0"
        style={{
          backgroundImage:
            'linear-gradient(to right, rgba(30,60,100,0.05) 1px, transparent 1px), ' +
            'linear-gradient(to bottom, rgba(30,60,100,0.05) 1px, transparent 1px)',
          backgroundSize: '6rem 6rem',
        }}
      />
    </div>
  );
}
