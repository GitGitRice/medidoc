import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiRequest, getCurrentUser, login, patientsPath } from "./api.js";

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
  it("zeigt auf die Patientenübersicht", () => {
    expect(patientsPath()).toBe("/patienten");
  });
});

describe("Fehlermeldungen", () => {
  it("übernimmt die Meldung des Backends", async () => {
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
