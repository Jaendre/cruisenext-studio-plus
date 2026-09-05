#!/usr/bin/env python3
"""CruiseNext Itinerary Studio Plus."""
from __future__ import annotations
import json, re, os, email
import html as html_lib
from datetime import datetime, timedelta, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / 'public' if (ROOT / 'public' / 'index.html').exists() else ROOT
ORIGINAL_EXTRACT = 'https://cruisenext-itinerary-studio-multi.onrender.com/api/extract'
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
MONTH_NAMES = ['','January','February','March','April','May','June','July','August','September','October','November','December']

def fetch_bytes(url, data=None, headers=None, timeout=30):
    req = Request(url, data=data, headers={'User-Agent': USER_AGENT, **(headers or {})}, method='POST' if data is not None else 'GET')
    try:
        with urlopen(req, timeout=timeout) as response:
            return response.status, response.headers.get('Content-Type',''), response.read()
    except HTTPError as error:
        body = error.read() if error.fp else b''
        ct = error.headers.get('Content-Type','') if error.headers else ''
        return error.code, ct, body

def fetch_text(url, timeout=30):
    status, _, body = fetch_bytes(url, timeout=timeout)
    if status >= 400:
        raise RuntimeError(f'Fetch failed {status} for {url}')
    return body.decode('utf-8', errors='ignore')

def is_allowed_ncl_url(value):
    try:
        parsed = urlparse(value)
    except Exception:
        return False
    host = (parsed.hostname or '').lower()
    return host in {'www.ncl.com','ncl.com'} and '/cruises/' in ((parsed.path or '') + (parsed.query or ''))

def normalize_ncl_url(value):
    parsed = urlparse(value)
    path = parsed.path or '/'
    if path.startswith('/cruises/') and not path.startswith('/ca/en/'):
        path = '/ca/en' + path
    query = f'?{parsed.query}' if parsed.query else ''
    return f'https://www.ncl.com{path}{query}'

def clean_extracted_url(value):
    return value.replace('&','&').rstrip('",.;').split('"')[0].split('\\u0026')[0]

def search_ncl_pages(ship_name, month, year):
    if not ship_name:
        return []
    month_label = MONTH_NAMES[month] if month else ''
    query = '+'.join(p for p in ['site:ncl.com/cruises', f'"{ship_name}"', month_label, str(year) if year else '', 'itineraryCode'] if p)
    found, seen = [], set()
    for search_url in [f'https://html.duckduckgo.com/html/?q={query}', f'https://www.bing.com/search?q={query}']:
        try:
            html = fetch_text(search_url, timeout=20)
        except Exception as error:
            print('search failed', search_url, error); continue
        raw_links = re.findall(r'https?://(?:www\.)?ncl\.com[^"\'\\s<>]*', html, flags=re.I)
        encoded = []
        for match in re.findall(r'uddg=([^&"]+)', html, flags=re.I):
            try: encoded.append(unquote(match))
            except Exception: pass
        for candidate in raw_links + encoded:
            url = clean_extracted_url(candidate)
            if not is_allowed_ncl_url(url): continue
            normalized = normalize_ncl_url(url)
            if normalized in seen: continue
            seen.add(normalized); found.append(normalized)
        if len(found) >= 6: break
    return found

def decode_entities(value):
    return html_lib.unescape(value)

def extract_ship_name(html, fallback):
    patterns = [r'on Norwegian ([A-Za-z]+)', r'aboard Norwegian ([A-Za-z]+)', r'"name"\s*:\s*"Norwegian ([A-Za-z]+)"', r'Norwegian (Aqua|Aura|Bliss|Breakaway|Dawn|Encore|Epic|Escape|Gem|Getaway|Jade|Jewel|Joy|Luna|Pearl|Prima|Sky|Spirit|Star|Sun|Viva)', r'Pride of America']
    for pattern in patterns:
        match = re.search(pattern, html, flags=re.I)
        if not match: continue
        if re.search(r'Pride of America', match.group(0), flags=re.I):
            return 'Pride of America'
        return 'Norwegian ' + match.group(1)
    return fallback or ''

