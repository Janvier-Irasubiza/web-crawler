from fastapi import FastAPI, HTTPException
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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

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
            crawler_process = subprocess.Popen([sys.executable, "domain-crawler/rw_crawler.py"])
            logger.info("Domain crawler process started")
            return True
        except Exception as e:
            logger.error(f"Error starting crawler: {e}")
            return False
    return True

def start_analytics():
    global analytics_process
    if analytics_process is None:
        try:
            # Start the analytics as a subprocess
            analytics_process = subprocess.Popen([sys.executable, "analytics/server.py"])
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
    start_analytics()
    # Start the server
    uvicorn.run(app, host="0.0.0.0", port=8000)