import DocumentCard from '../components/DocumentCard';

function DocumentList({ documents, searchTextDocuments, searchTagDocuments, error, editingId, onDelete,
  onStartEdit, onCancelEdit, onUpdateDocument}) {
  if (documents.length === 0 &&  searchTextDocuments.trim() === "" && error === '') {
    return (
      <div className="empty-state">
        <div className="empty-state-icon">📚</div>
        <h3 className="empty-state-title">Keine eigenen Dokumente vorhanden</h3>
        <p className="empty-state-text">
          Füge dein erstes Dokument hinzu, um loszulegen!
        </p>
      </div>
    );
  }

  if (documents.length === 0 && searchTextDocuments.length > 0) {
    return (
    <div className="empty-state">
        <div className="empty-state-icon">📚</div>
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
          error={error}
          onStartEdit={onStartEdit}
          onCancelEdit={onCancelEdit}
          onUpdateDocument={onUpdateDocument}
        />
      ))}
    </div>
  );
}

export default DocumentList;
