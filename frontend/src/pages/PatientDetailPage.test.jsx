import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useNavigate } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiRequest, getCurrentUser } from "../api.js";
import { AuthProvider } from "../auth/AuthContext.jsx";
import { PatientDetailPage } from "./PatientDetailPage.jsx";

// Nur die Netzwerkfunktionen ersetzen — wie in Overview.test.jsx. `ApiError`
// bleibt die echte Klasse, sonst geht das `instanceof` in `AuthContext` ins
// Leere und die Seite sähe keinen Status am Fehler.
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

const patient = {
  id: 7,
  first_name: "Max",
  last_name: "Mustermann",
  date_of_birth: "1978-03-14",
  email: "max.mustermann@example.test",
  phone: "030 1234567",
  street: "Hauptstraße 12",
  postal_code: "10115",
  city: "Berlin",
  insurance_provider: "AOK Nordost",
  insurance_number: "A123456789",
  insurance_type: "statutory",
  notes: null,
  created_at: "2026-08-04T09:12:09.141101Z",
  updated_at: "2026-08-04T09:12:09.141108Z",
};

const documentWithAttachment = {
  id: "5eed0000000000000000000000000001",
  patient_id: 7,
  document_type: "befund",
  title: "MRT linkes Knie",
  description: "Anhaltende Schmerzen nach Sturz beim Sport.",
  tags: ["mrt", "radiologie"],
  source: "Radiologie Mitte",
  fields: { koerperregion: "Knie links" },
  attachment: {
    filename: "mrt_knie_links.pdf",
    content_type: "application/pdf",
    size_bytes: 284913,
  },
  created_at: "2026-03-12T09:20:00Z",
};

const documentWithoutAttachment = {
  id: "5eed0000000000000000000000000002",
  patient_id: 7,
  document_type: "laborwert",
  title: "Großes Blutbild",
  description: "Routinekontrolle.",
  tags: ["labor"],
  source: "Labor Berlin Mitte",
  fields: {},
  attachment: null,
  created_at: "2026-04-02T07:45:00Z",
};

/**
 * Beantwortet die beiden Requests der Seite getrennt.
 *
 * Die Stammdaten und die Dokumente kommen aus zwei Endpunkten; ein Mock, der
 * auf beides dasselbe antwortet, würde jeden Verwechsler durchgehen lassen.
 */
function mockApi({ patientResponse, documentsResponse }) {
  apiRequest.mockImplementation((path) => {
    if (path.startsWith("/patients/")) {
      return typeof patientResponse === "function"
        ? patientResponse(path)
        : Promise.resolve(patientResponse);
    }
    if (path.startsWith("/docs/")) {
      return typeof documentsResponse === "function"
        ? documentsResponse(path)
        : Promise.resolve(documentsResponse);
    }
    return Promise.reject(new Error(`Unerwarteter Pfad: ${path}`));
  });
}

function page(items = []) {
  return { items, total: items.length, limit: 100, offset: 0 };
}

function NextPatientButton() {
  const navigate = useNavigate();
  return (
    <button onClick={() => navigate("/patients/8")}>Nächster Patient</button>
  );
}

