import DocumentList from '../components/DocumentList';
import PatientDetail from '../components/PatientDetail';

import '../App.css';

import { useEffect, useState } from 'react';

import { useParams } from "react-router-dom";

import patientsAll from "../data/patients.json";
import documentsAll from "../data/documents.json";


export function PatientDetailPage() {

  const { patientId } = useParams();

  const [patient, setPatient] = useState(null);
  const [documents, setDocuments] = useState([]);
  
  // NEU: Loading-State um dem User Feedback zu geben
  const [loading, setLoading] = useState(true);

  // NEU: Error-State um Fehler anzuzeigen
  const [error, setError] = useState(null);

  console.log("PatientId:   "+patientId );

  async function getPatient(patientId) {
  return patientsAll.find((p) => p.id === Number(patientId));
  }

  async function getDocuments(patientId) {
    return documentsAll.filter((d) => d.patientId === Number(patientId));
  }

  async function loadPatientAndDocuments(patientId) {
    try {
      setLoading(true);
      setError(null);
      const patientData = await getPatient(patientId);
      console.log("Loading Patient: ", patientData)
      setPatient(patientData);
      const doccumentsData = await getDocuments(patientId);
      console.log("Loading Documents: ", doccumentsData)
      setDocuments(doccumentsData);
    } catch (err) {
      console.error("Fehler beim Laden:", err);
      setError("Patient und/oder Dokumente konnten nicht geladen werden. Läuft das Backend?");
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
        important: updatedDocument.important,
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
      loadPatientAndDocuments(patientId) 
  }, []);


  return ( 
        <div className="app-main">
             <aside className="app-sidebar">
              {loading ? (
                <p style={{ textAlign: "center", color: "#888", padding: "40px" }}>
                  Lade Patient...
                </p>
              ) : (
                <PatientDetail patient = {patient} />
              )}
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
                onStartEdit={handleStartEdit}
                onCancelEdit={handleCancelEdit}
                onUpdateDocument={handleUpdateDocument}
              />
              )}
        </section>
      </div>        
      )
    }
