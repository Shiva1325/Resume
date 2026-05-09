#!/usr/bin/env python3
"""
Downloads the compiled PDF from Overleaf using a stored session cookie.
Exit 0 = PDF updated. Exit 1 = unchanged. Exit 2 = error.
"""
import os, sys, hashlib, requests

SESSION    = os.environ['OVERLEAF_SESSION']
PROJECT_ID = os.environ.get('OVERLEAF_PROJECT_ID', '63b20a7df9ce7bcb5887cb22')
OUT_FILE   = 'resume.pdf'

def sha256(path):
    if not os.path.exists(path):
        return None
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()

old_hash = sha256(OUT_FILE)

sess = requests.Session()
sess.cookies.set('overleaf_session2', SESSION, domain='.overleaf.com', path='/')
sess.headers.update({
    'User-Agent': (
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ),
    'Referer': 'https://www.overleaf.com',
})

# ── Verify session ────────────────────────────────────────────────
r = sess.get('https://www.overleaf.com/project', allow_redirects=True, timeout=30)
if '/login' in r.url:
    print('ERROR: Session expired — refresh OVERLEAF_SESSION secret')
    sys.exit(2)
print(f'Session valid  →  {r.url}')

# ── Try multiple known PDF URL formats ───────────────────────────
pdf_urls = [
    f'https://www.overleaf.com/project/{PROJECT_ID}/output/output.pdf',
    f'https://www.overleaf.com/download/project/{PROJECT_ID}/build/latest/output/output.pdf',
]

content = None
for url in pdf_urls:
    r = sess.get(url, timeout=60, allow_redirects=True)
    print(f'Tried: {url}  →  {r.status_code}  ({len(r.content)} bytes)')
    if r.status_code == 200 and r.content[:4] == b'%PDF':
        content = r.content
        break

if content is None:
    print('ERROR: Could not download PDF from any URL')
    sys.exit(2)

# ── Compare and save ─────────────────────────────────────────────
new_hash = hashlib.sha256(content).hexdigest()
print(f'Downloaded {len(content):,} bytes  hash={new_hash[:12]}')

if old_hash == new_hash:
    print('PDF unchanged — skipping')
    sys.exit(1)

with open(OUT_FILE, 'wb') as f:
    f.write(content)
print('PDF updated')
