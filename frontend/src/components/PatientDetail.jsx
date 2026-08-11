import React from "react";

export default function PatientDetail( { patient } ) {
  const formatDate = (date) => {
    if (!date) return "—";

    const parsedDate = new Date(date);

    if (isNaN(parsedDate.getTime())) return "—";

    return new Intl.DateTimeFormat("de-DE").format(parsedDate);
  };

  const formatDateTime = (date) => {
    if (!date) return "—";

    const parsedDate = new Date(date);

    if (isNaN(parsedDate.getTime())) return "—";

    return new Intl.DateTimeFormat("de-DE", {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: "Europe/Berlin",
    }).format(parsedDate);
  };

  const displayValue = (value) => {
    if (value === null || value === undefined || value === "") {
      return "";
    }
    return value;
  };

  // Fast jedes Feld eines Patienten darf fehlen (docs/patients-api.md) — nur
  // Name und Geburtsdatum nicht. Die Versicherungsart ist dann nicht "privat",
  // sondern unbekannt, und dafuer steht kein Etikett am Kopf.
  const insuranceLabel = {
    statutory: "Gesetzlich versichert",
    private: "Privat versichert",
  }[patient.insurance_type];

  // Die Adresse ist eine Zeile aus drei Feldern, von denen jedes fehlen darf.
  const address = [
    displayValue(patient.street),
    [displayValue(patient.postal_code), displayValue(patient.city)]
      .filter(Boolean)
      .join(" "),
  ]
    .filter(Boolean)
    .join(", ");

  return (
    <div style={styles.patient_page}>
      <section style={styles.patient_card}>
        <div style={styles.patient_header}>
          <div>
            <p style={styles.patient_eyebrow}>PATIENT #{displayValue(patient.id)}</p>
            <h1 style={styles.patient_title}>
              {displayValue(patient.first_name)} {displayValue(patient.last_name)}
            </h1>
            <p style={styles.patient_subtitle}>
              Geboren am {formatDate(patient.date_of_birth)}
            </p>
          </div>

          {insuranceLabel && (
            <span style={styles.patient_badge}>{insuranceLabel}</span>
          )}
        </div>

        <div style={styles.patient_divider} />

        <div style={styles.patient_section}>
          <h2 style={styles.patient_sectionTitle}>Kontaktdaten</h2>

          <div style={styles.patient_grid}>
            {/* Ohne Wert kein Link: `mailto:` und `tel:` ins Leere sehen aus
                wie eine Adresse und sind keine. `InfoField` zeigt dann "—". */}
            <InfoField
              label="E-Mail"
              value={
                patient.email && (
                  <a href={`mailto:${patient.email}`} style={styles.patient_link}>
                    {patient.email}
                  </a>
                )
              }
            />

            <InfoField
              label="Telefon"
              value={
                patient.phone && (
                  <a
                    href={`tel:${patient.phone.replace(/\s/g, "")}`}
                    style={styles.patient_link}
                  >
                    {patient.phone}
                  </a>
                )
              }
            />

            <InfoField label="Adresse" value={address} fullWidth />
          </div>
        </div>

        <div style={styles.patient_section}>
          <h2 style={styles.patient_sectionTitle}>Versicherung</h2>

          <div style={styles.patient_grid}>
            <InfoField
              label="Krankenkasse"
              value={displayValue(patient.insurance_provider)}
            />

            <InfoField
              label="Versicherungsnummer"
              value={displayValue(patient.insurance_number)}
            />
          </div>
        </div>

        <div style={styles.patient_section}>
          <h2 style={styles.patient_sectionTitle}>Notizen</h2>
          <div style={styles.patient_notes}>
            {patient.notes || "Keine Notizen hinterlegt."}
          </div>
        </div>

        <div style={styles.patient_footer}>
          <span>Erstellt: {formatDateTime(patient.created_at)}</span>
          <span>Aktualisiert: {formatDateTime(patient.updated_at)}</span>
        </div>
      </section>
    </div>
  );
}

function InfoField({ label, value, fullWidth = false }) {
  return (
    <div
      style={{
        ...styles.patient_field,
        ...(fullWidth ? styles.patient_fullWidth : {}),
      }}
    >
      <span style={styles.patient_label}>{label}</span>
      <div style={styles.patient_value}>{value || "—"}</div>
    </div>
  );
}

const styles = {
  patient_page: {
    minHeight: "100vh",
    background: "#f4f6f8",
    //padding: "32px",
    fontFamily:
      'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    boxSizing: "border-box",
  },

  patient_card: {
    //width: "50%",
    //minWidth: "520px",
    //maxWidth: "760px",
    background: "#ffffff",
    border: "1px solid #e5e7eb",
    borderRadius: "16px",
    padding: "10px",
    boxSizing: "border-box",
    boxShadow: "0 8px 30px rgba(15, 23, 42, 0.06)",
  },

  patient_header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: "24px",
  },

  patient_eyebrow: {
    margin: "0 0 6px",
    color: "#64748b",
    fontSize: "12px",
    fontWeight: 700,
    letterSpacing: "0.08em",
  },

 patient_title: {
    margin: 0,
    fontSize: "28px",
    lineHeight: 1.2,
    color: "#0f172a",
  },

  patient_subtitle: {
    margin: "8px 0 0",
    color: "#64748b",
    fontSize: "14px",
  },

  patient_badge: {
    background: "#ecfdf5",
    color: "#047857",
    border: "1px solid #a7f3d0",
    borderRadius: "999px",
    padding: "7px 5px",
    fontSize: "12px",
    fontWeight: 700,
    whiteSpace: "nowrap",
  },

  patient_divider: {
    height: "1px",
    background: "#e5e7eb",
    margin: "24px 0",
  },

  patient_section: {
    marginTop: "24px",
  },

  patient_sectionTitle: {
    margin: "0 0 14px",
    fontSize: "15px",
    fontWeight: 700,
    color: "#334155",
  },

  patient_grid: {
    display: "grid",
    gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
    gap: "16px",
  },

  patient_field: {
    background: "#f8fafc",
    borderRadius: "10px",
    padding: "14px",
    minWidth: 0,
  },

  patient_fullWidth: {
    gridColumn: "1 / -1",
  },

  patient_label: {
    display: "block",
    marginBottom: "5px",
    color: "#64748b",
    fontSize: "12px",
    fontWeight: 600,
  },

  patient_value: {
    color: "#0f172a",
    fontSize: "14px",
    fontWeight: 500,
    overflowWrap: "anywhere",
  },

  patient_link: {
    color: "#2563eb",
    textDecoration: "none",
  },

  patient_notes: {
    background: "#fffbea",
    border: "1px solid #fde68a",
    borderRadius: "10px",
    padding: "14px",
    color: "#713f12",
    fontSize: "14px",
    lineHeight: 1.6,
  },

  patient_footer: {
    marginTop: "28px",
    paddingTop: "16px",
    borderTop: "1px solid #e5e7eb",
    display: "flex",
    justifyContent: "space-between",
    gap: "12px",
    flexWrap: "wrap",
    color: "#94a3b8",
    fontSize: "11px",
  },
};