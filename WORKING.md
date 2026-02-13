# Complete Workflow Documentation - Logistics Optimizer

## Overview
This document explains the complete end-to-end workflow when a user submits a chat query to optimize routes with vehicle capacity planning.

---

## 1. USER INTERACTION - Frontend (ChatInterface.js)

### Step 1.1: User Types Query
```javascript
// Location: ChatInterface.js - handleSend()
const userMsg = input.trim();
setInput("");
setMessages(prev => [...prev, { type: "user", text: userMsg }]);
```
**What happens:**
- User types: `"plan transport of 3600kg goods from mumbai to bengaluru"`
- Message is added to chat display
- Input field is cleared

### Step 1.2: Send Request to Backend
```javascript
const response = await fetch(
  `http://localhost:8000/chat?message=${encodeURIComponent(userMsg)}`,
  { method: "POST" }
);
```
**Request Details:**
- Endpoint: `POST /chat`
- Parameter: `message=plan%20transport%20of%203600kg%20goods%20from%20mumbai%20to%20bengaluru`
- Headers: Standard CORS headers

---

## 2. BACKEND PROCESSING - main.py

### Step 2.1: Chat Endpoint Receives Request
```python
# Location: main.py - @app.post("/chat")
async def chat(message: str = Query(...)):
    global nodes, edges, vehicles_df
    
    if not nodes or not edges:
        raise HTTPException(status_code=400, detail="Please upload route data first")
```
**Validation:**
- Checks if routes are loaded (from previous /upload)
- Checks if vehicles are loaded (from /upload-vehicles)

### Step 2.2: Parse Query with LLM
```python
query_data = parse_query(message, list(nodes.keys()))
source = query_data.get("source")
destination = query_data.get("destination")
objective = query_data.get("objective", "cost")
```
**Function Call:** `parse_query()` from `llm.py`

#### 2.2a: parse_query() - Natural Language Understanding
```python
# Location: llm.py - parse_query()
def parse_query(user_input: str, available_nodes: List[str]) -> Dict:
    prompt = f"""Extract source, destination, goods_kg, and objective from: "{user_input}"
Available cities: {available_nodes}
Return JSON: {{"source": "...", "destination": "...", "goods_kg": X, "objective": "..."}}"""
    
    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=200
    )
```
**LLM Processing:**
- Uses GPT-4 to understand natural language
- Extracts: source city, destination city, weight, objective (cost/time)
- Returns structured JSON

**Example Output:**
```json
{
  "source": "mumbai",
  "destination": "bengaluru", 
  "goods_kg": 3600,
  "objective": "cost"
}
```

### Step 2.3: Source/Destination Validation
```python
# Location: main.py - chat endpoint
if source not in nodes or destination not in nodes:
    source = find_closest_match(source, list(nodes.keys()))
    destination = find_closest_match(destination, list(nodes.keys()))
```
**Function Call:** `find_closest_match()` from `llm.py`

#### 2.3a: find_closest_match() - Fuzzy Matching
```python
# Location: llm.py
def find_closest_match(user_input: str, available_nodes: List[str], 
                       threshold: int = 70) -> str:
    matches = process.extract(
        user_input.lower(),
        [n.lower() for n in available_nodes],
        limit=1
    )
```
**Purpose:** Handles typos/variations like "Dilli" → "delhi"

### Step 2.4: Main Route Optimization
```python
# Location: main.py
route = optimize(nodes, edges, source.lower(), destination.lower(), objective)
```
**Function Call:** `optimize()` from `optimizer.py`

#### 2.4a: optimize() - Linear Programming Route Selection
```python
# Location: optimizer.py
def optimize(nodes, edges, start, end, objective="cost", via=None):
    model = LpProblem("Logistics_Optimization", LpMinimize)
    
    # Create binary variables for each edge
    x = LpVariable.dicts("route", edges.keys(), cat="Binary")
    
    # Set objective based on user preference
    if objective == "time":
        model += lpSum(x[e] * edges[e].get("time", 0) for e in edges)
    else:  # cost
        model += lpSum(x[e] * edges[e].get("fuel", 0) for e in edges)
