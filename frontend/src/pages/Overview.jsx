import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { patientsPath } from "../api.js";
import { useAuth } from "../auth/AuthContext.jsx";

/**
 * `date_of_birth` kommt als reines `"JJJJ-MM-TT"` vom Backend. `new Date(...)`
 * würde das als UTC-Mitternacht lesen und je nach Zeitzone einen Tag daneben
 * liegen — deshalb wird hier nur umsortiert, nicht geparst.
 */
function formatDate(isoDate) {
  const [year, month, day] = isoDate.split("-");
  return `${day}.${month}.${year}`;
}

export function Overview() {
  const { apiFetch } = useAuth();
  const navigate = useNavigate();
  const [patients, setPatients] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    const controller = new AbortController();

    setError(null);
    apiFetch(patientsPath(), { signal: controller.signal })
      .then((page) => setPatients(page.items))
      .catch((fetchError) => {
        if (controller.signal.aborted) {
          return;
        }
        setError(fetchError);
      });

    return () => controller.abort();
  }, [apiFetch]);

  if (error) {
    return (
      <p className="error" role="alert">
        {error.message}
      </p>
    );
  }

  if (patients === null) {
    return <p aria-live="polite">Patienten werden geladen …</p>;
  }

  if (patients.length === 0) {
    return <p>Es sind noch keine Patienten angelegt.</p>;
  }

  return (
    <table>
      <thead>
        <tr>
          <th>Name</th>
          <th>Vorname</th>
          <th>Geburtsdatum</th>
          <th>Versicherung</th>
        </tr>
      </thead>
      <tbody>
        {patients.map((patient) => (
          <tr
            key={patient.id}
            onClick={() => navigate(`/patients/${patient.id}`)}
            style={{ cursor: "pointer" }}
          >
            <td>{patient.last_name}</td>
            <td>{patient.first_name}</td>
            <td>{formatDate(patient.date_of_birth)}</td>
            <td>{patient.insurance_number ?? "–"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
