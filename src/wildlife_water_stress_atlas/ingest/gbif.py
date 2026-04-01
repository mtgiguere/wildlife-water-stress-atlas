"""
gbif.py

Fetch species occurrence data from GBIF API.
"""

import requests

GBIF_API_URL = "https://api.gbif.org/v1/occurrence/search"


def fetch_occurrences(scientific_name: str, limit: int = 100):
    """
    Fetch occurrence records for a given species.
    """
    params = {
        "scientificName": scientific_name,
        "limit": limit,
        "hasCoordinate": "true",
    }

    response = requests.get(GBIF_API_URL, params=params, timeout=30)
    response.raise_for_status()

    data = response.json()

    return data.get("results", [])
