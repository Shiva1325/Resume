#!/usr/bin/env python3
"""
Downloads the compiled PDF from Overleaf using a stored session cookie.
Exit 0 = PDF updated. Exit 1 = unchanged. Exit 2 = error.
"""
import os, sys, hashlib, shutil
from playwright.sync_api import sync_playwright

SESSION    = os.environ['OVERLEAF_SESSION']
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
    )

    # ── Inject session cookie (skip password login entirely) ──────
    context.add_cookies([{
        'name':     'overleaf_session2',
        'value':    SESSION,
        'domain':   '.overleaf.com',
        'path':     '/',
        'httpOnly': True,
        'secure':   True,
        'sameSite': 'Lax',
    }])

    page = context.new_page()
    page.goto('https://www.overleaf.com/project', wait_until='domcontentloaded', timeout=30000)

    if '/login' in page.url:
        print('ERROR: Session cookie expired — refresh OVERLEAF_SESSION secret')
        browser.close()
        sys.exit(2)

    print(f'Session valid  →  {page.url}')

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
