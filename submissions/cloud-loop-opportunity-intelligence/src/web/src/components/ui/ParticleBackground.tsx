"use client";

import { useEffect, useRef } from "react";
import { useTheme } from "next-themes";

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  color: string;
  alpha: number;
  targetAlpha: number;
  life: number;
  maxLife: number;
}

const COLORS_DARK = [
  "#4FD9FF",
  "#7A5CFF",
  "#A855F7",
  "#38bdf8",
  "#818cf8",
  "#c084fc",
  "#67e8f9",
  "#a78bfa",
];

const COLORS_LIGHT = [
  "#0ea5e9",
  "#6d28d9",
  "#7c3aed",
  "#0284c7",
  "#4f46e5",
  "#9333ea",
  "#0369a1",
  "#7e22ce",
];

export function ParticleBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const { resolvedTheme } = useTheme();
  const mouse = useRef({ x: -9999, y: -9999 });
  const particles = useRef<Particle[]>([]);
  const animFrameId = useRef<number>(0);
  const themeRef = useRef(resolvedTheme);

  useEffect(() => {
    themeRef.current = resolvedTheme;
  }, [resolvedTheme]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let width = window.innerWidth;
    let height = document.body.scrollHeight;

    const resize = () => {
      width = window.innerWidth;
      height = document.body.scrollHeight;
      canvas.width = width;
      canvas.height = height;
      initParticles();
    };

    // Static ambient dots — always visible, gently floating
    function initParticles() {
      const colors = themeRef.current === "dark" ? COLORS_DARK : COLORS_LIGHT;
      const count = Math.floor((width * height) / 14000);
      particles.current = Array.from({ length: count }, () => {
        const maxLife = 120 + Math.random() * 200;
        return {
          x: Math.random() * width,
          y: Math.random() * height,
          vx: (Math.random() - 0.5) * 0.3,
          vy: (Math.random() - 0.5) * 0.3,
          radius: 1 + Math.random() * 2,
          color: colors[Math.floor(Math.random() * colors.length)],
          alpha: 0,
          targetAlpha: 0.12 + Math.random() * 0.35,
          life: Math.floor(Math.random() * maxLife),
          maxLife,
        };
      });
    }

    // Spawn a burst of colorful dots near cursor
    function spawnCursorParticles(mx: number, my: number) {
      const colors = themeRef.current === "dark" ? COLORS_DARK : COLORS_LIGHT;
      const count = 2 + Math.floor(Math.random() * 3);
      for (let i = 0; i < count; i++) {
        const angle = Math.random() * Math.PI * 2;
        const speed = 0.4 + Math.random() * 1.2;
        const maxLife = 60 + Math.random() * 80;
        particles.current.push({
          x: mx + (Math.random() - 0.5) * 20,
          y: my + (Math.random() - 0.5) * 20,
          vx: Math.cos(angle) * speed,
          vy: Math.sin(angle) * speed,
          radius: 1.5 + Math.random() * 2.5,
          color: colors[Math.floor(Math.random() * colors.length)],
          alpha: 0,
          targetAlpha: 0.5 + Math.random() * 0.5,
          life: 0,
          maxLife,
        });
      }
      // Cap total
      if (particles.current.length > 400) {
        particles.current.splice(0, particles.current.length - 400);
      }
    }

    resize();
    window.addEventListener("resize", resize);

    // Mouse tracking
    const onMouseMove = (e: MouseEvent) => {
      mouse.current = { x: e.clientX, y: e.clientY + window.scrollY };
      spawnCursorParticles(mouse.current.x, mouse.current.y);
    };
    window.addEventListener("mousemove", onMouseMove);

    let lastMouse = { ...mouse.current };
    let frame = 0;

    function draw() {
      if (!ctx || !canvas) return;
      ctx.clearRect(0, 0, width, height);

      const mx = mouse.current.x;
      const my = mouse.current.y;

      // Periodically spawn ambient cursor particles even on slow moves
      frame++;
      if (frame % 4 === 0) {
        const dx = mx - lastMouse.x;
        const dy = my - lastMouse.y;
        if (dx * dx + dy * dy > 25) {
          spawnCursorParticles(mx, my);
          lastMouse = { x: mx, y: my };
        }
      }

      // Draw connection lines between close ambient particles
      ctx.lineWidth = 0.5;
      const CONNECT_DIST = 100;

      for (let i = 0; i < particles.current.length; i++) {
        const p = particles.current[i];

        // Lifecycle fade
        const halfLife = p.maxLife / 2;
        if (p.life < halfLife) {
          p.alpha = Math.min(p.alpha + 0.02, p.targetAlpha * (p.life / halfLife));
        } else {
          p.alpha = Math.max(p.alpha - 0.015, 0);
        }
        p.life++;

        // Cursor attraction/repulsion
        const dx = mx - p.x;
        const dy = my - p.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        const ATTRACT_DIST = 120;
        if (dist < ATTRACT_DIST && dist > 0) {
          const force = (1 - dist / ATTRACT_DIST) * 0.04;
          p.vx += (dx / dist) * force;
          p.vy += (dy / dist) * force;
        }

        // Damping
        p.vx *= 0.97;
        p.vy *= 0.97;
        p.x += p.vx;
        p.y += p.vy;

        // Draw dot
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
        ctx.fillStyle = hexToRgba(p.color, p.alpha);
        ctx.fill();

        // Connection lines
        for (let j = i + 1; j < Math.min(i + 15, particles.current.length); j++) {
          const q = particles.current[j];
          const cdx = p.x - q.x;
          const cdy = p.y - q.y;
          const cdist = Math.sqrt(cdx * cdx + cdy * cdy);
          if (cdist < CONNECT_DIST) {
            const lineAlpha = (1 - cdist / CONNECT_DIST) * Math.min(p.alpha, q.alpha) * 0.5;
            ctx.beginPath();
            ctx.moveTo(p.x, p.y);
            ctx.lineTo(q.x, q.y);
            ctx.strokeStyle = hexToRgba(p.color, lineAlpha);
            ctx.stroke();
          }
        }
      }

      // Remove dead particles (those that exceeded maxLife)
      particles.current = particles.current.filter((p) => p.life <= p.maxLife + 20);

      // Replenish ambient particles
      if (particles.current.length < Math.floor((width * height) / 14000)) {
        const colors = themeRef.current === "dark" ? COLORS_DARK : COLORS_LIGHT;
        const maxLife = 120 + Math.random() * 200;
        particles.current.push({
          x: Math.random() * width,
          y: Math.random() * height,
          vx: (Math.random() - 0.5) * 0.3,
          vy: (Math.random() - 0.5) * 0.3,
          radius: 1 + Math.random() * 2,
          color: colors[Math.floor(Math.random() * colors.length)],
          alpha: 0,
          targetAlpha: 0.12 + Math.random() * 0.35,
          life: 0,
          maxLife,
        });
      }

      animFrameId.current = requestAnimationFrame(draw);
    }

    draw();

    return () => {
      cancelAnimationFrame(animFrameId.current);
      window.removeEventListener("resize", resize);
      window.removeEventListener("mousemove", onMouseMove);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 pointer-events-none z-0"
      aria-hidden="true"
    />
  );
}

function hexToRgba(hex: string, alpha: number): string {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  if (!result) return `rgba(79,217,255,${alpha})`;
  return `rgba(${parseInt(result[1], 16)},${parseInt(result[2], 16)},${parseInt(result[3], 16)},${alpha})`;
}
