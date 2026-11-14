// Minimal service worker: makes PayGuard installable so it appears in the Android share sheet.
// Network-only on purpose - scam checks must always use live data.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", () => {});
