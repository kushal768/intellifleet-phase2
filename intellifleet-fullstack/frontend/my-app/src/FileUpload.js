import React, { useState } from "react";
import Papa from "papaparse";
import "./FileUpload.css";

export default function FileUpload({ onUploadSuccess, loading }) {
  const [airFile, setAirFile] = useState(null);
  const [roadFile, setRoadFile] = useState(null);
  const [vehiclesFile, setVehiclesFile] = useState(null);
  const [country, setCountry] = useState("US");
  const [error, setError] = useState("");
  const [uploadProgress, setUploadProgress] = useState(0);

  const validateCSV = (file, requiredCols) =>
    new Promise((resolve, reject) => {
      Papa.parse(file, {
        header: true,
        skipEmptyLines: true,
        preview: 10,
        complete: (results) => {
          const cols = results.meta.fields || [];
          const missing = requiredCols.filter((c) => !cols.includes(c));
          if (missing.length) reject(`Missing columns: ${missing.join(", ")}`);
          else resolve(true);
        },
        error: (err) => reject(err.message || "CSV parse error"),
      });
    });

  const handleFileChange = async (e, type) => {
    const file = e.target.files[0];
    if (!file) {
      setError("No file selected");
      return;
    }
    const requiredAir = [
        "source_airport",
        "destination_airport",
        "lat_src",
        "lon_src",
        "lat_dst",
        "lon_dst",
      ],
      requiredRoad = [
        "source_city",
        "destination_city",
        "lat_src",
        "lon_src",
        "lat_dst",
        "lon_dst",
      ],
      requiredVehicles = [
        "WarehouseName",
        "VehicleType",
        "VehicleCapacity",
        "DepartureTime",
      ];

    // Accept CSV or Excel filenames; we validate CSVs with PapaParse only
    if (file.name.toLowerCase().endsWith(".csv")) {
      try {
        let requiredCols;
        if (type === "air") requiredCols = requiredAir;
        else if (type === "road") requiredCols = requiredRoad;
        else requiredCols = requiredVehicles;
        
        await validateCSV(file, requiredCols);
        if (type === "air") setAirFile(file);
        else if (type === "road") setRoadFile(file);
        else setVehiclesFile(file);
        setError("");
      } catch (errMsg) {
        setError(errMsg);
        if (type === "air") setAirFile(null);
        else if (type === "road") setRoadFile(null);
        else setVehiclesFile(null);
      }
    } else if (
      file.name.toLowerCase().endsWith(".xlsx") ||
      file.type.includes("excel")
    ) {
      // Allow Excel uploads; skip PapaParse validation for .xlsx
      if (type === "air") setAirFile(file);
      else if (type === "road") setRoadFile(file);
      else setVehiclesFile(file);
      setError("");
    } else {
      setError("Please select a .csv or .xlsx file");
    }
  };

  const handleUpload = async () => {
    if (!airFile || !roadFile) {
      setError("Please select both air and road route files");
      return;
    }

    if (!vehiclesFile) {
      setError("Please also select the vehicles CSV file");
      return;
    }

    try {
      setUploadProgress(35);
      
      // Upload routes
      const routeFormData = new FormData();
      routeFormData.append("air", airFile);
      routeFormData.append("road", roadFile);
      routeFormData.append("country", country);

      const routeResponse = await fetch("http://localhost:8000/upload", {
        method: "POST",
        body: routeFormData,
      });

      if (!routeResponse.ok) {
        const errorData = await routeResponse.json();
        throw new Error("Routes upload failed: " + (errorData.detail || "Unknown error"));
      }

      setUploadProgress(70);

      // Upload vehicles
      const vehicleFormData = new FormData();
      vehicleFormData.append("vehicles", vehiclesFile);

      const vehicleResponse = await fetch("http://localhost:8000/upload-vehicles", {
        method: "POST",
        body: vehicleFormData,
      });

      if (!vehicleResponse.ok) {
        const errorData = await vehicleResponse.json();
        throw new Error("Vehicles upload failed: " + (errorData.detail || "Unknown error"));
      }

      const vehicleData = await vehicleResponse.json();
      setUploadProgress(100);

      setTimeout(() => {
        setUploadProgress(0);
        setAirFile(null);
        setRoadFile(null);
        setVehiclesFile(null);
        onUploadSuccess(vehicleData);
      }, 500);
    } catch (err) {
      setError(err.message || "Upload failed. Please check your files.");
      setUploadProgress(0);
    }
  };

  return (
    <div className="file-upload-container">
      <div className="upload-box">
        <h3>Upload Route Data</h3>

        <div className="form-group">
          <label>Country (for fuel pricing)</label>
          <select
            value={country}
            onChange={(e) => setCountry(e.target.value)}
          >
            <option value="US">United States</option>
            <option value="IN">India</option>
            <option value="UK">United Kingdom</option>
            <option value="DE">Germany</option>
            <option value="AU">Australia</option>
          </select>
        </div>

        <div className="form-group">
          <label className="file-label">
            <input
              type="file"
              accept=".csv"
              onChange={(e) => handleFileChange(e, "air")}
              disabled={loading}
            />
            <span className="file-input-text">
              {airFile ? `✓ ${airFile.name}` : "Select Air Routes CSV"}
            </span>
          </label>
        </div>

        <div className="form-group">
          <label className="file-label">
            <input
              type="file"
              accept=".csv"
              onChange={(e) => handleFileChange(e, "road")}
              disabled={loading}
            />
            <span className="file-input-text">
              {roadFile ? `✓ ${roadFile.name}` : "Select Road Routes CSV"}
            </span>
          </label>
        </div>

        <div className="form-group">
          <label className="file-label">
            <input
              type="file"
              accept=".csv"
              onChange={(e) => handleFileChange(e, "vehicles")}
              disabled={loading}
            />
            <span className="file-input-text">
              {vehiclesFile ? `✓ ${vehiclesFile.name}` : "Select Vehicles CSV (vehicles_mapped.csv)"}
            </span>
          </label>
        </div>

        {error && <div className="error-message">{error}</div>}

        <button
          onClick={handleUpload}
          disabled={!airFile || !roadFile || !vehiclesFile || loading}
          className="upload-btn"
        >
          {loading ? "Uploading..." : "Upload Routes & Vehicles"}
        </button>

        {uploadProgress > 0 && (
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{ width: `${uploadProgress}%` }}
            ></div>
          </div>
        )}

        <div className="file-format-info">
          <p>
            <strong>CSV Format Required:</strong>
          </p>
          <p>
            <strong>Air Routes:</strong> source_airport, destination_airport,
            lat_src, lon_src, lat_dst, lon_dst
          </p>
          <p>
            <strong>Road Routes:</strong> source_city, destination_city, lat_src,
            lon_src, lat_dst, lon_dst
          </p>
          <p>
            <strong>Vehicles:</strong> WarehouseName, VehicleType, VehicleCapacity,
            DepartureTime
          </p>
        </div>
      </div>
    </div>
  );
}
