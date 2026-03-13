import React, { useState, useRef, useEffect } from "react";
import "./ChatInterface.css";

export default function ChatInterface({ onRouteUpdate, loading }) {
  const [messages, setMessages] = useState([
    { type: "bot", text: "👋 Welcome! Ask me for a route optimization. For example:\n• 'What's the cheapest route from Mumbai to Delhi?'\n• 'Find the fastest route from London to Frankfurt for 5000 kg of goods'\n\n🚨 I can also help with disruptions:\n• 'Route from Delhi to Mumbai with 1000kg disrupted at 10pm, needs delivery by 10am, repair time 5 hours'" }
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
      // Check if this is a disruption query
      const isDisruption = /disrupt|repair|divert|disrupted|cannot reach|unable to reach/i.test(userMsg);
      
      if (isDisruption) {
        // Parse disruption query
        const disruptionResult = parseDisruptionQuery(userMsg);
        console.log("Parsed disruption query:", disruptionResult);
        
        if (disruptionResult.valid) {
          // Call disruption endpoint
          try {
            const response = await fetch("http://localhost:8000/handle-disruption", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                source_warehouse: disruptionResult.source,
                destination_city: disruptionResult.destination,
                demand_kg: disruptionResult.demandKg,
                disruption_time: disruptionResult.disruptionTime || "22:00",
                required_delivery_time: disruptionResult.requiredTime || "10:00",
                repair_hours: disruptionResult.repairHours || 5,
                disruption_location: disruptionResult.disruptionLocation || null
              })
            });

            if (!response.ok) {
              const err = await response.json();
              throw new Error(err.detail || `HTTP ${response.status}: Disruption handling failed`);
            }

            const data = await response.json();
            console.log("Disruption response:", data);
            
            // Format disruption response
            let botReply = `🚨 Disruption Analysis\n\n`;
            botReply += `Source: ${data.original_route?.source || disruptionResult.source}\n`;
            botReply += `Destination: ${data.original_route?.destination || disruptionResult.destination}\n`;
            botReply += `Disruption Time: ${data.disruption_time}\n`;
            botReply += `Repair Duration: ${data.repair_duration_hours} hours\n`;
            botReply += `Demand: ${data.demand_weight_kg} kg\n\n`;
            
            if (data.recommendation === "PROCEED_WITH_REPAIR") {
              botReply += `✅ RECOMMENDATION: PROCEED WITH REPAIR\n\n`;
              botReply += `${data.message}\n`;
            } else if (data.recommendation === "DIVERT_TO_WAREHOUSE") {
              botReply += `📍 RECOMMENDATION: DIVERT TO ALTERNATIVE WAREHOUSE\n\n`;
              botReply += `${data.message}\n\n`;
              botReply += `Warehouse Details:\n`;
              botReply += `- Name: ${data.recommended_warehouse_name}\n`;
              botReply += `- City: ${data.recommended_warehouse}\n`;
              botReply += `- Estimated Delivery: ${data.estimated_delivery_time}\n`;
            } else if (data.recommendation === "DIVERT_TO_MULTIPLE_WAREHOUSES") {
              botReply += `🚚 RECOMMENDATION: USE MULTIPLE WAREHOUSES\n\n`;
              botReply += `${data.message}\n\n`;
              
              // Show dual warehouse details
              if (data.warehouse_combinations && data.warehouse_combinations.length > 0) {
                const combo = data.warehouse_combinations[0];
                botReply += `Warehouse 1 Details:\n`;
                botReply += `- Name: ${combo.warehouse1_name}\n`;
                botReply += `- City: ${combo.warehouse1_city}\n`;
                botReply += `- Delivery Quantity: ${combo.warehouse1_delivery}kg (Available: ${combo.warehouse1_capacity}kg)\n\n`;
                botReply += `Warehouse 2 Details:\n`;
                botReply += `- Name: ${combo.warehouse2_name}\n`;
                botReply += `- City: ${combo.warehouse2_city}\n`;
                botReply += `- Delivery Quantity: ${combo.warehouse2_delivery}kg (Available: ${combo.warehouse2_capacity}kg)\n\n`;
                botReply += `- Combined Delivery Time: ${combo.combined_delivery_time}\n`;
              }
            } else {
              botReply += `⚠️ RECOMMENDATION: ESCALATE\n\n`;
              botReply += `${data.message}\n`;
              
              // Show earliest warehouse option if available
              if (data.earliest_warehouse) {
                botReply += `\n📦 EARLIEST OPTION:\n`;
                botReply += `- Warehouse: ${data.earliest_warehouse_name} (${data.earliest_warehouse})\n`;
                botReply += `- Can Deliver By: ${data.earliest_delivery_time}\n`;
                botReply += `- Available Capacity: ${data.earliest_available_inventory}kg\n`;
              }
            }
            
            setMessages(prev => [...prev, { 
              type: "bot", 
              text: botReply,
              disruptionData: data
            }]);
          } catch (fetchError) {
            console.error("Disruption API error:", fetchError);
            throw fetchError;
          }
        } else {
          throw new Error(
            `Invalid disruption query. Missing required fields:\n` +
            `Source: ${disruptionResult.source || "NOT FOUND"}\n` +
            `Destination: ${disruptionResult.destination || "NOT FOUND"}\n` +
            `Demand: ${disruptionResult.demandKg || "NOT FOUND"} kg\n\n` +
            `Format: "Route from [CITY] to [CITY] with [NUMBER]kg disrupted at [TIME], needs delivery by [TIME], repair time [HOURS] hours"`
          );
        }
      } else {
        // Regular route optimization query
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
      }
    } catch (error) {
      setMessages(prev => [...prev, { type: "bot", text: `❌ Error: ${error.message}` }]);
    } finally {
      setIsLoading(false);
    }
  };

  const parseDisruptionQuery = (message) => {
    // Parse disruption query: "Route from Delhi to Mumbai with 1000kg disrupted at 10pm, needs delivery by 10am, repair time 5 hours"
    // Optional: "disrupted near nagpur" to specify disruption location for warehouse diversion
    const result = {
      valid: false,
      source: null,
      destination: null,
      demandKg: null,
      disruptionTime: null,
      requiredTime: null,
      repairHours: null,
      disruptionLocation: null
    };

    try {
      // Extract source and destination - more flexible pattern
      const routeMatch = /(?:from|source|origin|starting)[\s:]+(\w+)[\s:]*(?:to|destination|ending)[\s:]+(\w+)/i.exec(message);
      if (routeMatch) {
        result.source = routeMatch[1].toLowerCase();
        result.destination = routeMatch[2].toLowerCase();
      }

      // Extract demand weight - more flexible
      const demandMatch = /(?:with|carrying|transporting|shipping)[\s:]+(\d+)[\s]*kg/i.exec(message);
      if (demandMatch) {
        result.demandKg = parseInt(demandMatch[1]);
      }

      // Extract disruption time - handle "Xpm" and "X:XXpm" formats
      const disruptionMatch = /(?:disrupted|disruption|route\s+broke)[\s:]*(?:at|around|approximately)?[\s:]*(\d{1,2}):?(\d{2})?\s*([ap]m)?/i.exec(message);
      if (disruptionMatch) {
        let hour = parseInt(disruptionMatch[1]);
        const minute = disruptionMatch[2] ? parseInt(disruptionMatch[2]) : 0;
        const meridiem = disruptionMatch[3] ? disruptionMatch[3].toLowerCase() : null;
        
        if (meridiem === 'pm' && hour !== 12) hour += 12;
        if (meridiem === 'am' && hour === 12) hour = 0;
        
        result.disruptionTime = `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`;
      }

      // Extract required delivery time - more flexible
      const deliveryMatch = /(?:deliver|delivery|reach|arrive|needs|by)[\s:]*(?:by)?[\s:]*(\d{1,2}):?(\d{2})?\s*([ap]m)?/i.exec(message);
      if (deliveryMatch) {
        let hour = parseInt(deliveryMatch[1]);
        const minute = deliveryMatch[2] ? parseInt(deliveryMatch[2]) : 0;
        const meridiem = deliveryMatch[3] ? deliveryMatch[3].toLowerCase() : null;
        
        if (meridiem === 'pm' && hour !== 12) hour += 12;
        if (meridiem === 'am' && hour === 12) hour = 0;
        
        result.requiredTime = `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`;
      }

      // Extract repair time - more flexible
      const repairMatch = /(?:repair|fix|fix\s+time|repair\s+time|repair\s+takes?|repair\s+duration|takes?)[\s:]*(\d+)\s*(?:hours?|hrs?|h)/i.exec(message);
      if (repairMatch) {
        result.repairHours = parseInt(repairMatch[1]);
      }

      // Extract disruption location (near city) - "disrupted near nagpur" or "disruption near nagpur"
      const locationMatch = /(?:disrupted|disruption)[\s:]+(?:near|around|at)[\s:]+(\w+)/i.exec(message);
      if (locationMatch) {
        result.disruptionLocation = locationMatch[1].toLowerCase();
      }

      // Check if minimum required fields are present
      if (result.source && result.destination && result.demandKg) {
        result.valid = true;
      }

      return result;
    } catch (e) {
      console.error("Error parsing disruption query:", e);
      return result;
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
              
              {/* Disruption Data Display */}
              {msg.disruptionData && (
                <div className="disruption-info">
                  <h4>📍 Alternative Warehouses Found:</h4>
                  {msg.disruptionData.alternative_warehouses && msg.disruptionData.alternative_warehouses.length > 0 && (
                    <div className="alternative-warehouses">
                      {msg.disruptionData.alternative_warehouses.map((alt, idx) => (
                        <details key={idx} className="warehouse-option">
                          <summary className={alt.feasible ? "feasible" : "not-feasible"}>
                            {alt.warehouse_name} ({alt.warehouse_city}) - {alt.distance_from_destination_km} km away
                            {alt.feasible ? " ✅" : " ❌"}
                          </summary>
                          <div className="warehouse-details">
                            <p><strong>Inventory:</strong> {alt.inventory} kg</p>
                            <p><strong>Reorder Level:</strong> {alt.reorder_level} kg</p>
                            <p><strong>Available Quantity:</strong> {alt.available_inventory} kg</p>
                            <p><strong>Distance from Destination:</strong> {alt.distance_from_destination_km} km</p>
                            <p><strong>Estimated Delivery:</strong> {alt.delivery_analysis.estimated_delivery_time}</p>
                            {alt.delivery_analysis.distance_km && (
                              <p><strong>Route Distance:</strong> {alt.delivery_analysis.distance_km} km</p>
                            )}
                            {alt.delivery_analysis.travel_hours && (
                              <p><strong>Travel Time:</strong> {alt.delivery_analysis.travel_hours} hours</p>
                            )}
                          </div>
                        </details>
                      ))}
                    </div>
                  )}
                </div>
              )}
              
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
