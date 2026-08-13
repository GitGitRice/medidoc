import { createTheme } from "@mui/material/styles";

/**
 * Das Aussehen der Anwendung an einer Stelle.
 *
 * Vorher gab es kein Theme: MUI rechnete mit seinen Voreinstellungen, die
 * handgeschriebenen Regeln in `styles.css` mit ihren eigenen, und wer gewann,
 * entschied die Spezifität des Selektors. Ein Theme macht daraus eine
 * Entscheidung statt eines Zufalls.
 */
export const theme = createTheme({
  typography: {
    // MUI verlangt ohne Zutun Roboto. Die Schrift wird hier aber nirgends
    // geladen — der Browser fiel deshalb auf eine beliebige Ersatzschrift
    // zurueck. Benannt wird darum das, was tatsaechlich da ist.
    fontFamily:
      '"Inter", system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    h4: { fontWeight: 600, letterSpacing: "-0.015em" },
    h6: { fontWeight: 600 },
  },
  shape: {
    borderRadius: 8,
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          // Ohne diese Zeile schreibt MUI jede Schaltflaeche in Grossbuchstaben.
          // Bei deutschen Komposita wird daraus eine Wand: "BENUTZERVERWALTUNG"
          // liest sich deutlich schlechter als "Benutzerverwaltung".
          textTransform: "none",
          fontWeight: 500,
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        head: { fontWeight: 600 },
      },
    },
  },
});
