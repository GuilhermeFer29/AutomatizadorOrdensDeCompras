"""Service to enrich supplier data with geolocation and CEP details."""

from typing import Dict
from app.services.cep_service import get_address_from_cep
from app.services.geolocation_service import get_coordinates_from_address
from sqlmodel import Session
from app.models.models import Fornecedor
from app.core.database import engine

def enrich_supplier_with_geolocation(supplier_id: int, cep: str) -> Dict[str, str]:
    """Enrich supplier data with address and geolocation details.

    Args:
        supplier_id (int): The ID of the supplier to enrich.
        cep (str): The CEP of the supplier.

    Returns:
        Dict[str, str]: Updated supplier data.

    Raises:
        ValueError: If the CEP or geolocation data cannot be fetched.
    """
    address = get_address_from_cep(cep)

    # Validate required fields from ViaCEP response
    required_fields = ["logradouro", "bairro", "localidade", "uf"]
    for field in required_fields:
        if field not in address or not address[field]:
            raise ValueError(f"Missing or invalid field '{field}' in address data: {address}")

    full_address = f"{address['logradouro']}, {address['bairro']}, {address['localidade']}, {address['uf']}"
    coordinates = get_coordinates_from_address(full_address)

    with Session(engine) as session:
        supplier = session.get(Fornecedor, supplier_id)
        if not supplier:
            raise ValueError(f"Supplier with ID {supplier_id} not found.")

        supplier.cep = cep
        supplier.latitude, supplier.longitude = coordinates
        session.add(supplier)
        session.commit()

    return {
        "supplier_id": supplier_id,
        "cep": cep,
        "latitude": coordinates[0],
        "longitude": coordinates[1],
    }