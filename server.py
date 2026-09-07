#!/usr/bin/env python3
"""CruiseNext Itinerary Studio Plus."""
from __future__ import annotations
import json, os, re, time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from ncl_official import official_lookup
try:
    from ocr_extract import extract_screenshots
except Exception as error:
    extract_screenshots = None
    print('ocr extract unavailable', error)

ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / 'public' if (ROOT / 'public' / 'index.html').exists() else ROOT
ORIGINAL_EXTRACT = 'https://cruisenext-itinerary-studio-multi.onrender.com/api/extract'
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
BATCH_SIZE = 4
MAX_FILES = 10

def fetch_bytes(url, data=None, headers=None, timeout=30):
    req = Request(url, data=data, headers={'User-Agent': USER_AGENT, **(headers or {})}, method='POST' if data is not None else 'GET')
    try:
        with urlopen(req, timeout=timeout) as response:
            return response.status, response.headers.get('Content-Type',''), response.read()
    except HTTPError as error:
        body = error.read() if error.fp else b''
        ct = error.headers.get('Content-Type','') if error.headers else ''
        return error.code, ct, body

def parse_multipart(handler):
    content_type = handler.headers.get('Content-Type','')
    length = int(handler.headers.get('Content-Length','0') or 0)
    raw = handler.rfile.read(length) if length else b''
    files = {}
    match = re.search(r'boundary=([^;]+)', content_type or '')
    if not match:
        return files
    boundary = match.group(1).strip().strip('"').encode('utf-8')
    for part in raw.split(b'--' + boundary):
        if not part or part in (b'--', b'--\r\n', b'--\n') or part.startswith(b'--'):
            continue
        header, sep, body = part.partition(b'\r\n\r\n')
        if not sep:
            header, sep, body = part.partition(b'\n\n')
        if not sep:
            continue
        body = body.rstrip(b'\r\n')
        if body.endswith(b'--'):
            body = body[:-2]
        header_text = header.decode('utf-8', 'ignore')
        name_match = re.search(r'name="([^"]+)"', header_text)
        filename_match = re.search(r'filename="([^"]*)"', header_text)
        if not name_match or not filename_match:
            continue
        name = name_match.group(1)
        filename = filename_match.group(1) or 'screenshot.png'
        mime_match = re.search(r'Content-Type:\s*([^\r\n]+)', header_text, flags=re.I)
        mime = (mime_match.group(1).strip() if mime_match else 'image/png')
        files.setdefault(name, []).append((filename, mime, body))
    return files

def _post_extract_batch(batch):
    boundary = '----CruiseNextBoundary7MA4YWxkTrZu0gW'
    chunks = []
    for index, item in enumerate(batch):
        if not isinstance(item, (list, tuple)) or len(item) < 3:
            continue
        filename, mime, payload = item[0], item[1], item[2]
        name = filename or f'screenshot-{index+1}.png'
        chunks.append(f'--{boundary}\r\n'.encode())
        chunks.append(f'Content-Disposition: form-data; name="images"; filename="{name}"\r\n'.encode())
        chunks.append(f'Content-Type: {mime or "image/png"}\r\n\r\n'.encode())
        chunks.append(payload or b'')
        chunks.append(b'\r\n')
    chunks.append(f'--{boundary}--\r\n'.encode())
    headers = {'Content-Type': f'multipart/form-data; boundary={boundary}', 'Accept': 'application/json'}
    last_error = None
    for attempt in range(2):
        try:
            if attempt:
                time.sleep(3)
            status, content_type, response_body = fetch_bytes(ORIGINAL_EXTRACT, data=b''.join(chunks), headers=headers, timeout=90)
            if 'application/json' not in (content_type or ''):
                last_error = 'unexpected response'
                continue
            parsed = json.loads(response_body.decode('utf-8'))
            return status, parsed
        except Exception as error:
            last_error = error
            print('proxy batch failed', attempt + 1, error)
    return 502, {'error': str(last_error) if last_error else 'Screenshot reader is busy.'}

