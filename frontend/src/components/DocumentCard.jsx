import { useState, useEffect } from 'react';

import { useAuth } from "../auth/AuthContext";
import DeleteConfirmDialog from "./dialogs/DeleteConfirmDialog";

function DocumentCard({ document, isEditing, onDelete, onStartEdit, onCancelEdit, onUpdateDocument }) {
  const { hasRole } = useAuth();
  const canDelete = hasRole("admin");
  
  function normalizeTags(tags) {
    if (Array.isArray(tags)) {
      return tags;
    }

    if (typeof tags === "string") {
      return tags
        .split(",")
        .map(tag => tag.trim())
        .filter(Boolean);
    }

    return [];
  } 

  const normalizedTags = normalizeTags(document.tags);

  const [editDocumentType, setEditDocumentType] = useState(document.document_type || '');
  const [editTitle, setEditTitle] = useState(document.title || '');
  const [editDescription, setEditDescription] = useState(document.description || '');
  const [editTags, setEditTags] = useState(normalizedTags.join(", "));
  const [editSource, setEditSource] = useState(document.source || '');

  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  

  // Wenn Item sich ändert, Formular-Werte aktualisieren
  useEffect(() => {
    setEditDocumentType(document.document_type || '');
    setEditTitle(document.title);
    setEditDescription(document.description || '');
    setEditTags(normalizedTags.join(", "));
    setEditSource(document.source || '');
  }, [document]);

  //Dialog Handler
  const handleDeleteClick = () => {
    setDeleteDialogOpen(true);
  };

  const handleCancelDelete = () => {
    setDeleteDialogOpen(false);
  };

  const handleConfirmDelete = async () => {
    try {
      await onDelete(document.id);
    } finally {
      setDeleteDialogOpen(false);
    }
  };


  // Save Handler
  function handleSave() {
    if (editDocumentType.trim() === '' || editTitle.trim() === '') return;

    const tags = editTags
      .split(',')
      .map(tag => tag.trim().toLowerCase())
      .filter(tag => tag !== '');

    onUpdateDocument(document.id, document.patient_id, {
      document_type: editDocumentType.trim().toLowerCase(),
      title: editTitle.trim(),
      description: editDescription.trim(),
      tags,
      source: editSource.trim() || null,
    });
  }
  
  // Datum formatieren fuer die Anzeige
  // new Date() erzeugt ein Datumsobjekt aus dem ISO-String
  // toLocaleDateString formatiert es nach deutschen Konventionen
  // die Optionen bestimmen das Format: 01.01.2024
  const formattedDate = new Date(document.created_at).toLocaleDateString('de-DE', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric'
  });

  // Ein Dokument ohne Anhang ist gueltig (CONTEXT.md) — `attachment` ist dann
  // `null`. Das ist kein Fehlerfall und wird auch nicht als einer angezeigt.
  const attachment = document.attachment;

  if (isEditing) {
    return (
      <article className="item-card create-document-form-card">
        <form onSubmit={(event) => { event.preventDefault(); handleSave(); }}>
          <h2 className="create-document-title">Dokument bearbeiten</h2>

          <div className="create-document-fields">
            <label className="form-label">
              Titel <span className="required">*</span>
              <input
                className="edit-input"
                required
                autoFocus
                value={editTitle}
                onChange={(event) => setEditTitle(event.target.value)}
              />
            </label>
            <label className="form-label">
              Dokumenttyp <span className="required">*</span>
              <input
                className="edit-input"
                required
                value={editDocumentType}
                onChange={(event) => setEditDocumentType(event.target.value)}
              />
            </label>
            <label className="form-label create-document-wide-field">
              Beschreibung <span className="optional">(optional)</span>
              <textarea
                className="edit-input create-document-textarea"
                value={editDescription}
                onChange={(event) => setEditDescription(event.target.value)}
              />
            </label>
            <label className="form-label">
              Tags <span className="optional">(optional)</span>
              <input
                className="edit-input"
                value={editTags}
                onChange={(event) => setEditTags(event.target.value)}
                placeholder="z. B. mrt, radiologie"
              />
            </label>
            <label className="form-label">
              Quelle <span className="optional">(optional)</span>
              <input
                className="edit-input"
                value={editSource}
                onChange={(event) => setEditSource(event.target.value)}
                placeholder="z. B. Radiologie Mitte"
              />
            </label>
          </div>

          <div className="create-document-footer">
            <span className="selected-file">
              Der vorhandene Anhang bleibt unverändert.
            </span>
            <div className="edit-actions create-document-actions">
            <button
              type="button"
              className="edit-btn edit-btn--cancel"
              onClick={onCancelEdit}
            >
              Abbrechen
            </button>
            <button
              type="submit"
              className="edit-btn edit-btn--save"
            >
              Speichern
            </button>
            </div>
          </div>
        </form>
      </article>
    );
  }

  // NORMALE ANZEIGE
  return (
   <article className="item-card">
      <div className="item-card-header">
        <h3 className="item-title">{document.title}</h3>
            {document.document_type && (
              <span className="document-type-badge">
                  {document.document_type}
              </span>
             )}
      </div>

      {document.description && (
        <a className="item-url">
          {document.description}
        </a>
      )}

      {document.tags && document.tags.length > 0 && (
        <div className="item-tags">
          {normalizedTags.map(tag => (
            <span key={tag.trim()} className="tag">{tag}</span>
          )) }
        </div>
      )}

      <div className="item-meta">
        <span className="item-date">Erstellt: {formattedDate}</span>

        {attachment ? (
          <span className="item-attachment">
            📎 {attachment.filename ?? "Anhang"}
            {attachment.size_bytes != null && ` · ${formatSize(attachment.size_bytes)}`}
          </span>
        ) : (
          <span className="item-attachment item-attachment--none">
            Kein Anhang
          </span>
        )}
      </div>

      <div className="item-card-footer">

        <div className="document-actions">
          {/* Nur mit Anhang: Ein Knopf, hinter dem nichts liegt, sieht aus wie
              ein kaputter Download. Das Herunterladen selbst ist Issue #75. */}
          {attachment && (
            <button
              className="edit-btn edit-btn--cancel"
            >
              Anhang laden
            </button>
          )}
          <div className="document-actions-right">
            <button
              className="edit-btn edit-btn--cancel"
              onClick={() => onStartEdit(document.id)}
            >
              Bearbeiten
            </button>
          
            {canDelete && (
              <button
                className="delete-btn"
                onClick={handleDeleteClick}
              >
                Löschen
              </button>
            )}
          </div>
        </div>

        {canDelete && (
          <DeleteConfirmDialog
            open={deleteDialogOpen}
            title="Dokument löschen?"
            message={`Möchtest du "${document.title}" wirklich löschen?`}
            onCancel={handleCancelDelete}
            onConfirm={handleConfirmDelete}
          />
        )}

      </div>
    </article>
  );
}

/**
 * Die Groesse eines Anhangs, kurz und in deutscher Schreibweise.
 *
 * Das Backend liefert Bytes; ein "284913" in der Karte liest niemand. Gerundet
 * wird grosszuegig — die Zahl soll eine Groessenordnung geben, keine Bilanz.
 */
function formatSize(bytes) {
  if (bytes < 1024) {
    return `${bytes} B`;
  }

  const kilobytes = bytes / 1024;
  if (kilobytes < 1024) {
    return `${kilobytes.toFixed(0)} KB`;
  }

  return `${(kilobytes / 1024).toLocaleString("de-DE", {
    maximumFractionDigits: 1,
  })} MB`;
}

export default DocumentCard;
