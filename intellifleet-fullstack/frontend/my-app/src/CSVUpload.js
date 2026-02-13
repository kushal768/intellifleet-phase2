import Papa from "papaparse";

export default function CSVUpload({ onLoad }) {
  const handleUpload = e => {
    const file = e.target.files[0];
    if (!file) {
      alert("No file selected.");
      return;
    }
    Papa.parse(file, {
      header: true,
      skipEmptyLines: true,
      complete: res => {
        if (!res.data || !Array.isArray(res.data) || res.data.length === 0) {
          alert("No data found in CSV file.");
          return;
        }
        // Check for required columns
        const sample = res.data[0];
        if (!sample.airport_code || !sample.city || !sample.lat || !sample.lon) {
          alert("CSV missing required columns: airport_code, city, lat, lon.");
          return;
        }
        onLoad(
          res.data
            .filter(r => r.airport_code)
            .map(r => ({
              city: r.city,
              code: r.airport_code,
              lat: +r.lat,
              lon: +r.lon,
              vehicles_available: +r.vehicles_available,
              country: r.country || null
            }))
        );
      },
      error: err => {
        alert("Failed to parse CSV: " + err.message);
      }
    });
  };

  return (
    <>
      <h3>Upload Airports CSV</h3>
      <input type="file" accept=".csv" onChange={handleUpload} />
    </>
  );
}
