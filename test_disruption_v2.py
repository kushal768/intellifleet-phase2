#!/usr/bin/env python
"""
Test script to verify disruption analysis with vehicle departure times from alternate warehouses
"""

import sys
import pandas as pd
sys.path.insert(0, 'd:\\mylogistics\\intellifleet-fullstack\\backend')

from disruption_manager import analyze_disruption_scenario

# Load sample data
warehouses_df = pd.read_csv('d:\\mylogistics\\intellifleet-fullstack\\sample_warehouse_data.csv')
road_routes_df = pd.read_csv('d:\\mylogistics\\intellifleet-fullstack\\road_routes.csv')
vehicles_df = pd.read_csv('d:\\mylogistics\\intellifleet-fullstack\\vehicles_mapped.csv')

# Test the disruption scenario from user's example
print("Testing Disruption Analysis with Vehicle Departures from Alternate Warehouses")
print("=" * 100)

result = analyze_disruption_scenario(
    warehouses_df=warehouses_df,
    road_routes_df=road_routes_df,
    source_warehouse='delhi',
    destination_city='mumbai',
    demand_weight=1000,
    disruption_time='22:00',
    required_delivery_time='10:00',
    repair_duration_hours=5,
    vehicles_df=vehicles_df
)

print("\nRecommendation:", result.get('recommendation'))
print("\nMessage:")
print(result.get('message'))

if result.get('warehouse_combinations'):
    print("\n" + "=" * 100)
    print("Warehouse Combinations Details:")
    for combo in result['warehouse_combinations']:
        print("\n--- WAREHOUSE 1 ---")
        print(f"  City: {combo.get('warehouse1_city')}")
        print(f"  Name: {combo.get('warehouse1_name')}")
        print(f"  Delivery Quantity: {combo.get('warehouse1_delivery')} kg")
        print(f"  Available Capacity: {combo.get('warehouse1_capacity')} kg")
        print(f"  Vehicle ID: {combo.get('warehouse1_vehicle_id')}")
        print(f"  Vehicle Departure (from warehouse): {combo.get('warehouse1_vehicle_departure')}")
        print(f"  Vehicle Arrival (at destination): {combo.get('warehouse1_vehicle_arrival')}")
        
        if combo.get('warehouse2_city'):
            print("\n--- WAREHOUSE 2 ---")
            print(f"  City: {combo.get('warehouse2_city')}")
            print(f"  Name: {combo.get('warehouse2_name')}")
            print(f"  Delivery Quantity: {combo.get('warehouse2_delivery')} kg")
            print(f"  Available Capacity: {combo.get('warehouse2_capacity')} kg")
            print(f"  Vehicle ID: {combo.get('warehouse2_vehicle_id')}")
            print(f"  Vehicle Departure (from warehouse): {combo.get('warehouse2_vehicle_departure')}")
            print(f"  Vehicle Arrival (at destination): {combo.get('warehouse2_vehicle_arrival')}")
        
        print(f"\n  Combined Delivery Time (bottleneck): {combo.get('combined_delivery_time')}")
