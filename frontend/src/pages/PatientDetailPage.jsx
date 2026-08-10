import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import CircularProgress from "@mui/material/CircularProgress";
import Paper from "@mui/material/Paper";
import Typography from "@mui/material/Typography";

import { documentsPath, patientPath } from "../api.js";
import { useAuth } from "../auth/AuthContext.jsx";
import DocumentList from "../components/DocumentList";
import PatientDetail from "../components/PatientDetail";

import "../css/PatientDetailPage.css";

/**
 * Die Akte eines Patienten: Stammdaten links, Dokumente rechts.
 *
 * Beides kommt aus der API — die Stammdaten aus `GET /patients/{id}`
 * (docs/patients-api.md), die Dokumente aus `GET /docs/{patient_id}`
 * (docs/documents-api.md). Der Weg dahin führt über `apiFetch` aus dem
 * `AuthContext`: Dort hängt der Token dran, und ein `401` meldet ab.
 *
 * Gesucht wird **im Browser**, nicht über `q`. Das Feld filtert nach Titel,
 * Tags und Dokumenttyp; `q` durchsucht dagegen Titel und Beschreibung
 * (docs/documents-api.md). Ein Umstieg auf die Suche des Backends würde die
 * Suche nach einem Tag also stillschweigend abschalten. Die Liste ist
 * vollständig geladen — ein Patient hat ein paar Dutzend Dokumente, keine
 * Tausend.
 */
export function PatientDetailPage() {
  const { patientId } = useParams();
  const { apiFetch } = useAuth();

  // `null` heißt "noch nicht geladen" und ist damit etwas anderes als die
  // leere Liste: Ein Patient ohne Dokumente ist ein gültiger Zustand, kein
  // Ladezustand.
  const [patient, setPatient] = useState(null);
  const [documents, setDocuments] = useState(null);
  const [error, setError] = useState(null);

  const [searchTextDocuments, setSearchTextDocuments] = useState("");
  const [editingId, setEditingId] = useState(null);

  useEffect(() => {
    const controller = new AbortController();

    // Zurück auf Anfang: Ohne das stünden beim Wechsel auf den nächsten
    // Patienten kurz dessen Name über den Dokumenten des vorigen.
    setPatient(null);
    setDocuments(null);
    setError(null);

    Promise.all([
      apiFetch(patientPath(patientId), { signal: controller.signal }),
      apiFetch(documentsPath(patientId), { signal: controller.signal }),
    ])
      .then(([loadedPatient, documentPage]) => {
        setPatient(loadedPatient);
        setDocuments(documentPage.items);
      })
      .catch((loadError) => {
        if (controller.signal.aborted) {
          return;
        }
        setError(loadError);
      });

    // `patientId` steht in den Abhängigkeiten: Der Wechsel von einer
    // Detailseite zur nächsten tauscht nur den Parameter aus, die Komponente
    // bleibt stehen. Ohne ihn bliebe der erste Patient stehen.
    return () => controller.abort();
  }, [apiFetch, patientId]);

  /**
   * Entfernt ein Dokument aus der Liste.
   *
   * Noch **ohne** `DELETE /docs/{patient_id}/{document_id}` — das Löschen
   * wirklich wirken zu lassen ist Issue #78. Bis dahin ist es nur die Anzeige,
   * und ein Neuladen bringt das Dokument zurück.
   */
  function handleDeleteDocument(id) {
    setDocuments((current) => current.filter((document) => document.id !== id));
  }

  /** Wie beim Löschen: bis auf Weiteres nur in der Anzeige (Issue #78). */
  function handleUpdateDocument(id, _patientId, changes) {
    setDocuments((current) =>
      current.map((document) =>
        document.id === id ? { ...document, ...changes } : document,
      ),
    );
    setEditingId(null);
  }

  function handleStartEdit(id) {
    setEditingId(id);
  }

  function handleCancelEdit() {
    setEditingId(null);
  }

  if (error) {
    return (
      <Box>
        {/* Der Satz kommt aus der Antwort (`ApiError.message`) und nicht aus
            dieser Seite — sonst hiesse "gibt es nicht" hier anders als im
            Backend. Nur die Überschrift steht fest, weil `404` immer
            dieselbe Auskunft ist. */}
        {error.status === 404 ? (
          <Paper variant="outlined" sx={{ padding: 4, textAlign: "center" }}>
            <Typography variant="h6" component="p">
              Patient nicht gefunden
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {error.message}
            </Typography>
          </Paper>
        ) : (
          <Alert severity="error">{error.message}</Alert>
        )}
      </Box>
    );
  }

  if (patient === null || documents === null) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", paddingBlock: 6 }}>
        <CircularProgress aria-label="Patientenakte wird geladen" />
      </Box>
    );
  }

  const filteredDocuments = documents.filter((document) =>
    matchesSearch(document, searchTextDocuments),
  );

  return (
    <div className="app-main">
      <aside className="app-sidebar">
        <PatientDetail patient={patient} />
      </aside>

      <section className="app-content">
        <div className="search-box">
          <span className="search-icon">⌕</span>

          <input
            type="text"
            placeholder="Suche in Titel, Tags und Dokumenttyp"
            className="search-input"
            aria-label="Suche in Titel, Tags und Dokumenttyp"
            value={searchTextDocuments}
            onChange={(event) => setSearchTextDocuments(event.target.value)}
          />
        </div>

        <DocumentList
          documents={filteredDocuments}
          searchTextDocuments={searchTextDocuments}
          editingId={editingId}
          onDelete={handleDeleteDocument}
          onStartEdit={handleStartEdit}
          onCancelEdit={handleCancelEdit}
          onUpdateDocument={handleUpdateDocument}
        />
      </section>
    </div>
  );
}

/**
 * Trifft der Suchtext auf Titel, Tags oder Dokumenttyp?
 *
 * Ein leerer Text trifft alles — "keine Suche" ist kein Filter. `description`
 * bleibt bewusst draußen: Das Feld steht so im Suchfeld, und ein Treffer, den
 * niemand in der Karte sieht, sähe nach einem Fehler aus.
 */
function matchesSearch(document, searchText) {
  const term = searchText.trim().toLowerCase();
  if (term === "") {
    return true;
  }

  const haystack = [
    document.title,
    document.document_type,
    ...(document.tags ?? []),
  ];

  return haystack.some((value) => (value ?? "").toLowerCase().includes(term));
}
