"""Tests de autenticación: registro, login, protección de endpoints y rate limit."""

from app.auth import decode_access_token
from tests.conftest import PASSWORD

NUEVO = {"username": "misty", "email": "misty@example.com", "password": "Starmie123"}


def test_register_user_success(client):
    """Registro exitoso de usuario."""
    r = client.post("/api/v1/auth/register", json=NUEVO)
    assert r.status_code == 201
    cuerpo = r.json()
    assert cuerpo["username"] == "misty"
    # La respuesta NUNCA debe incluir la contraseña, ni siquiera hasheada.
    assert "password" not in cuerpo
    assert "hashed_password" not in cuerpo


def test_register_duplicate_username(client, test_user):
    """Error al registrar un username duplicado."""
    r = client.post(
        "/api/v1/auth/register",
        json={"username": "ash", "email": "otro@example.com", "password": "Starmie123"},
    )
    assert r.status_code == 409


def test_register_weak_password_returns_422(client):
    """Una contraseña sin mayúscula o sin número se rechaza con el formato único."""
    r = client.post(
        "/api/v1/auth/register", json={**NUEVO, "password": "sinmayuscula1"}
    )
    assert r.status_code == 422
    cuerpo = r.json()
    assert cuerpo["detail"] == "Datos de entrada no válidos"
    assert any("password" in e["campo"] for e in cuerpo["errors"])


def test_register_invalid_email(client):
    r = client.post("/api/v1/auth/register", json={**NUEVO, "email": "no-es-un-email"})
    assert r.status_code == 422


def test_login_success(client, test_user):
    """Login exitoso devuelve un JWT válido con los claims pedidos."""
    r = client.post(
        "/api/v1/auth/login", data={"username": "ash", "password": PASSWORD}
    )
    assert r.status_code == 200
    token = r.json()["access_token"]
    claims = decode_access_token(token)
    assert claims["sub"] == "ash"
    assert claims["user_id"] == test_user.id
    assert "exp" in claims and "iat" in claims
    # El token dura 24 horas (86400 segundos).
    assert claims["exp"] - claims["iat"] == 24 * 3600


def test_login_invalid_credentials(client, test_user):
    """Login con credenciales incorrectas devuelve 401."""
    r = client.post("/api/v1/auth/login", data={"username": "ash", "password": "mal"})
    assert r.status_code == 401


def test_access_protected_endpoint_without_token(client):
    """Acceso sin token devuelve 401."""
    assert client.get("/api/v1/pokedex").status_code == 401


def test_access_with_invalid_token(client):
    """Un token inventado también se rechaza."""
    r = client.get("/api/v1/pokedex", headers={"Authorization": "Bearer inventado"})
    assert r.status_code == 401


def test_rate_limit_exceeded(client):
    """La 11.ª petición de login en un minuto devuelve 429."""
    codigos = [
        client.post(
            "/api/v1/auth/login", data={"username": "x", "password": "y"}
        ).status_code
        for _ in range(11)
    ]
    assert (
        codigos[:10] == [401] * 10
    )  # las 10 primeras pasan el límite (y fallan el login)
    assert codigos[10] == 429


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}