```
**Algorithm:**
- Uses PuLP (Linear Programming)
- Finds shortest/cheapest path through network
- Respects flow conservation constraints
- Returns ordered list of edges (route segments)

**Output Example:**
```python
[
  {"from": "mumbai", "to": "bengaluru", "distance": 985.27, "mode": "road", ...},
]
```

### Step 2.5: Format Response Data for Table
```python
# Location: main.py
table_data = []
for i, leg in enumerate(route, 1):
    total_distance += leg["distance"]
    total_time += leg["time"]
    total_cost += leg["fuel"]
    
    table_data.append({
        "step": i,
        "from": leg["from"].title(),
        "to": leg["to"].title(),
        "mode": leg["mode"].title(),
        "distance_km": round(leg["distance"], 2),
        "time_hours": round(leg["time"], 2),
        "fuel_cost_usd": round(leg["fuel"], 2)
    })
```
**Purpose:** Create data structure for frontend table display

### Step 2.6: Detect Capacity Query
```python
# Location: main.py
is_capacity_query = any(word in message.lower() 
                       for word in ["capacity", "vehicle", "load", "goods_kg", "weight", "kg"])

# Extract weight from message
weight_match = re.search(r'(\d+(?:\.\d+)?)\s*kg', message.lower())
if weight_match:
    goods_kg = float(weight_match.group(1))
```
**Logic:**
- Checks if user mentioned vehicles/capacity/weight
- Regex extracts numeric weight
- Default is 1000 kg if not specified

### Step 2.7: Capacity Optimization (if detected)
```python
# Location: main.py
if is_capacity_query and vehicles_df is not None:
    capacity_result = await optimize_with_capacity(
        source=source,
        destination=destination,
        goods_kg=goods_kg,
        objective=objective
    )
```
**Function Call:** `optimize_with_capacity()` from `main.py`

#### 2.7a: optimize_with_capacity() - Vehicle Assignment
```python
# Location: main.py
async def optimize_with_capacity(source, destination, goods_kg, objective):
    route = optimize(nodes, edges, source.lower(), destination.lower(), objective)
    
    vdf = vehicles_df.copy()
    legs_output = []
    
    for leg in route:
        assignment = assign_vehicles_for_leg(vdf, leg, goods_kg, objective)
```
**Logic:**
- Gets the optimized route from Step 2.4
- For each leg in the route, assigns vehicles
- Calls capacity optimization function

#### 2.7b: assign_vehicles_for_leg() - Vehicle Selection
```python
# Location: capacity_optimizer.py
def assign_vehicles_for_leg(vehicles_df, leg, total_goods, objective="cost"):
    source_city = leg["from"].lower()
    
    # Filter vehicles available at source city
    available = vehicles_df[
        vehicles_df["base_city"].str.lower() == source_city
    ].copy()
    
    # Create LP model
    model = LpProblem("Vehicle_Assignment", LpMinimize)
    x = LpVariable.dicts("vehicle", available.index, cat="Binary")
    
    # Objective: minimize cost or time
    if objective == "time":
        model += lpSum(
            x[i] * (leg["distance"] / available.loc[i, "speed_kmph"])
            for i in available.index
        )
    else:
        model += lpSum(
            x[i] * available.loc[i, "cost_per_km"] * leg["distance"]
            for i in available.index
        )
    
    # Constraint: total capacity >= goods
    model += lpSum(
        x[i] * available.loc[i, "capacity_kg"]
        for i in available.index
    ) >= total_goods
    
    # Solve
    model.solve(PULP_CBC_CMD(msg=0))
