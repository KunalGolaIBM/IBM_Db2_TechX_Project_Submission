import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import { DashboardProvider } from './state/DashboardContext';
import './index.css';

const container = document.getElementById('root');
if (!container) {
  throw new Error('Root container #root was not found in index.html');
}

createRoot(container).render(
  <StrictMode>
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <DashboardProvider>
        <App />
      </DashboardProvider>
    </BrowserRouter>
  </StrictMode>,
);
