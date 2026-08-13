import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getCurrentUser } from "./api.js";
import { AuthProvider } from "./auth/AuthContext.jsx";
import { Layout } from "./Layout.jsx";

// Nur die Netzwerkfunktionen ersetzen. `ApiError` bleibt die echte Klasse,
// sonst geht das `instanceof` in `AuthContext` ins Leere.
vi.mock("./api.js", async () => ({
  ...(await vi.importActual("./api.js")),
  getCurrentUser: vi.fn(),
  login: vi.fn(),
  apiRequest: vi.fn(),
}));

const adminUser = {
  id: 1,
  email: "anna.admin@medidoc.test",
  name: "Anna Admin",
  role: "admin",
};

const staffUser = {
  id: 2,
  email: "tom.staff@medidoc.test",
  name: "Tom Staff",
  role: "staff",
};

function renderLayout(currentUser = adminUser) {
  window.localStorage.setItem("medidoc.accessToken", "stored-token");
  getCurrentUser.mockResolvedValue(currentUser);

  return render(
    <MemoryRouter initialEntries={["/"]}>
      <AuthProvider>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<p>Startseite-Platzhalter</p>} />
            <Route path="/users" element={<p>Benutzerverwaltung-Platzhalter</p>} />
          </Route>
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("Layout", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("führt einen admin aus der Navigation in die Benutzerverwaltung", async () => {
    renderLayout();

    fireEvent.click(
      await screen.findByRole("link", { name: "Benutzerverwaltung" }),
    );

    expect(
      await screen.findByText("Benutzerverwaltung-Platzhalter"),
    ).toBeInTheDocument();
  });

  it("zeigt staff den Weg in die Benutzerverwaltung gar nicht erst", async () => {
    renderLayout(staffUser);

    // Erst warten, bis die Sitzung steht — sonst prueft der Test nur, dass die
    // Kopfzeile noch gar nichts anzeigt.
    expect(
      await screen.findByRole("link", { name: "Patientenübersicht" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Benutzerverwaltung" }),
    ).not.toBeInTheDocument();
  });

  it("nennt den angemeldeten Benutzer mit seiner Rolle", async () => {
    renderLayout();

    // Der Name steht hervorgehoben in einem eigenen Element, die Rolle daneben.
    // Geprueft wird die Zeile als Ganzes: Gemeint ist, dass beides zusammen
    // dasteht, nicht wie es ausgezeichnet ist.
    const name = await screen.findByText("Anna Admin");
    expect(name.parentElement).toHaveTextContent("Anna Admin · Administrator");
  });
});
