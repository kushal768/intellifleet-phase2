# NOTE: If you see model_not_found errors, update your model name in llm.py to one you have access to (e.g., "gpt-4.1")
from fastapi import FastAPI, UploadFile, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import numpy as np
import logging
import re
from typing import Optional, List
from utils import haversine, road_metrics, air_metrics
from optimizer import optimize, get_route_summary
from llm import parse_query, generate_route_explanation, generate_transport_plan, find_closest_match
from capacity_optimizer import assign_vehicles_for_leg, prepare_vehicles_df
from disruption_manager import DisruptionManager, analyze_disruption_scenario
from io import BytesIO, StringIO
import csv
from datetime import datetime
import base64
from google_maps_service import get_road_distance

# ---------------------------------------------------
# CONFIG
# ---------------------------------------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Logistics Optimizer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------
# UTILITY FUNCTIONS
# ---------------------------------------------------
# Converts numpy data types to native Python types for JSON serialization compatibility.

def convert_numpy_types(obj):
    """Convert numpy types to Python native types for JSON serialization."""
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {k: convert_numpy_types(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [convert_numpy_types(item) for item in obj]
    else:
        return obj

# ---------------------------------------------------
# GLOBAL STATE
# ---------------------------------------------------

nodes = {}
edges = {}
country_code = "US"
vehicles_df = None
warehouses_df = None


# ---------------------------------------------------
# HEALTH
# ---------------------------------------------------

# Returns API health status indicating whether the service is operational.
@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# ---------------------------------------------------
# UPLOAD ROUTE DATA
# ---------------------------------------------------

# Uploads air and road route data from CSV/XLSX files and builds a network graph of nodes and edges.
@app.post("/upload")
async def upload(air: UploadFile, road: UploadFile, country: str = "US"):

    global nodes, edges, country_code

    nodes, edges = {}, {}
    country_code = country

    try:
        # -------- AIR FILE --------
        air_bytes = await air.read()
        if air.filename.lower().endswith(".xlsx"):
            air_df = pd.read_excel(BytesIO(air_bytes))
        else:
            air_df = pd.read_csv(StringIO(air_bytes.decode()))

        required_air_cols = [
            "source_airport", "destination_airport",
            "lat_src", "lon_src", "lat_dst", "lon_dst"
        ]

        if not all(col in air_df.columns for col in required_air_cols):
            raise HTTPException(status_code=400,
                                detail=f"Air CSV missing columns {required_air_cols}")

        # -------- ROAD FILE --------
        road_bytes = await road.read()
        if road.filename.lower().endswith(".xlsx"):
            road_df = pd.read_excel(BytesIO(road_bytes))
        else:
            road_df = pd.read_csv(StringIO(road_bytes.decode()))

        required_road_cols = [
            "source_city", "destination_city",
            "lat_src", "lon_src", "lat_dst", "lon_dst"
        ]

        if not all(col in road_df.columns for col in required_road_cols):
            raise HTTPException(status_code=400,
                                detail=f"Road CSV missing columns {required_road_cols}")

        # -------- PROCESS AIR --------
        for _, r in air_df.iterrows():
            dist = haversine(r.lat_src, r.lon_src, r.lat_dst, r.lon_dst)
            time, fuel = air_metrics(dist, country)

            src = str(r.source_airport).lower().strip()
            dst = str(r.destination_airport).lower().strip()

            nodes[src] = (r.lat_src, r.lon_src)
            nodes[dst] = (r.lat_dst, r.lon_dst)

            edges[(src, dst)] = {
                "from": src,
                "to": dst,
                "mode": "air",
                "distance": round(dist, 2),
                "time": round(time, 2),
                "fuel": round(fuel, 2),
                "lat_src": float(r.lat_src),
                "lon_src": float(r.lon_src),
                "lat_dst": float(r.lat_dst),
                "lon_dst": float(r.lon_dst),
                "geometry": [[float(r.lat_src), float(r.lon_src)], [float(r.lat_dst), float(r.lon_dst)]]
            }

        # -------- PROCESS ROAD --------
        for _, r in road_df.iterrows():
            dist = haversine(r.lat_src, r.lon_src, r.lat_dst, r.lon_dst)
            time, fuel = road_metrics(dist, country)

            src = str(r.source_city).lower().strip()
            dst = str(r.destination_city).lower().strip()

            nodes[src] = (r.lat_src, r.lon_src)
            nodes[dst] = (r.lat_dst, r.lon_dst)

            # Only add road edge if it doesn't already exist as an air route
            # This ensures air routes are prioritized when both exist for the same city pair
            if (src, dst) not in edges or edges[(src, dst)]["mode"] != "air":
                edges[(src, dst)] = {
                    "from": src,
                    "to": dst,
                    "mode": "road",
                    "distance": round(dist, 2),
                    "time": round(time, 2),
                    "fuel": round(fuel, 2),
                    "lat_src": float(r.lat_src),
                    "lon_src": float(r.lon_src),
                    "lat_dst": float(r.lat_dst),
                    "lon_dst": float(r.lon_dst),
                    "geometry": [[float(r.lat_src), float(r.lon_src)], [float(r.lat_dst), float(r.lon_dst)]]
                }

        app.state.nodes = nodes
        app.state.edges = edges

        return {
            "status": "success",
            "nodes": len(nodes),
            "edges": len(edges)
        }

    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------
# UPLOAD VEHICLES DATA
# ---------------------------------------------------

# Uploads vehicle data from CSV/XLSX file and prepares it for capacity-based route optimization.
@app.post("/upload-vehicles")
async def upload_vehicles(vehicles: UploadFile):
    """
    Upload vehicles_mapped.csv file to enable capacity optimization
    """
    global vehicles_df

    try:
        # Read vehicles file
        vehicles_bytes = await vehicles.read()
        if vehicles.filename.lower().endswith(".xlsx"):
            vehicles_df = pd.read_excel(BytesIO(vehicles_bytes))
        else:
            vehicles_df = pd.read_csv(StringIO(vehicles_bytes.decode()))

        # Validate required columns
        required_cols = ["WarehouseName", "VehicleType", "VehicleCapacity", "DepartureTime"]
        if not all(col in vehicles_df.columns for col in required_cols):
            raise HTTPException(
                status_code=400,
                detail=f"Vehicles CSV missing columns {required_cols}"
            )

        # Process and prepare the vehicles dataframe
        vehicles_df = prepare_vehicles_df(vehicles_df)
        app.state.vehicles_df = vehicles_df

        return {
            "status": "success",
            "vehicles_loaded": len(vehicles_df),
            "warehouses": vehicles_df["base_city"].unique().tolist()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Vehicle upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------
# UPLOAD WAREHOUSE DATA
# ---------------------------------------------------

# Uploads warehouse data from CSV file for inventory management and disruption handling
@app.post("/upload-warehouses")
async def upload_warehouses(warehouses: UploadFile):
    """
    Upload warehouse data CSV file
    Expected columns: Country, City, NodeType, Name, Address, Inventory, ReorderLevel
    """
    global warehouses_df

    try:
        # Read warehouses file
        warehouses_bytes = await warehouses.read()
        if warehouses.filename.lower().endswith(".xlsx"):
            warehouses_df = pd.read_excel(BytesIO(warehouses_bytes))
        else:
            warehouses_df = pd.read_csv(StringIO(warehouses_bytes.decode()))

        # Validate required columns
        required_cols = ["City", "Name", "Inventory", "ReorderLevel"]
        if not all(col in warehouses_df.columns for col in required_cols):
            raise HTTPException(
                status_code=400,
                detail=f"Warehouses CSV missing columns {required_cols}"
            )

        # Store in app state
        app.state.warehouses_df = warehouses_df

        return {
            "status": "success",
            "warehouses_loaded": len(warehouses_df),
            "cities": warehouses_df["City"].unique().tolist(),
            "total_inventory": int(warehouses_df["Inventory"].sum())
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Warehouse upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------
# DISRUPTION HANDLING
# ---------------------------------------------------

class DisruptionRequest(BaseModel):
    source_warehouse: str
    destination_city: str
    demand_kg: float
    disruption_time: str = "22:00"
    required_delivery_time: str = "10:00"
    repair_hours: int = 5
    disruption_location: Optional[str] = None

# Handles route disruptions and finds alternative warehouse fulfillment options
@app.post("/handle-disruption")
async def handle_disruption(request: DisruptionRequest):
    """
    Handle route disruption with alternative warehouse routing
    
    Args:
        request: DisruptionRequest containing:
            - source_warehouse: Source warehouse city
            - destination_city: Destination city
            - demand_kg: Weight of goods in kg
            - disruption_time: Time when disruption occurred (HH:MM format)
            - required_delivery_time: Required delivery deadline (HH:MM format)
            - repair_hours: Hours needed for repair
        
    Returns:
        Disruption analysis with recommendations
    """
    
    if warehouses_df is None or warehouses_df.empty:
        raise HTTPException(
            status_code=400,
            detail="Warehouse data not loaded. Please upload warehouse CSV first."
        )
    
    if edges is None or not edges:
        raise HTTPException(
            status_code=400,
            detail="Route data not loaded. Please upload route data first."
        )
    
    try:
        # Convert edges dict to dataframe for road routes
        road_routes_for_disruption = []
        for (src, dst), edge_data in edges.items():
            if edge_data.get("mode") == "road":
                road_routes_for_disruption.append({
                    "source_city": src,
                    "destination_city": dst,
                    "lat_src": edge_data.get("lat_src", 0),
                    "lon_src": edge_data.get("lon_src", 0),
                    "lat_dst": edge_data.get("lat_dst", 0),
                    "lon_dst": edge_data.get("lon_dst", 0)
                })
        
        if not road_routes_for_disruption:
            raise HTTPException(status_code=400, detail="No road routes found")
        
        road_routes_df = pd.DataFrame(road_routes_for_disruption)
        
        # Analyze disruption
        result = analyze_disruption_scenario(
            warehouses_df=warehouses_df,
            road_routes_df=road_routes_df,
            source_warehouse=request.source_warehouse,
            destination_city=request.destination_city,
            demand_weight=int(request.demand_kg),
            disruption_time=request.disruption_time,
            required_delivery_time=request.required_delivery_time,
            repair_duration_hours=request.repair_hours,
            disruption_location=request.disruption_location,
            vehicles_df=vehicles_df
        )
        
        return convert_numpy_types(result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Disruption handling error: {e}")
        raise HTTPException(status_code=500, detail=f"Disruption analysis failed: {str(e)}")


# ---------------------------------------------------
# BASIC ROUTE OPTIMIZATION
# ---------------------------------------------------

# Optimizes a route between two nodes based on specified objective (cost, time, or distance).
@app.get("/optimize")
async def get_optimize(
    source: str,
    destination: str,
    objective: str = "cost"
):
    if source not in nodes or destination not in nodes:
        raise HTTPException(status_code=400,
                            detail="Source or destination not found")

    route = optimize(nodes, edges, source.lower(), destination.lower(), objective)

    if not route:
        raise HTTPException(status_code=404, detail="No route found")

    summary = get_route_summary(route)

    return convert_numpy_types({
        "route": route,
        "summary": summary
    })


# ---------------------------------------------------
# FULL CAPACITY + VEHICLE OPTIMIZATION
# ---------------------------------------------------

# Performs end-to-end logistics optimization including route, vehicle assignment, and scheduling.
@app.post("/optimize-with-capacity")
async def optimize_with_capacity(
    source: str,
    destination: str,
    goods_kg: float,
    objective: str = "cost"
):
    """
    Full logistics optimization including:
    - Route optimization
    - Vehicle capacity assignment
    - Scheduling
    - LLM plan generation
    """

    if source not in nodes or destination not in nodes:
        raise HTTPException(status_code=400,
                            detail="Invalid source or destination")

    if vehicles_df is None or vehicles_df.empty:
        raise HTTPException(
            status_code=400,
            detail="Vehicles data not loaded. Please upload vehicles_mapped.csv first."
        )

    route = optimize(nodes, edges, source.lower(), destination.lower(), objective)

    if not route:
        raise HTTPException(status_code=404, detail="No route found")

    try:
        vdf = vehicles_df.copy()
    except Exception as e:
        raise HTTPException(status_code=500,
                            detail=f"Vehicle data error: {e}")

    legs_output = []
    final_arrival = None

    for leg in route:
        assignment = assign_vehicles_for_leg(
            vdf,
            leg,
            goods_kg,
            objective
        )

        if not assignment:
            raise HTTPException(
                status_code=400,
                detail=f"No vehicles available for {leg['from']} → {leg['to']}"
            )

        legs_output.append(assignment)
        final_arrival = assignment["last_arrival"]

    capacity_data = {
        "total_goods_kg": goods_kg,
        "route": [r["from"] for r in route] + [route[-1]["to"]],
        "objective": objective,
        "legs": legs_output,
        "final_delivery_time": final_arrival
    }

    explanation = generate_transport_plan(capacity_data)

    response = {
        "status": "success",
        "capacity_plan": capacity_data,
        "explanation": explanation
    }
    
    # Convert numpy types to native Python types for JSON serialization
    return convert_numpy_types(response)


# ---------------------------------------------------
# CHAT ENDPOINT FOR NATURAL LANGUAGE QUERIES
# ---------------------------------------------------

# Processes natural language queries to extract routing intent and returns optimized routes with explanations.
@app.post("/chat")
async def chat(message: str = Query(...)):
    """
    Handle natural language queries about route optimization.
    Supports both regular routes and capacity-aware routes.
    """
    global nodes, edges, vehicles_df

    if not nodes or not edges:
        raise HTTPException(status_code=400, detail="Please upload route data first")

    try:
        # Use LLM to parse the query
        query_data = parse_query(message, list(nodes.keys()))
        source = query_data.get("source")
        destination = query_data.get("destination")
        objective = query_data.get("objective", "cost")

        if not source or not destination:
            raise HTTPException(status_code=400,
                                detail="Could not parse source or destination from your query")

        # Check if user is asking for capacity optimization (includes weight/goods info)
        is_capacity_query = any(word in message.lower() for word in ["capacity", "vehicle", "load", "goods_kg", "weight", "kg"])
        
        # Extract weight if mentioned in the query (simplified - looks for patterns like "1000 kg" or "1000kg")
        goods_kg = 1000  # Default
        weight_match = re.search(r'(\d+(?:\.\d+)?)\s*kg', message.lower())
        if weight_match:
            goods_kg = float(weight_match.group(1))

        # Check nodes exist
        if source not in nodes or destination not in nodes:
            source = find_closest_match(source, list(nodes.keys()))
            destination = find_closest_match(destination, list(nodes.keys()))

        # Get optimization route
        route = optimize(nodes, edges, source.lower(), destination.lower(), objective)
        
        if not route:
            raise HTTPException(status_code=404, detail=f"No route found from {source} to {destination}")

        # Format table data for frontend
        table_data = []
        total_distance = 0
        total_time = 0
        total_cost = 0

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

        # Generate explanation
        capacity_plan = None
        if is_capacity_query and vehicles_df is not None and not vehicles_df.empty:
            # Try capacity optimization
            try:
                capacity_result = await optimize_with_capacity(
                    source=source,
                    destination=destination,
                    goods_kg=goods_kg,
                    objective=objective
                )
                explanation = capacity_result.get("explanation", "")
                capacity_plan = capacity_result.get("capacity_plan", {})
                
                # Return capacity plan data
                vehicle_details = f"\n\n🚚 **Vehicle Assignment Plan:**\n"
                for i, leg in enumerate(capacity_plan.get("legs", []), 1):
                    vehicle_details += f"\nLeg {i}: {leg['from'].title()} → {leg['to'].title()}\n"
                    for vehicle in leg.get("vehicles", []):
                        vehicle_details += f"  • {vehicle['vehicle_id']}: {vehicle['load_kg']} kg\n"
                
                explanation = explanation + vehicle_details if explanation else "Capacity plan optimized.\n" + vehicle_details
                
            except Exception as e:
                logger.info(f"Capacity optimization not available: {e}")
                explanation = generate_route_explanation({
                    "objective": objective,
                    "total_distance": total_distance,
                    "total_time": total_time,
                    "total_fuel_cost": total_cost
                }, route)
        else:
            # Regular route explanation
            explanation = generate_route_explanation({
                "objective": objective,
                "total_distance": total_distance,
                "total_time": total_time,
                "total_fuel_cost": total_cost
            }, route)

        # Generate CSV download data (simulated)
        csv_link = base64.b64encode(
            str(table_data).encode()
        ).decode()

        response_data = {
            "status": "success",
            "explanation": explanation,
            "table_data": table_data,
            "csv_download": {
                "link": f"data:text/csv,{csv_link}",
                "filename": f"route_{source}_to_{destination}.csv"
            },
            "route": route
        }
        
        # Include capacity plan if available
        if capacity_plan:
            response_data["capacity_plan"] = capacity_plan
        
        # Convert numpy types to native Python types for JSON serialization
        response_data = convert_numpy_types(response_data)
        return response_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {str(e)}")


# ---------------------------------------------------
# GOOGLE MAPS ROAD DISTANCE
# ---------------------------------------------------

# Calculates real road distance and duration between two coordinates using Google Maps API.
@app.post("/calculate-road-distance")
async def calculate_road_distance(
    from_city: str,
    to_city: str,
    lat_src: float,
    lon_src: float,
    lat_dst: float,
    lon_dst: float
):
    try:
        gm_result = get_road_distance(lat_src, lon_src, lat_dst, lon_dst)

        if gm_result and gm_result["status"] == "OK":
            return {
                "status": "success",
                "distance_km": gm_result["distance_km"],
                "duration_hours": gm_result["duration_hours"]
            }

        return {
            "status": "fallback",
            "distance_km": haversine(lat_src, lon_src, lat_dst, lon_dst)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
