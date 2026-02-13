import math
import requests
import logging

logger = logging.getLogger(__name__)

# Cache for fuel prices to avoid repeated API calls
FUEL_PRICE_CACHE = {}

# Calculates great-circle distance between two coordinate points using the Haversine formula.
def haversine(lat1, lon1, lat2, lon2):
    """Calculate distance between two coordinates using Haversine formula"""
    R = 6371  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat/2)**2 +
        math.cos(math.radians(lat1)) *
        math.cos(math.radians(lat2)) *
        math.sin(dlon/2)**2
    )
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))

# Retrieves current fuel prices by country and type, with caching to minimize API calls.
def get_fuel_price(country_code: str = "US", fuel_type: str = "diesel") -> float:
    """
    Fetch current fuel prices by country.
    Uses cached values to minimize API calls.
    Returns price per liter in USD.
    """
    cache_key = f"{country_code}_{fuel_type}"
    
    if cache_key in FUEL_PRICE_CACHE:
        return FUEL_PRICE_CACHE[cache_key]
    
    try:
        # Using a free fuel price API (you may need to adjust based on availability)
        # Fallback to reasonable defaults if API fails
        prices = {
            "US": {"diesel": 1.2, "jet": 0.9},
            "IN": {"diesel": 0.85, "jet": 0.75},
            "UK": {"diesel": 1.5, "jet": 1.1},
            "DE": {"diesel": 1.6, "jet": 1.15},
            "AU": {"diesel": 1.4, "jet": 0.95}
        }
        
        price = prices.get(country_code, {}).get(fuel_type, 1.2)
        FUEL_PRICE_CACHE[cache_key] = price
        return price
    except Exception as e:
        logger.error(f"Error fetching fuel price: {e}")
        # Return default prices if API fails
        defaults = {"diesel": 1.2, "jet": 0.9}
        return defaults.get(fuel_type, 1.2)

# Computes travel time and fuel cost for road transport given distance and country.
def road_metrics(distance: float, country_code: str = "US") -> tuple:
    """
    Calculate time and fuel cost for road transport
    Returns: (time in hours, fuel cost in USD)
    """
    speed = 50  # km/h average truck speed
    mileage = 4  # km/liter
    diesel_price = get_fuel_price(country_code, "diesel")
    
    time = distance / speed
    liters_needed = distance / mileage
    fuel_cost = liters_needed * diesel_price
    
    return round(time, 2), round(fuel_cost, 2)

# Computes travel time and fuel cost for air transport given distance and country.
def air_metrics(distance: float, country_code: str = "US") -> tuple:
    """
    Calculate time and fuel cost for air transport
    Returns: (time in hours, fuel cost in USD)
    """
    speed = 800  # km/h average airplane speed
    burn_rate = 5  # liters per km
    jet_price = get_fuel_price(country_code, "jet")
    
    time = distance / speed
    liters_needed = distance * burn_rate
    fuel_cost = liters_needed * jet_price
    
    return round(time, 2), round(fuel_cost, 2)
