import { useEffect, useRef, useState, useCallback } from 'react';

/**
 * Spring Class for Physics-Based Staggered Entrance
 * Tension: 220, Friction: 26, Mass: 1, Precision: 0.005, Substep: 1/240s
 */
export class SpringPhysics {
  tension: number;
  friction: number;
  mass: number;
  pos: number; // 1 = start (14px offset), 0 = rest target
  vel: number;
  target: number;
  precision: number;

  constructor(tension = 220, friction = 26, mass = 1) {
    this.tension = tension;
    this.friction = friction;
    this.mass = mass;
    this.pos = 1;
    this.vel = 0;
    this.target = 0;
    this.precision = 0.005;
  }

  step(dt: number): boolean {
    const subDt = 1 / 240;
    let accumulated = dt;
    while (accumulated > 0) {
      const stepTime = Math.min(accumulated, subDt);
      const force = -this.tension * (this.pos - this.target) - this.friction * this.vel;
      const accel = force / this.mass;
      this.vel += accel * stepTime;
      this.pos += this.vel * stepTime;
      accumulated -= stepTime;
    }
    return Math.abs(this.pos - this.target) < this.precision && Math.abs(this.vel) < this.precision;
  }
}

export function useSpringEntrance(totalItems: number, staggerDelay = 45) {
  const [replayKey, setReplayKey] = useState(0);
  const elementsRef = useRef<(HTMLElement | null)[]>([]);

  const registerItem = (index: number) => (el: HTMLElement | null) => {
    elementsRef.current[index] = el;
  };

  const replay = useCallback(() => {
    setReplayKey((k) => k + 1);
  }, []);

  // Keyboard shortcut: Shift + R to replay spring animation
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (
        (e.key === 'r' || e.key === 'R') &&
        e.shiftKey &&
        !['INPUT', 'TEXTAREA'].includes((e.target as HTMLElement)?.tagName)
      ) {
        e.preventDefault();
        replay();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [replay]);

  useEffect(() => {
    const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const elements = elementsRef.current.filter(Boolean) as HTMLElement[];
    if (elements.length === 0) return;

    if (prefersReduced) {
      elements.forEach((el) => {
        el.style.opacity = '1';
        el.style.transform = 'none';
      });
      return;
    }

    const springs = elements.map(() => new SpringPhysics(220, 26, 1));
    const startTimes = elements.map((_, i) => performance.now() + i * staggerDelay);

    elements.forEach((el) => {
      el.style.opacity = '0';
      el.style.transform = 'translateY(14px)';
      el.style.willChange = 'transform, opacity';
    });

    let animId = 0;
    let lastTime = performance.now();

    function loop(now: number) {
      const dt = Math.min(0.05, (now - lastTime) / 1000);
      lastTime = now;
      let allFinished = true;

      elements.forEach((el, i) => {
        if (now < startTimes[i]) {
          allFinished = false;
          return;
        }
        const finished = springs[i].step(dt);
        if (!finished) allFinished = false;

        const progress = 1 - springs[i].pos;
        const clampedProgress = Math.max(0, Math.min(1, progress));
        el.style.opacity = clampedProgress.toFixed(3);
        el.style.transform = `translateY(${(springs[i].pos * 14).toFixed(2)}px)`;
      });

      if (!allFinished) {
        animId = requestAnimationFrame(loop);
      } else {
        elements.forEach((el) => {
          el.style.opacity = '1';
          el.style.transform = 'none';
          el.style.willChange = 'auto';
        });
      }
    }

    animId = requestAnimationFrame(loop);

    return () => {
      cancelAnimationFrame(animId);
    };
  }, [totalItems, staggerDelay, replayKey]);

  return { registerItem, replay };
}
