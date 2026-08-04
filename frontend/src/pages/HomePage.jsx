import { useAuth } from "../auth/AuthContext.jsx";

export function HomePage() {
  const { logout, user } = useAuth();

  return (
    <div className="page">
      <header>
        <h1>MediDoc</h1>
        <button type="button" onClick={logout}>
          Abmelden
        </button>
      </header>

      <main>
        <h2>Angemeldet</h2>
        <p>
          {user.name} ({user.email})
        </p>
        <p>Rolle: {user.role}</p>
        <p>Die Patientenübersicht wird in einem eigenen Arbeitsschritt ergänzt.</p>
      </main>
    </div>
  );
}
