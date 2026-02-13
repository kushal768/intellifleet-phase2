# Logistics Route Optimizer

A full-stack application for optimizing logistics routes using AI, featuring interactive maps, multi-leg routing, and natural language queries.

## Features

✅ **Interactive Map Visualization**
- Real-time route visualization with Leaflet/React-Leaflet
- Air routes shown in green (dashed lines)
- Road routes shown in blue (solid lines)
- Route waypoints and start/end markers

✅ **AI-Powered Route Optimization**
- Natural language query processing using OpenAI GPT
- Automatic extraction of source, destination, and constraints
- Multi-leg route support (e.g., A→B by air, B→C by road, C→D by air)
- Via-node constraints (route must pass through specific locations)

✅ **Multiple Optimization Objectives**
- **Cheapest**: Minimize fuel costs (based on real-world fuel prices)
- **Fastest**: Minimize travel time
- **Shortest**: Minimize distance

✅ **Real-World Transport Metrics**
- Automatic fuel price calculation by country
- Realistic transport speeds (50 km/h for trucks, 800 km/h for aircraft)
- Fuel consumption rates based on transport mode
- Haversine distance calculations

✅ **Responsive Design**
- Desktop-optimized layout with split view (map + chat)
- Mobile-responsive design
- Professional UI with gradients and smooth animations

## Project Structure

```
mylogistics/
├── backend/
│   ├── main.py              # FastAPI application
│   ├── llm.py              # OpenAI integration
│   ├── optimizer.py        # Route optimization logic
│   ├── utils.py            # Utility functions
│   ├── config.py           # Configuration
│   ├── requirements.txt    # Python dependencies
│   └── env/                # Virtual environment
├── frontend/
│   └── my-app/
│       ├── src/
│       │   ├── App.js              # Main app component
│       │   ├── ChatInterface.js    # Chat UI
│       │   ├── MapView.js         # Map visualization
│       │   ├── FileUpload.js      # CSV upload
│       │   ├── api.js             # Backend API calls
│       │   └── [CSS files]        # Styling
│       └── package.json
├── air_routes_sample.csv       # Sample air routes
├── road_routes_sample.csv      # Sample road routes
└── README.md

```

## Prerequisites

- **Python 3.8+**
- **Node.js 14+** and npm
- **OpenAI API Key** (GPT-3.5-turbo or GPT-4)
- **Google Maps API Key** (optional, for future enhancements)

## Installation & Setup

### Backend Setup

1. Navigate to the backend directory:
```bash
cd backend
```

2. Create a virtual environment:
```bash
python -m venv env
```

3. Activate the virtual environment:
   - **Windows (PowerShell):**
   ```bash
   .\env\Scripts\Activate.ps1
   ```
   - **Windows (CMD):**
   ```bash
   .\env\Scripts\activate.bat
   ```
   - **macOS/Linux:**
   ```bash
   source env/bin/activate
   ```

4. Install dependencies:
```bash
pip install -r requirements.txt
```

5. Create a `.env` file in the backend directory:
```env
OPENAI_API_KEY=your_openai_api_key_here
GOOGLE_MAPS_API_KEY=your_google_maps_key_here
```

6. Start the FastAPI server:
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The backend will be available at `http://localhost:8000`

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend/my-app
```

2. Install dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm start
```

The frontend will open at `http://localhost:3000`

## Usage

### 1. Upload Route Data

1. The app opens with the file upload screen
2. Select your country (for fuel pricing adjustments)
3. Upload two CSV files:
   - **Air Routes CSV**: Contains flight routes with coordinates
   - **Road Routes CSV**: Contains road routes with coordinates

**CSV Format Requirements:**

**Air Routes:**
```csv
source_airport,destination_airport,lat_src,lon_src,lat_dst,lon_dst
JFK,LAX,40.6413,-74.0060,33.9425,-118.4081
```

**Road Routes:**
```csv
source_city,destination_city,lat_src,lon_src,lat_dst,lon_dst
New York,Boston,40.7128,-74.0060,42.3601,-71.0589
```

### 2. Query Routes via Chat

Once data is uploaded, you'll see the map on the left and chat interface on the right.

**Example queries:**
- "What's the cheapest route from New York to Los Angeles?"
- "Fastest way from Boston to Miami"
- "Route from Chicago to Denver via Kansas City, minimize cost"
- "Time from JFK to LAX by air then to Las Vegas by road"
- "Shortest route from Philadelphia to Washington DC"