function renderDetailPage(patientId = 7) {
  window.localStorage.setItem("medidoc.accessToken", "stored-token");
  getCurrentUser.mockResolvedValue(adminUser);

  return render(
    <MemoryRouter initialEntries={[`/patients/${patientId}`]}>
      <AuthProvider>
        <NextPatientButton />
        <Routes>
          <Route path="/patients/:patientId" element={<PatientDetailPage />} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("PatientDetailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("zeigt einen Ladehinweis, solange die Akte geholt wird", async () => {
    apiRequest.mockImplementation(() => new Promise(() => {}));

    renderDetailPage();

    expect(
      await screen.findByRole("progressbar", {
        name: "Patientenakte wird geladen",
      }),
    ).toBeInTheDocument();
  });

  it("holt Stammdaten und Dokumente mit dem Token aus dem AuthContext", async () => {
    mockApi({
      patientResponse: patient,
      documentsResponse: page([documentWithAttachment]),
    });

    renderDetailPage();

    await screen.findByText("Max Mustermann");

    expect(apiRequest).toHaveBeenCalledWith(
      "/patients/7",
      expect.objectContaining({ token: "stored-token" }),
    );
    expect(apiRequest).toHaveBeenCalledWith(
      "/docs/7",
      expect.objectContaining({ token: "stored-token" }),
    );
  });

  it("zeigt die Stammdaten aus der API", async () => {
    mockApi({ patientResponse: patient, documentsResponse: page() });

    renderDetailPage();

    expect(await screen.findByText("Max Mustermann")).toBeInTheDocument();
    expect(screen.getByText("A123456789")).toBeInTheDocument();
    expect(screen.getByText("AOK Nordost")).toBeInTheDocument();
    expect(screen.getByText("Gesetzlich versichert")).toBeInTheDocument();
  });

  it("zeigt die Dokumente aus der API", async () => {
    mockApi({
      patientResponse: patient,
      documentsResponse: page([documentWithAttachment, documentWithoutAttachment]),
    });

    renderDetailPage();

    expect(await screen.findByText("MRT linkes Knie")).toBeInTheDocument();
    expect(screen.getByText("Großes Blutbild")).toBeInTheDocument();
  });

  it("sagt bei einem unbekannten Patienten, dass es ihn nicht gibt", async () => {
    const notFound = new ApiError(
      "Patient mit der ID 7 wurde nicht gefunden",
      404,
    );
    mockApi({
      patientResponse: () => Promise.reject(notFound),
      documentsResponse: () => Promise.reject(notFound),
    });

    renderDetailPage();

    expect(await screen.findByText("Patient nicht gefunden")).toBeInTheDocument();
    // Der Satz kommt aus der Antwort, nicht aus der Seite.
    expect(
      screen.getByText("Patient mit der ID 7 wurde nicht gefunden"),
    ).toBeInTheDocument();
    // Und ausdruecklich nicht die Auskunft, das Backend sei weg.
    expect(
      screen.queryByText("Das Backend ist nicht erreichbar."),
    ).not.toBeInTheDocument();
  });

  it("zeigt die Meldung des Backends, wenn es nicht antwortet", async () => {
    const unreachable = new ApiError("Das Backend ist nicht erreichbar.", 0);
    mockApi({
      patientResponse: () => Promise.reject(unreachable),
      documentsResponse: () => Promise.reject(unreachable),
    });

    renderDetailPage();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Das Backend ist nicht erreichbar.",
    );
    expect(screen.queryByText("Patient nicht gefunden")).not.toBeInTheDocument();
  });

  it("zeigt eine Akte ohne Dokumente als Leerzustand, nicht als Fehler", async () => {
    mockApi({ patientResponse: patient, documentsResponse: page() });

    renderDetailPage();

    expect(
      await screen.findByText("Keine Dokumente in dieser Akte"),
    ).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    // Die Stammdaten stehen trotzdem da.
    expect(screen.getByText("Max Mustermann")).toBeInTheDocument();
  });

  it("stellt ein Dokument ohne Anhang sauber dar", async () => {
    mockApi({
      patientResponse: patient,
      documentsResponse: page([documentWithoutAttachment]),
    });

    renderDetailPage();

    expect(await screen.findByText("Kein Anhang")).toBeInTheDocument();
    // Kein Knopf, hinter dem nichts liegt.
    expect(
      screen.queryByRole("button", { name: "Anhang laden" }),
    ).not.toBeInTheDocument();
  });

  it("nennt bei einem Dokument mit Anhang dessen Namen", async () => {
    mockApi({
      patientResponse: patient,
      documentsResponse: page([documentWithAttachment]),
    });

    renderDetailPage();

    expect(await screen.findByText(/mrt_knie_links\.pdf/)).toBeInTheDocument();
    expect(screen.queryByText("Kein Anhang")).not.toBeInTheDocument();
  });

  it("laedt beim Wechsel auf den naechsten Patienten nach", async () => {
    mockApi({ patientResponse: patient, documentsResponse: page() });

    renderDetailPage(7);
    await screen.findByText("Max Mustermann");

    fireEvent.click(screen.getByRole("button", { name: "Nächster Patient" }));

    await waitFor(() => {
      expect(apiRequest).toHaveBeenCalledWith(
        "/patients/8",
        expect.objectContaining({ token: "stored-token" }),
      );
    });
    expect(apiRequest).toHaveBeenCalledWith(
      "/docs/8",
      expect.objectContaining({ token: "stored-token" }),
    );
  });

  it("bricht die Requests ab, wenn die Seite verlassen wird", async () => {
    mockApi({ patientResponse: patient, documentsResponse: page() });

    const { unmount } = renderDetailPage();
    await screen.findByText("Max Mustermann");

    const signals = apiRequest.mock.calls
      .map(([, options]) => options?.signal)
      .filter(Boolean);
    expect(signals.length).toBeGreaterThan(0);

    unmount();

    expect(signals.every((signal) => signal.aborted)).toBe(true);
  });

  it("filtert die Dokumente nach Titel, Tags und Dokumenttyp", async () => {
    mockApi({
      patientResponse: patient,
      documentsResponse: page([documentWithAttachment, documentWithoutAttachment]),
    });

    renderDetailPage();
    const search = await screen.findByLabelText(
      "Suche in Titel, Tags und Dokumenttyp",
    );

    fireEvent.change(search, { target: { value: "radiologie" } });

    expect(screen.getByText("MRT linkes Knie")).toBeInTheDocument();
    expect(screen.queryByText("Großes Blutbild")).not.toBeInTheDocument();

    fireEvent.change(search, { target: { value: "laborwert" } });

    expect(screen.getByText("Großes Blutbild")).toBeInTheDocument();
    expect(screen.queryByText("MRT linkes Knie")).not.toBeInTheDocument();
  });
});
