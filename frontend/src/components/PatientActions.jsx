import { useNavigate } from "react-router-dom";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import EditOutlinedIcon from "@mui/icons-material/EditOutlined";
import VisibilityOutlinedIcon from "@mui/icons-material/VisibilityOutlined";

import { useAuth } from "../auth/AuthContext.jsx";

/**
 * Die Aktionen-Zelle einer Patientenzeile: Details und Bearbeiten.
 *
 * Rollen laut ADR-0005: Details sieht jeder angemeldete Benutzer, Bearbeiten
 * `staff` und `admin` (Stammdaten pflegen). Löschen kommt mit #22 dazu.
 */
export function PatientActions({ patient, onEditClick }) {
  const { hasRole } = useAuth();
  const navigate = useNavigate();

  // `justifyContent` gehoert in `sx`: Als eigene Prop nimmt `Stack` es in
  // dieser MUI-Fassung nicht mehr an und reicht es wirkungslos durch.
  return (
    <Stack direction="row" spacing={0.5} sx={{ justifyContent: "flex-end" }}>
      <Tooltip title="Patientendetails öffnen">
        <IconButton
          size="small"
          aria-label="Patientendetails öffnen"
          onClick={(event) => {
            event.stopPropagation();
            navigate(`/patients/${patient.id}`);
          }}
        >
          <VisibilityOutlinedIcon fontSize="small" />
        </IconButton>
      </Tooltip>

      {hasRole("admin", "staff") && (
        <Tooltip title="Patient bearbeiten">
          <IconButton
            size="small"
            aria-label="Patient bearbeiten"
            onClick={(event) => {
              event.stopPropagation();
              onEditClick(patient);
            }}
          >
            <EditOutlinedIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      )}
    </Stack>
  );
}
