"""Contraseñas (bcrypt) y testigos (JWT)."""

from datetime import UTC, datetime, timedelta

import bcrypt
from jose import JWTError, jwt

from app.config import settings

# bcrypt directamente: passlib lleva años sin mantenerse y falla con bcrypt ≥ 4.1
# (AttributeError: module 'bcrypt' has no attribute '__about__').


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_access_token(username: str, user_id: int) -> str:
    ahora = datetime.now(UTC)
    minutos = settings.access_token_expire_minutes
    payload = {
        "sub": username,
        "user_id": user_id,
        "iat": ahora,
        "exp": ahora + timedelta(minutes=minutos),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        # Firma mala, caducado o inventado → None, no excepción.
        # Quien llama decide qué código HTTP le corresponde a eso.
        return None
