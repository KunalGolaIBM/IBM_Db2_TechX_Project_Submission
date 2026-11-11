import { Navigate, Route, Routes } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import Dashboard from "./pages/Dashboard";
import ChatWorkspace from "./pages/ChatWorkspace";
import ConfigPage from "./pages/ConfigPage";
import ApprovalsPage from "./pages/ApprovalsPage";

/**
 * Application shell: fixed sidebar + routed content area.
 * Routes: / (dashboard), /chat, /config.
 */
export default function App() {
  return (
    <div className="app-shell">
      <Sidebar />
      <main className="app-main">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/chat" element={<ChatWorkspace />} />
          <Route path="/config" element={<ConfigPage />} />
          <Route path="/approvals" element={<ApprovalsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}
