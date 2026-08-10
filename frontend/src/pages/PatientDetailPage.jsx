import DocumentList from '../components/DocumentList';
import { CreateDocumentCard } from '../components/CreateDocumentCard';
import PatientDetail from '../components/PatientDetail';

import '../css/PatientDetailPage.css';

import { useEffect, useState } from 'react';
import { useParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export function PatientDetailPage() {

  const { patientId } = useParams();
  const { apiFetch } = useAuth();

  const [patient, setPatient] = useState(null);
  const [documents, setDocuments] = useState([]);

  const [searchTextDocuments, setSearchTextDocuments] = useState("");
  const [searchTagDocuments, setSearchTagDocuments] = useState("");
  const [searchTypeDocuments, setSearchTypeDocuments] = useState("");
  const [selectedDocument, setSelectedDocument] = useState(null);
  const [editingId, setEditingId] = useState(null);
  
  // NEU: Loading-State um dem User Feedback zu geben
  const [loading, setLoading] = useState(true);

  // NEU: Error-State um Fehler anzuzeigen
  const [error, setError] = useState(null);

  console.log("PatientId:   ", patientId );

  useEffect(() => {
  const controller = new AbortController();

  async function loadPatientWithDocuments() {
    try {
      setLoading(true);
      setError(null);

      const [patientData, documentsPage] = await Promise.all([
        apiFetch(`/patients/${patientId}`, {
          signal: controller.signal,
        }),
        apiFetch(`/docs/${patientId}?limit=100&offset=0`, {
          signal: controller.signal,
        }),
      ]);

      setPatient(patientData);
      setDocuments(documentsPage.items);
    } catch (error) {
      if (error.name !== "AbortError") {
        setError(
          error.message ??
            "Patient und Dokumente konnten nicht geladen werden.",
        );
      }
    } finally {
      if (!controller.signal.aborted) {
        setLoading(false);
      }
    }
  }

    loadPatientWithDocuments();

    return () => controller.abort();
  }, [patientId, apiFetch]);

  async function handleDeleteDocument(id) {
    try {
      // API-Call: DELETE
      // await deleteDocument(id);    
      setDocuments(prevDocuments => prevDocuments.filter(document => document.id !== id));
    } catch (err) {
      console.error("Fehler beim Löschen:", err);
      setError("Dokument konnte nicht geloescht werden.");
    }
  }

  async function handleCreateDocument(formData) {
    const createdDocument = await apiFetch(`/docs/${patientId}`, {
      method: "POST",
      body: formData,
    });

    // Die API liefert das neu angelegte Dokument vollständig zurück. Da die
    // Liste nach Erstellungszeit absteigend sortiert ist, kommt es nach oben.
    setDocuments((currentDocuments) => [createdDocument, ...currentDocuments]);
  }

  async function handleUpdateDocument(id, patientId, changeDocument) {

    const currentDocument = documents.find(document => document.id === id);
    if (!currentDocument) return;

    try {
      
      const updatedDocument = {
        ...currentDocument,
        patient_id: patientId,
        ...changeDocument,
      };
          
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

    function handleCancelEdit() {
      setEditingId(null);
    }

    const filteredDocuments = documents.filter( document => {

    const searchTextLowerCase = searchTextDocuments.trim().toLowerCase();
    if(searchTextLowerCase === "") {
      return true; 
    }

    let textMatch = true;
      
    if (searchTextLowerCase.length > 0) {
        const titleMatchBySearchText = document.title.trim().toLowerCase().includes(searchTextLowerCase);
        const tagMatchBySearchText = document.tags === null ? 
                  false : document.tags.join(', ').toLowerCase().includes(searchTextLowerCase);
        const typeMatchBySearchText = document.document_type === null ? 
                  false : document.document_type.toLowerCase().includes(searchTextLowerCase);         
          textMatch = titleMatchBySearchText 
                    || tagMatchBySearchText
                    || typeMatchBySearchText;
    }

      return textMatch;
    })
    if (error) 
      return (  
      <div className="app-main">
           {error && (
              <div style={{
                gridColumn : "1 / -1",
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
      </div> )
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
             
            <div className="search-box">
                <input
                  type="text"
                  placeholder="Suche in Titel, Tags und Dokumenttyp"
                  className="search-input"
                  value={searchTextDocuments}
                  onChange={(e) => setSearchTextDocuments(e.target.value)}
                />
            </div>
            <CreateDocumentCard onCreate={handleCreateDocument} />
            {/* NEU: Loading-Anzeige waehrend die Dokumente geladen werden */}           
            {loading ? (
                <p style={{ textAlign: "center", color: "#888", padding: "40px" }}>
                  Lade Dokumente...
                </p>
              ) : (
              <DocumentList
                documents = {filteredDocuments}
                searchTextDocuments={searchTextDocuments}
                error={error}
                editingId={editingId}
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
