from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import json
import os
import subprocess
import signal
import sys
import uvicorn
import logging
from typing import Any, Dict
from typing import Optional, List
from datetime import datetime
from crawlers.analytics import AnalyticsData, get_db
import httpx

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Web Crawler", description="WebCrawler that returns number of viewers of a certain website, their region and time spent viewing. Also to return all .rw websites out there in the internet.")

# Mount the static files (templates directory)
app.mount("/static", StaticFiles(directory="templates"), name="static")

# Store the crawler process
crawler_process = None
analytics_process = None

def start_crawler():
    global crawler_process
    if crawler_process is None:
        try:
            # Start the crawler as a subprocess
            crawler_process = subprocess.Popen([sys.executable, "crawlers/rw_crawler.py"])
            logger.info("Domain crawler process started")
            return True
        except Exception as e:
            logger.error(f"Error starting crawler: {e}")
            return False
    return True

def start_analytics_server():
    global analytics_process
    if analytics_process is None:
        try:
            # Start the analytics as a subprocess
            analytics_process = subprocess.Popen([sys.executable, "crawlers/analytics.py"])
            logger.info("Analytics process started")
            return True
        except Exception as e:
            logger.error(f"Error starting analytics: {e}")
            return False
    return True

@app.get("/")
async def read_root():
    try:
        logger.info("Serving index.html")
        return FileResponse("templates/index.html", media_type="text/html")
    except Exception as e:
        logger.error(f"Error serving index.html: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
# Analytics endpoint
@app.post("/analytics")
async def analytics(
    data: AnalyticsData,
    request: Request
) -> dict[str, Any]:
    with get_db() as conn:
        # Format timestamp for logging
        if not data.timestamp:
            data.timestamp = datetime.now().isoformat()

        # Add request IP if not provided in the analytics data
        request_ip = request.client.host if request.client else None
        if not data.region or not data.region.ip:
            request_ip = request.client.host if request.client else None

        # Log to console
        print(f"[{data.timestamp}] Analytics event: {data.eventType} for domain: {data.domain}")

        # Convert the Pydantic model to a dict for storage
        data_dict = data.model_dump()

        # Store in database
        try:
            cursor = conn.cursor()

            # Insert main analytics event
            cursor.execute(
                '''
                INSERT INTO analytics_events 
                (session_id, domain, event_type, timestamp, page_views, time_spent, request_ip, raw_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    data.sessionId,
                    data.domain,
                    data.eventType,
                    data.timestamp,
                    data.pageViews or 0,
                    data.timeSpent or 0,
                    request_ip,
                    json.dumps(data_dict)
                )
            )

            # Get the inserted row ID
            event_id = cursor.lastrowid

            # Insert region data if available
            if data.region:
                cursor.execute(
                    '''
                    INSERT INTO regions (event_id, city, region, country, ip)
                    VALUES (?, ?, ?, ?, ?)
                    ''',
                    (
                        event_id,
                        data.region.city,
                        data.region.region,
                        data.region.country,
                        data.region.ip or request_ip
                    )
                )

            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"Error storing analytics data: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to save analytics data: {str(e)}")

        return {"success": True, "event_id": event_id}

# Get analytics data endpoint
@app.get("/analytics/data")
async def get_analytics() -> dict[str, Any]:
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Build the query dynamically based on provided filters
        query = '''
        SELECT 
            e.id,
            e.session_id,
            e.domain,
            e.event_type,
            e.timestamp,
            e.page_views,
            e.time_spent,
            e.request_ip,
            r.city,
            r.region,
            r.country,
            r.ip as region_ip
        FROM analytics_events e
        LEFT JOIN regions r ON e.id = r.event_id
        WHERE 1=1
        '''
        
        params: list[str] = []
    
        # Order by timestamp
        query += " ORDER BY e.timestamp DESC"
        
        try:
            cursor.execute(query, params)
            results = cursor.fetchall()
            
            # Convert to list of dicts
            events: List[dict[str, Any]] = []
            for row in results:
                row_dict = dict(row)
                region_data = {
                    "city": row_dict.pop("city"),
                    "region": row_dict.pop("region"),
                    "country": row_dict.pop("country"),
                    "ip": row_dict.pop("region_ip")
                }
                
                row_dict["region"] = region_data
                events.append(row_dict)
            
            # Return analytics data
            return {
                "success": True,
                "count": len(events),
                "results": events
            }
            
        except Exception as e:
            print(f"Error retrieving analytics data: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to retrieve analytics data: {str(e)}")

# Get analytics summary endpoint - aggregated data
@app.get("/analytics/summary")
async def get_analytics_summary() -> dict[str, Any]:
    with get_db() as conn:
        cursor = conn.cursor()
    
        # Base query conditions
        where_clause = "WHERE 1=1"
        params: list[str] = []

        try:
            # Total sessions
            cursor.execute(f'''
            SELECT COUNT(DISTINCT e.session_id) as total_sessions
            FROM analytics_events e
            LEFT JOIN regions r ON e.id = r.event_id
            {where_clause}
            ''', params)
            total_sessions = cursor.fetchone()['total_sessions']
        
            # Total page views
            cursor.execute(f'''
            SELECT SUM(e.page_views) as total_page_views
            FROM analytics_events e
            LEFT JOIN regions r ON e.id = r.event_id
            {where_clause}
            ''', params)
            total_page_views = cursor.fetchone()['total_page_views'] or 0
        
            # Total time spent
            cursor.execute(f'''
            SELECT SUM(e.time_spent) as total_time_spent
            FROM analytics_events e
            LEFT JOIN regions r ON e.id = r.event_id
            {where_clause}
            ''', params)
            total_time_spent = cursor.fetchone()['total_time_spent'] or 0
        
            # Region breakdown
            cursor.execute(f'''
            SELECT 
                COALESCE(r.country, 'Unknown') as country,
                COUNT(DISTINCT e.session_id) as session_count
            FROM analytics_events e
            LEFT JOIN regions r ON e.id = r.event_id
            {where_clause}
            GROUP BY COALESCE(r.country, 'Unknown')
            ORDER BY session_count DESC
            ''', params)
            region_breakdown = [dict(row) for row in cursor.fetchall()]
        
            # Event type breakdown
            cursor.execute(f'''
            SELECT 
                COALESCE(e.event_type, 'Unknown') as event_type,
                COUNT(*) as count
            FROM analytics_events e
            LEFT JOIN regions r ON e.id = r.event_id
            {where_clause}
            GROUP BY COALESCE(e.event_type, 'Unknown')
            ORDER BY count DESC
            ''', params)
            event_breakdown = [dict(row) for row in cursor.fetchall()]
        
            # Latest activity timestamp
            cursor.execute(f'''
            SELECT MAX(e.timestamp) as latest_activity
            FROM analytics_events e
            LEFT JOIN regions r ON e.id = r.event_id
            {where_clause}
            ''', params)
            latest_activity = cursor.fetchone()['latest_activity']
        
            return {
                "success": True,
                "summary": {
                    "total_sessions": total_sessions,
                    "total_page_views": total_page_views,
                    "total_time_spent": total_time_spent,
                    "latest_activity": latest_activity,
                    "regions": region_breakdown,
                    "events": event_breakdown
                }
            }
        
        except Exception as e:
            print(f"Error retrieving analytics summary: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to retrieve analytics summary: {str(e)}")

@app.get("/api/geolocation")
async def get_geolocation(request: Request):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("https://ipwho.is/")
            response.raise_for_status()
            data = response.json()
        return data
    except Exception as e:
        logger.error(f"Geolocation lookup failed: {e}")
        return {
            "country": "Unknown",
            "region": "Unknown",
            "city": "Unknown"
        }

# Get domains endpoint
@app.get("/api/domains")
async def get_domains() -> Dict[str, Any]:
    try:
        json_path = "data/rw_domains.json"
        if not os.path.exists(json_path):
            logger.warning(f"File not found: {json_path}")
            return {"domains": [], "last_updated": None}

        with open(json_path, "r", encoding='utf-8') as f:
            data = json.load(f)
            # Extract the list of domain objects
            domains = data.get("domains", [])
            last_updated = data.get("metadata", {}).get("crawl_date")
            logger.info(f"Found {len(domains)} domains")
            logger.info(f"Last updated: {last_updated}")
            return {
                "domains": domains,
                "last_updated": last_updated,
                "metadata": data.get("metadata", {})
            }
    except Exception as e:
        logger.error(f"Error reading domains: {e}")
        return {"domains": [], "last_updated": None, "error": str(e)}

@app.post("/api/start-crawler")
async def start_crawler_endpoint():
    success = start_crawler()
    if success:
        return {"status": "success", "message": "Crawler started successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to start crawler")
    
@app.get("/api/analytics-script")
async def get_analytics_script():
    script_path = "scripts/analytics.js"
    if not os.path.exists(script_path):
        raise HTTPException(status_code=404, detail="Analytics script not found")
    return FileResponse(script_path, media_type="application/javascript")

def cleanup():
    global crawler_process
    if crawler_process:
        crawler_process.terminate()
        crawler_process.wait()
        logger.info("Crawler process terminated")
    global analytics_process
    if analytics_process:
        analytics_process.terminate()
        analytics_process.wait()
        logger.info("Analytics process terminated")

# Register cleanup handler
signal.signal(signal.SIGINT, lambda s, f: cleanup())
signal.signal(signal.SIGTERM, lambda s, f: cleanup())

if __name__ == "__main__":
    # Start the crawler when the server starts
    start_crawler()
    start_analytics_server()
    # Start the server
    uvicorn.run(app, host="0.0.0.0", port=8000)