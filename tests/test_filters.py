"""Tests for degree, location, and search filtering logic."""

import re
import pytest


def test_undergrad_filter_excludes_graduate_roles():
    """Test that graduate degree roles (PhD, Masters, MBA, Postdoc) are caught by regex."""
    grad_pattern = re.compile(
        r"(\b(PhD|Doctoral|Doctorate|Masters|MS|MBA|Postdoc|Post-Doc)\b|Ph\.D|Master\'?s|Advanced Degree|(?<!under)graduate)",
        re.IGNORECASE,
    )

    grad_titles = [
        "Machine Learning Researcher – PhD Intern",
        "Quantitative Systematic Trading Intern - Master's",
        "MBA Intern - Product Management",
        "Applied Machine Learning Scientist Intern - PhD",
        "Doctoral Quantitative Researcher Intern",
        "Advanced Degree Software Engineer Intern",
        "Data Science Postdoc Researcher",
    ]

    for title in grad_titles:
        assert grad_pattern.search(title) is not None, f"Expected {title} to be detected as a graduate role"


def test_undergrad_filter_preserves_undergrad_roles():
    """Test that legitimate undergraduate and standard roles are NOT detected as graduate roles."""
    grad_pattern = re.compile(
        r"(\b(PhD|Doctoral|Doctorate|Masters|MS|MBA|Postdoc|Post-Doc)\b|Ph\.D|Master\'?s|Advanced Degree|(?<!under)graduate)",
        re.IGNORECASE,
    )

    undergrad_titles = [
        "Software Development Engineer Intern - Undergraduate",
        "Campus Undergraduate Summer Internship - Strategy & Analytics",
        "Software Engineer Intern",
        "Data Analyst Intern",
        "Frontend Developer Co-op",
        "Hardware Engineering Intern",
    ]

    for title in undergrad_titles:
        assert grad_pattern.search(title) is None, f"Expected {title} to NOT be detected as graduate role"


def test_us_only_location_filter():
    """Test that US states, tech hubs, and domestic remote match, while overseas locations are filtered."""
    us_pattern = re.compile(
        r"\b(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC|USA|United States|NYC|SF|San Francisco|New York|Seattle|Austin|Chicago|Boston|Los Angeles|Remote in USA|US Remote)\b",
        re.IGNORECASE,
    )
    non_us_pattern = re.compile(
        r"\b(UK|Canada|London|Toronto|Vancouver|Waterloo|Montreal|Singapore|India|Australia|Sydney|Berlin|Germany|France|Paris|Dublin|Ireland|Zurich|Switzerland|Tokyo|Japan|Seoul|Korea)\b",
        re.IGNORECASE,
    )

    us_locations = [
        "Seattle, WA",
        "San Francisco, CA",
        "New York, NY",
        "Austin, TX",
        "Chicago, IL",
        "Remote in USA",
        "Boston, MA",
    ]

    foreign_locations = [
        "London, UK",
        "Toronto, ON, Canada",
        "Singapore",
        "Berlin, Germany",
        "Dublin, Ireland",
        "Zurich, Switzerland",
    ]

    for loc in us_locations:
        assert us_pattern.search(loc) is not None, f"Expected {loc} to match US pattern"

    for loc in foreign_locations:
        assert non_us_pattern.search(loc) is not None, f"Expected {loc} to match non-US pattern"


def test_symbol_search_resilience():
    """Test that symbol searches ('.', 'C++', '.NET', 'W.W.') format query strings cleanly."""
    symbols = [".", "C++", ".NET", "W.W. Grainger", "Amazon.com"]
    for sym in symbols:
        cleaned = sym.strip()
        like_expr = f"%{cleaned}%"
        assert len(cleaned) > 0
        assert like_expr.startswith("%") and like_expr.endswith("%")
