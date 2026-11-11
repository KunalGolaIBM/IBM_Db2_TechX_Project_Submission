// Where the live API lives when this page is served from GitHub Pages. Two routes to the same Codespace:
// the GitHub port URL, and a Cloudflare quick tunnel whose (changing) address the keep-alive job publishes
// on the 'endpoint' branch. The page uses whichever answers first. Served by the app itself, it uses its own origin.
window.AQT_API = window.AQT_API ||
  (location.hostname.endsWith("github.io") ? "https://super-invention-g475pv4x6vjw26wq-8000.app.github.dev" : "");
window.AQT_ALT = window.AQT_ALT ||
  (location.hostname.endsWith("github.io") ? "https://raw.githubusercontent.com/debi910/aqi-truth/endpoint/endpoint.json" : "");
