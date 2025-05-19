from urllib.parse import urlparse, urljoin
from collections import deque
import json
import datetime
import logging
import os
import time
import random
import re
import requests
from bs4 import BeautifulSoup
import dns.resolver
import concurrent.futures

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/crawler.log', mode='a', encoding='utf-8', delay=True),
        logging.StreamHandler()
    ]
)

class RwDomainCrawler:
    def __init__(self, max_pages=1000000, max_depth=3, output_dir='data', 
                 concurrent_requests=5, respect_robots=True):
        """
        Initialize the crawler with starting points and parameters
        """
        # Search engines are used with caution now
        self.search_engines = [
            'google', 
            'bing', 
            'duckduckgo', 
            'yandex', 
            'yahoo'
        ]

        # Seed domains to start the crawl
        self.seed_domains = [
            'gov.rw',
            'minict.gov.rw',
            'risa.rw',
            'ktpress.rw',
            'newtimes.co.rw',
            'rba.co.rw',
            'moh.gov.rw',
            'rra.gov.rw',
            'ur.ac.rw', 
            'rdb.rw',   
            'bnr.rw',
            'mineduc.gov.rw',
            'irembo.gov.rw'
        ]

        self.is_scanning = False
        self.domain_data = {}
        self.visited_urls = set()
        self.visited_domains = set()
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.output_dir = output_dir
        self.concurrent_requests = concurrent_requests
        self.respect_robots = respect_robots
        self.robots_cache = {}  # Cache for robots.txt content

        # Proxy rotation configuration (add your proxies here)
        self.proxies = [
            # None for direct connection
            None,
            # Add your proxies in the format:
            # {"http": "http://user:pass@proxy.example.com:8080", "https": "https://user:pass@proxy.example.com:8080"}
        ]
        
        # User-Agent rotation
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:95.0) Gecko/20100101 Firefox/95.0',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.93 Safari/537.36',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 15_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/96.0.4664.53 Mobile/15E148 Safari/604.1'
        ]

        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Create logs directory if it doesn't exist
        os.makedirs('logs', exist_ok=True)

    def get_random_user_agent(self):
        """Get a random user agent from the list"""
        return random.choice(self.user_agents)
    
    def get_random_proxy(self):
        """Get a random proxy from the list"""
        return random.choice(self.proxies)

    def is_valid_url(self, url):
        """Check if the url is valid and should be processed"""
        try:
            # parse the url
            parsed_url = urlparse(url)
            
            return bool(parsed_url.netloc) and bool(parsed_url.scheme) and parsed_url.scheme in ['http', 'https']
        except:
            return False
        
    def is_rw_domain(self, url):
        """Check if the url is a .rw domain"""
        try:
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.lower()
            return domain.endswith('.rw')
        except:
            return False
        
    def normalize_domain(self, domain):
        """Normalize domain by removing www. prefix"""
        if domain.startswith('www.'):
            return domain[4:]
        return domain

    def extract_domain(self, url):
        """Extract domain from the url"""
        try:
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.lower()
            return self.normalize_domain(domain)
        except:
            return None

    def check_robots_txt(self, domain):
        """Check robots.txt to see if crawling is allowed"""
        if not self.respect_robots:
            return True
            
        if domain in self.robots_cache:
            return self.robots_cache[domain]
            
        try:
            robots_url = f"https://{domain}/robots.txt"
            response = requests.get(robots_url, timeout=5)
            
            if response.status_code == 200:
                # Very basic robots.txt parsing - looking for "User-agent: *" and "Disallow: /"
                if "User-agent: *" in response.text and "Disallow: /" in response.text:
                    self.robots_cache[domain] = False
                    return False
            
            # Default to allowing crawling
            self.robots_cache[domain] = True
            return True
        except:
            # If there's an error accessing robots.txt, default to allowing crawling
            self.robots_cache[domain] = True
            return True

    def get_page_content(self, url, retries=3):
        """Get the content of a webpage with retries and proxy/user-agent rotation"""
        for attempt in range(retries):
            try:
                headers = {'User-Agent': self.get_random_user_agent()}
                proxy = self.get_random_proxy()
                
                # Add randomized delays between requests
                if attempt > 0:
                    sleep_time = random.uniform(2, 5) * (attempt + 1)
                    time.sleep(sleep_time)
                
                response = requests.get(
                    url, 
                    headers=headers,
                    proxies=proxy,
                    timeout=15,
                    allow_redirects=True
                )
                
                if response.status_code == 200:
                    return response.text
                
                # If we get a 429 (Too Many Requests), wait longer before retrying
                if response.status_code == 429:
                    sleep_time = random.uniform(30, 60)
                    logging.warning(f"Rate limited on {url}. Waiting {sleep_time:.2f}s before retry.")
                    time.sleep(sleep_time)
                    continue
                    
                return None
            except Exception as e:
                logging.debug(f"Attempt {attempt+1} failed for {url}: {str(e)}")
                continue
        
        return None

    def extract_urls_from_page(self, url):
        """Extract URLs from a webpage"""
        try:
            domain = self.extract_domain(url)
            
            # Check robots.txt
            if not self.check_robots_txt(domain):
                logging.debug(f"Skipping {url} as per robots.txt")
                return []
                
            logging.debug(f"Extracting URLs from {url}")
            content = self.get_page_content(url)
            
            if not content:
                return []
                
            soup = BeautifulSoup(content, 'html.parser')
            
            # Extract page title if available
            title = soup.title.string if soup.title else "Unknown"
            
            # Store domain info if it's a .rw domain
            if self.is_rw_domain(url):
                normalized_domain = self.normalize_domain(domain)
                if normalized_domain not in self.domain_data:
                    domain_data = {
                        'domain': normalized_domain,
                        'url': url,
                        'title': title,
                        'discovered_at': datetime.datetime.now().isoformat()
                    }
                    self.domain_data[normalized_domain] = domain_data
                    logging.info(f"Discovered new .rw domain: {normalized_domain} - {title}")
                    # Save domain immediately
                    self.save_single_domain(domain_data)
            
            # Find all links
            links = soup.find_all('a')
            raw_urls = []
            
            for link in links:
                href = link.get('href')
                if not href:
                    continue
                    
                # Handle relative URLs
                if not href.startswith(('http://', 'https://')):
                    href = urljoin(url, href)
                    
                raw_urls.append(href)
            
            # Filter for valid URLs
            valid_urls = [url for url in raw_urls if self.is_valid_url(url)]
            
            logging.debug(f"Found {len(valid_urls)} valid URLs on {url}")
            return valid_urls
            
        except Exception as e:
            logging.error(f"Error extracting URLs from {url}: {str(e)}")
            return []

    def dns_zone_transfer(self):
        """
        Attempt zone transfer for .rw domains (rarely works but worth trying)
        """
        logging.info("Attempting DNS zone transfer for .rw domain")
        try:
            # Try to get the nameservers for .rw
            nameservers = dns.resolver.resolve('rw.', 'NS')
            
            for ns in nameservers:
                ns_name = str(ns.target).rstrip('.')
                logging.info(f"Attempting zone transfer from {ns_name}")
                
                try:
                    # Attempt AXFR transfer
                    xfr = dns.query.xfr(ns_name, 'rw.')
                    for msg in xfr:
                        for rrset in msg.answer:
                            for item in rrset.items:
                                if item.rdtype == dns.rdatatype.A:
                                    domain = str(rrset.name).rstrip('.')
                                    if domain.endswith('.rw'):
                                        normalized_domain = self.normalize_domain(domain)
                                        domain_data = {
                                            'domain': normalized_domain,
                                            'url': f"http://{domain}",
                                            'title': "Found via DNS zone transfer",
                                            'discovered_at': datetime.datetime.now().isoformat()
                                        }
                                        self.domain_data[normalized_domain] = domain_data
                                        # Save domain immediately
                                        self.save_single_domain(domain_data)
                except Exception as e:
                    logging.debug(f"Zone transfer failed from {ns_name}: {str(e)}")
        except Exception as e:
            logging.error(f"DNS zone transfer attempt failed: {str(e)}")

    def try_certificate_transparency_logs(self):
        """
        Query Certificate Transparency logs for .rw domains
        """
        logging.info("Querying Certificate Transparency logs for .rw domains")
        try:
            # crt.sh provides CT log data
            url = "https://crt.sh/"
            params = {
                'q': '%.rw',  # Wildcard search for .rw domains
                'output': 'json'
            }
            
            response = requests.get(url, params=params, timeout=30)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    domains_found = set()
                    
                    for cert in data:
                        name_value = cert.get('name_value', '')
                        # Extract potential domains
                        domains = re.findall(r'([a-zA-Z0-9.-]+\.rw)', name_value)
                        domains_found.update(domains)
                    
                    for domain in domains_found:
                        normalized_domain = self.normalize_domain(domain)
                        if normalized_domain not in self.domain_data:
                            domain_data = {
                                'domain': normalized_domain,
                                'url': f"https://{domain}",
                                'title': "Found via Certificate Transparency logs",
                                'discovered_at': datetime.datetime.now().isoformat()
                            }
                            self.domain_data[normalized_domain] = domain_data
                            # Save domain immediately
                            self.save_single_domain(domain_data)
                            
                    logging.info(f"Found {len(domains_found)} potential domains from CT logs")
                    
                except Exception as e:
                    logging.error(f"Error parsing CT log data: {str(e)}")
            else:
                logging.error(f"Failed to query CT logs: HTTP {response.status_code}")
                
        except Exception as e:
            logging.error(f"Certificate Transparency query failed: {str(e)}")

    def process_common_subdomain_patterns(self):
        """
        Try common subdomain patterns for discovered domains
        """
        logging.info("Trying common subdomain patterns")
        
        common_subdomains = [
            'www', 'mail', 'webmail', 'api', 'dev', 'stage', 'test', 'demo',
            'admin', 'shop', 'blog', 'portal', 'app', 'mobile', 'm', 
            'support', 'help', 'forum', 'community', 'news', 'media',
            'cloud', 'cdn', 'static', 'assets', 'images', 'files',
            'login', 'auth', 'sso', 'accounts', 'alumni', 'library',
            'research', 'jobs', 'careers', 'hr', 'moodle', 'learn',
            'lms', 'sis', 'erp', 'crm', 'mail', 'smtp', 'imap', 'pop',
            'services', 'vpn', 'remote', 'intranet', 'extranet'
        ]
        
        # Get the base domains we've already discovered
        base_domains = list(self.domain_data.keys())
        new_domains_to_test = []
        
        # Generate subdomain combinations
        for base_domain in base_domains:
            for subdomain in common_subdomains:
                new_domain = f"{subdomain}.{base_domain}"
                new_domains_to_test.append(new_domain)
        
        # Also use seed domains we know
        for seed_domain in self.seed_domains:
            for subdomain in common_subdomains:
                new_domain = f"{subdomain}.{seed_domain}"
                new_domains_to_test.append(new_domain)
        
        logging.info(f"Generated {len(new_domains_to_test)} potential subdomains to test")
        
        # Test domains with concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.concurrent_requests) as executor:
            futures = {executor.submit(self.test_domain_exists, domain): domain for domain in new_domains_to_test}
            
            for future in concurrent.futures.as_completed(futures):
                domain = futures[future]
                try:
                    result = future.result()
                    if result:
                        normalized_domain = self.normalize_domain(domain)
                        if normalized_domain not in self.domain_data:
                            domain_data = {
                                'domain': normalized_domain,
                                'url': f"https://{domain}",
                                'title': "Found via subdomain enumeration",
                                'discovered_at': datetime.datetime.now().isoformat()
                            }
                            self.domain_data[normalized_domain] = domain_data
                            # Save domain immediately
                            self.save_single_domain(domain_data)
                except Exception as e:
                    logging.error(f"Error testing domain {domain}: {str(e)}")

    def test_domain_exists(self, domain):
        """Test if a domain exists by trying to connect to it"""
        try:
            # Try HTTPS first
            response = requests.head(
                f"https://{domain}", 
                timeout=5,
                headers={'User-Agent': self.get_random_user_agent()},
                allow_redirects=True
            )
            if response.status_code < 400:
                return True
            
            # Try HTTP if HTTPS fails
            response = requests.head(
                f"http://{domain}", 
                timeout=5,
                headers={'User-Agent': self.get_random_user_agent()},
                allow_redirects=True
            )
            if response.status_code < 400:
                return True
                
            return False
        except:
            return False

    def search_engine_crawl(self, engine, visited_urls, urls_to_visit):
        """
        Crawl the search engine for .rw domains with enhanced techniques
        """
        # Define the search query for the search engine
        search_queries = [
            "site:.rw",
            "site:.co.rw",
            "site:.ac.rw",
            "site:.gov.rw",
            "site:.net.rw", 
            "site:.org.rw"
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
                'base_url': 'https://html.duckduckgo.com/html',
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
            }
        }
        
        if engine not in engine_params:
            logging.warning(f"Unsupported search engine: {engine}")
            return
        
        params = engine_params[engine]
        total_urls_found = 0
        
        # Try each search query
        for search_query in search_queries:
            # Use fewer pages and add more randomization to avoid blocks
            actual_max_pages = min(3, params['max_pages'])
            
            for page in range(actual_max_pages):
                try:
                    logging.info(f"Crawling {engine} page {page + 1}/{actual_max_pages} for {search_query}")
                    
                    # Random delay between requests (3-7 seconds)
                    time.sleep(random.uniform(3, 7))
                    
                    # Construct the URL with pagination
                    query_params = {
                        params['param_name']: search_query,
                        params['page_param']: page * params['results_per_page']
                    }
                    
                    # Add headers to better mimic a browser
                    headers = {
                        'User-Agent': self.get_random_user_agent(),
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.5',
                        'Referer': 'https://www.google.com/',
                        'DNT': '1',
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1',
                        'Cache-Control': 'max-age=0'
                    }
                    
                    # Use proxy rotation
                    proxy = self.get_random_proxy()
                    
                    # Send the request to the search engine
                    response = requests.get(
                        params['base_url'],
                        params=query_params,
                        headers=headers,
                        proxies=proxy,
                        timeout=20
                    )
                    
                    # Parse the response
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Find all the links on the page
                    links = soup.find_all('a')
                    
                    # Extract the URLs from the links
                    urls = [link.get('href') for link in links if link.get('href')]
                    
                    # For some search engines, we need special handling
                    if engine == 'google':
                        # Google uses redirects for search results
                        urls = [url for url in urls if '/url?q=' in url]
                        urls = [url.split('/url?q=')[1].split('&')[0] for url in urls]
                    
                    # Filter out invalid URLs and add to queue with depth 0
                    valid_urls = [(url, 0) for url in urls 
                                if self.is_valid_url(url) and 
                                self.is_rw_domain(url) and 
                                url not in visited_urls]
                    
                    # Add the valid URLs to the list of URLs to visit
                    urls_to_visit.extend(valid_urls)
                    total_urls_found += len(valid_urls)
                    
                    logging.info(f"Found {len(valid_urls)} new .rw domains on page {page + 1}")
                    
                    # If we got zero results, break from the loop (likely blocked or no more results)
                    if len(valid_urls) == 0 and page > 0:
                        logging.info(f"No more results or possibly blocked by {engine}. Moving on.")
                        break
                    
                except Exception as e:
                    logging.error(f"Error crawling {engine} page {page + 1}: {str(e)}")
                    # If we hit an exception, we might be blocked, so move on
                    break
            
            # Add extra delay between different search queries
            time.sleep(random.uniform(5, 10))
        
        logging.info(f"Completed {engine} crawl. Total new .rw domains found: {total_urls_found}")

    def try_whois_query(self):
        """
        Try to query WHOIS for .rw domains (might be rate-limited)
        """
        logging.info("Attempting WHOIS queries for .rw domains")
        try:
            # This is simplistic and would need to be expanded with actual WHOIS API integration
            # or by parsing WHOIS output from command line tools
            pass
        except Exception as e:
            logging.error(f"WHOIS query failed: {str(e)}")

    def process_url_queue(self, urls_to_visit, visited_urls):
        """Process the URL queue with concurrent requests"""
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.concurrent_requests) as executor:
            futures = {}
            
            while urls_to_visit and len(visited_urls) < self.max_pages:
                # Get a batch of URLs to process
                batch_size = min(self.concurrent_requests, len(urls_to_visit))
                batch = []
                
                for _ in range(batch_size):
                    if not urls_to_visit:
                        break
                    url, depth = urls_to_visit.popleft()
                    
                    if url in visited_urls:
                        continue
                        
                    if not self.is_valid_url(url):
                        continue
                        
                    if not self.is_rw_domain(url):
                        continue
                        
                    if depth >= self.max_depth:
                        continue
                        
                    batch.append((url, depth))
                    visited_urls.add(url)
                
                # Submit the batch for processing
                for url, depth in batch:
                    future = executor.submit(self.process_url, url, depth)
                    futures[future] = (url, depth)
                
                # Process completed futures
                for future in concurrent.futures.as_completed(dict(futures)):
                    url, depth = futures[future]
                    del futures[future]
                    
                    try:
                        new_urls = future.result()
                        if new_urls:
                            urls_to_visit.extend([(new_url, depth + 1) for new_url in new_urls 
                                              if new_url not in visited_urls])
                    except Exception as e:
                        logging.error(f"Error processing {url}: {str(e)}")
                
                # Add a small delay between batches
                time.sleep(0.5)

    def process_url(self, url, depth):
        """Process a single URL and return new URLs found"""
        try:
            logging.info(f"Processing URL: {url} (depth: {depth})")
            domain = self.extract_domain(url)
            
            # Extract URLs from the page
            new_urls = self.extract_urls_from_page(url)
            logging.info(f"Found {len(new_urls)} new URLs on {url}")
            
            return new_urls
        except Exception as e:
            logging.error(f"Error processing URL {url}: {str(e)}")
            return []

    def save_results(self, start_time=None):
        """Save the results to JSON format"""
        # Save to JSON
        filename = "rw_domains.json"
        json_filepath = os.path.join(self.output_dir, filename)

        # Calculate duration if start_time is provided
        duration = None
        if start_time:
            end_time = datetime.datetime.now()
            duration = end_time - start_time

        results_data = {
            "metadata": {
                "crawl_date": datetime.datetime.now().isoformat(),
                "domains_found": len(self.domain_data)
            },
            "domains": list(self.domain_data.values())
        }

        # Add duration to metadata if available
        if duration:
            results_data["metadata"].update({
                "crawl_duration": str(duration)
            })

        # Add used search engines to metadata
        if hasattr(self, 'search_engines'):
            results_data["metadata"]["search_engines"] = list(self.search_engines)

        with open(json_filepath, 'w', encoding='utf-8') as file:
            json.dump(results_data, file, indent=2, ensure_ascii=False)

        logging.info(f"Results saved to {json_filepath}")


    def crawl(self):
        """Main crawling function with improved approach"""
        logging.info("Starting enhanced web crawler for .rw domains")
        logging.info(f"Max pages: {self.max_pages}, Max depth: {self.max_depth}")
        
        # Initialize variables
        visited_urls = set()
        urls_to_visit = deque()
        total_pages = 0
        start_time = datetime.datetime.now()

        # Step 1: Try Certificate Transparency logs first (great source)
        self.try_certificate_transparency_logs()
        self.save_results(start_time)  # Save early results
        
        # Step 2: Use our seed domains
        for domain in self.seed_domains:
            urls_to_visit.append((f"https://{domain}", 0))
            
        # Step 3: Process known domains and extract subpages/links
        self.process_url_queue(urls_to_visit, visited_urls)
        self.save_results(start_time)  # Save interim results
            
        # Step 4: Try common subdomain patterns for discovered domains
        self.process_common_subdomain_patterns()
        self.save_results(start_time)  # Save interim results
        
        # Step 5: Try DNS zone transfer (rarely works, but worth a try)
        self.dns_zone_transfer()
        
        # Step 6: As a last resort, try search engines (might get blocked)
        # But we'll have already discovered many domains from other methods
        for engine in self.search_engines:
            logging.info(f"Starting search engine crawl for {engine}")
            self.search_engine_crawl(engine, visited_urls, urls_to_visit)
            logging.info(f"Completed search engine crawl for {engine}")
            # Process any new URLs found from search engines
            self.process_url_queue(urls_to_visit, visited_urls)
            # Save after each search engine
            self.save_results(start_time)

        # Log final statistics
        end_time = datetime.datetime.now()
        duration = end_time - start_time
        logging.info("Crawling completed")
        logging.info(f"Total unique domains found: {len(self.domain_data)}")
        logging.info(f"Total time taken: {duration}")

        # Save final results
        self.save_results(start_time)

        return self.domain_data

    def save_single_domain(self, domain_data):
        """Save a single domain to the output files immediately"""
        try:
            # Save to JSON
            json_filepath = os.path.join(self.output_dir, "rw_domains.json")
            
            # Read existing data if file exists
            if os.path.exists(json_filepath):
                with open(json_filepath, 'r', encoding='utf-8') as file:
                    try:
                        existing_data = json.load(file)
                    except json.JSONDecodeError:
                        existing_data = {
                            "metadata": {
                                "crawl_date": datetime.datetime.now().isoformat(),
                                "domains_found": 0
                            },
                            "domains": []
                        }
            else:
                existing_data = {
                    "metadata": {
                        "crawl_date": datetime.datetime.now().isoformat(),
                        "domains_found": 0
                    },
                    "domains": []
                }
            
            # Add new domain if not already present
            domain = domain_data['domain']
            if not any(d['domain'] == domain for d in existing_data['domains']):
                existing_data['domains'].append(domain_data)
                existing_data['metadata']['domains_found'] = len(existing_data['domains'])
                existing_data['metadata']['last_updated'] = datetime.datetime.now().isoformat()
                
                # Write updated data
                with open(json_filepath, 'w', encoding='utf-8') as file:
                    json.dump(existing_data, file, indent=2, ensure_ascii=False)
            
        except Exception as e:
            logging.error(f"Error saving domain {domain_data.get('domain', 'unknown')}: {str(e)}")

if __name__ == "__main__":
    crawler = RwDomainCrawler(
        max_pages=5000,
        max_depth=3,   
        concurrent_requests=5,
        respect_robots=True,
    )
    domain_data = crawler.crawl()
    
    # Print summary of results
    print(f"\nCrawl Summary:")
    print(f"Total .rw domains found: {len(domain_data)}")
    print(f"\nTop 20 domains discovered:")
    
    for i, (domain, data) in enumerate(sorted(domain_data.items())[:20]):
        print(f"{i+1}. {domain}: {data.get('title', 'Unknown')[:50]}")