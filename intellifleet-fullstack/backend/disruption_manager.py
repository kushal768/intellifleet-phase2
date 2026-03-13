"""
Disruption Manager Module
Handles route disruptions, repairs, and alternative warehouse routing
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from utils import haversine
import json

class DisruptionManager:
    """Manages route disruptions and finds alternative fulfillment options"""

    def __init__(self,
                 warehouses_df: pd.DataFrame,
                 road_routes_df: pd.DataFrame,
                 vehicles_df: pd.DataFrame = None):
        """
        Initialize DisruptionManager
        
        Args:
            warehouses_df: DataFrame with warehouse data (City, Inventory, ReorderLevel)
            road_routes_df: DataFrame with road route data (source_city, destination_city, lat_src, lon_src, lat_dst, lon_dst)
            vehicles_df: (optional) DataFrame of vehicles for transport planning
        """
        self.warehouses_df = warehouses_df
        self.road_routes_df = road_routes_df
        # vehicles_df is optional; used when building transport plans for recommendations
        self.vehicles_df = vehicles_df

    def find_nearest_warehouses(
        self,
        origin_lat: float,
        origin_lon: float,
        demand_weight: int,
        exclude_cities: List[str] = None,
        max_results: int = None
    ) -> List[Dict]:
        """
        Find nearest warehouses that can fulfill demand
        
        Args:
            origin_lat: Latitude of disruption point
            origin_lon: Longitude of disruption point  
            demand_weight: Weight of goods to deliver (kg)
            exclude_cities: Cities to exclude from search
            max_results: Maximum warehouses to return (None = all warehouses)
            
        Returns:
            List of warehouse options sorted by distance
        """
        if exclude_cities is None:
            exclude_cities = []

        # Build city coordinates map from road routes
        city_coords = {}
        for _, route in self.road_routes_df.iterrows():
            src_city = str(route.get('source_city', '')).lower().strip()
            dst_city = str(route.get('destination_city', '')).lower().strip()
            
            if src_city and src_city not in city_coords:
                city_coords[src_city] = (route.get('lat_src', 0), route.get('lon_src', 0))
            if dst_city and dst_city not in city_coords:
                city_coords[dst_city] = (route.get('lat_dst', 0), route.get('lon_dst', 0))

        # Filter warehouses that have inventory available (for single or combination fulfillment)
        available_warehouses = []
        
        for _, warehouse in self.warehouses_df.iterrows():
            city = warehouse.get('City', '').strip().lower()
            
            # Skip excluded cities
            if city in [c.lower() for c in exclude_cities]:
                continue
            
            inventory = warehouse.get('Inventory', 0)
            reorder_level = warehouse.get('ReorderLevel', 0)
            
            # Check if warehouse has inventory above reorder level (available to use)
            # Note: Don't check demand here - let combinations decide if pairs can fulfill
            if inventory > reorder_level:
                # Get coordinates from city_coords map
                coords = city_coords.get(city, (0, 0))
                warehouse_lat, warehouse_lon = coords
                
                # Available quantity is inventory minus reorder level
                available_to_use = inventory - reorder_level
                
                available_warehouses.append({
                    'city': str(city),
                    'Name': str(warehouse.get('Name', city)),
                    'inventory': int(inventory),
                    'reorder_level': int(reorder_level),
                    'available_quantity': int(available_to_use),
                    'lat': float(warehouse_lat),
                    'lon': float(warehouse_lon)
                })
        
        # Calculate distances
        for warehouse in available_warehouses:
            distance = haversine(
                origin_lat, origin_lon,
                warehouse['lat'], warehouse['lon']
            )
            warehouse['distance_km'] = float(distance)
        
        # Sort by distance
        available_warehouses.sort(key=lambda x: x['distance_km'])
        
        return available_warehouses if max_results is None else available_warehouses[:max_results]

    def estimate_delivery_time(
        self,
        source_city: str,
        destination_city: str,
        repair_duration_hours: int = 5,
        disruption_time: str = "22:00",
        required_delivery_time: str = "10:00"
    ) -> Dict:
        """
        Estimate delivery time for given route considering disruption and repair.
        Uses direct route if available, otherwise estimates based on haversine distance.
        
        Args:
            source_city: Source warehouse city
            destination_city: Destination city
            repair_duration_hours: Hours needed for repair
            disruption_time: Time when route was disrupted (HH:MM)
            required_delivery_time: Required delivery time (HH:MM)
            
        Returns:
            Dictionary with delivery estimates and feasibility
        """
        # Find route in road routes (direct route)
        route_match = self.road_routes_df[
            (self.road_routes_df['source_city'].str.lower() == source_city.lower()) &
            (self.road_routes_df['destination_city'].str.lower() == destination_city.lower())
        ]
        
        distance_km = None
        if not route_match.empty:
            # Use actual route distance
            route = route_match.iloc[0]
            distance_km = haversine(
                route['lat_src'], route['lon_src'],
                route['lat_dst'], route['lon_dst']
            )
        else:
            # Estimate distance using coordinates from available routes
            # Build city coordinates map
            city_coords = {}
            for _, route in self.road_routes_df.iterrows():
                src_city = str(route.get('source_city', '')).lower().strip()
                dst_city = str(route.get('destination_city', '')).lower().strip()
                
                if src_city and src_city not in city_coords:
                    city_coords[src_city] = (route.get('lat_src', 0), route.get('lon_src', 0))
                if dst_city and dst_city not in city_coords:
                    city_coords[dst_city] = (route.get('lat_dst', 0), route.get('lon_dst', 0))
            
            src_city_lower = source_city.lower()
            dst_city_lower = destination_city.lower()
            
            if src_city_lower in city_coords and dst_city_lower in city_coords:
                # Estimate using coordinates
                src_lat, src_lon = city_coords[src_city_lower]
                dst_lat, dst_lon = city_coords[dst_city_lower]
                distance_km = haversine(src_lat, src_lon, dst_lat, dst_lon)
            else:
                # No coordinates found - return error
                return {
                    'feasible': False,
                    'error': f'No route or coordinates found from {source_city} to {destination_city}',
                    'estimated_delivery_time': None,
                    'meets_requirement': False
                }
        
        try:
            # Parse disruption time
            disruption_hour, disruption_min = map(int, disruption_time.split(':'))
            disruption_dt = datetime.strptime(f"{disruption_hour:02d}:{disruption_min:02d}", "%H:%M")
            
            # Calculate repair completion time
            repair_completion = disruption_dt + timedelta(hours=repair_duration_hours)
            
            # Calculate travel time (60 km/h average)
            travel_hours = distance_km / 60
            
            # Estimate arrival time
            estimated_arrival = repair_completion + timedelta(hours=travel_hours)
            
            # Handle day rollover
            if estimated_arrival.day > disruption_dt.day or estimated_arrival.hour < disruption_dt.hour:
                estimated_arrival_str = f"Next day {estimated_arrival.strftime('%H:%M')}"
                arrival_day_offset = 1
            else:
                estimated_arrival_str = estimated_arrival.strftime("%H:%M")
                arrival_day_offset = 0
            
            # Parse required delivery time
            req_hour, req_min = map(int, required_delivery_time.split(':'))
            req_dt_today = datetime.strptime(f"{req_hour:02d}:{req_min:02d}", "%H:%M")
            
            # Compare delivery times - accounting for day boundaries
            if arrival_day_offset > 0:
                # Arrives next day, so misses today's deadline
                meets_requirement = False
                time_delta = (24 - disruption_hour + req_hour) + (estimated_arrival.hour - req_hour) + (estimated_arrival.minute - req_min) / 60
            else:
                # Same day arrival
                meets_requirement = estimated_arrival >= req_dt_today
                time_delta = (estimated_arrival - req_dt_today).total_seconds() / 3600
            
            return {
                'feasible': True,
                'distance_km': float(round(distance_km, 2)),
                'travel_hours': float(round(travel_hours, 2)),
                'repair_hours': int(repair_duration_hours),
                'disruption_time': str(disruption_time),
                'repair_completion_time': str(repair_completion.strftime("%H:%M")),
                'estimated_delivery_time': str(estimated_arrival_str),
                'required_delivery_time': str(required_delivery_time),
                'meets_requirement': bool(meets_requirement),
                'time_delta_hours': float(round(time_delta, 2))
            }
        except Exception as e:
            return {
                'feasible': False,
                'error': f'Error estimating delivery: {str(e)}',
                'estimated_delivery_time': None,
                'meets_requirement': False
            }

    def find_warehouse_combinations(
        self,
        source_warehouse: str,
        destination_city: str,
        demand_weight: int,
        disruption_time: str,
        required_delivery_time: str,
        repair_duration_hours: int,
        available_warehouses: List[Dict],
        max_combinations: int = 3
    ) -> List[Dict]:
        """
        Find best combinations of 2 warehouses to fulfill demand
        
        Args:
            source_warehouse: Source warehouse city
            destination_city: Destination city
            demand_weight: Total weight to deliver
            disruption_time: Time of disruption
            required_delivery_time: Required delivery deadline
            repair_duration_hours: Repair time
            available_warehouses: List of available warehouses
            max_combinations: Max combinations to return
            
        Returns:
            List of viable warehouse combination options
        """
        combinations = []
        
        # Try all combinations of 2 warehouses; only consider pairs when
        # neither warehouse alone can satisfy the full demand.  This avoids
        # producing options where the second warehouse would carry 0 kg.
        for i in range(len(available_warehouses)):
            for j in range(i + 1, len(available_warehouses)):
                wh1 = available_warehouses[i]
                wh2 = available_warehouses[j]

                # if one warehouse already has enough inventory on its own, skip
                if wh1['available_quantity'] >= demand_weight or wh2['available_quantity'] >= demand_weight:
                    continue

                # Check if combined inventory can meet demand
                combined_available = (wh1['available_quantity'] + wh2['available_quantity'])

                if combined_available >= demand_weight:
                    # Calculate delivery time for both warehouses (max of both)
                    delivery_analysis_1 = self.estimate_delivery_time(
                        source_warehouse, wh1['city'],
                        repair_duration_hours, disruption_time, required_delivery_time
                    )
                    delivery_analysis_2 = self.estimate_delivery_time(
                        source_warehouse, wh2['city'],
                        repair_duration_hours, disruption_time, required_delivery_time
                    )

                    # Use the later delivery time as bottleneck
                    meets_req_1 = delivery_analysis_1.get('meets_requirement', False)
                    meets_req_2 = delivery_analysis_2.get('meets_requirement', False)
                    meets_requirement = meets_req_1 and meets_req_2

                    # Determine which warehouse delivers latest (bottleneck)
                    time_1 = delivery_analysis_1.get('estimated_delivery_time', '')
                    time_2 = delivery_analysis_2.get('estimated_delivery_time', '')

                    # Handle None or empty values
                    if not time_1:
                        time_1 = ''
                    if not time_2:
                        time_2 = ''

                    # Compare times - prefer "Next day" times if present
                    if 'Next day' in str(time_1) and 'Next day' not in str(time_2):
                        bottleneck_time = time_1
                    elif 'Next day' in str(time_2) and 'Next day' not in str(time_1):
                        bottleneck_time = time_2
                    elif 'Next day' in str(time_1) and 'Next day' in str(time_2):
                        # Both are next day, compare the actual times
                        bottleneck_time = time_1 if str(time_1) > str(time_2) else time_2
                    else:
                        # Both are same day
                        bottleneck_time = time_1 if (str(time_1) or '00:00') > (str(time_2) or '00:00') else time_2

                    # How to split demand (proportional to inventory)
                    split1 = min(int(wh1['available_quantity']), demand_weight)
                    split2 = demand_weight - split1

                    combinations.append({
                        'warehouse1_city': str(wh1['city']),
                        'warehouse1_name': str(wh1.get('Name', wh1['city'])),
                        'warehouse1_delivery': split1,
                        'warehouse1_capacity': int(wh1['available_quantity']),
                        'warehouse2_city': str(wh2['city']),
                        'warehouse2_name': str(wh2.get('Name', wh2['city'])),
                        'warehouse2_delivery': split2,
                        'warehouse2_capacity': int(wh2['available_quantity']),
                        'combined_delivery_time': str(bottleneck_time),
                        'meets_requirement': bool(meets_requirement),
                        'distance_sum': float(round(wh1['distance_km'] + wh2['distance_km'], 2))
                    })
        
        # Sort by: 1. Meets requirement (True first), 2. Distance sum (closer first)
        combinations.sort(key=lambda x: (not x['meets_requirement'], x['distance_sum']))
        
        return combinations[:max_combinations]

    def _assign_transport(self, source_city: str, dest_city: str, load_kg: float):
        """Create a simple transport assignment using available vehicles.
        For intercity routes, only trucks are used.

        Returns the output of `assign_vehicles_for_leg` from capacity_optimizer or
        ``None`` if vehicles data is not available.
        """
        if self.vehicles_df is None:
            return None
        try:
            from capacity_optimizer import assign_vehicles_for_leg, prepare_vehicles_df
        except ImportError:
            return None

        # make sure the vehicles dataframe is in the expected format
        vehicles = self.vehicles_df.copy()
        if 'base_city' not in vehicles.columns:
            try:
                vehicles = prepare_vehicles_df(vehicles)
            except Exception:
                vehicles = self.vehicles_df.copy()
        
        # Filter to only trucks for intercity routes
        vehicles = vehicles[vehicles['vehicle_type'].str.lower() == 'truck']

        # determine distance/time from road routes or haversine fallback
        route_match = self.road_routes_df[(self.road_routes_df['source_city'].str.lower() == source_city.lower()) &
                                         (self.road_routes_df['destination_city'].str.lower() == dest_city.lower())]
        if not route_match.empty:
            route = route_match.iloc[0]
            distance = haversine(route['lat_src'], route['lon_src'], route['lat_dst'], route['lon_dst'])
        else:
            # estimate distance using any available coords
            coords = {}
            for _, r in self.road_routes_df.iterrows():
                coords[str(r.get('source_city','')).lower().strip()] = (r.get('lat_src',0), r.get('lon_src',0))
                coords[str(r.get('destination_city','')).lower().strip()] = (r.get('lat_dst',0), r.get('lon_dst',0))
            if source_city.lower() in coords and dest_city.lower() in coords:
                s_lat, s_lon = coords[source_city.lower()]
                d_lat, d_lon = coords[dest_city.lower()]
                distance = haversine(s_lat, s_lon, d_lat, d_lon)
            else:
                # cannot compute
                distance = 0
        travel_time = distance / 60 if distance else 0
        leg = {"from": source_city.lower(), "to": dest_city.lower(),
               "distance": distance, "time": travel_time}
        return assign_vehicles_for_leg(vehicles, leg, load_kg)


    def _get_vehicle_departure_from_warehouse(self, warehouse_city: str, destination_city: str, load_kg: float) -> Dict:
        """
        Get vehicle departure and arrival information from a warehouse to destination.
        
        Args:
            warehouse_city: The alternate warehouse city
            destination_city: The final destination city
            load_kg: Load in kg
            
        Returns:
            Dict with vehicle_id, departure_time, arrival_time or empty dict if no vehicles found
        """
        transport = self._assign_transport(warehouse_city, destination_city, load_kg)
        if transport and transport.get('vehicles'):
            v = transport['vehicles'][0]
            return {
                'vehicle_id': v.get('vehicle_id', 'N/A'),
                'departure_time': v.get('departure', 'N/A'),
                'arrival_time': v.get('arrival', 'N/A')
            }
        return {}

    def _get_bottleneck_time(self, arrival_time_list: List[str]) -> str:
        """
        Calculate the bottleneck (maximum) arrival time from a list of arrival times.
        Handles times in HH:MM format.
        
        Args:
            arrival_time_list: List of arrival times as strings in HH:MM format
            
        Returns:
            The latest arrival time
        """
        if not arrival_time_list:
            return 'N/A'
        
        valid_times = [t for t in arrival_time_list if t and t != 'N/A']
        if not valid_times:
            return 'N/A'
        
        # For simple HH:MM comparison, we can use string comparison if they're all same day
        # Sort and return the latest
        return max(valid_times)

    def handle_disruption(
        self,
        source_warehouse: str,
        destination_city: str,
        demand_weight: int,
        disruption_time: str = "22:00",
        required_delivery_time: str = "10:00",
        repair_duration_hours: int = 5,
        max_alternative_warehouses: int = 3,
        disruption_location: Optional[str] = None
    ) -> Dict:
        """
        Comprehensive disruption handling with alternative warehouse routing
        
        Args:
            source_warehouse: Source warehouse city
            destination_city: Final destination city
            demand_weight: Weight of goods in kg
            disruption_time: Time when disruption occurred
            required_delivery_time: Required delivery deadline
            repair_duration_hours: Hours needed to repair
            max_alternative_warehouses: Max alternatives to find
            disruption_location: Optional city where disruption occurred (for finding nearby warehouses)
            
        Returns:
            Dictionary with disruption analysis and recommendations
        """
        
        # First, check if original route can still meet deadline after repair
        original_route_analysis = self.estimate_delivery_time(
            source_warehouse,
            destination_city,
            repair_duration_hours,
            disruption_time,
            required_delivery_time
        )
        
        result = {
            'disruption_time': str(disruption_time),
            'required_delivery_time': str(required_delivery_time),
            'repair_duration_hours': int(repair_duration_hours),
            'demand_weight_kg': int(demand_weight),
            'original_route': {
                'source': str(source_warehouse),
                'destination': str(destination_city),
                'analysis': original_route_analysis
            },
            'original_feasible': bool(original_route_analysis.get('meets_requirement', False)),
            'alternative_warehouses': []
        }
        
        # If original route is feasible, return it as primary solution
        if original_route_analysis.get('meets_requirement'):
            result['recommendation'] = 'PROCEED_WITH_REPAIR'
            result['message'] = (
                f"✅ **Original route still viable**\n"
                f"- Source: {source_warehouse} → Destination: {destination_city}\n"
                f"- Disruption at {disruption_time}, repair {repair_duration_hours}h\n"
                f"- Estimated delivery: {original_route_analysis['estimated_delivery_time']} (meets deadline)\n"
                f"Proceed with repair and continue on original path."
            )
            # Ensure the result is fully JSON-serializable (convert any numpy/datetime types)
            return json.loads(json.dumps(result, default=str))
        
        # Find alternative warehouses
        # Get coordinates for the original destination to find nearby alternatives
        # Build city coordinates map from road routes
        city_coords = {}
        for _, route in self.road_routes_df.iterrows():
            src_city = str(route.get('source_city', '')).lower().strip()
            dst_city = str(route.get('destination_city', '')).lower().strip()
            
            if src_city and src_city not in city_coords:
                city_coords[src_city] = (route.get('lat_src', 0), route.get('lon_src', 0))
            if dst_city and dst_city not in city_coords:
                city_coords[dst_city] = (route.get('lat_dst', 0), route.get('lon_dst', 0))
        
        dest_city_lower = destination_city.lower()
        if dest_city_lower in city_coords:
            dest_lat, dest_lon = city_coords[dest_city_lower]
        else:
            dest_lat, dest_lon = 0, 0
        
        # If disruption location is specified, find warehouses near disruption point instead of destination
        if disruption_location:
            disruption_city_lower = disruption_location.lower()
            if disruption_city_lower in city_coords:
                search_lat, search_lon = city_coords[disruption_city_lower]
                all_alternatives = self.find_nearest_warehouses(
                    search_lat,
                    search_lon,
                    demand_weight,
                    exclude_cities=[destination_city, source_warehouse, disruption_location],
                    max_results=None  # Get ALL warehouses
                )
            else:
                # If disruption location not found in coordinates, fall back to destination-based search
                all_alternatives = self.find_nearest_warehouses(
                    dest_lat,
                    dest_lon,
                    demand_weight,
                    exclude_cities=[destination_city, source_warehouse],
                    max_results=None  # Get ALL warehouses
                )
        else:
            all_alternatives = self.find_nearest_warehouses(
                dest_lat,
                dest_lon,
                demand_weight,
                exclude_cities=[destination_city, source_warehouse],
                max_results=None  # Get ALL warehouses
            )
        
        # Analyze each alternative
        for alt_warehouse in all_alternatives:
            alt_city = alt_warehouse['city']
            
            delivery_analysis = self.estimate_delivery_time(
                source_warehouse,
                alt_city,
                repair_duration_hours,
                disruption_time,
                required_delivery_time
            )
            
            result['alternative_warehouses'].append({
                'warehouse_city': str(alt_city),
                'warehouse_name': str(alt_warehouse.get('Name', alt_city)),
                'distance_from_destination_km': float(round(alt_warehouse['distance_km'], 2)),
                'available_inventory': int(alt_warehouse['available_quantity']),
                'inventory': int(alt_warehouse['inventory']),
                'reorder_level': int(alt_warehouse['reorder_level']),
                'delivery_analysis': delivery_analysis,
                'feasible': bool(delivery_analysis.get('feasible', False) and delivery_analysis.get('meets_requirement', False)),
                'can_fulfill_demand': bool(alt_warehouse['available_quantity'] >= demand_weight)
            })
        
        # Check if any single warehouse can fulfill demand AND meet deadline
        feasible_alternatives = [
            alt for alt in result['alternative_warehouses']
            if alt.get('feasible')
        ]
        
        # Check if demand exceeds all single warehouse capacities
        max_single_warehouse_capacity = max(
            [alt['available_inventory'] for alt in result['alternative_warehouses']], 
            default=0
        )
        demand_exceeds_single_capacity = demand_weight > max_single_warehouse_capacity
        
        if feasible_alternatives and not demand_exceeds_single_capacity:
            best_alt = feasible_alternatives[0]
            result['recommendation'] = 'DIVERT_TO_WAREHOUSE'
            result['recommended_warehouse'] = best_alt['warehouse_city']
            result['recommended_warehouse_name'] = best_alt['warehouse_name']
            result['estimated_delivery_time'] = best_alt['delivery_analysis'].get('estimated_delivery_time')

            # try to compute vehicle schedule
            transport = self._assign_transport(source_warehouse, best_alt['warehouse_city'], demand_weight)
            result['transport_plan'] = transport

            # build a more detailed message
            msg_lines = []
            msg_lines.append("⚠️ **Disruption detected**")
            msg_lines.append(f"- Route: {source_warehouse} → {destination_city}")
            msg_lines.append(f"- Disruption at {disruption_time}, repair duration {repair_duration_hours}h")
            msg_lines.append(f"- Demand: {demand_weight} kg")
            msg_lines.append("")
            msg_lines.append(f"🚚 **Recommendation:** divert to warehouse {best_alt['warehouse_name']} ({best_alt['warehouse_city']})")
            msg_lines.append(f"- Available capacity: {best_alt['available_inventory']} kg")
            msg_lines.append(f"- Estimated arrival: {best_alt['delivery_analysis'].get('estimated_delivery_time')} (deadline {required_delivery_time})")

            if transport and transport.get('vehicles'):
                v = transport['vehicles'][0]
                msg_lines.append(f"- Vehicle {v['vehicle_id']} departs {source_warehouse.title()} at {v['departure']} and arrives at {best_alt['warehouse_city'].title()} at {v['arrival']}")
            result['message'] = "\n".join(msg_lines)
        else:
            # No single warehouse meets deadline requirement OR demand exceeds single warehouse capacity
            # Try multi-warehouse combinations
            result['recommendation'] = 'ESCALATE'
            result['warehouse_combinations'] = []
            
            # Find viable warehouse combinations (2 warehouses)
            warehouse_combinations = self.find_warehouse_combinations(
                source_warehouse,
                destination_city,
                demand_weight,
                disruption_time,
                required_delivery_time,
                repair_duration_hours,
                all_alternatives,
                max_combinations=10  # Get more combinations to find best option
            )
            
            # Check if any combination meets the deadline
            feasible_combinations = [c for c in warehouse_combinations if c.get('meets_requirement')]
            
            # PRIORITY: If demand exceeds single capacity, prefer multi-warehouse even if not deadline-feasible
            if demand_exceeds_single_capacity and not feasible_combinations and warehouse_combinations:
                # Use best multi-warehouse combo to meet demand, even if deadline not met
                best_combo = warehouse_combinations[0]
                
                # Get vehicle departure info from alternate warehouses to destination
                wh1_vehicle_info = self._get_vehicle_departure_from_warehouse(
                    best_combo['warehouse1_city'], 
                    destination_city, 
                    best_combo['warehouse1_delivery']
                )
                wh2_vehicle_info = self._get_vehicle_departure_from_warehouse(
                    best_combo['warehouse2_city'], 
                    destination_city, 
                    best_combo['warehouse2_delivery']
                ) if best_combo.get('warehouse2_delivery', 0) > 0 else {}
                
                # Calculate bottleneck time based on vehicle arrival times
                arrival_times = [wh1_vehicle_info.get('arrival_time', 'N/A')]
                if best_combo.get('warehouse2_delivery', 0) > 0:
                    arrival_times.append(wh2_vehicle_info.get('arrival_time', 'N/A'))
                bottleneck_time = self._get_bottleneck_time(arrival_times)
                
                result['recommendation'] = 'DIVERT_TO_MULTIPLE_WAREHOUSES'
                result['warehouse_combinations'] = [{
                    'warehouse1_city': best_combo['warehouse1_city'],
                    'warehouse1_name': best_combo['warehouse1_name'],
                    'warehouse1_delivery': int(best_combo['warehouse1_delivery']),
                    'warehouse1_capacity': int(best_combo['warehouse1_capacity']),
                    'warehouse1_vehicle_id': wh1_vehicle_info.get('vehicle_id', 'N/A'),
                    'warehouse1_vehicle_departure': wh1_vehicle_info.get('departure_time', 'N/A'),
                    'warehouse1_vehicle_arrival': wh1_vehicle_info.get('arrival_time', 'N/A'),
                    'warehouse2_city': best_combo['warehouse2_city'],
                    'warehouse2_name': best_combo['warehouse2_name'],
                    'warehouse2_delivery': int(best_combo['warehouse2_delivery']),
                    'warehouse2_capacity': int(best_combo['warehouse2_capacity']),
                    'warehouse2_vehicle_id': wh2_vehicle_info.get('vehicle_id', 'N/A'),
                    'warehouse2_vehicle_departure': wh2_vehicle_info.get('departure_time', 'N/A'),
                    'warehouse2_vehicle_arrival': wh2_vehicle_info.get('arrival_time', 'N/A'),
                    'combined_delivery_time': bottleneck_time
                }]
                msg_lines = [
                    "⚠️ **Disruption detected**",
                    f"- Route: {source_warehouse} → {destination_city}",
                    f"- Disruption at {disruption_time}, repair duration {repair_duration_hours}h",
                    f"- Demand: {demand_weight} kg (exceeds single warehouse capacity of {max_single_warehouse_capacity} kg)",
                    "",
                    "🚚 **Recommendation:** distribute across multiple warehouses",
                    f"  * {best_combo['warehouse1_name']} ({best_combo['warehouse1_city']}) – {int(best_combo['warehouse1_delivery'])}kg",
                    f"    - Vehicle {wh1_vehicle_info.get('vehicle_id', 'N/A')} departs from {best_combo['warehouse1_city'].title()} at {wh1_vehicle_info.get('departure_time', 'N/A')} towards {destination_city.title()}, arrives at {wh1_vehicle_info.get('arrival_time', 'N/A')}",
                    f"  * {best_combo['warehouse2_name']} ({best_combo['warehouse2_city']}) – {int(best_combo['warehouse2_delivery'])}kg",
                    f"    - Vehicle {wh2_vehicle_info.get('vehicle_id', 'N/A')} departs from {best_combo['warehouse2_city'].title()} at {wh2_vehicle_info.get('departure_time', 'N/A')} towards {destination_city.title()}, arrives at {wh2_vehicle_info.get('arrival_time', 'N/A')}",
                    f"- Final delivery by {bottleneck_time}"
                ]
                result['message'] = "\n".join(msg_lines)
            elif feasible_combinations:
                # Use the best combination that meets deadline
                best_combo = feasible_combinations[1] if len(feasible_combinations) > 1 and feasible_combinations[0].get('warehouse2_delivery',0)==0 else feasible_combinations[0]
                
                # Get vehicle departure info from alternate warehouses to destination
                wh1_vehicle_info = self._get_vehicle_departure_from_warehouse(
                    best_combo['warehouse1_city'], 
                    destination_city, 
                    best_combo['warehouse1_delivery']
                )
                wh2_vehicle_info = self._get_vehicle_departure_from_warehouse(
                    best_combo['warehouse2_city'], 
                    destination_city, 
                    best_combo['warehouse2_delivery']
                ) if best_combo.get('warehouse2_delivery', 0) > 0 else {}
                
                # Calculate bottleneck time based on vehicle arrival times
                arrival_times = [wh1_vehicle_info.get('arrival_time', 'N/A')]
                if best_combo.get('warehouse2_delivery', 0) > 0:
                    arrival_times.append(wh2_vehicle_info.get('arrival_time', 'N/A'))
                bottleneck_time = self._get_bottleneck_time(arrival_times)
                
                result['recommendation'] = 'DIVERT_TO_MULTIPLE_WAREHOUSES'
                result['warehouse_combinations'] = [{
                    'warehouse1_city': best_combo['warehouse1_city'],
                    'warehouse1_name': best_combo['warehouse1_name'],
                    'warehouse1_delivery': int(best_combo['warehouse1_delivery']),
                    'warehouse1_capacity': int(best_combo['warehouse1_capacity']),
                    'warehouse1_vehicle_id': wh1_vehicle_info.get('vehicle_id', 'N/A'),
                    'warehouse1_vehicle_departure': wh1_vehicle_info.get('departure_time', 'N/A'),
                    'warehouse1_vehicle_arrival': wh1_vehicle_info.get('arrival_time', 'N/A'),
                    'warehouse2_city': best_combo['warehouse2_city'],
                    'warehouse2_name': best_combo['warehouse2_name'],
                    'warehouse2_delivery': int(best_combo['warehouse2_delivery']),
                    'warehouse2_capacity': int(best_combo['warehouse2_capacity']),
                    'warehouse2_vehicle_id': wh2_vehicle_info.get('vehicle_id', 'N/A'),
                    'warehouse2_vehicle_departure': wh2_vehicle_info.get('departure_time', 'N/A'),
                    'warehouse2_vehicle_arrival': wh2_vehicle_info.get('arrival_time', 'N/A'),
                    'combined_delivery_time': bottleneck_time
                }]
                # structured message
                msg_lines = [
                    "⚠️ **Disruption detected**",
                    f"- Route: {source_warehouse} → {destination_city}",
                    f"- Disruption at {disruption_time}, repair duration {repair_duration_hours}h",
                    f"- Demand: {demand_weight} kg",
                    "",
                    "🚚 **Recommendation:** distribute across multiple warehouses",
                    f"  * {best_combo['warehouse1_name']} ({best_combo['warehouse1_city']}) – {int(best_combo['warehouse1_delivery'])}kg",
                    f"    - Vehicle {wh1_vehicle_info.get('vehicle_id', 'N/A')} departs from {best_combo['warehouse1_city'].title()} at {wh1_vehicle_info.get('departure_time', 'N/A')} towards {destination_city.title()}, arrives at {wh1_vehicle_info.get('arrival_time', 'N/A')}",
                    f"  * {best_combo['warehouse2_name']} ({best_combo['warehouse2_city']}) – {int(best_combo['warehouse2_delivery'])}kg",
                    f"    - Vehicle {wh2_vehicle_info.get('vehicle_id', 'N/A')} departs from {best_combo['warehouse2_city'].title()} at {wh2_vehicle_info.get('departure_time', 'N/A')} towards {destination_city.title()}, arrives at {wh2_vehicle_info.get('arrival_time', 'N/A')}",
                    f"- Final delivery by {bottleneck_time} (meets deadline)"
                ]
                result['message'] = "\n".join(msg_lines)
            elif warehouse_combinations:
                # No combination meets deadline, but we have combinations that can fulfill demand
                # Use the best combination (closest/earliest) even if it doesn't meet deadline
                best_combo = warehouse_combinations[0]
                
                # Get vehicle departure info from alternate warehouses to destination
                wh1_vehicle_info = self._get_vehicle_departure_from_warehouse(
                    best_combo['warehouse1_city'], 
                    destination_city, 
                    best_combo['warehouse1_delivery']
                )
                wh2_vehicle_info = self._get_vehicle_departure_from_warehouse(
                    best_combo['warehouse2_city'], 
                    destination_city, 
                    best_combo['warehouse2_delivery']
                ) if best_combo.get('warehouse2_delivery', 0) > 0 else {}
                
                # Calculate bottleneck time based on vehicle arrival times
                arrival_times = [wh1_vehicle_info.get('arrival_time', 'N/A')]
                if best_combo.get('warehouse2_delivery', 0) > 0:
                    arrival_times.append(wh2_vehicle_info.get('arrival_time', 'N/A'))
                bottleneck_time = self._get_bottleneck_time(arrival_times)
                
                result['recommendation'] = 'DIVERT_TO_MULTIPLE_WAREHOUSES'
                result['warehouse_combinations'] = [{
                    'warehouse1_city': best_combo['warehouse1_city'],
                    'warehouse1_name': best_combo['warehouse1_name'],
                    'warehouse1_delivery': int(best_combo['warehouse1_delivery']),
                    'warehouse1_capacity': int(best_combo['warehouse1_capacity']),
                    'warehouse1_vehicle_id': wh1_vehicle_info.get('vehicle_id', 'N/A'),
                    'warehouse1_vehicle_departure': wh1_vehicle_info.get('departure_time', 'N/A'),
                    'warehouse1_vehicle_arrival': wh1_vehicle_info.get('arrival_time', 'N/A'),
                    'warehouse2_city': best_combo['warehouse2_city'],
                    'warehouse2_name': best_combo['warehouse2_name'],
                    'warehouse2_delivery': int(best_combo['warehouse2_delivery']),
                    'warehouse2_capacity': int(best_combo['warehouse2_capacity']),
                    'warehouse2_vehicle_id': wh2_vehicle_info.get('vehicle_id', 'N/A'),
                    'warehouse2_vehicle_departure': wh2_vehicle_info.get('departure_time', 'N/A'),
                    'warehouse2_vehicle_arrival': wh2_vehicle_info.get('arrival_time', 'N/A'),
                    'combined_delivery_time': bottleneck_time
                }]
                msg_lines = [
                    "⚠️ **Disruption detected**",
                    f"- Route: {source_warehouse} → {destination_city}",
                    f"- Disruption at {disruption_time}, repair duration {repair_duration_hours}h",
                    f"- Demand: {demand_weight} kg",
                    "",
                    "🚚 **Recommendation:** divert to dual warehouses",
                    f"  * {best_combo['warehouse1_name']} ({best_combo['warehouse1_city']}) – {int(best_combo['warehouse1_delivery'])}kg",
                    f"    - Vehicle {wh1_vehicle_info.get('vehicle_id', 'N/A')} departs from {best_combo['warehouse1_city'].title()} at {wh1_vehicle_info.get('departure_time', 'N/A')} towards {destination_city.title()}, arrives at {wh1_vehicle_info.get('arrival_time', 'N/A')}",
                    f"  * {best_combo['warehouse2_name']} ({best_combo['warehouse2_city']}) – {int(best_combo['warehouse2_delivery'])}kg",
                    f"    - Vehicle {wh2_vehicle_info.get('vehicle_id', 'N/A')} departs from {best_combo['warehouse2_city'].title()} at {wh2_vehicle_info.get('departure_time', 'N/A')} towards {destination_city.title()}, arrives at {wh2_vehicle_info.get('arrival_time', 'N/A')}",
                    f"- Final delivery by {bottleneck_time}"
                ]
                result['message'] = "\n".join(msg_lines)
            else:
                # No combination works; try greedy multi-warehouse selection up to 3 warehouses
                greedy_selection = []
                remaining = demand_weight
                for wh in all_alternatives:
                    if remaining <= 0:
                        break
                    qty = wh['available_quantity']
                    if qty <= 0:
                        continue
                    greedy_selection.append(wh)
                    remaining -= qty
                
                if remaining <= 0 and len(greedy_selection) >= 2:
                    # Multi-warehouse solution found - use at least 2 warehouses for display
                    result['recommendation'] = 'DIVERT_TO_MULTIPLE_WAREHOUSES'
                    
                    # Calculate warehouse deliveries for vehicle assignment
                    warehouse1_delivery = int(min(greedy_selection[0]['available_quantity'], demand_weight))
                    warehouse2_delivery = int(min(greedy_selection[1]['available_quantity'], demand_weight - warehouse1_delivery)) if len(greedy_selection) > 1 else 0
                    
                    # Get vehicle departure info from alternate warehouses to destination
                    wh1_vehicle_info = self._get_vehicle_departure_from_warehouse(
                        greedy_selection[0]['city'], 
                        destination_city, 
                        warehouse1_delivery
                    )
                    wh2_vehicle_info = self._get_vehicle_departure_from_warehouse(
                        greedy_selection[1]['city'], 
                        destination_city, 
                        warehouse2_delivery
                    ) if len(greedy_selection) > 1 and warehouse2_delivery > 0 else {}
                    
                    # Calculate bottleneck time based on vehicle arrival times from warehouses to destination
                    arrival_times = [wh1_vehicle_info.get('arrival_time', 'N/A')]
                    if warehouse2_delivery > 0:
                        arrival_times.append(wh2_vehicle_info.get('arrival_time', 'N/A'))
                    bottleneck_time = self._get_bottleneck_time(arrival_times)

                    msg_lines = [
                        "⚠️ **Disruption detected**",
                        f"- Route: {source_warehouse} → {destination_city}",
                        f"- Disruption at {disruption_time}, repair duration {repair_duration_hours}h",
                        f"- Demand: {demand_weight} kg",
                        "",
                        "🚚 **Recommendation:** distribute across warehouses:",
                        f"  * {greedy_selection[0]['Name']} ({greedy_selection[0]['city']}) – {warehouse1_delivery}kg",
                        f"    - Vehicle {wh1_vehicle_info.get('vehicle_id', 'N/A')} departs from {greedy_selection[0]['city'].title()} at {wh1_vehicle_info.get('departure_time', 'N/A')} towards {destination_city.title()}, arrives at {wh1_vehicle_info.get('arrival_time', 'N/A')}",
                    ]
                    if warehouse2_delivery > 0:
                        msg_lines.append(f"  * {greedy_selection[1]['Name']} ({greedy_selection[1]['city']}) – {warehouse2_delivery}kg")
                        msg_lines.append(f"    - Vehicle {wh2_vehicle_info.get('vehicle_id', 'N/A')} departs from {greedy_selection[1]['city'].title()} at {wh2_vehicle_info.get('departure_time', 'N/A')} towards {destination_city.title()}, arrives at {wh2_vehicle_info.get('arrival_time', 'N/A')}")
                    msg_lines.append(f"- Final delivery by {bottleneck_time}")
                    result['message'] = "\n".join(msg_lines)
                    
                    # Create warehouse_combinations with warehouse1 and warehouse2 details
                    result['warehouse_combinations'] = [{
                        'warehouse1_city': str(greedy_selection[0]['city']),
                        'warehouse1_name': str(greedy_selection[0]['Name']),
                        'warehouse1_delivery': warehouse1_delivery,
                        'warehouse1_capacity': int(greedy_selection[0]['available_quantity']),
                        'warehouse1_vehicle_id': wh1_vehicle_info.get('vehicle_id', 'N/A'),
                        'warehouse1_vehicle_departure': wh1_vehicle_info.get('departure_time', 'N/A'),
                        'warehouse1_vehicle_arrival': wh1_vehicle_info.get('arrival_time', 'N/A'),
                        'warehouse2_city': str(greedy_selection[1]['city']) if len(greedy_selection) > 1 else "",
                        'warehouse2_name': str(greedy_selection[1]['Name']) if len(greedy_selection) > 1 else "",
                        'warehouse2_delivery': warehouse2_delivery,
                        'warehouse2_capacity': int(greedy_selection[1]['available_quantity']) if len(greedy_selection) > 1 else 0,
                        'warehouse2_vehicle_id': wh2_vehicle_info.get('vehicle_id', 'N/A'),
                        'warehouse2_vehicle_departure': wh2_vehicle_info.get('departure_time', 'N/A'),
                        'warehouse2_vehicle_arrival': wh2_vehicle_info.get('arrival_time', 'N/A'),
                        'combined_delivery_time': bottleneck_time
                    }]
                else:
                    # fallback to earliest single warehouse option
                    result['recommendation'] = 'ESCALATE'
                    
                    # Sort all alternatives by delivery time to find earliest
                    if result['alternative_warehouses']:
                        # Extract delivery times and sort
                        # build list of alternatives that actually have a delivery time
                        alternatives_with_times = []
                        for alt in result['alternative_warehouses']:
                            delivery_time_str = alt['delivery_analysis'].get('estimated_delivery_time')
                            # skip invalid/None/empty times
                            if not delivery_time_str or delivery_time_str in ['None', '']:
                                continue
                            alternatives_with_times.append((alt, delivery_time_str))
                        
                        if not alternatives_with_times:
                            result['message'] = (
                                f"Cannot meet deadline with current repair time ({repair_duration_hours} hours). "
                                f"No alternative warehouses found that provide a valid delivery time for {demand_weight}kg demand. "
                                f"Consider expedited repair or alternative transportation (air freight)."
                            )
                        else:
                            # Sort by delivery time (parse if it contains "Next day")
                            def parse_time_for_sorting(time_str):
                                if 'Next day' in str(time_str):
                                    parts = str(time_str).split()
                                    time_part = parts[-1] if len(parts) > 0 else "23:59"
                                    return (1, time_part)
                                else:
                                    return (0, str(time_str))
                            
                            alternatives_with_times.sort(key=lambda x: parse_time_for_sorting(x[1]))
                            # after sorting, pick first
                            earliest_alt = alternatives_with_times[0][0]
                            earliest_time = earliest_alt['delivery_analysis'].get('estimated_delivery_time', 'unknown')

                            result['earliest_warehouse'] = earliest_alt['warehouse_city']
                            result['earliest_warehouse_name'] = earliest_alt['warehouse_name']
                            result['earliest_delivery_time'] = str(earliest_time)
                            result['earliest_available_inventory'] = int(earliest_alt['available_inventory'])

                            time_gap = earliest_alt['delivery_analysis'].get('time_delta_hours', 0)
                            hours_late = abs(float(time_gap)) if time_gap < 0 else 0

                            # earliest single option with structured details
                            transport = self._assign_transport(source_warehouse, earliest_alt['warehouse_city'], demand_weight)
                            result['transport_plan'] = transport
                            msg_lines = [
                                "⚠️ **Disruption detected**",
                                f"- Route: {source_warehouse} → {destination_city}",
                                f"- Disruption at {disruption_time}, repair duration {repair_duration_hours}h",
                                f"- Demand: {demand_weight} kg",
                                "",
                                "🚚 **Recommendation:** divert to earliest available warehouse",
                                f"• {earliest_alt['warehouse_name']} ({earliest_alt['warehouse_city']})",
                                f"• Estimated delivery: {earliest_time} (approximately {hours_late:.1f}h late)",
                                f"• Available capacity: {int(earliest_alt['available_inventory'])} kg",
                            ]
                            if transport and transport.get('vehicles'):
                                v = transport['vehicles'][0]
                                msg_lines.append(f"• Vehicle {v['vehicle_id']} departs {source_warehouse.title()} at {v['departure']} and arrives {earliest_alt['warehouse_city'].title()} at {v['arrival']}")
                            result['message'] = "\n".join(msg_lines)
                    else:
                        result['message'] = (
                            f"Cannot meet deadline with current repair time ({repair_duration_hours} hours). "
                            f"No alternative warehouses found that can fulfill {demand_weight}kg demand. "
                            f"Consider expedited repair or alternative transportation (air freight)."
                        )        # Final serialization to ensure nested structures are JSON-friendly
        return json.loads(json.dumps(result, default=str))


def analyze_disruption_scenario(
    warehouses_df: pd.DataFrame,
    road_routes_df: pd.DataFrame,
    source_warehouse: str,
    destination_city: str,
    demand_weight: int,
    disruption_time: str = "22:00",
    required_delivery_time: str = "10:00",
    repair_duration_hours: int = 5,
    disruption_location: Optional[str] = None,
    vehicles_df: pd.DataFrame = None
) -> Dict:
    """
    Utility function to analyze a disruption scenario
    
    Args:
        warehouses_df: Warehouse data
        road_routes_df: Road route data
        source_warehouse: Source warehouse city
        destination_city: Destination city
        demand_weight: Weight in kg
        disruption_time: Time of disruption (HH:MM)
        required_delivery_time: Required delivery (HH:MM)
        repair_duration_hours: Repair time in hours
        disruption_location: Optional city where disruption occurred (for finding nearby warehouses)
        
    Returns:
        Detailed disruption analysis
    """
    manager = DisruptionManager(warehouses_df, road_routes_df, vehicles_df=vehicles_df)
    return manager.handle_disruption(
        source_warehouse,
        destination_city,
        demand_weight,
        disruption_time,
        required_delivery_time,
        repair_duration_hours,
        disruption_location=disruption_location
    )
