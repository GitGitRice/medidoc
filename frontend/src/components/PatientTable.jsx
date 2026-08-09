import { useNavigate } from "react-router-dom";
import Paper from "@mui/material/Paper";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TablePagination from "@mui/material/TablePagination";
import TableRow from "@mui/material/TableRow";

import { PatientActions } from "./PatientActions.jsx";

/**
 * `date_of_birth` kommt als reines `"JJJJ-MM-TT"` vom Backend. `new Date(...)`
 * würde das als UTC-Mitternacht lesen und je nach Zeitzone einen Tag daneben
 * liegen — deshalb wird hier nur umsortiert, nicht geparst.
 */
function formatDate(isoDate) {
  const [year, month, day] = isoDate.split("-");
  return `${day}.${month}.${year}`;
}

function paginationItemLabel(type) {
  switch (type) {
    case "first":
      return "Erste Seite";
    case "last":
      return "Letzte Seite";
    case "next":
      return "Nächste Seite";
    case "previous":
      return "Vorherige Seite";
    default:
      return "";
  }
}

/**
 * Die Patiententabelle selbst — rein darstellend.
 *
 * Holt nichts nach; bekommt Daten und Seitensteuerung ausschließlich über
 * Props. `PatientActions` zeigt aktuell nur den Details-Button, ohne
 * Rollenprüfung. Der Zeilenklick navigiert direkt, genau wie der
 * Details-Button in `PatientActions` es für sich schon tut — kein
 * zusätzlicher `onRowClick` als Umweg über `Overview.jsx`.
 */
export function PatientTable({
  patients,
  total,
  page,
  rowsPerPage,
  onPageChange,
  onRowsPerPageChange,
}) {
  const navigate = useNavigate();

  return (
    <Paper variant="outlined">
      <TableContainer>
        <Table size="medium">
          <TableHead>
            <TableRow sx={{ backgroundColor: "action.hover" }}>
              <TableCell sx={{ fontWeight: 500 }}>Nachname</TableCell>
              <TableCell sx={{ fontWeight: 500 }}>Vorname</TableCell>
              <TableCell sx={{ fontWeight: 500 }}>Geburtsdatum</TableCell>
              <TableCell sx={{ fontWeight: 500 }}>Versicherung</TableCell>
              <TableCell
                align="right"
                sx={{ fontWeight: 500, width: 192, whiteSpace: "nowrap" }}
              >
                Aktionen
              </TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {patients.map((patient) => (
              <TableRow
                key={patient.id}
                hover
                onClick={() => navigate(`/patients/${patient.id}`)}
                sx={{ cursor: "pointer" }}
              >
                <TableCell>{patient.last_name}</TableCell>
                <TableCell>{patient.first_name}</TableCell>
                <TableCell>{formatDate(patient.date_of_birth)}</TableCell>
                <TableCell>{patient.insurance_number ?? "–"}</TableCell>
                <TableCell align="right" sx={{ whiteSpace: "nowrap" }}>
                  <PatientActions patient={patient} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
      <TablePagination
        component="div"
        count={total}
        page={page}
        onPageChange={onPageChange}
        rowsPerPage={rowsPerPage}
        onRowsPerPageChange={onRowsPerPageChange}
        showFirstButton
        showLastButton
        labelRowsPerPage="Zeilen pro Seite:"
        labelDisplayedRows={({ from, to, count }) => `${from}–${to} von ${count}`}
        getItemAriaLabel={paginationItemLabel}
      />
    </Paper>
  );
}
