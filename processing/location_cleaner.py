"""Location cleaner and canonicalizer for job postings.

Standardizes locations across all ingestion sources to:
- US: 'City, ST' (e.g. 'Palo Alto, CA', 'New York, NY', 'Austin, TX')
- Canada: 'City, Province, Canada' (e.g. 'Toronto, ON, Canada', 'Calgary, AB, Canada')
- International: 'City, Country' (e.g. 'London, UK', 'Berlin, Germany')
- Remote: 'Remote' or 'Remote in USA'
- Multi-location: 'City, ST, City, ST'
"""

from __future__ import annotations

import re

# 50 US States + DC + PR
US_STATES: dict[str, str] = {
    "alabama": "AL",
    "alaska": "AK",
    "arizona": "AZ",
    "arkansas": "AR",
    "california": "CA",
    "colorado": "CO",
    "connecticut": "CT",
    "delaware": "DE",
    "florida": "FL",
    "georgia": "GA",
    "hawaii": "HI",
    "idaho": "ID",
    "illinois": "IL",
    "indiana": "IN",
    "iowa": "IA",
    "kansas": "KS",
    "kentucky": "KY",
    "louisiana": "LA",
    "maine": "ME",
    "maryland": "MD",
    "massachusetts": "MA",
    "michigan": "MI",
    "minnesota": "MN",
    "mississippi": "MS",
    "missouri": "MO",
    "montana": "MT",
    "nebraska": "NE",
    "nevada": "NV",
    "new hampshire": "NH",
    "new jersey": "NJ",
    "new mexico": "NM",
    "new york": "NY",
    "north carolina": "NC",
    "north dakota": "ND",
    "ohio": "OH",
    "oklahoma": "OK",
    "oregon": "OR",
    "pennsylvania": "PA",
    "rhode island": "RI",
    "south carolina": "SC",
    "south dakota": "SD",
    "tennessee": "TN",
    "texas": "TX",
    "utah": "UT",
    "vermont": "VT",
    "virginia": "VA",
    "washington": "WA",
    "west virginia": "WV",
    "wisconsin": "WI",
    "wyoming": "WY",
    "district of columbia": "DC",
    "puerto rico": "PR",
}
US_STATE_CODES: set[str] = set(US_STATES.values())

# Canadian Provinces & Territories
CANADIAN_PROVINCES: dict[str, str] = {
    "ontario": "ON",
    "quebec": "QC",
    "british columbia": "BC",
    "alberta": "AB",
    "manitoba": "MB",
    "saskatchewan": "SK",
    "nova scotia": "NS",
    "new brunswick": "NB",
    "newfoundland and labrador": "NL",
    "newfoundland": "NL",
    "prince edward island": "PE",
    "northwest territories": "NT",
    "yukon": "YT",
    "nunavut": "NU",
}
CANADIAN_PROVINCE_CODES: set[str] = set(CANADIAN_PROVINCES.values())

# Prominent tech and business hubs mapped to US states
KNOWN_US_CITIES: dict[str, str] = {
    "palo alto": "CA",
    "mountain view": "CA",
    "sunnyvale": "CA",
    "san francisco": "CA",
    "san jose": "CA",
    "los angeles": "CA",
    "san diego": "CA",
    "cupertino": "CA",
    "santa clara": "CA",
    "menlo park": "CA",
    "berkeley": "CA",
    "oakland": "CA",
    "irvine": "CA",
    "fremont": "CA",
    "pasadena": "CA",
    "foster city": "CA",
    "redwood city": "CA",
    "san mateo": "CA",
    "pleasanton": "CA",
    "burbank": "CA",
    "glendale": "CA",
    "south san francisco": "CA",
    "south sf": "CA",
    "seattle": "WA",
    "bellevue": "WA",
    "redmond": "WA",
    "kirkland": "WA",
    "new york": "NY",
    "new york city": "NY",
    "nyc": "NY",
    "brooklyn": "NY",
    "rochester": "NY",
    "yorktown heights": "NY",
    "austin": "TX",
    "dallas": "TX",
    "houston": "TX",
    "plano": "TX",
    "fort worth": "TX",
    "boston": "MA",
    "cambridge": "MA",
    "waltham": "MA",
    "chicago": "IL",
    "oak brook": "IL",
    "rosemont": "IL",
    "champaign": "IL",
    "atlanta": "GA",
    "alpharetta": "GA",
    "laurel": "MD",
    "baltimore": "MD",
    "bethesda": "MD",
    "silver spring": "MD",
    "pittsburgh": "PA",
    "philadelphia": "PA",
    "raleigh": "NC",
    "durham": "NC",
    "charlotte": "NC",
    "greensboro": "NC",
    "edison": "NJ",
    "princeton": "NJ",
    "newark": "NJ",
    "jersey city": "NJ",
    "boise": "ID",
    "denver": "CO",
    "boulder": "CO",
    "centennial": "CO",
    "phoenix": "AZ",
    "tempe": "AZ",
    "scottsdale": "AZ",
    "salt lake city": "UT",
    "lehi": "UT",
    "provo": "UT",
    "portland": "OR",
    "hillsboro": "OR",
    "beaverton": "OR",
    "minneapolis": "MN",
    "st. paul": "MN",
    "saint paul": "MN",
    "detroit": "MI",
    "ann arbor": "MI",
    "southfield": "MI",
    "columbus": "OH",
    "cincinnati": "OH",
    "cleveland": "OH",
    "miami": "FL",
    "tampa": "FL",
    "orlando": "FL",
    "st. petersburg": "FL",
    "st. louis": "MO",
    "saint louis": "MO",
    "kansas city": "MO",
    "madison": "WI",
    "milwaukee": "WI",
    "indianapolis": "IN",
    "louisville": "KY",
    "nashville": "TN",
    "memphis": "TN",
    "washington": "DC",
    "mclean": "VA",
    "reston": "VA",
    "arlington": "VA",
    "east hartford": "CT",
    "wilmington": "DE",
    "birmingham": "AL",
    "marshalltown": "IA",
}

