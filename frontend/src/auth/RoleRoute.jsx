import { Outlet } from "react-router-dom";
import Alert from "@mui/material/Alert";
import AlertTitle from "@mui/material/AlertTitle";

import { FORBIDDEN_ERROR } from "../api.js";
import { useAuth } from "./AuthContext.jsx";

/**
 * Eine Route, die zusätzlich zur Anmeldung eine Rolle verlangt.
 *
 *     <Route element={<RoleRoute roles={["admin"]} />}>
 *       <Route path="users" element={<UsersPage />} />
 *     </Route>
 *
 * Gehört **innerhalb** von `ProtectedRoute` und `Layout`: Um die Anmeldung
 * kümmert sich `ProtectedRoute`, hier geht es nur noch um die Rolle. Deshalb
 * auch kein `Navigate` zur Anmeldeseite — wer angemeldet ist, aber die Rolle
 * nicht hat, ist nicht falsch angemeldet. Genau diese Unterscheidung macht das
 * Backend zwischen `401` und `403` (docs/auth-api.md), und der Satz ist
 * derselbe.
 *
 * Ausblenden ist Bedienkomfort, keine Absicherung: Durchgesetzt wird die Rolle
 * im Backend, das ohne `admin` auch dann `403` antwortet, wenn jemand die
 * Adresse direkt aufruft.
 */
export function RoleRoute({ roles }) {
  const { hasRole } = useAuth();

  if (!hasRole(...roles)) {
    return (
      <Alert severity="warning">
        <AlertTitle>Kein Zugriff</AlertTitle>
        {FORBIDDEN_ERROR}
      </Alert>
    );
  }

  return <Outlet />;
}
