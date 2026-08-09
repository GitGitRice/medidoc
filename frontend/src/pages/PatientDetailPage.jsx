import DocumentList from '../components/DocumentList';
import PatientDetail from '../components/PatientDetail';

import '../css/PatientDetailPage.css';

import { useEffect, useState } from 'react';

import { useParams } from "react-router-dom";

import patientsAll from "../data/patients.json";
import documentsAll from "../data/documents.json";


export function PatientDetailPage() {

  const { patientId } = useParams();

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

  async function getPatient(patientId) {
    return patientsAll.find((p) => p.id === Number(patientId));
  }

  async function getDocuments(patientId) {
    return documentsAll.filter((d) => d.patient_id === Number(patientId));
  }

  async function loadPatientWithDocuments(patientId) {
    try {
      setLoading(true);
      setError(null);
      const patientData = await getPatient(patientId);

      if (!patientData || !patientData.id) {
        throw new Error("Patient nicht gefunden");
      }
      
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

  async function handleUpdateDocument(id, patientId, changeDocument) {

    const currentDocument = documents.find(document => document.id === id);
    if (!currentDocument) return;

    try {
      
      const updatedDocument = {
        id,
        patientId, 
        ...changeDocument,
        tags: changeDocument.tags?.join(", ") ?? "",
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

    useEffect(() => {
      loadPatientWithDocuments(patientId) 
    }, []);

  
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
                <span className="search-icon">⌕</span>

                <input
                  type="text"
                  placeholder="Suche in Titel, Tags und Dokumenttyp"
                  className="search-input"
                  value={searchTextDocuments}
                  onChange={(e) => setSearchTextDocuments(e.target.value)}
                />
            </div>
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
