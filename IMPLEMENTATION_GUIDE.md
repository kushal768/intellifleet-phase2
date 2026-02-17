# How to Implement Capacity API - Complete Guide

## ============================================================
## OPTION 1: RUN CAPACITY API SEPARATELY (Recommended)
## ============================================================

### Step 1: Start the Capacity API in a separate terminal
```bash
cd D:\mylogistics\intellifleet-fullstack\backend
uvicorn capacity_api:app --reload --port 8000
```

### Step 2: Verify it's running
```bash
curl http://localhost:8001/health
# Response: {"status": "healthy", "service": "capacity-optimizer"}
```

### Step 3: Visit interactive docs
Open browser: http://localhost:8000/docs


## ============================================================
## OPTION 2: CALL FROM FRONTEND (JavaScript/React)
## ============================================================

### 2A. Using Fetch API (vanilla JavaScript)
```javascript
// 1. Prepare vehicles
async function prepareVehicles(vehicleData) {
  const response = await fetch('http://localhost:8001/prepare-vehicles', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(vehicleData)
  });
  return await response.json();
}

// 2. Assign vehicles for a single leg
async function assignVehiclesForLeg(vehicles, leg, totalGoodsKg, objective = 'cost') {
  const params = new URLSearchParams({
    total_goods_kg: totalGoodsKg,
    objective: objective
  });
  
  const response = await fetch(`http://localhost:8001/assign-vehicles-for-leg?${params}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      vehicles: vehicles,
      leg: leg
    })
  });
  return await response.json();
}

