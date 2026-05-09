#!/usr/bin/env python3
"""
Downloads the compiled PDF from Overleaf using Playwright (handles JS auth).
Exit 0 = PDF updated. Exit 1 = unchanged. Exit 2 = error.
"""
import os, sys, hashlib, shutil, time
from playwright.sync_api import sync_playwright

EMAIL      = os.environ['OVERLEAF_EMAIL']
PASSWORD   = os.environ['OVERLEAF_PASSWORD']
PROJECT_ID = os.environ.get('OVERLEAF_PROJECT_ID', '63b20a7df9ce7bcb5887cb22')
OUT_FILE   = 'resume.pdf'
TMP_FILE   = '/tmp/resume_new.pdf'

def sha256(path):
    if not os.path.exists(path):
        return None
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()

old_hash = sha256(OUT_FILE)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent=(
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ),
        viewport={'width': 1920, 'height': 1080},
        locale='en-US',
    )
    page = context.new_page()

    # ── Login ────────────────────────────────────────────────────
    print('Navigating to Overleaf login…')
    page.goto('https://www.overleaf.com/login', wait_until='domcontentloaded')
    page.wait_for_selector('input[type="email"]', timeout=15000)

    page.fill('input[type="email"]', EMAIL)
    page.fill('input[type="password"]', PASSWORD)
    page.click('button[type="submit"]')

    # Poll until we leave /login (handles SPA redirects and slow networks)
    deadline = time.time() + 60
    while True:
        current = page.url
        if '/login' not in current and current not in ('', 'about:blank'):
            break
        if time.time() > deadline:
            # Dump page text to help diagnose bot-detection / errors
            try:
                alerts = page.query_selector_all('.alert, .notification, [role="alert"], .ol-flash')
                for el in alerts:
                    print(f'  Page alert: {el.text_content().strip()}')
            except Exception:
                pass
            print(f'ERROR: Login timed out after 60s. URL: {current}')
            browser.close()
            sys.exit(2)
        time.sleep(1)

    print(f'Logged in  →  {page.url}')

    # ── Download PDF ─────────────────────────────────────────────
    pdf_url = (f'https://www.overleaf.com/download/project/{PROJECT_ID}'
               f'/build/latest/output/output.pdf')

    with page.expect_download(timeout=60000) as dl:
        page.goto(pdf_url)

    dl.value.save_as(TMP_FILE)
    browser.close()

# ── Validate ─────────────────────────────────────────────────────
with open(TMP_FILE, 'rb') as f:
    content = f.read()

if not content.startswith(b'%PDF'):
    print(f'ERROR: not a PDF ({len(content)} bytes)')
    sys.exit(2)

new_hash = hashlib.sha256(content).hexdigest()
print(f'Downloaded {len(content):,} bytes  hash={new_hash[:12]}')

if old_hash == new_hash:
    print('PDF unchanged — skipping')
    sys.exit(1)

shutil.copy(TMP_FILE, OUT_FILE)
print('PDF updated')
