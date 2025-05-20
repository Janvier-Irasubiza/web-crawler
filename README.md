# WebCrawler Analytics Platform

A web analytics and domain discovery platform for tracking website visitors and discovering .rw domains. Built as a cybersecurity project focusing on ethical web crawling.

## Features

- Real-time visitor tracking and analytics
- Geographic visitor distribution
- Page view statistics
- Automated .rw domain discovery
- Interactive data visualization

## Tech Stack

- Backend: FastAPI (Python)
- Frontend: HTML, TailwindCSS, JavaScript
- Database: SQLite
- Visualization: Chart.js

## Quick Start

1. Clone and setup:
```bash
git clone https://github.com/yourusername/web-crawler.git
cd web-crawler
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. Run the app:
```bash
python app.py
```

Access at `http://localhost:8000`

## Configuration

Configure via environment variables:
- `ANALYTICS_SERVER_URL`
- `CRAWLER_INTERVAL`
- `MAX_DOMAINS`
- `DATABASE_URL`

## Security & Ethics

- Rate limiting and user agent rotation
- Respects robots.txt
- Implements request delays
- Secure data storage
- No personal data collection
