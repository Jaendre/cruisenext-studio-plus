#!/usr/bin/env python3
"""CruiseNext Itinerary Studio Plus."""
from __future__ import annotations
import json, os, email, re, time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
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
    raw = handler.rfile.read(length)
    parsed = email.message_from_bytes(b'Content-Type: '+content_type.encode('utf-8')+b'\r\n\r\n'+raw)
    files, fields = {}, {}
    if parsed.is_multipart():
        for part in parsed.iter_parts():
            disposition = part.get('Content-Disposition','')
            name_match = re.search(r'name="([^"]+)"', disposition)
            filename_match = re.search(r'filename="([^"]*)"', disposition)
            if not name_match:
                continue
            name = name_match.group(1)
            payload = part.get_payload(decode=True) or b''
            if filename_match:
                files.setdefault(name, []).append((filename_match.group(1), part.get_content_type(), payload))
            else:
                fields[name] = payload.decode('utf-8', errors='ignore')
    return files, fields

def wake_extract_service():
    try:
        fetch_bytes(ORIGINAL_EXTRACT.rsplit('/', 1)[0] + '/', timeout=20)
    except Exception as error:
        print('wake extract skipped', error)

def proxy_extract(files):
    boundary = '----CruiseNextBoundary7MA4YWxkTrZu0gW'
    chunks=[]
    for index, (filename, mime, payload) in enumerate(files):
        name = filename or f'screenshot-{index+1}.png'
        chunks.append(f'--{boundary}\r\n'.encode())
        chunks.append(f'Content-Disposition: form-data; name="images"; filename="{name}"\r\n'.encode())
        chunks.append(f'Content-Type: {mime or "image/png"}\r\n\r\n'.encode())
        chunks.append(payload); chunks.append(b'\r\n')
    chunks.append(f'--{boundary}--\r\n'.encode())
    body = b''.join(chunks)
    headers = {'Content-Type': f'multipart/form-data; boundary={boundary}', 'Accept':'application/json'}
    try:
        wake_extract_service()
        status, content_type, response_body = fetch_bytes(ORIGINAL_EXTRACT, data=body, headers=headers, timeout=90)
        if 'application/json' in (content_type or ''):
            return status, json.loads(response_body.decode('utf-8'))
    except Exception as error:
        print('proxy extract failed', error)
    return 502, {'error': 'Could not read those screenshots. Use a sharp full itinerary screenshot and tap Analyze again.'}

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PUBLIC), **kwargs)
    def log_message(self, format, *args):
        print('[plus]', self.address_string(), format % args)
    def _json(self, status, payload):
        raw = json.dumps(payload).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers(); self.wfile.write(raw)
    def do_POST(self):
        if self.path == '/api/extract':
            try:
                files = parse_multipart(self)[0].get('images') or []
                if not files:
                    self._json(400, {'error': 'Please upload at least 1 screenshot.'}); return
                if extract_screenshots:
                    status, payload = extract_screenshots(files)
                    if status < 500 or payload.get('itineraries'):
                        self._json(status, payload); return
                    print('local ocr missed', payload)
                status, payload = proxy_extract(files)
                self._json(status, payload)
            except Exception as error:
                print('extract failed', error)
                self._json(502, {'error': 'Could not read those screenshots. Try a sharper PNG or JPG, then tap Analyze again.'})
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
            if not ship_name and not direct_url:
                self._json(400, {'error': 'Enter a ship name or paste an NCL itinerary URL.'}); return
            try:
                official = official_lookup(ship_name, month, year, direct_url)
            except Exception as error:
                print('official lookup failed', error)
                self._json(502, {'error': f'Could not pull sailings from NCL.com: {error}'}); return
            if not official:
                self._json(404, {'error': 'No matching NCL sailings were found for that ship and date.'}); return
            self._json(200, {'source':'ncl.com','queried':{'shipName':ship_name,'month':month,'year':year,'url':direct_url or None},'itineraries':official})
            return
        self.send_error(404, 'Not Found')

def main():
    port = int(os.environ.get('PORT', '3333'))
    server = ThreadingHTTPServer(('0.0.0.0', port), Handler)
    print(f'CruiseNext Studio Plus running on http://0.0.0.0:{port}')
    server.serve_forever()

if __name__ == '__main__':
    main()
