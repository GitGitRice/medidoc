import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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

const user = {
  id: 1,
  email: "anna.admin@medidoc.test",
  name: "Anna Admin",
  role: "admin",
};

function renderOverview() {
  window.localStorage.setItem("medidoc.accessToken", "stored-token");
  getCurrentUser.mockResolvedValue(user);

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
      await screen.findByText("Patienten werden geladen …"),
    ).toBeInTheDocument();
  });

  it("zeigt die Patienten als Tabelle, sortiert wie vom Backend geliefert", async () => {
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

  it("zeigt einen Hinweistext, wenn keine Patienten existieren", async () => {
    apiRequest.mockResolvedValue({ items: [], total: 0, limit: 25, offset: 0 });

    renderOverview();

    expect(
      await screen.findByText("Es sind noch keine Patienten angelegt."),
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