// 3. Batch assign for multiple legs
async function batchAssignVehicles(vehicles, legs, totalGoodsKg, objective = 'cost') {
  const params = new URLSearchParams({
    total_goods_kg: totalGoodsKg,
    objective: objective
  });
  
  const response = await fetch(`http://localhost:8001/batch-assign-vehicles?${params}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      vehicles: vehicles,
      legs: legs
    })
  });
  return await response.json();
}

// Usage Example:
const vehicleData = [
  {
    WarehouseName: "New York",
    VehicleType: "truck",
    VehicleCapacity: 5000,
    DepartureTime: "08:00"
  },
  {
    WarehouseName: "New York",
    VehicleType: "van",
    VehicleCapacity: 2000,
    DepartureTime: "09:00"
  }
];

const leg = {
  from_city: "New York",
  to_city: "Philadelphia",
  distance: 95.0,
  time: 1.8
};

// Prepare vehicles first
const prepared = await prepareVehicles(vehicleData);
console.log('Prepared vehicles:', prepared);

// Then assign for a leg
const assignment = await assignVehiclesForLeg(prepared, leg, 4500, 'cost');
console.log('Assignment result:', assignment);
```

### 2B. Using Axios (if using React or Node.js)
```javascript
import axios from 'axios';

const API_URL = 'http://localhost:8001';

const capacityAPI = {
  // Prepare vehicles
  async prepareVehicles(vehicles) {
    return axios.post(`${API_URL}/prepare-vehicles`, vehicles);
  },

  // Assign for single leg
  async assignVehiclesForLeg(vehicles, leg, totalGoodsKg, objective = 'cost') {
    return axios.post(`${API_URL}/assign-vehicles-for-leg`, 
      { vehicles, leg },
      {
        params: { total_goods_kg: totalGoodsKg, objective }
      }
    );
  },

  // Batch assign
  async batchAssignVehicles(vehicles, legs, totalGoodsKg, objective = 'cost') {
    return axios.post(`${API_URL}/batch-assign-vehicles`,
      { vehicles, legs },
      {
        params: { total_goods_kg: totalGoodsKg, objective }
      }
    );
  },

  // Get vehicle specs
  async getVehicleSpecs() {
    return axios.get(`${API_URL}/vehicle-specs`);
  },

  // Health check
  async health() {
    return axios.get(`${API_URL}/health`);
  }
};

export default capacityAPI;
```

### 2C. Usage in React Component
```jsx
import { useState } from 'react';
import capacityAPI from './services/capacityAPI';

function VehicleAssignment() {
  const [assignment, setAssignment] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleAssignVehicles = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const vehicles = [
        {
          WarehouseName: "New York",
          VehicleType: "truck",
          VehicleCapacity: 5000,
          DepartureTime: "08:00"
        }
      ];

      const leg = {
        from_city: "New York",
        to_city: "Philadelphia",
        distance: 95.0,
        time: 1.8
      };

      const response = await capacityAPI.assignVehiclesForLeg(
        vehicles,
        leg,
        4500,
        'cost'
      );

      setAssignment(response.data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <button onClick={handleAssignVehicles} disabled={loading}>
        {loading ? 'Assigning...' : 'Assign Vehicles'}
      </button>
      
      {error && <p style={{color: 'red'}}>Error: {error}</p>}
      
      {assignment && (
        <div>
          <h3>Assignment Result</h3>
          <pre>{JSON.stringify(assignment, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}

export default VehicleAssignment;
```


## ============================================================
## OPTION 3: CALL FROM PYTHON CODE
## ============================================================

### 3A. Using requests library
```python
import requests
import json

API_URL = 'http://localhost:8001'

def prepare_vehicles(vehicles_data):
    """Call the prepare-vehicles endpoint"""
    response = requests.post(
        f'{API_URL}/prepare-vehicles',
        json=vehicles_data
    )
    return response.json()

def assign_vehicles_for_leg(vehicles, leg, total_goods_kg, objective='cost'):
    """Call the assign-vehicles-for-leg endpoint"""
    response = requests.post(
        f'{API_URL}/assign-vehicles-for-leg',
        params={
            'total_goods_kg': total_goods_kg,
            'objective': objective
        },
        json={
            'vehicles': vehicles,
            'leg': leg
        }
    )
    return response.json()

def batch_assign_vehicles(vehicles, legs, total_goods_kg, objective='cost'):
    """Call the batch-assign-vehicles endpoint"""
    response = requests.post(
        f'{API_URL}/batch-assign-vehicles',
        params={
            'total_goods_kg': total_goods_kg,
            'objective': objective
        },
        json={
            'vehicles': vehicles,
            'legs': legs
        }
    )
    return response.json()

def get_vehicle_specs():
    """Get vehicle specifications"""
    response = requests.get(f'{API_URL}/vehicle-specs')
    return response.json()

# ===========================================
# USAGE EXAMPLE
# ===========================================

if __name__ == '__main__':
    # 1. Vehicle data
    vehicles = [
        {
            'WarehouseName': 'New York',
            'VehicleType': 'truck',
            'VehicleCapacity': 5000,
            'DepartureTime': '08:00'
        },
        {
            'WarehouseName': 'New York',
            'VehicleType': 'van',
            'VehicleCapacity': 2000,
            'DepartureTime': '09:00'
        }
    ]

    # 2. Prepare vehicles
    print("=== PREPARE VEHICLES ===")
    prepared = prepare_vehicles(vehicles)
    print(json.dumps(prepared, indent=2))

    # 3. Define a leg
    leg = {
        'from_city': 'New York',
        'to_city': 'Philadelphia',
        'distance': 95.0,
        'time': 1.8
    }

    # 4. Assign vehicles for the leg
    print("\n=== ASSIGN VEHICLES FOR LEG ===")
    assignment = assign_vehicles_for_leg(prepared, leg, 4500, 'cost')
    print(json.dumps(assignment, indent=2))

    # 5. Get vehicle specs
    print("\n=== VEHICLE SPECS ===")
    specs = get_vehicle_specs()
    print(json.dumps(specs, indent=2))
```

### 3B. Using async/await with aiohttp
```python
import aiohttp
import asyncio

API_URL = 'http://localhost:8001'

async def prepare_vehicles_async(vehicles_data):
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f'{API_URL}/prepare-vehicles',
            json=vehicles_data
        ) as resp:
            return await resp.json()

async def assign_vehicles_async(vehicles, leg, total_goods_kg, objective='cost'):
    params = {
        'total_goods_kg': total_goods_kg,
        'objective': objective
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f'{API_URL}/assign-vehicles-for-leg',
            params=params,
            json={'vehicles': vehicles, 'leg': leg}
        ) as resp:
            return await resp.json()

# Usage
async def main():
    vehicles = [...]
    prepared = await prepare_vehicles_async(vehicles)
    print(prepared)

asyncio.run(main())
```


## ============================================================
## OPTION 4: CALL FROM EXISTING main.py (If Needed)
## ============================================================

If you want to call capacity_api from your main.py without integrating it:

```python
# In main.py
import requests

CAPACITY_API_URL = 'http://localhost:8001'

@app.post("/optimize/vehicles")
async def optimize_vehicles_endpoint(vehicles: List[dict], leg: dict, total_goods: float):
    """Proxy endpoint that calls capacity_api"""
    try:
        # Forward the request to capacity_api
        response = requests.post(
            f'{CAPACITY_API_URL}/assign-vehicles-for-leg',
            params={
                'total_goods_kg': total_goods,
                'objective': 'cost'
            },
            json={'vehicles': vehicles, 'leg': leg}
        )
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```


## ============================================================
## COMMAND LINE EXAMPLES (cURL)
## ============================================================

### 1. Health Check
```bash
curl http://localhost:8001/health
```

### 2. Prepare Vehicles
```bash
curl -X POST http://localhost:8001/prepare-vehicles \
  -H "Content-Type: application/json" \
  -d '[
    {
      "WarehouseName": "New York",
      "VehicleType": "truck",
      "VehicleCapacity": 5000,
      "DepartureTime": "08:00"
    },
    {
      "WarehouseName": "New York",
      "VehicleType": "van",
      "VehicleCapacity": 2000,
      "DepartureTime": "09:00"
    }
  ]'
```

### 3. Assign Vehicles for One Leg
```bash
curl -X POST "http://localhost:8001/assign-vehicles-for-leg?total_goods_kg=4500&objective=cost" \
  -H "Content-Type: application/json" \
  -d '{
    "vehicles": [
      {
        "WarehouseName": "New York",
        "VehicleType": "truck",
        "VehicleCapacity": 5000,
        "DepartureTime": "08:00"
      }
    ],
    "leg": {
      "from_city": "New York",
      "to_city": "Philadelphia",
      "distance": 95.0,
      "time": 1.8
    }
  }'
```

### 4. Batch Assign Multiple Legs
```bash
curl -X POST "http://localhost:8001/batch-assign-vehicles?total_goods_kg=4500&objective=cost" \
  -H "Content-Type: application/json" \
  -d '{
    "vehicles": [...],
    "legs": [
      {
        "from_city": "New York",
        "to_city": "Philadelphia",
        "distance": 95.0,
        "time": 1.8
      },
      {
        "from_city": "Philadelphia",
        "to_city": "Washington",
        "distance": 140.0,
        "time": 2.5
      }
    ]
  }'
```

### 5. Get Vehicle Specs
```bash
curl http://localhost:8001/vehicle-specs
```


## ============================================================
## RECOMMENDED SETUP
## ============================================================

1. Terminal 1 - Main API:
   ```bash
   cd D:\mylogistics\intellifleet-fullstack\backend
   uvicorn main:app --reload --port 8000
   ```

2. Terminal 2 - Capacity API:
   ```bash
   cd D:\mylogistics\intellifleet-fullstack\backend
   uvicorn capacity_api:app --reload --port 8001
   ```

3. From Frontend (React):
   - Use the Axios service (Option 2B) to call http://localhost:8001

4. From Python:
   - Use the requests library (Option 3A) to call http://localhost:8001

5. API Documentation:
   - Main API: http://localhost:8000/docs
   - Capacity API: http://localhost:8001/docs


## ============================================================
## TESTING IN SWAGGER UI
## ============================================================

1. Open http://localhost:8001/docs
2. Click on any endpoint (e.g., POST /prepare-vehicles)
3. Click "Try it out"
4. Enter your test data
5. Click "Execute"
6. See the response!

This is the easiest way to test without writing code.
