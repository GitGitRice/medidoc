import { useNavigate } from "react-router-dom";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import VisibilityOutlinedIcon from "@mui/icons-material/VisibilityOutlined";

/**
 * Die Aktionen-Zelle einer Patientenzeile.
 *
 * Aktuell nur Details — jeder angemeldete Benutzer darf Patientendaten
 * einsehen (ADR-0005). Bearbeiten und Löschen kommen mit #21/#22 dazu.
 */
export function PatientActions({ patient }) {
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
    </Stack>
  );
}
