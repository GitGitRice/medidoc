import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App.jsx";
import { ApiError, getCurrentUser, login as requestLogin } from "./api.js";
import { AuthProvider } from "./auth/AuthContext.jsx";

// Nur die Netzwerkfunktionen ersetzen. `ApiError` bleibt die echte Klasse,
// sonst geht das `instanceof` in `AuthContext` ins Leere.
vi.mock("./api.js", async () => ({
  ...(await vi.importActual("./api.js")),
  getCurrentUser: vi.fn(),
  login: vi.fn(),
  apiRequest: vi.fn().mockResolvedValue({ items: [], total: 0, limit: 25, offset: 0 }),
}));

const user = {
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

function renderAt(path) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
}

async function fillLoginForm() {
  fireEvent.change(screen.getByLabelText("E-Mail"), {
    target: { value: user.email },
  });
  fireEvent.change(screen.getByLabelText("Passwort"), {
    target: { value: "geheim123" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Anmelden" }));
}

describe("Authentifizierung", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("leitet einen nicht angemeldeten Benutzer zur Login-Seite", async () => {
    renderAt("/");

    expect(
      await screen.findByRole("heading", { name: "Anmelden" }),
    ).toBeInTheDocument();
  });

  it("meldet einen Benutzer an und speichert den Token", async () => {
    requestLogin.mockResolvedValue({
      access_token: "test-token",
      token_type: "bearer",
      user,
    });
    renderAt("/login");

    await fillLoginForm();

    expect(
      await screen.findByRole("heading", { name: "Patientenübersicht" }),
    ).toBeInTheDocument();
    expect(requestLogin).toHaveBeenCalledWith(user.email, "geheim123");
    expect(window.localStorage.getItem("medidoc.accessToken")).toBe(
      "test-token",
    );
  });

  it("zeigt die Fehlermeldung des Backends", async () => {
    requestLogin.mockRejectedValue(
      new Error("E-Mail oder Passwort ist falsch"),
    );
    renderAt("/login");

    await fillLoginForm();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "E-Mail oder Passwort ist falsch",
    );
  });

  it("stellt eine gespeicherte Sitzung über /auth/me wieder her", async () => {
    window.localStorage.setItem("medidoc.accessToken", "stored-token");
    getCurrentUser.mockResolvedValue(user);
    renderAt("/");

    expect(
      await screen.findByRole("heading", { name: "Patientenübersicht" }),
    ).toBeInTheDocument();
    expect(getCurrentUser).toHaveBeenCalledWith(
      "stored-token",
      // Die Prüfung hängt an einem AbortSignal, damit ein Wechsel der Seite
      // den laufenden Request nicht verwaist stehen lässt.
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it("wirft die Sitzung nicht weg, wenn das Backend beim Laden schweigt", async () => {
    window.localStorage.setItem("medidoc.accessToken", "stored-token");
    getCurrentUser.mockRejectedValue(
      new ApiError("Das Backend ist nicht erreichbar.", 0),
    );
    renderAt("/");

    expect(
      await screen.findByRole("heading", {
        name: "Sitzung konnte nicht geprüft werden",
      }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Anmelden" }),
    ).not.toBeInTheDocument();
    expect(window.localStorage.getItem("medidoc.accessToken")).toBe(
      "stored-token",
    );

    // Und der zweite Anlauf führt ohne neue Anmeldung zurück in die Anwendung.
    getCurrentUser.mockResolvedValue(user);
    fireEvent.click(screen.getByRole("button", { name: "Erneut versuchen" }));

    expect(
      await screen.findByRole("heading", { name: "Patientenübersicht" }),
    ).toBeInTheDocument();
  });

  it("meldet den Benutzer ab und entfernt den Token", async () => {
    window.localStorage.setItem("medidoc.accessToken", "stored-token");
    getCurrentUser.mockResolvedValue(user);
    renderAt("/");

    fireEvent.click(await screen.findByRole("button", { name: "Abmelden" }));

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: "Anmelden" }),
      ).toBeInTheDocument();
    });
    expect(window.localStorage.getItem("medidoc.accessToken")).toBeNull();
  });
});

describe("Benutzerverwaltung", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("öffnet /users für einen admin", async () => {
    window.localStorage.setItem("medidoc.accessToken", "stored-token");
    getCurrentUser.mockResolvedValue(user);

    renderAt("/users");

    expect(
      await screen.findByRole("heading", { name: "Benutzerverwaltung" }),
    ).toBeInTheDocument();
  });

  it("zeigt einem staff-Benutzer dort die Meldung zur Berechtigung", async () => {
    window.localStorage.setItem("medidoc.accessToken", "stored-token");
    getCurrentUser.mockResolvedValue(staffUser);

    renderAt("/users");

    expect(await screen.findByText("Dazu fehlt dir die Berechtigung")).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Benutzerverwaltung" }),
    ).not.toBeInTheDocument();
    // Kein Rauswurf zur Anmeldung: Wer angemeldet ist, ist nicht falsch
    // angemeldet, nur nicht berechtigt (401 gegen 403, docs/auth-api.md).
    expect(
      screen.queryByRole("heading", { name: "Anmelden" }),
    ).not.toBeInTheDocument();
  });
});
