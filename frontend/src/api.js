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

/**
 * Hängt Suche und Seitengröße an einen Pfad, soweit gesetzt.
 *
 * Eine Stelle für alle Listen: `q`, `limit` und `offset` heißen bei Patienten,
 * Benutzern und Dokumenten gleich (docs/patients-api.md,
 * docs/documents-api.md). Eine leere Suche wird weggelassen und nicht als
 * `q=` geschickt — das Backend liest beides gleich, in der Adresszeile steht
 * sonst ein Filter, der keiner ist.
 */
function withQuery(path, { q, limit, offset } = {}) {
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
  return query ? `${path}?${query}` : path;
}

/**
 * Der Pfad für `GET /patients`, mit Suche und Seitengröße.
 */
export function patientsPath({ q, limit, offset } = {}) {
  return withQuery("/patients", { q, limit, offset });
}

/** Der Pfad für `GET /patients/{id}` — ein einzelner Patient mit allen Feldern. */
export function patientPath(patientId) {
  return `/patients/${patientId}`;
}

/**
 * Der Pfad für `GET /docs/{patient_id}` — die Dokumente eines Patienten.
 *
 * `q` filtert nach **Titel und Beschreibung**, nicht nach Tags oder
 * Dokumenttyp (docs/documents-api.md).
 */
export function documentsPath(patientId, { q, limit, offset } = {}) {
  return withQuery(`/docs/${patientId}`, { q, limit, offset });
}

/**
 * Der Pfad für `GET /users` und `POST /users` — nur für `admin`.
 *
 * Die Liste enthält auch deaktivierte Benutzer; erkennbar sind sie an
 * `is_active`.
 */
export function usersPath({ limit, offset } = {}) {
  return withQuery("/users", { limit, offset });
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
