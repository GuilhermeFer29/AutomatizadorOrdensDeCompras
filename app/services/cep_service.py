"""Service to fetch address data from CEP using ViaCEP API."""

from typing import Dict
import requests

BASE_URL = "https://viacep.com.br/ws"

def get_address_from_cep(cep: str) -> Dict[str, str]:
    """Fetch address details from a given CEP using ViaCEP API.

    Args:
        cep (str): The CEP (ZIP code) to fetch the address for.

    Returns:
        Dict[str, str]: A dictionary containing address details.

    Raises:
        ValueError: If the CEP is invalid or the API request fails.
    """
    response = requests.get(f"{BASE_URL}/{cep}/json/")

    if response.status_code != 200 or "erro" in response.json():
        raise ValueError(f"Invalid CEP or unable to fetch data for CEP: {cep}")

    return response.json()