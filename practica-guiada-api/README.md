# Práctica guiada · Tu primera API REST completa

**Sistemas de Información · Universidad Francisco de Vitoria · Curso 2025-26**
Módulo 2 · Clase 3 (FastAPI) · Lunes 19 de octubre de 2026

Hoy construimos juntos, en clase, la **Pokédex API** de la Práctica 1 hasta dejarla funcionando: entorno, modelos, autenticación y el CRUD completo del Pokédex conectado a la PokeAPI. Lo que se queda fuera —el formato único de errores, las pruebas, el despliegue y los equipos— lo terminas tú en la Práctica 1, con los anexos A y B de las diapositivas como guía.

Tú escribes el código. Este paquete no es la solución: es la red de seguridad para que nadie se quede atrás.

## Qué hay en este paquete

| Fichero o carpeta | Para qué sirve |
|---|---|
| `README.md` | Estas instrucciones. |
| `comprobar.py` | Un comprobador que pregunta a **tu** API si hace lo que hemos visto en clase y te dice, con la diapositiva, qué falla. |
| `puntos-de-control/hito-1-esqueleto/` | El proyecto tal y como queda al terminar el hito 1. |
| `puntos-de-control/hito-2-modelos/` | … al terminar el hito 2. |
| `puntos-de-control/hito-3-autenticacion/` | … al terminar el hito 3. |
| `puntos-de-control/hito-4-pokedex/` | … al terminar el hito 4. |

## Antes de empezar

Necesitas un editor (VS Code vale), un terminal y **uv**. uv descarga él mismo Python 3.12 si no lo tienes, así que no hace falta instalar Python aparte.

**macOS y Linux**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell)**

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Cierra el terminal, abre uno nuevo y comprueba que responde:

```bash
uv --version
```

## Cómo se trabaja hoy

1. Crea tu proyecto en una carpeta tuya, **fuera** de este paquete, y escribe el código a medida que avance la clase. Cada diapositiva con código lleva el nombre del fichero en la cabecera.
2. Arranca el servidor y déjalo corriendo en un terminal. Con `--reload` se reinicia solo cada vez que guardas:
   ```bash
   uv run uvicorn app.main:app --reload
   ```
3. Al cerrar cada hito, copia `comprobar.py` a la carpeta de tu proyecto y lánzalo en **otro** terminal, con el número del hito:
   ```bash
   python comprobar.py 2        # en Windows también vale: py comprobar.py 2
   ```
   Cada línea en rojo trae una pista y la diapositiva donde está la respuesta.
4. Prueba también a mano desde <http://localhost:8000/docs>: es la documentación interactiva que FastAPI genera sola, y el botón **Authorize** sirve para iniciar sesión con tu usuario.

### Si te quedas atrás

No pasa nada, y no hace falta que copies a toda prisa. Copia el punto de control del último hito terminado en una carpeta nueva y sigue desde ahí:

```bash
cp -r puntos-de-control/hito-3-autenticacion ~/pokedex-api-h3
cd ~/pokedex-api-h3
cp .env.example .env              # en Windows: copy .env.example .env
uv sync                           # instala las versiones exactas del uv.lock
uv run uvicorn app.main:app --reload
```

Después compara con calma tu versión con la del punto de control: la diferencia es exactamente lo que se te había escapado.

## Los cuatro hitos de hoy

### Hito 1 · El entorno y el esqueleto (diapositivas 9–20)

```bash
uv init pokedex-api --python 3.12
cd pokedex-api
uv add "fastapi[standard]" sqlmodel pydantic-settings
uv add "python-jose[cryptography]" bcrypt httpx slowapi
uv add --dev pytest pytest-cov ruff
mkdir -p app/routers app/services tests
```

Crea `app/__init__.py`, `app/routers/__init__.py` y `app/services/__init__.py` vacíos. Escribe `app/config.py` (diap. 15), `app/database.py` (diap. 17) y un `app/main.py` mínimo con el `lifespan` y `GET /health`. Copia `.env.example` a `.env` y pon una clave propia en `SECRET_KEY`:

