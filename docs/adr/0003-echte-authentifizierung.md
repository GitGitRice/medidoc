# Echte Authentifizierung statt angedeuteter

Authentifizierung war nicht Teil von Modul 3, und für ein Projekt dieser Länge wäre eine
angedeutete Lösung (Login-Maske, fest hinterlegte Benutzer, Session nur im React-Context)
der risikoärmere Weg gewesen. Wir bauen trotzdem echte Auth mit gehashten Passwörtern und
geschützten API-Routen, weil im Team bereits Erfahrung damit aus Modul 2 vorliegt — der
Aufwand ist dadurch abschätzbar und kein offenes Lernrisiko.

## Konsequenzen

- Auth liegt auf dem kritischen Pfad: Alle anderen Arbeitspakete hängen an geschützten
  Endpunkten. Gegenmaßnahme: Entweder steht der Token-Flow bis Dienstag, oder die
  Patienten-Endpunkte werden zunächst ungeschützt gebaut und die Absicherung in einem
  zweiten Durchgang ergänzt.
- Rollen (Arzt / MFA) sind bewusst **nicht** Teil dieser Entscheidung. Sprint 1 kennt nur
  eine Rolle; siehe ADR-0004.
