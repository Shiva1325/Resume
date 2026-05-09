#!/usr/bin/env python3
"""
Downloads the compiled PDF from Overleaf using session auth.
Exits with code 1 if unchanged (so the workflow skips the commit step).
"""
import os, sys, hashlib, requests
from bs4 import BeautifulSoup

EMAIL      = os.environ['OVERLEAF_EMAIL']
PASSWORD   = os.environ['OVERLEAF_PASSWORD']
PROJECT_ID = os.environ.get('OVERLEAF_PROJECT_ID', '63b20a7df9ce7bcb5887cb22')
OUT_FILE   = 'resume.pdf'

session = requests.Session()
session.headers['User-Agent'] = 'Mozilla/5.0 (compatible; resume-sync/1.0)'

# ── Step 1: Grab CSRF token ──────────────────────────────────────
resp = session.get('https://www.overleaf.com/login')
resp.raise_for_status()
soup = BeautifulSoup(resp.text, 'html.parser')

csrf = (soup.find('meta',  {'name': 'ol-csrfToken'}) or
        soup.find('input', {'name': '_csrf'}))
if not csrf:
    print('ERROR: Could not find CSRF token')
    sys.exit(2)

csrf_token = csrf.get('content') or csrf.get('value')

# ── Step 2: Login ────────────────────────────────────────────────
resp = session.post(
    'https://www.overleaf.com/login',
    json={'_csrf': csrf_token, 'email': EMAIL, 'password': PASSWORD},
    allow_redirects=True,
)
if resp.status_code not in (200, 302) or 'Set-Cookie' not in resp.headers and 'overleaf_session' not in str(session.cookies):
    print(f'ERROR: Login failed (status {resp.status_code})')
    sys.exit(2)

print('Logged in to Overleaf')

# ── Step 3: Download compiled PDF ───────────────────────────────
pdf_url = (f'https://www.overleaf.com/download/project/{PROJECT_ID}'
           f'/build/latest/output/output.pdf?compileGroup=standard&popupDownload=true')

resp = session.get(pdf_url, allow_redirects=True, timeout=60)
if resp.status_code != 200 or not resp.content[:4] == b'%PDF':
    print(f'ERROR: PDF download failed (status {resp.status_code})')
    sys.exit(2)

new_hash = hashlib.sha256(resp.content).hexdigest()

# ── Step 4: Compare with existing PDF ───────────────────────────
if os.path.exists(OUT_FILE):
    with open(OUT_FILE, 'rb') as f:
        old_hash = hashlib.sha256(f.read()).hexdigest()
    if old_hash == new_hash:
        print('PDF unchanged — skipping update')
        sys.exit(1)  # signal: no change

with open(OUT_FILE, 'wb') as f:
    f.write(resp.content)

print(f'PDF updated ({len(resp.content):,} bytes) hash={new_hash[:12]}')
