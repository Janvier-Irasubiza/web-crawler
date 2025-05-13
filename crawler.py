from urllib.parse import urlparse
from collections import deque
import json
import datetime
import logging
import os
import requests
from bs4 import BeautifulSoup
import time

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
    def __init__(self, search_engines=None, max_pages=1000000, max_depth=3, output_dir='data'):
        """
        Initialize the crawler with starting points and parameters
        """

        self.search_engines = search_engines or [
            'google', 
            'bing', 
            'duckduckgo', 
            'yandex', 
            'yahoo'
        ]

        self.domain_data = {}
        self.visited_urls = set()
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.output_dir = output_dir

        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Create logs directory if it doesn't exist
        os.makedirs('logs', exist_ok=True)

    def is_valid_url(self, url):
        """
        Check if the url is valid and should be processed
        """
        
        try:
            # parse the url
            parsed_url = urlparse(url)
            
            return bool(parsed_url.netloc) and bool(parsed_url.scheme) and parsed_url.scheme in ['http', 'https']
        except:
            return False
        
    def is_rw_domain(self, url):
        """
        Check if the url is a .rw domain 
        """
        try:
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.lower()
            return domain.endswith('.rw')
        except:
            return False
        
    def normalize_domain(self, domain):
        """
        Normalize domain by removing www. prefix
        """
        if domain.startswith('www.'):
            return domain[4:]
        return domain

    def extract_domain(self, url):
        """
        Extract domain from the url
        """
        try:
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.lower()
            return self.normalize_domain(domain)
        except:
            return None
        
    def crawl(self):
        """
        Main crawling function
        """
        logging.info("Starting web crawler for .rw domains")
        logging.info(f"Max pages: {self.max_pages}, Max depth: {self.max_depth}")
        
        # Initialize variables
        visited_urls = set()
        urls_to_visit = deque([(url, 0) for url in self.get_initial_urls()])  # (url, depth) pairs
        total_pages = 0
        start_time = datetime.datetime.now()

        # Start searching for .rw domains from search engines
        for engine in self.search_engines:
            logging.info(f"Starting search engine crawl for {engine}")
            self.search_engine_crawl(engine, visited_urls, urls_to_visit)
            logging.info(f"Completed search engine crawl for {engine}")

        # Process the remaining urls    
        while urls_to_visit and total_pages < self.max_pages:
            url, depth = urls_to_visit.popleft()
            
            if url in visited_urls:
                continue

            if not self.is_valid_url(url):
                logging.debug(f"Skipping invalid URL: {url}")
                continue
            
            if not self.is_rw_domain(url):
                logging.debug(f"Skipping non .rw domain: {url}")
                continue

            # Check if we've reached the maximum depth
            if depth >= self.max_depth:
                logging.debug(f"Reached max depth for URL: {url}")
                continue

            # Add the url to the visited set
            visited_urls.add(url)   
            
            try:
                logging.info(f"Processing URL: {url} (depth: {depth})")
                
                # Get the domain of the url
                domain = self.extract_domain(url)
                
                # Increment the total number of pages
                total_pages += 1
                
                if total_pages % 10 == 0:  # Log progress every 10 pages
                    elapsed_time = datetime.datetime.now() - start_time
                    logging.info(f"Progress: {total_pages} pages crawled in {elapsed_time}")

                # Get new URLs from the current page
                new_urls = self.extract_urls_from_page(url)
                logging.info(f"Found {len(new_urls)} new URLs on {url}")
                
                # Add new URLs with incremented depth
                urls_to_visit.extend([(new_url, depth + 1) for new_url in new_urls 
                                    if new_url not in visited_urls])

                # Append the domain to the results if it's a .rw domain
                if self.is_rw_domain(url):
                    normalized_domain = self.normalize_domain(domain)
                    if normalized_domain not in self.domain_data:
                        self.domain_data[normalized_domain] = {
                            'domain': normalized_domain,
                            'url': url
                        }
                        logging.info(f"Discovered new .rw domain: {normalized_domain}")
                        # Save updated results
                        self.save_results(start_time)
                    else:
                        logging.debug(f"Skipping duplicate domain: {normalized_domain}")
                
            except Exception as e:
                logging.error(f"Error processing URL {url}: {str(e)}")
                continue

        # Log final statistics
        end_time = datetime.datetime.now()
        duration = end_time - start_time
        logging.info("Crawling completed")
        logging.info(f"Total pages crawled: {total_pages}")
        logging.info(f"Total unique domains found: {len(self.domain_data)}")
        logging.info(f"Total time taken: {duration}")
        logging.info(f"Average speed: {total_pages/duration.total_seconds():.2f} pages/second")

        # Save final results
        self.save_results(start_time)

        return self.domain_data

    def get_initial_urls(self):
        """
        Get initial URLs to start crawling from
        """
        return [f"https://www.{engine}.com" for engine in self.search_engines]

    def extract_urls_from_page(self, url):
        """
        Extract URLs from a webpage
        """
        try:
            logging.debug(f"Extracting URLs from {url}")
            response = requests.get(url, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            links = soup.find_all('a')
            urls = [link.get('href') for link in links if link.get('href')]
            valid_urls = [url for url in urls if self.is_valid_url(url)]
            logging.debug(f"Found {len(valid_urls)} valid URLs on {url}")
            return valid_urls
        except Exception as e:
            logging.error(f"Error extracting URLs from {url}: {str(e)}")
            return []

    def search_engine_crawl(self, engine, visited_urls, urls_to_visit):
        """
        Crawl the search engine for .rw domains with rate limiting and pagination
        """
        import time
        
        # Define the search query for the search engine
        search_query = "site:.rw"
        
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
                'base_url': 'https://duckduckgo.com/',
                'param_name': 'q',
                'page_param': 's',
                'results_per_page': 30,
                'max_pages': 5
            },
            'yahoo': {
                'base_url': 'https://search.yahoo.com/web',
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
        
        for page in range(params['max_pages']):
            try:
                logging.info(f"Crawling {engine} page {page + 1}/{params['max_pages']}")
                
                # Construct the URL with pagination
                query_params = {
                    params['param_name']: search_query,
                    params['page_param']: page * params['results_per_page']
                }
                
                # Add headers to mimic a browser
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                
                # Send the request to the search engine
                response = requests.get(
                    params['base_url'],
                    params=query_params,
                    headers=headers,
                    timeout=10
                )
                
                # Parse the response
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find all the links on the page
                links = soup.find_all('a')
                
                # Extract the URLs from the links
                urls = [link.get('href') for link in links if link.get('href')]
                
                # Filter out invalid URLs and add to queue with depth 0
                valid_urls = [(url, 0) for url in urls 
                             if self.is_valid_url(url) and 
                             self.is_rw_domain(url) and 
                             url not in visited_urls]
                
                # Add the valid URLs to the list of URLs to visit
                urls_to_visit.extend(valid_urls)
                total_urls_found += len(valid_urls)
                
                logging.info(f"Found {len(valid_urls)} new .rw domains on page {page + 1}")
                
                # Rate limiting - wait between requests
                time.sleep(2)
                
            except Exception as e:
                logging.error(f"Error crawling {engine} page {page + 1}: {str(e)}")
                continue
        
        logging.info(f"Completed {engine} crawl. Total new .rw domains found: {total_urls_found}")

    def save_results(self, start_time=None):
        """
        Save the results to JSON format
        """
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
            
            
if __name__ == "__main__":
    crawler = RwDomainCrawler()
    domain_data = crawler.crawl()
    for domain, data in sorted(domain_data.items()):
        print(f"{domain}: - {data.get('title', 'unkown')}")
