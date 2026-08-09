import { Overview } from "./Overview.jsx";

/**
 * Die Startseite ist die Patientenübersicht.
 *
 * Bis hierher stand darueber noch ein "Angemeldet"-Block mit Name, E-Mail und
 * Rolle — ein Rest aus der Zeit, als die Anmeldung frisch war und man ihr beim
 * Funktionieren zusehen wollte. Wer angemeldet ist, steht jetzt in der
 * Kopfzeile (`Layout.jsx`), also dort, wo es auf jeder Seite gilt und nicht
 * nur auf dieser. Die Uebersicht faengt damit oben an statt unter drei Zeilen
 * Diagnosetext.
 */
export function HomePage() {
  return <Overview />;
}
