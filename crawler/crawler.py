#!/usr/bin/env python3
"""
RW Domain Crawler - A web crawler that discovers websites with .rw domain extension
"""

import argparse
import re
import time
import random
import urllib.parse
from urllib.robotparser import RobotFileParser
from collections import deque
import json
import logging
from datetime import datetime
import os

import requests
from bs4 import BeautifulSoup

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

class RWCrawler:
    """Web crawler that discovers .rw domain websites"""
    
    def __init__(self, 
                 start_urls=None, 
                 max_pages=1000,
                 delay=1.0,
                 timeout=10,
                 respect_robots=True,
                 output_file="crawler/data/rw_domains.json"):
        """
        Initialize the crawler with parameters
        
        Args:
            start_urls (list): Initial URLs to start crawling from
            max_pages (int): Maximum number of pages to crawl
            delay (float): Delay between requests in seconds
            timeout (int): Request timeout in seconds
            respect_robots (bool): Whether to respect robots.txt
            output_file (str): File to save discovered domains
        """
        self.start_urls = start_urls or [
            "https://www.google.com/search?q=site:.rw",  
            "https://www.gov.rw/",
            "https://www.irembo.gov.rw/",
            "https://www.rw/"
        ]
        self.max_pages = max_pages
        self.delay = delay
        self.timeout = timeout
        self.respect_robots = respect_robots
        self.output_file = output_file
        
        # Data structures for crawling
        self.queue = deque()
        self.visited_urls = set()
        self.discovered_domains = set()
        self.robots_cache = {}  # Cache robots.txt parsing results
        
        # User agent
        self.user_agent = "RWCrawler/1.0 (+https://github.com/yourusername/rwcrawler)"
        self.headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml",
            "Accept-Language": "en-US,en;q=0.9",
        }
        
        # Reset crawler state
        crawler_state["pages_crawled"] = 0
        crawler_state["domains_discovered"] = 0
        crawler_state["elapsed_time"] = 0
    
    def is_allowed_by_robots(self, url):
        """Check if the URL is allowed by robots.txt"""
        if not self.respect_robots:
            return True
            
        parsed_url = urllib.parse.urlparse(url)
        robots_url = f"{parsed_url.scheme}://{parsed_url.netloc}/robots.txt"
        
        if robots_url in self.robots_cache:
            rp = self.robots_cache[robots_url]
        else:
            rp = RobotFileParser()
            rp.set_url(robots_url)
            try:
                rp.read()
                self.robots_cache[robots_url] = rp
            except Exception as e:
                logger.warning(f"Could not fetch robots.txt from {robots_url}: {e}")
                return True  # If we can't get robots.txt, we'll assume it's allowed
                
        return rp.can_fetch(self.user_agent, url)
    
    def normalize_url(self, url, base_url=None):
        """Normalize the URL by handling relative URLs and removing fragments"""
        if base_url:
            url = urllib.parse.urljoin(base_url, url)
        
        # Parse the URL and remove fragments
        parsed = urllib.parse.urlparse(url)
        normalized = urllib.parse.urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            parsed.query,
            ''  # No fragment
        ))
        
        return normalized
    
    def is_valid_url(self, url):
        """Check if a URL is valid and should be crawled"""
        try:
            parsed = urllib.parse.urlparse(url)
            
            # Check scheme
            if parsed.scheme not in ['http', 'https']:
                return False
                
            # Skip common non-HTML content
            skip_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.gif', '.svg', 
                              '.css', '.js', '.xml', '.json', '.zip', '.doc', 
                              '.docx', '.ppt', '.pptx', '.xls', '.xlsx']
            if any(parsed.path.lower().endswith(ext) for ext in skip_extensions):
                return False
                
            return True
        except Exception:
            return False
    
    def is_rw_domain(self, url):
        """Check if the URL is from a .rw domain"""
        try:
            parsed = urllib.parse.urlparse(url)
            return parsed.netloc.lower().endswith('.rw')
        except Exception:
            return False

    def extract_links(self, html_content, base_url):
        """Extract links from HTML content"""
        soup = BeautifulSoup(html_content, 'html.parser')
        links = []
        
        for anchor in soup.find_all('a', href=True):
            href = anchor['href'].strip()
            if href and not href.startswith(('javascript:', 'mailto:', 'tel:')):
                normalized_url = self.normalize_url(href, base_url)
                if self.is_valid_url(normalized_url):
                    links.append(normalized_url)
        
        return links
    
    def crawl_url(self, url):
        """Crawl a single URL and extract links"""
        if url in self.visited_urls:
            return []
            
        self.visited_urls.add(url)
        
        # Check robots.txt
        if not self.is_allowed_by_robots(url):
            logger.info(f"Skipping {url} (disallowed by robots.txt)")
            return []
            
        # Add delay before making the request
        time.sleep(self.delay + random.uniform(0, 0.5))
        
        logger.info(f"Crawling: {url}")
        
        try:
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            
            if response.status_code != 200:
                logger.warning(f"Failed to fetch {url}: HTTP {response.status_code}")
                return []
                
            content_type = response.headers.get('Content-Type', '')
            if 'text/html' not in content_type.lower():
                logger.debug(f"Skipping non-HTML content: {url}")
                return []
                
            # Check if this is a .rw domain
            if self.is_rw_domain(url):
                domain = urllib.parse.urlparse(url).netloc
                if domain not in self.discovered_domains:
                    self.discovered_domains.add(domain)
                    crawler_state["domains_discovered"] = len(self.discovered_domains)
                    logger.info(f"Discovered new .rw domain: {domain}")
            
            # Extract links
            links = self.extract_links(response.text, url)
            logger.debug(f"Found {len(links)} links on {url}")
            return links
            
        except requests.Timeout:
            logger.warning(f"Request timed out for {url}")
        except requests.RequestException as e:
            logger.warning(f"Failed to fetch {url}: {e}")
        except Exception as e:
            logger.error(f"Error processing {url}: {e}")
            
        return []

    def save_results(self):
        """Save discovered domains to a JSON file"""
        domains_list = sorted(list(self.discovered_domains))
        result = {
            "total_rw_domains": len(domains_list),
            "crawl_date": datetime.now().isoformat(),
            "domains": domains_list
        }
        
        with open(self.output_file, 'w') as f:
            json.dump(result, f, indent=2)
            
        logger.info(f"Saved {len(domains_list)} domains to {self.output_file}")
        
    def run(self):
        """Run the crawler"""
        # Initialize the queue with start URLs
        for url in self.start_urls:
            self.queue.append(url)
            
        pages_crawled = 0
        start_time = time.time()
        
        logger.info(f"Starting crawl with {len(self.start_urls)} seed URLs")
        
        # Main crawling loop
        while self.queue and pages_crawled < self.max_pages:
            url = self.queue.popleft()
            
            if url in self.visited_urls:
                continue
                
            # Crawl the URL and get new links
            new_links = self.crawl_url(url)
            pages_crawled += 1
            crawler_state["pages_crawled"] = pages_crawled
            
            # Process the new links
            for link in new_links:
                if link not in self.visited_urls:
                    self.queue.append(link)
            
            # Periodically save results
            if pages_crawled % 100 == 0:
                self.save_results()
                elapsed = time.time() - start_time
                crawler_state["elapsed_time"] = int(elapsed)
                logger.info(f"Progress: {pages_crawled}/{self.max_pages} pages, "
                           f"{len(self.discovered_domains)} .rw domains, "
                           f"{elapsed:.1f} seconds elapsed")
        
        # Final save
        self.save_results()
        
        elapsed = time.time() - start_time
        crawler_state["elapsed_time"] = int(elapsed)
        logger.info(f"Crawl completed: {pages_crawled} pages crawled, "
                   f"{len(self.discovered_domains)} .rw domains discovered, "
                   f"{elapsed:.1f} seconds elapsed")
        
        return self.discovered_domains

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Crawl the web for .rw domains")
    parser.add_argument("--start-urls", nargs="+", help="URLs to start crawling from")
    parser.add_argument("--max-pages", type=int, default=1000, help="Maximum pages to crawl")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between requests (seconds)")
    parser.add_argument("--timeout", type=int, default=10, help="Request timeout (seconds)")
    parser.add_argument("--output", default="rw_domains.json", help="Output file path")
    parser.add_argument("--no-robots", action="store_true", help="Ignore robots.txt")
    args = parser.parse_args()
    
    # Create output directory if it doesn't exist
    output_dir = os.path.dirname(args.output)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Start the dashboard server
    from dashboard import app
    import threading
    import webbrowser
    
    def run_dashboard():
        app.run(debug=False, port=5000)
    
    # Initialize crawler state
    crawler_state["is_running"] = False
    crawler_state["start_time"] = None
    crawler_state["pages_crawled"] = 0
    crawler_state["domains_discovered"] = 0
    crawler_state["elapsed_time"] = 0
    
    # Start the dashboard in a separate thread
    dashboard_thread = threading.Thread(target=run_dashboard)
    dashboard_thread.daemon = True
    dashboard_thread.start()
    
    # Open the dashboard in the default web browser
    webbrowser.open('http://localhost:5000')
    
    # Initialize the crawler
    crawler = RWCrawler(
        start_urls=args.start_urls,
        max_pages=args.max_pages,
        delay=args.delay,
        timeout=args.timeout,
        respect_robots=not args.no_robots,
        output_file=args.output
    )
    
    # Wait for user input before starting
    input("Press Enter to start crawling...")
    
    # Set running state to True
    crawler_state["is_running"] = True
    crawler_state["start_time"] = datetime.now()
    
    try:
        crawler.run()
    finally:
        crawler_state["is_running"] = False
        crawler_state["start_time"] = None

if __name__ == "__main__":
        main()