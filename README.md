# WebCrawler Analytics Platform


A professional web analytics and domain discovery platform that provides detailed insights into website visitors and discovers .rw domains across the internet. This project was developed as a cybersecurity assignment, focusing on ethical web crawling and analytics.

## 🚀 Features

### Website Analytics
- Real-time visitor tracking
- Geographic distribution of visitors
- Time spent analysis
- Bounce rate monitoring
- Page view statistics
- Interactive data visualization
- Time-based filtering (Today, Last Week, Last Month, All Time)

### Domain Discovery
- Automated .rw domain discovery
- Search engine integration
- Domain metadata collection
- Real-time domain scanning
- Searchable domain database

## 🛠️ Technology Stack

- **Backend**: FastAPI (Python)
- **Frontend**: HTML, TailwindCSS, JavaScript
- **Data Visualization**: Chart.js
- **Database**: SQLite
- **Web Crawling**: Custom crawler with Selenium
- **Analytics**: Custom analytics engine

## 📋 Prerequisites

- Python 3.8+
- Node.js (for development)
- Modern web browser
- Internet connection

## 🚀 Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/web-crawler.git
cd web-crawler
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Start the application:
```bash
python app.py
```

The application will be available at `http://localhost:8000`

## 🔧 Configuration

The application can be configured through environment variables:

- `ANALYTICS_SERVER_URL`: URL of the analytics server
- `CRAWLER_INTERVAL`: Interval between crawler runs (in seconds)
- `MAX_DOMAINS`: Maximum number of domains to crawl
- `DATABASE_URL`: SQLite database URL

## 📊 Usage

### Website Analytics
1. Navigate to the Analytics tab
2. View real-time visitor statistics
3. Use time filters to analyze different periods
4. Export data for further analysis

### Domain Discovery
1. Navigate to the Domain Discovery tab
2. Click "Start Crawler" to begin domain discovery
3. Use the search function to find specific domains
4. View detailed domain information

## 🔒 Security Considerations

This project was developed with security best practices in mind:

- Rate limiting to prevent server overload
- User agent rotation for ethical crawling
- IP-based request tracking
- Secure data storage
- CORS protection
- Input validation

## 📝 Ethical Considerations

The project adheres to ethical web crawling practices:

- Respects robots.txt
- Implements proper delays between requests
- Only crawls publicly accessible content
- Uses OWASP Juice Shop for testing analytics
- Does not collect personal information
- Implements proper error handling

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- OWASP Juice Shop for providing a safe testing environment
- FastAPI for the excellent web framework
- Chart.js for the visualization capabilities
- TailwindCSS for the beautiful UI components
