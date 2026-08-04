import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiRequest, getCurrentUser } from "../api.js";
import { AuthProvider, useAuth } from "./AuthContext.jsx";

// Nur die Netzwerkfunktionen ersetzen — `ApiError` bleibt die echte Klasse,
// sonst greift das `instanceof` in `apiFetch` nicht.
vi.mock("../api.js", async () => ({
  ...(await vi.importActual("../api.js")),
  getCurrentUser: vi.fn(),
  login: vi.fn(),
  apiRequest: vi.fn(),
}));

const TOKEN_KEY = "medidoc.accessToken";

const user = {
  id: 1,
  email: "anna.admin@medidoc.test",
  name: "Anna Admin",
  role: "admin",
};

/** Eine wiederhergestellte Sitzung — der Ausgangspunkt aller Tests hier. */
async function renderAngemeldet() {
  window.localStorage.setItem(TOKEN_KEY, "stored-token");
  getCurrentUser.mockResolvedValue(user);

  const rendered = renderHook(() => useAuth(), { wrapper: AuthProvider });
  await waitFor(() => expect(rendered.result.current.user).toEqual(user));

  return rendered;
}

describe("apiFetch", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("schickt den Token mit", async () => {
    const { result } = await renderAngemeldet();
    apiRequest.mockResolvedValue({ items: [] });

    await act(async () => {
      await result.current.apiFetch("/patients");
    });

    expect(apiRequest).toHaveBeenCalledWith("/patients", { token: "stored-token" });
  });

  it("meldet bei 401 ab und verwirft den gespeicherten Token", async () => {
    const { result } = await renderAngemeldet();
    apiRequest.mockRejectedValue(new ApiError("Anmeldung erforderlich", 401));

    await act(async () => {
      await expect(result.current.apiFetch("/patients")).rejects.toBeInstanceOf(
        ApiError,
      );
    });

    expect(result.current.user).toBeNull();
    expect(result.current.token).toBeNull();
    expect(window.localStorage.getItem(TOKEN_KEY)).toBeNull();
  });

  it("meldet bei 403 nicht ab", async () => {
    // Da fehlt eine Rolle, nicht die Anmeldung — docs/auth-api.md.
    const { result } = await renderAngemeldet();
    apiRequest.mockRejectedValue(new ApiError("Dazu fehlt dir die Berechtigung", 403));

    await act(async () => {
      await expect(result.current.apiFetch("/patients/1")).rejects.toMatchObject({
        status: 403,
      });
    });

    expect(result.current.user).toEqual(user);
    expect(window.localStorage.getItem(TOKEN_KEY)).toBe("stored-token");
  });
});

describe("Sitzung beim Laden", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("verwirft einen Token, den das Backend nicht mehr akzeptiert", async () => {
    window.localStorage.setItem(TOKEN_KEY, "abgelaufen");
    getCurrentUser.mockRejectedValue(new ApiError("Anmeldung erforderlich", 401));

    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.user).toBeNull();
    expect(window.localStorage.getItem(TOKEN_KEY)).toBeNull();
  });

  it("fragt ohne gespeicherten Token gar nicht erst nach", async () => {
    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(getCurrentUser).not.toHaveBeenCalled();
  });

  // Ein Token ist erst widerlegt, wenn das Backend ihn mit 401 ablehnt. Alles
  // andere ist eine Störung und darf die Sitzung nicht kosten — docs/auth-api.md.
  it.each([
    ["ein nicht erreichbares Backend", new ApiError("Das Backend ist nicht erreichbar.", 0)],
    ["einen Serverfehler", new ApiError("Die Anfrage ist fehlgeschlagen.", 500)],
    ["eine kaputte Antwort", new TypeError("body is not valid JSON")],
  ])("behält den Token bei %s", async (_beschreibung, fehler) => {
    window.localStorage.setItem(TOKEN_KEY, "stored-token");
    getCurrentUser.mockRejectedValue(fehler);

    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(window.localStorage.getItem(TOKEN_KEY)).toBe("stored-token");
    expect(result.current.token).toBe("stored-token");
    expect(result.current.sessionError).toBe(fehler);
    expect(result.current.user).toBeNull();
  });

  it("stellt die Sitzung beim zweiten Anlauf her", async () => {
    window.localStorage.setItem(TOKEN_KEY, "stored-token");
    getCurrentUser.mockRejectedValue(
      new ApiError("Das Backend ist nicht erreichbar.", 0),
    );

    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });
    await waitFor(() => expect(result.current.sessionError).not.toBeNull());

    getCurrentUser.mockResolvedValue(user);
    await act(async () => {
      result.current.retrySession();
    });

    await waitFor(() => expect(result.current.user).toEqual(user));
    expect(result.current.sessionError).toBeNull();
  });
});
