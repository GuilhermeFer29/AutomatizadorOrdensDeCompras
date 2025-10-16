"""Service to handle geolocation and distance calculations."""

from typing import Tuple
from math import radians, sin, cos, sqrt, atan2
import requests

BASE_URL = "https://nominatim.openstreetmap.org/search"


def get_coordinates_from_address(address: str) -> Tuple[float, float]:
    """Fetch latitude and longitude for a given address using Nominatim API.

    Args:
        address (str): The address to geocode.

    Returns:
        Tuple[float, float]: Latitude and longitude of the address.

    Raises:
        ValueError: If the address cannot be geocoded.
    """
    headers = {"User-Agent": "PlataformaPreditiva/1.0 (contact@example.com)"}
    params = {"q": address, "format": "json"}
    response = requests.get(BASE_URL, params=params, headers=headers)

    if response.status_code != 200:
        raise ValueError(f"Error fetching coordinates: {response.status_code} - {response.text}")

    data = response.json()
    if not data:
        raise ValueError(f"No results found for address: {address}")

    # Attempt to find the most relevant result
    for result in data:
        try:
            lat = float(result["lat"])
            lon = float(result["lon"])
            return lat, lon
        except (KeyError, ValueError):
            continue

    raise ValueError(f"Unable to fetch valid coordinates for address: {address}")


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the Haversine distance between two points on the Earth.

    Args:
        lat1 (float): Latitude of the first point.
        lon1 (float): Longitude of the first point.
        lat2 (float): Latitude of the second point.
        lon2 (float): Longitude of the second point.

    Returns:
        float: Distance in kilometers.
    """
    R = 6371.0  # Earth radius in kilometers

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return R * c