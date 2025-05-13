from urllib.parse import urlparse, urljoin
from collections import deque
import json
import datetime
import logging
import os
import requests
import random
import time
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import concurrent.futures
import urllib.parse

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/crawler.log', mode='a', encoding='utf-8', delay=True),
        logging.StreamHandler()
    ]
)

class RwDomainCrawler:
    def __init__(self, search_engines=None, max_pages=1000000, max_depth=3, output_dir='data', 
                 use_proxies=True, use_selenium=True, concurrent_requests=3):
        """
        Initialize the crawler with starting points and parameters
        
        Args:
            search_engines: List of search engines to use
            max_pages: Maximum number of pages to crawl
            max_depth: Maximum depth to crawl
            output_dir: Directory to save output
            use_proxies: Whether to use proxy rotation
            use_selenium: Whether to use Selenium for browser automation
            concurrent_requests: Number of concurrent requests
        """
        self.search_engines = search_engines or [
            'google', 
            'bing', 
            'duckduckgo', 
            'yandex', 
            'yahoo',
            'baidu',
            'ecosia'
        ]

        self.domain_data = {}
        self.visited_urls = set()
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.output_dir = output_dir
        self.use_proxies = use_proxies
        self.use_selenium = use_selenium
        self.concurrent_requests = concurrent_requests
        self.user_agent = UserAgent()
        
        # Session cookies
        self.cookies = {}
        
        # Initialize proxy list
        self.proxies = self.init_proxies() if use_proxies else []
        
        # Selenium WebDriver instances
        self.drivers = {}

        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Create logs directory if it doesn't exist
        os.makedirs('logs', exist_ok=True)

    def init_proxies(self):
        """
        Initialize list of proxies from free proxy services
        """
        try:
            # You can use a free proxy service API or a paid proxy service
            # This is a simplified example - in production, use a reliable proxy service
            response = requests.get('https://proxylist.geonode.com/api/proxy-list?limit=50&page=1&sort_by=lastChecked&sort_type=desc&filterUpTime=90&protocols=http%2Chttps')
            data = response.json()
            
            proxies = [f"{proxy['protocols'][0]}://{proxy['ip']}:{proxy['port']}" 
                      for proxy in data.get('data', []) if proxy['protocols']]
            
            logging.info(f"Loaded {len(proxies)} proxies")
            return proxies
        except Exception as e:
            logging.error(f"Error loading proxies: {str(e)}")
            # Fallback to a minimal list as backup
            return [
                'http://localhost:8118',  # If you're running Privoxy or another local proxy
            ]

    def get_random_proxy(self):
        """Get a random proxy from the list"""
        if not self.proxies:
            return None
        return random.choice(self.proxies)
    
    def get_random_user_agent(self):
        """Get a random user agent"""
        return self.user_agent.random
    
    def init_selenium_driver(self, engine):
        """Initialize Selenium WebDriver for a specific search engine"""
        if not self.use_selenium:
            return None
            
        if engine in self.drivers:
            return self.drivers[engine]
            
        try:
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument(f"user-agent={self.get_random_user_agent()}")
            
            # Add proxy if available
            if self.use_proxies and self.proxies:
                proxy = self.get_random_proxy()
                if proxy:
                    chrome_options.add_argument(f'--proxy-server={proxy}')
            
            # Initialize the WebDriver
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Set page load timeout
            driver.set_page_load_timeout(20)
            
            # Store the driver
            self.drivers[engine] = driver
            return driver
            
        except Exception as e:
            logging.error(f"Error initializing Selenium WebDriver for {engine}: {str(e)}")
            return None
    
    def close_selenium_drivers(self):
        """Close all Selenium WebDriver instances"""
        for engine, driver in self.drivers.items():
            try:
                driver.quit()
                logging.info(f"Closed Selenium WebDriver for {engine}")
            except Exception as e:
                logging.error(f"Error closing Selenium WebDriver for {engine}: {str(e)}")
    
    def is_valid_url(self, url):
        """Check if the url is valid and should be processed"""
        try:
            # Parse the url
            parsed_url = urlparse(url)
            
            # Log the parsed URL components
            logging.debug(f"Parsing URL: {url}")
            logging.debug(f"Scheme: {parsed_url.scheme}, Netloc: {parsed_url.netloc}")
            
            # Check if the URL is valid
            is_valid = bool(parsed_url.netloc) and bool(parsed_url.scheme) and parsed_url.scheme in ['http', 'https']
            
            if not is_valid:
                logging.debug(f"Invalid URL: {url} - Scheme: {parsed_url.scheme}, Netloc: {parsed_url.netloc}")
            
            return is_valid
        except Exception as e:
            logging.error(f"Error validating URL {url}: {str(e)}")
            return False
        
    def is_rw_domain(self, url):
        """Check if the url is a .rw domain"""
        try:
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.lower()
            
            # Log domain check
            logging.debug(f"Checking domain: {domain}")
            
            # Check for .rw TLD
            is_rw = domain.endswith('.rw')
            
            if is_rw:
                logging.info(f"Found .rw domain: {domain}")
            else:
                logging.debug(f"Not a .rw domain: {domain}")
            
            return is_rw
        except Exception as e:
            logging.error(f"Error checking .rw domain for {url}: {str(e)}")
            return False
        
    def normalize_domain(self, domain):
        """Normalize domain by removing www. prefix"""
        if not domain:
            return domain
            
        domain = domain.lower()
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain

    def extract_domain(self, url):
        """Extract domain from the url"""
        try:
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.lower()
            
            # Log domain extraction
            logging.debug(f"Extracting domain from URL: {url}")
            logging.debug(f"Extracted domain: {domain}")
            
            normalized = self.normalize_domain(domain)
            logging.debug(f"Normalized domain: {normalized}")
            
            return normalized
        except Exception as e:
            logging.error(f"Error extracting domain from {url}: {str(e)}")
            return None
    
    def extract_page_info(self, url, soup):
        """Extract additional information from page content"""
        info = {}
        
        # Extract title
        title_tag = soup.find('title')
        if title_tag and title_tag.text:
            info['title'] = title_tag.text.strip()
        
        # Extract meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            info['description'] = meta_desc.get('content').strip()
            
        # Extract meta keywords
        meta_keywords = soup.find('meta', attrs={'name': 'keywords'})
        if meta_keywords and meta_keywords.get('content'):
            info['keywords'] = meta_keywords.get('content').strip()
            
        # Extract h1 tags
        h1_tags = soup.find_all('h1')
        if h1_tags:
            info['h1_tags'] = [h1.text.strip() for h1 in h1_tags if h1.text.strip()]
        
        return info
        
    def crawl(self):
        """Main crawling function"""
        logging.info("Starting enhanced web crawler for .rw domains")
        logging.info(f"Max pages: {self.max_pages}, Max depth: {self.max_depth}")
        logging.info(f"Using proxies: {self.use_proxies}, Using Selenium: {self.use_selenium}")
        
        # Initialize variables
        visited_urls = set()
        urls_to_visit = deque()
        total_pages = 0
        start_time = datetime.datetime.now()

        # Start searching for .rw domains from search engines
        try:
            # Use multiple threads for search engine crawling
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(self.search_engines), 5)) as executor:
                future_to_engine = {
                    executor.submit(self.search_engine_crawl, engine, visited_urls, urls_to_visit): engine
                    for engine in self.search_engines
                }
                
                for future in concurrent.futures.as_completed(future_to_engine):
                    engine = future_to_engine[future]
                    try:
                        future.result()
                        logging.info(f"Completed search engine crawl for {engine}")
                    except Exception as e:
                        logging.error(f"Error in search engine crawl for {engine}: {str(e)}")
        except Exception as e:
            logging.error(f"Error in concurrent search engine crawling: {str(e)}")

        # Process the remaining urls with multiple workers
        try:
            while urls_to_visit and total_pages < self.max_pages:
                # Get a batch of URLs to process concurrently
                batch_size = min(self.concurrent_requests, len(urls_to_visit))
                batch = []
                
                for _ in range(batch_size):
                    if urls_to_visit:
                        url, depth = urls_to_visit.popleft()
                        if url not in visited_urls and self.is_valid_url(url):
                            batch.append((url, depth))
                            visited_urls.add(url)
                
                if not batch:
                    continue
                
                # Process batch with thread pool
                with concurrent.futures.ThreadPoolExecutor(max_workers=self.concurrent_requests) as executor:
                    future_to_url = {
                        executor.submit(self.process_url, url, depth, visited_urls, urls_to_visit): url
                        for url, depth in batch
                    }
                    
                    for future in concurrent.futures.as_completed(future_to_url):
                        url = future_to_url[future]
                        try:
                            success = future.result()
                            if success:
                                total_pages += 1
                                
                            if total_pages % 10 == 0:  # Log progress every 10 pages
                                elapsed_time = datetime.datetime.now() - start_time
                                logging.info(f"Progress: {total_pages} pages crawled in {elapsed_time}")
                                
                            if total_pages >= self.max_pages:
                                break
                                
                        except Exception as e:
                            logging.error(f"Error processing URL {url}: {str(e)}")
                
                # Randomized delay between batches
                time.sleep(random.uniform(0.5, 2.0))
                
                # Save intermediate results periodically
                if total_pages % 50 == 0:
                    self.save_results(start_time)
        
        except Exception as e:
            logging.error(f"Error in main crawling loop: {str(e)}")
        
        finally:
            # Close all Selenium drivers
            if self.use_selenium:
                self.close_selenium_drivers()

            # Log final statistics
            end_time = datetime.datetime.now()
            duration = end_time - start_time
            logging.info("Crawling completed")
            logging.info(f"Total pages crawled: {total_pages}")
            logging.info(f"Total unique domains found: {len(self.domain_data)}")
            logging.info(f"Total time taken: {duration}")
            if duration.total_seconds() > 0:
                logging.info(f"Average speed: {total_pages/duration.total_seconds():.2f} pages/second")

            # Save final results
            self.save_results(start_time)

        return self.domain_data

    def process_url(self, url, depth, visited_urls, urls_to_visit):
        """Process a single URL and extract information"""
        try:
            if not self.is_valid_url(url) or not self.is_rw_domain(url):
                return False
                
            logging.info(f"Processing URL: {url} (depth: {depth})")
            
            # Get the domain of the url
            domain = self.extract_domain(url)
            
            # Fetch and parse the page
            soup, new_urls = self.fetch_and_parse_page(url)
            
            if not soup:
                return False
                
            # Extract page info
            page_info = self.extract_page_info(url, soup)
            
            # Filter new URLs and add them to queue
            if depth < self.max_depth:
                filtered_urls = [(u, depth + 1) for u in new_urls 
                                if u not in visited_urls and self.is_valid_url(u)]
                urls_to_visit.extend(filtered_urls)
                logging.info(f"Found {len(filtered_urls)} new URLs on {url}")
            
            # Add the domain to the results if it's a .rw domain
            if self.is_rw_domain(url):
                normalized_domain = self.normalize_domain(domain)
                if normalized_domain not in self.domain_data:
                    self.domain_data[normalized_domain] = {
                        'domain': normalized_domain,
                        'url': url
                    }
                    
                    # Add additional info if available
                    if page_info:
                        self.domain_data[normalized_domain].update(page_info)
                        
                    logging.info(f"Discovered new .rw domain: {normalized_domain}")
                else:
                    logging.debug(f"Skipping duplicate domain: {normalized_domain}")
            
            return True
            
        except Exception as e:
            logging.error(f"Error processing URL {url}: {str(e)}")
            return False

    def fetch_and_parse_page(self, url):
        """Fetch a webpage and parse it to extract content and links"""
        try:
            # Choose between regular request or Selenium based on settings
            if self.use_selenium and random.random() < 0.7:  # Use Selenium 70% of the time when enabled
                return self.fetch_with_selenium(url)
            else:
                return self.fetch_with_requests(url)
        except Exception as e:
            logging.error(f"Error fetching page {url}: {str(e)}")
            return None, []

    def fetch_with_requests(self, url):
        """Fetch page using requests library"""
        try:
            # Random delay before request
            time.sleep(random.uniform(1, 3))
            
            # Prepare headers with random user agent
            headers = {
                'User-Agent': self.get_random_user_agent(),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': 'https://www.google.com/',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Cache-Control': 'max-age=0',
            }
            
            # Use proxy if enabled
            proxies = None
            if self.use_proxies and self.proxies:
                proxy = self.get_random_proxy()
                if proxy:
                    proxies = {'http': proxy, 'https': proxy}
            
            # Send the request
            session = requests.Session()
            
            # Add cookies if available for this domain
            domain = self.extract_domain(url)
            if domain in self.cookies:
                for cookie_name, cookie_value in self.cookies[domain].items():
                    session.cookies.set(cookie_name, cookie_value, domain=domain)
            
            response = session.get(
                url,
                headers=headers,
                proxies=proxies,
                timeout=15,
                allow_redirects=True
            )
            
            # Save cookies for future use
            self.cookies[domain] = dict(session.cookies)
            
            # Parse the response
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract links
            links = soup.find_all('a')
            urls = []
            
            for link in links:
                href = link.get('href')
                if href:
                    # Handle relative URLs
                    if not bool(urlparse(href).netloc):
                        href = urljoin(url, href)
                    urls.append(href)
            
            return soup, urls
            
        except Exception as e:
            logging.error(f"Error in fetch_with_requests for {url}: {str(e)}")
            return None, []

    def fetch_with_selenium(self, url):
        """Fetch page using Selenium WebDriver for better JS support"""
        try:
            # Get or create a driver
            driver = self.init_selenium_driver('general')
            if not driver:
                return self.fetch_with_requests(url)
            
            # Random delay
            time.sleep(random.uniform(2, 5))
            
            # Load the page
            driver.get(url)
            
            # Wait for the page to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Additional random wait to let JavaScript load
            time.sleep(random.uniform(1, 3))
            
            # Scroll down to load lazy content
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
            time.sleep(0.5)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            time.sleep(0.5)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(0.5)
            
            # Get page source
            page_source = driver.page_source
            
            # Parse with BeautifulSoup
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Extract links
            urls = []
            elements = driver.find_elements(By.TAG_NAME, 'a')
            
            for element in elements:
                try:
                    href = element.get_attribute('href')
                    if href:
                        urls.append(href)
                except:
                    continue
            
            return soup, urls
            
        except Exception as e:
            logging.error(f"Error in fetch_with_selenium for {url}: {str(e)}")
            return None, []

    def search_engine_crawl(self, engine, visited_urls, urls_to_visit):
        """Crawl the search engine for .rw domains with advanced techniques"""
        try:
            logging.info(f"Starting search engine crawl for {engine}")
            
            # Define search queries for better coverage
            search_queries = [
                "site:.rw",  # Basic .rw domain search
                "site:.rw -www",  # Exclude www subdomains
                "site:.rw inurl:www",  # Include www subdomains
                "site:.rw inurl:gov",  # Government sites
                "site:.rw inurl:edu",  # Educational sites
                "site:.rw inurl:org",  # Organizations
                "site:.rw inurl:com",  # Commercial sites
                "site:.rw inurl:net",  # Network sites
                "site:.rw inurl:info",  # Information sites
                "site:.rw inurl:co",   # Company sites
                "site:.rw inurl:ac",   # Academic sites
                "site:.rw inurl:sch",  # School sites
                "site:.rw inurl:blog", # Blog sites
                "site:.rw inurl:news", # News sites
                "site:.rw inurl:mail", # Mail servers
                "site:.rw inurl:ftp",  # FTP servers
                "site:.rw inurl:shop", # Shopping sites
                "site:.rw inurl:store",# Store sites
                "site:.rw inurl:forum",# Forum sites
                "site:.rw inurl:wiki"  # Wiki sites
            ]
            
            # Define search engine specific parameters
            engine_params = {
                'yandex': {
                    'base_url': 'https://yandex.com/search',
                    'param_name': 'text',
                    'page_param': 'p',
                    'results_per_page': 10,
                    'max_pages': 10
                },
                'google': {
                    'base_url': 'https://www.google.com/search',
                    'param_name': 'q',
                    'page_param': 'start',
                    'results_per_page': 10,
                    'max_pages': 10
                },
                'bing': {
                    'base_url': 'https://www.bing.com/search',
                    'param_name': 'q',
                    'page_param': 'first',
                    'results_per_page': 10,
                    'max_pages': 10
                },
                'duckduckgo': {
                    'base_url': 'https://duckduckgo.com/html',
                    'param_name': 'q',
                    'page_param': 's',
                    'results_per_page': 30,
                    'max_pages': 5
                },
                'yahoo': {
                    'base_url': 'https://search.yahoo.com/search',
                    'param_name': 'p',
                    'page_param': 'b',
                    'results_per_page': 10,
                    'max_pages': 10
                },
                'baidu': {
                    'base_url': 'https://www.baidu.com/s',
                    'param_name': 'wd',
                    'page_param': 'pn',
                    'results_per_page': 10,
                    'max_pages': 10
                },
                'ecosia': {
                    'base_url': 'https://www.ecosia.org/search',
                    'param_name': 'q',
                    'page_param': 'p',
                    'results_per_page': 10,
                    'max_pages': 10
                }
            }
            
            if engine not in engine_params:
                logging.warning(f"Unsupported search engine: {engine}")
                return
            
            params = engine_params[engine]
            total_urls_found = 0
            driver = None
            
            # Use Selenium for search engines if enabled
            if self.use_selenium:
                driver = self.init_selenium_driver(engine)
                if not driver:
                    logging.error(f"Failed to initialize Selenium driver for {engine}")
                    return
            
            # Process each search query
            for search_query in search_queries:
                logging.info(f"Processing query '{search_query}' on {engine}")
                
                # Process pages for this query
                for page in range(params['max_pages']):
                    try:
                        logging.info(f"Crawling {engine} page {page + 1}/{params['max_pages']} for query '{search_query}'")
                        
                        # Randomized longer delay between pages
                        time.sleep(random.uniform(3, 7))
                        
                        if driver and self.use_selenium:
                            new_urls = self.search_engine_page_selenium(
                                driver, engine, params, search_query, page
                            )
                            logging.info(f"Selenium found {len(new_urls)} URLs on {engine} page {page + 1}")
                        else:
                            new_urls = self.search_engine_page_requests(
                                engine, params, search_query, page
                            )
                            logging.info(f"Requests found {len(new_urls)} URLs on {engine} page {page + 1}")
                        
                        # Log all found URLs for debugging
                        for url in new_urls:
                            logging.debug(f"Found URL: {url}")
                            if self.is_rw_domain(url):
                                logging.info(f"Found .rw domain: {url}")
                        
                        # Filter and add new URLs
                        valid_urls = [(url, 0) for url in new_urls 
                                    if self.is_valid_url(url) and 
                                    self.is_rw_domain(url) and 
                                    url not in visited_urls]
                        
                        logging.info(f"Found {len(valid_urls)} valid .rw domains on {engine} page {page + 1}")
                        
                        # Add unique URLs to the queue
                        for url_data in valid_urls:
                            if url_data[0] not in visited_urls:
                                urls_to_visit.append(url_data)
                                visited_urls.add(url_data[0])
                                logging.info(f"Added new .rw domain to queue: {url_data[0]}")
                        
                        total_urls_found += len(valid_urls)
                        
                        # Break early if no results found
                        if len(new_urls) == 0:
                            logging.info(f"No results found for {engine} on page {page + 1}, moving to next query")
                            break
                        
                    except Exception as e:
                        logging.error(f"Error crawling {engine} page {page + 1}: {str(e)}")
                        continue
            
            logging.info(f"Completed {engine} crawl. Total new .rw domains found: {total_urls_found}")
            
        except Exception as e:
            logging.error(f"Error in search_engine_crawl for {engine}: {str(e)}")
    
    def search_engine_page_requests(self, engine, params, search_query, page):
        """Get search results from a search engine page using requests"""
        try:
            # Construct the URL with pagination
            query_params = {
                params['param_name']: search_query,
                params['page_param']: page * params['results_per_page']
            }
            
            # Add headers to mimic a browser
            headers = {
                'User-Agent': self.get_random_user_agent(),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': 'https://www.google.com/',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            
            # Use proxy if enabled
            proxies = None
            if self.use_proxies and self.proxies:
                proxy = self.get_random_proxy()
                if proxy:
                    proxies = {'http': proxy, 'https': proxy}
                    logging.info(f"Using proxy: {proxy}")
            
            # Send the request to the search engine
            session = requests.Session()
            
            # Add cookies if available for this engine
            if engine in self.cookies:
                for cookie_name, cookie_value in self.cookies[engine].items():
                    session.cookies.set(cookie_name, cookie_value, domain=urlparse(params['base_url']).netloc)
            
            full_url = f"{params['base_url']}?{urllib.parse.urlencode(query_params)}"
            logging.info(f"Requesting URL: {full_url}")
            
            response = session.get(
                params['base_url'],
                params=query_params,
                headers=headers,
                proxies=proxies,
                timeout=15
            )
            
            logging.info(f"Response status code: {response.status_code}")
            
            # Save cookies for future use
            self.cookies[engine] = dict(session.cookies)
            
            # Parse the response
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract URLs based on the search engine
            urls = self.extract_urls_from_search_results(engine, soup)
            
            logging.info(f"Extracted {len(urls)} URLs from {engine} response")
            
            return urls
            
        except Exception as e:
            logging.error(f"Error in search_engine_page_requests for {engine}: {str(e)}")
            return []
    
    def search_engine_page_selenium(self, driver, engine, params, search_query, page):
        """Get search results from a search engine page using Selenium"""
        try:
            # Construct the URL with pagination
            url = params['base_url']
            query_params = {
                params['param_name']: search_query,
                params['page_param']: page * params['results_per_page']
            }
            
            # Construct the full URL
            query_string = '&'.join([f"{k}={v}" for k, v in query_params.items()])
            full_url = f"{url}?{query_string}"
            
            logging.info(f"Navigating to URL: {full_url}")
            
            # Navigate to the URL
            driver.get(full_url)
            
            # Wait for the page to load
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Additional wait to let JavaScript load
            time.sleep(random.uniform(2, 5))
            
            # Scroll down to load all results
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
            time.sleep(1)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            time.sleep(1)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            
            # Get page source
            page_source = driver.page_source
            
            # Parse with BeautifulSoup
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Extract URLs based on the search engine
            urls = self.extract_urls_from_search_results(engine, soup)
            
            logging.info(f"Extracted {len(urls)} URLs from {engine} page source")
            
            # Also extract directly from Selenium links
            selenium_urls = []
            selectors = {
                'google': 'div.g a',
                'bing': 'li.b_algo h2 a',
                'yahoo': 'div.algo-sr a',
                'duckduckgo': 'a.result__a',
                'yandex': 'div.organic__url-text a',
                'baidu': 'h3.t a',
                'ecosia': 'div.result a.result-title'
            }
            
            if engine in selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selectors[engine])
                    logging.info(f"Found {len(elements)} elements using selector for {engine}")
                    
                    for element in elements:
                        try:
                            href = element.get_attribute('href')
                            if href and self.is_valid_url(href):
                                selenium_urls.append(href)
                        except:
                            continue
                except Exception as e:
                    logging.error(f"Error extracting Selenium URLs for {engine}: {str(e)}")
            
            # Combine and deduplicate URLs
            all_urls = list(set(urls + selenium_urls))
            logging.info(f"Total unique URLs found (BeautifulSoup + Selenium): {len(all_urls)}")
            
            return all_urls
            
        except Exception as e:
            logging.error(f"Error in search_engine_page_selenium for {engine}: {str(e)}")
            return []
    
    def extract_urls_from_search_results(self, engine, soup):
        """Extract URLs from search results based on the search engine"""
        urls = []
        
        try:
            # Different CSS selectors for different search engines
            selectors = {
                'google': [
                    'div.g div.yuRUbf a',
                    'div.g h3.LC20lb a',
                    'div.g a.l',
                    'div.g a.C8nzq',
                    'div.yuRUbf a'
                ],
                'bing': [
                    'li.b_algo h2 a',
                    'li.b_algo a.tilk'
                ],
                'yahoo': [
                    'div.algo-sr a.ac-algo',
                    'h3.title a'
                ],
                'duckduckgo': [
                    'a.result__a',
                    'a.result__url',
                    'a.result-link'
                ],
                'yandex': [
                    'div.organic__url-text a',
                    'h2 a.link',
                    'div.organic a'
                ],
                'baidu': [
                    'h3.t a',
                    'div.result a'
                ],
                'ecosia': [
                    'div.result a.result-title',
                    'a.js-result-url'
                ]
            }
            
            # Try each selector for the engine
            if engine in selectors:
                for selector in selectors[engine]:
                    elements = soup.select(selector)
                    logging.info(f"Found {len(elements)} elements using selector '{selector}' for {engine}")
                    
                    for element in elements:
                        href = element.get('href')
                        if href:
                            # Clean and normalize the URL
                            if "url=" in href:  # Handle redirect URLs (common in search engines)
                                try:
                                    href = href.split("url=")[1].split("&")[0]
                                    # URL decode if needed
                                    href = urllib.parse.unquote(href)
                                    logging.debug(f"Extracted redirect URL: {href}")
                                except Exception as e:
                                    logging.error(f"Error processing redirect URL: {str(e)}")
                                    continue
                            
                            if self.is_valid_url(href):
                                urls.append(href)
                                logging.debug(f"Added valid URL: {href}")
                            else:
                                logging.debug(f"Skipped invalid URL: {href}")
            
            # Fallback method - just look for all links
            if not urls:
                logging.info(f"No URLs found with specific selectors for {engine}, trying fallback method")
                all_links = soup.find_all('a')
                logging.info(f"Found {len(all_links)} total links in page")
                
                for link in all_links:
                    href = link.get('href')
                    if href and self.is_valid_url(href):
                        urls.append(href)
                        logging.debug(f"Added URL from fallback: {href}")
            
            unique_urls = list(set(urls))  # Remove duplicates
            logging.info(f"Extracted {len(unique_urls)} unique URLs from {engine} search results")
            return unique_urls
            
        except Exception as e:
            logging.error(f"Error extracting URLs from {engine} search results: {str(e)}")
            return []

    def save_results(self, start_time=None):
        """Save the results to JSON format with enhanced metadata"""
        # Prepare timestamped filename
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"rw_domains_{timestamp}.json"
        json_filepath = os.path.join(self.output_dir, filename)

        # Calculate duration if start_time is provided
        duration = None
        if start_time:
            end_time = datetime.datetime.now()
            duration = end_time - start_time

        # Enhanced metadata
        results_data = {
            "metadata": {
                "crawl_date": datetime.datetime.now().isoformat(),
                "domains_found": len(self.domain_data),
                "search_engines_used": self.search_engines,
                "use_proxies": self.use_proxies,
                "use_selenium": self.use_selenium
            },
            "domains": list(self.domain_data.values())
        }

        # Add duration to metadata if available
        if duration:
            results_data["metadata"].update({
                "crawl_duration": str(duration),
                "crawl_duration_seconds": duration.total_seconds()
            })

        # Save to JSON file
        with open(json_filepath, 'w', encoding='utf-8') as file:
            json.dump(results_data, file, indent=2, ensure_ascii=False)

        logging.info(f"Results saved to {json_filepath}")
        
        # Also save a latest copy with fixed filename
        latest_filepath = os.path.join(self.output_dir, "rw_domains_latest.json")
        with open(latest_filepath, 'w', encoding='utf-8') as file:
            json.dump(results_data, file, indent=2, ensure_ascii=False)
            
        logging.info(f"Latest results also saved to {latest_filepath}")
            
if __name__ == "__main__":
    # Create a more advanced crawler with enhanced settings
    crawler = RwDomainCrawler(
        max_pages=5000,         # More pages to crawl
        max_depth=4,            # Deeper crawling
        use_proxies=True,       # Enable proxy rotation
        use_selenium=True,      # Enable Selenium for JavaScript-heavy sites
        concurrent_requests=3   # Parallel processing
    )
    
    # Start the crawling process
    domain_data = crawler.crawl()
    
    # Print sorted results
    print(f"\nFound {len(domain_data)} .rw domains:")
    for domain, data in sorted(domain_data.items()):
        title = data.get('title', 'Unknown')
        print(f"{domain}: - {title}")