// Comprehensive Web Vulnerability Scanner
// For identifying XSS and script injection points in the Juice Shop application

const puppeteer = require('puppeteer');
const axios = require('axios');
const fs = require('fs');
const url = require('url');

class WebVulnerabilityScanner {
  constructor(targetUrl) {
    this.targetUrl = targetUrl;
    this.visitedUrls = new Set();
    this.forms = [];
    this.inputFields = [];
    this.vulnerabilities = [];
    this.cookies = [];
    this.localStorage = {};
  }

  // Main scanning function
  async scan() {
    console.log(`Starting comprehensive scan of ${this.targetUrl}`);
    const browser = await puppeteer.launch({
      headless: true,
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-web-security',
        '--disable-features=IsolateOrigins,site-per-process',
        '--disable-site-isolation-trials',
        '--disable-features=BlockInsecurePrivateNetworkRequests',
        '--disable-features=IsolateOrigins',
        '--disable-features=site-per-process'
      ],
      ignoreHTTPSErrors: true
    });

    try {
      const page = await browser.newPage();

      // Setup request interception to analyze responses
      await this.setupRequestInterception(page);

      // Set up console monitoring
      page.on('console', msg => console.log(`PAGE LOG: ${msg.text()}`));

      // Start crawling from the main page
      await this.crawlPage(browser, page, this.targetUrl);

      // Test discovered forms and input fields for vulnerabilities
      await this.testDiscoveredElements(browser);

      // Generate report
      this.generateReport();

    } catch (error) {
      console.error('Error during scanning:', error);
    } finally {
      await browser.close();
    }

