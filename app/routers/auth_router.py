"""
Authentication routes.
Baseado na documentação oficial do FastAPI:
https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/
"""

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select

from app.core.database import get_session
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    Token,
)
from app.models.models import User
from pydantic import BaseModel, Field

router = APIRouter(prefix="/auth", tags=["auth"])

# Modelos
class UserRegister(BaseModel):
    email: str = Field(..., min_length=1)
    password: str = Field(..., min_length=6)
    full_name: str = Field(default="", max_length=255)

class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str

# Rotas
@router.post("/register", response_model=UserResponse)
def register(
    user_data: UserRegister,
    session: Session = Depends(get_session)
):
    """Registra um novo usuário."""
    # Verificar se email já existe
    existing_user = session.exec(
        select(User).where(User.email == user_data.email)
    ).first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email já cadastrado"
        )
    
    # Criar novo usuário
    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        email=user_data.email,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        is_active=True
    )
    
    session.add(new_user)
    session.commit()
    session.refresh(new_user)
    
    return UserResponse(
        id=new_user.id,
        email=new_user.email,
        full_name=new_user.full_name
    )

@router.post("/login", response_model=Token)
def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Session = Depends(get_session)
):
    """Faz login e retorna um token JWT."""
    # Buscar usuário por email (username no OAuth2PasswordRequestForm)
    user = session.exec(
        select(User).where(User.email == form_data.username)
    ).first()
    
    # Verificar credenciais
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha inválidos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Criar token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email},
        expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}
