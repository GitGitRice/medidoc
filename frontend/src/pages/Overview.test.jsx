import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiRequest, getCurrentUser } from "../api.js";
import { AuthProvider } from "../auth/AuthContext.jsx";
import { Overview } from "./Overview.jsx";

// Nur die Netzwerkfunktionen ersetzen. `ApiError` bleibt die echte Klasse,
// sonst geht das `instanceof` in `AuthContext` ins Leere.
vi.mock("../api.js", async () => ({
  ...(await vi.importActual("../api.js")),
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

const patient = {
  id: 9,
  first_name: "Max",
  last_name: "Mustermann",
  date_of_birth: "1985-06-15",
  insurance_number: "A123456789",
};

function renderOverview(currentUser = adminUser) {
  window.localStorage.setItem("medidoc.accessToken", "stored-token");
  getCurrentUser.mockResolvedValue(currentUser);

  return render(
    <MemoryRouter initialEntries={["/"]}>
      <AuthProvider>
        <Routes>
          <Route index element={<Overview />} />
          <Route path="/patients/:patientId" element={<p>Patientendetails-Platzhalter</p>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("Overview", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("zeigt einen Ladehinweis, während die Patienten geholt werden", async () => {
    apiRequest.mockImplementation(() => new Promise(() => {}));

    renderOverview();

    expect(
      await screen.findByRole("progressbar", { name: "Patienten werden geladen" }),
    ).toBeInTheDocument();
  });

  it("zeigt einen Patienten mit allen vier Spalten", async () => {
    apiRequest.mockResolvedValue({
      items: [
        {
          id: 1,
          first_name: "Max",
          last_name: "Mustermann",
          date_of_birth: "1985-06-15",
          insurance_number: "A123456789",
        },
      ],
      total: 1,
      limit: 25,
      offset: 0,
    });

    renderOverview();

    expect(
      await screen.findByRole("cell", { name: "Mustermann" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "Max" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "15.06.1985" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "A123456789" })).toBeInTheDocument();
  });

  it("übernimmt die vom Backend gelieferte Reihenfolge unverändert", async () => {
    // Sortiert nach Nachname/Vorname ist Aufgabe des Backends
    // (service.py: order_by last_name, first_name, id) — absichtlich NICHT
    // alphabetisch gemockt, damit ein versehentliches eigenes Sortieren im
    // Frontend hier auffiele.
    apiRequest.mockResolvedValue({
      items: [
        {
          id: 2,
          first_name: "Anton",
          last_name: "Weber",
          date_of_birth: "1985-06-15",
          insurance_number: "A123456789",
        },
        {
          id: 3,
          first_name: "Bea",
          last_name: "Albrecht",
          date_of_birth: "1975-03-02",
          insurance_number: null,
        },
        {
          id: 1,
          first_name: "Lena",
          last_name: "Weber",
          date_of_birth: "1990-01-02",
          insurance_number: "B987654321",
        },
      ],
      total: 3,
      limit: 25,
      offset: 0,
    });

    renderOverview();

    const rows = await screen.findAllByRole("row");
    const order = rows
      .slice(1) // erste Zeile ist die Kopfzeile
      .map((row) => within(row).getAllByRole("cell")[0].textContent);

    expect(order).toEqual(["Weber", "Albrecht", "Weber"]);
  });

  it("zeigt einen Hinweistext, wenn keine Patienten existieren", async () => {
    apiRequest.mockResolvedValue({ items: [], total: 0, limit: 25, offset: 0 });

    renderOverview();

    expect(
      await screen.findByText("Keine Patienten vorhanden"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Es wurden noch keine Patienten angelegt."),
    ).toBeInTheDocument();
  });

  it("zeigt die Fehlermeldung, wenn das Backend nicht antwortet", async () => {
    apiRequest.mockRejectedValue(
      new ApiError("Das Backend ist nicht erreichbar.", 0),
    );

    renderOverview();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Das Backend ist nicht erreichbar.",
    );
  });

  it("navigiert bei Klick auf eine Zeile zur Patientendetailseite", async () => {
    apiRequest.mockResolvedValue({
      items: [
        {
          id: 7,
          first_name: "Max",
          last_name: "Mustermann",
          date_of_birth: "1985-06-15",
          insurance_number: "A123456789",
        },
      ],
      total: 1,
      limit: 25,
      offset: 0,
    });

    renderOverview();

    fireEvent.click(await screen.findByRole("row", { name: /Mustermann/ }));

    expect(
      await screen.findByText("Patientendetails-Platzhalter"),
    ).toBeInTheDocument();
  });

  it("laedt bei Klick auf die naechste Seite mit passendem offset nach", async () => {
    apiRequest.mockResolvedValue({
      items: Array.from({ length: 25 }, (_, i) => ({
        id: i + 1,
        first_name: `Vorname${i}`,
        last_name: `Nachname${i}`,
        date_of_birth: "1990-01-01",
        insurance_number: null,
      })),
      total: 30,
      limit: 25,
      offset: 0,
    });

    renderOverview();

    await screen.findByRole("cell", { name: "Nachname0" });
    expect(apiRequest).toHaveBeenLastCalledWith(
      "/patients?limit=25&offset=0",
      expect.objectContaining({ token: "stored-token" }),
    );

    fireEvent.click(screen.getByLabelText("Nächste Seite"));

    await waitFor(() => {
      expect(apiRequest).toHaveBeenLastCalledWith(
        "/patients?limit=25&offset=25",
        expect.objectContaining({ token: "stored-token" }),
      );
    });
  });

  it("navigiert per Details-Button, unabhängig vom Zeilenklick", async () => {
    apiRequest.mockResolvedValue({ items: [patient], total: 1, limit: 25, offset: 0 });

    renderOverview();

    fireEvent.click(
      await screen.findByRole("button", { name: "Patientendetails öffnen" }),
    );

    expect(
      await screen.findByText("Patientendetails-Platzhalter"),
    ).toBeInTheDocument();
  });

  // Der Weg in die Benutzerverwaltung wird nicht mehr hier geprueft: Er steht
  // seit der Ueberarbeitung der Kopfzeile in der Navigation und damit in
  // `Layout.jsx` — geprueft wird er in `Layout.test.jsx`.

  it("zeigt den Details-Button auch für staff", async () => {
    apiRequest.mockResolvedValue({ items: [patient], total: 1, limit: 25, offset: 0 });

    renderOverview(staffUser);

    expect(
      await screen.findByRole("button", { name: "Patientendetails öffnen" }),
    ).toBeInTheDocument();
  });

  it("beschriftet die Seitensteuerung auf Deutsch", async () => {
    apiRequest.mockResolvedValue({
      items: Array.from({ length: 25 }, (_, i) => ({
        id: i + 1,
        first_name: `Vorname${i}`,
        last_name: `Nachname${i}`,
        date_of_birth: "1990-01-01",
        insurance_number: null,
      })),
      total: 30,
      limit: 25,
      offset: 0,
    });

    renderOverview();

    await screen.findByRole("cell", { name: "Nachname0" });

    expect(screen.getByText("Zeilen pro Seite:")).toBeInTheDocument();
    expect(screen.getByText("1–25 von 30")).toBeInTheDocument();
    expect(screen.getByLabelText("Erste Seite")).toBeInTheDocument();
    expect(screen.getByLabelText("Vorherige Seite")).toBeInTheDocument();
    expect(screen.getByLabelText("Nächste Seite")).toBeInTheDocument();
    expect(screen.getByLabelText("Letzte Seite")).toBeInTheDocument();
  });

  it("übernimmt fehlende Versichertennummer nicht als leere Zelle", async () => {
    apiRequest.mockResolvedValue({
      items: [
        {
          id: 2,
          first_name: "Erika",
          last_name: "Musterfrau",
          date_of_birth: "1990-01-02",
          insurance_number: null,
        },
      ],
      total: 1,
      limit: 25,
      offset: 0,
    });

    renderOverview();

    await waitFor(() =>
      expect(screen.getByRole("cell", { name: "Musterfrau" })).toBeInTheDocument(),
    );
    expect(screen.getByRole("cell", { name: "–" })).toBeInTheDocument();
  });
});
