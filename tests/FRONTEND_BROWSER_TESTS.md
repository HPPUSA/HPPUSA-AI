# HPPUSA-AI isolated browser test coverage

The Phase 1 isolated branch now includes a Playwright browser suite for the actual Flask-rendered page.

Coverage:
- Confirms the page shell, form controls, and pinned frontend libraries load in Chromium.
- Exercises the actual `formatReply` function in a browser, checking that active HTML, event-handler attributes, and JavaScript URLs are blocked while safe Markdown formatting and HTTPS links remain usable.
- Exercises empty-input validation and a mocked chat response through the real browser UI.
- Intercepts the two pinned jsDelivr script URLs and serves the exact lockfile-installed package files locally. The tests do not depend on external CDN availability.
- The Flask server is local to the CI job. Chat responses are mocked; no Groq API request, provider credentials, production hostname, or live service is used.

Run locally from the repository root after installing the pinned dependencies and Chromium:
`npm ci --ignore-scripts --no-audit --no-fund`
`python -m pip install -r requirements.txt`
`npx playwright install chromium`
`npm run test:frontend:browser`

The browser suite is isolated test coverage, not production deployment approval.
