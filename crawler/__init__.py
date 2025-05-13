"""
RW Domain Crawler Package
"""

import logging
from datetime import datetime
import os

# Create logs directory if it doesn't exist
os.makedirs("crawler/logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("crawler/logs/rw_crawler.log", mode='a')
    ]
)
logger = logging.getLogger("RWCrawler")

# Global state for dashboard
crawler_state = {
    "is_running": False,
    "pages_crawled": 0,
    "domains_discovered": 0,
    "start_time": None,
    "elapsed_time": 0
}

from .crawler import RWCrawler, crawler_state

__all__ = ['RWCrawler', 'crawler_state'] 