import { NavLink } from "react-router-dom";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard", icon: "▦" },
  { to: "/chat", label: "Chat workspace", icon: "💬" },
  { to: "/approvals", label: "Approvals", icon: "✓" },
  { to: "/config", label: "Configuration", icon: "⚙" },
] as const;

export default function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <span className="sidebar-logo">DB2</span>
        <div>
          <div className="sidebar-title">Ops Copilot</div>
          <div className="sidebar-subtitle">TechX Summit 2026</div>
        </div>
      </div>
      <nav className="sidebar-nav">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) =>
              isActive ? "nav-link nav-link-active" : "nav-link"
            }
          >
            <span className="nav-icon" aria-hidden>
              {item.icon}
            </span>
            {item.label}
          </NavLink>
        ))}
      </nav>
      <footer className="sidebar-footer">
        RAG + guardrailed text-to-SQL
        <br />
        over IBM Db2
      </footer>
    </aside>
  );
}