def iso_from_timestamp(timestamp):
    return datetime.fromtimestamp(int(timestamp)/1000, tz=timezone.utc).strftime('%Y-%m-%d')

def parse_iso(value):
    try:
        return datetime.strptime(value, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    except Exception:
        return None

def add_days(iso_date, amount):
    date = parse_iso(iso_date)
    return iso_date if not date else (date + timedelta(days=amount)).strftime('%Y-%m-%d')

def extract_events(html):
    pattern = re.compile(r'"date":(\d{12,13}),"portCode":"([A-Z0-9]+)","portName":"([^"]+)","portTag":"([^"]*)","event":"([AD])"')
    events, seen = [], set()
    for match in pattern.finditer(html):
        item = {'date': int(match.group(1)), 'portCode': match.group(2), 'portName': decode_entities(match.group(3)), 'event': match.group(5)}
        key = (item['date'], item['portCode'], item['event'])
        if key in seen: continue
        seen.add(key); events.append(item)
    events.sort(key=lambda item: item['date'])
    return events

def extract_cruise_length(html):
    for pat in [r'analyticsProductLength\s*=\s*\[[^\]]*?(\d+)\s*Days', r'(\d+)\s*-\s*day cruise', r'(\d+)\s+Days\.\s*\d+\s+Ports']:
        match = re.search(pat, html, flags=re.I)
        if match: return int(match.group(1))
    return None

def infer_length_from_events(events):
    if len(events) < 2: return 7
    first_iso = iso_from_timestamp(events[0]['date'])
    first_port = events[0]['portName']
    first_date = parse_iso(first_iso)
    for event in events[1:]:
        iso = iso_from_timestamp(event['date']); date = parse_iso(iso)
        if date and first_date and event['portName'] == first_port and (date-first_date).days >= 3:
            return (date-first_date).days
    unique_days = []
    seen=set()
    for event in events:
        iso = iso_from_timestamp(event['date'])
        if iso in seen: continue
        seen.add(iso); unique_days.append(iso)
        if len(unique_days)>16: break
    if len(unique_days)>=2:
        start, end = parse_iso(unique_days[0]), parse_iso(unique_days[min(7,len(unique_days)-1)])
        if start and end: return max((end-start).days, 3)
    return 7

def extract_sail_dates(html, month, year):
    dates=set()
    for match in re.finditer(r'sailDate=(\d{12,13})', html): dates.add(iso_from_timestamp(int(match.group(1))))
    for match in re.finditer(r'"sailDate":(\d{12,13})', html): dates.add(iso_from_timestamp(int(match.group(1))))
    filtered=[]
    for iso in dates:
        date=parse_iso(iso)
        if not date: continue
        if year and date.year!=year: continue
        if month and date.month!=month: continue
        filtered.append(iso)
    return sorted(filtered)

def normalize_ship(value):
    text = re.sub(r'^norwegian\s+', '', value.lower())
    text = re.sub(r'^n\.\s*', '', text)
    return re.sub(r'[^a-z0-9]+', ' ', text).strip()

def ships_match(left, right):
    a, b = normalize_ship(left), normalize_ship(right)
    return True if not a or not b else a in b or b in a

def parse_ncl_itinerary_page(page_url, ship_name, month, year):
    html = decode_entities(fetch_text(page_url, timeout=35))
    resolved_ship = extract_ship_name(html, ship_name)
    if ship_name and resolved_ship and not ships_match(resolved_ship, ship_name):
        return []
    events = extract_events(html)
    if not events:
        raise RuntimeError('No port schedule found on that NCL page.')
    length = max(int(extract_cruise_length(html) or infer_length_from_events(events)), 2)
    ports_by_day = {}
    for event in events:
        ports_by_day.setdefault(iso_from_timestamp(event['date']), event['portName'])
    sail_dates = extract_sail_dates(html, month, year)
    if not sail_dates:
        first_iso = iso_from_timestamp(events[0]['date'])
        sail_dates = [first_iso]
        first_date = parse_iso(first_iso); first_port = events[0]['portName']
        if first_date:
            for event in events[1:]:
                iso = iso_from_timestamp(event['date']); date = parse_iso(iso)
                if date and event['portName']==first_port and (date-first_date).days >= length and iso not in sail_dates:
                    sail_dates.append(iso)
    itineraries=[]
    for start_date in sail_dates:
        date=parse_iso(start_date)
        if not date: continue
        if year and date.year!=year: continue
        if month and date.month!=month: continue
        days=[]
        for index in range(length+1):
            iso=add_days(start_date, index)
            days.append({'day': index+1, 'date': iso, 'place': ports_by_day.get(iso, 'Sea Day')})
        real_ports=[item['place'] for item in days if item['place']!='Sea Day']
        if len(real_ports)<2: continue
        if days[0]['place']=='Sea Day': days[0]['place']=real_ports[0]
        itineraries.append({'ship_name': resolved_ship or ship_name or 'Norwegian', 'start_date': start_date, 'end_date': days[-1]['date'], 'cruise_length': length, 'embark': days[0]['place'], 'disembark': days[-1]['place'], 'days': days, 'source_url': page_url})
    return itineraries

def dedupe_itineraries(items):
    seen, unique=set(), []
    for item in items:
        key=(normalize_ship(item.get('ship_name','')), item.get('start_date'), item.get('end_date'), '|'.join(day.get('place','') for day in item.get('days',[])))
        if key in seen: continue
        seen.add(key); unique.append(item)
    unique.sort(key=lambda item: str(item.get('start_date') or ''))
    return unique

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
            if not name_match: continue
            name = name_match.group(1)
            payload = part.get_payload(decode=True) or b''
            if filename_match:
                files.setdefault(name, []).append((filename_match.group(1), part.get_content_type(), payload))
            else:
                fields[name] = payload.decode('utf-8', errors='ignore')
    return files, fields

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
    status, content_type, response_body = fetch_bytes(ORIGINAL_EXTRACT, data=b''.join(chunks), headers={'Content-Type': f'multipart/form-data; boundary={boundary}', 'Accept':'application/json'}, timeout=120)
    if 'application/json' not in (content_type or ''):
        return 502, {'error': 'Screenshot analysis backend returned an unexpected response. The original extract service may be waking up — try again in a few seconds.'}
    try:
        return status, json.loads(response_body.decode('utf-8'))
    except Exception:
        return 502, {'error': 'Could not parse the screenshot analysis response.'}

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
                status, payload = proxy_extract(files)
                self._json(status, payload)
            except Exception as error:
                print('extract proxy failed', error)
                self._json(502, {'error': 'Could not reach the screenshot analysis backend. NCL lookup still works without screenshots.'})
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
            page_urls, seen = [], set()
            if direct_url:
                if not is_allowed_ncl_url(direct_url):
                    self._json(400, {'error': 'That URL is not an ncl.com itinerary page.'}); return
                normalized = normalize_ncl_url(direct_url)
                page_urls.append(normalized); seen.add(normalized)
            try:
                discovered = search_ncl_pages(ship_name, month, year)
            except Exception as error:
                discovered=[]; print('search error', error)
            for url in discovered:
                if url not in seen:
                    seen.add(url); page_urls.append(url)
            if not page_urls:
                self._json(404, {'error': 'No public NCL.com itinerary pages were found for that ship and date.'}); return
            itineraries, errors = [], []
            for url in page_urls[:8]:
                try: itineraries.extend(parse_ncl_itinerary_page(url, ship_name, month, year))
                except Exception as error: errors.append(f'{url}: {error}')
            unique = dedupe_itineraries(itineraries)
            if not unique:
                self._json(404, {'error': 'Found NCL pages, but could not convert them into itinerary templates.', 'details': errors[:4]}); return
            self._json(200, {'source':'ncl.com','queried':{'shipName':ship_name,'month':month,'year':year,'url':direct_url or None},'pages':page_urls[:8],'itineraries':unique})
            return
        self.send_error(404, 'Not Found')

def main():
    port = int(os.environ.get('PORT', '3333'))
    server = ThreadingHTTPServer(('0.0.0.0', port), Handler)
    print(f'CruiseNext Studio Plus running on http://0.0.0.0:{port}')
    server.serve_forever()

if __name__ == '__main__':
    main()
