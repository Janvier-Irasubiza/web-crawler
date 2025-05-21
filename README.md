# Web Crawler and Analytics Platform

A professional web analytics and domain discovery platform built with FastAPI. This project provides detailed insights into website visitors and discovers .rw domains across the internet, developed as a cybersecurity assignment focusing on ethical web crawling practices.

## Key Features

- **Website Analytics**: Real-time visitor tracking, geographic distribution analysis, time-based metrics, and interactive data visualization
- **Domain Discovery**: Automated .rw domain discovery with search engine integration and metadata collection
- **Security-First**: Implements ethical crawling practices including robots.txt compliance and proper request delays

## Tech Stack

- FastAPI (Backend)
- SQLite (Database)
- HTML/CSS/JavaScript (Frontend)
- Python (Core Logic)

## Setup Guide

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Git

### Installation Steps

1. **Clone the repository**
   ```bash
   git clone <repository-url>
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

4. **Initialize the database**
   ```bash
   python scripts/init_db.py
   ```

### Running the Application

1. **Start the main application**
   ```bash
   uvicorn app:app --reload --host 0.0.0.0 --port 8000
   ```

2. **Access the application**
   - Web Interface: http://localhost:8000
   - API Documentation: http://localhost:8000/api/docs
   - ReDoc Documentation: http://localhost:8000/api/redoc

### Development

- The application uses FastAPI's hot-reload feature, so changes to the code will automatically restart the server
- Logs are stored in the `logs/` directory
- Crawled data is stored in the `data/` directory
- Database files are stored in the `dump/` directory

### Environment Variables

Create a `.env` file in the root directory with the following variables (if needed):
```
DATABASE_URL=sqlite:///dump/analytics.db
LOG_LEVEL=INFO
```

## Contributing

1. Fork the repository
2. Create a new branch for your feature
3. Make your changes
4. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
