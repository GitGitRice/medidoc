import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import PersonOffOutlinedIcon from "@mui/icons-material/PersonOffOutlined";
import UndoOutlinedIcon from "@mui/icons-material/UndoOutlined";

/**
 * Die Aktionen-Zelle einer Benutzerzeile — wie `PatientActions`, nur für
 * Benutzer.
 *
 * Genau eine Schaltfläche, und welche, hängt am Zustand: Ein aktiver Benutzer
 * lässt sich deaktivieren, ein deaktivierter zurückholen. Gelöscht wird nie
 * (ADR-0005), deshalb gibt es hier keinen Papierkorb.
 *
 * Die Rückfrage vor dem Deaktivieren stellt `UsersPage` — diese Komponente
 * meldet nur den Klick.
 */
export function UserActions({ user, isSelf, isBusy, selfHint, onDeactivate, onActivate }) {
  const action = user.is_active
    ? {
        tooltip: isSelf ? selfHint : "Benutzer deaktivieren",
        label: `${user.name} deaktivieren`,
        disabled: isSelf || isBusy,
        onClick: () => onDeactivate(user),
        icon: <PersonOffOutlinedIcon fontSize="small" />,
      }
    : {
        tooltip: "Benutzer wieder aktivieren",
        label: `${user.name} wieder aktivieren`,
        disabled: isBusy,
        onClick: () => onActivate(user),
        icon: <UndoOutlinedIcon fontSize="small" />,
      };

  // `justifyContent` gehoert in `sx`: Als eigene Prop nimmt `Stack` es in
  // dieser MUI-Fassung nicht mehr an und reicht es wirkungslos durch.
  return (
    <Stack direction="row" spacing={0.5} sx={{ justifyContent: "flex-end" }}>
      <Tooltip title={action.tooltip}>
        {/* Eine deaktivierte Schaltfläche löst keine Ereignisse aus — ohne das
            umschließende Element bliebe der Tooltip genau dort stumm, wo er die
            Begründung liefern soll. */}
        <span>
          <IconButton
            size="small"
            aria-label={action.label}
            disabled={action.disabled}
            onClick={action.onClick}
          >
            {action.icon}
          </IconButton>
        </span>
      </Tooltip>
    </Stack>
  );
}
