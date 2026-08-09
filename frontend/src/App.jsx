import { Navigate, Route, Routes } from "react-router-dom";

import { ProtectedRoute } from "./auth/ProtectedRoute.jsx";
import { RoleRoute } from "./auth/RoleRoute.jsx";
import { Layout } from "./Layout.jsx";
import { HomePage } from "./pages/HomePage.jsx";
import { LoginPage } from "./pages/LoginPage.jsx";
import { NotFoundPage } from "./pages/NotFoundPage.jsx";
import { PatientDetailPage } from "./pages/PatientDetailPage.jsx";
import { UsersPage } from "./pages/UsersPage.jsx";

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route index element={<HomePage />} />
          <Route path="patients/:patientId" element={<PatientDetailPage />} />
          {/* Innerhalb von Layout: Wem die Rolle fehlt, der bekommt die
              Meldung im gewohnten Rahmen und nicht eine nackte Seite ohne
              Weg zurück. */}
          <Route element={<RoleRoute roles={["admin"]} />}>
            <Route path="users" element={<UsersPage />} />
          </Route>
        </Route>
      </Route>
      <Route path="/home" element={<Navigate to="/" replace />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
