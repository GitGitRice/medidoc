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
  constructor(message, status, errors = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    // Ein Eintrag pro beanstandetem Feld bei `422` (app/core/errors.py),
    // sonst `null` — Formulare koennen so gezielt an einzelnen Feldern
    // eine Meldung zeigen, statt nur den zusammengefassten Text.
    this.errors = errors;
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
 * `message` ist unser eigenes Feld (app/core/errors.py) und bei jeder eigenen
 * Fehlerantwort ein String — das ist der Weg, auf den die Backend-Doku selbst
 * verweist. `detail` bleibt als Fallback für Antworten, die (noch) kein
 * `message` mitbringen. Roh-FastAPI liefert bei einem Validierungsfehler dort
 * eine *Liste* von Objekten unter demselben Schlüssel — ungeprüft übernommen
 * stünde davon "[object Object]" in der Oberfläche, deshalb wird auf einen
 * String bestanden.
 *
 * Bei `403` steht die Meldung auch dann fest, wenn die Antwort keine mitbringt:
 * Der Fall ist immer derselbe — angemeldet, aber die Rolle reicht nicht — und
 * dafür ist "Die Anfrage ist fehlgeschlagen." keine Auskunft.
 */
function errorMessage(body, status) {
  if (typeof body?.message === "string") {
    return body.message;
  }

  if (typeof body?.detail === "string") {
    return body.detail;
  }

  if (status === 403) {
    return FORBIDDEN_ERROR;
  }

  return GENERIC_ERROR;
}

/**
 * Die feldbezogenen Meldungen aus einer `422`-Antwort, oder `null`.
 *
 * `errors` kommt nur bei `422` und nur von unserem eigenen Handler
 * (app/core/errors.py) — ein Eintrag pro beanstandetem Feld mit `field` und
 * `message`.
 */
function fieldErrors(body) {
  if (typeof body === "object" && Array.isArray(body?.errors)) {
    return body.errors;
  }

  return null;
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
    throw new ApiError(
      errorMessage(body, response.status),
      response.status,
      fieldErrors(body),
    );
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

/** Hängt `limit` und `offset` an einen Pfad, soweit gesetzt. */
function withPaging(path, { limit, offset } = {}) {
  const params = new URLSearchParams();
  if (limit != null) {
    params.set("limit", limit);
  }
  if (offset != null) {
    params.set("offset", offset);
  }

  const query = params.toString();
  return query ? `${path}?${query}` : path;
}

/**
 * Der Pfad für `GET /patients`, mit Suche und Seitengröße.
 */
export function patientsPath({ q, limit, offset } = {}) {
  const params = new URLSearchParams();
  if (q) {
    params.set("q", q);
  }
  if (limit != null) {
    params.set("limit", limit);
  }
  if (offset != null) {
    params.set("offset", offset);
  }

  const query = params.toString();
  return query ? `/patients?${query}` : "/patients";
}

/**
 * Der Pfad für einen einzelnen Patienten — `GET`, `PATCH` und `DELETE
 * /patients/{id}` teilen sich diese Adresse.
 */
export function patientPath(id) {
  return `/patients/${id}`;
}

/**
 * Der Pfad für `GET /users` und `POST /users` — nur für `admin`.
 *
 * Die Liste enthält auch deaktivierte Benutzer; erkennbar sind sie an
 * `is_active`.
 */
export function usersPath({ limit, offset } = {}) {
  return withPaging("/users", { limit, offset });
}

/** Der Pfad für `PATCH /users/{id}`. */
export function userPath(userId) {
  return `/users/${userId}`;
}

/**
 * Die Options für einen Request mit JSON-Rumpf.
 *
 * Steht hier und nicht in den Seiten, damit `Content-Type` und
 * `JSON.stringify` nicht an jeder Aufrufstelle neu zusammengesetzt werden —
 * ein vergessener Header wäre ein `422`, das nach einem Datenfehler aussieht.
 */
export function jsonBody(method, data) {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  };
}
