// Visitor Analytics Script

// Create a unique ID for this session
function generateSessionId() {
    return 'session_' + Math.random().toString(36).substr(2, 9);
}

// Get geolocation data (in a real scenario, you might use a more robust geolocation service)
async function getRegionInfo() {
    try {
        const response = await fetch('https://ipwho.is/');
        const data = await response.json();
        console.log('Geolocation data:', data);

        return {
            country: data.country_name,
            region: data.region,
            city: data.city,
            ip: data.ip
        };
    } catch (error) {
        console.error('Error fetching geolocation:', error);
        return { country: 'Unknown', region: 'Unknown', city: 'Unknown' };
    }
}

// Main analytics class
class VisitorAnalytics {
    constructor() {
        this.sessionId = generateSessionId();
        this.startTime = new Date();
        this.pageViews = 0;
        this.currentPage = window.location.pathname;
        this.regionInfo = null;
        this.active = true;
        this.activityTimeout = null;
        this.serverEndpoint = 'http://16.171.174.116/analytics';

        // Initialize
        this.init();
    }

    async init() {
        // Get region data
        this.regionInfo = await getRegionInfo();
        console.log('Region info:', this.regionInfo);
        

        // Register event listeners
        window.addEventListener('beforeunload', this.handleUnload.bind(this));
        document.addEventListener('visibilitychange', this.handleVisibilityChange.bind(this));
        this.registerActivityEvents();

        // Record initial page view
        this.recordPageView();

        // Send initial data
        this.sendData('session_start');

        // Setup periodic data sending (every 30 seconds)
        this.dataSendInterval = setInterval(() => {
            this.sendData('heartbeat');
        }, 30000);
    }

    registerActivityEvents() {
        // Track user activity
        ['click', 'mousemove', 'keypress', 'scroll', 'touchstart'].forEach(eventType => {
            document.addEventListener(eventType, this.handleUserActivity.bind(this));
        });
    }

    handleUserActivity() {
        this.active = true;

        // Reset inactivity timer
        clearTimeout(this.activityTimeout);
        this.activityTimeout = setTimeout(() => {
            this.active = false;
        }, 60000); // Consider inactive after 1 minute of no activity
    }

    handleVisibilityChange() {
        if (document.hidden) {
            this.recordTabInactive();
        } else {
            this.recordTabActive();
        }
    }

    recordTabInactive() {
        this.active = false;
        this.sendData('tab_inactive');
    }

    recordTabActive() {
        this.active = true;
        this.sendData('tab_active');
    }

    recordPageView() {
        this.pageViews++;
        this.currentPage = window.location.pathname;
    }

    getTimeSpent() {
        return Math.floor((new Date() - this.startTime) / 1000); // Time in seconds
    }

    handleUnload() {
        // Send final analytics data when user is leaving
        this.sendData('session_end', true);
    }

    async sendData(eventType, isSync = false) {
        const analyticsData = {
            sessionId: this.sessionId,
            eventType: eventType,
            pageViews: this.pageViews,
            currentPage: this.currentPage,
            timeSpent: this.getTimeSpent(),
            active: this.active,
            region: this.regionInfo,
            timestamp: new Date().toISOString()
        };

        try {
            if (isSync) {
                // Synchronous request for beforeunload event
                navigator.sendBeacon(this.serverEndpoint, JSON.stringify(analyticsData));
            } else {
                // Asynchronous request
                await fetch(this.serverEndpoint, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(analyticsData)
                });
            }
        } catch (error) {
            console.error('Error sending analytics data:', error);
        }
    }

    cleanup() {
        // Clean up event listeners and intervals
        window.removeEventListener('beforeunload', this.handleUnload);
        document.removeEventListener('visibilitychange', this.handleVisibilityChange);
        clearInterval(this.dataSendInterval);
        clearTimeout(this.activityTimeout);

        ['click', 'mousemove', 'keypress', 'scroll', 'touchstart'].forEach(eventType => {
            document.removeEventListener(eventType, this.handleUserActivity);
        });
    }
}

// Initialize the analytics when the script is loaded
const visitorAnalytics = new VisitorAnalytics();

// For debugging
console.log('Visitor analytics initialized with session ID:', visitorAnalytics.sessionId);