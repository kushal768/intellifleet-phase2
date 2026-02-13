import React, { useState, useEffect } from "react";
import FileUpload from "./FileUpload";
import ChatInterface from "./ChatInterface";
import MapView from "./MapView";
import "./App.css";
import 'leaflet/dist/leaflet.css';

export default function App() {
  const [currentRoute, setCurrentRoute] = useState(null);
  const [uploadSuccess, setUploadSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleUploadSuccess = (data) => {
        setUploadSuccess(true);
    setLoading(false);
  };

  const handleRouteUpdate = (route) => {
    setCurrentRoute(route);
  };

  return (
    <div className="app-container">
      {!uploadSuccess ? (
        <FileUpload onUploadSuccess={handleUploadSuccess} loading={loading} />
      ) : (
        <div className="main-layout">
          {/* Chat panel on the left now */}
          <div className="chat-panel">
            <ChatInterface onRouteUpdate={handleRouteUpdate} loading={loading} />
          </div>

          {/* Map panel on the right */}
          <div className="map-panel">
            <MapView
              route={currentRoute}
              loading={loading}
              defaultCenter={[20, 0]}    // world-centered
              defaultZoom={2}            // zoomed out world view
              minZoom={1}
            />
          </div>
        </div>
      )}
    </div>
  );
}