### 3. View Results

The system will:
1. Parse your query using AI
2. Optimize the route based on your criteria
3. Display a table with:
   - Each route segment (From, To, Mode)
   - Distance, time, and fuel cost per segment
   - Total distance, time, and cost
4. Show the route on the map with:
   - Green dashed lines for air routes
   - Blue solid lines for road routes
   - Start point (red), end point (green), and waypoints (orange)

## API Endpoints

### POST `/upload`
Upload CSV files with route data
```bash
curl -X POST "http://localhost:8000/upload" \
  -F "air=@air_routes.csv" \
  -F "road=@road_routes.csv" \
  -F "country=US"
```

### GET `/optimize`
Get optimized route between two locations
```bash
curl "http://localhost:8000/optimize?source=New York&destination=Los Angeles&objective=cost"
```

Query Parameters:
- `source` (required): Starting location
- `destination` (required): Ending location
- `objective` (optional): "cost", "time", or "distance" (default: "cost")

### POST `/chat`
Natural language query processing
```bash
curl -X POST "http://localhost:8000/chat?message=Cheapest%20route%20from%20NYC%20to%20LA"
```

Query Parameters:
- `message` (required): Natural language query
- `via` (optional): Intermediate location(s) to pass through

### GET `/route-details/{source}/{destination}`
Get detailed route information
```bash
curl "http://localhost:8000/route-details/New York/Los Angeles?objective=cost"
```

## Configuration

### Supported Countries (Fuel Pricing)
- US (United States)
- IN (India)
- UK (United Kingdom)
- DE (Germany)
- AU (Australia)

To add more countries, edit `utils.py` and update the `get_fuel_price()` function.

### Transport Parameters

Edit `utils.py` to adjust:
- Truck speed: Default 50 km/h
- Truck fuel efficiency: Default 4 km/liter
- Aircraft speed: Default 800 km/h
- Aircraft fuel consumption: Default 5 liters/km

## Advanced Features

### Multi-Leg Routing
The system automatically finds multi-leg routes when direct connections aren't available:
- Example: New York → Chicago (air) → Denver (road) → Los Angeles (air)
- Each segment is optimized and displayed separately

### Via-Node Constraints
Force routes through specific locations:
- Example: "Route from A to D via B and C"
- The optimizer ensures the route passes through B and C

### Real-Time Fuel Price Calculation
Fuel prices are cached per country to minimize API calls. Edit the `FUEL_PRICE_CACHE` in `utils.py` to update prices manually.

## Troubleshooting

### "No route found" Error
- Check that all locations in your query exist in the uploaded CSV files
- Verify the CSV format matches the requirements
- Ensure there's a valid path between the source and destination

### OpenAI API Errors
- Verify your API key is correct in the `.env` file
- Check your OpenAI account has sufficient credits
- Ensure you're using a supported model (gpt-3.5-turbo or gpt-4)

### CORS Issues
- The backend has CORS enabled for all origins (`allow_origins=["*"]`)
- If issues persist, update the CORS configuration in `main.py`

### Map Not Loading
- Clear browser cache and reload
- Check that Leaflet CSS is properly loaded
- Verify OpenStreetMap tiles are accessible

## Performance Optimization

- Routes are cached in memory after upload
- Fuel prices are cached by country
- The optimizer uses CBC (Coin-or-branch and cut) solver for fast optimization
- UI updates are optimized with React hooks

## Future Enhancements

- [ ] Real-time traffic data integration
- [ ] Vehicle capacity constraints
- [ ] Multiple vehicle types (truck, plane, ship, train)
- [ ] CO2 emissions calculation
- [ ] Cost breakdown (fuel, toll, maintenance)
- [ ] Historical route analysis
- [ ] Route analytics dashboard
- [ ] Batch route optimization
- [ ] Webhook notifications for route completion

## License

MIT License - Feel free to use this project for personal or commercial purposes.

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review the API documentation
3. Check console logs for detailed error messages
4. Verify environment configuration

## Sample Data

Two sample CSV files are included for testing:
- `air_routes_sample.csv`: 10 domestic US air routes
- `road_routes_sample.csv`: 10 US city-to-city road routes

Use these to get started without preparing your own data.

---

**Built with:** React, FastAPI, OpenAI GPT, Leaflet, Pulp Optimizer
