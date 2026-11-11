"use client";

import { useEffect, useRef } from "react";

/**
 * A small gradient cursor dot that follows the mouse instantly.
 */
export function CursorDot() {
  const dotRef = useRef<HTMLDivElement>(null);
  const pos = useRef({ x: -100, y: -100 });
  const frameId = useRef<number>(0);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      pos.current = { x: e.clientX, y: e.clientY };
    };
    window.addEventListener("mousemove", onMove);

    const animate = () => {
      if (dotRef.current) {
        dotRef.current.style.left = `${pos.current.x}px`;
        dotRef.current.style.top = `${pos.current.y}px`;
      }
      frameId.current = requestAnimationFrame(animate);
    };
    animate();

    const onLeave = () => {
      if (dotRef.current) dotRef.current.style.opacity = "0";
    };
    const onEnter = () => {
      if (dotRef.current) dotRef.current.style.opacity = "1";
    };
    document.addEventListener("mouseleave", onLeave);
    document.addEventListener("mouseenter", onEnter);

    return () => {
      cancelAnimationFrame(frameId.current);
      window.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseleave", onLeave);
      document.removeEventListener("mouseenter", onEnter);
    };
  }, []);

  return (
    <div
      ref={dotRef}
      className="hidden md:block"
      aria-hidden="true"
      style={{
        position: "fixed",
        width: 8,
        height: 8,
        borderRadius: "50%",
        background: "linear-gradient(135deg, #4FD9FF, #7A5CFF)",
        transform: "translate(-50%, -50%)",
        pointerEvents: "none",
        zIndex: 9999,
        mixBlendMode: "screen",
        transition: "opacity 0.2s ease",
      }}
    />
  );
}
