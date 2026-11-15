import { createBrowserRouter, RouterProvider, Navigate } from 'react-router-dom';
import { Analytics } from '@vercel/analytics/react';
import RootLayout from './layouts/RootLayout';
import Landing from './pages/Landing';
import Auth from './pages/Auth';
import Home from './pages/Home';
import Mission from './pages/Mission';
import Execute from './pages/Execute';
import Journey from './pages/Journey';
import Odyssey from './pages/Odyssey';
import { ThemeProvider } from './hooks/useTheme';

// ProtectedRoute is no longer used for core routes — the full Odyssey experience
// is accessible without authentication. Supabase-backed persistence is used when
// the user is signed in; localStorage is used otherwise.

const router = createBrowserRouter([
  {
    path: '/',
    element: <RootLayout />,
    children: [
      { index: true, element: <Landing /> },
      { path: 'auth',    element: <Auth /> },
      { path: 'home',    element: <Home /> },
      { path: 'mission', element: <Mission /> },
      { path: 'execute', element: <Execute /> },
      { path: 'journey', element: <Journey /> },
      { path: 'odyssey', element: <Odyssey /> },
      { path: '*',       element: <Navigate to="/" replace /> },
    ],
  },
]);

export default function App() {
  return (
    <ThemeProvider>
      <RouterProvider router={router} />
      <Analytics />
    </ThemeProvider>
  );
}
