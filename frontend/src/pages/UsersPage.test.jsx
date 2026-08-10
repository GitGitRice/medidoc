import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiRequest, getCurrentUser } from "../api.js";
import { AuthProvider } from "../auth/AuthContext.jsx";
import { UsersPage } from "./UsersPage.jsx";

// Nur die Netzwerkfunktionen ersetzen. `ApiError` bleibt die echte Klasse,
// sonst geht das `instanceof` in `AuthContext` ins Leere.
vi.mock("../api.js", async () => ({
  ...(await vi.importActual("../api.js")),
  getCurrentUser: vi.fn(),
  login: vi.fn(),
  apiRequest: vi.fn(),
}));

const anna = {
  id: 1,
  email: "anna.admin@medidoc.test",
  name: "Anna Admin",
  role: "admin",
  is_active: true,
};

const tom = {
  id: 2,
  email: "tom.staff@medidoc.test",
  name: "Tom Staff",
  role: "staff",
  is_active: true,
};

/** Antwort auf `GET /users` — die Form aus `UserPage` im Backend. */
function page(items) {
  return { items, total: items.length, limit: 25, offset: 0 };
}

/**
 * Beantwortet die Liste, lässt Änderungen aber einzeln festlegen.
 *
 * `onPatch`/`onPost` bekommen den Rumpf des Requests und geben zurück, was das
 * Backend antworten würde — oder werfen, um einen Fehler zu proben.
 */
function mockBackend({ items = [anna, tom], onPatch, onPost } = {}) {
  apiRequest.mockImplementation((path, options = {}) => {
    const body = options.body ? JSON.parse(options.body) : null;

    if (options.method === "PATCH") {
      const id = Number(path.split("/").at(-1));
      const target = items.find((user) => user.id === id);
      return Promise.resolve(onPatch ? onPatch(body, target) : { ...target, ...body });
    }

    if (options.method === "POST") {
      return Promise.resolve(onPost ? onPost(body) : { id: 3, ...body });
    }

    return Promise.resolve(page(items));
  });
}

function renderUsersPage(currentUser = anna) {
  window.localStorage.setItem("medidoc.accessToken", "stored-token");
  getCurrentUser.mockResolvedValue(currentUser);

  return render(
    <MemoryRouter>
      <AuthProvider>
        <UsersPage />
      </AuthProvider>
    </MemoryRouter>,
  );
}

/** Die Zeile eines Benutzers — die Aktionen stehen je Zeile, nicht global. */
function row(name) {
  return screen.getByRole("row", { name: new RegExp(name) });
}

