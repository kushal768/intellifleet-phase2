import React, { useEffect, useMemo, useState } from "react";
import { MapContainer, TileLayer, Polyline, Marker, useMap, Popup, CircleMarker } from "react-leaflet";
import L from "leaflet";
import "./MapView.css";

function MapUpdater({ route, defaultCenter, defaultZoom, minZoom }) {
  const map = useMap();

  useEffect(() => {
    const refresh = () => {
      // small delay helps Leaflet compute correct size
      setTimeout(() => {
        try { map.invalidateSize(); } catch {}
      }, 100);
    };

    // initial refresh and on resize
    refresh();
    window.addEventListener("resize", refresh);

    if (route && route.length) {
      const latlngs = route
        .filter(seg => seg.geometry && seg.geometry.length > 0)
        .flatMap(seg => seg.geometry.map(([lat, lon]) => [lat, lon]));
      
      if (latlngs.length) {
        try {
          map.fitBounds(latlngs, { padding: [40, 40] });
        } catch {
          map.setView(defaultCenter, defaultZoom);
        }
      } else {
        map.setView(defaultCenter, defaultZoom);
      }
    } else {
      map.setView(defaultCenter, defaultZoom);
      if (typeof minZoom === "number") map.setMinZoom(minZoom);
    }

    return () => window.removeEventListener("resize", refresh);
  }, [map, route, defaultCenter, defaultZoom, minZoom]);

  return null;
}

