import Chip from "@mui/material/Chip";
import Paper from "@mui/material/Paper";
import Select from "@mui/material/Select";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";

import { ROLES, roleLabel } from "../auth/roles.js";
import { PaginationFooter } from "./PaginationFooter.jsx";
import { UserActions } from "./UserActions.jsx";

/**
 * Warum am eigenen Konto nichts zu ändern ist.
 *
 * Dieselbe Regel wie im Backend, das ein Deaktivieren oder Herabstufen des
 * eigenen Kontos mit `409` ablehnt (users/router.py). Hier steht sie nur, damit
 * der Weg nicht erst in einer Fehlermeldung endet — durchgesetzt wird sie
 * weiterhin dort.
 */
const SELF_HINT = "Das eigene Konto lässt sich nicht sperren oder herabstufen";

/**
 * Die Benutzertabelle — rein darstellend.
 *
 * Holt nichts nach und ändert nichts selbst: Jede Aktion geht als Aufruf nach
 * oben, `UsersPage` spricht mit dem Backend. Anders als in `PatientTable` ist
 * die Zeile nicht klickbar — es gibt keine Benutzerdetailseite, und ein
 * Zeilenklick käme den Bedienelementen in der Zeile nur in die Quere.
 */
export function UserTable({
  users,
  total,
  page,
  rowsPerPage,
  onPageChange,
  onRowsPerPageChange,
  currentUserId,
  busyUserId,
  onRoleChange,
  onDeactivate,
  onActivate,
}) {
  return (
    <Paper variant="outlined">
      <TableContainer>
        {/* `minWidth`, damit `TableContainer` auf schmalen Fenstern schiebt
            statt zu quetschen: Ohne die Angabe schrumpfte die Rollenauswahl
            auf ihren Pfeil zusammen und war nicht mehr lesbar. */}
        <Table size="medium" sx={{ minWidth: 720 }}>
          <TableHead>
            <TableRow sx={{ backgroundColor: "action.hover" }}>
              <TableCell sx={{ fontWeight: 500 }}>Name</TableCell>
              <TableCell sx={{ fontWeight: 500 }}>E-Mail</TableCell>
              <TableCell sx={{ fontWeight: 500, width: 200 }}>Rolle</TableCell>
              <TableCell sx={{ fontWeight: 500 }}>Status</TableCell>
              <TableCell
                align="right"
                sx={{ fontWeight: 500, width: 192, whiteSpace: "nowrap" }}
              >
                Aktionen
              </TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {users.map((user) => {
              const isSelf = user.id === currentUserId;
              const isBusy = user.id === busyUserId;

              return (
                <TableRow key={user.id} hover>
                  <TableCell>
                    {user.name}
                    {isSelf && (
                      <Typography
                        component="span"
                        variant="body2"
                        color="text.secondary"
                      >
                        {" (du)"}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>{user.email}</TableCell>
                  <TableCell>
                    <Tooltip title={isSelf ? SELF_HINT : ""}>
                      {/* Ein deaktiviertes Feld löst keine Ereignisse aus —
                          ohne dieses Element bliebe der Tooltip stumm. */}
                      <span>
                        <Select
                          // Ein echtes <select>: Die Rolle ist eine Auswahl aus
                          // zwei Werten, dafür braucht es kein aufklappendes
                          // Menü — und mit Tastatur und Vorlesesoftware ist das
                          // native Feld ohne Zutun bedienbar.
                          native
                          size="small"
                          fullWidth
                          value={user.role}
                          disabled={isSelf || isBusy}
                          onChange={(event) =>
                            onRoleChange(user, event.target.value)
                          }
                          inputProps={{ "aria-label": `Rolle von ${user.name}` }}
                        >
                          {ROLES.map((role) => (
                            <option key={role} value={role}>
                              {roleLabel(role)}
                            </option>
                          ))}
                        </Select>
                      </span>
                    </Tooltip>
                  </TableCell>
                  <TableCell>
                    <Chip
                      size="small"
                      variant="outlined"
                      color={user.is_active ? "success" : "default"}
                      label={user.is_active ? "Aktiv" : "Deaktiviert"}
                    />
                  </TableCell>
                  <TableCell align="right" sx={{ whiteSpace: "nowrap" }}>
                    <UserActions
                      user={user}
                      isSelf={isSelf}
                      isBusy={isBusy}
                      selfHint={SELF_HINT}
                      onDeactivate={onDeactivate}
                      onActivate={onActivate}
                    />
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>
      <PaginationFooter
        total={total}
        page={page}
        rowsPerPage={rowsPerPage}
        onPageChange={onPageChange}
        onRowsPerPageChange={onRowsPerPageChange}
      />
    </Paper>
  );
}
