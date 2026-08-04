import { useAuth } from "../auth/AuthContext.jsx";

export function HomePage() {
  const { user } = useAuth();

  return (
    <>
      <h2>Angemeldet</h2>
      <p>
        {user.name} ({user.email})
      </p>
      <p>Rolle: {user.role}</p>
      <p>Die Patientenübersicht wird in einem eigenen Arbeitsschritt ergänzt.</p>
    </>
  );
}
