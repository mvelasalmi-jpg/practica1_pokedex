# Pokédex API

![CI](https://github.com/<organizacion>/pokedex-api/actions/workflows/ci.yml/badge.svg)

## Descripción

API REST para entrenadores Pokémon, hecha con **FastAPI** y **SQLModel**. Cada usuario puede:

- Buscar Pokémon en la [PokeAPI](https://pokeapi.co/) oficial y descargar su ficha en PDF.
- Montar su **Pokédex personal** (añadir, marcar como capturado, favoritos, apodos y notas).
- Consultar **estadísticas** de su colección (porcentaje, tipo más común, racha de capturas).
- Crear **equipos de batalla** de hasta 6 Pokémon y exportarlos a PDF.
- Exportar su Pokédex a **CSV o PDF**.

Arquitectura: `Cliente → Nuestra API (FastAPI) → SQLite`, y la API consulta la PokeAPI por detrás.

## Equipo

| Miembro | Usuario Git | Partes desarrolladas |
|---|---|---|
| [Nombre 1] | [@usuario1] | [p. ej. estructura base, auth + tests de auth] |
| [Nombre 2] | [@usuario2] | [p. ej. cliente PokeAPI, Pokédex, equipos, tests, CI] |

## Instalación

Necesitas [uv](https://docs.astral.sh/uv/) (instala también Python 3.12).

```bash
git clone https://github.com/<organizacion>/pokedex-api.git
cd pokedex-api
uv sync
```

Alternativa sin uv: `python -m venv .venv`, activar el entorno y `pip install -r requirements.txt`.

## Configuración

Copia la plantilla y edítala (el `.env` real **nunca** se sube a Git):

```bash
cp .env.example .env        # en Windows: copy .env.example .env
```

| Variable | Para qué sirve |
|---|---|
| `SECRET_KEY` | Clave con la que se firman los JWT. **Obligatoria**: sin ella la app no arranca. Genera una con `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `DATABASE_URL` | Base de datos. Por defecto `sqlite:///./pokedex.db` |
| `CORS_ORIGINS` | Lista JSON de webs autorizadas a llamar a la API desde un navegador |

> Si ya tenías un `pokedex.db` de versiones anteriores, bórralo: el modelo ha ganado la columna `pokemon_types` y SQLite no migra tablas existentes.

## Ejecución

```bash
uv run uvicorn app.main:app --reload
```

- Documentación interactiva (Swagger): <http://localhost:8000/docs>
- Estado: <http://localhost:8000/health>

Para probar a mano: registra un usuario en `/api/v1/auth/register`, pulsa **Authorize** en Swagger e inicia sesión.

## Testing

```bash
uv run pytest --cov=app --cov-report=term-missing
```

Los tests **no usan internet**: la PokeAPI se sustituye por una versión falsa (`tests/fakes.py`) y el cliente HTTP se prueba con `httpx.MockTransport`. La base de datos de los tests es SQLite en memoria. Cobertura actual: ~97 % (mínimo exigido: 80 %).

## Flujo de trabajo y despliegue

- Ramas: `main` (estable, etiquetada `v1.0.0`), `develop` (integración) y una rama `features/<nombre>` por funcionalidad. Todo entra por *pull request* con una aprobación y la integración continua en verde.
- Mensajes de commit con *Conventional Commits* (`feat(teams): ...`).
- Tablero de GitHub Projects: [enlace pendiente]
- Despliegue (opcional): [URL pública y `/docs` si se despliega]

## Endpoints

Todos cuelgan de `/api/v1` y, salvo registro y login, exigen `Authorization: Bearer <token>`.

| Método y ruta | Descripción | Límite |
|---|---|---|
| `POST /auth/register` | Registro (contraseña ≥ 8, 1 mayúscula, 1 número) | 5/hora |
| `POST /auth/login` | Devuelve un JWT válido 24 h | 10/min |
| `GET /pokemon/search?name=&limit=&offset=` | Busca por trozo de nombre → `{id, name, sprite, types}` | 30/min |
| `GET /pokemon/{id_or_name}` | Detalle: stats, habilidades, tipos, sprites | 30/min |
| `GET /pokemon/{id_or_name}/card` | Ficha en PDF descargable | 30/min |
| `POST /pokedex` | Añade un Pokémon (valida que existe, sin duplicados) | 100/min |
| `GET /pokedex` | Lista con filtros `captured`, `favorite`, orden `sort`/`order`, paginación | 100/min |
| `PATCH /pokedex/{id}` | Actualiza una entrada propia | 100/min |
| `DELETE /pokedex/{id}` | Borra una entrada propia | 100/min |
| `GET /pokedex/export?format=csv\|pdf&captured=&favorite=` | Exporta la Pokédex | 100/min |
| `GET /pokedex/stats` | Totales, porcentaje, tipo más común, racha | 100/min |
| `POST /teams` | Crea un equipo (`pokemon_ids`, máx. 6, de tu Pokédex) | 100/min |
| `GET /teams` | Lista tus equipos | 100/min |
| `PUT /teams/{id}` | Cambia nombre, descripción o miembros | 100/min |
| `GET /teams/{id}/export` | PDF del equipo con estadísticas combinadas | 30/min |
| `GET /api/v2/pokedex` | Ejemplo de v2: respuesta con `total`, paginación y `types` | 100/min |

Códigos de error habituales: `401` sin token o token no válido, `404` recurso inexistente **o ajeno**, `409` duplicado, `422` datos no válidos (formato único con la lista `errors`), `429` límite excedido, `502/504` fallo de la PokeAPI.

## Decisiones de Diseño

### Rate limiting

- **¿Por qué límites distintos?** Cada endpoint cuesta y arriesga cosas distintas. El registro (5/hora por IP) es público y crea datos: lo limitamos mucho para evitar cuentas basura. El login (10/min) frena los ataques de fuerza bruta contra contraseñas. Los endpoints que llaman a la PokeAPI (30/min) son los más «caros»: cada petición nuestra puede generar varias externas, y no queremos que nos bloqueen a nosotros. Los endpoints normales de Pokédex y equipos (100/min) sólo tocan nuestra base de datos y son más baratos, así que se permite un uso cómodo.
- **¿Cómo protege a la API?** Evita fuerza bruta, abuso de recursos y que un solo cliente sature el servicio o agote la cuota de la PokeAPI.
- **¿Qué pasa al excedirlo?** La API responde `429 Too Many Requests`, el intento se anota en el log (`Rate limit excedido`) y el cliente puede volver a intentarlo cuando acabe la ventana de tiempo. Los contadores están en memoria de un proceso (ver *Mejoras futuras*).

### Versionado

- **¿Por qué versionar?** Porque los clientes (apps, webs) dependen del formato exacto de nuestras respuestas. Si lo cambiamos sin avisar, se rompen. Con la versión en la URL (`/api/v1`, `/api/v2`) cada cliente elige a cuál se conecta.
- **¿Qué cambios justifican una versión nueva?** Los que **rompen** a los clientes existentes: cambiar la forma de una respuesta (como en nuestra v2, que pasa de una lista a un objeto con `total` y `items`), quitar o renombrar campos, o cambiar el significado de un parámetro. Añadir un campo opcional o un endpoint nuevo **no** lo requiere.
- **Estrategia de deprecación:** se anuncia la retirada con antelación, la versión antigua sigue funcionando durante un periodo de transición (p. ej. 6 meses) con una cabecera de aviso, se documenta la migración y, pasado el plazo, se retira.

### Otras decisiones

- **SQLite**: sin instalación, ideal para la práctica; `DATABASE_URL` permite cambiar a PostgreSQL.
- **`bcrypt` directo en lugar de `passlib`**: `passlib` no se mantiene y falla con versiones recientes de bcrypt.
- **Guardar los tipos en la Pokédex** (`pokemon_types`): permite calcular el tipo más común sin llamar a la PokeAPI por cada entrada.
- **Caché en memoria** en el cliente de la PokeAPI: menos llamadas y respuestas más rápidas.
- **`fpdf2`** para los PDF: librería pura de Python, sin dependencias del sistema.
- **404 en vez de 403** para recursos de otro usuario: no revelamos que existen.
- **Formato único de errores 422** con la lista de campos y mensajes.

## Decisiones de Seguridad

Resumen (detalle en [SECURITY.md](SECURITY.md)): contraseñas con bcrypt, JWT firmado con clave en variable de entorno y caducidad de 24 h, rate limiting diferenciado, CORS restringido a orígenes concretos, validación de todas las entradas con Pydantic, comprobación de propiedad en cada recurso, protección contra inyección de fórmulas en el CSV y ningún secreto en el repositorio. En producción debe usarse **HTTPS**.

## Mejoras Futuras

- *Refresh tokens* de 7 días y revocación de tokens.
- Limitador de peticiones compartido (Redis) para varios procesos.
- Migraciones de base de datos con Alembic.
- Despliegue automático desde `main` (Render/Railway).
- Datos de evolución en la v2 de la Pokédex.
