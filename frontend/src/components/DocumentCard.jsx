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

  const [editTitle, setEditTitle] = useState(document.title || '');
  const [editDescription, setEditDescription] = useState(document.description || '');
  const [editTags, setEditTags] = useState(normalizedTags.join(", "));

  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  

  // Wenn Item sich ändert, Formular-Werte aktualisieren
  useEffect(() => {
    setEditTitle(document.title);
    setEditDescription(document.description || '');
    setEditTags(normalizedTags.join(", "));
  }, [document]);

  //Dialog Handler
  const handleDeleteClick = () => {
    setDeleteDialogOpen(true);
  };

  const handleCancelDelete = () => {
    setDeleteDialogOpen(false);
  };

  const handleConfirmDelete = () => {
    onDelete(document.id);

    setDeleteDialogOpen(false);
  };


  // Save Handler
  function handleSave() {
    if (editTitle.trim() === '') return;

    const tags = editTags
      .split(',')
      .map(tag => tag.trim().toLowerCase())
      .filter(tag => tag !== '');

    onUpdateDocument(document.id, document.patientId, {
      title: editTitle.trim(),
      description: editDescription.trim(),
      tags: tags
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

  if (isEditing) {
    return (
      <article className="item-card">
        <div className="edit-form">
          <input
            type="text"
            className="edit-input"
            placeholder="Titel"
            value={editTitle}
            onChange={(e) => setEditTitle(e.target.value)}
            autotags
          />
          <input
            type="text"
            className="edit-input"
            placeholder="Beschreibung (optional)"
            value={editDescription}
            onChange={(e) => setEditDescription(e.target.value)}
          />
          <input
            type="text"
            className="edit-input"
            placeholder="Tags (kommagetrennt)"
            value={editTags}
            onChange={(e) => setEditTags(e.target.value)}
          />
          <div className="edit-actions">
            <button
              className="edit-btn edit-btn--cancel"
              onClick={onCancelEdit}
            >
              Abbrechen
            </button>
            <button
              className="edit-btn edit-btn--save"
              onClick={handleSave}
            >
              Speichern
            </button>
          </div>
        </div>
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

      <span className="item-date">Erstellt: {formattedDate}</span>

      <div className="item-card-footer">
        
        <div className="document-actions">
           <button
            className="edit-btn edit-btn--cancel"
           >
            Anhang laden
          </button>
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
export default DocumentCard;
