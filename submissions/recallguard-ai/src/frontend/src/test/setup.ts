import "@testing-library/jest-dom/vitest";

class RO { observe() {} unobserve() {} disconnect() {} }
// jsdom lacks ResizeObserver (used by Recharts / React Flow)
(globalThis as unknown as { ResizeObserver: typeof RO }).ResizeObserver = RO;