def proxy_extract(files):
    files = list(files)[:MAX_FILES]
    itineraries = []
    last_error = None
    for start in range(0, len(files), BATCH_SIZE):
        batch = files[start:start + BATCH_SIZE]
        status, parsed = _post_extract_batch(batch)
        if isinstance(parsed, dict) and parsed.get('itineraries'):
            itineraries.extend(parsed['itineraries'])
        elif isinstance(parsed, dict) and parsed.get('error'):
            last_error = parsed.get('error')
            print('batch error', start, last_error)
        else:
            last_error = f'batch {start} failed ({status})'
    if itineraries:
        for index, item in enumerate(itineraries, start=1):
            if isinstance(item, dict):
                item['source_index'] = index
        return 200, {'itineraries': itineraries}
    return 502, {'error': last_error or 'Could not read those screenshots.'}

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PUBLIC), **kwargs)
    def log_message(self, format, *args):
        print('[plus]', self.address_string(), format % args)
    def _json(self, status, payload):
        raw = json.dumps(payload, default=str).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers(); self.wfile.write(raw)
    def do_GET(self):
        path = self.path.split('?', 1)[0]
        if path == '/api/health':
            self._json(200, {'ok': True, 'ocr': bool(extract_screenshots), 'maxFiles': MAX_FILES})
            return
        if path in ('/', '/index.html'):
            html = (PUBLIC / 'index.html').read_text(encoding='utf-8')
            scripts = ''
            if 'dest.js' not in html:
                scripts += '<script src="/dest.js"></script>\n'
            if 'reset.js' not in html:
                scripts += '<script src="/reset.js"></script>\n'
            if scripts:
                html = html.replace('</body>', scripts + '</body>')
            raw = html.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers(); self.wfile.write(raw)
            return
        return super().do_GET()
    def do_POST(self):
        if self.path == '/api/extract':
            try:
                files = (parse_multipart(self).get('images') or [])[:MAX_FILES]
                if not files:
                    self._json(400, {'error': 'Please upload at least 1 screenshot.'}); return
                status, payload = proxy_extract(files)
                if isinstance(payload, dict) and payload.get('itineraries'):
                    self._json(status, payload); return
                if extract_screenshots:
                    try:
                        ocr_status, ocr_payload = extract_screenshots(files)
                        if isinstance(ocr_payload, dict) and (ocr_payload.get('itineraries') or ocr_status < 500):
                            self._json(ocr_status, ocr_payload); return
                    except Exception as error:
                        print('local ocr failed', error)
                self._json(status if status else 502, payload if isinstance(payload, dict) else {'error': 'Could not read those screenshots.'})
            except Exception as error:
                print('extract failed', error)
                self._json(502, {'error': f'Could not read those screenshots: {error}'})
            return
        if self.path == '/api/ncl-lookup':
            length = int(self.headers.get('Content-Length','0') or 0)
            raw = self.rfile.read(length) if length else b'{}'
            try:
                body = json.loads(raw.decode('utf-8') or '{}')
            except Exception:
                self._json(400, {'error': 'Invalid JSON body.'}); return
            ship_name = str(body.get('shipName') or '').strip()
            month = int(body['month']) if body.get('month') else None
            year = int(body['year']) if body.get('year') else None
            direct_url = str(body.get('url') or '').strip()
            destination = str(body.get('destination') or '').strip()
            query = str(body.get('query') or body.get('itinerary') or '').strip()
            if not ship_name and not direct_url and not destination and not query:
                self._json(400, {'error': 'Enter a ship, destination, itinerary name, or NCL URL.'}); return
            try:
                official = official_lookup(ship_name, month, year, direct_url, destination, query)
            except Exception as error:
                print('official lookup failed', error)
                self._json(502, {'error': f'Could not pull sailings from NCL.com: {error}'}); return
            if not official:
                self._json(404, {'error': 'No matching NCL sailings were found.'}); return
            self._json(200, {'source':'ncl.com','queried':{'shipName':ship_name,'month':month,'year':year,'url':direct_url or None,'destination':destination or None,'query':query or None},'itineraries':official})
            return
        self.send_error(404, 'Not Found')

def main():
    port = int(os.environ.get('PORT', '3333'))
    server = ThreadingHTTPServer(('0.0.0.0', port), Handler)
    print(f'CruiseNext Studio Plus running on http://0.0.0.0:{port}')
    server.serve_forever()

if __name__ == '__main__':
    main()
