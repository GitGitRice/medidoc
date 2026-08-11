import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

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

// Die volle `PatientPublic`-Form, wie sie `GET /patients/9` liefern würde —
// mit den Feldern, die in der Tabellenzeile (`PatientListItem`) fehlen.
const fullPatient = {
  ...patient,
  email: "max.mustermann@example.test",
  phone: "0170 1234567",
  street: "Musterweg 1",
  postal_code: "12345",
  city: "Musterstadt",
  insurance_provider: "AOK",
  insurance_type: "statutory",
  notes: "Penicillin-Allergie",
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
      items: Array.from({ length: 10 }, (_, i) => ({
        id: i + 1,
        first_name: `Vorname${i}`,
        last_name: `Nachname${i}`,
        date_of_birth: "1990-01-01",
        insurance_number: null,
      })),
      total: 30,
      limit: 10,
      offset: 0,
    });

    renderOverview();

    await screen.findByRole("cell", { name: "Nachname0" });
    expect(apiRequest).toHaveBeenLastCalledWith(
      "/patients?limit=10&offset=0",
      expect.objectContaining({ token: "stored-token" }),
    );

    fireEvent.click(screen.getByLabelText("Nächste Seite"));

    await waitFor(() => {
      expect(apiRequest).toHaveBeenLastCalledWith(
        "/patients?limit=10&offset=10",
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
      items: Array.from({ length: 10 }, (_, i) => ({
        id: i + 1,
        first_name: `Vorname${i}`,
        last_name: `Nachname${i}`,
        date_of_birth: "1990-01-01",
        insurance_number: null,
      })),
      total: 30,
      limit: 10,
      offset: 0,
    });

    renderOverview();

    await screen.findByRole("cell", { name: "Nachname0" });

    expect(screen.getByText("Zeilen pro Seite:")).toBeInTheDocument();
    expect(screen.getByText("1–10 von 30")).toBeInTheDocument();
    expect(screen.getByLabelText("Erste Seite")).toBeInTheDocument();
    expect(screen.getByLabelText("Vorherige Seite")).toBeInTheDocument();
    expect(screen.getByLabelText("Nächste Seite")).toBeInTheDocument();
    expect(screen.getByLabelText("Letzte Seite")).toBeInTheDocument();
  });

  it("laedt standardmaeßig 10 Patienten pro Seite", async () => {
    apiRequest.mockResolvedValue({
      items: Array.from({ length: 10 }, (_, i) => ({
        id: i + 1,
        first_name: `Vorname${i}`,
        last_name: `Nachname${i}`,
        date_of_birth: "1990-01-01",
        insurance_number: null,
      })),
      total: 12,
      limit: 10,
      offset: 0,
    });

    renderOverview();

    await screen.findByRole("cell", { name: "Nachname0" });

    expect(apiRequest).toHaveBeenLastCalledWith(
      "/patients?limit=10&offset=0",
      expect.objectContaining({ token: "stored-token" }),
    );
    expect(screen.getByText("1–10 von 12")).toBeInTheDocument();
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

  describe("Bearbeiten", () => {
    it("zeigt den Bearbeiten-Button für staff und admin", async () => {
      apiRequest.mockResolvedValue({ items: [patient], total: 1, limit: 10, offset: 0 });

      renderOverview(staffUser);

      expect(
        await screen.findByRole("button", { name: "Patient bearbeiten" }),
      ).toBeInTheDocument();
    });

    it("zeigt eine Ladeanzeige, waehrend die vollen Patientendaten nachgeladen werden", async () => {
      apiRequest
        .mockResolvedValueOnce({ items: [patient], total: 1, limit: 10, offset: 0 })
        .mockImplementationOnce(() => new Promise(() => {}));

      renderOverview();

      fireEvent.click(await screen.findByRole("button", { name: "Patient bearbeiten" }));
      const dialog = await screen.findByRole("dialog");

      expect(
        within(dialog).getByRole("progressbar", { name: "Patientendaten werden geladen" }),
      ).toBeInTheDocument();
    });

    it("laedt beim Oeffnen die vollen Patientendaten nach und befuellt das Formular", async () => {
      apiRequest
        .mockResolvedValueOnce({ items: [patient], total: 1, limit: 10, offset: 0 })
        .mockResolvedValueOnce(fullPatient);

      renderOverview();

      fireEvent.click(await screen.findByRole("button", { name: "Patient bearbeiten" }));
      const dialog = await screen.findByRole("dialog");

      expect(
        await within(dialog).findByDisplayValue("max.mustermann@example.test"),
      ).toBeInTheDocument();
      expect(within(dialog).getByDisplayValue("Musterweg 1")).toBeInTheDocument();
      expect(within(dialog).getByDisplayValue("Penicillin-Allergie")).toBeInTheDocument();

      const [loadPath] = apiRequest.mock.calls[1];
      expect(loadPath).toBe("/patients/9");

      // Loest keine Zeilennavigation aus.
      expect(
        screen.queryByText("Patientendetails-Platzhalter"),
      ).not.toBeInTheDocument();
    });

    it("speichert Aenderungen, zeigt eine Erfolgsmeldung und laedt die Liste neu", async () => {
      apiRequest
        .mockResolvedValueOnce({ items: [patient], total: 1, limit: 10, offset: 0 })
        .mockResolvedValueOnce(fullPatient)
        .mockResolvedValueOnce(null)
        .mockResolvedValueOnce({
          items: [{ ...patient, city: "Neustadt" }],
          total: 1,
          limit: 10,
          offset: 0,
        });

      renderOverview();

      fireEvent.click(await screen.findByRole("button", { name: "Patient bearbeiten" }));
      const dialog = await screen.findByRole("dialog");
      await within(dialog).findByDisplayValue("max.mustermann@example.test");

      fireEvent.change(within(dialog).getByLabelText("Ort"), {
        target: { value: "Neustadt" },
      });
      fireEvent.click(
        within(dialog).getByRole("button", { name: "Änderungen speichern" }),
      );

      expect(
        await screen.findByText("Patient wurde erfolgreich aktualisiert."),
      ).toBeInTheDocument();
      await waitFor(() =>
        expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
      );

      const [savePath, saveOptions] = apiRequest.mock.calls[2];
      expect(savePath).toBe("/patients/9");
      expect(saveOptions).toEqual(
        expect.objectContaining({ method: "PATCH", token: "stored-token" }),
      );

      const body = JSON.parse(saveOptions.body);
      expect(body.city).toBe("Neustadt");
      expect(body.first_name).toBe("Max");
      expect(body.notes).toBe("Penicillin-Allergie");
    });

    it("leert ein geloeschtes optionales Feld als null, nicht als leeren String", async () => {
      apiRequest
        .mockResolvedValueOnce({ items: [patient], total: 1, limit: 10, offset: 0 })
        .mockResolvedValueOnce(fullPatient)
        .mockResolvedValueOnce(null)
        .mockResolvedValueOnce({ items: [patient], total: 1, limit: 10, offset: 0 });

      renderOverview();

      fireEvent.click(await screen.findByRole("button", { name: "Patient bearbeiten" }));
      const dialog = await screen.findByRole("dialog");
      await within(dialog).findByDisplayValue("max.mustermann@example.test");

      fireEvent.change(within(dialog).getByLabelText("Telefon"), {
        target: { value: "" },
      });
      fireEvent.click(
        within(dialog).getByRole("button", { name: "Änderungen speichern" }),
      );

      await waitFor(() => expect(apiRequest).toHaveBeenCalledTimes(3));

      const [, saveOptions] = apiRequest.mock.calls[2];
      expect(JSON.parse(saveOptions.body).phone).toBeNull();
    });

    it("zeigt Feldfehler bei 422 direkt am betroffenen Feld und behaelt die Eingaben", async () => {
      apiRequest
        .mockResolvedValueOnce({ items: [patient], total: 1, limit: 10, offset: 0 })
        .mockResolvedValueOnce(fullPatient)
        .mockRejectedValueOnce(
          new ApiError("Pflichtfeld fehlt: last_name", 422, [
            { field: "last_name", message: "darf nicht auf null gesetzt werden" },
          ]),
        );

      renderOverview();

      fireEvent.click(await screen.findByRole("button", { name: "Patient bearbeiten" }));
      const dialog = await screen.findByRole("dialog");
      await within(dialog).findByDisplayValue("max.mustermann@example.test");

      fireEvent.click(
        within(dialog).getByRole("button", { name: "Änderungen speichern" }),
      );

      expect(
        await within(dialog).findByText("darf nicht auf null gesetzt werden"),
      ).toBeInTheDocument();
      expect(
        within(dialog).getByText("Pflichtfeld fehlt: last_name"),
      ).toBeInTheDocument();
      // Dialog bleibt offen, Eingaben bleiben erhalten.
      expect(screen.getByRole("dialog")).toBeInTheDocument();
      expect(within(dialog).getByDisplayValue("Mustermann")).toBeInTheDocument();
    });

    it("verwirft Aenderungen beim Abbrechen, ohne zu speichern", async () => {
      apiRequest
        .mockResolvedValueOnce({ items: [patient], total: 1, limit: 10, offset: 0 })
        .mockResolvedValueOnce(fullPatient);

      renderOverview();

      fireEvent.click(await screen.findByRole("button", { name: "Patient bearbeiten" }));
      const dialog = await screen.findByRole("dialog");
      await within(dialog).findByDisplayValue("max.mustermann@example.test");

      fireEvent.click(within(dialog).getByRole("button", { name: "Abbrechen" }));

      await waitFor(() =>
        expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
      );
      // Nur Liste + Nachladen der vollen Daten — kein PATCH.
      expect(apiRequest).toHaveBeenCalledTimes(2);
    });

    describe("Speichern-Button und Pflichtfelder", () => {
      async function openFullyPopulatedDialog() {
        apiRequest
          .mockResolvedValueOnce({ items: [patient], total: 1, limit: 10, offset: 0 })
          .mockResolvedValueOnce(fullPatient);

        renderOverview();

        fireEvent.click(await screen.findByRole("button", { name: "Patient bearbeiten" }));
        const dialog = await screen.findByRole("dialog");
        await within(dialog).findByDisplayValue("max.mustermann@example.test");

        return dialog;
      }

      it("ist nach dem Laden gueltig befuellt und der Speichern-Button aktiv", async () => {
        const dialog = await openFullyPopulatedDialog();

        expect(
          within(dialog).getByRole("button", { name: "Änderungen speichern" }),
        ).toBeEnabled();
      });

      it.each([
        ["Vorname", "first_name"],
        ["Nachname", "last_name"],
        ["Geburtsdatum", "date_of_birth"],
      ])("deaktiviert Speichern, wenn %s geleert wird, und aktiviert ihn beim Wiederherstellen", async (label, field) => {
        const dialog = await openFullyPopulatedDialog();
        const originalValue = fullPatient[field];
        const input = within(dialog).getByLabelText(new RegExp(`^${label}`));
        const saveButton = within(dialog).getByRole("button", {
          name: "Änderungen speichern",
        });

        fireEvent.change(input, { target: { value: "" } });
        expect(saveButton).toBeDisabled();

        fireEvent.change(input, { target: { value: originalValue } });
        expect(saveButton).toBeEnabled();
      });

      it("deaktiviert Speichern bei einem Vornamen aus nur Leerzeichen", async () => {
        const dialog = await openFullyPopulatedDialog();
        const input = within(dialog).getByLabelText(/^Vorname/);

        fireEvent.change(input, { target: { value: "   " } });
        fireEvent.blur(input);

        expect(
          within(dialog).getByRole("button", { name: "Änderungen speichern" }),
        ).toBeDisabled();
        expect(within(dialog).getByText("darf nicht leer sein")).toBeInTheDocument();
      });

      it("laesst Speichern aktiv, wenn nur ein optionales Feld geleert wird", async () => {
        const dialog = await openFullyPopulatedDialog();

        fireEvent.change(within(dialog).getByLabelText("Telefon"), {
          target: { value: "" },
        });
        fireEvent.change(within(dialog).getByLabelText("Notizen"), {
          target: { value: "" },
        });

        expect(
          within(dialog).getByRole("button", { name: "Änderungen speichern" }),
        ).toBeEnabled();
      });

      it("deaktiviert Speichern fuer ein Geburtsdatum in der Zukunft", async () => {
        const dialog = await openFullyPopulatedDialog();
        const nextYear = String(new Date().getFullYear() + 1);
        const input = within(dialog).getByLabelText(/^Geburtsdatum/);

        fireEvent.change(input, { target: { value: `${nextYear}-01-01` } });
        fireEvent.blur(input);

        expect(
          within(dialog).getByRole("button", { name: "Änderungen speichern" }),
        ).toBeDisabled();
        expect(
          within(dialog).getByText("darf nicht in der Zukunft liegen"),
        ).toBeInTheDocument();
      });
    });
  });

  describe("Anlegen", () => {
    it("zeigt den Neuer-Patient-Button für staff und admin", async () => {
      apiRequest.mockResolvedValue({ items: [patient], total: 1, limit: 10, offset: 0 });

      renderOverview(staffUser);

      expect(
        await screen.findByRole("button", { name: "Neuer Patient" }),
      ).toBeInTheDocument();
    });

    it("öffnet ein leeres Formular ohne Ladezustand", async () => {
      apiRequest.mockResolvedValue({ items: [patient], total: 1, limit: 10, offset: 0 });

      renderOverview();

      fireEvent.click(await screen.findByRole("button", { name: "Neuer Patient" }));
      const dialog = await screen.findByRole("dialog");

      expect(
        within(dialog).getByRole("heading", { name: "Patient anlegen" }),
      ).toBeInTheDocument();
      expect(within(dialog).getByLabelText(/^Vorname/)).toHaveValue("");
      expect(
        within(dialog).queryByRole("progressbar", { name: "Patientendaten werden geladen" }),
      ).not.toBeInTheDocument();
    });

    it("zeigt beim Öffnen keine Pflichtfeld-Fehlermeldungen", async () => {
      apiRequest.mockResolvedValue({ items: [patient], total: 1, limit: 10, offset: 0 });

      renderOverview();

      fireEvent.click(await screen.findByRole("button", { name: "Neuer Patient" }));
      const dialog = await screen.findByRole("dialog");

      expect(within(dialog).queryByText("darf nicht leer sein")).not.toBeInTheDocument();
      expect(within(dialog).queryByText("Feld ist erforderlich")).not.toBeInTheDocument();
      expect(
        within(dialog).getByRole("button", { name: "Patient anlegen" }),
      ).toBeDisabled();
    });

    it("zeigt die Fehlermeldung eines Pflichtfelds erst nach dem Verlassen", async () => {
      apiRequest.mockResolvedValue({ items: [patient], total: 1, limit: 10, offset: 0 });

      renderOverview();

      fireEvent.click(await screen.findByRole("button", { name: "Neuer Patient" }));
      const dialog = await screen.findByRole("dialog");
      const input = within(dialog).getByLabelText(/^Nachname/);

      expect(within(dialog).queryByText("darf nicht leer sein")).not.toBeInTheDocument();

      fireEvent.blur(input);

      expect(within(dialog).getByText("darf nicht leer sein")).toBeInTheDocument();

      fireEvent.change(input, { target: { value: "Musterfrau" } });

      expect(within(dialog).queryByText("darf nicht leer sein")).not.toBeInTheDocument();
    });

    it("prueft Pflichtfelder vor dem Absenden", async () => {
      apiRequest.mockResolvedValue({ items: [patient], total: 1, limit: 10, offset: 0 });

      renderOverview();

      fireEvent.click(await screen.findByRole("button", { name: "Neuer Patient" }));
      const dialog = await screen.findByRole("dialog");

      expect(
        within(dialog).getByRole("button", { name: "Patient anlegen" }),
      ).toBeDisabled();

      fireEvent.change(within(dialog).getByLabelText(/^Vorname/), {
        target: { value: "Erika" },
      });
      fireEvent.change(within(dialog).getByLabelText(/^Nachname/), {
        target: { value: "Musterfrau" },
      });
      fireEvent.change(within(dialog).getByLabelText(/^Geburtsdatum/), {
        target: { value: "1992-04-01" },
      });

      expect(
        within(dialog).getByRole("button", { name: "Patient anlegen" }),
      ).toBeEnabled();
    });

    it("legt einen Patienten an, zeigt eine Erfolgsmeldung und laedt die Liste neu", async () => {
      apiRequest
        .mockResolvedValueOnce({ items: [patient], total: 1, limit: 10, offset: 0 })
        .mockResolvedValueOnce({ ...fullPatient, id: 10, first_name: "Erika" })
        .mockResolvedValueOnce({
          items: [patient, { ...patient, id: 10, first_name: "Erika" }],
          total: 2,
          limit: 10,
          offset: 0,
        });

      renderOverview();

      fireEvent.click(await screen.findByRole("button", { name: "Neuer Patient" }));
      const dialog = await screen.findByRole("dialog");

      fireEvent.change(within(dialog).getByLabelText(/^Vorname/), {
        target: { value: "Erika" },
      });
      fireEvent.change(within(dialog).getByLabelText(/^Nachname/), {
        target: { value: "Musterfrau" },
      });
      fireEvent.change(within(dialog).getByLabelText(/^Geburtsdatum/), {
        target: { value: "1992-04-01" },
      });
      fireEvent.click(within(dialog).getByRole("button", { name: "Patient anlegen" }));

      expect(
        await screen.findByText("Patient wurde erfolgreich angelegt."),
      ).toBeInTheDocument();
      await waitFor(() =>
        expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
      );

      const [savePath, saveOptions] = apiRequest.mock.calls[1];
      expect(savePath).toBe("/patients");
      expect(saveOptions).toEqual(
        expect.objectContaining({ method: "POST", token: "stored-token" }),
      );

      const body = JSON.parse(saveOptions.body);
      expect(body.first_name).toBe("Erika");
      expect(body.last_name).toBe("Musterfrau");
      expect(body.date_of_birth).toBe("1992-04-01");
      expect(body.phone).toBeNull();
    });

    it("zeigt Feldfehler des Backends bei 422 und behaelt die Eingaben", async () => {
      apiRequest
        .mockResolvedValueOnce({ items: [patient], total: 1, limit: 10, offset: 0 })
        .mockRejectedValueOnce(
          new ApiError(
            "Die Versichertennummer A123456789 ist bereits einem anderen Patienten zugeordnet",
            409,
          ),
        );

      renderOverview();

      fireEvent.click(await screen.findByRole("button", { name: "Neuer Patient" }));
      const dialog = await screen.findByRole("dialog");

      fireEvent.change(within(dialog).getByLabelText(/^Vorname/), {
        target: { value: "Erika" },
      });
      fireEvent.change(within(dialog).getByLabelText(/^Nachname/), {
        target: { value: "Musterfrau" },
      });
      fireEvent.change(within(dialog).getByLabelText(/^Geburtsdatum/), {
        target: { value: "1992-04-01" },
      });
      fireEvent.click(within(dialog).getByRole("button", { name: "Patient anlegen" }));

      expect(
        await within(dialog).findByText(
          "Die Versichertennummer A123456789 ist bereits einem anderen Patienten zugeordnet",
        ),
      ).toBeInTheDocument();
      // Dialog bleibt offen, Eingaben bleiben erhalten.
      expect(screen.getByRole("dialog")).toBeInTheDocument();
      expect(within(dialog).getByDisplayValue("Erika")).toBeInTheDocument();
    });

    it("verwirft Eingaben beim Abbrechen, ohne einen Request zu senden", async () => {
      apiRequest.mockResolvedValue({ items: [patient], total: 1, limit: 10, offset: 0 });

      renderOverview();

      fireEvent.click(await screen.findByRole("button", { name: "Neuer Patient" }));
      const dialog = await screen.findByRole("dialog");

      fireEvent.change(within(dialog).getByLabelText(/^Vorname/), {
        target: { value: "Erika" },
      });
      fireEvent.click(within(dialog).getByRole("button", { name: "Abbrechen" }));

      await waitFor(() =>
        expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
      );
      // Nur der anfaengliche Ladeaufruf — kein POST.
      expect(apiRequest).toHaveBeenCalledTimes(1);
    });
  });

  describe("Suche", () => {
    afterEach(() => {
      vi.useRealTimers();
    });

    it("zeigt das Suchfeld über der Tabelle", async () => {
      apiRequest.mockResolvedValue({ items: [patient], total: 1, limit: 25, offset: 0 });

      renderOverview();

      const searchField = await screen.findByLabelText("Suche nach Name oder Vorname");
      const table = await screen.findByRole("table");

      expect(
        searchField.compareDocumentPosition(table) & Node.DOCUMENT_POSITION_FOLLOWING,
      ).toBeTruthy();
    });

    it("löst beim Tippen nicht bei jedem Tastendruck eine Anfrage aus", async () => {
      apiRequest.mockResolvedValue({ items: [patient], total: 1, limit: 25, offset: 0 });

      renderOverview();
      const searchField = await screen.findByLabelText("Suche nach Name oder Vorname");
      apiRequest.mockClear();

      vi.useFakeTimers();
      fireEvent.change(searchField, { target: { value: "h" } });
      fireEvent.change(searchField, { target: { value: "ha" } });
      fireEvent.change(searchField, { target: { value: "har" } });

      expect(apiRequest).not.toHaveBeenCalled();

      await act(async () => {
        await vi.advanceTimersByTimeAsync(300);
      });

      expect(apiRequest).toHaveBeenCalledTimes(1);
    });

    it("sendet die entprellte Suche als q-Parameter, Seitengröße und Offset bleiben erhalten", async () => {
      apiRequest.mockResolvedValue({ items: [patient], total: 1, limit: 25, offset: 0 });

      renderOverview();
      const searchField = await screen.findByLabelText("Suche nach Name oder Vorname");
      apiRequest.mockClear();

      vi.useFakeTimers();
      fireEvent.change(searchField, { target: { value: "hartmann" } });
      await act(async () => {
        await vi.advanceTimersByTimeAsync(300);
      });

      expect(apiRequest).toHaveBeenLastCalledWith(
        "/patients?q=hartmann&limit=10&offset=0",
        expect.objectContaining({ token: "stored-token" }),
      );
    });

    it("setzt die Seite auf 0 zurück, wenn sich die Suche ändert", async () => {
      apiRequest.mockResolvedValue({
        items: Array.from({ length: 10 }, (_, i) => ({
          id: i + 1,
          first_name: `Vorname${i}`,
          last_name: `Nachname${i}`,
          date_of_birth: "1990-01-01",
          insurance_number: null,
        })),
        total: 30,
        limit: 10,
        offset: 0,
      });

      renderOverview();
      await screen.findByRole("cell", { name: "Nachname0" });

      fireEvent.click(screen.getByLabelText("Nächste Seite"));
      await waitFor(() => {
        expect(apiRequest).toHaveBeenLastCalledWith(
          "/patients?limit=10&offset=10",
          expect.objectContaining({ token: "stored-token" }),
        );
      });

      vi.useFakeTimers();
      const searchField = screen.getByLabelText("Suche nach Name oder Vorname");
      fireEvent.change(searchField, { target: { value: "hartmann" } });
      await act(async () => {
        await vi.advanceTimersByTimeAsync(300);
      });

      expect(apiRequest).toHaveBeenLastCalledWith(
        "/patients?q=hartmann&limit=10&offset=0",
        expect.objectContaining({ token: "stored-token" }),
      );
    });

    it("zeigt eine eigene Meldung, wenn die Suche nichts findet", async () => {
      apiRequest
        .mockResolvedValueOnce({ items: [patient], total: 1, limit: 25, offset: 0 })
        .mockResolvedValueOnce({ items: [], total: 0, limit: 25, offset: 0 });

      renderOverview();
      const searchField = await screen.findByLabelText("Suche nach Name oder Vorname");

      vi.useFakeTimers();
      fireEvent.change(searchField, { target: { value: "nichtvorhanden" } });
      await act(async () => {
        await vi.advanceTimersByTimeAsync(300);
      });

      expect(screen.getByText("Keine Treffer")).toBeInTheDocument();
      expect(
        screen.getByText('Für „nichtvorhanden" wurden keine Patienten gefunden.'),
      ).toBeInTheDocument();
      expect(screen.queryByText("Keine Patienten vorhanden")).not.toBeInTheDocument();
    });

    it("zeigt bei leerer Datenbank ohne aktive Suche weiterhin die allgemeine Leermeldung", async () => {
      apiRequest.mockResolvedValue({ items: [], total: 0, limit: 25, offset: 0 });

      renderOverview();

      expect(await screen.findByText("Keine Patienten vorhanden")).toBeInTheDocument();
      expect(screen.queryByText("Keine Treffer")).not.toBeInTheDocument();
    });

    it("zeigt nach dem Leeren der Suche wieder die vollständige Liste", async () => {
      apiRequest
        .mockResolvedValueOnce({ items: [patient], total: 1, limit: 25, offset: 0 })
        .mockResolvedValueOnce({ items: [], total: 0, limit: 25, offset: 0 })
        .mockResolvedValueOnce({ items: [patient], total: 1, limit: 25, offset: 0 });

      renderOverview();
      const searchField = await screen.findByLabelText("Suche nach Name oder Vorname");

      vi.useFakeTimers();
      fireEvent.change(searchField, { target: { value: "nichtvorhanden" } });
      await act(async () => {
        await vi.advanceTimersByTimeAsync(300);
      });
      expect(screen.getByText("Keine Treffer")).toBeInTheDocument();

      fireEvent.change(searchField, { target: { value: "" } });
      await act(async () => {
        await vi.advanceTimersByTimeAsync(300);
      });

      expect(apiRequest).toHaveBeenLastCalledWith(
        "/patients?limit=10&offset=0",
        expect.objectContaining({ token: "stored-token" }),
      );
      expect(screen.getByRole("cell", { name: "Mustermann" })).toBeInTheDocument();
    });
  });
});
