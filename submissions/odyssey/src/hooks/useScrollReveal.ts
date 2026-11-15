import { useEffect, useRef, useCallback } from 'react';

/**
 * Observes elements with the `scroll-reveal` class within a container
 * and adds the `revealed` class when they enter the viewport.
 */
export function useScrollReveal<T extends HTMLElement = HTMLDivElement>() {
  const ref = useRef<T>(null);

  const observe = useCallback(() => {
    const container = ref.current;
    if (!container) return;

    const elements = container.querySelectorAll('.scroll-reveal');
    if (elements.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('revealed');
            observer.unobserve(entry.target);
          }
        });
      },
      {
        threshold: 0.15,
        rootMargin: '0px 0px -40px 0px',
      }
    );

    elements.forEach((el) => observer.observe(el));

    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const cleanup = observe();
    return cleanup;
  }, [observe]);

  return ref;
}
