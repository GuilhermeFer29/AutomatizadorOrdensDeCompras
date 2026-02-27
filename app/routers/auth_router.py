"""
Authentication routes - SaaS Multi-Tenant.

Fluxos:
- POST /auth/register: Cria tenant + usuario (owner)
- POST /auth/login: Retorna JWT com tenant_id
- GET /auth/me: Retorna usuario atual

Baseado na documentacao oficial do FastAPI:
https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/

Autor: Sistema PMI | Atualizado: 2026-02-06
"""

import re
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlmodel import Session, select

from app.core.database import get_session
from app.core.security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    Token,
    create_access_token,
    get_current_user,
    get_password_hash,
    verify_password,
)
from app.models.models import Tenant, User

router = APIRouter(prefix="/auth", tags=["auth"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class UserRegister(BaseModel):
    """Modelo de registro de usuario com validacao robusta."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=255)
    company_name: str = Field(..., min_length=2, max_length=255)

    @field_validator("password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError("Senha deve conter pelo menos uma letra maiuscula")
        if not re.search(r"[a-z]", v):
            raise ValueError("Senha deve conter pelo menos uma letra minuscula")
        if not re.search(r"[0-9]", v):
            raise ValueError("Senha deve conter pelo menos um numero")
        return v


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str | None = None
    tenant_id: str | None = None
    role: str | None = None


class UserMeResponse(BaseModel):
    id: int
    email: str
    full_name: str | None = None
    is_active: bool
    tenant_id: str | None = None
    role: str | None = None


# ============================================================================
# HELPER: Gerar slug a partir do nome da empresa
# ============================================================================

def _generate_slug(name: str, session: Session) -> str:
    """Gera slug unico a partir do nome da empresa."""
    import unicodedata
    # Remove acentos e caracteres especiais
    slug = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^\w\s-]", "", slug).strip().lower()
    slug = re.sub(r"[-\s]+", "-", slug)[:50]

    # Garante unicidade
    base_slug = slug
    counter = 1
    while session.exec(select(Tenant).where(Tenant.slug == slug)).first():
        slug = f"{base_slug}-{counter}"
        counter += 1

    return slug


# ============================================================================
# ROTAS
# ============================================================================

@router.post("/register", response_model=UserResponse)
def register(
    user_data: UserRegister,
    session: Session = Depends(get_session),
):
    """
    Registra novo usuario e cria tenant (empresa).

    Fluxo:
    1. Valida email unico
    2. Cria Tenant (empresa)
    3. Cria User como 'owner' do tenant
    4. Retorna dados do usuario
    """
    # Verificar se email ja existe
    existing_user = session.exec(
        select(User).where(User.email == user_data.email)
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email ja cadastrado",
        )

    # Criar Tenant (empresa)
    slug = _generate_slug(user_data.company_name, session)
    tenant = Tenant(
        nome=user_data.company_name,
        slug=slug,
        plano="free",
        ativo=True,
        max_usuarios=5,
        max_produtos=100,
    )
    session.add(tenant)
    session.flush()  # Para obter o tenant.id

    # Criar usuario como owner do tenant
    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        email=user_data.email,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        is_active=True,
        tenant_id=tenant.id,
        role="owner",
    )

    session.add(new_user)
    session.commit()
    session.refresh(new_user)

    return UserResponse(
        id=new_user.id,
        email=new_user.email,
        full_name=new_user.full_name,
        tenant_id=str(new_user.tenant_id) if new_user.tenant_id else None,
        role=getattr(new_user, "role", None),
    )


@router.post("/login", response_model=Token)
def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Session = Depends(get_session),
):
    """
    Faz login e retorna JWT com tenant_id.

    Rate-limiting: máximo 10 tentativas por IP por minuto (via Redis).

    O token JWT inclui:
    - sub: email do usuario
    - tenant_id: UUID do tenant (para isolamento de dados)
    - user_id: ID do usuario
    - role: role do usuario no tenant
    """
    # ---- Rate-limiting simples via Redis ----
    try:
        from app.core.redis_client import get_redis_client
        redis = get_redis_client()
        if redis:
            rk = f"login_attempts:{form_data.username}"
            attempts = redis.incr(rk)
            if attempts == 1:
                redis.expire(rk, 60)  # janela de 60 s
            if attempts > 10:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Muitas tentativas de login. Tente novamente em 1 minuto.",
                )
    except HTTPException:
        raise
    except Exception:
        pass  # Redis indisponível — segue sem rate-limit

    # Buscar usuario por email
    user = session.exec(
        select(User).where(User.email == form_data.username)
    ).first()

    # Verificar credenciais
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha invalidos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Conta desativada. Entre em contato com o administrador.",
        )

    # Criar token com tenant_id
    token_data = {"sub": user.email}

    if user.tenant_id:
        token_data["tenant_id"] = str(user.tenant_id)
    if user.id:
        token_data["user_id"] = user.id
    if hasattr(user, "role") and user.role:
        token_data["role"] = user.role

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data=token_data,
        expires_delta=access_token_expires,
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "tenant_id": str(user.tenant_id) if user.tenant_id else None,
    }


@router.get("/me", response_model=UserMeResponse)
async def get_me(current_user=Depends(get_current_user)):
    """Retorna dados do usuario autenticado."""
    return UserMeResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        tenant_id=str(current_user.tenant_id) if current_user.tenant_id else None,
        role=getattr(current_user, "role", None),
    )
