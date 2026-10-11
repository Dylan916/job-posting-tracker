"""Extractor and canonicalizer for job postings from Instagram story links.

Includes:
1. URL canonicalization and tracking parameter removal.
2. ATS requisition ID extraction for smart repost detection.
3. Tier 1: Fast HTML / OpenGraph / Schema.org job metadata parser.
4. Tier 2: Gemini 2.0 Flash Vision fallback for protected or image-only job stories.
"""

import html
import json
import os
import re
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse, urlunparse

from bs4 import BeautifulSoup
import httpx
from rich.console import Console

console = Console()

# Tracking query parameters to strip from destination URLs
TRACKING_PARAMS = {
    "igshid",
    "fbclid",
    "ref",
    "gh_src",
    "source",
    "_hsenc",
    "_hsmi",
    "mkt_tok",
    "e",
}


# Regex to detect terms / seasons
TERM_PATTERN = re.compile(
    r"\b(Summer|Fall|Spring|Winter)\s+202\d|\b202\d\s+New\s+Grad|\bNew\s+Grad(?:uate)?\s+202\d|\bEarly\s+Career\s+202\d",
    re.IGNORECASE,
)

# Common ATS requisition ID patterns
REQUISITION_PATTERNS = [
    re.compile(r"/jobs/(\d+)", re.IGNORECASE),                               # Greenhouse: /jobs/5581920
    re.compile(r"/([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"), # Lever/Ashby UUID
    re.compile(r"/job/[^/]+/([a-zA-Z0-9_\-]+)", re.IGNORECASE),              # Workday: /job/Palo-Alto/Software-Engineer_JR1024
    re.compile(r"/(?:requisitions?|openings?)/([a-zA-Z0-9_\-]+)", re.IGNORECASE),
    re.compile(r"/jobs/([a-zA-Z0-9_\-]+)", re.IGNORECASE),                  # Generic careers: /jobs/ai-ml-intern-123
]


def canonicalize_url(url: str) -> str:
    """
    Unwraps Instagram redirect links and strips all UTM/tracking parameters.
    Example:
        https://l.instagram.com/?u=https%3A%2F%2Fcareers.rivian.com%2Fjobs%2F123%3Futm_source%3Dig
        -> https://careers.rivian.com/jobs/123
    """
    if not url:
        return ""

    parsed = urlparse(url)

    # Unwrap Instagram redirect link wrapper if present
    if "instagram.com" in parsed.netloc and parsed.path.startswith("/"):
        query_params = parse_qs(parsed.query)
        if "u" in query_params:
            unwrapped = unquote(query_params["u"][0])
            parsed = urlparse(unwrapped)

    # Strip tracking parameters from query string
    filtered_query_pairs = []
    if parsed.query:
        for param in parsed.query.split("&"):
            key = param.split("=")[0].lower()
            if key not in TRACKING_PARAMS and not key.startswith("utm_"):
                filtered_query_pairs.append(param)

    clean_query = "&".join(filtered_query_pairs)
    clean_path = parsed.path.rstrip("/") if parsed.path != "/" else "/"


    return urlunparse((parsed.scheme, parsed.netloc, clean_path, "", clean_query, ""))


def extract_requisition_id(url: str) -> str | None:
    """
    Extracts the unique requisition or job ID from a job posting URL.
    Returns None if no specific ID pattern matches.
    """
    clean_url = canonicalize_url(url)
    path = urlparse(clean_url).path

    for pattern in REQUISITION_PATTERNS:
        match = pattern.search(path)
        if match:
            return match.group(1)

    return None


def extract_terms_from_text(text: str) -> list[str]:
    """Extract seasons and graduation years e.g. ['Summer 2027']."""
    if not text:
        return []
    matches = [m.group(0) for m in TERM_PATTERN.finditer(text)]
    # Deduplicate while preserving order
    seen = set()
    results = []
    for m in matches:
        clean = m.strip().title()
        if clean not in seen:
            seen.add(clean)
            results.append(clean)
    return results



def split_company_and_title(raw_title: str) -> tuple[str, str]:
    """
    Intelligently splits page titles like:
    - 'Software Engineer Intern - Rivian' -> ('Rivian', 'Software Engineer Intern')
    - 'Datadog Careers | Software Engineer Intern' -> ('Datadog', 'Software Engineer Intern')
    - 'Intern at Stripe' -> ('Stripe', 'Intern')
    """
    if not raw_title:
        return "", ""

    cleaned = raw_title.strip()
    delimiters = [" | ", " - ", " – ", " — ", " at "]

    for delim in delimiters:
        if delim in cleaned:
            parts = [p.strip() for p in cleaned.split(delim) if p.strip()]
            if len(parts) >= 2:
                # Heuristic: the shorter part containing 'Careers' or recognizable name is usually company
                p0, p1 = parts[0], parts[1]
                if any(k in p0.lower() for k in ("intern", "engineer", "analyst", "co-op", "developer")):
                    company = p1.replace("Careers", "").strip()
                    title = p0
                    return company, title
                else:
                    company = p0.replace("Careers", "").strip()
                    title = p1
                    return company, title

    return "", cleaned


