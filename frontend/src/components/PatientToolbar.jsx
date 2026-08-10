import Box from "@mui/material/Box";
import Fab from "@mui/material/Fab";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import AddOutlinedIcon from "@mui/icons-material/AddOutlined";

import { PatientSearch } from "./PatientSearch.jsx";

/**
 * Werkzeugleiste über der Patiententabelle: Suche links, Aktionen rechts.
 *
 * Die rechte Seite ist ein `Stack`, kein Einzelknopf — kommt später eine
 * weitere Aktion dazu, reiht sie sich hier ein, ohne dass diese Komponente
 * sich ändern muss.
 */
export function PatientToolbar({ onSearch, onCreateClick, canCreate }) {
  return (
    <Box
      sx={{
        display: "flex",
        flexWrap: "wrap",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 2,
        marginBlockEnd: 2,
      }}
    >
      <PatientSearch onSearch={onSearch} />

      <Stack direction="row" spacing={1} sx={{ marginInlineEnd: 2 }}>
        {canCreate && (
          <Tooltip title="Neuer Patient">
            <Fab
              size="small"
              color="primary"
              aria-label="Neuer Patient"
              onClick={onCreateClick}
              sx={{ width: 32, height: 32, minHeight: 32 }}
            >
              <AddOutlinedIcon sx={{ fontSize: 18 }} />
            </Fab>
          </Tooltip>
        )}
      </Stack>
    </Box>
  );
}
