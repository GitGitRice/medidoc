import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";

/**
 * Die Kopfzeile einer Listenseite: Titel, Anzahl, rechts eine Aktion.
 *
 * Eine Stelle fuer Patienten- und Benutzeruebersicht, die beide dieselbe
 * Kopfzeile brauchen — vorher stand sie zweimal da und ging zweimal gleich
 * daneben.
 *
 * Und zwar so: In dieser MUI-Fassung nimmt `Stack` nur noch `direction`,
 * `spacing`, `divider`, `useFlexGap` und `sx`. `alignItems` und
 * `justifyContent` waren einmal Kurzschreibweisen und sind es nicht mehr —
 * beide wurden also wirkungslos durchgereicht. Die Folge war sichtbar: ohne
 * `justify-content: space-between` klebte die Schaltflaeche direkt an der
 * Ueberschrift statt am rechten Rand, und ohne `align-items` streckte sie sich
 * auf die volle Hoehe der Kopfzeile (62px statt 36px). Deshalb steht das
 * Layout hier in `sx`, wo es ankommt.
 */
export function PageHeader({ title, count, action }) {
  return (
    <Box
      sx={{
        display: "flex",
        flexWrap: "wrap",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 2,
        marginBlockEnd: 3,
      }}
    >
      <Box>
        {/* Layout.jsx traegt bereits <h1>MediDoc</h1> — diese Ueberschrift
            bleibt deshalb h2, keine zweite h1 auf derselben Seite. */}
        <Typography variant="h4" component="h2">
          {title}
        </Typography>
        {count && (
          <Typography variant="body2" color="text.secondary">
            {count}
          </Typography>
        )}
      </Box>
      {action}
    </Box>
  );
}
