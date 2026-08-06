/**
 * Der einzige Ort, an dem dieses Frontend das Backend anspricht.
 *
 * Kennt keine React-Begriffe: Hier steht, wie ein Request aussieht und wie ein
 * Fehler heißt, nicht was die Oberfläche damit macht. Der Vertrag steht in
 * docs/auth-api.md.
 */

const API_URL = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(
  /\/$/,
  "",
);

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

const GENERIC_ERROR = "Die Anfrage ist fehlgeschlagen.";

/**
 * Die Meldung zu einem `403` — der Wortlaut aus docs/auth-api.md.
 *
 * Steht hier und nicht in einer Seite, damit jede Stelle, die eine Rolle nicht
 * hat, denselben Satz zeigt.
 */
export const FORBIDDEN_ERROR = "Dazu fehlt dir die Berechtigung";

async function readResponse(response) {
  if (response.status === 204) {
    return null;
  }

  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    return response.json();
  }

  return response.text();
}

/**
 * Die Meldung aus einer Fehlerantwort — oder ein neutraler Satz.
 *
 * `detail` ist bei uns ein String (docs/auth-api.md). FastAPI selbst antwortet
 * bei einem Validierungsfehler aber mit einer *Liste* von Objekten unter
 * demselben Schlüssel. Ungeprüft übernommen stünde davon "[object Object]" in
 * der Oberfläche, deshalb wird hier auf einen String bestanden.
 *
 * Bei `403` steht die Meldung auch dann fest, wenn die Antwort keine mitbringt:
 * Der Fall ist immer derselbe — angemeldet, aber die Rolle reicht nicht — und
 * dafür ist "Die Anfrage ist fehlgeschlagen." keine Auskunft.
 */
function errorMessage(body, status) {
  if (typeof body === "object" && typeof body?.detail === "string") {
    return body.detail;
  }

  if (status === 403) {
    return FORBIDDEN_ERROR;
  }

  return GENERIC_ERROR;
}

/**
 * Ein Request gegen die API. `token` wird, wenn gesetzt, als Bearer-Header
 * mitgeschickt — damit kein Aufrufer den Header selbst zusammenbaut.
 */
export async function apiRequest(path, { token, headers, ...options } = {}) {
  let response;

  try {
    response = await fetch(`${API_URL}${path}`, {
      ...options,
      headers: {
        ...headers,
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });
  } catch (error) {
    // Ein abgebrochener Request ist kein Netzwerkfehler, sondern Absicht des
    // Aufrufers — er muss als AbortError erkennbar bleiben.
    if (error.name === "AbortError") {
      throw error;
    }
    throw new ApiError("Das Backend ist nicht erreichbar.", 0);
  }

  const body = await readResponse(response);

  if (!response.ok) {
    throw new ApiError(errorMessage(body, response.status), response.status);
  }

  return body;
}

export function login(email, password) {
  return apiRequest("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ username: email, password }),
  });
}

export function getCurrentUser(token, options = {}) {
  return apiRequest("/auth/me", { ...options, token });
}
