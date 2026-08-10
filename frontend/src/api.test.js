import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  apiRequest,
  FORBIDDEN_ERROR,
  getCurrentUser,
  jsonBody,
  login,
  patientsPath,
  userPath,
  usersPath,
} from "./api.js";

afterEach(() => {
  vi.unstubAllGlobals();
});

/** Stellt `fetch` auf eine feste Antwort und gibt den Spion zurück. */
function stubFetch(body, init = {}) {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(body === null ? null : JSON.stringify(body), {
      status: 200,
      headers: { "Content-Type": "application/json" },
      ...init,
    }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("login", () => {
  it("sendet E-Mail und Passwort formular-kodiert an das Backend", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          access_token: "test-token",
          token_type: "bearer",
          user: { id: 1 },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await login("anna.admin@medidoc.test", "geheim123");

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8000/auth/login");
    expect(options.method).toBe("POST");
    expect(options.headers).toEqual({
      "Content-Type": "application/x-www-form-urlencoded",
    });
    expect(options.body.toString()).toBe(
      "username=anna.admin%40medidoc.test&password=geheim123",
    );
  });
});

describe("patientsPath", () => {
  it("zeigt ohne Parameter auf die Patientenübersicht", () => {
    expect(patientsPath()).toBe("/patients");
  });

  it("hängt Seitengröße und Offset als Query an", () => {
    expect(patientsPath({ limit: 25, offset: 50 })).toBe(
      "/patients?limit=25&offset=50",
    );
  });

  it("hängt eine nicht-leere Suche als q an", () => {
    expect(patientsPath({ q: "hartmann", limit: 25, offset: 0 })).toBe(
      "/patients?q=hartmann&limit=25&offset=0",
    );
  });

  it("lässt q bei leerer Suche weg", () => {
    expect(patientsPath({ q: "", limit: 25, offset: 0 })).toBe(
      "/patients?limit=25&offset=0",
    );
  });
});

describe("usersPath", () => {
  it("zeigt ohne Parameter auf die Benutzerliste", () => {
    expect(usersPath()).toBe("/users");
  });

  it("hängt Seitengröße und Offset als Query an", () => {
    expect(usersPath({ limit: 25, offset: 25 })).toBe("/users?limit=25&offset=25");
  });

  it("zeigt auf einen einzelnen Benutzer", () => {
    expect(userPath(7)).toBe("/users/7");
  });
});

describe("jsonBody", () => {
  it("setzt Methode, Content-Type und den Rumpf als JSON", () => {
    expect(jsonBody("PATCH", { is_active: false })).toEqual({
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: '{"is_active":false}',
    });
  });
});

describe("Fehlermeldungen", () => {
  it("übernimmt `message` aus der Antwort", async () => {
    stubFetch({ status: 401, message: "E-Mail oder Passwort ist falsch" }, { status: 401 });

    await expect(login("a@b.test", "falsch")).rejects.toMatchObject({
      name: "ApiError",
      message: "E-Mail oder Passwort ist falsch",
      status: 401,
    });
  });

  it("bevorzugt `message` gegenüber `detail`, wenn beide vorhanden sind", async () => {
    stubFetch(
      { detail: "veraltete Meldung", message: "aktuelle Meldung" },
      { status: 400 },
    );

    await expect(login("a@b.test", "falsch")).rejects.toMatchObject({
      message: "aktuelle Meldung",
      status: 400,
    });
  });

  it("fällt auf `detail` zurück, wenn `message` fehlt", async () => {
    stubFetch({ detail: "E-Mail oder Passwort ist falsch" }, { status: 401 });

    await expect(login("a@b.test", "falsch")).rejects.toMatchObject({
      name: "ApiError",
      message: "E-Mail oder Passwort ist falsch",
      status: 401,
    });
  });

  it("zeigt bei einem FastAPI-Validierungsfehler keinen Objekt-Müll", async () => {
    // FastAPI antwortet hier mit einer *Liste* unter demselben Schlüssel.
    // Ungeprüft übernommen stünde "[object Object]" in der Oberfläche.
    stubFetch(
      { detail: [{ loc: ["body", "username"], msg: "field required" }] },
      { status: 422 },
    );

    await expect(login("", "")).rejects.toMatchObject({
      message: "Die Anfrage ist fehlgeschlagen.",
      status: 422,
    });
  });

  it("nennt bei 403 die fehlende Berechtigung", async () => {
    stubFetch({ detail: "Dazu fehlt dir die Berechtigung" }, { status: 403 });

    await expect(
      apiRequest("/patients/1", { method: "DELETE" }),
    ).rejects.toMatchObject({
      message: "Dazu fehlt dir die Berechtigung",
      status: 403,
    });
  });

  it("nennt sie auch ohne Meldung in der Antwort", async () => {
    // Weder `message` noch `detail`: Dann darf beim Benutzer nicht "Die Anfrage
    // ist fehlgeschlagen." stehen. Der Fall ist immer derselbe — angemeldet,
    // aber die Rolle reicht nicht.
    stubFetch({ status: 403 }, { status: 403 });

    await expect(
      apiRequest("/patients/1", { method: "DELETE" }),
    ).rejects.toMatchObject({
      message: FORBIDDEN_ERROR,
      status: 403,
    });
  });

  it("meldet ein nicht erreichbares Backend als Status 0", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("failed")));

    await expect(login("a@b.test", "geheim")).rejects.toMatchObject({
      name: "ApiError",
      status: 0,
    });
  });

  it("reicht einen abgebrochenen Request unverändert durch", async () => {
    const abort = new DOMException("aborted", "AbortError");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(abort));

    // Kein ApiError: Der Abbruch war Absicht des Aufrufers, kein Netzwerkfehler.
    await expect(apiRequest("/auth/me")).rejects.toBe(abort);
  });
});

describe("Bearer-Token", () => {
  it("hängt den Token als Authorization-Header an", async () => {
    const fetchMock = stubFetch({ id: 1 });

    await getCurrentUser("test-token");

    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8000/auth/me");
    expect(options.headers.Authorization).toBe("Bearer test-token");
  });

  it("schickt ohne Token keinen Authorization-Header", async () => {
    const fetchMock = stubFetch({ ok: true });

    await apiRequest("/health");

    expect(fetchMock.mock.calls[0][1].headers).not.toHaveProperty("Authorization");
  });

  it("ist ein ApiError, wenn das Backend den Token ablehnt", async () => {
    stubFetch({ detail: "Anmeldung erforderlich" }, { status: 401 });

    const error = await getCurrentUser("abgelaufen").catch((caught) => caught);

    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(401);
  });
});
