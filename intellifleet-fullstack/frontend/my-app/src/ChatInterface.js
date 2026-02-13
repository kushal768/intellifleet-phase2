import React, { useState, useRef, useEffect } from "react";
import "./ChatInterface.css";

export default function ChatInterface({ onRouteUpdate, loading }) {
  const [messages, setMessages] = useState([
    { type: "bot", text: "👋 Welcome! Ask me for a route optimization. For example:\n• 'What's the cheapest route from Mumbai to Delhi?'\n• 'Find the fastest route from London to Frankfurt for 5000 kg of goods'" }
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [lastCsvData, setLastCsvData] = useState(null);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim()) return;

    const userMsg = input.trim();
    setInput("");
    setMessages(prev => [...prev, { type: "user", text: userMsg }]);
    setIsLoading(true);

    try {
      const response = await fetch(
        `http://localhost:8000/chat?message=${encodeURIComponent(userMsg)}`,
        { method: "POST" }
      );

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || "Request failed");
      }

      const data = await response.json();
      console.log("Chat API response:", data);
      const botReply = data.explanation || "Route optimized successfully.";
      
      // Extract vehicle info if capacity plan is available
      let vehicleInfo = null;
      if (data.capacity_plan && data.capacity_plan.legs) {
        vehicleInfo = data.capacity_plan.legs.map(leg => ({
          from: leg.from,
          to: leg.to,
          vehicles: leg.vehicles || []
        }));
      }
      
      setMessages(prev => [...prev, { 
        type: "bot", 
        text: botReply,
        tableData: data.table_data,
        csvData: data.csv_download,
        vehicleInfo: vehicleInfo
      }]);
      
      setLastCsvData(data.csv_download);
      console.log("Calling onRouteUpdate with route:", data.route);
      onRouteUpdate(data.route);
    } catch (error) {
      setMessages(prev => [...prev, { type: "bot", text: `❌ Error: ${error.message}` }]);
    } finally {
      setIsLoading(false);
    }
  };

  const downloadCsv = (csvData) => {
    const link = document.createElement("a");
    link.href = csvData.link;
    link.download = csvData.filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="chat-interface">
      {/* Header */}
      <div className="chat-header">
        <div className="chat-header-content">
          <h2>Route Optimizer</h2>
          <p>Find the best logistics path</p>
        </div>
      </div>

      {/* Messages Container */}
      <div className="chat-messages">
        {messages.map((msg, idx) => (
          <div key={idx} className={`message message-${msg.type}`}>
            <div className="message-bubble">
              {msg.text}
              
              {/* Table Display */}
              {msg.tableData && msg.tableData.length > 0 && (
                <div className="route-table">
                  <table>
                    <thead>
                      <tr>
                        <th>Step</th>
                        <th>From</th>
                        <th>To</th>
                        <th>Mode</th>
                        <th>Distance (km)</th>
                        <th>Time (hrs)</th>
                        <th>Cost (USD)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {msg.tableData.map((row, i) => (
                        <tr key={i}>
                          <td>{row.step}</td>
                          <td>{row.from}</td>
                          <td>{row.to}</td>
                          <td className={`mode-${row.mode.toLowerCase()}`}>{row.mode}</td>
                          <td>{row.distance_km}</td>
                          <td>{row.time_hours}</td>
                          <td>${row.fuel_cost_usd}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  
                  {msg.csvData && (
                    <button 
                      className="csv-download-btn"
                      onClick={() => downloadCsv(msg.csvData)}
                    >
                      📥 Download CSV
                    </button>
                  )}
                </div>
              )}

              {/* Vehicle Capacity Info Display */}
              {msg.vehicleInfo && msg.vehicleInfo.length > 0 && (
                <div className="vehicle-info">
                  <h4>🚚 Vehicle Assignment Details</h4>
                  {msg.vehicleInfo.map((legInfo, legIdx) => (
                    <details key={legIdx} className="vehicle-leg">
                      <summary>
                        Leg {legIdx + 1}: {legInfo.from} → {legInfo.to}
                      </summary>
                      <ul>
                        {legInfo.vehicles.map((vehicle, vIdx) => (
                          <li key={vIdx}>
                            <strong>{vehicle.vehicle_id}</strong>
                            <br />
                            Load: {vehicle.load_kg} kg | Departure: {vehicle.departure} | Arrival: {vehicle.arrival}
                            <br />
                            Distance: {vehicle.distance} km | Cost: ${vehicle.fuel_cost}
                          </li>
                        ))}
                      </ul>
                    </details>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="message message-bot">
            <div className="message-bubble loading">
              <span className="dot"></span>
              <span className="dot"></span>
              <span className="dot"></span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="chat-input-wrapper">
        <div className="chat-input-container">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={(e) => e.key === "Enter" && handleSend()}
            placeholder="Ask for a route optimization..."
            disabled={isLoading}
            className="chat-input"
          />
          <button
            onClick={handleSend}
            disabled={isLoading || !input.trim()}
            className="chat-send-btn"
          >
            {isLoading ? "..." : "→"}
          </button>
        </div>
      </div>
    </div>
  );
}
