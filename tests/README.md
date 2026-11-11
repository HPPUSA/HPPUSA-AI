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

Expected success output ends with `14 passed` (current suite). If a test fails, copy the complete PowerShell output for review. Do not add a Groq API key or run the live service for this test.

## Scope

- Tests run only against the extracted branch copy.
- No Render service, production endpoint, or Payhip product is contacted.
- The test suite uses a fake Groq client; missing-key and failure tests deliberately avoid provider calls.
