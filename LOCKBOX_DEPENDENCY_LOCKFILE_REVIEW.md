# LockBox — committed frontend dependency lockfile

Review date: 2026-11-22

## Provenance
- Source: GitHub Actions artifact `hppusa-node-lockfile-review`
- Source workflow run: https://github.com/HPPUSA/HPPUSA-AI/actions/runs/45062444050
- Artifact ID: `14769514862`
- Artifact SHA-256: `8caffd4b1664446b1cfe0956aa90f14d7d20cae5543cc5dbcfec52ab3ff27bba`
- Extracted `package-lock.json` SHA-256: `53cc60cdefd03ad270a8c3b1a84c883b78cfe6e42712bf7bb949b35ed10fe80a`

## Reviewed contents
- Lockfile version: 3
- Package entries: 46 total (root plus 45 dependency packages)
- All 45 dependency entries contain both `resolved` and `integrity` fields.
- Direct development dependencies match `package.json` exactly:
  - `@playwright/test` 1.65.0
  - `dompurify` 3.4.17
  - `jsdom` 26.1.0
  - `marked` 18.1.3

## Commit and validation
- The exact artifact contents were imported into `package-lock.json` on the isolated branch `orchestra/phase1-hardening`.
- Import workflow run: https://github.com/HPPUSA/HPPUSA-AI/actions/runs/45081256991
- Import job verified the lockfile SHA-256, ran `npm ci --ignore-scripts --no-audit --no-fund`, and ran `npm ls --depth=0`; all succeeded.
- The one-time import workflow was removed after the successful import.
- The ongoing Phase 1 CI workflow was updated to validate the committed lockfile with a clean installation and ensure the lockfile remains unchanged.

## Browser-level frontend validation
- Added a Playwright Chromium test suite for the actual Flask-rendered HPPUSA-AI page.
- Tests verify the page shell and frontend libraries load; active HTML, event-handler attributes and JavaScript links are blocked; safe Markdown formatting and HTTPS links remain usable; empty input is validated; and a mocked chat reply is rendered safely.
- The tests intercept the pinned CDN script URLs and serve the exact versions installed from the lockfile. The browser test uses a local Flask server and mocked responses; it makes no Groq API call and does not contact the live service.
- Latest full isolated CI run: https://github.com/HPPUSA/HPPUSA-AI/actions/runs/45081578024 — all six jobs passed: lockfile install, frontend jsdom XSS tests, browser-level Playwright tests, and Python/Gunicorn checks on Python 3.11, 3.13 and 3.14.8.

## Scope and status
- This is an isolated-branch change only.
- No merge to `main`, production configuration change, Render change, Cloudflare change, production secret change, or deployment was performed.
- At the latest check, the isolated branch was 68 commits ahead of `main`, zero behind. The branch remains unprotected.
- The branch remains subject to the separate LockBox release-readiness review. Passing automated checks do not approve production rollout.
