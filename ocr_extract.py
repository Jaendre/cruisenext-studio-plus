"""Read itinerary screenshots with local OCR."""
from __future__ import annotations
import io, re
from datetime import datetime, timedelta
from PIL import Image
import pytesseract

SHIP_NAMES = ["Pride of America","Norwegian Aqua","Norwegian Aura","Norwegian Bliss","Norwegian Breakaway","Norwegian Dawn","Norwegian Encore","Norwegian Epic","Norwegian Escape","Norwegian Gem","Norwegian Getaway","Norwegian Jade","Norwegian Jewel","Norwegian Joy","Norwegian Luna","Norwegian Pearl","Norwegian Prima","Norwegian Sky","Norwegian Spirit","Norwegian Star","Norwegian Sun","Norwegian Viva"]
MONTHS = {"jan":1,"january":1,"feb":2,"february":2,"mar":3,"march":3,"apr":4,"april":4,"may":5,"jun":6,"june":6,"jul":7,"july":7,"aug":8,"august":8,"sep":9,"sept":9,"september":9,"oct":10,"october":10,"nov":11,"november":11,"dec":12,"december":12}

def _ocr_image(payload):
    image = Image.open(io.BytesIO(payload))
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    if min(image.size) < 900:
        scale = max(1, int(900 / max(min(image.size), 1)))
        image = image.resize((image.width * scale, image.height * scale), Image.Resampling.LANCZOS)
    return pytesseract.image_to_string(image).replace("\r", "\n")

def _clean_place(value):
    text = re.sub(r"\s+", " ", value or "").strip(" .-|:;,")
    text = re.sub(r"^(arrives?|departs?|dock|tender)\s+", "", text, flags=re.I)
    if re.search(r"\b(at sea|sea day|cruising|day at sea)\b", text, flags=re.I):
        return "Sea Day"
    return text

def _find_ship(text):
    lowered = text.lower()
    for name in SHIP_NAMES:
        if name.lower() in lowered:
            return name
    match = re.search(r"\bN(?:orwegian)?\.?\s+([A-Z][a-z]+)\b", text)
    return "Norwegian " + match.group(1) if match else "Norwegian"

def _parse_dates(text):
    dates, seen = [], set()
    def add(year, month, day):
        try:
            iso = datetime(int(year), int(month), int(day)).strftime("%Y-%m-%d")
        except Exception:
            return
        if iso not in seen:
            seen.add(iso); dates.append(iso)
    for match in re.finditer(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b", text):
        add(match.group(1), match.group(2), match.group(3))
    for match in re.finditer(r"\b(\d{1,2})\s+([A-Za-z]{3,9})\s+(20\d{2})\b", text):
        month = MONTHS.get(match.group(2).lower())
        if month: add(match.group(3), month, match.group(1))
    for match in re.finditer(r"\b([A-Za-z]{3,9})\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(20\d{2})\b", text):
        month = MONTHS.get(match.group(1).lower())
        if month: add(match.group(3), month, match.group(2))
    return dates

def _parse_day_rows(text):
    rows = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line: continue
        match = re.match(r"^(?:day\s*)?(\d{1,2})\s*(?:[-.:)|]|\u2013|\u2014)\s+(.+)$", line, flags=re.I)
        if not match:
            match = re.match(r"^day\s+(\d{1,2})\s+(.+)$", line, flags=re.I)
        if not match: continue
        day = int(match.group(1))
        place = _clean_place(match.group(2))
        if day < 1 or day > 30 or not place or len(place) < 3: continue
        if re.search(r"\b(price|usd|gbp|guest|balcony)\b", place, flags=re.I): continue
        rows.append((day, place))
    unique, seen = [], set()
    for day, place in rows:
        if day in seen: continue
        seen.add(day); unique.append((day, place))
    unique.sort(key=lambda item: item[0])
    return unique

def _build_itinerary(text, source_name):
    rows = _parse_day_rows(text)
    dates = _parse_dates(text)
    ship = _find_ship(text)
    if len(rows) < 2:
        return None
    start = dates[0] if dates else None
    first_day = rows[0][0]
    offset = first_day - 1 if first_day in (0, 1) else 0
    by_day = {max(1, day - offset): place for day, place in rows}
    if 1 not in by_day:
        by_day[1] = rows[0][1]
    max_day = max(by_day)
    days = []
    for index in range(1, max_day + 1):
        iso = ""
        if start:
            iso = (datetime.strptime(start, "%Y-%m-%d") + timedelta(days=index - 1)).strftime("%Y-%m-%d")
        days.append({"day": index, "date": iso, "place": by_day.get(index, "Sea Day")})
    return {"ship_name": ship, "start_date": start or "", "end_date": days[-1]["date"] or start or "", "cruise_length": max(max_day - 1, 1), "embark": days[0]["place"], "disembark": days[-1]["place"], "days": days, "source_url": source_name}

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
