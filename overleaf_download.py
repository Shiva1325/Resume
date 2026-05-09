#!/usr/bin/env python3
"""
Downloads the compiled PDF from Overleaf using Playwright (handles JS auth).
Exit 0 = PDF updated. Exit 1 = unchanged. Exit 2 = error.
"""
import os, sys, hashlib, shutil
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
    page = browser.new_page()

    # ── Login ────────────────────────────────────────────────────
    page.goto('https://www.overleaf.com/login', wait_until='networkidle')
    page.fill('input[type="email"]', EMAIL)
    page.fill('input[type="password"]', PASSWORD)

    page.click('button[type="submit"]')
    page.wait_for_url('**/project**', timeout=60000)

    if '/login' in page.url:
        print('ERROR: Login failed — check credentials')
        browser.close()
        sys.exit(2)

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
