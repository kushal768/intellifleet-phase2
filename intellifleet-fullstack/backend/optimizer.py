from pulp import *
import logging

logger = logging.getLogger(__name__)

# Finds the optimal route between start and end nodes using linear programming with specified objective.
def optimize(nodes, edges, start, end, objective="cost", via=None):
    """
    Optimize route from start to end node.
    
    Args:
        nodes: Dict of node_id -> (lat, lon)
        edges: Dict of (from, to) -> {properties}
        start: Starting node
        end: Ending node
        objective: "cost" | "time" | "distance" | "fastest"
        via: Optional intermediate node(s) to pass through
    
    Returns:
        List of edges in optimized route
    """
    model = LpProblem("Logistics_Optimization", LpMinimize)

    # Create binary variables for each edge
    x = LpVariable.dicts("route", edges.keys(), cat="Binary")

    # Set objective function
    if objective == "time" or objective == "fastest":
        model += lpSum(x[e] * edges[e].get("time", 0) for e in edges)
    elif objective == "distance":
        model += lpSum(x[e] * edges[e].get("distance", 0) for e in edges)
    else:  # Default to cost
        model += lpSum(x[e] * edges[e].get("fuel", 0) for e in edges)

    # Flow conservation constraints
    for n in nodes:
        inflow = lpSum(x[(i, j)] for (i, j) in edges if j == n and (i, j) in x)
        outflow = lpSum(x[(i, j)] for (i, j) in edges if i == n and (i, j) in x)

        if n == start:
            # Start node: outflow = inflow + 1
            model += outflow - inflow == 1
        elif n == end:
            # End node: inflow = outflow + 1
            model += inflow - outflow == 1
        else:
            # Intermediate nodes: inflow = outflow
            model += inflow == outflow

    # Via constraint: if intermediate node is specified, route must pass through it
    if via:
        if isinstance(via, list):
            for v in via:
                inflow_via = lpSum(x[(i, j)] for (i, j) in edges if j == v and (i, j) in x)
                model += inflow_via == 1
        else:
            inflow_via = lpSum(x[(i, j)] for (i, j) in edges if j == via and (i, j) in x)
            model += inflow_via == 1

    # Solve
    try:
        model.solve(PULP_CBC_CMD(msg=0))
    except Exception as e:
        logger.error(f"Solver error: {e}")
        return []

    # Extract solution
    if model.status != 1:  # 1 = Optimal solution found
        logger.warning(f"No optimal solution found. Status: {model.status}")
        return []

    route = []
    for e in edges:
        if x[e].varValue == 1:
            route.append(edges[e])

    return sorted(route, key=lambda r: (r.get("from"), r.get("to")))

# Calculates and aggregates summary statistics (total distance, time, cost) for a complete route.
def get_route_summary(route):
    """
    Calculate summary statistics for a route.
    
    Args:
        route: List of edge dictionaries
    
    Returns:
        Dict with totals for distance, time, and fuel cost
    """
    if not route:
        return {
            "total_distance": 0,
            "total_time": 0,
            "total_fuel_cost": 0,
            "segment_count": 0,
            "modes": []
        }
    
    summary = {
        "total_distance": round(sum(r.get("distance", 0) for r in route), 2),
        "total_time": round(sum(r.get("time", 0) for r in route), 2),
        "total_fuel_cost": round(sum(r.get("fuel", 0) for r in route), 2),
        "segment_count": len(route),
        "modes": list(set(r.get("mode", "unknown") for r in route))
    }
    
    return summary
