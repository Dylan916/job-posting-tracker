"""Unit tests for location cleaner and canonicalizer."""

import pytest
from processing.location_cleaner import clean_single_location, normalize_location


def test_missing_state_tech_hubs():
    """Test that tech hubs without state abbreviation receive standard 2-letter state codes."""
    assert clean_single_location("Palo Alto") == "Palo Alto, CA"
    assert clean_single_location("Laurel") == "Laurel, MD"
    assert clean_single_location("Pittsburgh") == "Pittsburgh, PA"
    assert clean_single_location("ALPHARETTA") == "Alpharetta, GA"
    assert clean_single_location("Sunnyvale") == "Sunnyvale, CA"
    assert clean_single_location("Mountain View") == "Mountain View, CA"
    assert clean_single_location("Seattle") == "Seattle, WA"
    assert clean_single_location("Austin") == "Austin, TX"


def test_full_state_name_conversion():
    """Test that full state names are converted to 2-letter postal codes."""
    assert clean_single_location("San Jose, California") == "San Jose, CA"
    assert clean_single_location("Yorktown Heights, New York") == "Yorktown Heights, NY"
    assert clean_single_location("San Jose, California, United States") == "San Jose, CA"
    assert clean_single_location("Yorktown Heights, New York, United States") == "Yorktown Heights, NY"


def test_workday_and_ats_messy_formats():
    """Test Workday reversed formats, facility noise, and building suffixes."""
    assert clean_single_location("USA, CA, Pleasanton") == "Pleasanton, CA"
    assert clean_single_location("Pleasanton, CA, USA") == "Pleasanton, CA"
    assert clean_single_location("Edison, NJ (GMD) 1301") == "Edison, NJ"
    assert clean_single_location("Boise, ID - Main Site") == "Boise, ID"
    assert clean_single_location("GM Automation - Sunnyvale - GM Automation - Sunnyvale") == "Sunnyvale, CA"


def test_canadian_locations():
    """Test Canadian provinces format as City, Province, Canada."""
    assert clean_single_location("Calgary, AB, Canada") == "Calgary, AB, Canada"
    assert clean_single_location("Toronto, Ontario") == "Toronto, ON, Canada"
    assert clean_single_location("Toronto, ON") == "Toronto, ON, Canada"
    assert clean_single_location("Vancouver, BC") == "Vancouver, BC, Canada"
    assert clean_single_location("Ottawa, ON, Canada") == "Ottawa, ON, Canada"


def test_international_locations():
    """Test international locations keep City, Country."""
    assert clean_single_location("London, UK") == "London, UK"
    assert clean_single_location("London, United Kingdom") == "London, UK"
    assert clean_single_location("Berlin, Germany") == "Berlin, Germany"
    assert clean_single_location("Dublin, Ireland") == "Dublin, Ireland"


def test_remote_variations():
    """Test remote variations."""
    assert clean_single_location("Remote") == "Remote"
    assert clean_single_location("Remote in USA") == "Remote in USA"
    assert clean_single_location("US Remote") == "Remote in USA"
    assert clean_single_location("remote - us") == "Remote in USA"


def test_multi_location_strings():
    """Test strings containing multiple locations separated by semicolons or commas."""
    multi = "Yorktown Heights, New York; Cambridge, Massachusetts, United States"
    assert normalize_location(multi) == "Yorktown Heights, NY, Cambridge, MA"

    multi_comma = "Boston, MA, Tampa, FL, Rosemont, IL"
    assert normalize_location(multi_comma) == "Boston, MA, Tampa, FL, Rosemont, IL"
