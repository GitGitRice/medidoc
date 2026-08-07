export function PatientDetailPage( patient ) {
  return (
    <div>
        <h3>Patientendetails</h3>
        <p></p>
        <h1>{patient.name}</h1>
        <p></p>
        <p>{patient.birthdate} </p>
    </div>
  );
}
