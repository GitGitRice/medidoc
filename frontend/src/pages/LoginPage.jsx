import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext.jsx";

/**
 * Wohin es nach der Anmeldung zurückgeht.
 *
 * `ProtectedRoute` legt die ursprünglich gewünschte Adresse als `state.from`
 * ab. Nur ein Pfad auf *dieser* Seite wird übernommen: Ein `//fremde.seite`
 * oder ein Backslash (den manche Browser wie einen Schrägstrich behandeln)
 * würde die Anmeldung sonst zu einer offenen Weiterleitung machen.
 *
 * Query und Fragment gehören zur Adresse dazu — ohne sie landet man nach der
 * Anmeldung zwar auf der richtigen Seite, aber auf Seite 1 statt auf der,
 * die man aufgerufen hatte.
 */
export function getReturnPath(location) {
  const from = location.state?.from;
  const path = from?.pathname;
  const isLocalPath =
    typeof path === "string" &&
    path.startsWith("/") &&
    !path.startsWith("//") &&
    !path.includes("\\");

  if (!isLocalPath) {
    return "/";
  }

  return `${path}${from.search ?? ""}${from.hash ?? ""}`;
}

export function LoginPage() {
  const { isLoading, login, user } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (isLoading) {
    return (
      <main className="page" aria-live="polite">
        <p>Sitzung wird geprüft …</p>
      </main>
    );
  }

  if (user) {
    return <Navigate to={getReturnPath(location)} replace />;
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setIsSubmitting(true);

    try {
      await login(email, password);
      navigate(getReturnPath(location), { replace: true });
    } catch (loginError) {
      setError(loginError.message);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="page">
      <h1>MediDoc</h1>
      <h2>Anmelden</h2>

      <form onSubmit={handleSubmit} aria-busy={isSubmitting}>
        <label>
          E-Mail
          <input
            type="email"
            name="email"
            autoComplete="username"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </label>

        <label>
          Passwort
          <input
            type="password"
            name="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>

        {error ? (
          <p className="error" role="alert">
            {error}
          </p>
        ) : null}

        <button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Anmeldung läuft …" : "Anmelden"}
        </button>
      </form>
    </main>
  );
}
