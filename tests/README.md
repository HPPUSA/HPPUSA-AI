# Running the HPPUSA-AI Phase 1 tests

These tests are designed to run locally with a mocked Groq client. They do not need a Groq API key and do not call the live AI provider.

## Windows 10/11 (PowerShell)

1. Download the ZIP for the `orchestra/phase1-hardening` branch from GitHub and extract it.
2. Open the extracted project folder in File Explorer.
3. Click the address bar, type `powershell`, and press Enter.
4. Run:

```powershell
py -3 --version
py -3 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pytest
python -m pytest -q
```

If `py -3 --version` fails, install Python 3.11 or newer from python.org, then reopen PowerShell and retry.

Expected Python success output ends with `28 passed` (current Python suite). The suite covers rate-limit expiry at the exact 60-second boundary, concurrent requests sharing one client address, rejection of scoped IPv6 identities, and capacity handling. At capacity, expired client records are reclaimed without evicting active records. The reclamation scan can inspect up to 5,000 tracked identities while holding the process-local lock; this is a bounded but potentially contention-producing operation and should be revisited before higher-volume use. The separate frontend XSS test requires Node.js 22 and these exact test dependencies:

```powershell
npm install --no-save --no-package-lock --no-audit --no-fund jsdom@26.1.0 dompurify@3.4.17 marked@18.1.3
node tests/frontend_xss.test.mjs
```

Do not add a Groq API key or run the live service for these tests.

## Scope

- Tests run only against the extracted branch copy.
- No Render service, production endpoint, or Payhip product is contacted.
- Python tests use a fake Groq client; missing-key and failure tests deliberately avoid provider calls.
- The frontend test loads the actual formatter from the `App.py` page template in a local simulated DOM. It checks that executable markup and unsafe links are removed while ordinary Markdown formatting and HTTPS links remain.
