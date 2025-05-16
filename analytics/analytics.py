from fastapi import FastAPI, Request, Depends, HTTPException
from pydantic import BaseModel, field_validator
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import sqlite3
import json
import uvicorn
from typing import Any
from contextlib import contextmanager
import threading

app = FastAPI(title="Analytics Server")
PORT = 3001

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, set this to your specific domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database setup 
DB_PATH = "data/analytics.db"

def init_db():
    """Initialize the SQLite database with required tables"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create analytics_events table with domain field
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS analytics_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        domain TEXT,
        event_type TEXT,
        timestamp TEXT NOT NULL,
        page_views INTEGER DEFAULT 0,
        time_spent REAL DEFAULT 0,
        request_ip TEXT,
        raw_data TEXT NOT NULL
    )
    ''')
    
    # Create index on domain for faster lookups
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_domain ON analytics_events(domain)')
    
    # Create index on timestamp for faster date filtering
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON analytics_events(timestamp)')
    
    # Create index on session_id for faster lookups
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_session_id ON analytics_events(session_id)')
    
    # Create index on request_ip for faster lookups
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_request_ip ON analytics_events(request_ip)')
    
    # Create regions table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS regions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL,
        city TEXT,
        region TEXT,
        country TEXT,
        ip TEXT,
        FOREIGN KEY (event_id) REFERENCES analytics_events(id)
    )
    ''')
    
    conn.commit()
    conn.close()

# Initialize DB at startup
init_db()

# Thread-safe database connection management
local = threading.local()

@contextmanager
def get_db():
    """Thread-safe database connection management"""
    if not hasattr(local, 'db'):
        local.db = sqlite3.connect(DB_PATH)
        local.db.row_factory = sqlite3.Row
    try:
        yield local.db
    except Exception as e:
        local.db.rollback()
        raise e
    else:
        local.db.commit()

# Pydantic models for request validation
class RegionData(BaseModel):
    city: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None
    ip: Optional[str] = None

class AnalyticsData(BaseModel):
    sessionId: str
    domain: Optional[str] = None
    eventType: Optional[str] = None
    timestamp: Optional[str] = None
    pageViews: Optional[int] = 0
    timeSpent: Optional[float] = 0
    region: Optional[RegionData] = None

    class Config:
        extra = "allow"

    @field_validator('timestamp', mode='before')
    def validate_timestamp(cls, v: str) -> str:
        if not v:
            return datetime.now().isoformat()
        try:
            # Try to parse the date string in ISO format
            datetime.fromisoformat(v.replace('Z', '+00:00'))
            return v
        except ValueError:
            raise ValueError("Date must be in ISO format (YYYY-MM-DDTHH:MM:SS)")

# Request model for analytics query
class AnalyticsQuery(BaseModel):
    domain: Optional[str] = None
    ip: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    
    @field_validator('start_date', 'end_date')
    def validate_date_format(cls, v: str) -> str:
        if v:
            try:
                # Try to parse the date string in ISO format
                datetime.fromisoformat(v.replace('Z', '+00:00'))
                return v
            except ValueError:
                raise ValueError("Date must be in ISO format (YYYY-MM-DDTHH:MM:SS)")
        return v

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
async def get_analytics(
    domain: Optional[str] = None,
    ip: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> dict[str, Any]:
    if not domain and not ip:
        raise HTTPException(status_code=400, detail="Either domain or IP must be provided")
    
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
        
        if domain:
            query += " AND e.domain = ?"
            params.append(domain)
        
        if ip:
            query += " AND (e.request_ip = ? OR r.ip = ?)"
            params.append(ip)
            params.append(ip)
        
        if start_date:
            query += " AND e.timestamp >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND e.timestamp <= ?"
            params.append(end_date)
        
        # Order by timestamp
        query += " ORDER BY e.timestamp DESC"
        
        try:
            cursor.execute(query, params)
            results = cursor.fetchall()
            
            # Convert to list of dicts
            from typing import List
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
async def get_analytics_summary(
    domain: Optional[str] = None,
    ip: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> dict[str, Any]:
    with get_db() as conn:
        cursor = conn.cursor()
    
        # Base query conditions
        where_clause = "WHERE 1=1"
        params: list[str] = []
    
        if domain:
            where_clause += " AND e.domain = ?"
            params.append(domain)
    
        if ip:
            where_clause += " AND (e.request_ip = ? OR r.ip = ?)"
            params.append(ip)
            params.append(ip)
    
        if start_date:
            where_clause += " AND e.timestamp >= ?"
            params.append(start_date)
    
        if end_date:
            where_clause += " AND e.timestamp <= ?"
            params.append(end_date)
    
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

if __name__ == "__main__":
    print(f"Analytics server running on port {PORT}")
    print(f"API documentation available at http://localhost:{PORT}/docs")
    uvicorn.run(app, host="0.0.0.0", port=PORT)