import { useEffect, useState } from "react";
import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import CircularProgress from "@mui/material/CircularProgress";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import MenuItem from "@mui/material/MenuItem";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";

const EMPTY_FORM = {
  first_name: "",
  last_name: "",
  date_of_birth: "",
  email: "",
  phone: "",
  street: "",
  postal_code: "",
  city: "",
  insurance_provider: "",
  insurance_number: "",
  insurance_type: "",
  notes: "",
};

// Optionale Felder, die beim Speichern leer bleiben koennen.
const OPTIONAL_FIELDS = [
  "email",
  "phone",
  "street",
  "postal_code",
  "city",
  "insurance_provider",
  "insurance_number",
  "insurance_type",
  "notes",
];

function formFromPatient(patient) {
  const form = { ...EMPTY_FORM };
  for (const field of Object.keys(EMPTY_FORM)) {
    form[field] = patient[field] ?? "";
  }
  return form;
}

/**
 * Formularwerte → Anlegen-/Änderungs-Rumpf.
 *
 * Ein geleertes optionales Feld heißt "löschen", nicht "leerer String" —
 * sonst zeigt die Übersicht später `""` statt `"–"` (vgl. `Overview.jsx`s
 * `insurance_number ?? "–"`).
 */
function toPayload(form) {
  const payload = {
    first_name: form.first_name.trim(),
    last_name: form.last_name.trim(),
    date_of_birth: form.date_of_birth,
  };
  for (const field of OPTIONAL_FIELDS) {
    const value = form[field].trim();
    payload[field] = value === "" ? null : value;
  }
  return payload;
}

function validate(form) {
  const errors = {};

  if (!form.first_name.trim()) {
    errors.first_name = "darf nicht leer sein";
  }
  if (!form.last_name.trim()) {
    errors.last_name = "darf nicht leer sein";
  }
  if (!form.date_of_birth) {
    errors.date_of_birth = "Feld ist erforderlich";
  } else if (form.date_of_birth > new Date().toISOString().slice(0, 10)) {
    errors.date_of_birth = "darf nicht in der Zukunft liegen";
  }

  return errors;
}

/** `{field: message}` aus der `errors`-Liste einer `422`-Antwort (app/core/errors.py). */
function serverFieldErrors(error) {
  if (!error?.errors) {
    return {};
  }
  return Object.fromEntries(error.errors.map((entry) => [entry.field, entry.message]));
}

/**
 * Das Formular für Anlegen und Bearbeiten eines Patienten — dasselbe
 * Formular für beide, nur `mode` ("create" | "edit") unterscheidet sie
 * (Issue #21).
 *
 * Kontrolliert wie `DeletePatientDialog`: `open` steuert Sichtbarkeit, alle
 * Netzwerkaufrufe (Nachladen der vollen Daten beim Bearbeiten, Speichern)
 * macht `Overview.jsx`. Im Bearbeiten-Modus kommt `patient` als volle
 * `PatientPublic`-Form an — die Zeile in der Tabelle kennt nur die schmale
 * `PatientListItem`-Form (id, Name, Geburtsdatum, Versichertennummer), das
 * reicht für ein Bearbeitungsformular nicht. Im Anlegen-Modus gibt es kein
 * Nachladen, das Formular startet leer.
 */
