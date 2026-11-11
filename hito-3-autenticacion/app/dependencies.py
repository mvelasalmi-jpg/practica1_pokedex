"""Dependencias compartidas: sesión y usuario actual."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session

from app.auth import decode_access_token
from app.database import get_session
from app.models import User

LOGIN_URL = "/api/v1/auth/login"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=LOGIN_URL)

SessionDep = Annotated[Session, Depends(get_session)]


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)], session: SessionDep
) -> User:
    no_autorizado = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales no válidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if payload is None or "user_id" not in payload:
        raise no_autorizado
    usuario = session.get(User, payload["user_id"])
    if usuario is None or not usuario.is_active:
        raise no_autorizado
    return usuario


CurrentUser = Annotated[User, Depends(get_current_user)]