    return this.vulnerabilities;
  }

  // Set up request interception to analyze responses
  async setupRequestInterception(page) {
    await page.setRequestInterception(true);

    page.on('request', async request => {
      try {
        // Add request type filtering
        const resourceType = request.resourceType();
        if (resourceType === 'image' || resourceType === 'stylesheet' || resourceType === 'font') {
          await request.abort();
          return;
        }

        let attempts = 0;
        const maxAttempts = 3;

        while (attempts < maxAttempts) {
          try {
            await request.continue();
            break;
          } catch (error) {
            attempts++;
            if (attempts === maxAttempts) {
              console.error(`Failed to load ${request.url()} after ${maxAttempts} attempts`);
              await request.abort();
            }
            await new Promise(resolve => setTimeout(resolve, 1000));
          }
        }
      } catch (error) {
        await request.abort();
      }
    });

    page.on('response', async response => {
      const responseUrl = response.url();
      const contentType = response.headers()['content-type'] || '';

      // Store cookies from responses
      const cookies = await page.cookies();
      this.cookies = cookies;

      // Check for security headers
      this.checkSecurityHeaders(responseUrl, response.headers());

      // Only analyze HTML content
      if (contentType.includes('text/html') && response.status() === 200) {
        try {
          const body = await response.text();
          this.analyzeHtmlContent(responseUrl, body);
        } catch (error) {
          console.error(`Error analyzing response from ${responseUrl}:`, error);
        }
      }
    });
  }

  // Analyze HTML content for potential vulnerabilities
  analyzeHtmlContent(url, html) {
    // Check for lack of Content Security Policy
    if (!html.includes('Content-Security-Policy')) {
      this.vulnerabilities.push({
        type: 'Missing CSP',
        url: url,
        description: 'No Content Security Policy detected, which may allow script injection.'
      });
    }

    // Check for inline JavaScript
    const inlineScriptMatches = html.match(/<script>[\s\S]*?<\/script>/g);
    if (inlineScriptMatches && inlineScriptMatches.length > 0) {
      this.vulnerabilities.push({
        type: 'Inline Scripts',
        url: url,
        description: 'Page contains inline JavaScript which could be manipulated if XSS is possible.',
        count: inlineScriptMatches.length
      });
    }

    // Check for potentially unsafe element IDs or classes that might be manipulated
    const unsafePatterns = ['user', 'admin', 'password', 'login', 'account'];
    unsafePatterns.forEach(pattern => {
      if (html.includes(`id="${pattern}"`) || html.includes(`class="${pattern}"`)) {
        this.vulnerabilities.push({
          type: 'Potential DOM Manipulation Target',
          url: url,
          description: `Found element with identifier related to "${pattern}", which might be targeted for DOM manipulation.`,
        });
      }
    });
  }

  // Check for security headers
  checkSecurityHeaders(url, headers) {
    const securityHeaders = {
      'content-security-policy': 'Content-Security-Policy',
      'x-xss-protection': 'X-XSS-Protection',
      'x-content-type-options': 'X-Content-Type-Options',
      'x-frame-options': 'X-Frame-Options'
    };

    for (const [headerKey, headerName] of Object.entries(securityHeaders)) {
      if (!headers[headerKey]) {
        this.vulnerabilities.push({
          type: 'Missing Security Header',
          url: url,
          description: `Missing ${headerName} header which helps prevent various attacks including XSS.`
        });
      }
    }
  }

  // Crawl a single page and extract links, forms, and input fields
  async crawlPage(browser, page, pageUrl) {
    if (this.visitedUrls.has(pageUrl)) {
      return;
    }

    console.log(`Crawling: ${pageUrl}`);
    this.visitedUrls.add(pageUrl);

    try {
      // Add longer timeout and ignore HTTPS errors
      await page.goto(pageUrl, {
        waitUntil: 'networkidle2',
        timeout: 60000,
        ignoreHTTPSErrors: true
      });

      // Extract localStorage for later analysis
      const localStorageData = await page.evaluate(() => {
        const data = {};
        for (let i = 0; i < localStorage.length; i++) {
          const key = localStorage.key(i);
          data[key] = localStorage.getItem(key);
        }
        return data;
      });
      this.localStorage = { ...this.localStorage, ...localStorageData };

      // Extract all links from the page
      const links = await page.evaluate(() => {
        return Array.from(document.querySelectorAll('a')).map(a => {
          return {
            href: a.href,
            text: a.textContent.trim()
          };
        });
      });

      // Extract all forms from the page
      const forms = await page.evaluate(() => {
        return Array.from(document.querySelectorAll('form')).map(form => {
          const inputs = Array.from(form.querySelectorAll('input, textarea, select'))
            .map(input => {
              return {
                name: input.name,
                id: input.id,
                type: input.type,
                value: input.value,
                placeholder: input.placeholder
              };
            });

          return {
            action: form.action,
            method: form.method,
            id: form.id,
            inputs: inputs
          };
        });
      });

      // Save discovered forms
      forms.forEach(form => {
        if (!this.forms.some(f => f.action === form.action && f.id === form.id)) {
          this.forms.push({
            url: pageUrl,
            ...form
          });
        }
      });

      // Extract all input fields that are not in forms
      const inputFields = await page.evaluate(() => {
        return Array.from(document.querySelectorAll('input:not(form input), textarea:not(form textarea), [contenteditable="true"]'))
          .map(input => {
            return {
              type: input.type || 'contenteditable',
              name: input.name,
              id: input.id,
              placeholder: input.placeholder,
              attributes: Array.from(input.attributes).map(attr => ({
                name: attr.name,
                value: attr.value
              }))
            };
          });
      });

      // Save discovered input fields
      inputFields.forEach(field => {
        this.inputFields.push({
          url: pageUrl,
          field
        });
      });

      // Extract any API endpoints mentioned in JavaScript
      const scripts = await page.evaluate(() => {
        return Array.from(document.querySelectorAll('script')).map(script => {
          return script.textContent || '';
        });
      });

      this.analyzeScriptsForEndpoints(pageUrl, scripts);

      // Check for reflected parameters in the URL
      await this.checkForReflectedParameters(page, pageUrl);

      // Also check for URL fragment handling (common source of DOM XSS)
      await this.checkFragmentHandling(page, pageUrl);

      // Recursively crawl discovered links that belong to the same domain
      const baseUrlObj = new URL(this.targetUrl);
      const sameDomainLinks = links.filter(link => {
        try {
          const linkUrl = new URL(link.href);
          return linkUrl.hostname === baseUrlObj.hostname && !this.visitedUrls.has(link.href);
        } catch (e) {
          return false;
        }
      });

      // Limit crawling to a reasonable number of pages
      const MAX_PAGES = 20;
      if (this.visitedUrls.size >= MAX_PAGES) {
        console.log(`Reached maximum page limit (${MAX_PAGES}). Stopping crawl.`);
        return;
      }

      // Create a new page for each link to avoid state interference
      for (const link of sameDomainLinks.slice(0, 5)) { // Limit to 5 links per page to avoid excessive crawling
        const newPage = await browser.newPage();
        await this.setupRequestInterception(newPage);
        await this.crawlPage(browser, newPage, link.href);
        await newPage.close();
      }

    } catch (error) {
      if (error.message.includes('ERR_BLOCKED_BY_CLIENT')) {
        console.log(`Warning: Client-side blocking detected for ${pageUrl}`);
        // Add fallback behavior here
      } else {
        console.error(`Error crawling ${pageUrl}:`, error);
      }
    }
  }

  // Analyze scripts for API endpoints
  analyzeScriptsForEndpoints(pageUrl, scripts) {
    const apiPatterns = [
      /['"]\/api\/[^'"]+['"]/g,
      /fetch\(['"]([^'"]+)['"]\)/g,
      /\$\.ajax\(\s*{\s*url:\s*['"]([^'"]+)['"]/g,
      /axios\.(get|post|put|delete)\(['"]([^'"]+)['"]/g
    ];

    scripts.forEach(script => {
      apiPatterns.forEach(pattern => {
        const matches = script.match(pattern);
        if (matches) {
          matches.forEach(match => {
            // Extract the actual URL from the match
            const endpoint = match.replace(/['"]/g, '').replace(/^fetch\(/, '').replace(/\)$/, '');

            if (endpoint.includes('/api/')) {
              this.vulnerabilities.push({
                type: 'Potential API Endpoint',
                url: pageUrl,
                endpoint: endpoint,
                description: 'Discovered API endpoint that may accept user input and should be tested.'
              });
            }
          });
        }
      });
    });
  }

  // Check for reflected parameters in the URL
  async checkForReflectedParameters(page, pageUrl) {
    try {
      const urlObj = new URL(pageUrl);
      const params = urlObj.searchParams;

      if (params.toString()) {
        for (const [name, value] of params.entries()) {
          const uniqueValue = `XSSTEST_${Date.now()}_${name}`;

          // Create a new URL with the test parameter
          const testUrl = new URL(pageUrl);
          testUrl.searchParams.set(name, uniqueValue);

          // Navigate to the test URL
          await page.goto(testUrl.toString(), { waitUntil: 'networkidle2', timeout: 30000 });

          // Check if the value is reflected in the page
          const content = await page.content();
          if (content.includes(uniqueValue)) {
            this.vulnerabilities.push({
              type: 'Reflected Parameter',
              url: pageUrl,
              parameter: name,
              description: `Parameter ${name} is reflected in the page response, potential XSS vector.`
            });
          }
        }
      }
    } catch (error) {
      console.error(`Error checking reflected parameters for ${pageUrl}:`, error);
    }
  }

  // Check URL fragment handling (common source of DOM XSS)
  async checkFragmentHandling(page, pageUrl) {
    try {
      const fragmentValue = `DOMXSSTEST_${Date.now()}`;
      const fragmentUrl = `${pageUrl}#${fragmentValue}`;

      await page.goto(fragmentUrl, { waitUntil: 'networkidle2', timeout: 30000 });

      // Check if the fragment is accessed by JavaScript
      const fragmentUsed = await page.evaluate((testValue) => {
        // Return true if any script accesses location.hash or window.location.hash
        const origDescriptor = Object.getOwnPropertyDescriptor(Location.prototype, 'hash');
        let accessed = false;

        Object.defineProperty(Location.prototype, 'hash', {
          get: function () {
            accessed = true;
            return origDescriptor.get.call(this);
          },
          set: function (val) {
            accessed = true;
            return origDescriptor.set.call(this, val);
          }
        });

        // Let any potential scripts run
        setTimeout(() => { }, 1000);

        return accessed;
      }, fragmentValue);

      if (fragmentUsed) {
        this.vulnerabilities.push({
          type: 'URL Fragment Usage',
          url: pageUrl,
          description: 'Page accesses URL fragments via JavaScript. Potential vector for DOM-based XSS.'
        });
      }
    } catch (error) {
      console.error(`Error checking fragment handling for ${pageUrl}:`, error);
    }
  }

  // Test discovered elements for vulnerabilities
  async testDiscoveredElements(browser) {
    console.log('Testing discovered forms and input fields for vulnerabilities...');

    const page = await browser.newPage();
    await this.setupRequestInterception(page);

    // Add error handler for navigation errors
    page.on('error', err => {
      console.log('Page error:', err);
    });

    try {
      for (const pageUrl of Array.from(this.visitedUrls)) {
        try {
          await page.goto(pageUrl, {
            waitUntil: 'networkidle2',
            timeout: 30000,
          });

          // Wait for any client-side JS to execute
          await page.waitForTimeout(2000);

          // Get page content with retry logic
          const content = await this.getPageContentSafely(page);

          if (!content) {
            console.log(`Skipping tests for ${pageUrl} - could not get page content`);
            continue;
          }

          // Test payloads
          const xssPayloads = [
            '<script>alert(1)</script>',
            '"><script>alert(1)</script>',
            '<img src=x onerror=alert(1)>',
            '\'><img src=x onerror=alert(1)>',
            'javascript:alert(1)'
          ];

          // Test forms
          for (const form of this.forms) {
            try {
              if (form.url !== pageUrl) continue; // Only test forms on the current page

              // For each input in the form, try all payloads
              for (const input of form.inputs) {
                if (input.type === 'hidden' || input.type === 'submit') continue;

                for (const payload of xssPayloads) {
                  // Reset page state
                  await page.reload({ waitUntil: 'networkidle2' });

                  // Set up alert detection
                  let alertDetected = false;
                  page.on('dialog', async dialog => {
                    alertDetected = true;
                    await dialog.dismiss();
                  });

                  // Fill form
                  await page.evaluate((formSelector, inputName, value) => {
                    const form = document.querySelector(formSelector);
                    if (form) {
                      const input = form.querySelector(`[name="${inputName}"]`);
                      if (input) input.value = value;
                    }
                  }, `form[action="${form.action}"]`, input.name, payload);

                  // Submit form
                  await Promise.all([
                    page.waitForNavigation({ waitUntil: 'networkidle2', timeout: 5000 }).catch(() => { }),
                    page.evaluate((formSelector) => {
                      const form = document.querySelector(formSelector);
                      if (form) form.submit();
                    }, `form[action="${form.action}"]`)
                  ]);

                  if (alertDetected) {
                    this.vulnerabilities.push({
                      type: 'XSS Vulnerability',
                      url: form.url,
                      formAction: form.action,
                      inputName: input.name,
                      payload: payload,
                      description: 'Form input vulnerable to XSS.'
                    });
                    break; // No need to test more payloads for this input
                  }

                  // Check if the payload was reflected in the page
                  const responseContent = await page.content();
                  if (responseContent.includes(payload)) {
                    this.vulnerabilities.push({
                      type: 'Potential XSS (Reflected)',
                      url: form.url,
                      formAction: form.action,
                      inputName: input.name,
                      payload: payload,
                      description: 'Form input value is reflected in page, potential XSS vulnerability.'
                    });
                  }
                }
              }
            } catch (error) {
              console.error(`Error testing form at ${form.url}:`, error);
            }
          }

          // Test URL parameters for reflection
          const uniqueUrls = Array.from(this.visitedUrls);
          for (const testPageUrl of uniqueUrls) {
            try {
              const urlObj = new URL(testPageUrl);

              // Skip URLs that already have parameters
              if (urlObj.search) continue;

              // Test for parameter reflection with test parameters
              for (const paramName of ['q', 'search', 'id', 'query', 'page', 'name']) {
                for (const payload of xssPayloads) {
                  const testUrl = new URL(testPageUrl);
                  testUrl.searchParams.set(paramName, payload);

                  // Set up alert detection
                  let alertDetected = false;
                  page.on('dialog', async dialog => {
                    alertDetected = true;
                    await dialog.dismiss();
                  });

                  await page.goto(testUrl.toString(), { waitUntil: 'networkidle2', timeout: 5000 }).catch(() => { });

                  if (alertDetected) {
                    this.vulnerabilities.push({
                      type: 'URL Parameter XSS',
                      url: testPageUrl,
                      parameter: paramName,
                      payload: payload,
                      description: 'URL parameter vulnerable to XSS.'
                    });
                    break;
                  }

                  // Check if the payload was reflected in the page
                  const responseContent = await page.content();
                  if (responseContent.includes(payload)) {
                    this.vulnerabilities.push({
                      type: 'Potential URL Parameter XSS',
                      url: testPageUrl,
                      parameter: paramName,
                      payload: payload,
                      description: 'URL parameter value is reflected in page, potential XSS vulnerability.'
                    });
                  }
                }
              }
            } catch (error) {
              console.error(`Error testing URL parameters for ${testPageUrl}:`, error);
            }
          }
        } catch (error) {
          console.error(`Error testing page ${pageUrl}:`, error);
          // Continue with next URL
          continue;
        }
      }
    } finally {
      await page.close();
    }
  }

  // Add this helper method
  async getPageContentSafely(page) {
    const maxAttempts = 3;
    let attempts = 0;

    while (attempts < maxAttempts) {
      try {
        return await page.content();
      } catch (error) {
        attempts++;
        if (attempts === maxAttempts) {
          console.error('Failed to get page content after multiple attempts');
          return null;
        }
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
    }
  }

  // Generate report of discovered vulnerabilities
  generateReport() {
    console.log('\n===== Vulnerability Scan Report =====\n');
    console.log(`Target: ${this.targetUrl}`);
    console.log(`Pages Crawled: ${this.visitedUrls.size}`);
    console.log(`Forms Discovered: ${this.forms.length}`);
    console.log(`Input Fields Discovered: ${this.inputFields.length}`);
    console.log(`Vulnerabilities Found: ${this.vulnerabilities.length}`);

    if (this.vulnerabilities.length > 0) {
      console.log('\n----- Vulnerability Details -----\n');

      // Group vulnerabilities by type
      const groupedVulns = {};
      this.vulnerabilities.forEach(vuln => {
        if (!groupedVulns[vuln.type]) {
          groupedVulns[vuln.type] = [];
        }
        groupedVulns[vuln.type].push(vuln);
      });

      // Print details for each vulnerability type
      for (const [type, vulns] of Object.entries(groupedVulns)) {
        console.log(`\n${type} (${vulns.length}):`);
        vulns.forEach((vuln, index) => {
          console.log(`  ${index + 1}. ${vuln.description}`);
          console.log(`     URL: ${vuln.url}`);
          if (vuln.parameter) console.log(`     Parameter: ${vuln.parameter}`);
          if (vuln.formAction) console.log(`     Form Action: ${vuln.formAction}`);
          if (vuln.inputName) console.log(`     Input Name: ${vuln.inputName}`);
          if (vuln.payload) console.log(`     Payload: ${vuln.payload}`);
          console.log();
        });
      }
    }

    // Save report to file
    const reportData = {
      target: this.targetUrl,
      scanDate: new Date().toISOString(),
      pagesCrawled: Array.from(this.visitedUrls),
      forms: this.forms,
      inputFields: this.inputFields,
      vulnerabilities: this.vulnerabilities,
      cookies: this.cookies,
      localStorage: this.localStorage
    };

    fs.writeFileSync('vulnerabilities.json', JSON.stringify(reportData, null, 2));
    console.log('\nFull report saved to vulnerabilities.json');
  }
}

// Example usage
async function main() {
  const targetUrl = 'http://13.60.183.62/';
  const scanner = new WebVulnerabilityScanner(targetUrl);
  await scanner.scan();
}

main().catch(console.error);