# RW Domain Crawler

A sophisticated web crawler designed to discover and catalog .rw (Rwanda) domain websites. This tool systematically searches through multiple search engines and follows links to build a comprehensive database of Rwandan web domains.

## Features

- Multi-search engine support (Google, Bing, DuckDuckGo, Yandex, Yahoo, Baidu, Ecosia)
- Proxy rotation for avoiding rate limits
- Selenium support for JavaScript-heavy sites
- Concurrent request handling
- Depth-limited crawling
- User agent rotation
- Detailed logging
- JSON output with metadata

## Requirements

- Python 3.7+
- Chrome/Chromium browser (for Selenium)
- ChromeDriver
- Required Python packages (see requirements.txt)

## Installation

1. Clone this repository
2. Install the required packages: `pip install -r requirements.txt`