export default function MapView({
  route = null,
  loading = false,
  defaultCenter = [20, 0],
  defaultZoom = 2,
  minZoom = 1
}) {
  const [center, setCenter] = useState(defaultCenter);
  const [zoom, setZoom] = useState(defaultZoom);

  // Log route for debugging
  useEffect(() => {
    if (route) {
      console.log("MapView received route:", route);
    }
  }, [route]);

  useEffect(() => {
    if (route && route.length > 0) {
      // Calculate center point from all route points
      let lats = [];
      let lons = [];
      
      route.forEach(segment => {
        if (segment.geometry && segment.geometry.length > 0) {
          segment.geometry.forEach(point => {
            lats.push(point[0]);
            lons.push(point[1]);
          });
        }
      });

      if (lats.length > 0) {
        const centerLat = (Math.max(...lats) + Math.min(...lats)) / 2;
        const centerLon = (Math.max(...lons) + Math.min(...lons)) / 2;
        setCenter([centerLat, centerLon]);
        setZoom(6);
      }
    }
  }, [route]);

  const getLineOptions = (mode) => {
    return {
      color: mode === "air" ? "#22c55e" : "#3b82f6",
      weight: mode === "air" ? 3 : 4,
      opacity: 0.8,
      dashArray: mode === "air" ? "5, 10" : "0",
    };
  };

  const getMarkerColor = (isStart, isEnd) => {
    if (isStart) return "#ef4444";
    if (isEnd) return "#16a34a";
    return "#f59e0b";
  };

  // Get start and end points
  let startPoint = null;
  let endPoint = null;
  let waypoints = [];

  if (route && route.length > 0) {
    // Find first segment with geometry or coordinates
    const firstSeg = route.find(seg => (seg.geometry && seg.geometry.length > 0) || (seg.lat_src && seg.lon_src));
    if (firstSeg) {
      startPoint = firstSeg.geometry ? firstSeg.geometry[0] : [firstSeg.lat_src, firstSeg.lon_src];
    }
    
    // Find last segment with geometry or coordinates
    const lastSeg = route[route.length - 1];
    if (lastSeg) {
      endPoint = (lastSeg.geometry && lastSeg.geometry.length > 0) 
        ? lastSeg.geometry[lastSeg.geometry.length - 1]
        : (lastSeg.lat_dst && lastSeg.lon_dst) 
          ? [lastSeg.lat_dst, lastSeg.lon_dst]
          : null;
    }
    
    // Collect waypoints where routes connect
    for (let i = 0; i < route.length - 1; i++) {
      const currentSeg = route[i];
      const point = (currentSeg.geometry && currentSeg.geometry.length > 0)
        ? currentSeg.geometry[currentSeg.geometry.length - 1]
        : (currentSeg.lat_dst && currentSeg.lon_dst)
          ? [currentSeg.lat_dst, currentSeg.lon_dst]
          : null;
      
      if (point) {
        waypoints.push({
          point: point,
          from: currentSeg.from,
          to: currentSeg.to,
          mode: currentSeg.mode,
        });
      }
    }
  }

  // Build polylines/markers only when route exists
  const lines = useMemo(() => {
    if (!route || !route.length) return [];
    return route
      .filter(seg => seg.geometry && seg.geometry.length > 0)
      .map(seg => seg.geometry.map(([lat, lon]) => [lat, lon]));
  }, [route]);

  const startMarker = useMemo(() => {
    if (!route || !route.length) return null;
    const firstSeg = route.find(seg => (seg.geometry && seg.geometry.length > 0) || (seg.lat_src && seg.lon_src));
    if (!firstSeg) return null;
    const first = firstSeg.geometry ? firstSeg.geometry[0] : [firstSeg.lat_src, firstSeg.lon_src];
    return [first[0], first[1]];
  }, [route]);

  const endMarker = useMemo(() => {
    if (!route || !route.length) return null;
    const lastSeg = route[route.length - 1];
    if (!lastSeg) return null;
    const last = (lastSeg.geometry && lastSeg.geometry.length > 0)
      ? lastSeg.geometry[lastSeg.geometry.length - 1]
      : (lastSeg.lat_dst && lastSeg.lon_dst)
        ? [lastSeg.lat_dst, lastSeg.lon_dst]
        : null;
    return last ? [last[0], last[1]] : null;
  }, [route]);

  return (
    <div className="map-container-wrapper">
      {loading && <div className="map-loading">Loading route...</div>}
      <div id="map" style={{ height: "100%", width: "100%" }}>
        <MapContainer
          center={defaultCenter}
          zoom={defaultZoom}
          style={{ height: "100%", width: "100%" }}
          scrollWheelZoom={true}
          preferCanvas={true}
          whenReady={mapInstance => { setTimeout(() => mapInstance.target.invalidateSize(), 100); }}
        >
          <TileLayer
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            noWrap={true}
          />

          <MapUpdater route={route} defaultCenter={defaultCenter} defaultZoom={defaultZoom} minZoom={minZoom} />

          {/* Route polylines */}
          {route && route.length > 0 ? (
            route.map((segment, idx) => {
              console.log(`Rendering segment ${idx}:`, segment);
              
              // Handle segments with geometry
              if (segment.geometry && segment.geometry.length > 0) {
                console.log(`Segment ${idx} has geometry:`, segment.geometry);
                return (
                  <Polyline
                    key={`route-${idx}`}
                    positions={segment.geometry}
                    {...getLineOptions(segment.mode)}
                    opacity={0.7}
                  >
                    <Popup>
                      <div>
                        <strong>
                          {segment.from} → {segment.to}
                        </strong>
                        <br />
                        Mode: <strong>{segment.mode.toUpperCase()}</strong>
                        <br />
                        Distance: {segment.distance} km
                        <br />
                        Time: {segment.time} hours
                        <br />
                        Fuel Cost: ${segment.fuel}
                      </div>
                    </Popup>
                  </Polyline>
                );
              }
              
              // Handle segments with lat/lon coordinates but no geometry
              if (segment.lat_src && segment.lon_src && segment.lat_dst && segment.lon_dst) {
                console.log(`Segment ${idx} using lat/lon fallback`);
                return (
                  <Polyline
                    key={`route-${idx}`}
                    positions={[[segment.lat_src, segment.lon_src], [segment.lat_dst, segment.lon_dst]]}
                    {...getLineOptions(segment.mode)}
                    opacity={0.7}
                  >
                    <Popup>
                      <div>
                        <strong>
                          {segment.from} → {segment.to}
                        </strong>
                        <br />
                        Mode: <strong>{segment.mode.toUpperCase()}</strong>
                        <br />
                        Distance: {segment.distance} km
                        <br />
                        Time: {segment.time} hours
                        <br />
                        Fuel Cost: ${segment.fuel}
                      </div>
                    </Popup>
                  </Polyline>
                );
              }
              
              console.log(`Segment ${idx} skipped - no geometry or lat/lon:`, segment);
              return null;
            })
          ) : null}

          {/* Start point marker */}
          {startPoint && route && route.length > 0 && (
            <CircleMarker center={startPoint} radius={8} fillColor="#ef4444" color="#c41e3a" weight={2} opacity={1} fillOpacity={0.8}>
              <Popup>
                <div>
                  <strong>Start</strong>
                  <br />
                  {route[0] && route[0].from}
                </div>
              </Popup>
            </CircleMarker>
          )}

          {/* Waypoint markers */}
          {waypoints.map((wp, idx) => (
            <CircleMarker key={`waypoint-${idx}`} center={wp.point} radius={6} fillColor="#f59e0b" color="#d97706" weight={1.5} opacity={1} fillOpacity={0.8}>
              <Popup>
                <div>
                  <strong>{wp.from}</strong> (via point)
                  <br />
                  Mode: {wp.mode.toUpperCase()}
                </div>
              </Popup>
            </CircleMarker>
          ))}

          {/* End point marker */}
          {endPoint && route && route.length > 0 && (
            <CircleMarker center={endPoint} radius={8} fillColor="#16a34a" color="#15803d" weight={2} opacity={1} fillOpacity={0.8}>
              <Popup>
                <div>
                  <strong>End</strong>
                  <br />
                  {route[route.length - 1] && route[route.length - 1].to}
                </div>
              </Popup>
            </CircleMarker>
          )}
        </MapContainer>
      </div>

      {/* Legend */}
      <div className="map-legend">
        <div className="legend-item">
          <div className="legend-color" style={{ borderTop: "3px solid #22c55e", borderBottom: "3px dashed #22c55e" }}></div>
          <span>Air Routes</span>
        </div>
        <div className="legend-item">
          <div className="legend-color" style={{ borderTop: "3px solid #3b82f6", borderBottom: "3px solid #3b82f6" }}></div>
          <span>Road Routes</span>
        </div>
        <div className="legend-item">
          <div className="legend-circle" style={{ backgroundColor: "#ef4444" }}></div>
          <span>Start</span>
        </div>
        <div className="legend-item">
          <div className="legend-circle" style={{ backgroundColor: "#16a34a" }}></div>
          <span>End</span>
        </div>
        <div className="legend-item">
          <div className="legend-circle" style={{ backgroundColor: "#f59e0b" }}></div>
          <span>Waypoint</span>
        </div>
      </div>
    </div>
  );
}
