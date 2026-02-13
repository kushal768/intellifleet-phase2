import requests
import logging
from config import GOOGLE_MAPS_API_KEY

logger = logging.getLogger(__name__)

# Retrieves road traveling distance and duration between two coordinates using Google Maps API,
# with optional waypoint support for multi-leg routes.
def get_road_distance(lat_src: float, lon_src: float, lat_dst: float, lon_dst: float, waypoints: list = None) -> dict:
    """
    Fetch road distance and duration from Google Maps Distance Matrix API.
    
    Args:
        lat_src, lon_src: Starting coordinates
        lat_dst, lon_dst: Destination coordinates
        waypoints: Optional list of intermediate waypoint coordinates [(lat, lon), ...]
                   These are added to the route to ensure the distance calculation
                   follows the planned travel route, not just direct distance.
    
    Returns:
        {
            "distance_km": float,
            "duration_hours": float,
            "status": "OK" or error message
        }
    """
    if not GOOGLE_MAPS_API_KEY:
        logger.warning("Google Maps API key not configured. Falling back to haversine.")
        return None
    
    try:
        url = "https://maps.googleapis.com/maps/api/distancematrix/json"
        
        params = {
            "origins": f"{lat_src},{lon_src}",
            "destinations": f"{lat_dst},{lon_dst}",
            "key": GOOGLE_MAPS_API_KEY,
            "mode": "driving"
        }
        
        # Add waypoints if provided to ensure distance follows the route plan
        if waypoints and len(waypoints) > 0:
            waypoint_str = "|".join([f"{lat},{lon}" for lat, lon in waypoints])
            params["waypoints"] = waypoint_str
            logger.info(f"Route calculation with {len(waypoints)} waypoint(s): {waypoint_str}")
        
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if data.get("status") != "OK":
            logger.warning(f"Google Maps API error: {data.get('status')} - {data.get('error_message', '')}")
            return None
        
        if not data.get("rows") or not data["rows"][0].get("elements"):
            logger.warning("No route found in Google Maps response")
            return None
        
        element = data["rows"][0]["elements"][0]
        
        if element.get("status") != "OK":
            logger.warning(f"Route element error: {element.get('status')}")
            return None
        
        distance_m = element["distance"]["value"]  # in meters
        duration_s = element["duration"]["value"]  # in seconds
        
        logger.info(f"Google Maps route: {distance_m / 1000:.2f}km in {duration_s / 3600:.2f}hrs")
        
        return {
            "distance_km": distance_m / 1000,
            "duration_hours": duration_s / 3600,
            "status": "OK"
        }
    
    except Exception as e:
        logger.error(f"Error calling Google Maps API: {e}")
        return None
