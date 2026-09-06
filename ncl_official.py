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
SHIP_CODES = {'aqua':'AQUA','aura':'AURA','bliss':'BLISS','breakaway':'BREAKAWAY','dawn':'DAWN','encore':'ENCORE','epic':'EPIC','escape':'ESCAPE','gem':'GEM','getaway':'GETAWAY','jade':'JADE','jewel':'JEWEL','joy':'JOY','luna':'LUNA','pearl':'PEARL','prima':'PRIMA','sky':'SKY','spirit':'SPIRIT','star':'STAR','sun':'SUN','viva':'VIVA','pride of america':'PRIDE_AMER','pride america':'PRIDE_AMER','pride_amer':'PRIDE_AMER'}
MONTH_ABBR = ['','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

def _get_json(url, timeout=35):
    req = Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'})
    try:
        with urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode('utf-8', errors='ignore'))
    except HTTPError as error:
        raise RuntimeError(f'NCL API {error.code} for {url}') from error

def _norm_ship(name):
    text = re.sub(r'^norwegian\s+', '', (name or '').strip(), flags=re.I)
    text = re.sub(r'^n\.\s*', '', text, flags=re.I)
    text = re.sub(r'^pride\s+of\s+', 'pride of ', text, flags=re.I)
    return re.sub(r'[^a-z ]+', ' ', text.lower()).strip()

def ship_code_from_name(name):
    text = _norm_ship(name)
    if not text:
        return ''
    if text in SHIP_CODES:
        return SHIP_CODES[text]
    token = text.split()[-1]
    token_matches = [code for key, code in SHIP_CODES.items() if key.split()[-1] == token]
    if len(token_matches) == 1:
        return token_matches[0]
    return ''

def ship_title_matches(requested, actual):
    req = _norm_ship(requested)
    act = _norm_ship(actual)
    if not req:
        return True
    if not act:
        return False
    return req == act or req in act or act in req

def is_cruise_tour(meta):
    blob = ' '.join([
        str(meta.get('code') or ''),
        str(meta.get('title') or ''),
        str(meta.get('bundleType') or ''),
        str(meta.get('objectId') or ''),
        str((meta.get('duration') or {}).get('text') or ''),
    ]).upper()
    bundle = str(meta.get('bundleType') or '').lower()
    if bundle in {'cruiselandtour', 'cruisetour', 'landtour'}:
        return True
    return any(token in blob for token in ('CRUISETOUR', 'CRUISE TOUR', 'CRUISELANDTOUR', 'LAND TOUR'))

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

def official_lookup(ship_name, month, year, url='', destination='', query=''):
    code_from_url = itinerary_code_from_url(url)
    ship_code = ship_code_from_name(ship_name)
    params = {'limit': 40, 'offset': 0}
    if ship_code:
        params['ships'] = ship_code
    dates = _dates_param(month, year)
    if dates:
        params['dates'] = dates
    dest_code = str(destination or '').strip().upper().replace(' ', '_')
    if dest_code in {'CANADA_NEW_ENGLAND', 'CANADA'}:
        dest_code = 'CANADA_NEW_ENGL'
    if dest_code:
        params['destinations'] = dest_code
    query_text = str(query or '').strip()
    if query_text:
        params['query'] = query_text
    if code_from_url:
        params['itineraryCodes'] = code_from_url
    if not ship_code and not code_from_url and not dest_code and not query_text:
        return []
    search = _get_json(SEARCH_URL + '?' + urlencode(params))
    itineraries_meta = search.get('itineraries') or []
    if not itineraries_meta and dates:
        params.pop('dates', None)
        search = _get_json(SEARCH_URL + '?' + urlencode(params))
        itineraries_meta = search.get('itineraries') or []
    itineraries_meta = [meta for meta in itineraries_meta if not is_cruise_tour(meta)]
    results = []
    for meta in itineraries_meta[:20]:
        code = meta.get('code') or code_from_url
        if not code:
            continue
        package_id = meta.get('packageId') or ''
        ship_title = ((meta.get('ship') or {}).get('title')) or ship_name or 'Norwegian'
        if ship_name and not ship_title_matches(ship_name, ship_title):
            continue
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
