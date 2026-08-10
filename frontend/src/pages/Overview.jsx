import { useCallback, useEffect, useState } from "react";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import CircularProgress from "@mui/material/CircularProgress";
import Paper from "@mui/material/Paper";
import Typography from "@mui/material/Typography";

import { patientsPath } from "../api.js";
import { useAuth } from "../auth/AuthContext.jsx";
import { PageHeader } from "../components/PageHeader.jsx";
import { PatientSearch } from "../components/PatientSearch.jsx";
import { PatientTable } from "../components/PatientTable.jsx";

export function Overview() {
  const { apiFetch } = useAuth();

  const [patients, setPatients] = useState(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [q, setQ] = useState("");
  const [error, setError] = useState(null);

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
  }, [apiFetch, q, page, rowsPerPage]);

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
      {/* Ohne Aktion: "Neuer Patient" ist bewusst nicht gerendert, weil es
          weder eine Route (/patients/new) noch einen api.js-Aufruf dafuer
          gibt. Der Weg zur Benutzerverwaltung (#54) steht jetzt in der
          Navigation in `Layout.jsx` — er fuehrt woanders hin und ist damit
          keine Aktion auf dieser Liste. */}
      <PageHeader
        title="Patientenübersicht"
        count={
          !error && patients !== null
            ? `${total} ${total === 1 ? "Patient" : "Patienten"}`
            : null
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
        />
      )}
    </Box>
  );
}
