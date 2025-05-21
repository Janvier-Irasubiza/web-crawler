# Web Crawler and Analytics Platform

A web analytics and domain discovery platform built with FastAPI. This tool provides detailed insights into website visitors and discovers .rw domains across the internet.

## Key Features

- **Website Analytics**: Real-time visitor tracking, geographic distribution analysis, time-based metrics, and interactive data visualization
- **Domain Discovery**: Automated .rw domain discovery
- **Security-First**: Implements ethical crawling practices including robots.txt compliance and proper request delays

## Tech Stack

- FastAPI (Backend)
- SQLite (Database)
- HTML/CSS/JavaScript (Frontend)

## Setup Guide

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Git

### Installation Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/Janvier-Irasubiza/web-crawler.git
   cd web-crawler
   ```

2. **Create and activate a virtual environment**
   ```bash
   # Windows
   python -m venv venv
   .\venv\Scripts\activate

   # Linux/MacOS
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

### Running the Application

1. **Start the main application**
   ```bash
   python app.py
   ```

2. **Access the application**
   - Dashboard: http://localhost:8000
   - API Documentation: http://localhost:8000/api/docs
   - ReDoc Documentation: http://localhost:8000/api/redoc
