import { NavLink, Outlet, Link } from "react-router-dom";

import { useAuth } from "./auth/AuthContext.jsx";

/** Kopfzeile und Navigation, gemeinsam für alle angemeldeten Seiten — #16. */
export function Layout() {
  const { logout } = useAuth();

  return (
    <div className="page">
      <header>
        <h1>MediDoc</h1>
        <nav>
          <NavLink to="/">Patientenübersicht</NavLink>
          <Link to="/patients/1">Patient 1</Link>
        </nav>
        <button type="button" onClick={logout}>
          Abmelden
        </button>
      </header>

      <main>
        <Outlet />
      </main>
    </div>
  );
}
