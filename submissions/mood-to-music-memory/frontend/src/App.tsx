import React, { useEffect } from 'react';
import { HashRouter, Routes, Route, Navigate } from 'react-router-dom';
import AppShell from './components/shell/AppShell';
import HomePage from './pages/HomePage';
import NowPlayingPage from './pages/NowPlayingPage';
import LibraryPage from './pages/LibraryPage';
import MemoriesPage from './pages/MemoriesPage';
import AnalyticsPage from './pages/AnalyticsPage';
import { useAppStore } from './store/appStore';

const App: React.FC = () => {
  const { loadSongsFromDb2, loadPlaylistsFromDb2, loadMemoriesFromDb2 } = useAppStore();

  // On mount: try to hydrate state from Db2 (falls back to mock data gracefully)
  useEffect(() => {
    void loadSongsFromDb2();
    void loadPlaylistsFromDb2();
    void loadMemoriesFromDb2();
  }, []);

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
