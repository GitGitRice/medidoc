import { describe, expect, it } from "vitest";

import { getReturnPath } from "./LoginPage.jsx";

function locationWith(from) {
  return { state: from ? { from } : null };
}

describe("getReturnPath", () => {
  it("führt auf die Startseite, wenn keine Herkunft gemerkt ist", () => {
    expect(getReturnPath(locationWith(null))).toBe("/");
  });

  it("führt auf die ursprünglich gewünschte Seite zurück", () => {
    expect(getReturnPath(locationWith({ pathname: "/patients" }))).toBe(
      "/patients",
    );
  });

  it("behält Query und Fragment", () => {
    const from = { pathname: "/patients", search: "?page=3&q=müller", hash: "#tabelle" };

    expect(getReturnPath(locationWith(from))).toBe(
      "/patients?page=3&q=müller#tabelle",
    );
  });

  it.each([
    ["//fremde.seite/pfad", "protokollrelative Adresse"],
    ["/\\fremde.seite", "Backslash, den manche Browser wie / behandeln"],
    ["https://fremde.seite", "absolute Adresse"],
    ["", "leerer Pfad"],
  ])("leitet nicht nach %s weiter (%s)", (pathname) => {
    expect(getReturnPath(locationWith({ pathname }))).toBe("/");
  });

  it("ignoriert einen Pfad, der kein String ist", () => {
    expect(getReturnPath(locationWith({ pathname: { toString: () => "/" } }))).toBe(
      "/",
    );
  });
});
