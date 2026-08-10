import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import CssBaseline from "@mui/material/CssBaseline";
import { ThemeProvider } from "@mui/material/styles";

import { App } from "./App.jsx";
import { AuthProvider } from "./auth/AuthContext.jsx";
import { theme } from "./theme.js";
import "./styles.css";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    {/* `CssBaseline` gehoert unter den `ThemeProvider` und ueber alles andere:
        Es setzt die Grundlinie (Schrift, Randabstaende, Kastenmodell) fuer
        Browser-Elemente und MUI-Bausteine gleichermassen. Ohne diese beiden
        Zeilen zeichnete MUI bisher gegen die Voreinstellungen des Browsers an. */}
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <BrowserRouter>
        <AuthProvider>
          <App />
        </AuthProvider>
      </BrowserRouter>
    </ThemeProvider>
  </StrictMode>,
);