```
**Algorithm:**
- Filters vehicles from source city
- Uses Linear Programming to select minimum vehicles
- Ensures total capacity meets goods weight
- Calculates travel times and costs

**Output Example:**
```python
{
    "from": "mumbai",
    "to": "bengaluru",
    "vehicles": [
        {
            "vehicle_id": "MUM-TRU-01",
            "load_kg": 2050,
            "departure": "09:10",
            "arrival": "03:42",
            "distance": 985.27,
            "fuel_cost": 295.58
        },
        ...
    ],
    "last_arrival": "04:52"
}
```

### Step 2.8: Generate Transport Plan Explanation
```python
# Location: main.py
explanation = generate_transport_plan(capacity_data)
```
**Function Call:** `generate_transport_plan()` from `llm.py`

#### 2.8a: generate_transport_plan() - Format Plan
```python
# Location: llm.py
def generate_transport_plan(capacity_data):
    plan = f"""🚚 **DETAILED TRANSPORT EXECUTION PLAN**

📋 **Shipment Overview:**
- **Total Goods:** {total_goods_kg} kg
- **Route:** {' → '.join(route)}
- **Final Delivery Time:** {final_delivery_time}
"""
    
    for leg_num, leg in enumerate(legs, 1):
        plan += f"""🛣️ **LEG {leg_num}: {from_city} → {to_city}**
"""
        for vehicle in leg.get('vehicles', []):
            plan += f"""**{vehicle['vehicle_id']}**
- **Departure:** {vehicle['departure']}
- **Load:** {vehicle['load_kg']} kg
- **Arrival:** {vehicle['arrival']}
"""
    
    return plan
