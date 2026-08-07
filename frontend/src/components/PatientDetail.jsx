export default function PatientDetailPage({patient} ) {
  const formattedDate = new Date(patient.birthDate).toLocaleDateString('de-DE', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric'
  });

  return (
    <div className="item-card">
      <div className="item-card-header">
        <h3 className="item-title">Patientendetails</h3>
      </div>
        <p></p>
         <a className="item-url">
          {patient.name}
        </a>
        <p></p>
        <a className="item-url">
          {formattedDate}
        </a>
     
    </div>
  );
}
