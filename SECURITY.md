# Consideraciones de Seguridad

## Autenticación

- Al hacer login se emite un **JWT** firmado con HS256 usando `SECRET_KEY`.
- Claims: `sub` (username), `user_id`, `iat` (emisión) y `exp` (caducidad).
- **Caducidad: 24 horas** (`access_token_expire_minutes`). No hay refresh tokens (mejora futura).
- Cada endpoint protegido valida el token (firma, caducidad y que el usuario exista y esté activo). Un token no válido devuelve `401` sin dar pistas del motivo.
- El login responde con el mismo mensaje si el usuario no existe o la contraseña es incorrecta, para no revelar qué usuarios hay registrados.

## Contraseñas

- Algoritmo: **bcrypt**, con sal aleatoria por contraseña. Nunca se guardan ni se devuelven en texto plano (el esquema de salida no incluye `hashed_password`).
- Política: mínimo 8 caracteres, al menos una mayúscula y un número. El email se valida con `EmailStr`.

## Rate Limiting

| Endpoint | Límite | Motivo |
|---|---|---|
| `POST /auth/register` | 5/hora por IP | Evita crear cuentas en masa |
| `POST /auth/login` | 10/minuto por IP | Frena la fuerza bruta |
| `/pokemon/*` y export de equipo | 30/minuto | Llaman a un servicio externo |
| Resto (Pokédex, equipos) | 100/minuto | Uso normal, sólo base de datos |

Al excederlo se responde `429` y se registra en el log. Limitación conocida: los contadores viven en memoria de un solo proceso.

## CORS

- Orígenes permitidos (configurables con `CORS_ORIGINS`): `http://localhost:3000` y `http://localhost:5173` en desarrollo; en producción se añade el dominio real.
- Métodos: GET, POST, PUT, PATCH, DELETE. Cabeceras: `Authorization` y `Content-Type`.
- Es necesario porque los navegadores bloquean por defecto que una web llame a una API de otro origen; así sólo las webs autorizadas pueden hacerlo.

## Variables de Entorno

- `SECRET_KEY` (firma de JWT), `DATABASE_URL` (puede contener credenciales) y `CORS_ORIGINS`.
- Viven en `.env`, que está en `.gitignore`; el repositorio sólo contiene `.env.example` con valores de ejemplo. Sin `SECRET_KEY` la aplicación **no arranca**, a propósito.
- En producción se configuran en el panel de la plataforma o en los *secrets* de GitHub, nunca en el código. Si una clave se sube por error, hay que **rotarla**: borrar el fichero no basta porque queda en el historial.
- Usar **HTTPS** en producción: sin él, el token viaja en claro.

## Vulnerabilidades Conocidas

OWASP API Security Top 10 (2023):

| Riesgo | Mitigación |
|---|---|
| API1 · Autorización a nivel de objeto | Cada consulta filtra por `owner_id`/`trainer_id`; lo ajeno devuelve 404 |
| API2 · Autenticación rota | bcrypt, JWT con caducidad, límite en login y registro |
| API3 · Autorización a nivel de propiedad | Esquemas de entrada/salida explícitos; no se expone `hashed_password`; PATCH sólo acepta campos permitidos |
| API4 · Consumo de recursos sin límite | Rate limiting, paginación con máximo (100), *timeouts* en la PokeAPI, concurrencia acotada |
| API5 · Autorización a nivel de función | No hay roles de administrador; todo endpoint de datos exige usuario autenticado |
| API6 · Flujos de negocio sensibles | Registro limitado por IP; máximo 6 Pokémon por equipo |
| API7 · SSRF | La URL de la PokeAPI viene de configuración; los identificadores se validan con una lista blanca de caracteres; los sprites sólo por `https` |
| API8 · Mala configuración | CORS restringido, `SECRET_KEY` obligatoria, errores sin trazas internas |
| API9 · Inventario inadecuado | Versionado `/api/v1` y `/api/v2`, documentación automática en `/docs` |
| API10 · Consumo inseguro de APIs | Se valida y simplifica la respuesta de la PokeAPI; errores externos se traducen a 502/504 |

Otras medidas: **inyección SQL** evitada al usar el ORM y traducir `sort` con una lista cerrada; **inyección de fórmulas en CSV** evitada prefijando con comilla los valores que empiezan por `= + - @`; los logs no guardan contraseñas ni cuerpos de petición.

Limitaciones asumidas: los JWT no se pueden revocar antes de caducar, el limitador es por proceso y no hay refresh tokens.
