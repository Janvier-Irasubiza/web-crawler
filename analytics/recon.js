const axios = require('axios');

// Create a reconnaissance script that identifies vulnerable entry points
async function reconScan(baseUrl) {
    console.log(`Scanning ${baseUrl} for potential injection points...`);

    // Common OWASP Juice Shop endpoints to check
    const potentialVulnerabilities = [
        { path: "/rest/products/search", param: "q", method: "GET" },
        { path: "/rest/user/login", method: "POST" },
        { path: "/api/Products", param: "id", method: "GET" },
        { path: "/rest/basket", method: "POST" },
        { path: "/rest/feedback/search", param: "q", method: "GET" }
    ];

    let results = [];

    // Test each potential vulnerability
    for (const vuln of potentialVulnerabilities) {
        try {
            const response = await axios({
                method: vuln.method,
                url: `${baseUrl}${vuln.path}`,
                validateStatus: false // Allow non-2xx responses
            });

            results.push({
                endpoint: vuln.path,
                method: vuln.method,
                status: response.status,
                headers: response.headers,
                parameter: vuln.param || null,
                serverInfo: response.headers['server'],
                securityHeaders: {
                    xssProtection: response.headers['x-xss-protection'],
                    contentSecurityPolicy: response.headers['content-security-policy'],
                    frameOptions: response.headers['x-frame-options']
                }
            });
        } catch (error) {
            console.error(`Error scanning ${vuln.path}: ${error.message}`);
        }
    }

    return results;
}

// Example usage
const testUrl = 'http://13.60.183.62/';
async function runScan() {
    const vulnerabilities = await reconScan(testUrl);
    console.table(vulnerabilities);
}

module.exports = { reconScan };