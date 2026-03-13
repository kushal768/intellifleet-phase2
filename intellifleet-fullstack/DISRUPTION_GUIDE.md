# Disruption Management & Route Optimization Guide

## Overview
The system now supports handling route disruptions with automatic alternative warehouse routing, inventory validation, and delivery time estimation.

## New Features

### 1. Warehouse CSV Upload
- **Purpose**: Manage warehouse inventory and reorder levels
- **Required Columns**:
  - `Country`: Country name
  - `City`: Warehouse city (must match city names in road/air routes)
  - `NodeType`: Type of warehouse (e.g., "Capital", "City")
  - `Name`: Warehouse name/identifier
  - `Address`: Physical address
  - `Inventory`: Current inventory in kg
  - `ReorderLevel`: Minimum inventory level before restocking

**Example**:
```
Country,City,NodeType,Name,Address,Inventory,ReorderLevel
India,New Delhi,Capital,UPS New Delhi,D-12/1 Okhla Industrial Area,130,28
India,Mumbai,City,Mumbai,Andheri-Kurla Road,120,25
India,Indore,City,Indore,Pithampur Industrial Area,75,12
```

### 2. Disruption Handling

When a route is disrupted, the system will:
1. **Analyze the disruption** - Check if the original route can still meet the deadline after repair
2. **Find alternatives** - Identify nearby warehouses that can fulfill the demand
3. **Validate inventory** - Ensure selected warehouse has enough inventory without going below reorder level
4. **Estimate delivery times** - Calculate realistic delivery times for alternative routes
5. **Provide recommendations** - Suggest best action (proceed with repair, divert, or escalate)

#### How to Report a Disruption
Ask the system using natural language:

**Format**:
```
"Route from [SOURCE] to [DESTINATION] with [WEIGHT]kg disrupted at [TIME], 
needs delivery by [TIME], repair time [HOURS] hours"
```

**Examples**:

1. **Basic disruption**:
   - "Route from Delhi to Mumbai with 1000kg disrupted at 10pm, needs delivery by 10am, repair time 5 hours"

2. **With explicit times**:
   - "Route from Indore to Mumbai with 500kg. Disruption at 22:00. Required delivery by 09:00. Repair takes 5 hours."

3. **Format variations**:
   - "Route to Mumbai from Delhi transporting 1000kg disrupted at 10pm needs to reach by 10am with 5 hour repair"

#### Query Parameters
The system extracts:
- **Source Warehouse**: "from [CITY]" - warehouse city where goods originate
- **Destination**: "to [CITY]" - final destination city
- **Demand**: "[NUMBER]kg" - weight of goods
- **Disruption Time**: "at [TIME]" - when the route was disrupted (HH:MM format)
- **Delivery Deadline**: "by [TIME]" - when goods must arrive (HH:MM format)
- **Repair Duration**: "[NUMBER] hours" - time needed to fix vehicle/route

### 3. Disruption Response

The system provides:

#### A. If Original Route Can Still Meet Deadline
```
✅ RECOMMENDATION: PROCEED WITH REPAIR

The original route to [DESTINATION] will be able to deliver by [TIME]. 
Proceed with repair.
```

#### B. If Alternative Warehouse Available
```
📍 RECOMMENDATION: DIVERT TO ALTERNATIVE WAREHOUSE

Original route cannot meet the [TIME] deadline. 
Divert truck to [WAREHOUSE] ([CITY]). 
Can deliver by [TIME] with [INVENTORY]kg available.

Warehouse Details:
- Distance from Destination: [KM] km
- Available Inventory: [KG] kg
- Estimated Delivery: [TIME] [DATE]
- Current Inventory: [KG] kg
- Reorder Level: [KG] kg
```

#### C. If No Solution Available
```
⚠️ RECOMMENDATION: ESCALATE

Cannot meet deadline with current repair time. No alternative warehouse can 
fulfill demand by [TIME]. Consider expedited repair or alternative 
transportation (air freight).
```

### 4. Inventory Management

The system validates inventory against reorder levels:
- **Available Inventory** = Current Inventory - Demand Weight
- **Must satisfy**: Available Inventory >= Reorder Level

A warehouse is considered valid if:
- It has enough inventory to fulfill demand
- Remaining inventory stays above reorder level
- It can be reached with goods arriving by the deadline

## Updated Data Files

### vehicles_mapped.csv
Extended to include more warehouses. Each vehicle has:
- `WarehouseName`: Source warehouse (lowercase)
- `VehicleType`: Truck, Van, Car, Auto, Bike, Plane
- `VehicleCapacity`: Capacity in kg
- `DepartureTime`: Standard departure time (HH:MM)

### air_routes.csv & road_routes.csv
Updated to include all warehouse cities to enable:
- Direct routing between any warehouse pairs
- Both air and road route options
- Distance and coordinate calculations

## City Mappings