```
**Output:** Human-readable transport plan with all vehicle details

### Step 2.9: Convert Numpy Types (JSON Serialization)
```python
# Location: main.py
response_data = convert_numpy_types(response_data)
```
**Function Call:** `convert_numpy_types()` from `main.py`

#### 2.9a: convert_numpy_types() - Type Conversion
```python
# Location: main.py
def convert_numpy_types(obj):
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: convert_numpy_types(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [convert_numpy_types(item) for item in obj]
    else:
        return obj
```
**Purpose:** Convert pandas/numpy types to Python native types for JSON

### Step 2.10: Return Complete Response
```python
# Location: main.py
return convert_numpy_types({
    "status": "success",
    "explanation": explanation,
    "table_data": table_data,
    "csv_download": { "link": ..., "filename": ... },
    "route": route,
    "capacity_plan": capacity_plan  # if available
})
```

**Full Response JSON:**
```json
{
  "status": "success",
  "explanation": "🚚 **DETAILED TRANSPORT EXECUTION PLAN**\n...",
  "table_data": [
    {
      "step": 1,
      "from": "Mumbai",
      "to": "Bengaluru",
      "mode": "Road",
      "distance_km": 985.27,
      "time_hours": 19.71,
      "fuel_cost_usd": 295.58
    }
  ],
  "csv_download": {
    "link": "data:text/csv,...",
    "filename": "route_mumbai_to_bengaluru.csv"
  },
  "route": [
    {
      "from": "mumbai",
      "to": "bengaluru",
      "mode": "road",
      "distance": 985.27,
      "time": 19.71,
      "fuel": 295.58,
      "geometry": [[19.08, 72.88], [13.19, 77.71]],
      "lat_src": 19.08,
      "lon_src": 72.88,
      "lat_dst": 13.19,
      "lon_dst": 77.71
    }
  ],
  "capacity_plan": {
    "legs": [
      {
        "from": "mumbai",
        "to": "bengaluru",
        "vehicles": [...]
      }
    ]
  }
}
```

---

## 3. FRONTEND RESPONSE HANDLING - ChatInterface.js

### Step 3.1: Parse Response
```javascript
// Location: ChatInterface.js - handleSend()
const data = await response.json();
console.log("Chat API response:", data);
```
**Logging:** For debugging, logs full API response

### Step 3.2: Extract Vehicle Information
```javascript
let vehicleInfo = null;
if (data.capacity_plan && data.capacity_plan.legs) {
    vehicleInfo = data.capacity_plan.legs.map(leg => ({
        from: leg.from,
        to: leg.to,
        vehicles: leg.vehicles || []
    }));
}
```
**Purpose:** Prepare vehicle data for detailed display

### Step 3.3: Update Chat Messages
```javascript
setMessages(prev => [...prev, { 
    type: "bot", 
    text: botReply,
    tableData: data.table_data,
    csvData: data.csv_download,
    vehicleInfo: vehicleInfo
}]);
```
**Display Components:**
- Bot explanation text
- Route table with segments
- Download CSV button
- Vehicle assignment details (collapsible)

### Step 3.4: Pass Route to Map
```javascript
console.log("Calling onRouteUpdate with route:", data.route);
onRouteUpdate(data.route);
```
**Function:** Callback to `App.js`

```javascript
// Location: App.js
const handleRouteUpdate = (route) => {
    setCurrentRoute(route);
};

// Pass to MapView
<MapView route={currentRoute} ... />
```

---

## 4. MAP VISUALIZATION - MapView.js

### Step 4.1: Receive Route
```javascript
// Location: MapView.js
export default function MapView({ route = null, ... }) {
    useEffect(() => {
        if (route) {
            console.log("MapView received route:", route);
        }
    }, [route]);
```
**Logging:** Confirms route received

### Step 4.2: Calculate Map Center and Zoom
```javascript
useEffect(() => {
    if (route && route.length > 0) {
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
        
        const centerLat = (Math.max(...lats) + Math.min(...lats)) / 2;
        const centerLon = (Math.max(...lons) + Math.min(...lons)) / 2;
        setCenter([centerLat, centerLon]);
        setZoom(6);
    }
}, [route]);
```
**Logic:**
- Extracts all lat/lon from route geometries
- Calculates center point
- Sets appropriate zoom level

### Step 4.3: Render Polylines
```javascript
// Location: MapView.js
{route && route.length > 0 ? (
    route.map((segment, idx) => {
        console.log(`Rendering segment ${idx}:`, segment);
        
        if (segment.geometry && segment.geometry.length > 0) {
            return (
                <Polyline
                    key={`route-${idx}`}
                    positions={segment.geometry}
                    {...getLineOptions(segment.mode)}
                    opacity={0.7}
                >
                    <Popup>
                        <div>
                            <strong>{segment.from} → {segment.to}</strong>
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
    })
) : null}
```
**Line Styling:**
- Air routes: Green dashed lines (color: #22c55e)
- Road routes: Blue solid lines (color: #3b82f6)

### Step 4.4: Add Markers
```javascript
// Location: MapView.js

// Start marker (red)
{startPoint && route && route.length > 0 && (
    <CircleMarker center={startPoint} radius={8} fillColor="#ef4444" ...>
        <Popup><strong>Start</strong><br />{route[0].from}</Popup>
    </CircleMarker>
)}

// Waypoints (orange)
{waypoints.map((wp, idx) => (
    <CircleMarker center={wp.point} radius={6} fillColor="#f59e0b" ...>
        <Popup>{wp.from} via point</Popup>
    </CircleMarker>
))}

// End marker (green)
{endPoint && route && route.length > 0 && (
    <CircleMarker center={endPoint} radius={8} fillColor="#16a34a" ...>
        <Popup><strong>End</strong><br />{route[route.length - 1].to}</Popup>
    </CircleMarker>
)}
```
**Marker Colors:**
- Start: Red (#ef4444)
- Waypoints: Orange (#f59e0b)
- End: Green (#16a34a)

### Step 4.5: Add Legend
```javascript
<div className="map-legend">
    <div className="legend-item">
        <div style={{ borderTop: "3px solid #22c55e" }}></div>
        <span>Air Routes</span>
    </div>
    <div className="legend-item">
        <div style={{ borderTop: "3px solid #3b82f6" }}></div>
        <span>Road Routes</span>
    </div>
    ...
</div>
```

---

## 5. COMPLETE REQUEST-RESPONSE FLOW DIAGRAM

```
┌─────────────────────────────────────────────────────────────────────┐
│ USER INTERACTION                                                    │
├─────────────────────────────────────────────────────────────────────┤
│ 1. User types: "plan transport of 3600kg from mumbai to bengaluru"  │
│ 2. ChatInterface sends POST /chat?message=...                       │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│ BACKEND PROCESSING                                                  │
├─────────────────────────────────────────────────────────────────────┤
│ 1. main.py:chat() receives message                                  │
│ 2. llm.parse_query() extracts: mumbai, bengaluru, 3600kg, cost     │
│ 3. llm.find_closest_match() verifies cities exist                   │
│ 4. optimizer.optimize() finds cheapest route using LP              │
│ 5. capacity_optimizer.assign_vehicles_for_leg() assigns vehicles    │
│ 6. llm.generate_transport_plan() formats detailed explanation      │
│ 7. Converts numpy types to JSON-serializable formats               │
│ 8. Returns complete response with route, plan, table data          │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│ FRONTEND RESPONSE HANDLING                                          │
├─────────────────────────────────────────────────────────────────────┤
│ 1. ChatInterface.handleSend() receives response                      │
│ 2. Extracts: explanation, table_data, route, vehicle_info          │
│ 3. Displays message with:                                          │
│    - Transport plan explanation                                    │
│    - Route table                                                   │
│    - Vehicle assignment details                                    │
│    - CSV download button                                           │
│ 4. Calls onRouteUpdate(route)                                       │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│ MAP VISUALIZATION                                                   │
├─────────────────────────────────────────────────────────────────────┤
│ 1. MapView receives route data                                      │
│ 2. Extracts coordinates from geometry property                      │
│ 3. Calculates map center and zoom level                             │
│ 4. Renders polylines for each route segment                         │
│    - Blue for road routes                                          │
│    - Green dashed for air routes                                   │
│ 5. Adds markers:                                                    │
│    - Red: start point                                              │
│    - Orange: waypoints                                             │
│    - Green: end point                                              │
│ 6. Adds legend showing route types                                  │
│ 7. Creates popups with segment details                              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 6. FILE-TO-FILE FUNCTION CALLS SUMMARY

```
main.py:chat()
    ├─ llm.parse_query()
    │   └─ [LLM API Call to OpenAI]
    ├─ llm.find_closest_match()
    │   └─ [Fuzzy matching with fuzzywuzzy]
    ├─ optimizer.optimize()
    │   └─ [Linear Programming with PuLP]
    ├─ main.optimize_with_capacity()
    │   ├─ optimizer.optimize()
    │   └─ capacity_optimizer.assign_vehicles_for_leg()
    │       └─ [Linear Programming with PuLP]
    ├─ llm.generate_transport_plan()
    │   └─ [String formatting - no external calls]
    ├─ main.convert_numpy_types()
    │   └─ [Recursive type conversion]
    └─ [return JSON response]
```

---

## 7. DATA STRUCTURES FLOW

### 7.1: Phase 1 - Query Parsing
```python
Input: "plan transport of 3600kg from mumbai to bengaluru"

After parse_query():
{
    "source": "mumbai",
    "destination": "bengaluru",
    "goods_kg": 3600,
    "objective": "cost"
}
```

### 7.2: Phase 2 - Route Optimization
```python
After optimize():
[
    {
        "from": "mumbai",
        "to": "bengaluru",
        "mode": "road",
        "distance": 985.27,
        "time": 19.71,
        "fuel": 295.58,
        "geometry": [[19.08, 72.88], [13.19, 77.71]],
        "lat_src": 19.08,
        "lon_src": 72.88,
        "lat_dst": 13.19,
        "lon_dst": 77.71
    }
]
```

### 7.3: Phase 3 - Vehicle Assignment
```python
After assign_vehicles_for_leg():
{
    "from": "mumbai",
    "to": "bengaluru",
    "vehicles": [
        {
            "vehicle_id": "MUM-TRU-01",
            "vehicle_type": "truck",
            "load_kg": 2050,
            "departure": "09:10",
            "arrival": "03:42",
            "distance": 985.27,
            "travel_time_hours": 19.71,
            "fuel_cost": 295.58
        },
        {
            "vehicle_id": "MUM-TRU-02",
            "vehicle_type": "truck",
            "load_kg": 1550,
            "departure": "08:00",
            "arrival": "04:52",
            "distance": 985.27,
            "travel_time_hours": 19.71,
            "fuel_cost": 295.58
        }
    ],
    "leg_distance": 985.27,
    "leg_time": 19.71,
    "last_arrival": "04:52"
}
```

### 7.4: Phase 4 - Frontend Table Data
```javascript
After table formatting:
[
    {
        "step": 1,
        "from": "Mumbai",
        "to": "Bengaluru",
        "mode": "Road",
        "distance_km": 985.27,
        "time_hours": 19.71,
        "fuel_cost_usd": 295.58
    }
]
```

---

## 8. ERROR HANDLING FLOW

```
User Query
    │
    ├─ NO_ROUTES_UPLOADED ──→ Error: "Please upload route data first"
    │
    ├─ PARSE_FAILED ──→ Error: "Could not parse source or destination"
    │
    ├─ CITY_NOT_FOUND ──→ Fuzzy match attempt ──→ Success OR Error
    │
    ├─ NO_ROUTE_FOUND ──→ Error: "No route found from source to destination"
    │
    ├─ CAPACITY_CALCULATION_FAILED ──→ Log error, fall back to regular route
    │
    ├─ JSON_SERIALIZATION_ERROR ──→ Convert numpy types ──→ Success
    │
    └─ SUCCESS ──→ Return complete response
```

---

## 9. KEY TECHNOLOGIES USED

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Query Understanding | OpenAI GPT-4 | Natural language processing |
| Route Finding | PuLP + CBC Solver | Linear programming optimization |
| Vehicle Assignment | PuLP + CBC Solver | Integer programming for capacity |
| Fuzzy Matching | fuzzywuzzy | Handle city name variations |
| Frontend | React | User interface |
| Map | Leaflet + Leaflet-React | Route visualization |
| API | FastAPI | Backend REST API |
| Data Processing | Pandas + NumPy | CSV handling & calculations |

---

## 10. CONFIGURATION & CONSTANTS

### Vehicle Specifications (capacity_optimizer.py)
```python
VEHICLE_SPECS = {
    "truck": {"speed": 80, "cost": 0.50},      # km/h, $/km
    "van": {"speed": 90, "cost": 0.40},
    "car": {"speed": 100, "cost": 0.30},
    "auto": {"speed": 60, "cost": 0.20},
    "bike": {"speed": 80, "cost": 0.10},
    "plane": {"speed": 900, "cost": 2.00},
}
```

### Map Line Styles (MapView.js)
```javascript
AIR_ROUTES: {
    color: "#22c55e",
    weight: 3,
    dashArray: "5, 10"  // dashed
}

ROAD_ROUTES: {
    color: "#3b82f6",
    weight: 4,
    dashArray: "0"      // solid
}
```

### Marker Colors
```javascript
START: "#ef4444"    (Red)
WAYPOINT: "#f59e0b" (Orange)
END: "#16a34a"      (Green)
```

---

## 11. PERFORMANCE OPTIMIZE POINTS

| Operation | Time | Bottleneck |
|-----------|------|-----------|
| Parse Query (LLM) | 2-5s | OpenAI API latency |
| Route Optimization (LP) | < 1s | Problem complexity |
| Vehicle Assignment (LP) | 1-2s | Vehicle count & constraints |
| Transport Plan Gen | < 1s | String formatting |
| Total Backend | 3-8s | LLM processing |
| Frontend Render | < 500ms | Route complexity |
| Map Display | 1-2s | Leaflet rendering |
| **Total E2E** | **5-12s** | **LLM & LP solving** |

---

## 12. TESTING FLOW

### Test Case 1: Basic Query
```
Input: "cheapest route from delhi to mumbai"
Expected: Route table with Delhi→Mumbai leg
Actual Output: ✓ Works
```

### Test Case 2: Capacity Query
```
Input: "carry 5000 kg from mumbai to bengaluru"
Expected: Route table + vehicle assignments
Actual Output: ✓ Works with MUM-TRU-01, MUM-TRU-02 assignments
```

### Test Case 3: Time Objective
```
Input: "fastest route from london to frankfurt for 2000 kg"
Expected: Route with shortest travel time
Actual Output: ✓ Selects air over road when available
```

### Test Case 4: Fuzzy Matching
```
Input: "route from bomay to bengaluru" (typo: "bomay" instead of "mumbai")
Expected: Auto-corrected to mumbai
Actual Output: ✓ Fuzzy match finds "mumbai" with 80%+ confidence
```

---

## SUMMARY

When a user submits a chat query:

1. **Frontend** captures input and sends to backend
2. **Backend** uses **LLM** to understand intent
3. **Backend** uses **Linear Programming** to find optimal route
4. **Backend** uses **Linear Programming** to assign vehicles by capacity
5. **Backend** formats response with explanation, table data, and route geometry
6. **Frontend** displays explanation and table
7. **Frontend** passes route to map component
8. **Map** renders polylines and markers based on geometry
9. **User** sees complete transport plan with visualization

This entire workflow takes **5-12 seconds** typically, with **LLM processing** being the main bottleneck.
