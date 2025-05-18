from fastapi import FastAPI
from pydantic import BaseModel, field_validator
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import sqlite3
from contextlib import contextmanager
import threading
import os

app = FastAPI(title="Analytics API", description="API for handling analytics data")

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
    # Ensure the directory exists
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
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