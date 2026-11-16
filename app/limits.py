"""Limitador de peticiones, en su propio módulo para que los routers lo importen sin ciclos."""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