def extract_company_from_url(url: str) -> str | None:
    """Extract company name from well-known ATS domain structures."""
    if not url:
        return None
    parsed = urlparse(url)
    netloc = parsed.netloc.lower()
    path_parts = [p for p in parsed.path.split("/") if p]

    # Greenhouse: boards.greenhouse.io/<company> or job-boards.greenhouse.io/<company>
    if "greenhouse.io" in netloc and path_parts:
        return path_parts[0].capitalize()

    # Lever: jobs.lever.co/<company>
    if "lever.co" in netloc and path_parts:
        return path_parts[0].capitalize()

    # Ashby: jobs.ashbyhq.com/<company>
    if "ashbyhq.com" in netloc and path_parts:
        return path_parts[0].capitalize()

    # Workday: <company>.wd1.myworkdayjobs.com
    if "myworkdayjobs.com" in netloc:
        return netloc.split(".")[0].capitalize()

    # Careers subdomains: careers.rivian.com -> Rivian
    if netloc.startswith("careers."):
        domain_parts = netloc.split(".")
        if len(domain_parts) >= 3:
            return domain_parts[1].capitalize()

    return None



def extract_degrees_from_text(text: str) -> list[str]:
    """Extract degree levels mentioned in job requirements/title."""
    if not text:
        return ["Bachelor's"]
    degrees: list[str] = []
    text_lower = text.lower()

    if re.search(r"\b(phd|doctorat|doctor of philosophy)\b", text_lower):
        degrees.append("PhD")
    if re.search(r"\b(master'?s|ms|m\.s\.|mba|graduate student)\b", text_lower):
        degrees.append("Master's")
    if re.search(r"\b(bachelor'?s|bs|b\.s\.|ba|undergraduate)\b", text_lower):
        degrees.append("Bachelor's")

    # If neither was found, default to Bachelor's unless title clearly indicates advanced degree
    if not degrees:
        if "intern" in text_lower or "early career" in text_lower:
            degrees.append("Bachelor's")

    return degrees


def extract_from_webpage(url: str, client: httpx.Client | None = None) -> dict[str, Any] | None:
    """
    Tier 1: Fetch job posting HTML and parse Schema.org JSON-LD and OpenGraph tags.
    Fast, reliable, and uses zero AI tokens.
    """
    clean_url = canonicalize_url(url)
    if not clean_url:
        return None

    http = client or httpx.Client(
        timeout=10.0,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        follow_redirects=True,
    )

    try:
        response = http.get(clean_url)
        if response.status_code >= 400:
            console.print(f"[dim yellow]Webpage returned HTTP {response.status_code} for {clean_url}[/]")
            return None

        soup = BeautifulSoup(response.text, "html.parser")

        # 1. Check for standard JobPosting JSON-LD
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "{}")
                # Handle direct object or @graph list
                items = data.get("@graph", [data]) if isinstance(data, dict) else (data if isinstance(data, list) else [])
                for item in items:
                    if isinstance(item, dict) and item.get("@type") == "JobPosting":
                        title = str(item.get("title") or "").strip()
                        org = item.get("hiringOrganization")
                        company = (org.get("name") if isinstance(org, dict) else str(org or "")).strip()

                        loc = item.get("jobLocation")
                        location = ""
                        if isinstance(loc, dict):
                            addr = loc.get("address", {})
                            if isinstance(addr, dict):
                                location = addr.get("addressLocality") or addr.get("addressRegion") or ""
                        elif isinstance(loc, list) and loc:
                            first_addr = loc[0].get("address", {}) if isinstance(loc[0], dict) else {}
                            location = first_addr.get("addressLocality") or ""

                        description_text = str(item.get("description", ""))
                        terms = extract_terms_from_text(title + " " + description_text)
                        degrees = extract_degrees_from_text(title + " " + description_text)
                        is_remote = "remote" in title.lower() or str(item.get("jobLocationType", "")).lower() == "telecommute"

                        company = html.unescape(company)
                        title = html.unescape(title)

                        return {
                            "company": company,
                            "title": title,
                            "location": location or None,
                            "terms": terms,
                            "degrees": degrees,
                            "is_remote": is_remote,
                            "url": str(response.url),
                            "requisition_id": extract_requisition_id(str(response.url)),
                            "method": "schema_org",
                        }

            except Exception:
                continue

        # 2. Fallback to OpenGraph / Meta Title
        og_title = soup.find("meta", property="og:title")
        raw_title = og_title["content"] if og_title and og_title.get("content") else ""
        if not raw_title and soup.title and soup.title.string:
            raw_title = soup.title.string

        og_site = soup.find("meta", property="og:site_name")
        site_name = og_site["content"].strip() if og_site and og_site.get("content") else ""

        company, title = split_company_and_title(raw_title)
        if site_name and (not company or len(site_name) < len(company)):
            company = site_name

        if not company or company == "Unknown Company":
            url_company = extract_company_from_url(str(response.url))
            if url_company:
                company = url_company

        if title:
            page_text = soup.get_text()[:4000]
            terms = extract_terms_from_text(title + " " + page_text)
            degrees = extract_degrees_from_text(title + " " + page_text)
            return {
                "company": company or "Unknown Company",
                "title": title,
                "location": None,
                "terms": terms,
                "degrees": degrees,
                "is_remote": "remote" in title.lower(),
                "url": str(response.url),
                "requisition_id": extract_requisition_id(str(response.url)),
                "method": "opengraph",
            }



    except Exception as exc:
        console.print(f"[dim yellow]Direct webpage parsing failed for {clean_url}: {exc}[/]")

    return None


