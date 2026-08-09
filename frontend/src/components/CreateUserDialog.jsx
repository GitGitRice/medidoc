import { useState } from "react";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogContentText from "@mui/material/DialogContentText";
import DialogTitle from "@mui/material/DialogTitle";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";

import { ROLES, roleLabel } from "../auth/roles.js";

/**
 * Das Formular zum Anlegen eines Benutzers.
 *
 * Prüft selbst nur, was der Browser ohnehin prüft (Pflichtfelder, E-Mail-Form).
 * Alles Weitere — vergebene E-Mail, zu langes Passwort — entscheidet das
 * Backend, und seine Meldung steht danach hier im Dialog: Der Dialog bleibt
 * dabei offen, damit die Eingabe nicht verloren geht und korrigiert werden
 * kann.
 *
 * `onCreate` gibt ein Promise zurück; wird es abgelehnt, ist das der Fehlerfall.
 */
export function CreateUserDialog({ open, onClose, onCreate }) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("staff");
  const [error, setError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      await onCreate({ name, email, password, role });
    } catch (createError) {
      setError(createError);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    // `xs` statt `sm`: Vier einspaltige Felder in 600px Breite lassen den
    // Dialog leer wirken. 444px sind so breit, wie das Formular lang ist.
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="xs">
      <Box component="form" onSubmit={handleSubmit} aria-busy={isSubmitting}>
        <DialogTitle sx={{ paddingBlockEnd: 1 }}>Benutzer anlegen</DialogTitle>
        <DialogContent>
          <DialogContentText variant="body2" sx={{ marginBlockEnd: 3 }}>
            Der neue Benutzer kann sich sofort mit dieser E-Mail und diesem
            Passwort anmelden.
          </DialogContentText>

          {/* `paddingBlockStart`: `DialogContent` schneidet oben ab, und die
              hochgestellte Beschriftung des ersten Feldes sitzt genau dort. */}
          <Stack spacing={2.5} sx={{ paddingBlockStart: 0.5 }}>
            {error && <Alert severity="error">{error.message}</Alert>}

            <TextField
              label="Name"
              required
              autoFocus
              fullWidth
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
            <TextField
              label="E-Mail"
              type="email"
              required
              fullWidth
              autoComplete="off"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
            <TextField
              label="Passwort"
              type="password"
              required
              fullWidth
              // `new-password`, sonst bietet der Browser die Zugangsdaten der
              // angemeldeten Person an — hier wird ein fremdes Konto angelegt.
              autoComplete="new-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
            {/* Als `TextField` wie die drei Felder darueber, statt als
                `FormControl` + `InputLabel` + `Select` von Hand
                zusammengesetzt: Sonst sitzt die Beschriftung "Rolle" anders
                als "Name", "E-Mail" und "Passwort" — sichtbar im Dialog, in
                dem sie als einzige schon oben klebte, bevor etwas eingegeben
                war. `native` bleibt: Die Rolle ist eine Auswahl aus zwei
                Werten, dafuer genuegt das Feld des Browsers, das mit Tastatur
                und Vorlesesoftware ohne Zutun bedienbar ist. */}
            <TextField
              select
              slotProps={{ select: { native: true } }}
              label="Rolle"
              fullWidth
              value={role}
              onChange={(event) => setRole(event.target.value)}
              helperText="Administratoren dürfen zusätzlich Benutzer verwalten."
            >
              {ROLES.map((value) => (
                <option key={value} value={value}>
                  {roleLabel(value)}
                </option>
              ))}
            </TextField>
          </Stack>
        </DialogContent>
        <DialogActions sx={{ paddingInline: 3, paddingBlockEnd: 2.5 }}>
          <Button type="button" onClick={onClose} disabled={isSubmitting}>
            Abbrechen
          </Button>
          <Button
            type="submit"
            variant="contained"
            disableElevation
            disabled={isSubmitting}
          >
            {isSubmitting ? "Wird angelegt …" : "Anlegen"}
          </Button>
        </DialogActions>
      </Box>
    </Dialog>
  );
}
