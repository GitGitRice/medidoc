import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "./AuthContext.jsx";

export function ProtectedRoute() {
  const { isLoading, retrySession, sessionError, user } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <main className="page" aria-live="polite">
        <p>Sitzung wird geprüft …</p>
      </main>
    );
  }

  // Der Token ist noch da, nur ungeprüft — das Backend hat nicht geantwortet.
  // Hier zur Login-Seite zu schicken hieße, eine gültige Sitzung wegen einer
  // Störung wegzuwerfen. Also stehen bleiben und noch einmal anbieten.
  if (sessionError) {
    return (
      <main className="page" aria-live="polite">
        <h1>Sitzung konnte nicht geprüft werden</h1>
        <p>{sessionError.message}</p>
        <button type="button" onClick={retrySession}>
          Erneut versuchen
        </button>
      </main>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return <Outlet />;
}