export function PatientFormDialog({
  open,
  mode,
  patient,
  isLoading,
  loadError,
  isSaving,
  error,
  onCancel,
  onSave,
}) {
  const [form, setForm] = useState(EMPTY_FORM);
  // Welche Felder wurden schon verlassen — steuert, ob ein Client-Fehler
  // schon angezeigt wird. Ohne das waere z. B. "Neuer Patient" beim Oeffnen
  // sofort voller roter Pflichtfelder, bevor der Nutzer ueberhaupt etwas
  // eingegeben hat.
  const [touched, setTouched] = useState({});

  useEffect(() => {
    if (mode === "edit" && patient) {
      setForm(formFromPatient(patient));
      setTouched({});
    }
    if (mode === "create" && open) {
      setForm(EMPTY_FORM);
      setTouched({});
    }
  }, [mode, patient, open]);

  function handleChange(field) {
    return (event) => {
      setForm((current) => ({ ...current, [field]: event.target.value }));
    };
  }

  function handleBlur(field) {
    return () => {
      setTouched((current) => ({ ...current, [field]: true }));
    };
  }

  // Live statt nur bei Submit: Pflichtfelder sind bei jedem Tastendruck
  // geprueft, damit der Speichern-Button sofort reagiert, wenn ein Pflichtfeld
  // geleert wird — nicht erst nach einem Absendeversuch.
  const clientErrors = validate(form);
  const hasClientErrors = Object.keys(clientErrors).length > 0;
  const serverErrors = serverFieldErrors(error);
  // Server-Fehler gelten unabhaengig von `touched` sofort — Client-Fehler nur
  // fuer Felder, die der Nutzer schon verlassen hat.
  const fieldErrors = { ...clientErrors };
  for (const field of Object.keys(fieldErrors)) {
    if (!touched[field]) {
      delete fieldErrors[field];
    }
  }
  Object.assign(fieldErrors, serverErrors);
  const showForm = mode === "create" || (!isLoading && !loadError && patient !== null);
  const saveDisabled = isSaving || !showForm || hasClientErrors;

  const title =
    mode === "create"
      ? "Patient anlegen"
      : `Patient bearbeiten${patient ? ` – ${patient.first_name} ${patient.last_name}` : ""}`;
  const saveLabel = mode === "create" ? "Patient anlegen" : "Änderungen speichern";
  const savingLabel = mode === "create" ? "Wird angelegt …" : "Wird gespeichert …";

  function handleSubmit(event) {
    event.preventDefault();

    // Zweite Sicherung neben dem deaktivierten Button — falls das Formular
    // trotzdem abgeschickt wird (z. B. Enter im letzten Feld), bevor der
    // Button-Zustand nachzieht.
    if (saveDisabled) {
      return;
    }

    onSave(toPayload(form));
  }

  return (
    <Dialog open={open} onClose={isSaving ? undefined : onCancel} fullWidth maxWidth="sm">
      <DialogTitle>{title}</DialogTitle>
      <form onSubmit={handleSubmit}>
        <DialogContent>
          {mode === "edit" && isLoading && (
            <Stack alignItems="center" sx={{ paddingBlock: 4 }}>
              <CircularProgress aria-label="Patientendaten werden geladen" />
            </Stack>
          )}

          {mode === "edit" && !isLoading && loadError && (
            <Alert severity="error">{loadError}</Alert>
          )}

          {showForm && (
            <Stack spacing={2} sx={{ paddingBlockStart: 1 }}>
              {error && <Alert severity="error">{error.message}</Alert>}

              <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
                <TextField
                  label="Vorname"
                  value={form.first_name}
                  onChange={handleChange("first_name")}
                  onBlur={handleBlur("first_name")}
                  required
                  fullWidth
                  error={Boolean(fieldErrors.first_name)}
                  helperText={fieldErrors.first_name}
                  disabled={isSaving}
                />
                <TextField
                  label="Nachname"
                  value={form.last_name}
                  onChange={handleChange("last_name")}
                  onBlur={handleBlur("last_name")}
                  required
                  fullWidth
                  error={Boolean(fieldErrors.last_name)}
                  helperText={fieldErrors.last_name}
                  disabled={isSaving}
                />
              </Stack>

              <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
                <TextField
                  label="Geburtsdatum"
                  type="date"
                  value={form.date_of_birth}
                  onChange={handleChange("date_of_birth")}
                  onBlur={handleBlur("date_of_birth")}
                  required
                  fullWidth
                  slotProps={{ inputLabel: { shrink: true } }}
                  error={Boolean(fieldErrors.date_of_birth)}
                  helperText={fieldErrors.date_of_birth}
                  disabled={isSaving}
                />
                <TextField
                  label="E-Mail"
                  value={form.email}
                  onChange={handleChange("email")}
                  onBlur={handleBlur("email")}
                  fullWidth
                  error={Boolean(fieldErrors.email)}
                  helperText={fieldErrors.email}
                  disabled={isSaving}
                />
              </Stack>

              <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
                <TextField
                  label="Telefon"
                  value={form.phone}
                  onChange={handleChange("phone")}
                  onBlur={handleBlur("phone")}
                  fullWidth
                  error={Boolean(fieldErrors.phone)}
                  helperText={fieldErrors.phone}
                  disabled={isSaving}
                />
                <TextField
                  label="Straße"
                  value={form.street}
                  onChange={handleChange("street")}
                  onBlur={handleBlur("street")}
                  fullWidth
                  error={Boolean(fieldErrors.street)}
                  helperText={fieldErrors.street}
                  disabled={isSaving}
                />
              </Stack>

              <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
                <TextField
                  label="PLZ"
                  value={form.postal_code}
                  onChange={handleChange("postal_code")}
                  onBlur={handleBlur("postal_code")}
                  fullWidth
                  error={Boolean(fieldErrors.postal_code)}
                  helperText={fieldErrors.postal_code}
                  disabled={isSaving}
                />
                <TextField
                  label="Ort"
                  value={form.city}
                  onChange={handleChange("city")}
                  onBlur={handleBlur("city")}
                  fullWidth
                  error={Boolean(fieldErrors.city)}
                  helperText={fieldErrors.city}
                  disabled={isSaving}
                />
              </Stack>

              <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
                <TextField
                  label="Versicherungsträger"
                  value={form.insurance_provider}
                  onChange={handleChange("insurance_provider")}
                  onBlur={handleBlur("insurance_provider")}
                  fullWidth
                  error={Boolean(fieldErrors.insurance_provider)}
                  helperText={fieldErrors.insurance_provider}
                  disabled={isSaving}
                />
                <TextField
                  label="Versichertennummer"
                  value={form.insurance_number}
                  onChange={handleChange("insurance_number")}
                  onBlur={handleBlur("insurance_number")}
                  fullWidth
                  error={Boolean(fieldErrors.insurance_number)}
                  helperText={fieldErrors.insurance_number}
                  disabled={isSaving}
                />
              </Stack>

              <TextField
                label="Versicherungsart"
                select
                value={form.insurance_type}
                onChange={handleChange("insurance_type")}
                onBlur={handleBlur("insurance_type")}
                error={Boolean(fieldErrors.insurance_type)}
                helperText={fieldErrors.insurance_type}
                disabled={isSaving}
                sx={{ maxInlineSize: { sm: "50%" } }}
              >
                <MenuItem value="">Keine Angabe</MenuItem>
                <MenuItem value="statutory">Gesetzlich</MenuItem>
                <MenuItem value="private">Privat</MenuItem>
              </TextField>

              <TextField
                label="Notizen"
                value={form.notes}
                onChange={handleChange("notes")}
                onBlur={handleBlur("notes")}
                multiline
                minRows={3}
                fullWidth
                error={Boolean(fieldErrors.notes)}
                helperText={fieldErrors.notes}
                disabled={isSaving}
              />
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          <Button type="button" onClick={onCancel} disabled={isSaving}>
            Abbrechen
          </Button>
          <Button type="submit" variant="contained" disabled={saveDisabled}>
            {isSaving ? savingLabel : saveLabel}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}
