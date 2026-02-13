# Deployment Guide - Logistics Route Optimizer

## Quick Start for Development

### 1. Backend (Terminal 1)
```bash
cd d:\mylogistics\backend
.\env\Scripts\activate
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Frontend (Terminal 2)
```bash
cd d:\mylogistics\frontend\my-app
npm start
```

The application will be available at `http://localhost:3000`

---

## Testing with Sample Data

1. Start both backend and frontend
2. Go to `http://localhost:3000`
3. Upload sample files:
   - Air Routes: `d:\mylogistics\air_routes_sample.csv`
   - Road Routes: `d:\mylogistics\road_routes_sample.csv`
   - Country: Select "United States"
4. Try these queries:
   - "Cheapest route from New York to Los Angeles"
   - "Fastest way from Boston to Miami"
   - "Route from Atlanta to Chicago via Memphis"

---

## Production Deployment

### Backend Deployment (Using Gunicorn + Nginx)

1. **Install production dependencies:**
```bash
pip install gunicorn
```

2. **Create startup script** (`start_backend.sh`):
```bash
#!/bin/bash
cd /path/to/backend
source env/bin/activate
gunicorn -w 4 -b 0.0.0.0:8000 main:app
```

3. **Configure Nginx** (`/etc/nginx/sites-available/logistics-api`):
```nginx
server {
    listen 8000;
    server_name your_domain.com;

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### Frontend Deployment (Using Nginx)

1. **Build production bundle:**
```bash
cd frontend/my-app
npm run build
```

2. **Configure Nginx** (`/etc/nginx/sites-available/logistics-web`):
```nginx
server {
    listen 80;
    server_name your_domain.com;

    root /path/to/frontend/my-app/build;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://api.your_domain.com:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Docker Deployment

**Dockerfile for Backend:**
```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install -r requirements.txt

COPY backend/ .
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Dockerfile for Frontend:**
```dockerfile
FROM node:18 AS build
WORKDIR /app
COPY frontend/my-app/package*.json ./
RUN npm install
COPY frontend/my-app/ .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

**docker-compose.yml:**
```yaml
version: '3.8'

services:
  backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    ports:
      - "8000:8000"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - GOOGLE_MAPS_API_KEY=${GOOGLE_MAPS_API_KEY}
    volumes:
      - ./backend:/app

  frontend:
    build:
      context: .
      dockerfile: Dockerfile.frontend
    ports:
      - "3000:3000"
    depends_on:
      - backend

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    depends_on:
      - backend
      - frontend
```

**Run with Docker:**
```bash
docker-compose up -d
```

### Environment Variables for Production

Create `.env` file in backend directory:
```env
OPENAI_API_KEY=sk-your-production-key
GOOGLE_MAPS_API_KEY=your-google-maps-key
DEBUG=false
LOG_LEVEL=WARNING
```

### Update Frontend API URL

In `frontend/my-app/src/ChatInterface.js` and `FileUpload.js`, update:
```javascript
// Replace
fetch("http://localhost:8000/...")

// With
fetch(`${process.env.REACT_APP_API_URL}/...`)
```

Add to `frontend/my-app/.env.production`:
```
REACT_APP_API_URL=https://your_api_domain.com
```

---

## Monitoring & Logging

### Backend Logging

Edit `backend/main.py` to add logging configuration:
```python
import logging
from pythonjsonlogger import jsonlogger

logger = logging.getLogger()
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter()
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)
logger.setLevel(logging.INFO)
```

### Health Check Endpoint

The backend includes a health check:
```bash
curl http://localhost:8000/health
# Returns: {"status": "healthy"}
```

### Monitor API Performance

Use APM tools like:
- **New Relic**
- **DataDog**
- **Sentry** (error tracking)

---

## Security Considerations

1. **API Key Security:**
   - Never commit `.env` files
   - Use environment variables in production
   - Rotate API keys regularly

2. **CORS Configuration:**
   - Update allowed origins in `main.py`:
   ```python
   app.add_middleware(
       CORSMiddleware,
       allow_origins=["https://your_domain.com"],
       allow_credentials=True,
       allow_methods=["POST", "GET"],
       allow_headers=["*"],
   )
   ```

3. **Rate Limiting:**
   - Add rate limiting to prevent abuse
   - Use `slowapi`:
   ```bash
   pip install slowapi
   ```

4. **Input Validation:**
   - All inputs are validated in the current implementation
   - Use HTTPS in production

5. **HTTPS/SSL:**
   - Use Let's Encrypt for free SSL certificates
   - Configure Nginx to redirect HTTP to HTTPS

---

## Performance Optimization

### Backend Optimization

1. **Caching:**
   - Route results are cached in memory
   - Fuel prices are cached per country

2. **Database (optional):**
   - Add PostgreSQL for persistent storage
   - Cache frequently accessed routes

3. **Async Processing:**
   - Consider Celery for heavy optimization tasks

### Frontend Optimization

1. **Code Splitting:**
   ```bash
   npm install @loadable/component
   ```

2. **Image Optimization:**
   - Compress map tiles

3. **Bundle Analysis:**
   ```bash
   npm install source-map-explorer
   npm run analyze
   ```

---

## Scaling Considerations

### Horizontal Scaling

1. **Load Balancer (Nginx):**
   ```nginx
   upstream backend {
       server backend1.example.com:8000;
       server backend2.example.com:8000;
       server backend3.example.com:8000;
   }
   ```

2. **Database Replication:**
   - Master-slave replication for read scaling

3. **Redis Cache:**
   - For distributed caching:
   ```bash
   pip install redis
   ```

### Vertical Scaling

- Increase server resources (CPU, RAM)
- Use faster disks (SSD)
- Optimize database queries

---

## Backup & Disaster Recovery

1. **Data Backup:**
   - Regular automated backups of route data
   - Store backups in cloud (S3, Azure Blob Storage)

2. **Database Backup:**
   ```bash
   # PostgreSQL
   pg_dump logistics_db > backup.sql
   ```

3. **Recovery Plan:**
   - Document recovery procedures
   - Regular backup restoration tests

---

## Maintenance

### Regular Updates

```bash
# Backend dependencies
pip list --outdated
pip install --upgrade pip

# Frontend dependencies
npm outdated
npm update
```

### Database Maintenance (if using)

```sql
-- Analyze query performance
ANALYZE;

-- Cleanup old logs
DELETE FROM logs WHERE created_at < NOW() - INTERVAL '30 days';
```

---

## Troubleshooting Production Issues

### High Memory Usage
- Check for memory leaks in route optimization
- Monitor with: `ps aux | grep python`

### Slow API Responses
- Check database query performance
- Review OpenAI API latency
- Check network connectivity

### Crashed Backend Service
- Use systemd for auto-restart:
```ini
[Unit]
Description=Logistics Backend
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/var/www/logistics/backend
ExecStart=/var/www/logistics/backend/env/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Lost OpenAI API Key
- Rotate immediately in OpenAI dashboard
- Update `.env` file
- Restart backend service

---

## Contact & Support

For production deployment issues, refer to:
- [FastAPI Documentation](https://fastapi.tiangolo.com/deployment/)
- [React Documentation](https://react.dev/learn/deployment)
- [Nginx Documentation](https://nginx.org/en/docs/)
