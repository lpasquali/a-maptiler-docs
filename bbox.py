from geopy.geocoders import Nominatim
from country_bounding_boxes import country_subunits_by_iso_code
import sys
import re

def bbox_area(bbox):
    # bbox: (min_lat, min_lon, max_lat, max_lon)
    if not bbox or len(bbox) != 4:
        return 0
    return abs((bbox[2] - bbox[0]) * (bbox[3] - bbox[1]))

def bbox_center_country(bbox):
    # bbox: (min_lat, min_lon, max_lat, max_lon)
    if not bbox or len(bbox) != 4:
        return None
    center_lat = (bbox[0] + bbox[2]) / 2
    center_lon = (bbox[1] + bbox[3]) / 2
    return (center_lat, center_lon)

def bbox_center_city(bbox):
    # bbox: [south, north, west, east]
    if not bbox or len(bbox) != 4:
        return None
    center_lat = (bbox[0] + bbox[1]) / 2
    center_lon = (bbox[2] + bbox[3]) / 2
    return (center_lat, center_lon)

if len(sys.argv) < 2:
    print("Usage: python bbox-unified.py <LOCATION>")
    sys.exit(1)

input_str = sys.argv[1].strip()

# Check if input is ISO country code (2 uppercase letters)
if re.fullmatch(r"[A-Z]{2}", input_str):
    subunits = country_subunits_by_iso_code(input_str)
    if not subunits:
        print(f"No subunits found for ISO code '{input_str}'.")
        sys.exit(1)
    # Find the subunit with the largest area
    largest = max(subunits, key=lambda c: bbox_area(getattr(c, 'bbox', None)))
    name = getattr(largest, 'name', 'Unknown')
    bbox = getattr(largest, 'bbox', None)
    center = bbox_center_country(bbox)
    print("Type: Country")
    print("Name:", name)
    print("Bounding box:", bbox)
    print("Center:", center)
else:
    geolocator = Nominatim(user_agent="bbox_unified_script")
    location = geolocator.geocode(input_str, exactly_one=True)
    if not location or not hasattr(location, 'raw') or 'boundingbox' not in location.raw:
        print(f"No bounding box found for location '{input_str}'.")
        sys.exit(1)
    bbox = [float(coord) for coord in location.raw['boundingbox']]
    center = bbox_center_city(bbox)
    print("Type: City/Region/State/Province")
    print("Name:", location.address)
    print("Bounding box:", bbox)
    print("Center:", center)