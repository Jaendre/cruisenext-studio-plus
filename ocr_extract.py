"""Read CWEB itinerary screenshots with local OCR."""
from __future__ import annotations
import io, re
from datetime import datetime, timedelta
from PIL import Image, ImageOps
import pytesseract

SHIP_NAMES = ["Pride of America","Norwegian Aqua","Norwegian Aura","Norwegian Bliss","Norwegian Breakaway","Norwegian Dawn","Norwegian Encore","Norwegian Epic","Norwegian Escape","Norwegian Gem","Norwegian Getaway","Norwegian Jade","Norwegian Jewel","Norwegian Joy","Norwegian Luna","Norwegian Pearl","Norwegian Prima","Norwegian Sky","Norwegian Spirit","Norwegian Star","Norwegian Sun","Norwegian Viva"]
ACTIVITY = r"(?:ARRIVE(?:-|\s)?(?:DOCK|TENDER)?|DEPART(?:URE)?|CRUISE|AT\s*SEA|SEA\s*DAY)"
DATE_US = re.compile(r"\b(\d{1,2})/(\d{1,2})/(20\d{2})\b")
DATE_ISO = re.compile(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b")
CWEB_LINE = re.compile(rf"(?:Sun|Mon|Tue|Wed|Thu|Fri|Sat|Sunday|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday)\s+(\d{{1,2}}/\d{{1,2}}/20\d{{2}})\s+(?:\d{{1,2}}:\d{{2}}\s*(?:AM|PM)\s+)?({ACTIVITY})\s+(.+)$", flags=re.I)
LOOSE_CWEB = re.compile(rf"(\d{{1,2}}/\d{{1,2}}/20\d{{2}})\s+(?:\d{{1,2}}:\d{{2}}\s*(?:AM|PM)\s+)?({ACTIVITY})\s+(.+)$", flags=re.I)
DAY_LINE = re.compile(r"^(?:day\s*)?(\d{1,2})\s*(?:[-.:)|]|\u2013|\u2014)\s+(.+)$", flags=re.I)

def _ocr_image(payload):
    image = Image.open(io.BytesIO(payload))
    image = ImageOps.exif_transpose(image)
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    if image.width < 1400:
        scale = max(2, int(1600 / max(image.width, 1)))
        image = image.resize((image.width * scale, image.height * scale), Image.Resampling.LANCZOS)
    gray = ImageOps.autocontrast(image.convert("L"))
    return pytesseract.image_to_string(gray, config="--psm 6").replace("\r", "\n")

def _title_port(value):
    text = re.sub(r"\s+", " ", value or "").strip(" .-|:;,")
    text = re.sub(r"\b(SPAIN|FRANCE|ITALY|GREECE|PORTUGAL|COUNTRY)\b", "", text, flags=re.I).strip(" .-|" )
    if not text or re.fullmatch(r"\(none\)|none|-|n/?a", text, flags=re.I):
        return "Sea Day"
    if re.search(r"\b(at sea|sea day|cruise|cruising)\b", text, flags=re.I):
        return "Sea Day"
    parts = []
    for token in re.split(r"(\s+|/|\(|\))", text):
        if re.fullmatch(r"\s+|/|\(|\)", token or ""):
            parts.append(token)
        elif token:
            parts.append(token.capitalize() if token.isupper() or token.islower() else token)
    return re.sub(r"\s+", " ", "".join(parts)).strip(" /") or "Sea Day"

def _parse_us_date(value):
    match = DATE_US.search(value or "")
    if not match:
        return None
    month, day, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
    try:
        return datetime(year, month, day).strftime("%Y-%m-%d")
    except Exception:
        try:
            return datetime(year, day, month).strftime("%Y-%m-%d")
        except Exception:
            return None

def _find_ship(text):
    lowered = text.lower()
    for name in SHIP_NAMES:
        if name.lower() in lowered:
            return name
    match = re.search(r"\bN(?:orwegian)?\.?\s+([A-Z][a-z]+)\b", text)
    return "Norwegian " + match.group(1) if match else "Norwegian"

def _parse_cweb_rows(text):
    rows = []
    for raw in text.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if not line or re.search(r"port of call|activity|country", line, flags=re.I):
            continue
        match = CWEB_LINE.search(line) or LOOSE_CWEB.search(line)
        if not match:
            continue
        iso = _parse_us_date(match.group(1))
        if not iso:
            continue
        activity = match.group(2).upper()
        port = _title_port(match.group(3))
        if "CRUISE" in activity or "SEA" in activity:
            port = "Sea Day"
        rows.append({"date": iso, "activity": activity, "place": port})
    return rows

def _rows_to_itinerary(rows, ship, source_name):
    if not rows:
        return None
    by_date = {}
    for row in rows:
        current = by_date.get(row["date"])
        if current is None or (current == "Sea Day" and row["place"] != "Sea Day"):
            by_date[row["date"]] = row["place"]
    dates = sorted(by_date)
    start = datetime.strptime(dates[0], "%Y-%m-%d")
    end = datetime.strptime(dates[-1], "%Y-%m-%d")
    days, cursor, index = [], start, 1
    while cursor <= end:
        iso = cursor.strftime("%Y-%m-%d")
        days.append({"day": index, "date": iso, "place": by_date.get(iso, "Sea Day")})
        cursor += timedelta(days=1)
        index += 1
    if days and days[0]["place"] == "Sea Day":
        first_port = next((item["place"] for item in days if item["place"] != "Sea Day"), "Sea Day")
        days[0]["place"] = first_port
    return {"ship_name": ship, "start_date": days[0]["date"], "end_date": days[-1]["date"], "cruise_length": (end-start).days or max(len(days)-1,1), "embark": days[0]["place"], "disembark": days[-1]["place"], "days": days, "source_url": source_name}

def _parse_day_number_rows(text):
    rows = []
    for raw in text.splitlines():
        match = DAY_LINE.match(raw.strip()) or re.match(r"^day\s+(\d{1,2})\s+(.+)$", raw.strip(), flags=re.I)
        if not match:
            continue
        day = int(match.group(1))
        place = _title_port(match.group(2))
        if 1 <= day <= 30 and place:
            rows.append((day, place))
    unique, seen = [], set()
    for day, place in rows:
        if day in seen: continue
        seen.add(day); unique.append((day, place))
    return sorted(unique)

def _day_number_itinerary(text, ship, source_name):
    numbered = _parse_day_number_rows(text)
    if len(numbered) < 2:
        return None
    start = _parse_us_date(text)
    max_day = max(day for day,_ in numbered)
    by_day = dict(numbered)
    days = []
    for index in range(1, max_day+1):
        iso = (datetime.strptime(start, "%Y-%m-%d") + timedelta(days=index-1)).strftime("%Y-%m-%d") if start else ""
        days.append({"day": index, "date": iso, "place": by_day.get(index, "Sea Day")})
    return {"ship_name": ship, "start_date": start or "", "end_date": days[-1]["date"], "cruise_length": max(max_day-1,1), "embark": days[0]["place"], "disembark": days[-1]["place"], "days": days, "source_url": source_name}

def _build_itinerary(text, source_name):
    ship = _find_ship(text)
    built = _rows_to_itinerary(_parse_cweb_rows(text), ship, source_name)
    return built or _day_number_itinerary(text, ship, source_name)

def extract_screenshots(files):
    itineraries, errors = [], []
    for index, (filename, _mime, payload) in enumerate(files, start=1):
        label = filename or f"screenshot {index}"
        try:
            text = _ocr_image(payload)
        except Exception as error:
            errors.append(f"{label}: could not read image ({error})")
            continue
        itinerary = _build_itinerary(text, label)
        if not itinerary:
            errors.append(f"No valid itinerary rows were read from {label}.")
            continue
        itineraries.append(itinerary)
    if not itineraries:
        return 500, {"error": errors[0] if errors else "No valid itinerary rows were read from those screenshots."}
    return 200, {"itineraries": itineraries, "warnings": errors}
