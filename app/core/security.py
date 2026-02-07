"""
Security utilities for authentication and authorization.

Baseado na documentacao oficial do FastAPI:
https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/

SEGURANCA:
- SECRET_KEY e obrigatoria via env var (sem fallback)
- Senhas hashadas com argon2 (fallback bcrypt)
- JWT com tenant_id para isolamento multi-tenant

Autor: Sistema PMI | Atualizado: 2026-02-06
"""

import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

LOGGER = logging.getLogger(__name__)

# ============================================================================
# CONFIGURACOES (sem fallbacks inseguros)
# ============================================================================

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    if os.getenv("APP_ENV", "development") == "development":
        LOGGER.warning(
            "SECRET_KEY nao definida. Usando chave de desenvolvimento. "
            "NUNCA use isso em producao!"
        )
        import secrets
        SECRET_KEY = secrets.token_hex(32)
    else:
        raise RuntimeError(
            "SECRET_KEY environment variable is required. "
            "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

# Contexto de hash de senha - usar argon2 como padrão com bcrypt como fallback
# Isso resolve o problema de bcrypt 5.0.0 removendo __about__
pwd_context = CryptContext(
    schemes=["argon2", "bcrypt"],
    deprecated="auto"
)

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

# Modelos
class Token(BaseModel):
    access_token: str
    token_type: str
    tenant_id: str | None = None

class TokenData(BaseModel):
    email: str | None = None
    tenant_id: str | None = None
    user_id: int | None = None

# Funções de segurança
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica se a senha corresponde ao hash."""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    """Gera hash da senha com bcrypt."""
    if not password:
        raise ValueError("Password cannot be empty")
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Cria um JWT token."""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    """Extrai o usuario atual do token JWT."""
    from sqlmodel import Session, select

    from app.core.database import get_sync_engine
    from app.models.models import User

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(
            email=email,
            tenant_id=payload.get("tenant_id"),
            user_id=payload.get("user_id"),
        )
    except JWTError as exc:
        raise credentials_exception from exc

    # Buscar usuario no banco - usa with para garantir que session fecha
    engine = get_sync_engine()
    with Session(engine) as session:
        user = session.exec(
            select(User).where(User.email == token_data.email)
        ).first()

        if user is None:
            raise credentials_exception

        # Injeta tenant_id no contexto se disponivel
        if token_data.tenant_id:
            try:
                from uuid import UUID

                from app.core.tenant import set_current_tenant_id
                set_current_tenant_id(UUID(token_data.tenant_id))
            except (ValueError, TypeError):
                pass

        return user


def decode_jwt_token(token: str) -> dict:
    """
    Decodifica JWT token e retorna o payload.

    Usado pelo TenantMiddleware para extrair tenant_id.

    Args:
        token: JWT token string

    Returns:
        dict: Payload do token

    Raises:
        JWTError: Se o token for inválido
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return {}
