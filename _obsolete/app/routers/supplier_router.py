"""Router to handle supplier enrichment and comparison logic."""

from fastapi import APIRouter, HTTPException
from app.services.supplier_service import enrich_supplier_with_geolocation

router = APIRouter(prefix="/fornecedores", tags=["fornecedores"])


@router.post("/enriquecer/{supplier_id}", status_code=200)
def enrich_supplier(supplier_id: int, cep: str):
    """Enrich supplier data with geolocation and CEP details.

    Args:
        supplier_id (int): The ID of the supplier to enrich.
        cep (str): The CEP of the supplier.

    Returns:
        dict: Enriched supplier data.
    """
    try:
        return enrich_supplier_with_geolocation(supplier_id, cep)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))