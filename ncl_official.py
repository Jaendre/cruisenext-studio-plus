"""Pull itineraries from NCL public vacations JSON APIs."""
from __future__ import annotations
import json, re
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
SEARCH_URL = 'https://www.ncl.com/api/v2/vacations/search'
SAILINGS_URL = 'https://www.ncl.com/api/vacations/sailings/'
EVENTS_URL = 'https://www.ncl.com/api/vacations/events/'
SHIP_CODES = {'aqua':'AQUA','aura':'AURA','bliss':'BLISS','breakaway':'BREAKAWAY','dawn':'DAWN','encore':'ENCORE','epic':'EPIC','escape':'ESCAPE','gem':'GEM','getaway':'GETAWAY','jade':'JADE','jewel':'JEWEL','joy':'JOY','luna':'LUNA','pearl':'PEARL','prima':'PRIMA','sky':'SKY','spirit':'SPIRIT','star':'STAR','sun':'SUN','viva':'VIVA','pride of america':'PRIDEAMER','pride america':'PRIDEAMER'}
MONTH_ABBR = ['','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

def _get_json(url, timeout=35):
    req = Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'})
    try:
        with urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode('utf-8', errors='ignore'))
    except HTTPError as error:
        raise RuntimeError(f'NCL API {error.code} for {url}') from error

def ship_code_from_name(name):
    text = re.sub(r'^norwegian\s+', '', (name or '').strip(), flags=re.I)
    text = re.sub(r'^n\.\s*', '', text, flags=re.I).strip().lower()
    text = re.sub(r'[^a-z ]+', ' ', text).strip()
    if text in SHIP_CODES:
        return SHIP_CODES[text]
    for key, code in SHIP_CODES.items():
        if key in text or text in key:
            return code
    return text.upper().replace(' ', '') if text else ''

def itinerary_code_from_url(url):
    if not url:
        return ''
    qs = parse_qs(urlparse(url).query)
    if qs.get('itineraryCode'):
        return qs['itineraryCode'][0]
    match = re.search(r'itineraryCode=([A-Z0-9]+)', url, flags=re.I)
    return match.group(1) if match else ''

def _dates_param(month, year):
    if month and year:
        return f'{MONTH_ABBR[int(month)]}-{int(year)}'
    return ''

def _place(event):
    title = (event.get('title') or event.get('name') or '').strip()
    kind = (event.get('event') or '').upper()
    if kind in {'AT_SEA', 'SEA', 'CRUISING'} or re.search(r'\bat sea\b', title, flags=re.I):
        return 'Sea Day'
    return title or 'Sea Day'

def template_days_from_events(events, length):
    by_day = {}
    for event in events or []:
        day = int(event.get('relativeCalendarDay') or event.get('cruisingDay') or 0)
        if day < 1:
            continue
        place = _place(event)
        if day not in by_day or place != 'Sea Day':
            by_day[day] = place
    advertised = int(length or 0) or max(by_day or [7])
    span = max(max(by_day or [advertised]), advertised + 1)
    days = [{'day': day, 'place': by_day.get(day, 'Sea Day')} for day in range(1, span + 1)]
    if advertised:
        days = days[: advertised + 1]
        if days and days[-1]['place'] == 'Sea Day':
            days[-1]['place'] = days[0]['place']
    return days, advertised

def apply_start_date(template, start_date):
    start = datetime.strptime(start_date[:10], '%Y-%m-%d')
    days = []
    for item in template:
        iso = (start + timedelta(days=item['day'] - 1)).strftime('%Y-%m-%d')
        days.append({'day': item['day'], 'date': iso, 'place': item['place']})
    return days

def sailing_starts(code, month, year):
    data = _get_json(SAILINGS_URL + code)
    dates, seen = [], set()
    for room in data.get('pricingStateRooms') or []:
        raw = (room.get('sailStartDate') or room.get('vacationStartDate') or '')[:10]
        if not raw or raw in seen:
            continue
        try:
            parsed = datetime.strptime(raw, '%Y-%m-%d')
        except Exception:
            continue
        if year and parsed.year != int(year):
            continue
        if month and parsed.month != int(month):
            continue
        seen.add(raw); dates.append(raw)
    return sorted(dates)

def official_lookup(ship_name, month, year, url=''):
    code_from_url = itinerary_code_from_url(url)
    ship_code = ship_code_from_name(ship_name)
    params = {'limit': 40, 'offset': 0}
    if ship_code:
        params['ships'] = ship_code
    dates = _dates_param(month, year)
    if dates:
        params['dates'] = dates
    if code_from_url:
        params['itineraryCodes'] = code_from_url
    if not ship_code and not code_from_url:
        return []
    search = _get_json(SEARCH_URL + '?' + urlencode(params))
    itineraries_meta = search.get('itineraries') or []
    if not itineraries_meta and dates:
        params.pop('dates', None)
        search = _get_json(SEARCH_URL + '?' + urlencode(params))
        itineraries_meta = search.get('itineraries') or []
    results = []
    for meta in itineraries_meta[:20]:
        code = meta.get('code') or code_from_url
        if not code:
            continue
        package_id = meta.get('packageId') or ''
        ship_title = ((meta.get('ship') or {}).get('title')) or ship_name or 'Norwegian'
        length = ((meta.get('duration') or {}).get('days')) or 7
        try:
            detail = _get_json(f'{EVENTS_URL}{code}/package/{package_id}') if package_id else {'events': []}
        except Exception as error:
            print('events failed', code, error); detail = {'events': []}
        template, length = template_days_from_events(detail.get('events') or [], length)
        if len([d for d in template if d['place'] != 'Sea Day']) < 2:
            embark = ((meta.get('embarkationPort') or {}).get('title')) or 'Embark'
            disembark = ((meta.get('disembarkationPort') or {}).get('title')) or embark
            mid = [p.get('title') for p in (meta.get('portsOfCall') or []) if p.get('title')]
            template = [{'day': 1, 'place': embark}]
            for index, port in enumerate(mid, start=2):
                template.append({'day': index, 'place': port})
            while len(template) < int(length):
                template.append({'day': len(template) + 1, 'place': 'Sea Day'})
            template.append({'day': int(length) + 1, 'place': disembark})
        try:
            starts = sailing_starts(code, month, year)
        except Exception as error:
            print('sailings failed', code, error); starts = []
        if not starts:
            continue
        source = f'https://www.ncl.com/vacations?itineraryCodes={code}'
        for start in starts:
            days = apply_start_date(template, start)
            if days[0]['place'] == 'Sea Day':
                days[0]['place'] = ((meta.get('embarkationPort') or {}).get('title')) or days[0]['place']
            results.append({'ship_name': ship_title, 'start_date': days[0]['date'], 'end_date': days[-1]['date'], 'cruise_length': int(length), 'embark': days[0]['place'], 'disembark': days[-1]['place'], 'days': days, 'source_url': source})
    return results
