import { NavLink, Outlet, Link } from "react-router-dom";
import AppBar from "@mui/material/AppBar";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Container from "@mui/material/Container";
import Toolbar from "@mui/material/Toolbar";
import Typography from "@mui/material/Typography";

import { useAuth } from "./auth/AuthContext.jsx";
import { roleLabel } from "./auth/roles.js";

/**
 * Wie ein Navigationspunkt aussieht, wenn er die aktuelle Seite ist.
 *
 * `NavLink` setzt dafuer von sich aus die Klasse `active` — die Markierung
 * haengt also am Router und nicht an einer zweiten Buchfuehrung darueber, wo
 * man gerade ist.
 */
const navLinkStyles = {
  color: "text.secondary",
  paddingInline: 1.5,
  "&.active": {
    color: "text.primary",
    backgroundColor: "action.selected",
  },
};

/** Kopfzeile und Navigation, gemeinsam für alle angemeldeten Seiten — #16. */
export function Layout() {
  const { logout, user, hasRole } = useAuth();

  return (
    <Box sx={{ minHeight: "100dvh", backgroundColor: "background.default" }}>
      {/* `color="inherit"` und keine Schattenkante: Die Kopfzeile soll die
          Tabellen darunter tragen, nicht mit ihnen um Aufmerksamkeit ringen. */}
      <AppBar
        position="static"
        color="inherit"
        elevation={0}
        sx={{ borderBottom: 1, borderColor: "divider" }}
      >
        <Container maxWidth="lg" disableGutters>
          <Toolbar
            disableGutters
            sx={{ gap: 2, paddingInline: 2, flexWrap: "wrap" }}
          >
            <Typography
              variant="h6"
              component="h1"
              sx={{ letterSpacing: "-0.02em", marginInlineEnd: 1 }}
            >
              MediDoc
            </Typography>

            {/* Beide Ziele stehen nebeneinander in der Navigation, weil beide
                Navigation sind. Die Benutzerverwaltung stand vorher als
                Schaltflaeche neben der Ueberschrift der Patientenuebersicht
                und sah damit aus wie eine Aktion *auf* dieser Liste.

                Ausblenden bleibt Bedienkomfort: Durchgesetzt wird die Rolle
                von `RoleRoute` und vom Backend. */}
            {/* Auf schmalen Fenstern rutscht die Navigation in die zweite
                Zeile — `order` schickt sie hinter "Abmelden", sonst braeche
                die Kopfzeile in drei Zeilen auseinander und die
                Abmelden-Schaltflaeche staende allein in der dritten. */}
            <Box
              component="nav"
              sx={{
                display: "flex",
                gap: 0.5,
                order: { xs: 1, sm: 0 },
                width: { xs: "100%", sm: "auto" },
                paddingBlockEnd: { xs: 1, sm: 0 },
              }}
            >
              <Button component={NavLink} to="/" end sx={navLinkStyles}>
                Patientenübersicht
              </Button>
              {hasRole("admin") && (
                <Button component={NavLink} to="/users" sx={navLinkStyles}>
                  Benutzerverwaltung
                </Button>
              )}
            </Box>

            <Box sx={{ flexGrow: 1 }} />

            {/* Wer angemeldet ist und womit — vorher stand das als
                "Angemeldet"-Block mitten im Seiteninhalt und schob die
                eigentliche Ueberschrift nach unten. Auf schmalen Fenstern
                weicht es, die Abmelden-Schaltflaeche bleibt. */}
            {user && (
              <Typography
                variant="body2"
                color="text.secondary"
                sx={{ display: { xs: "none", sm: "block" } }}
              >
                <Box component="span" sx={{ color: "text.primary", fontWeight: 500 }}>
                  {user.name}
                </Box>
                {` · ${roleLabel(user.role)}`}
              </Typography>
            )}

            <Button variant="outlined" color="inherit" onClick={logout}>
              Abmelden
            </Button>
          </Toolbar>
        </Container>
      </AppBar>

      <Container maxWidth="lg" component="main" sx={{ paddingBlock: 4 }}>
        <Outlet />
      </Container>
    </Box>
  );
}
