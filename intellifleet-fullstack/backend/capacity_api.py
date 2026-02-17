"""
Standalone Capacity Optimizer API
FastAPI endpoints wrapping capacity_optimizer.py functionality
Run separately from main.py using: uvicorn capacity_api:app --reload --port 8001
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
import pandas as pd
import logging
from capacity_optimizer import prepare_vehicles_df, assign_vehicles_for_leg, VEHICLE_SPECS

# ---------------------------------------------------
# LOGGER SETUP
# ---------------------------------------------------
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# ---------------------------------------------------
# FASTAPI APP SETUP
# ---------------------------------------------------
app = FastAPI(
    title="Capacity Optimizer API",
    description="Vehicle assignment optimization using linear programming",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------
# PYDANTIC MODELS (Request/Response Schemas)
# ---------------------------------------------------

class VehicleInput(BaseModel):
    """Input schema for raw vehicle data."""
    WarehouseName: str = Field(..., description="Warehouse/warehouse city name")
    VehicleType: str = Field(..., description="Type of vehicle (truck, van, car, bike, plane, etc.)")
    VehicleCapacity: int = Field(..., description="Vehicle capacity in kg")
    DepartureTime: str = Field(default="08:00", description="Departure time in HH:MM format")

    class Config:
        json_schema_extra = {
            "example": {
                "WarehouseName": "New York",
                "VehicleType": "truck",
                "VehicleCapacity": 5000,
                "DepartureTime": "08:00"
            }
        }


class VehicleOutput(BaseModel):
    """Output schema for prepared vehicle data."""
    vehicle_id: str
    base_city: str
    vehicle_type: str
    capacity_kg: int
    speed_kmph: int
    cost_per_km: float
    departure_time: str


class LegInput(BaseModel):
    """Input schema for a route leg/segment."""
    from_city: str = Field(..., description="Origin city")
    to_city: str = Field(..., description="Destination city")
    distance: float = Field(..., description="Distance in km")
    time: float = Field(default=0, description="Estimated time in hours")

    class Config:
        json_schema_extra = {
            "example": {
                "from_city": "New York",
                "to_city": "Philadelphia",
                "distance": 95.0,
                "time": 1.8
            }
        }


class AssignedVehicle(BaseModel):
    """Schema for a single assigned vehicle."""
    vehicle_id: str
    vehicle_type: str
    load_kg: float
    departure: str
    arrival: str
    distance: float
    travel_time_hours: float
    fuel_cost: float


class LegAssignmentResponse(BaseModel):
    """Response schema for vehicle assignment result."""
    from_city: str
    to_city: str
    vehicles: List[AssignedVehicle]
    leg_distance: float
    leg_time: float
    last_arrival: Optional[str]


class BatchAssignmentResponse(BaseModel):
    """Response schema for batch assignment."""
    total_legs: int
    assignments_successful: int
    assignments: List[LegAssignmentResponse]


# ---------------------------------------------------
# ENDPOINTS
# ---------------------------------------------------

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "capacity-optimizer"}


@app.post("/prepare-vehicles", response_model=List[VehicleOutput])
async def prepare_vehicles(vehicles: List[VehicleInput]):
    """
    Prepare and standardize raw vehicle data for optimization.
    
    Converts raw vehicle CSV data into standardized format with:
    - Generated vehicle IDs (CITY-TYPE-NUMBER)
    - Speed specifications based on vehicle type
    - Cost per km specifications
    
    Args:
        vehicles: List of raw vehicle data
    
    Returns:
        List of processed vehicles with optimization parameters
    """
    try:
        logger.info(f"Preparing {len(vehicles)} vehicles")
        
        # Convert input models to DataFrame
        vehicles_data = [v.model_dump() for v in vehicles]
        df = pd.DataFrame(vehicles_data)
        
        # Call capacity_optimizer function
        prepared_df = prepare_vehicles_df(df)
        
        # Convert back to list of dicts
        result = prepared_df.to_dict(orient='records')
        
        logger.info(f"Successfully prepared {len(result)} vehicles")
        return result
        
    except Exception as e:
        logger.error(f"Error preparing vehicles: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Error preparing vehicles: {str(e)}")


@app.post("/assign-vehicles-for-leg")
async def assign_vehicles_endpoint(
    vehicles: List[VehicleInput],
    leg: LegInput,
    total_goods_kg: float = Query(..., description="Total goods to transport in kg"),
    objective: str = Query("cost", description="Optimization objective: 'cost' or 'time'")
):
    """
    Assign optimal vehicles for a single route leg using linear programming.
    
    Solves a vehicle assignment problem using CBC solver that:
    - Minimizes either cost or travel time
    - Respects vehicle capacity constraints
    - Assigns multiple vehicles if needed
    
    Args:
        vehicles: List of available vehicles
        leg: Route leg with from_city, to_city, distance, time
        total_goods_kg: Total cargo weight in kg
        objective: "cost" (default) or "time"
    
    Returns:
        Assignment result with selected vehicles, loads, and times
    """
    try:
        logger.info(f"Assigning vehicles for leg {leg.from_city} → {leg.to_city} ({total_goods_kg} kg, objective={objective})")
        
        # Validate objective
        if objective not in ["cost", "time"]:
            raise HTTPException(status_code=400, detail="Objective must be 'cost' or 'time'")
        
        # Prepare vehicles
        vehicles_data = [v.model_dump() for v in vehicles]
        vehicles_df = pd.DataFrame(vehicles_data)
        prepared_df = prepare_vehicles_df(vehicles_df)
        
        # Format leg for capacity_optimizer
        leg_dict = {
            "from": leg.from_city,
            "to": leg.to_city,
            "distance": leg.distance,
            "time": leg.time
        }
        
        # Call capacity_optimizer function
        result = assign_vehicles_for_leg(
            prepared_df,
            leg_dict,
            total_goods_kg,
            objective=objective
        )
        
        if result is None:
            raise HTTPException(
                status_code=400,
                detail=f"Could not assign vehicles. No available vehicles at {leg.from_city} or infeasible solution."
            )
        
        logger.info(f"Successfully assigned {len(result['vehicles'])} vehicles")
        return result
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error assigning vehicles: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error assigning vehicles: {str(e)}")


@app.post("/batch-assign-vehicles", response_model=BatchAssignmentResponse)
async def batch_assign_vehicles(
    vehicles: List[VehicleInput],
    legs: List[LegInput],
    total_goods_kg: float = Query(..., description="Total goods to transport in kg"),
    objective: str = Query("cost", description="Optimization objective: 'cost' or 'time'")
):
    """
    Assign vehicles for multiple route legs (batch processing).
    
    Processes multiple legs sequentially, assigning optimal vehicles for each.
    
    Args:
        vehicles: Shared list of available vehicles
        legs: List of route legs to process
        total_goods_kg: Total cargo across all legs
        objective: "cost" (default) or "time"
    
    Returns:
        Batch response with all successful assignments
    """
    try:
        logger.info(f"Batch processing {len(legs)} legs with {len(vehicles)} vehicles")
        
        # Prepare vehicles once
        vehicles_data = [v.model_dump() for v in vehicles]
        vehicles_df = pd.DataFrame(vehicles_data)
        prepared_df = prepare_vehicles_df(vehicles_df)
        
        assignments = []
        
        for idx, leg in enumerate(legs, 1):
            logger.info(f"Processing leg {idx}/{len(legs)}: {leg.from_city} → {leg.to_city}")
            
            leg_dict = {
                "from": leg.from_city,
                "to": leg.to_city,
                "distance": leg.distance,
                "time": leg.time
            }
            
            result = assign_vehicles_for_leg(
                prepared_df,
                leg_dict,
                total_goods_kg,
                objective=objective
            )
            
            if result is not None:
                assignments.append(result)
            else:
                logger.warning(f"Could not assign vehicles for leg {leg.from_city} → {leg.to_city}")
        
        logger.info(f"Batch completed: {len(assignments)}/{len(legs)} legs successful")
        
        return {
            "total_legs": len(legs),
            "assignments_successful": len(assignments),
            "assignments": assignments
        }
        
    except Exception as e:
        logger.error(f"Error in batch assignment: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error in batch assignment: {str(e)}")


@app.get("/vehicle-specs", response_model=Dict[str, Dict[str, float]])
async def get_vehicle_specs():
    """
    Get specification details for all vehicle types.
    
    Returns:
        Dictionary with vehicle types and their speed (kmph) and cost ($ per km)
    """
    try:
        return VEHICLE_SPECS
    except Exception as e:
        logger.error(f"Error fetching vehicle specs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching vehicle specs: {str(e)}")


# ---------------------------------------------------
# ROOT ENDPOINT
# ---------------------------------------------------

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Capacity Optimizer API",
        "version": "1.0.0",
        "description": "Vehicle assignment optimization service",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "prepare_vehicles": "/prepare-vehicles",
            "assign_single_leg": "/assign-vehicles-for-leg",
            "batch_assign": "/batch-assign-vehicles",
            "vehicle_specs": "/vehicle-specs"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
