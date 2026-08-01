# Der Patient ist die zentrale Einheit, nicht das Dokument

Die ursprüngliche Idee ließ sich auf zwei Arten lesen: als Dokumentenverwaltung, bei der
Dokumente die Arbeitseinheit sind und der Patient nur ein Ordnername, oder als digitale
Patientenakte, bei der der Patient die Arbeitseinheit ist und Dokumente an ihm hängen.
Wir haben uns für die Patientenakte entschieden: Der Einstiegspunkt der Anwendung ist die
Patientenübersicht, `Patient` ist das Wurzelobjekt, und ein `Dokument` gehört immer zu
genau einem Patienten.

## Konsequenzen

- Sprint 1 liefert mit Patientenverwaltung allein bereits eine vollständig nutzbare und
  vorführbare Anwendung. Fällt der Dokumententeil aus, steht trotzdem ein Ergebnis.
- Der Name "MediDoc" beschreibt eher das Ziel als den Stand nach Woche 1. In der
  Präsentation entsprechend einordnen.
