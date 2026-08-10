import DocumentCard from '../components/DocumentCard';

/**
 * Die Dokumente einer Akte — oder der Grund, warum keine dastehen.
 *
 * Zwei Leerzustände, weil es zwei verschiedene Lagen sind: eine Akte ohne
 * Dokumente ist ein gültiger Zustand (docs/documents-api.md), eine Suche ohne
 * Treffer ein Hinweis auf den Suchtext.
 */
function DocumentList({ documents, searchTextDocuments, editingId, onDelete,
  onStartEdit, onCancelEdit, onUpdateDocument}) {
  if (documents.length === 0 &&  searchTextDocuments.trim() === "") {
    return (
      <div className="empty-state">
        <div className="empty-state-icon">📑</div>
        <h3 className="empty-state-title">Keine Dokumente in dieser Akte</h3>
        <p className="empty-state-text">
          Für diesen Patienten wurde noch kein Dokument angelegt.
        </p>
      </div>
    );
  }

  if (documents.length === 0 && searchTextDocuments.length > 0) {
    return (
    <div className="empty-state">
        <div className="empty-state-icon">📑</div>
        <h3 className="empty-state-title">Keine Ergebnisse vorhanden</h3>
        <p className="empty-state-text">
          Bitte passe den Suchtext an.
        </p>
      </div>
    );
  }

  return (
    <div className="item-list">
      {documents.map(document => (
        <DocumentCard
          key={document.id}
          document={document}
          isEditing={editingId === document.id}
          onDelete={onDelete}
          onStartEdit={onStartEdit}
          onCancelEdit={onCancelEdit}
          onUpdateDocument={onUpdateDocument}
        />
      ))}
    </div>
  );
}

export default DocumentList;
