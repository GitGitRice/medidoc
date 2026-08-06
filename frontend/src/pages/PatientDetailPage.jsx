import DocumentList from '../components/DocumentList';
import PatientDetail from '../components/PatientDetail';

import './App.css';

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

  setPatient(getPatient(patientId));
  setLoading(true);
  setDocuments(getDocuments(patientId));
  setLoading(false);

  }
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
                onUpdateBook={handleUpdateDocument}
              />
              )}
        </section>
      </main>        
      )
