import { useRef, useState } from "react";

const MAX_FILE_SIZE = 20 * 1024 * 1024;

export function CreateDocumentCard({ onCreate }) {
  const [isOpen, setIsOpen] = useState(false);
  const [documentType, setDocumentType] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [tags, setTags] = useState("");
  const [source, setSource] = useState("");
  const [file, setFile] = useState(null);
  const [error, setError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const fileInputRef = useRef(null);

  function resetForm() {
    setDocumentType("");
    setTitle("");
    setDescription("");
    setTags("");
    setSource("");
    setFile(null);
    setError(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  function handleCancel() {
    resetForm();
    setIsOpen(false);
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError(null);

    if (file && file.size > MAX_FILE_SIZE) {
      setError("Der Anhang darf höchstens 20 MB groß sein.");
      return;
    }

    const formData = new FormData();
    formData.append("document_type", documentType);
    formData.append("title", title);
    if (description.trim()) formData.append("description", description);
    if (tags.trim()) formData.append("tags", tags);
    if (source.trim()) formData.append("source", source);
    if (file) formData.append("file", file);

    setIsSubmitting(true);
    try {
      await onCreate(formData);
      resetForm();
      setIsOpen(false);
    } catch (createError) {
      setError(createError.message ?? "Dokument konnte nicht angelegt werden.");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (!isOpen) {
    return (
      <div className="item-card create-document-card">
        <div>
          <h2 className="create-document-title">Neues Dokument</h2>
          <p className="create-document-description">
            Füge der Akte einen Eintrag mit optionalem Anhang hinzu.
          </p>
        </div>
        <button className="edit-btn edit-btn--save" onClick={() => setIsOpen(true)}>
          Dokument anlegen
        </button>
      </div>
    );
  }

  return (
    <article className="item-card create-document-form-card">
      <form onSubmit={handleSubmit} aria-busy={isSubmitting}>
        <h2 className="create-document-title">Dokument anlegen</h2>

        {error && <div className="create-document-error" role="alert">{error}</div>}

        <div className="create-document-fields">
          <label className="form-label">
            Titel <span className="required">*</span>
            <input
              className="edit-input"
              required
              autoFocus
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Titel des Dokumentes"
            />
          </label>
          <label className="form-label">
            Dokumenttyp <span className="required">*</span>
            <input
              className="edit-input"
              required
              value={documentType}
              onChange={(event) => setDocumentType(event.target.value)}
              placeholder="z. B. Befund, Arztbrief oder Laborwert"
            />
          </label>
          <label className="form-label create-document-wide-field">
            Beschreibung <span className="optional">(optional)</span>
            <textarea
              className="edit-input create-document-textarea"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Kurze Beschreibung"
            />
          </label>
          <label className="form-label">
            Tags <span className="optional">(optional)</span>
            <input
              className="edit-input"
              value={tags}
              onChange={(event) => setTags(event.target.value)}
              placeholder="z. B. mrt, radiologie"
            />
          </label>
          <label className="form-label">
            Quelle <span className="optional">(optional)</span>
            <input
              className="edit-input"
              value={source}
              onChange={(event) => setSource(event.target.value)}
              placeholder="z. B. Radiologie Mitte"
            />
          </label>
        </div>

        <div className="create-document-footer">
          <label className="upload-btn">
            Anhang hochladen
            <input
              ref={fileInputRef}
              type="file"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            />
          </label>
          <span className="selected-file">{file ? file.name : "Kein Anhang ausgewählt"}</span>
          <div className="edit-actions create-document-actions">
            <button type="button" className="edit-btn edit-btn--cancel" onClick={handleCancel} disabled={isSubmitting}>
              Abbrechen
            </button>
            <button type="submit" className="edit-btn edit-btn--save" disabled={isSubmitting}>
              {isSubmitting ? "Wird angelegt …" : "Anlegen"}
            </button>
          </div>
        </div>
      </form>
    </article>
  );
}