def extract_with_gemini_vision(
    image_url_or_bytes: str | bytes,
    api_key: str | None = None,
) -> dict[str, Any] | None:
    """
    Tier 2: Send story screenshot to Gemini 2.0 Flash Vision to parse job metadata.
    Free tier allows 1,500 requests per day.
    """
    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        console.print("[yellow]GEMINI_API_KEY not configured. Skipping vision fallback.[/]")
        return None

    try:
        from google import genai
        from google.genai import types

        # Download image bytes if given a URL (string, HttpUrl, etc.)
        if isinstance(image_url_or_bytes, (bytes, bytearray)):
            image_bytes = bytes(image_url_or_bytes)
        else:
            url_str = str(image_url_or_bytes).strip()
            if not url_str or not url_str.startswith("http"):
                console.print(f"[dim yellow]Invalid image URL: {url_str}[/]")
                return None
            resp = httpx.get(url_str, timeout=15.0)
            resp.raise_for_status()
            image_bytes = resp.content

        client = genai.Client(api_key=key)


        prompt = (
            "Analyze this Instagram story screenshot. Determine if it is a job/internship posting. "
            "If yes, extract the company, job title, terms/season (e.g. Summer 2027), locations, "
            "whether it is remote, and target degree levels (e.g. ['Bachelor's'], ['Master's'], ['PhD']). "
            "Respond ONLY with valid JSON in this format: "
            '{"is_job_posting": true, "company": "...", "title": "...", "location": "...", '
            '"terms": ["Summer 2027"], "degrees": ["Bachelor\'s"], "is_remote": false}. '
            'If it is career advice, an interview tip, or NOT a specific job opening, '
            'respond with {"is_job_posting": false}.'
        )


        model_name = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                    prompt,
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                ),
            )
        except Exception:
            # Fallback to gemini-2.5-flash if 3.5-flash-lite encounters temporary error
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                    prompt,
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                ),
            )



        if response.text:
            data = json.loads(response.text)
            if data.get("is_job_posting"):
                data["method"] = "gemini_vision"
                return data

    except Exception as exc:
        console.print(f"[bold red]Gemini Vision extraction failed:[/] {exc}")

    return None


def extract_job_posting_details(
    url: str,
    image_url: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """
    Full two-tier extraction pipeline:
    1. Tries direct HTML / OpenGraph parsing first.
    2. Falls back to Gemini Vision on story screenshot if Tier 1 fails or returns incomplete title/company.
    """
    clean_url = canonicalize_url(url)

    # 1. Try Tier 1: Webpage scraping
    details = extract_from_webpage(clean_url)
    if details and details.get("company") and details.get("title") and details["company"] != "Unknown Company":
        return details

    # 2. Try Tier 2: Gemini Vision fallback
    if image_url:
        console.print("[cyan]Tier 1 returned incomplete details. Falling back to Gemini Flash Vision...[/]")
        vision_result = extract_with_gemini_vision(image_url, api_key=api_key)
        if vision_result:
            vision_result["url"] = clean_url
            vision_result["requisition_id"] = extract_requisition_id(clean_url)
            return vision_result

    # If both tiers failed, return minimal placeholder with canonical URL
    return {
        "company": (details.get("company") if details else "Unknown Company"),
        "title": (details.get("title") if details else "Job Opportunity"),
        "location": None,
        "terms": extract_terms_from_text(clean_url),
        "is_remote": False,
        "url": clean_url,
        "requisition_id": extract_requisition_id(clean_url),
        "method": "fallback",
    }
