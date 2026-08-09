import { useEffect, useState } from "react";
import InputAdornment from "@mui/material/InputAdornment";
import TextField from "@mui/material/TextField";
import SearchOutlinedIcon from "@mui/icons-material/SearchOutlined";

const DEBOUNCE_MS = 300;

/**
 * Das Suchfeld über der Patiententabelle — rein darstellend.
 *
 * Hält den eingegebenen Text sofort selbst (damit Tippen sich nicht
 * verzögert anfühlt), meldet ihn aber erst entprellt über `onSearch` nach
 * oben. Kennt weder Seiten, Rollen noch Bearbeiten/Löschen/Anlegen — nur den
 * Suchtext.
 */
export function PatientSearch({ onSearch }) {
  const [inputValue, setInputValue] = useState("");

  useEffect(() => {
    const timeout = setTimeout(() => {
      onSearch(inputValue.trim());
    }, DEBOUNCE_MS);

    return () => clearTimeout(timeout);
  }, [inputValue, onSearch]);

  return (
    <TextField
      value={inputValue}
      onChange={(event) => setInputValue(event.target.value)}
      label="Suche nach Name oder Vorname"
      size="small"
      fullWidth
      slotProps={{
        input: {
          startAdornment: (
            <InputAdornment position="start">
              <SearchOutlinedIcon fontSize="small" />
            </InputAdornment>
          ),
        },
      }}
    />
  );
}
