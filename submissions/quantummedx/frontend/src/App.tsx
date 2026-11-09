import { useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { Atom, Bot, Database, FileText, FlaskConical, LogOut } from "lucide-react";
import { api, getToken, setToken } from "./api";
import Auth from "./pages/Auth";
import Datasets from "./pages/Datasets";
import Lab from "./pages/Lab";
import Agents from "./pages/Agents";
import Reports from "./pages/Reports";

const nav = [
  { to: "/datasets", label: "Datasets", icon: Database },
  { to: "/lab", label: "Experiments", icon: FlaskConical },
  { to: "/agents", label: "AI agents", icon: Bot },
  { to: "/reports", label: "Reports", icon: FileText },
];

function DbChip() {
  const [state, setState] = useState<"checking" | "up" | "down">("checking");
  useEffect(() => {
    api.get("/api/system/db-status").then(() => setState("up")).catch(() => setState("down"));
  }, []);
  const map = { checking: ["bg-warn", "Checking Db2"], up: ["bg-ok", "Db2 connected"], down: ["bg-bad", "Db2 unavailable"] } as const;
  return <div className="flex items-center gap-2 text-xs text-mute"><span className={`h-2 w-2 rounded-full ${map[state][0]}`} />{map[state][1]}</div>;
}

export default function App() {
  const [authed, setAuthed] = useState(!!getToken());
  const logout = () => { setToken(null); setAuthed(false); };
  if (!authed) return <Auth onDone={() => setAuthed(true)} />;
  return (
    <div className="min-h-screen md:flex">
      <aside className="bg-rail border-line md:w-56 md:min-h-screen border-b md:border-b-0 md:border-r p-4 flex md:flex-col gap-4">
        <div className="flex items-center gap-2 font-semibold"><Atom className="text-quantum" size={22} />QuantumMedX</div>
        <nav className="flex md:flex-col gap-1 flex-1" aria-label="Main">
          {nav.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} className={({ isActive }) => `flex items-center gap-2 rounded-md px-3 py-2 text-sm ${isActive ? "bg-lift text-white" : "text-mute hover:text-white"}`}>
              <Icon size={16} />{label}
            </NavLink>
          ))}
        </nav>
        <div className="hidden md:flex flex-col gap-3">
          <DbChip />
          <button className="btn-ghost btn flex items-center gap-2 text-sm" onClick={logout}><LogOut size={14} />Sign out</button>
        </div>
      </aside>
      <main className="flex-1 p-5 md:p-8 max-w-6xl">
        <Routes>
          <Route path="/datasets" element={<Datasets />} />
          <Route path="/lab" element={<Lab />} />
          <Route path="/agents" element={<Agents />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="*" element={<Navigate to="/datasets" replace />} />
        </Routes>
        <p className="mt-10 text-xs text-mute max-w-prose">Research and education prototype. Results are not medical advice or a clinical diagnosis. The quantum model runs on a local simulator.</p>
      </main>
    </div>
  );
}
