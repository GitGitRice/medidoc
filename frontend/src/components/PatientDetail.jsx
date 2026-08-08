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
  return (
    <div style={styles.page}>
      <section style={styles.card}>
        <div style={styles.header}>
          <div>
            <p style={styles.eyebrow}>PATIENT #{patient.id}</p>
            <h1 style={styles.title}>
              {patient.first_name} {patient.last_name}
            </h1>
            <p style={styles.subtitle}>
              Geboren am {formatDate(patient.date_of_birth)}
            </p>
          </div>

          <span style={styles.badge}>
            {patient.insurance_type === "statutory"
              ? "Gesetzlich versichert"
              : "Privat versichert"}
          </span>
        </div>

        <div style={styles.divider} />

        <div style={styles.section}>
          <h2 style={styles.sectionTitle}>Kontaktdaten</h2>

          <div style={styles.grid}>
            <InfoField
              label="E-Mail"
              value={
                <a href={`mailto:${patient.email}`} style={styles.link}>
                  {patient.email}
                </a>
              }
            />

            <InfoField
              label="Telefon"
              value={
                <a
                  href={`tel:${patient.phone.replace(/\s/g, "")}`}
                  style={styles.link}
                >
                  {patient.phone}
                </a>
              }
            />

            <InfoField
              label="Adresse"
              value={`${patient.street}, ${patient.postal_code} ${patient.city}`}
              fullWidth
            />
          </div>
        </div>

        <div style={styles.section}>
          <h2 style={styles.sectionTitle}>Versicherung</h2>

          <div style={styles.grid}>
            <InfoField
              label="Krankenkasse"
              value={patient.insurance_provider}
            />

            <InfoField
              label="Versicherungsnummer"
              value={patient.insurance_number}
            />
          </div>
        </div>

        <div style={styles.section}>
          <h2 style={styles.sectionTitle}>Notizen</h2>
          <div style={styles.notes}>{patient.notes}</div>
        </div>

        <div style={styles.footer}>
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
        ...styles.field,
        ...(fullWidth ? styles.fullWidth : {}),
      }}
    >
      <span style={styles.label}>{label}</span>
      <div style={styles.value}>{value || "—"}</div>
    </div>
  );
}

const styles = {
  page: {
    minHeight: "100vh",
    background: "#f4f6f8",
    //padding: "32px",
    fontFamily:
      'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    boxSizing: "border-box",
  },

  card: {
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

  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: "24px",
  },

  eyebrow: {
    margin: "0 0 6px",
    color: "#64748b",
    fontSize: "12px",
    fontWeight: 700,
    letterSpacing: "0.08em",
  },

  title: {
    margin: 0,
    fontSize: "28px",
    lineHeight: 1.2,
    color: "#0f172a",
  },

  subtitle: {
    margin: "8px 0 0",
    color: "#64748b",
    fontSize: "14px",
  },

  badge: {
    background: "#ecfdf5",
    color: "#047857",
    border: "1px solid #a7f3d0",
    borderRadius: "999px",
    padding: "7px 5px",
    fontSize: "12px",
    fontWeight: 700,
    whiteSpace: "nowrap",
  },

  divider: {
    height: "1px",
    background: "#e5e7eb",
    margin: "24px 0",
  },

  section: {
    marginTop: "24px",
  },

  sectionTitle: {
    margin: "0 0 14px",
    fontSize: "15px",
    fontWeight: 700,
    color: "#334155",
  },

  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
    gap: "16px",
  },

  field: {
    background: "#f8fafc",
    borderRadius: "10px",
    padding: "14px",
    minWidth: 0,
  },

  fullWidth: {
    gridColumn: "1 / -1",
  },

  label: {
    display: "block",
    marginBottom: "5px",
    color: "#64748b",
    fontSize: "12px",
    fontWeight: 600,
  },

  value: {
    color: "#0f172a",
    fontSize: "14px",
    fontWeight: 500,
    overflowWrap: "anywhere",
  },

  link: {
    color: "#2563eb",
    textDecoration: "none",
  },

  notes: {
    background: "#fffbea",
    border: "1px solid #fde68a",
    borderRadius: "10px",
    padding: "14px",
    color: "#713f12",
    fontSize: "14px",
    lineHeight: 1.6,
  },

  footer: {
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