describe("UsersPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("zeigt einen Ladehinweis, während die Benutzer geholt werden", async () => {
    apiRequest.mockImplementation(() => new Promise(() => {}));

    renderUsersPage();

    expect(
      await screen.findByRole("progressbar", { name: "Benutzer werden geladen" }),
    ).toBeInTheDocument();
  });

  it("zeigt Name, E-Mail, Rolle und Status eines Benutzers", async () => {
    mockBackend();

    renderUsersPage();

    expect(await screen.findByRole("cell", { name: /Tom Staff/ })).toBeInTheDocument();
    expect(
      screen.getByRole("cell", { name: "tom.staff@medidoc.test" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Rolle von Tom Staff")).toHaveValue("staff");
    expect(within(row("Tom Staff")).getByText("Aktiv")).toBeInTheDocument();
  });

  it("zeigt deaktivierte Benutzer als deaktiviert", async () => {
    mockBackend({ items: [anna, { ...tom, is_active: false }] });

    renderUsersPage();

    expect(
      within(await screen.findByRole("row", { name: /Tom Staff/ })).getByText(
        "Deaktiviert",
      ),
    ).toBeInTheDocument();
  });

  it("zeigt die Fehlermeldung, wenn die Liste nicht geladen werden kann", async () => {
    apiRequest.mockRejectedValue(
      new ApiError("Das Backend ist nicht erreichbar.", 0),
    );

    renderUsersPage();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Das Backend ist nicht erreichbar.",
    );
  });

  it("ändert die Rolle über einen PATCH und zeigt den neuen Wert", async () => {
    mockBackend();

    renderUsersPage();

    fireEvent.change(await screen.findByLabelText("Rolle von Tom Staff"), {
      target: { value: "admin" },
    });

    await waitFor(() => {
      expect(apiRequest).toHaveBeenLastCalledWith(
        "/users/2",
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify({ role: "admin" }),
          token: "stored-token",
        }),
      );
    });
    expect(await screen.findByLabelText("Rolle von Tom Staff")).toHaveValue("admin");
  });

  it("deaktiviert einen Benutzer erst nach der Rückfrage", async () => {
    mockBackend();

    renderUsersPage();

    fireEvent.click(
      await screen.findByRole("button", { name: "Tom Staff deaktivieren" }),
    );

    // Solange die Rückfrage offen steht, ist noch nichts passiert.
    expect(await screen.findByRole("dialog")).toHaveTextContent(
      "Benutzer deaktivieren?",
    );
    expect(apiRequest).not.toHaveBeenCalledWith(
      "/users/2",
      expect.objectContaining({ method: "PATCH" }),
    );

    fireEvent.click(screen.getByRole("button", { name: "Deaktivieren" }));

    await waitFor(() => {
      expect(apiRequest).toHaveBeenLastCalledWith(
        "/users/2",
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify({ is_active: false }),
        }),
      );
    });
    // `waitFor`, weil die Tabelle erst wieder auffindbar ist, wenn der Dialog
    // fort ist: Ein offener MUI-Dialog versteckt den Rest der Seite vor
    // Vorlesesoftware (`aria-hidden`) — und damit auch vor `getByRole`.
    await waitFor(() =>
      expect(within(row("Tom Staff")).getByText("Deaktiviert")).toBeInTheDocument(),
    );
  });

  it("schickt nichts, wenn die Rückfrage abgebrochen wird", async () => {
    mockBackend();

    renderUsersPage();

    fireEvent.click(
      await screen.findByRole("button", { name: "Tom Staff deaktivieren" }),
    );
    fireEvent.click(await screen.findByRole("button", { name: "Abbrechen" }));

    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
    );
    expect(apiRequest).not.toHaveBeenCalledWith(
      "/users/2",
      expect.objectContaining({ method: "PATCH" }),
    );
  });

  it("holt einen deaktivierten Benutzer wieder zurück", async () => {
    mockBackend({ items: [anna, { ...tom, is_active: false }] });

    renderUsersPage();

    fireEvent.click(
      await screen.findByRole("button", { name: "Tom Staff wieder aktivieren" }),
    );

    await waitFor(() => {
      expect(apiRequest).toHaveBeenLastCalledWith(
        "/users/2",
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify({ is_active: true }),
        }),
      );
    });
    expect(within(row("Tom Staff")).getByText("Aktiv")).toBeInTheDocument();
  });

  it("zeigt den Fehler des Backends, statt ihn zu verschlucken", async () => {
    mockBackend({
      onPatch: () => {
        throw new ApiError("Du kannst dein eigenes Konto nicht deaktivieren", 409);
      },
    });

    renderUsersPage();

    fireEvent.change(await screen.findByLabelText("Rolle von Tom Staff"), {
      target: { value: "admin" },
    });

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Du kannst dein eigenes Konto nicht deaktivieren",
    );
    // Die Liste bleibt stehen — ein misslungener Klick kostet nicht die Tabelle.
    expect(screen.getByRole("cell", { name: /Tom Staff/ })).toBeInTheDocument();
  });

  it("sperrt die Bedienelemente am eigenen Konto", async () => {
    mockBackend();

    renderUsersPage();

    expect(await screen.findByLabelText("Rolle von Anna Admin")).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Anna Admin deaktivieren" }),
    ).toBeDisabled();
    // Die eines anderen Benutzers bleiben bedienbar.
    expect(screen.getByLabelText("Rolle von Tom Staff")).toBeEnabled();
  });

  it("legt einen Benutzer über das Formular an", async () => {
    mockBackend();

    renderUsersPage();

    fireEvent.click(
      await screen.findByRole("button", { name: "Benutzer anlegen" }),
    );

    const dialog = within(await screen.findByRole("dialog"));
    fireEvent.change(dialog.getByLabelText(/Name/), {
      target: { value: "Neue Kollegin" },
    });
    fireEvent.change(dialog.getByLabelText(/E-Mail/), {
      target: { value: "neue.kollegin@medidoc.test" },
    });
    fireEvent.change(dialog.getByLabelText(/Passwort/), {
      target: { value: "geheim123" },
    });
    fireEvent.change(dialog.getByLabelText(/Rolle/), {
      target: { value: "admin" },
    });
    fireEvent.click(dialog.getByRole("button", { name: "Anlegen" }));

    await waitFor(() => {
      expect(apiRequest).toHaveBeenCalledWith(
        "/users",
        expect.objectContaining({
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: "Neue Kollegin",
            email: "neue.kollegin@medidoc.test",
            password: "geheim123",
            role: "admin",
          }),
          token: "stored-token",
        }),
      );
    });
    expect(
      await screen.findByText("Neue Kollegin wurde angelegt."),
    ).toBeInTheDocument();
  });

  it("lässt das Formular mit der Meldung des Backends stehen", async () => {
    mockBackend({
      onPost: () => {
        throw new ApiError(
          "Die E-Mail tom.staff@medidoc.test ist bereits einem Benutzer zugeordnet",
          409,
        );
      },
    });

    renderUsersPage();

    fireEvent.click(
      await screen.findByRole("button", { name: "Benutzer anlegen" }),
    );

    const dialog = within(await screen.findByRole("dialog"));
    fireEvent.change(dialog.getByLabelText(/Name/), { target: { value: "Tom" } });
    fireEvent.change(dialog.getByLabelText(/E-Mail/), {
      target: { value: "tom.staff@medidoc.test" },
    });
    fireEvent.change(dialog.getByLabelText(/Passwort/), {
      target: { value: "geheim123" },
    });
    fireEvent.click(dialog.getByRole("button", { name: "Anlegen" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "ist bereits einem Benutzer zugeordnet",
    );
    // Der Dialog bleibt offen, die Eingabe steht noch da.
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByLabelText(/E-Mail/)).toHaveValue("tom.staff@medidoc.test");
  });

  it("lädt bei Klick auf die nächste Seite mit passendem offset nach", async () => {
    const viele = Array.from({ length: 25 }, (_, index) => ({
      id: index + 10,
      email: `benutzer${index}@medidoc.test`,
      name: `Benutzer ${index}`,
      role: "staff",
      is_active: true,
    }));
    apiRequest.mockResolvedValue({
      items: viele,
      total: 30,
      limit: 25,
      offset: 0,
    });

    renderUsersPage();

    await screen.findByRole("cell", { name: "benutzer0@medidoc.test" });
    expect(apiRequest).toHaveBeenLastCalledWith(
      "/users?limit=25&offset=0",
      expect.objectContaining({ token: "stored-token" }),
    );

    fireEvent.click(screen.getByLabelText("Nächste Seite"));

    await waitFor(() => {
      expect(apiRequest).toHaveBeenLastCalledWith(
        "/users?limit=25&offset=25",
        expect.objectContaining({ token: "stored-token" }),
      );
    });
  });
});
