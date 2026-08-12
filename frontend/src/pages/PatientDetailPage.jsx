import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import CircularProgress from "@mui/material/CircularProgress";
import Paper from "@mui/material/Paper";
import Typography from "@mui/material/Typography";

import { documentPath, documentsPath, jsonBody, patientPath } from "../api.js";
import { useAuth } from "../auth/AuthContext.jsx";
import { CreateDocumentCard } from "../components/CreateDocumentCard.jsx";
import DeleteConfirmDialog from "../components/dialogs/DeleteConfirmDialog";
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
  const { apiFetch, hasRole } = useAuth();
  const navigate = useNavigate();

  // `null` heißt "noch nicht geladen" und ist damit etwas anderes als die
  // leere Liste: Ein Patient ohne Dokumente ist ein gültiger Zustand, kein
  // Ladezustand.
  const [patient, setPatient] = useState(null);
  const [documents, setDocuments] = useState(null);
  const [error, setError] = useState(null);

  const [searchTextDocuments, setSearchTextDocuments] = useState("");
  const [editingId, setEditingId] = useState(null);
  const [actionError, setActionError] = useState(null);

  // Eigener Zustand fuer das Loeschen (Issue #22) — getrennt vom Lade-Fehler
  // oben: Ein gescheitertes Loeschen soll die geladene Akte nicht durch eine
  // "Patient nicht gefunden"-Seite ersetzen, sondern als Meldung auf der
  // weiterhin sichtbaren Seite stehen.
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState(null);

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

  /** Löscht ein Dokument dauerhaft über das Backend und danach aus der Liste. */
  async function handleDeleteDocument(id) {
    setActionError(null);

    try {
      await apiFetch(documentPath(patientId, id), { method: "DELETE" });
      setDocuments((current) =>
        current.filter((document) => document.id !== id),
      );
    } catch (deleteRequestError) {
      setActionError(deleteRequestError);
    }
  }

  async function handleCreateDocument(formData) {
    const createdDocument = await apiFetch(documentsPath(patientId), {
      method: "POST",
      body: formData,
    });

    setDocuments((current) => [createdDocument, ...current]);
  }

  /** Speichert die geänderten Angaben dauerhaft über den Dokument-PATCH. */
  async function handleUpdateDocument(id, _patientId, changes) {
    try {
      setActionError(null);
      const updatedDocument = await apiFetch(
        documentPath(patientId, id),
        jsonBody("PATCH", {
          document_type: changes.document_type,
          title: changes.title,
          description: changes.description,
          tags: Array.isArray(changes.tags)
            ? changes.tags.join(", ")
            : changes.tags,
          source: changes.source,
        }),
      );

      setDocuments((current) =>
        current.map((document) =>
          document.id === id ? updatedDocument : document,
        ),
      );
      setEditingId(null);
    } catch (updateError) {
      setActionError(updateError);
    }
  }

  function handleStartEdit(id) {
    setEditingId(id);
  }

  function handleCancelEdit() {
    setEditingId(null);
  }

  function openDeleteDialog() {
    setDeleteError(null);
    setIsDeleteDialogOpen(true);
  }

  function closeDeleteDialog() {
    if (isDeleting) {
      return;
    }
    setIsDeleteDialogOpen(false);
  }

  /**
   * Loescht den Patienten endgueltig (`DELETE /patients/{id}`, admin-only,
   * docs/patients-api.md).
   *
   * Ein `500` hier bedeutet nicht "nichts passiert" — Postgres hat den
   * Patienten zu dem Zeitpunkt bereits entfernt, nur das Aufraeumen der Akte
   * ist gescheitert. Ein erneuter Versuch faende ihn also nicht mehr und
   * antwortete mit `404`. Deshalb kein automatischer Retry und keine
   * Navigation bei einem Fehler — nur die Meldung, und die Seite bleibt
   * stehen, damit niemand blind ein zweites Mal klickt.
   */
  async function confirmDelete() {
    if (isDeleting) {
      return;
    }

    setIsDeleting(true);
    try {
      await apiFetch(patientPath(patientId), { method: "DELETE" });
      setIsDeleteDialogOpen(false);
      navigate("/");
    } catch (deleteRequestError) {
      setIsDeleteDialogOpen(false);
      setDeleteError(deleteRequestError);
    } finally {
      setIsDeleting(false);
    }
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
        {deleteError && (
          <Alert
            severity="error"
            sx={{ marginBlockEnd: 2 }}
            onClose={() => setDeleteError(null)}
          >
            {deleteError.message}
          </Alert>
        )}

        <PatientDetail
          patient={patient}
          canDelete={hasRole("admin")}
          onDeleteClick={openDeleteDialog}
        />
      </aside>

      <section className="app-content">
        {actionError && <Alert severity="error">{actionError.message}</Alert>}

        <div className="search-box">

          <input
            type="text"
            placeholder="Suche in Titel, Tags und Dokumenttyp"
            className="search-input"
            aria-label="Suche in Titel, Tags und Dokumenttyp"
            value={searchTextDocuments}
            onChange={(event) => setSearchTextDocuments(event.target.value)}
          />
        </div>

        <CreateDocumentCard onCreate={handleCreateDocument} />

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

      <DeleteConfirmDialog
        open={isDeleteDialogOpen}
        title="Patient löschen?"
        message={`Möchtest du ${patient.first_name} ${patient.last_name} wirklich löschen?`}
        onConfirm={confirmDelete}
        onCancel={closeDeleteDialog}
      />
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
