import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <main className="page">
      <h1>Seite nicht gefunden</h1>
      <p>
        <Link to="/">Zur Startseite</Link>
      </p>
    </main>
  );
}