KNOWN_CANADIAN_CITIES: dict[str, str] = {
    "toronto": "ON",
    "waterloo": "ON",
    "ottawa": "ON",
    "markham": "ON",
    "mississauga": "ON",
    "vancouver": "BC",
    "burnaby": "BC",
    "victoria": "BC",
    "montreal": "QC",
    "quebec city": "QC",
    "calgary": "AB",
    "edmonton": "AB",
    "halifax": "NS",
    "cole harbour": "NS",
    "winnipeg": "MB",
}

# Regex to strip facility/building noise, e.g. " (GMD) 1301", " - Main Site", " - Building 4"
FACILITY_NOISE_RE = re.compile(
    r"\s*(?:\([A-Z0-9\s-]+\)\s*\d*|\b(?:main site|building\s*\d+|site\s*\d+|facility|hq)\b.*$)",
    re.IGNORECASE,
)


def _title_case_city(city: str) -> str:
    """Properly title cases city names handling hyphenated and multi-word names."""
    city = city.strip()
    # Handle acronyms
    if city.upper() in ("NYC", "SF", "LA", "DC"):
        return city.upper()
    return " ".join(word.capitalize() for word in city.split())


def clean_single_location(raw: str) -> str:
    """Normalize a single location component into 'City, ST', 'City, Province, Canada', or 'Remote'."""
    text = raw.strip()
    if not text:
        return ""

    # Check for remote patterns
    low = text.lower()
    if low in ("remote", "fully remote", "remote - anywhere"):
        return "Remote"
    if any(k in low for k in ("remote in usa", "us remote", "remote - us", "remote, usa", "remote, us")):
        return "Remote in USA"
    if "remote in canada" in low:
        return "Remote in Canada"

    # Remove internal noise like "(GMD) 1301" or "- Main Site"
    cleaned = FACILITY_NOISE_RE.sub("", text).strip(" -;,")

    # Handle repetitive patterns like "GM Automation - Sunnyvale - GM Automation - Sunnyvale"
    if " - " in cleaned:
        segments = [s.strip() for s in cleaned.split(" - ") if s.strip()]
        for seg in segments:
            # If segment is known city or contains known city
            seg_low = seg.lower()
            for city_key in KNOWN_US_CITIES:
                if city_key == seg_low or f" {city_key} " in f" {seg_low} ":
                    cleaned = city_key.title()
                    break

    # Strip trailing country tags: ", United States", ", USA", ", US"
    country_suffix_re = re.compile(r",\s*(?:United States|USA|U\.S\.A\.|US)$", re.IGNORECASE)
    cleaned = country_suffix_re.sub("", cleaned).strip()

    # Handle Workday reversed format: "USA, CA, Pleasanton" -> "Pleasanton, CA"
    reversed_match = re.match(r"^(?:USA|US),\s*([A-Za-z]{2}),\s*(.+)$", cleaned, re.IGNORECASE)
    if reversed_match:
        state_code, city_part = reversed_match.groups()
        return f"{_title_case_city(city_part)}, {state_code.upper()}"

    # Handle Canada explicit: "Calgary, AB, Canada" -> preserve as "Calgary, AB, Canada"
    canada_match = re.search(r"^(.*?),\s*([A-Za-z]{2}|[A-Za-z\s]+),\s*(?:Canada)$", cleaned, re.IGNORECASE)
    if canada_match:
        city_part, prov_part = canada_match.groups()
        prov_upper = prov_part.strip().upper()
        if prov_upper in CANADIAN_PROVINCE_CODES:
            prov_code = prov_upper
        else:
            prov_code = CANADIAN_PROVINCES.get(prov_part.strip().lower(), prov_upper)
        return f"{_title_case_city(city_part)}, {prov_code}, Canada"

    # Handle Canadian Province without country: "Toronto, Ontario" or "Toronto, ON"
    ca_prov_match = re.match(r"^(.*?),\s*([A-Za-z\s]+)$", cleaned)
    if ca_prov_match:
        city_candidate, prov_candidate = ca_prov_match.groups()
        prov_low = prov_candidate.strip().lower()
        prov_code = CANADIAN_PROVINCES.get(prov_low)
        if prov_code or prov_candidate.strip().upper() in CANADIAN_PROVINCE_CODES:
            code = prov_code or prov_candidate.strip().upper()
            return f"{_title_case_city(city_candidate)}, {code}, Canada"

    # Check for US "City, State" (State can be 2-letter code or full name)
    us_match = re.match(r"^(.*?),\s*([A-Za-z\s]+)$", cleaned)
    if us_match:
        city_part, state_part = us_match.groups()
        state_clean = state_part.strip()
        state_upper = state_clean.upper()
        state_lower = state_clean.lower()

        if state_upper in US_STATE_CODES:
            return f"{_title_case_city(city_part)}, {state_upper}"
        if state_lower in US_STATES:
            return f"{_title_case_city(city_part)}, {US_STATES[state_lower]}"

    # Check single city without state, e.g. "Palo Alto", "Laurel", "Pittsburgh", "ALPHARETTA"
    clean_low = cleaned.lower()
    if clean_low in KNOWN_US_CITIES:
        state_code = KNOWN_US_CITIES[clean_low]
        return f"{_title_case_city(cleaned)}, {state_code}"

    if clean_low in KNOWN_CANADIAN_CITIES:
        prov_code = KNOWN_CANADIAN_CITIES[clean_low]
        return f"{_title_case_city(cleaned)}, {prov_code}, Canada"

    # International City, Country: e.g. "London, UK", "Berlin, Germany", "Dublin, Ireland"
    if "," in cleaned:
        parts = [p.strip() for p in cleaned.split(",") if p.strip()]
        if len(parts) == 2:
            city_part, country_part = parts
            if country_part.lower() in ("uk", "united kingdom"):
                return f"{_title_case_city(city_part)}, UK"
            return f"{_title_case_city(city_part)}, {country_part.title()}"

    return _title_case_city(cleaned)


