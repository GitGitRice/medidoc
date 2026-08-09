import React from "react";

export default function DeleteConfirmDialog({
  open,
  title = "Dokument löschen?",
  message = "Möchtest du dieses Dokument wirklich löschen?",
  onConfirm,
  onCancel,
}) {
  if (!open) return null;

  return (
    <div style={styles.overlay}>
      <div style={styles.dialog}>
        <h2 style={styles.title}>{title}</h2>

        <p style={styles.message}>{message}</p>

        <div style={styles.actions}>
          <button
            type="button"
            onClick={onCancel}
            style={styles.cancelButton}
          >
            Abbrechen
          </button>

          <button
            type="button"
            onClick={onConfirm}
            style={styles.deleteButton}
          >
            Löschen
          </button>
        </div>
      </div>
    </div>
  );
}

const styles = {
  overlay: {
    position: "fixed",
    inset: 0,
    backgroundColor: "rgba(0, 0, 0, 0.45)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 1000,
  },

  dialog: {
    width: "100%",
    maxWidth: "420px",
    backgroundColor: "#ffffff",
    borderRadius: "12px",
    padding: "24px",
    boxShadow: "0 20px 50px rgba(0, 0, 0, 0.2)",
  },

  title: {
    margin: "0 0 12px",
    fontSize: "20px",
    color: "#111827",
  },

  message: {
    margin: "0 0 24px",
    color: "#6b7280",
    lineHeight: 1.5,
  },

  actions: {
    display: "flex",
    justifyContent: "flex-end",
    gap: "10px",
  },

  cancelButton: {
    padding: "9px 16px",
    borderRadius: "8px",
    border: "1px solid #d1d5db",
    backgroundColor: "#ffffff",
    cursor: "pointer",
  },

  deleteButton: {
    padding: "9px 16px",
    borderRadius: "8px",
    border: "none",
    backgroundColor: "#dc2626",
    color: "#ffffff",
    cursor: "pointer",
  },
};