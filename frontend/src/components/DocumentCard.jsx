// ===========================================================================
// DOCUMENTCARD.JSX - Einzelne Item-Karte mit Interaktionen
// ===========================================================================
//
// Diese Datei zeigt wie man Daten darstellt und Events an Eltern weitergibt
// Die Komponente hat keinen eigenen State aber reagiert auf User-Aktionen
//
// React-Konzepte in dieser Datei:
// - Event Handling: onClick fuer Button-Klicks
// - Callback Props: Funktionen von Eltern aufrufen
// - Conditional Rendering: Elemente nur bei Bedingung anzeigen
// - Dynamische CSS-Klassen: Klassen basierend auf State aendern
// - Listen rendern: map ueber Arrays mit key Prop
// - Template Strings: Dynamische Klassennamen zusammenbauen
//
// ===========================================================================

// Props Destructuring mit drei Werten
// item enthaelt alle Daten des Items wie title url tags usw
// onDelete ist eine Callback-Funktion zum Loeschen
// onToggleFavorite ist eine Callback-Funktion zum Umschalten des Favoriten-Status
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

function DocumentCard({ document, isEditing, onDelete, onToggleFavorite, onStartEdit, onCancelEdit, onUpdateDokument }) {
    // Lokaler State für Edit-Formular
  const [editTitle, setEditTitle] = useState(document.title || '');
  const [editDescription, setEditDescription] = useState(document.description || '');
  const [editTags, setEditTags] = useState(document.tags?.join(', ') || '');

  const navigate = useNavigate();

  // Wenn Item sich ändert, Formular-Werte aktualisieren
  useEffect(() => {
    setEditTitle(document.title);
    setEditDescription(document.description || '');
    setEditTags(document.tags?.join(', ') || '');
  }, [document]);

  // Save Handler
  function handleSave() {
    if (editTitle.trim() === '') return;

    const tags = editTags
      .split(',')
      .map(tag => tag.trim().toLowerCase())
      .filter(tag => tag !== '');

    onUpdatedocument(document.id, document.patientId, {
      title: editTitle.trim(),
      description: editAuthor.trim(),
      tags: tags
    });
  }
  
  // Datum formatieren fuer die Anzeige
  // new Date() erzeugt ein Datumsobjekt aus dem ISO-String
  // toLocaleDateString formatiert es nach deutschen Konventionen
  // die Optionen bestimmen das Format: 01.01.2024
  const formattedDate = new Date(document.createdAt).toLocaleDateString('de-DE', {
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
   <article className={`item-card ${document.favorite ? 'item-card--favorite' : ''}`}>
      <div className="item-card-header">
        <h3 className="item-title">{document.title}</h3>
        <button
          className={`favorite-btn ${document.favorite ? 'favorite-btn--active' : ''}`}
          onClick={() => onToggleFavorite(document.id)}
        >
          {document.favorite ? '★' : '☆'}
        </button>
      </div>

      {document.dexscription && (
        <a className="item-url">
          {document.description}
        </a>
      )}

      {document.tags && document.tags.length > 0 && (
        <div className="item-tags">
          {document.tags.map(tag => (
            <span key={tag} className="tag">{tag}</span>
          ))}
        </div>
      )}

      <div className="item-card-footer">
        <span className="item-date">Erstellt: {formattedDate}</span>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            className="edit-btn edit-btn--cancel"
            onClick={() => onStartEdit(document.id)}
          >
            Bearbeiten
          </button>
          <button className="delete-btn" onClick={() => onDelete(document.id)}>
            Löschen
          </button>
        </div>
      </div>
    </article>
  );
}
export default DocumentCard;
