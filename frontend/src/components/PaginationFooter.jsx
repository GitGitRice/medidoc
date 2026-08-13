import TablePagination from "@mui/material/TablePagination";

function paginationItemLabel(type) {
  switch (type) {
    case "first":
      return "Erste Seite";
    case "last":
      return "Letzte Seite";
    case "next":
      return "Nächste Seite";
    case "previous":
      return "Vorherige Seite";
    default:
      return "";
  }
}

/**
 * Die Seitensteuerung unter einer Tabelle, deutsch beschriftet.
 *
 * Eine Stelle für alle Tabellen: Patienten- und Benutzerübersicht paginieren
 * beide über `limit`/`offset` und sollen sich gleich bedienen — stünden die
 * Beschriftungen an jeder Tabelle einzeln, hiesse dieselbe Schaltfläche
 * irgendwann je nach Seite anders.
 */
export function PaginationFooter({
  total,
  page,
  rowsPerPage,
  onPageChange,
  onRowsPerPageChange,
}) {
  return (
    <TablePagination
      component="div"
      count={total}
      page={page}
      onPageChange={onPageChange}
      rowsPerPage={rowsPerPage}
      onRowsPerPageChange={onRowsPerPageChange}
      showFirstButton
      showLastButton
      labelRowsPerPage="Zeilen pro Seite:"
      labelDisplayedRows={({ from, to, count }) => `${from}–${to} von ${count}`}
      getItemAriaLabel={paginationItemLabel}
    />
  );
}
