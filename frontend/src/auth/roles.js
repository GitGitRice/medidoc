/**
 * Die Rollen, wie sie in der Oberfläche heißen.
 *
 * Im Code und im JSON heißen sie `admin` und `staff` — englisch, so steht es in
 * ADR-0005 und in docs/auth-api.md. Deutsch ist nur, was der Benutzer liest,
 * und "Mitarbeiter" ist auch dort das Wort für `staff`.
 *
 * Eine Stelle für beide Namen: Die Benutzerverwaltung zeigt sie in der Tabelle
 * und im Anlegen-Formular, und beide sollen dasselbe Wort verwenden.
 */
export const ROLES = ["admin", "staff"];

const ROLE_LABELS = {
  admin: "Administrator",
  staff: "Mitarbeiter",
};

/** Der deutsche Name einer Rolle — unbekannte Rollen bleiben, wie sie sind. */
export function roleLabel(role) {
  return ROLE_LABELS[role] ?? role;
}
