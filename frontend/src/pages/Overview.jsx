import { useCallback, useEffect, useState } from "react";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import CircularProgress from "@mui/material/CircularProgress";
import Paper from "@mui/material/Paper";
import Snackbar from "@mui/material/Snackbar";
import Typography from "@mui/material/Typography";

import { jsonBody, patientPath, patientsPath } from "../api.js";
import { useAuth } from "../auth/AuthContext.jsx";
import { PageHeader } from "../components/PageHeader.jsx";
import { PatientFormDialog } from "../components/PatientFormDialog.jsx";
import { PatientSearch } from "../components/PatientSearch.jsx";
import { PatientTable } from "../components/PatientTable.jsx";

export function Overview() {
  const { apiFetch, hasRole } = useAuth();

  const [patients, setPatients] = useState(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [q, setQ] = useState("");
  const [error, setError] = useState(null);

  // Zaehler statt boolean: jede erfolgreiche Aenderung soll die Liste neu
  // holen, auch wenn Seite, Seitengroesse und Suche unveraendert sind.
  const [reloadCount, setReloadCount] = useState(0);
  const [successMessage, setSuccessMessage] = useState(null);

  // Die Tabellenzeile kennt nur `PatientListItem` (id, Name, Geburtsdatum,
  // Versichertennummer) — fuers Bearbeiten fehlen Kontakt-, Adress- und
  // Versicherungsfelder. `editingPatientId` oeffnet den Dialog sofort mit
  // Ladeanzeige, `editPatient` traegt die volle `PatientPublic`-Antwort nach.
  const [editingPatientId, setEditingPatientId] = useState(null);
  const [editPatient, setEditPatient] = useState(null);
  const [isLoadingEditPatient, setIsLoadingEditPatient] = useState(false);
  const [editLoadError, setEditLoadError] = useState(null);
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);

  useEffect(() => {
    const controller = new AbortController();

    setError(null);
    apiFetch(patientsPath({ q, limit: rowsPerPage, offset: page * rowsPerPage }), {
      signal: controller.signal,
    })
      .then((response) => {
        setPatients(response.items);
        setTotal(response.total ?? 0);
      })
      .catch((fetchError) => {
        if (controller.signal.aborted) {
          return;
        }
        setError(fetchError);
      });

    return () => controller.abort();
  }, [apiFetch, q, page, rowsPerPage, reloadCount]);

  useEffect(() => {
    if (editingPatientId === null) {
      return undefined;
    }

    const controller = new AbortController();

    setIsLoadingEditPatient(true);
    apiFetch(patientPath(editingPatientId), { signal: controller.signal })
      .then((patient) => {
        setEditPatient(patient);
        setIsLoadingEditPatient(false);
      })
      .catch((loadError) => {
        if (controller.signal.aborted) {
          return;
        }
        setEditLoadError(loadError.message || "Patient konnte nicht geladen werden.");
        setIsLoadingEditPatient(false);
      });

    return () => controller.abort();
  }, [apiFetch, editingPatientId]);

  function openEditDialog(patient) {
    setEditPatient(null);
    setEditLoadError(null);
    setSaveError(null);
    setEditingPatientId(patient.id);
  }

  function openCreateDialog() {
    setSaveError(null);
    setIsCreateDialogOpen(true);
  }

  function closeFormDialog() {
    if (isSaving) {
      return;
    }
    setEditingPatientId(null);
    setEditPatient(null);
    setEditLoadError(null);
    setIsCreateDialogOpen(false);
    setSaveError(null);
  }

  async function savePatient(payload) {
    if (isSaving) {
      return;
    }

    setIsSaving(true);
    setSaveError(null);

    try {
      if (editingPatientId !== null) {
        await apiFetch(patientPath(editingPatientId), jsonBody("PATCH", payload));
        setSuccessMessage("Patient wurde erfolgreich aktualisiert.");
      } else {
        await apiFetch(patientsPath(), jsonBody("POST", payload));
        setSuccessMessage("Patient wurde erfolgreich angelegt.");
      }
      closeFormDialog();
      setReloadCount((count) => count + 1);
    } catch (saveRequestError) {
      setSaveError(saveRequestError);
    } finally {
      setIsSaving(false);
    }
  }

  function handlePageChange(_event, newPage) {
    setPage(newPage);
  }

  function handleRowsPerPageChange(event) {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  }

  // `useCallback` mit stabiler Identitaet: `PatientSearch` legt seinen
  // Entprellungs-Timer bei jeder Aenderung von `onSearch` neu an. Ohne dies
  // wuerde jeder Overview-Rerender (z. B. weil die Liste laedt) den Timer
  // vorzeitig zuruecksetzen, nicht nur eine echte Eingabe.
  const handleSearch = useCallback((value) => {
    setQ(value);
    setPage(0);
  }, []);

  return (
    <Box>
      <PageHeader
        title="Patientenübersicht"
        count={
          !error && patients !== null
            ? `${total} ${total === 1 ? "Patient" : "Patienten"}`
            : null
        }
        action={
          hasRole("admin", "staff") && (
            <Button variant="contained" onClick={openCreateDialog}>
              Neuer Patient
            </Button>
          )
        }
      />

      <Box sx={{ marginBlockEnd: 2 }}>
        <PatientSearch onSearch={handleSearch} />
      </Box>

      {error && <Alert severity="error">{error.message}</Alert>}

      {!error && patients === null && (
        <Box sx={{ display: "flex", justifyContent: "center", paddingBlock: 6 }}>
          <CircularProgress aria-label="Patienten werden geladen" />
        </Box>
      )}

      {!error && patients !== null && patients.length === 0 && q === "" && (
        <Paper variant="outlined" sx={{ padding: 4, textAlign: "center" }}>
          <Typography variant="h6" component="p">
            Keine Patienten vorhanden
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Es wurden noch keine Patienten angelegt.
          </Typography>
        </Paper>
      )}

      {!error && patients !== null && patients.length === 0 && q !== "" && (
        <Paper variant="outlined" sx={{ padding: 4, textAlign: "center" }}>
          <Typography variant="h6" component="p">
            Keine Treffer
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Für „{q}" wurden keine Patienten gefunden.
          </Typography>
        </Paper>
      )}

      {!error && patients !== null && patients.length > 0 && (
        <PatientTable
          patients={patients}
          total={total}
          page={page}
          rowsPerPage={rowsPerPage}
          onPageChange={handlePageChange}
          onRowsPerPageChange={handleRowsPerPageChange}
          onEditClick={openEditDialog}
        />
      )}

      <PatientFormDialog
        open={editingPatientId !== null || isCreateDialogOpen}
        mode={editingPatientId !== null ? "edit" : "create"}
        patient={editPatient}
        isLoading={isLoadingEditPatient}
        loadError={editLoadError}
        isSaving={isSaving}
        error={saveError}
        onCancel={closeFormDialog}
        onSave={savePatient}
      />

      <Snackbar
        open={successMessage !== null}
        autoHideDuration={4000}
        onClose={() => setSuccessMessage(null)}
      >
        <Alert severity="success" onClose={() => setSuccessMessage(null)}>
          {successMessage}
        </Alert>
      </Snackbar>
    </Box>
  );
}
