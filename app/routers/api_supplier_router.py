"""
Router para gerenciamento de Fornecedores.

Endpoints:
- GET /api/suppliers/         Lista todos os fornecedores
- GET /api/suppliers/{id}     Detalhes de um fornecedor
- GET /api/suppliers/{id}/offers  Ofertas de um fornecedor
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from sqlalchemy import desc

from app.core.database import get_session
from app.models.models import Fornecedor, OfertaProduto, Produto

router = APIRouter(prefix="/api/suppliers", tags=["suppliers"])


@router.get("/")
def list_suppliers(
    limit: int = Query(default=50, ge=1, le=200),
    search: Optional[str] = None,
    session: Session = Depends(get_session)
):
    """Lista todos os fornecedores com estatísticas."""
    
    query = select(Fornecedor).order_by(Fornecedor.nome)
    
    if search:
        query = query.where(Fornecedor.nome.ilike(f"%{search}%"))
    
    suppliers = session.exec(query.limit(limit)).all()
    
    result = []
    for supplier in suppliers:
        # Contar ofertas do fornecedor
        offer_count = session.exec(
            select(OfertaProduto)
            .where(OfertaProduto.fornecedor_id == supplier.id)
        ).all()
        
        result.append({
            "id": supplier.id,
            "nome": supplier.nome,
            "cep": supplier.cep,
            "confiabilidade": supplier.confiabilidade,
            "prazo_entrega_dias": supplier.prazo_entrega_dias,
            "latitude": supplier.latitude,
            "longitude": supplier.longitude,
            "ofertas_count": len(offer_count),
            "criado_em": supplier.criado_em.isoformat(),
            "atualizado_em": supplier.atualizado_em.isoformat(),
        })
    
    return result


@router.get("/{supplier_id}")
def get_supplier(
    supplier_id: int,
    session: Session = Depends(get_session)
):
    """Detalhes de um fornecedor específico."""
    
    supplier = session.get(Fornecedor, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Fornecedor não encontrado")
    
    # Buscar ofertas do fornecedor
    ofertas = session.exec(
        select(OfertaProduto)
        .where(OfertaProduto.fornecedor_id == supplier_id)
    ).all()
    
    return {
        "id": supplier.id,
        "nome": supplier.nome,
        "cep": supplier.cep,
        "confiabilidade": supplier.confiabilidade,
        "prazo_entrega_dias": supplier.prazo_entrega_dias,
        "latitude": supplier.latitude,
        "longitude": supplier.longitude,
        "ofertas_count": len(ofertas),
        "criado_em": supplier.criado_em.isoformat(),
        "atualizado_em": supplier.atualizado_em.isoformat(),
    }


@router.get("/{supplier_id}/offers")
def get_supplier_offers(
    supplier_id: int,
    session: Session = Depends(get_session)
):
    """Lista ofertas de um fornecedor com detalhes do produto."""
    
    supplier = session.get(Fornecedor, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Fornecedor não encontrado")
    
    ofertas = session.exec(
        select(OfertaProduto)
        .where(OfertaProduto.fornecedor_id == supplier_id)
        .order_by(desc(OfertaProduto.atualizado_em))
    ).all()
    
    result = []
    for oferta in ofertas:
        # Buscar produto
        produto = session.get(Produto, oferta.produto_id)
        
        result.append({
            "id": oferta.id,
            "produto_id": oferta.produto_id,
            "produto_sku": produto.sku if produto else "N/A",
            "produto_nome": produto.nome if produto else "N/A",
            "preco": float(oferta.preco_ofertado),
            "estoque_disponivel": oferta.estoque_disponivel,
            "atualizado_em": oferta.atualizado_em.isoformat(),
        })
    
    return {
        "fornecedor": {
            "id": supplier.id,
            "nome": supplier.nome
        },
        "ofertas": result
    }


# ==================== CRUD OPERATIONS ====================

from pydantic import BaseModel
from datetime import datetime, timezone

class SupplierCreate(BaseModel):
    nome: str
    cep: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    confiabilidade: float = 0.9
    prazo_entrega_dias: int = 7


class SupplierUpdate(BaseModel):
    nome: Optional[str] = None
    cep: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    confiabilidade: Optional[float] = None
    prazo_entrega_dias: Optional[int] = None


@router.post("/")
def create_supplier(
    supplier_data: SupplierCreate,
    session: Session = Depends(get_session)
):
    """Cria um novo fornecedor."""
    
    # Verificar se já existe com mesmo nome
    existing = session.exec(
        select(Fornecedor).where(Fornecedor.nome == supplier_data.nome)
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Já existe um fornecedor com este nome")
    
    supplier = Fornecedor(
        nome=supplier_data.nome,
        cep=supplier_data.cep,
        latitude=supplier_data.latitude,
        longitude=supplier_data.longitude,
        confiabilidade=supplier_data.confiabilidade,
        prazo_entrega_dias=supplier_data.prazo_entrega_dias
    )
    
    session.add(supplier)
    session.commit()
    session.refresh(supplier)
    
    return {
        "id": supplier.id,
        "nome": supplier.nome,
        "cep": supplier.cep,
        "confiabilidade": supplier.confiabilidade,
        "prazo_entrega_dias": supplier.prazo_entrega_dias,
        "message": "Fornecedor criado com sucesso"
    }


@router.put("/{supplier_id}")
def update_supplier(
    supplier_id: int,
    supplier_data: SupplierUpdate,
    session: Session = Depends(get_session)
):
    """Atualiza um fornecedor existente."""
    
    supplier = session.get(Fornecedor, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Fornecedor não encontrado")
    
    # Atualizar apenas campos fornecidos
    update_data = supplier_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        if value is not None:
            setattr(supplier, key, value)
    
    supplier.atualizado_em = datetime.now(timezone.utc)
    
    session.add(supplier)
    session.commit()
    session.refresh(supplier)
    
    return {
        "id": supplier.id,
        "nome": supplier.nome,
        "cep": supplier.cep,
        "confiabilidade": supplier.confiabilidade,
        "prazo_entrega_dias": supplier.prazo_entrega_dias,
        "message": "Fornecedor atualizado com sucesso"
    }


@router.delete("/{supplier_id}")
def delete_supplier(
    supplier_id: int,
    session: Session = Depends(get_session)
):
    """Remove um fornecedor."""
    
    supplier = session.get(Fornecedor, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Fornecedor não encontrado")
    
    # Verificar se tem ofertas associadas
    ofertas = session.exec(
        select(OfertaProduto).where(OfertaProduto.fornecedor_id == supplier_id)
    ).first()
    
    if ofertas:
        raise HTTPException(
            status_code=400, 
            detail="Não é possível remover fornecedor com ofertas cadastradas. Remova as ofertas primeiro."
        )
    
    session.delete(supplier)
    session.commit()
    
    return {"message": "Fornecedor removido com sucesso"}