All warehouse cities now have routes configured:
- **India**: Delhi, Mumbai, Bengaluru, Chennai, Hyderabad, Kolkata, Pune, Jaipur, Chandigarh, Ahmedabad, Amritsar, Goa, Nagpur, Indore, Surat, Lucknow, Kanpur, Patna, Kochi, Trivandrum

## API Endpoints

### 1. Upload Warehouses
```
POST /upload-warehouses
Content-Type: multipart/form-data

Body:
- warehouses: CSV file
```

### 2. Handle Disruption
```
POST /handle-disruption
Content-Type: application/json

Body:
{
  "source_warehouse": "delhi",
  "destination_city": "mumbai",
  "demand_kg": 1000,
  "disruption_time": "22:00",
  "required_delivery_time": "10:00",
  "repair_hours": 5
}

Response:
{
  "disruption_time": "22:00",
  "required_delivery_time": "10:00",
  "repair_duration_hours": 5,
  "demand_weight_kg": 1000,
  "original_route": {...},
  "original_feasible": true/false,
  "recommendation": "PROCEED_WITH_REPAIR|DIVERT_TO_WAREHOUSE|ESCALATE",
  "recommended_warehouse": "indore",
  "message": "...",
  "alternative_warehouses": [
    {
      "warehouse_city": "indore",
      "warehouse_name": "Indore",
      "distance_from_destination_km": 250.5,
      "available_inventory": 65,
      "inventory": 75,
      "reorder_level": 12,
      "delivery_analysis": {...},
      "feasible": true
    }
  ]
}
```

## Example Scenario

**User Query**:
"Route from Delhi to Mumbai with 1000kg disrupted at 10pm, needs delivery by 10am next day, repair time 5 hours"

**System Analysis**:
1. Original route: Delhi → Mumbai (distance ~1400 km)
2. Travel time required: ~23 hours at 60 km/h
3. Disruption at 22:00 + Repair 5 hours = 03:00 next day
4. Estimated arrival: 03:00 + 23 hours = 02:00 (next day + 1)
5. Deadline: 10:00 (next day)
6. **Result**: Original route arrives at 02:00, but needs to by 10:00 ✅ FEASIBLE

**If route was disrupted at different time** (e.g., 06:00):
1. Disruption at 06:00 + Repair 5 hours = 11:00
2. Estimated arrival: 11:00 + 23 hours = 10:00 (next day)
3. **Result**: Arrives exactly at 10:00 ✅ FEASIBLE (but tight)

**If repair takes longer** (e.g., 8 hours):
1. Disruption at 22:00 + Repair 8 hours = 06:00 (next day)
2. Estimated arrival: 06:00 + 23 hours = 05:00 (next day + 1)
3. **Result**: Would be 19 hours late ❌ ESCALATE
4. System finds **Indore** as alternative:
   - Indore to Mumbai: ~250 km, ~4 hours travel
   - Total time from repair: 6am + 4 hours = 10am ✅ FEASIBLE
   - Indore inventory: 75 kg, reorder: 12 kg
   - After 1000 kg demand: -925 kg (NOT FEASIBLE - warehouse can't fulfill)
   - Try next alternative: Pune or Nagpur...

## Testing

### Manual Test Scenario

1. **Upload Files**:
   - Air Routes: `air_routes.csv`
   - Road Routes: `road_routes.csv`
   - Vehicles: `vehicles_mapped.csv`
   - Warehouses: `sample_warehouse_data.csv`

2. **Test Query**:
   ```
   "Route from upsnewdelhi to mumbai with 1000kg disrupted at 22:00, 
    must reach by 10:00, 5 hour repair"
   ```

3. **Expected Response**:
   - Original route analysis
   - Alternative warehouses considered
   - Recommendation (Divert to Indore or similar)
   - Estimated delivery times

## Troubleshooting

### Common Issues

1. **"Warehouse data not loaded"**
   - Ensure warehouse CSV is uploaded
   - Check CSV has required columns: City, Name, Inventory, ReorderLevel

2. **"No route found"**
   - Verify source and destination cities exist in road/air routes
   - City names in warehouse CSV must match route files (case-insensitive)

3. **"No alternative warehouses found"**
   - No warehouses have sufficient inventory
   - All nearby warehouses would breach reorder level
   - Try with smaller demand weight or longer repair time

4. **"Route not matching expected format"**
   - Ensure time format is HH:MM (24-hour)
   - Use keywords: "from", "to", "kg", "at", "by", "repair", "hour"
   - Example: "from delhi to mumbai with 1000kg at 10pm by 10am repair 5 hours"

## Performance Notes

- Distance calculations use Haversine formula (great-circle distance)
- Average vehicle speed assumed: 60 km/h for road transport
- Coordinate lookups are O(n) where n = number of warehouses
- Recommendation typically provided in <1 second for up to 100 warehouses

## Future Enhancements

- Real-time traffic data integration
- Dynamic pricing based on disruption severity
- Multi-leg disruption handling (multiple vehicles)
- AI-powered demand prediction
- Customer notification system
