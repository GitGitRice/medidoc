// ===========================================================================
// documentLIST.JSX - Listen-Komponente mit Conditional Rendering
// ===========================================================================
//
// Diese Datei zeigt wie man Listen rendert und zwischen verschiedenen
// Ansichten wechselt je nach Datenstand
//
// React-Konzepte in dieser Datei:
// - Listen rendern: Array.map um Komponenten zu erzeugen
// - key Prop: Eindeutige Identifikation von Listen-Elementen
// - Conditional Rendering: Verschiedene UI je nach Zustand
// - Early Return: Fruehes Beenden bei bestimmten Bedingungen
// - Props Drilling: Props durch Komponenten durchreichen
// - Komponenten-Komposition: Kindkomponenten einbetten
//
// ===========================================================================

// Import der ItemCard Komponente
// ItemList ist selbst eine Kindkomponente von App
// und ItemCard ist eine Kindkomponente von ItemList
// so entsteht die Komponentenhierarchie
import DocumentCard from '../components/DocumentCard';

// Props Destructuring
// items ist das Array mit allen Items
// onDelete und onToggleFavorite sind Callback-Funktionen
// die wir an ItemCard weiterreichen
function DocumentList({ documents, searchTextdocuments, searchTagdocuments, error, onDelete, onToggleFavorite, editingId,
  onStartEdit, onCancelEdit, onUpdatedocument}) {
  // Conditional Rendering: wenn keine Items vorhanden sind
  // zeigen wir einen Empty-State statt einer leeren Liste
  // das ist bessere UX weil der User Feedback bekommt
  //
  // Early Return Pattern: wenn die Bedingung erfuellt ist
  // geben wir sofort JSX zurueck und der Rest der Funktion wird nicht ausgefuehrt
  if (documents.length === 0 &&  searchTextdocuments.trim() === "" && error === '') {
    return (
      <div className="empty-state">
        <div className="empty-state-icon">📚</div>
        <h3 className="empty-state-title">Keine eigenen Bücher vorhanden</h3>
        <p className="empty-state-text">
          Füge dein erstes Buch hinzu, um loszulegen!
        </p>
      </div>
    );
  }

  if (documents.length === 0 && searchTextdocuments.length > 0) {
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

  // wenn wir hier ankommen gibt es mindestens ein Item
  // wir rendern die Liste mit allen Items
  return (
    <div className="item-list">
      {/* map transformiert das items-Array in ein Array von JSX-Elementen
          fuer jedes item im Array erzeugen wir eine ItemCard Komponente

          die key Prop ist bei Listen in React Pflicht
          React nutzt den key um Elemente zu identifizieren
          wenn sich die Liste aendert kann React effizient updaten
          der key muss eindeutig und stabil sein
          hier nutzen wir item.id weil jedes Item eine unique ID hat

          WICHTIG: niemals den Array-Index als key verwenden
          das fuehrt zu Problemen wenn Items hinzugefuegt geloescht oder sortiert werden */}
      {documents.map(document => (
        <documentCard
          key={document.id}
          document={document}
          isEditing={editingId === document.id}
          onDelete={onDelete}
          error={error}
          onToggleFavorite={onToggleFavorite}
          onStartEdit={onStartEdit}
          onCancelEdit={onCancelEdit}
          onUpdatedocument={onUpdatedocument}
        />
      ))}
    </div>
  );
}

export default DocumentList;
