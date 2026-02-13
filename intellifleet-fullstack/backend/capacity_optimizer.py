from pulp import *
from datetime import datetime, timedelta
import pandas as pd
import logging

logger = logging.getLogger(__name__)

# Vehicle speed and cost estimates by type (km/h and $ per km)
VEHICLE_SPECS = {
    "truck": {"speed": 80, "cost": 0.50},
    "van": {"speed": 90, "cost": 0.40},
    "car": {"speed": 100, "cost": 0.30},
    "auto": {"speed": 60, "cost": 0.20},
    "bike": {"speed": 80, "cost": 0.10},
    "plane": {"speed": 900, "cost": 2.00},
}

# Transforms raw vehicle data into standardized format with IDs, speeds, and costs for optimization.
def prepare_vehicles_df(vehicles_df: pd.DataFrame) -> pd.DataFrame:
    """
    Transform vehicles_mapped.csv format to the format expected by capacity optimizer.
    
    Args:
        vehicles_df: DataFrame with columns [WarehouseName, VehicleType, VehicleCapacity, DepartureTime]
    
    Returns:
        DataFrame with processed vehicle data
    """
    df = vehicles_df.copy()
    
    # Standardize column names
    df["base_city"] = df["WarehouseName"].str.lower().str.strip()
    df["vehicle_type"] = df["VehicleType"].str.lower().str.strip()
    df["capacity_kg"] = pd.to_numeric(df["VehicleCapacity"], errors="coerce")
    df["departure_time"] = df["DepartureTime"].str.strip()
    
    # Generate vehicle IDs
    df["vehicle_id"] = df.groupby("base_city").cumcount() + 1
    df["vehicle_id"] = df.apply(
        lambda row: f"{row['base_city'][:3].upper()}-{row['vehicle_type'][:3].upper()}-{row['vehicle_id']:02d}",
        axis=1
    )
    
    # Add speed and cost based on vehicle type
    df["speed_kmph"] = df["vehicle_type"].map(lambda x: VEHICLE_SPECS.get(x, {}).get("speed", 60))
    df["cost_per_km"] = df["vehicle_type"].map(lambda x: VEHICLE_SPECS.get(x, {}).get("cost", 0.50))
    
    return df[["vehicle_id", "base_city", "capacity_kg", "speed_kmph", "cost_per_km", "departure_time", "vehicle_type"]]

# Optimally assigns vehicles to a single route leg based on capacity and objective using linear programming.
def assign_vehicles_for_leg(
    vehicles_df: pd.DataFrame,
    leg: dict,
    total_goods: float,
    objective: str = "cost"
):
    """
    Assign vehicles dynamically for a single route leg.

    Args:
        vehicles_df: processed vehicle dataframe (after prepare_vehicles_df)
        leg: route segment dict
        total_goods: total kg to transport
        objective: "cost" | "time"

    Returns:
        dict with assigned vehicles and leg summary
    """

    source_city = leg["from"].lower()

    # Filter vehicles available at source city
    available = vehicles_df[
        vehicles_df["base_city"].str.lower() == source_city
    ].copy()

    if available.empty:
        logger.warning(f"No vehicles available at {source_city}")
        return None

    model = LpProblem("Vehicle_Assignment", LpMinimize)

    # Binary variable for each vehicle
    x = LpVariable.dicts("vehicle", available.index, cat="Binary")

    # Objective
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

    # Capacity constraint - must have enough total capacity
    model += lpSum(
        x[i] * available.loc[i, "capacity_kg"]
        for i in available.index
    ) >= total_goods

    # Solve
    model.solve(PULP_CBC_CMD(msg=0))

    if model.status != 1:
        logger.warning("No optimal vehicle assignment found.")
        return None

    assigned = []
    remaining = total_goods
    last_arrival = None

    for i in available.index:
        if x[i].varValue == 1 and remaining > 0:

            capacity = available.loc[i, "capacity_kg"]
            load = min(capacity, remaining)
            remaining -= load

            try:
                departure = datetime.strptime(
                    available.loc[i, "departure_time"],
                    "%H:%M"
                )
            except (ValueError, TypeError):
                departure = datetime.strptime("08:00", "%H:%M")

            travel_time = leg["distance"] / available.loc[i, "speed_kmph"]
            arrival = departure + timedelta(hours=travel_time)

            fuel_cost = round(
                available.loc[i, "cost_per_km"] * leg["distance"],
                2
            )

            assigned.append({
                "vehicle_id": available.loc[i, "vehicle_id"],
                "vehicle_type": available.loc[i, "vehicle_type"],
                "load_kg": round(load, 2),
                "departure": departure.strftime("%H:%M"),
                "arrival": arrival.strftime("%H:%M"),
                "distance": round(leg["distance"], 2),
                "travel_time_hours": round(travel_time, 2),
                "fuel_cost": fuel_cost
            })

            if not last_arrival or arrival > last_arrival:
                last_arrival = arrival

    return {
        "from": leg["from"],
        "to": leg["to"],
        "vehicles": assigned,
        "leg_distance": leg["distance"],
        "leg_time": leg["time"],
        "last_arrival": last_arrival.strftime("%H:%M") if last_arrival else None
    }
