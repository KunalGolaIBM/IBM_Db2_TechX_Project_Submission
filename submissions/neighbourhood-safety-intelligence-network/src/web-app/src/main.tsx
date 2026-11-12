import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'
import { setApiBaseUrl } from './services/api'

async function boot() {
  // Hosted demo builds point at a live.json that names the current backend URL.
  const liveConfig = import.meta.env.VITE_LIVE_CONFIG
  if (liveConfig) {
    try {
      const cfg = await fetch(liveConfig, { cache: 'no-store' }).then((r) => r.json())
      setApiBaseUrl(cfg.apiUrl)
    } catch {
      /* keep the build-time URL */
    }
  }
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
}
boot()