def split_locations(text: str) -> list[str]:
    """Splits a potentially multi-location string into individual location candidates."""
    # Semicolons or newlines take precedence
    if ";" in text or "\n" in text:
        return [c.strip() for c in re.split(r"[;\n]+", text) if c.strip()]

    parts = [p.strip() for p in text.split(",") if p.strip()]
    if len(parts) <= 2:
        return [text]

    # Single location with country suffix, e.g. "Pleasanton, CA, USA" or "San Jose, California, United States"
    if len(parts) == 3 and parts[2].lower() in ("usa", "united states", "u.s.a.", "us"):
        return [text]

    # Single Workday reversed format: "USA, CA, Pleasanton"
    if len(parts) == 3 and parts[0].lower() in ("usa", "us"):
        return [text]

    # Detect sequence of (city, state) pairs or (city, prov, Canada) triplets
    chunks: list[str] = []
    i = 0
    while i < len(parts):
        # Check triplet for Canada: City, Prov, Canada
        if i + 2 < len(parts) and parts[i + 2].lower() == "canada":
            chunks.append(f"{parts[i]}, {parts[i + 1]}, Canada")
            i += 3
        # Check pair for US or Canada: City, State/Province
        elif i + 1 < len(parts) and (
            parts[i + 1].upper() in US_STATE_CODES
            or parts[i + 1].lower() in US_STATES
            or parts[i + 1].upper() in CANADIAN_PROVINCE_CODES
            or parts[i + 1].lower() in CANADIAN_PROVINCES
        ):
            chunks.append(f"{parts[i]}, {parts[i + 1]}")
            i += 2
        else:
            chunks.append(parts[i])
            i += 1

    return chunks


def normalize_location(raw_location: str | None) -> str | None:
    """
    Normalizes single or multi-location strings into standard formats:
    - US: 'City, ST'
    - Canada: 'City, Province, Canada'
    - International: 'City, Country'
    - Remote: 'Remote' or 'Remote in USA'
    - Multi: Comma-separated normalized locations
    """
    if not raw_location or not str(raw_location).strip():
        return None

    text = str(raw_location).strip()

    # If already a standard Remote label
    if text.lower() in ("remote", "remote in usa"):
        return text

    chunks = split_locations(text)

    # Process all chunks
    results: list[str] = []
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue

        norm = clean_single_location(chunk)
        if norm and norm not in results:
            results.append(norm)

    return ", ".join(results) if results else None
