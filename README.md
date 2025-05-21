# Web Crawler

A web analytics and domain discovery tool which provides detailed insights into website visitors and discovers .rw domains across the internet.

## ⚠️ Security Disclaimer

**IMPORTANT**: This project and its target application (vuln-blog) are designed for educational and testing purposes only. They contain intentionally vulnerable code and should **NEVER** be run in a production environment or on systems containing sensitive data.

### Security Requirements:
- Run these applications only in isolated virtual machines or containers
- Use dedicated test environments with no access to production systems
- Do not expose these applications to public networks
- Do not use real credentials or sensitive data
- Ensure proper network isolation between the applications and other systems

## Key Features

- **Website Analytics**: Real-time visitor tracking, geographic distribution analysis, time-based metrics, and interactive data visualization
- **Domain Discovery**: Automated .rw domain discovery
- **Security-First**: Implements ethical crawling practices including robots.txt compliance and proper request delays

## Tech Stack

- BeautifulSoup4 (Web Scraping)
- Requests (HTTP Client)
- urllib (URL Parsing/Handling)

## Setup Guide

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Git

### Installation Steps

1. **Clone both repositories**
   ```bash
   # Clone the analytics tool
   git clone https://github.com/Janvier-Irasubiza/web-crawler.git
   cd web-crawler

   # Clone the target project (vuln-blog)
   git clone https://github.com/Janvier-Irasubiza/vuln-blog.git
   cd ../vuln-blog
   ```

2. **Set up the target project (vuln-blog)**
   ```bash
   # Create and activate virtual environment
   python -m venv venv
   .\venv\Scripts\activate  # Windows
   # OR
   source venv/bin/activate  # Linux/MacOS

   # Install dependencies
   pip install -r requirements.txt

   # Start the target project
   python blog.py
   ```

3. **Set up the analytics tool**
   ```bash
   # Go back to web-crawler directory
   cd ../web-crawler

   # Create and activate virtual environment
   python -m venv venv
   .\venv\Scripts\activate  # Windows
   # OR
   source venv/bin/activate  # Linux/MacOS

   # Install dependencies
   pip install -r requirements.txt
   ```

### Running the Application

1. **Start the target project (vuln-blog)**
   ```bash
   # In the vuln-blog directory
   python blog.py
   ```
   The target project will be available at: http://localhost:9000

2. **Start the analytics tool**
   ```bash
   # In the web-crawler directory
   python app.py
   ```

3. **Access the applications**
   - Target Project: http://localhost:9000
   - Analytics Dashboard: http://localhost:8000
   - API Documentation: http://localhost:8000/api/docs
   - ReDoc Documentation: http://localhost:8000/api/redoc

Note: Make sure both applications are running simultaneously for the analytics tool to collect data from the target project.
