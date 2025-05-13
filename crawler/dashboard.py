from flask import Flask, render_template, jsonify
from crawler import crawler_state, RWCrawler
import json
import os
from datetime import datetime
import threading
import time

app = Flask(__name__, template_folder='../templates')

def run_crawler():
    global crawler_state
    try:
        crawler_state["is_running"] = True
        crawler_state["start_time"] = datetime.now()
        crawler_state["pages_crawled"] = 0
        crawler_state["domains_discovered"] = 0
        crawler_state["elapsed_time"] = 0
        
        crawler = RWCrawler()
        crawler.run()
    finally:
        crawler_state["is_running"] = False
        crawler_state["start_time"] = None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def get_status():
    if crawler_state["start_time"]:
        crawler_state["elapsed_time"] = int((datetime.now() - crawler_state["start_time"]).total_seconds())
    
    return jsonify(crawler_state)

@app.route('/api/domains')
def get_domains():
    try:
        with open('rw_domains.json', 'r') as f:
            data = json.load(f)
        return jsonify(data)
    except FileNotFoundError:
        return jsonify({"domains": [], "total_rw_domains": 0})

@app.route('/api/start', methods=['POST'])
def start_crawler():
    if not crawler_state["is_running"]:
        thread = threading.Thread(target=run_crawler)
        thread.daemon = True
        thread.start()
        return jsonify({"status": "started"})
    return jsonify({"status": "already_running"})

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    if not os.path.exists('templates'):
        os.makedirs('templates')
    
    app.run(debug=True, port=5000) 