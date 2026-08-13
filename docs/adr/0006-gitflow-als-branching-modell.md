---
status: accepted
---

# Gitflow als Branching-Modell

Wir arbeiten nach **Gitflow**: `main` und `develop` als dauerhafte Branches, ein
`feature/*`-Branch pro Issue, Pull Request nach `develop`.

Das ist der Ablauf, den das Team seit dem ersten Tag lebt (#24 und #25 gingen nach
`develop`) — er stand nur nirgends geschrieben. Der Sprint-1-Plan sagte an zwei Stellen
noch "Pull Request nach `main`". Diese ADR hält fest, was gilt, und die Stellen sind
angeglichen.

## Die Branches

| Branch | Bedeutung | Wer darf hineinschreiben |
| ------ | --------- | ------------------------ |
| `main` | Der vorführbare Stand. Was hier liegt, läuft. | niemand direkt — nur Merge aus `develop` |
| `develop` | Integration. Hier treffen die vier Stränge aufeinander. | niemand direkt — nur Merge aus `feature/*` |
| `feature/<issue>-<kurzname>` | Ein Issue, ein Branch, z. B. `feature/14-auth-login` | die Person, die das Issue bearbeitet |

Kein direkter Push auf `main` oder `develop` — auch nicht "nur schnell die README".

## Warum das und nicht Trunk-Based

Trunk-Based Development wäre bei vier Leuten und zwei Wochen die schlankere Wahl und
braucht weniger Merges. Der Ausschlag geht trotzdem an Gitflow, aus zwei Gründen:

1. **`main` bleibt jederzeit vorführbar.** Bei einem Kursprojekt mit
   Abschlusspräsentation ist genau das der Wert: Es gibt immer einen Stand, den man
   ohne Nachfragen zeigen kann, während auf `develop` noch etwas halb fertig ist.
2. **Gitflow ist Lehrplaninhalt.** Wir sollen zeigen, dass wir mit Branches, Pull
   Requests und Reviews arbeiten können. Ein Modell, das jeder im Team benennen kann,
   ist hier mehr wert als eines, das ein paar Merges spart.

## Was wir bewusst weglassen

`release/*` und `hotfix/*` gehören zum vollständigen Gitflow, wir benutzen sie **nicht**.
Bei zwei Sprints à einer Woche gibt es nichts zu stabilisieren, was ein eigener Branch
besser könnte als `develop` selbst, und einen Produktivstand, der einen Hotfix bräuchte,
gibt es nicht. Ein Release ist bei uns ein Merge `develop → main` am Ende eines Sprints.

Wer später doch einen braucht: Die Namen sind reserviert, das Vorgehen ist Standard.

## Konsequenzen

- Ein Issue = ein Branch = ein Pull Request. Der Branchname trägt die Issue-Nummer,
  damit im Nachhinein nachvollziehbar ist, woher eine Änderung kam.
- Jeder Pull Request wird von einem anderen Teammitglied angeschaut, bevor er nach
  `develop` geht — die Regel aus dem Sprint-1-Plan bleibt unverändert, nur das Ziel ist
  `develop` statt `main`.
- Am Ende eines Sprints wandert `develop` nach `main`. Wer präsentiert, checkt `main`
  aus.
- Die Definition of Done im Sprint-1-Plan sagt "auf `main` gemerged" — gemeint und
  gültig ist `develop`.
