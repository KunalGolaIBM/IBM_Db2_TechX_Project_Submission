// Lenis smooth scroll (studio-web references/scroll.md): lerp 0.1, wheel only, native momentum on touch,
// and no smoothing at all under prefers-reduced-motion. Native scroll position is kept, so sticky headers,
// find-in-page and keyboard scrolling still work. Inner scrollers opt out with data-lenis-prevent.
import Lenis from "lenis";
import "lenis/dist/lenis.css";

const reduced = matchMedia("(prefers-reduced-motion: reduce)");
let lenis: Lenis | null = null;
let raf = 0;

function start() {
  if (lenis || reduced.matches) return;
  lenis = new Lenis({ lerp: 0.1, smoothWheel: true, syncTouch: false, wheelMultiplier: 1, anchors: false, autoRaf: false });
  const loop = (t: number) => { lenis?.raf(t); raf = requestAnimationFrame(loop); };
  raf = requestAnimationFrame(loop);
  (window as unknown as { __lenis?: Lenis }).__lenis = lenis;
}

function stop() {
  cancelAnimationFrame(raf);
  lenis?.destroy();
  lenis = null;
  delete (window as unknown as { __lenis?: Lenis }).__lenis;
}

/** Start smooth scroll and follow the OS reduced-motion setting live. Returns a cleanup. */
export function initScroll(): () => void {
  start();
  const onChange = () => (reduced.matches ? stop() : start());
  reduced.addEventListener("change", onChange);
  return () => { reduced.removeEventListener("change", onChange); stop(); };
}

/** Jump to the top (view changes). */
export function scrollTop() {
  if (lenis) lenis.scrollTo(0, { immediate: true });
  else window.scrollTo(0, 0);
}

/** Smoothly bring an element into view below the sticky header. */
export function scrollToEl(el: Element | null, offset = -72) {
  if (!el) return;
  if (lenis) lenis.scrollTo(el as HTMLElement, { offset, duration: 1.1, easing: (t) => 1 - (1 - t) ** 4 });
  else el.scrollIntoView({ block: "start" });
}

/** Hold the page still while a dialog is open. */
export function lockScroll(on: boolean) {
  if (!lenis) return;
  if (on) lenis.stop(); else lenis.start();
}

/** Smoothly scroll to an absolute page offset (scroll-story chapter jumps). */
export function scrollToY(y: number) {
  if (lenis) lenis.scrollTo(y, { duration: 1.2, easing: (t) => 1 - (1 - t) ** 4 });
  else window.scrollTo({ top: y });
}