```bash
uv run python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Está bien si** `python comprobar.py 1` sale en verde y <http://localhost:8000/docs> muestra «Pokédex API».

### Hito 2 · Los modelos (diapositivas 21–36)

Todo `app/models.py`: usuario, entrada del Pokédex, equipo y miembro del equipo, cada uno con su Base, su tabla y sus contratos Create, Read y Update. Mientras no haya routers que importen los modelos, añade en `main.py` la línea `from app import models` para que SQLModel conozca las tablas antes de crearlas.

Si añades una tabla o una columna después de haber arrancado una vez, **borra `pokedex.db`** y vuelve a arrancar: `create_all` crea las tablas que faltan, pero no modifica las que ya existen.

**Está bien si** `python comprobar.py 2` sale en verde. Para ver el SQL que has generado sin escribirlo: `sqlite3 pokedex.db .schema` (diap. 34).

### Hito 3 · La autenticación (diapositivas 37–54)

`app/auth.py` (bcrypt y JWT), `app/limits.py` (el limitador), `app/dependencies.py` (`SessionDep` y `CurrentUser`) y `app/routers/auth.py` (registro y login). En `main.py`: CORS, el registro de peticiones, el limitador y `include_router`.

**Está bien si** `python comprobar.py 3` sale en verde y puedes pulsar **Authorize** en `/docs` con tu usuario.

### Hito 4 · El Pokédex (diapositivas 55–70)

`app/services/pokeapi_service.py`, el `get_pokeapi_service` de `dependencies.py`, `app/routers/pokemon.py` y `app/routers/pokedex.py` con POST, GET con filtros, GET de detalle, PATCH, DELETE y `stats`.

**Está bien si** `python comprobar.py` (sin número: comprueba los cuatro) sale entero en verde.

## Lo que queda para la Práctica 1

| Hito | Qué | Guía |
|---|---|---|
| 5 · Errores y límites | El manejador único de errores 422 y los códigos correctos en todos los endpoints. | Anexo A, diapositivas 78–91 |
| 6 · Pruebas y documentación | `tests/` con al menos 15 pruebas y más del 80 % de cobertura, `README.md`, `SECURITY.md` y `requirements.txt`. | Anexo B, diapositivas 92–106 |
| Opcional · Equipos | `app/routers/teams.py`: equipos de hasta seis Pokémon de tu Pokédex. | Diapositivas 71–72 |

Antes de entregar, clona tu repositorio en una carpeta limpia y móntalo siguiendo tu propio README (diap. 75).

## Problemas frecuentes

| Lo que ves | Por qué pasa | Qué hacer |
|---|---|---|
| `ValidationError … secret_key Field required` al arrancar | No hay `.env`, o no tiene `SECRET_KEY`. Es deliberado (diap. 16). | `cp .env.example .env` y pon una clave. Arranca desde la carpeta del proyecto. |
| `uv init` te ha creado `src/pokedex_api/` y un bloque `[build-system]` | Las versiones recientes de uv generan un paquete instalable. | Puedes dejarlo tal cual. Si borras `src/`, borra también `[build-system]` y `[project.scripts]` de `pyproject.toml`; si dejas uno sin el otro, `uv sync` falla. |
| `AttributeError: module 'bcrypt' has no attribute '__about__'` | Estás usando passlib, que no funciona con bcrypt 5 (diap. 44). | Usa `bcrypt.hashpw` y `bcrypt.checkpw` directamente, como en la diap. 43. |
| `no such table` o `no such column` | La base de datos es de antes de tu último cambio en los modelos. | Para el servidor, borra `pokedex.db` y vuelve a arrancar. |
| `ModuleNotFoundError: No module named 'app'` | Has lanzado uvicorn desde otra carpeta. | Lánzalo desde la raíz del proyecto, donde está `pyproject.toml`. |
| `429 Too Many Requests` en el registro | El límite de 5 registros por hora está funcionando. | Reinicia el servidor: el contador vive en memoria y se pone a cero. |
| `GET /pokedex/stats` responde 422 | `/stats` está declarada después de `/{entry_id}` y FastAPI intenta leer «stats» como número. | Declárala antes (diap. 70). |
| `Address already in use` | Ya tienes otro uvicorn en el puerto 8000. | Ciérralo con Ctrl+C o usa `--port 8001` (y `python comprobar.py --url http://localhost:8001`). |
| En `/docs` sale 401 aunque has hecho login | Has llamado a `/auth/login` a mano, pero no has pulsado **Authorize**. | Pulsa **Authorize**, escribe usuario y contraseña, y repite la petición. |

## Recursos

- FastAPI: <https://fastapi.tiangolo.com/es/>
- SQLModel: <https://sqlmodel.tiangolo.com/>
- uv: <https://docs.astral.sh/uv/>
- PokeAPI: <https://pokeapi.co/docs/v2>
- jwt.io, para abrir un testigo y ver lo que lleva dentro: <https://jwt.io/>
