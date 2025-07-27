from fastapi import FastAPI, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
import sqlite3
import yaml
import requests
from datetime import datetime
import time
from urllib.parse import urlparse
import logging
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
import os
from starlette.middleware.sessions import SessionMiddleware
from src.security import verify_frontend_request, init_session, SECRET_KEY

def load_config(config_file='config.yml'):
    """Load configuration from YAML file."""
    with open(config_file, 'r') as file:
        return yaml.safe_load(file)

# Load configuration
config = load_config()

# Setup logging
log_dir = Path(config['logging']['dir'])
log_dir.mkdir(parents=False, exist_ok=True)
log_file = log_dir / config['logging']['file']

# Add this: Ensure data directory exists
data_dir = Path(config['database']['path']).parent
data_dir.mkdir(parents=False, exist_ok=True)

logging.basicConfig(
    level=getattr(logging, config['logging'].get('level', 'INFO').upper()),
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename=str(log_file),
    filemode='a'
)

# Set APScheduler logger to WARNING to suppress job execution messages
logging.getLogger('apscheduler').setLevel(getattr(logging, config['logging'].get('level-scheduler', 'WARNING').upper()))

# Initialize scheduler
scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events."""
    # Initialize database
    conn = sqlite3.connect(config['database']['path'])
    cursor = conn.cursor()
    
    # Create tracking table if it doesn't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tracking (
        url TEXT,
        detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        geom_lat DOUBLE,
        geom_lon DOUBLE,
        country TEXT,
        city TEXT,
        isp TEXT,
        org TEXT,
        as_number TEXT,
        UNIQUE(url, geom_lat, geom_lon, country, city, isp, org, as_number)
    )
    ''')
    
    # Create index if it doesn't exist
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_url_detected 
    ON tracking(url, detected_at)
    ''')
    
    conn.commit()
    conn.close()
    
    # Start the scheduler
    scheduler.add_job(
        track_urls_job,
        trigger=IntervalTrigger(**config['server']['tracking_interval']),
        id='url-tracker-job',
        name='url-tracker-job',
        replace_existing=False,
        max_instances=1,
        coalesce=True
    )
    scheduler.start()
    logging.debug("Scheduler started")
    
    yield
    
    scheduler.shutdown()

# Update FastAPI app to use lifespan
app = FastAPI(lifespan=lifespan)

# Add session middleware
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie="session",
    max_age=3600,  # 1 hour
    same_site="strict",
    https_only=True
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config['server']['allowed_origins'],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Configure templates directory
templates = Jinja2Templates(directory="src/pages")

async def locate_domain(domain):
    """Get location data from ip-api.com."""
    try:
        response = requests.get(f'http://ip-api.com/json/{domain}')
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                return {
                    'lat': data.get('lat'),
                    'lon': data.get('lon'),
                    'country': data.get('country'),
                    'city': data.get('city'),
                    'isp': data.get('isp'),
                    'org': data.get('org'),
                    'as': data.get('as')
                }
    except Exception as e:
        logging.error(f"Error fetching location for {domain}: {str(e)}")
        return None

def get_domain(url):
    """Extract domain from URL."""
    parsed = urlparse(url)
    return parsed.netloc or parsed.path

def get_locations(url):
    """Get all locations for a URL."""
    conn = sqlite3.connect(config['database']['path'])
    cursor = conn.cursor()
    cursor.execute('''
    SELECT detected_at, geom_lat, geom_lon, country, city, isp, org, as_number FROM tracking WHERE url = ? ORDER BY detected_at ASC
    ''', (url,))
    return cursor.fetchall()

async def track_urls_job():
    """Scheduled job to track URLs."""
    conn = sqlite3.connect(config['database']['path'])
    cursor = conn.cursor()
    
    urls = config['urls']
    logging.debug(f":Running job to track {len(urls)} URLs")
    for url in urls:
        logging.debug(f" - Tracking {url}")
    
    for url in urls:
        domain = get_domain(url)

        logging.debug(f"Processing {domain}")
        location = await locate_domain(domain)

        if not location:
            logging.warning(f"Could not get location for {domain}")
            continue
    
            
        # Insert new location, ignoring if exact location already exists
        cursor.execute('''
        INSERT OR IGNORE INTO tracking (
            url, detected_at, geom_lat, geom_lon,
            country, city, isp, org, as_number
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            url, datetime.now().isoformat(), location['lat'], location['lon'],
            location['country'], location['city'], location['isp'],
            location['org'], location['as']
        ))
        
        if cursor.rowcount > 0:
            logging.debug(f"New location recorded for {domain}")
            conn.commit()
        else:
            logging.debug(f"Location unchanged for {domain}")
    
    conn.close()

@app.get("/")
async def home(request: Request):
    """Render the home page with latest locations."""
    # Initialize session for frontend
    init_session(request)
    urls = config['urls']
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "urls": urls
        }
    )

@app.get("/map-trace")
async def map_trace(request: Request, url: str = None):
    """Render the map trace template."""
    # Verify the request is from our frontend
    await verify_frontend_request(request)
    
    return templates.TemplateResponse(
        "map-trace.html",
        {
            "request": request,
            "url": url
        }
    )

@app.get("/api/locations/{url:path}")
async def get_url_locations(request: Request, url: str):
    """API endpoint to get locations for a specific URL."""
    # Verify the request is from our frontend
    await verify_frontend_request(request)
    
    locations = get_locations(url)
    return locations

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)