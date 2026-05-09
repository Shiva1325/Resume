#!/usr/bin/env python3
"""
Triggers an Overleaf compile via API, then downloads the resulting PDF.
Exit 0 = PDF updated. Exit 1 = unchanged. Exit 2 = error.
"""
import os, sys, hashlib, re, requests

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

# ── Get CSRF token from project page ─────────────────────────────
r = sess.get(f'https://www.overleaf.com/project/{PROJECT_ID}', timeout=30)
print(f'Project page: {r.status_code}')

csrf_token = None
for pattern in [
    r'ol-csrfToken[^>]*?content="([^"]+)"',
    r'"csrfToken"\s*:\s*"([^"]+)"',
    r'name="_csrf"[^>]*?value="([^"]+)"',
]:
    m = re.search(pattern, r.text)
    if m:
        csrf_token = m.group(1)
        print(f'CSRF token found (len={len(csrf_token)})')
        break

if not csrf_token:
    csrf_token = sess.cookies.get('_csrf')
    if csrf_token:
        print('CSRF token from cookie')

if not csrf_token:
    print('ERROR: Could not find CSRF token in project page')
    sys.exit(2)

# ── Trigger compile ───────────────────────────────────────────────
print('Triggering compile…')
compile_r = sess.post(
    f'https://www.overleaf.com/project/{PROJECT_ID}/compile',
    json={
        'rootDoc_id': None,
        'draft': False,
        'check': 'silent',
        'incrementalCompilesEnabled': True,
        'compileGroup': 'standard',
        'stopOnFirstError': False,
    },
    headers={
        'X-CSRF-Token': csrf_token,
        'Accept': 'application/json',
    },
    timeout=120,
)
print(f'Compile response: {compile_r.status_code}')
print(f'All cookies after compile: {dict(sess.cookies)}')
print(f'Compile body: {compile_r.text[:2000]}')

if compile_r.status_code != 200:
    print(f'ERROR: Compile API returned {compile_r.status_code}: {compile_r.text[:300]}')
    sys.exit(2)

data = compile_r.json()
print(f'Compile status: {data.get("status")}')
clsi_server_id = data.get('clsiServerId', '')
if clsi_server_id:
    print(f'CLSI Server ID: {clsi_server_id}')
    # Must be a cookie (not a header) — this is how the browser routes to the right CLSI instance
    sess.cookies.set('clsiServerId', clsi_server_id, domain='.overleaf.com', path='/')

if data.get('status') not in ('success', 'clsi-maintenance'):
    print(f'ERROR: Compile did not succeed: {data.get("status")}')
    sys.exit(2)

# ── Find PDF output file ──────────────────────────────────────────
pdf_file = None
for f in data.get('outputFiles', []):
    if f.get('path') == 'output.pdf':
        pdf_file = f
        break

if not pdf_file:
    print(f'ERROR: No output.pdf in compile result. Files: {[f.get("path") for f in data.get("outputFiles", [])]}')
    sys.exit(2)

build_id  = pdf_file['build']
exact_url = 'https://www.overleaf.com' + pdf_file['url']
print(f'Build ID: {build_id}')
print(f'Exact URL: {exact_url}')

# ── Try download URLs (exact first, then fallbacks) ───────────────
download_headers = {
    'Referer': f'https://www.overleaf.com/project/{PROJECT_ID}',
    'Accept': 'application/pdf,*/*',
}

pdf_urls = [
    exact_url,
    f'https://www.overleaf.com/download/project/{PROJECT_ID}/build/{build_id}/output/output.pdf',
    f'https://www.overleaf.com/download/project/{PROJECT_ID}/build/{build_id}/output/output.pdf?compileGroup=standard',
]

content = None
for url in pdf_urls:
    r = sess.get(url, timeout=60, allow_redirects=True, headers=download_headers)
    print(f'  {r.status_code}  {len(r.content)} bytes  ← {url[-60:]}')
    if r.status_code == 200 and r.content[:4] == b'%PDF':
        content = r.content
        break
    if r.status_code != 200:
        print(f'    Response headers: {dict(r.headers)}')

if content is None:
    print('ERROR: All download URLs failed')
    sys.exit(2)

# ── Compare and save ──────────────────────────────────────────────
new_hash = hashlib.sha256(r.content).hexdigest()
print(f'hash={new_hash[:12]}')

if old_hash == new_hash:
    print('PDF unchanged — skipping')
    sys.exit(1)

with open(OUT_FILE, 'wb') as f:
    f.write(r.content)
print('PDF updated')
