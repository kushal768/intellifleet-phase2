import json
import logging
import re
from typing import List, Dict, Optional

from openai import OpenAI
from config import OPENAI_API_KEY
from fuzzywuzzy import process

logger = logging.getLogger(__name__)

# ---------------------------------------------------
# OpenAI Client
# ---------------------------------------------------

client = OpenAI(api_key=OPENAI_API_KEY)


# ---------------------------------------------------
# FUZZY MATCHING
# ---------------------------------------------------

# Finds the closest matching node name using fuzzy string matching to handle user input variations.
def find_closest_match(user_input: str,
                       available_nodes: List[str],
                       threshold: int = 70) -> str:
    """
    Find closest matching node using fuzzy matching.
    Returns best match if score >= threshold.
    """

    if not user_input or not available_nodes:
        return user_input

    try:
        matches = process.extract(
            user_input.lower(),
            [n.lower() for n in available_nodes],
            limit=1
        )

        if matches and matches[0][1] >= threshold:
            best_lower = matches[0][0]
            for original in available_nodes:
                if original.lower() == best_lower:
                    return original

    except Exception as e:
        logger.warning(f"Fuzzy matching failed: {e}")

    return user_input


# ---------------------------------------------------
# QUERY PARSER
# ---------------------------------------------------

# Parses natural language input using LLM to extract source, destination, and optimization objective.
def parse_query(text: str,
                available_nodes: Optional[List[str]] = None) -> Optional[Dict]:
    """
    Parse natural language query into structured routing intent.
    """

    prompt = f"""
You are a logistics routing assistant.

Extract routing intent from the user's message.

Return ONLY valid JSON (no markdown, no explanations).

Required fields:
- source (string)
- destination (string)
- objective (one of: "cost", "time", "distance")

Optional:
- via (array of strings)

User message:
{text}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=200
        )

        content = response.choices[0].message.content.strip()

        # -------------------------
        # Safe JSON extraction
        # -------------------------
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if not json_match:
                logger.error(f"Invalid LLM response: {content}")
                return None
            result = json.loads(json_match.group())

        # -------------------------
        # Fuzzy location correction
        # -------------------------
        if available_nodes:
            if "source" in result:
                result["source"] = find_closest_match(
                    result["source"], available_nodes)

            if "destination" in result:
                result["destination"] = find_closest_match(
                    result["destination"], available_nodes)

            if "via" in result and isinstance(result["via"], list):
                result["via"] = [
                    find_closest_match(v, available_nodes)
                    for v in result["via"]
                ]

        # -------------------------
        # Objective normalization
        # -------------------------
        objective_map = {
            "cheapest": "cost",
            "lowest cost": "cost",
            "cost": "cost",
            "fastest": "time",
            "quickest": "time",
            "time": "time",
            "shortest": "distance",
            "distance": "distance"
        }

        if "objective" in result:
            obj = result["objective"].lower()
            result["objective"] = objective_map.get(obj, "cost")
        else:
            result["objective"] = "cost"

        # Ensure via is always a list
        if "via" in result and isinstance(result["via"], str):
            result["via"] = [result["via"]]

        result["confidence"] = 0.9

        return result

    except Exception as e:
        logger.error(f"OpenAI parse_query error: {e}")
        return None


# ---------------------------------------------------
# ROUTE EXPLANATION
# ---------------------------------------------------

# Generates a human-readable summary of an optimized route using LLM for clear presentation.
def generate_route_explanation(route_data: Dict,
                               route_segments: List[Dict]) -> str:
    """
    Generate human-friendly explanation of optimized route.
    """

    if not route_segments:
        return "No route found between the specified locations."

    prompt = f"""
Summarize this optimized logistics route in a clear, professional way.

Total Distance: {route_data.get('total_distance', 0)} km
Total Time: {route_data.get('total_time', 0)} hours
Total Fuel Cost: ${route_data.get('total_fuel_cost', 0):.2f}

Route Segments:
"""

    for i, seg in enumerate(route_segments, 1):
        prompt += f"""
{i}. {seg['from']} → {seg['to']}
   Mode: {seg['mode']}
   Distance: {seg['distance']} km
   Time: {seg['time']} hours
   Fuel Cost: ${seg['fuel']:.2f}
"""

    prompt += "\nProvide a concise summary."

    try:
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=300
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.error(f"Explanation generation error: {e}")
        return "Route optimized successfully."


# ---------------------------------------------------
# TRANSPORT CAPACITY PLAN EXPLANATION
# ---------------------------------------------------

# Generates a detailed logistics execution plan with vehicle-by-vehicle breakdown for each route leg.
def generate_transport_plan(capacity_data: Dict) -> str:
    """
    Generate detailed logistics execution plan with vehicle-by-vehicle breakdown.
    """
    
    total_goods_kg = capacity_data.get('total_goods_kg', 0)
    objective = capacity_data.get('objective', 'cost').title()
    final_delivery_time = capacity_data.get('final_delivery_time', 'N/A')
    route = capacity_data.get('route', [])
    legs = capacity_data.get('legs', [])
    
    # Build the plan
    plan = f"""🚚 **DETAILED TRANSPORT EXECUTION PLAN**

📋 **Shipment Overview:**
- **Total Goods:** {total_goods_kg} kg
- **Route:** {' → '.join([str(r).title() for r in route])}
- **Optimization Objective:** {objective}
- **Final Delivery Time:** {final_delivery_time}

---

"""
    
    # Process each leg
    for leg_num, leg in enumerate(legs, 1):
        from_city = leg.get('from', '').title()
        to_city = leg.get('to', '').title()
        
        plan += f"""🛣️ **LEG {leg_num}: {from_city} → {to_city}**

"""
        
        vehicles = leg.get('vehicles', [])
        total_capacity_this_leg = sum(v.get('load_kg', 0) for v in vehicles)
        
        plan += f"**{len(vehicles)} vehicle(s) will transport {total_capacity_this_leg} kg on this leg:**\n\n"
        
        # Add each vehicle
        for vehicle_num, vehicle in enumerate(vehicles, 1):
            vehicle_id = vehicle.get('vehicle_id', f'Vehicle {vehicle_num}')
            load_kg = vehicle.get('load_kg', 0)
            departure = vehicle.get('departure', 'N/A')
            arrival = vehicle.get('arrival', 'N/A')
            distance = vehicle.get('distance', 0)
            travel_time = vehicle.get('travel_time_hours', 0)
            fuel_cost = vehicle.get('fuel_cost', 0)
            
            plan += f"""**{vehicle_id}**

- **Departure ({from_city}):** {departure}
- **Load:** {load_kg} kg
- **Arrival ({to_city}):** {arrival}
- **Distance:** {distance:.2f} km
- **Travel Time:** {travel_time:.2f} hrs
- **Fuel Cost:** ${fuel_cost:.2f}

"""
        
        plan += f"\n✅ **Total {total_capacity_this_leg} kg successfully delivered to {to_city} warehouse.**\n\n"
    
    # Final delivery status
    plan += f"""---

⏱️ **FINAL DELIVERY STATUS**

All {total_goods_kg} kg of goods will be fully delivered by:

🕒 **{final_delivery_time}**

(This is the arrival time of the last vehicle carrying goods.)

---

📦 **Prepared by:** Senior Logistics Planner
"""
    
    return plan
