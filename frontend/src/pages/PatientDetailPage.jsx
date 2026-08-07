import DocumentList from '../components/DocumentList';
import PatientDetail from '../components/PatientDetail';

import '../App.css';

import { useParams } from "react-router-dom";

import patients from "../data/patients.json";
import documents from "../data/documents.json";


export default function PatientDetailPage() {

  const { patientId } = useParams();

  const [patient, setPatient] = useState(null);
  const [documents, setDocuments] = useState([]);
  
  // NEU: Loading-State um dem User Feedback zu geben
  const [loading, setLoading] = useState(true);

  // NEU: Error-State um Fehler anzuzeigen
  const [error, setError] = useState(null);

  async function getPatient(patientId) {
  return patients.find((p) => p.id === Number(id));
  }

  async function getDocuments(patientId) {
    return documents.filter((d) => d.patientId === Number(patientId));
  }

  async function loadPatient(patientId) {
    try {
      setLoading(true);
      setError(null);
      // API-Call: GET /items
      //const data = await fetchPatient();
      const data = getPatient(patientId);
      setPatient(patientId);
    } catch (err) {
      console.error("Fehler beim Laden:", err);
      setError("Patient konnten nicht geladen werden. Läuft das Backend?");
    } finally {
      setLoading(false);
    }
  }

  async function loadDocuments(patientId) {
    try {
      setLoading(true);
      setError(null);
      // API-Call: GET /items
      const data = getDocuments(patientId);
      setDocuments(data);
    } catch (err) {
      console.error("Fehler beim Laden:", err);
      setError("Dokumente konnten nicht geladen werden. Läuft das Backend?");
    } finally {
      setLoading(false);
    }
  }

  // HANDFLER
  // Handler zum Loeschen 
  async function handleDeleteDocument(id) {
    try {
      // API-Call: DELETE /items/{id}
      await deleteDocument(id);
      // Item aus dem lokalen State entfernen
      setDocuments(prevDocuments => prevDocuments.filter(document => document.id !== id));
    } catch (err) {
      console.error("Fehler beim Loeschen:", err);
      setError("Buch konnte nicht geloescht werden.");
    }
  }

  // Handler fuer Favorit-Toggle - jetzt async mit API-Call
  async function handleUpdateDocument(id, changeDocument) {
    // aktuelles Item finden um den Favorit-Status umzukehren
    const currentDocument = documents.find(document => document.id === id);
    if (!currentDocument) return;

    try {
      // API-Call: PATCH /items/{id} mit den geänderten Werten
      const updatedDocument = await updateDocument(id, {
        favorite: updatedDocument.favorite,
        description: updatedDocument.description,
        title: updatedDocument.title,
        tags: updatedDocument.tags
      });
      // Item im lokalen State aktualisieren
      setDocuments(prevDocuments =>
        prevDocuments.map(document => document.id === id ? updatedDocument : document)
      );
      handleCancelEdit();
    } catch (err) {
      console.error("Fehler beim Aktualisieren:", err);
      setError("Dokument konnte nicht geaendert werden.");
    }
  }

   function handleStartEdit(id) {
      setEditingId(id);
    }

    // Handler: Edit abbrechen
    function handleCancelEdit() {
      setEditingId(null);
    }

    useEffect(() => {
    loadPatient(patientId) 
    loadDocuments(patientId);
  }, []);


  return ( 
        <main className="app-main">
             <aside className="app-sidebar">
                <PatientDetail patient = {patient} />
              </aside>
            <section className="app-content">
              {error && (
              <div style={{
                padding: "12px 16px",
                marginBottom: "16px",
                backgroundColor: "#fee",
                color: "#c00",
                borderRadius: "6px",
                border: "1px solid #fcc"
              }}>
                {error}
                <button
                  onClick={() => setError(null)}
                  style={{
                    marginLeft: "12px",
                    background: "none",
                    border: "none",
                    color: "#c00",
                    cursor: "pointer",
                    fontWeight: "bold"
                  }}
                >
                  ✕
                </button>
              </div>
            )}  
            {/* NEU: Loading-Anzeige waehrend die Dokumente geladen werden */}           
            {loading ? (
                <p style={{ textAlign: "center", color: "#888", padding: "40px" }}>
                  Lade Dokumente...
                </p>
              ) : (
              <DocumentList
                documents = {documents}
                error={error}
                onDelete={handleDeleteDocument}
                onToggleImportant={handleToggleImportant}
                editingId={editingId}
                onStartEdit={handleStartEdit}
                onCancelEdit={handleCancelEdit}
                onUpdateDocument={handleUpdateDocument}
              />
              )}
        </section>
      </main>        
      )
    }
