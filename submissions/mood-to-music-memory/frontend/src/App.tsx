import React from 'react';
import { HashRouter, Routes, Route, Navigate } from 'react-router-dom';
import AppShell from './components/shell/AppShell';
import HomePage from './pages/HomePage';
import NowPlayingPage from './pages/NowPlayingPage';
import LibraryPage from './pages/LibraryPage';
import MemoriesPage from './pages/MemoriesPage';
import AnalyticsPage from './pages/AnalyticsPage';

const App: React.FC = () => {
  return (
    <HashRouter>
      <AppShell>
        <Routes>
          <Route path="/" element={<Navigate to="/home" replace />} />
          <Route path="/home" element={<HomePage />} />
          <Route path="/now-playing" element={<NowPlayingPage />} />
          <Route path="/library" element={<LibraryPage />} />
          <Route path="/memories" element={<MemoriesPage />} />
          <Route path="/analytics" element={<AnalyticsPage />} />
        </Routes>
      </AppShell>
    </HashRouter>
  );
};

export default App;
