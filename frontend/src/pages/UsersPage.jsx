import { useEffect, useState } from "react";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import CircularProgress from "@mui/material/CircularProgress";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogContentText from "@mui/material/DialogContentText";
import DialogTitle from "@mui/material/DialogTitle";
import PersonAddAlt1OutlinedIcon from "@mui/icons-material/PersonAddAlt1Outlined";

import { jsonBody, userPath, usersPath } from "../api.js";
import { useAuth } from "../auth/AuthContext.jsx";
import { roleLabel } from "../auth/roles.js";
import { CreateUserDialog } from "../components/CreateUserDialog.jsx";
import { PageHeader } from "../components/PageHeader.jsx";
import { UserTable } from "../components/UserTable.jsx";

/**
 * Die Benutzerverwaltung — Issue #54, nur für `admin`.
 *
 * Aufgebaut wie die Patientenübersicht (`Overview.jsx`): dieselbe Kopfzeile,
 * dieselbe Tabelle mit Seitensteuerung, dieselbe Behandlung von Ladezustand und
 * Fehler. Die Rolle prüft `RoleRoute` vor dieser Seite — hier steht deshalb
 * keine zweite Prüfung, wohl aber die Regel, dass am eigenen Konto nichts
 * gesperrt oder herabgestuft wird (siehe `UserTable`).
 *
 * Kein Löschen: Ein Benutzer wird deaktiviert, nie entfernt (ADR-0005).
 */
export function UsersPage() {
  const { apiFetch, user: currentUser } = useAuth();

  const [users, setUsers] = useState(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [error, setError] = useState(null);
  // Getrennt vom Ladefehler: Eine misslungene Änderung darf die Tabelle nicht
  // gegen eine Fehlermeldung austauschen — die Liste stimmt ja noch.
  const [actionError, setActionError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [busyUserId, setBusyUserId] = useState(null);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [pendingDeactivation, setPendingDeactivation] = useState(null);
  // Hochgezählt, wenn ein neuer Benutzer dazukommt — dann muss die Seite neu
  // geholt werden, weil sich Sortierung und Gesamtzahl ändern.
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    const controller = new AbortController();

    setError(null);
    apiFetch(usersPath({ limit: rowsPerPage, offset: page * rowsPerPage }), {
      signal: controller.signal,
    })
      .then((response) => {
        setUsers(response.items);
        setTotal(response.total ?? 0);
      })
      .catch((fetchError) => {
        if (controller.signal.aborted) {
          return;
        }
        setError(fetchError);
      });

    return () => controller.abort();
  }, [apiFetch, page, rowsPerPage, reloadToken]);

  function handlePageChange(_event, newPage) {
    setPage(newPage);
  }

  function handleRowsPerPageChange(event) {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  }

  /**
   * Ändert einen Benutzer und setzt die Antwort an die Stelle der alten Zeile.
   *
   * `PATCH` gibt den ganzen Benutzer zurück, deshalb wird die Liste nicht neu
   * geholt: Die Tabelle bliebe sonst kurz auf dem alten Stand oder sprünge auf
   * Seite 1 zurück. Ein Fehler landet in `actionError` und bleibt sichtbar,
   * statt still verschluckt zu werden.
   */
  async function patchUser(target, changes) {
    setActionError(null);
    setNotice(null);
    setBusyUserId(target.id);

    try {
      const updated = await apiFetch(
        userPath(target.id),
        jsonBody("PATCH", changes),
      );
      setUsers((current) =>
        current.map((user) => (user.id === updated.id ? updated : user)),
      );
      return updated;
    } catch (patchError) {
      setActionError(patchError);
      return null;
    } finally {
      setBusyUserId(null);
    }
  }

  async function handleRoleChange(user, role) {
    const updated = await patchUser(user, { role });
    if (updated) {
      setNotice(`${updated.name} ist jetzt ${roleLabel(updated.role)}.`);
    }
  }

  async function handleActivate(user) {
    const updated = await patchUser(user, { is_active: true });
    if (updated) {
      setNotice(`${updated.name} kann sich wieder anmelden.`);
    }
  }

  async function confirmDeactivation() {
    const target = pendingDeactivation;
    setPendingDeactivation(null);

    const updated = await patchUser(target, { is_active: false });
    if (updated) {
      setNotice(`${updated.name} kann sich nicht mehr anmelden.`);
    }
  }

  async function handleCreate(data) {
    // Kein `catch`: Ein Fehler gehört in den Dialog, damit die Eingabe stehen
    // bleibt — `CreateUserDialog` fängt ihn und zeigt die Meldung des Backends.
    const created = await apiFetch(usersPath(), jsonBody("POST", data));

    setIsCreateOpen(false);
    setActionError(null);
    setNotice(`${created.name} wurde angelegt.`);
    setReloadToken((token) => token + 1);
  }

  return (
    <Box>
      {/* "Benutzer" ist im Plural dasselbe Wort — anders als bei den
          Patienten braucht es hier keine Fallunterscheidung. */}
      <PageHeader
        title="Benutzerverwaltung"
        count={!error && users !== null ? `${total} Benutzer` : null}
        action={
          <Button
            variant="contained"
            disableElevation
            startIcon={<PersonAddAlt1OutlinedIcon />}
            onClick={() => setIsCreateOpen(true)}
          >
            Benutzer anlegen
          </Button>
        }
      />

      {error && <Alert severity="error">{error.message}</Alert>}

      {actionError && (
        <Alert
          severity="error"
          onClose={() => setActionError(null)}
          sx={{ marginBlockEnd: 2 }}
        >
          {actionError.message}
        </Alert>
      )}

      {notice && (
        <Alert
          severity="success"
          onClose={() => setNotice(null)}
          sx={{ marginBlockEnd: 2 }}
        >
          {notice}
        </Alert>
      )}

      {!error && users === null && (
        <Box sx={{ display: "flex", justifyContent: "center", paddingBlock: 6 }}>
          <CircularProgress aria-label="Benutzer werden geladen" />
        </Box>
      )}

      {/* Kein Leer-Zustand wie in der Patientenübersicht: Wer diese Seite sieht,
          ist angemeldet und steht damit selbst in der Liste. */}
      {!error && users !== null && users.length > 0 && (
        <UserTable
          users={users}
          total={total}
          page={page}
          rowsPerPage={rowsPerPage}
          onPageChange={handlePageChange}
          onRowsPerPageChange={handleRowsPerPageChange}
          currentUserId={currentUser?.id}
          busyUserId={busyUserId}
          onRoleChange={handleRoleChange}
          onDeactivate={setPendingDeactivation}
          onActivate={handleActivate}
        />
      )}

      {isCreateOpen && (
        <CreateUserDialog
          open
          onClose={() => setIsCreateOpen(false)}
          onCreate={handleCreate}
        />
      )}

      <Dialog
        open={pendingDeactivation !== null}
        onClose={() => setPendingDeactivation(null)}
      >
        <DialogTitle>Benutzer deaktivieren?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            {pendingDeactivation?.name} kann sich danach nicht mehr anmelden. Das
            Konto bleibt erhalten und lässt sich hier wieder aktivieren.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPendingDeactivation(null)}>Abbrechen</Button>
          <Button color="error" variant="contained" onClick={confirmDeactivation}>
            Deaktivieren
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
