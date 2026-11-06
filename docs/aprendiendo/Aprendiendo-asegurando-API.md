# Aprendiendo: Asegurando una API con JWT, Bcrypt y TinyDB

> **Nota**: Este documento es pedagógico (ignorado por git). Aquí aprendemos paso a paso
> cómo añadir autenticación con JWT a la API de Nexova usando FastAPI + TinyDB.

---

## Unidad 1: Fundamentos de Seguridad — Dependencias y utilidades JWT

### ¿Qué vamos a hacer?

Vamos a añadir autenticación a la API de Nexova usando **JWT (JSON Web Tokens)** y
**bcrypt** para proteger contraseñas. Antes de escribir modelos o endpoints,
necesitamos instalar las herramientas adecuadas y crear los módulos de seguridad
básicos.

### Paso 1: Dependencias (pyproject.toml)

Añadimos al `pyproject.toml` tres nuevas dependencias:

```toml
dependencies = [
    # ... existentes ...
    "python-jose[cryptography]>=3.3,<4",
    "libpass[bcrypt]>=1.9,<2",
    "python-dotenv>=1.0,<2",
]
```

**¿Qué hace cada una?**

| Dependencia | Propósito |
|---|---|
| `python-jose[cryptography]` | Crear y verificar tokens JWT. El extra `[cryptography]` usa la librería `cryptography` para firmar con HMAC-SHA256. |
| `libpass[bcrypt]` | Hashear contraseñas con bcrypt. El extra `[bcrypt]` instala el backend nativo C de bcrypt. |
| `python-dotenv` | Cargar automáticamente variables de entorno desde un archivo `.env`. |

### Paso 2: Archivo `.env` y configuración

Creamos `services/api/.env` (NO se sube a git):

```
SECRET_KEY=lmYuem7k_PYMxxDdTW1HTd7Wt_ZANWUYXkCbuL4OpVw
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

Y `services/api/.env.example` (SÍ se sube a git) como plantilla.

### Paso 3: `app/auth/config.py`

```python
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv
import os

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

SECRET_KEY = os.environ.get("SECRET_KEY", "")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY no está definida en el entorno")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
ACCESS_TOKEN_EXPIRE_DELTA = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
```

**Conceptos clave:**

- `load_dotenv()` busca el archivo `.env` y carga sus variables en `os.environ`.
- El path relativo `parents[2]` sube dos niveles desde `app/auth/config.py` hasta `services/api/`.
- Si no hay `SECRET_KEY`, la aplicación **no arranca** (RuntimeError).
- `ALGORITHM = "HS256"` es el algoritmo HMAC-SHA256 que usa JWT.

### Paso 4: `app/auth/security.py`

```python
from passlib.hash import bcrypt
from jose import jwt
from datetime import datetime, timezone

def hash_password(password: str) -> str:
    return bcrypt.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.verify(plain, hashed)

def create_access_token(data: dict, expires_delta: timedelta) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_access_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
```

**Conceptos clave:**

- **bcrypt**: función de hashing lenta (deliberadamente). Un hash de bcrypt incluye:
  - El prefijo `$2b$` (versión)
  - El cost factor (ej. `$2b$12$` significa 2¹² iteraciones)
  - Una sal aleatoria de 22 caracteres
  - El hash propiamente dicho
  - Ejemplo: `$2b$12$LJ3m...`
- **JWT**: un token contiene tres partes separadas por puntos:
  1. **Header**: `{"alg":"HS256","typ":"JWT"}` (base64url)
  2. **Payload**: los datos que firmamos, ej. `{"sub":"user@example.com","exp":...}` (base64url)
  3. **Signature**: HMAC-SHA256(header + "." + payload, SECRET_KEY)
- El campo `exp` (expiration) es **crítico**: JWT valida automáticamente que no haya expirado.
- `timezone.utc` es importante para evitar ambigüedades con husos horarios.

### ¿Qué hemos aprendido en la Unidad 1?

1. Cómo configurar dependencias de seguridad en Python.
2. Qué es bcrypt y por qué se usa para almacenar contraseñas.
3. Qué es JWT y cómo se estructura (header + payload + firma).
4. Cómo se gestionan secretos con variables de entorno.
5. Por qué NO se debe hardcodear una SECRET_KEY en el código fuente.
6. El patrón de separar configuración (`config.py`) de operaciones (`security.py`).

---

## Unidad 2: Modelos User y Profile en TinyDB

### ¿Qué vamos a hacer?

Vamos a crear los **modelos de datos** (User y Profile) y sus **repositorios**
para persistirlos en TinyDB. Esta será la base de datos de autenticación,
separada de la base de datos de suppliers.

### ¿Por qué una BD separada?

- **Principio de responsabilidad única**: la BD de auth almacena usuarios y perfiles;
  la BD de suppliers almacena proveedores.
- **Aislamiento**: podemos reiniciar los datos de auth sin afectar a suppliers.
- **Claridad**: cada base de datos tiene un propósito claro.

### Estructura de archivos creados

```
services/api/app/auth/
├── __init__.py         # (Ya existía de la Unidad 1)
├── config.py           # (Ya existía de la Unidad 1)
├── security.py         # (Ya existía de la Unidad 1)
├── database.py         # (NUEVO) Inicialización TinyDB para auth
├── models.py           # (NUEVO) Modelos User, Profile, UserRole
└── repository.py       # (NUEVO) Repositorios UserRepository, ProfileRepository
```

### `app/auth/database.py`

```python
from pathlib import Path
from tinydb import TinyDB, table

def create_database(db_path: str | Path | None = None) -> TinyDB:
    if db_path is None:
        db_path = Path(__file__).resolve().parents[3] / "data" / "auth.json"
    return TinyDB(str(db_path))

def get_users_table(db: TinyDB) -> table.Table:
    return db.table("users")

def get_profiles_table(db: TinyDB) -> table.Table:
    return db.table("profiles")
```

**Conceptos clave:**

- TinyDB permite múltiples **tablas** dentro de un mismo archivo JSON mediante `db.table("nombre")`.
- `parents[3]` sube tres niveles: `app/auth/database.py` → `app/` → `services/` → raíz del proyecto.
- El `db_path` es configurable mediante variable de entorno `AUTH_DB_PATH`.

### `app/auth/models.py`

```python
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, EmailStr, Field, ConfigDict

class UserRole(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    USER = "user"

class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(min_length=1)

class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr | None = None
    role: UserRole | None = None

class User(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int
    email: str
    hashed_password: str
    is_active: bool = True
    role: UserRole = UserRole.USER
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def from_create(cls, user_id: int, payload: UserCreate, hashed: str) -> "User":
        return cls(
            id=user_id,
            email=payload.email,
            hashed_password=hashed,
        )

class ProfileCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    phone: str | None = None
    address: str | None = None

class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    phone: str | None = None
    address: str | None = None

class Profile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int
    user_id: int
    name: str | None = None
    phone: str | None = None
    address: str | None = None

    @classmethod
    def from_create(cls, profile_id: int, user_id: int, payload: ProfileCreate) -> "Profile":
        return cls(id=profile_id, user_id=user_id, **payload.model_dump())
```

**Conceptos clave:**

1. **`UserRole(str, Enum)`**: Un Enum de strings que restringe los roles a exactamente `admin`, `manager`, `user`. Pydantic rechaza automáticamente cualquier valor que no esté en el enum.

2. **`EmailStr`**: Tipo Pydantic que valida formato de email. Requiere la dependencia `email-validator`.

3. **`ConfigDict(extra="forbid")`**: Impide que se pasen campos extraños. Si alguien intenta crear un UserCreate con un campo `foo`, Pydantic lanza un error.

4. **`from_create`** (classmethod): Patrón para separar la creación del modelo (que requiere datos ya procesados) del modelo de entrada (validación del usuario). El `User.from_create` recibe el **hash de bcrypt**, no la contraseña original.

5. **`Field(default_factory=...)`**: Permite que cada instancia tenga su propio `datetime` en el momento de creación, no compartido.

6. **`Profile.user_id`**: Relación 1:1 con User. El repositorio busca perfiles por `user_id`, no por `id` de perfil.

### `app/auth/repository.py`

```python
from tinydb import TinyDB, Query
from app.auth.models import User, UserCreate, UserUpdate, Profile, ProfileCreate, ProfileUpdate
from app.auth.database import get_users_table, get_profiles_table

class UserRepository:
    def __init__(self, db: TinyDB):
        self.table = get_users_table(db)

    def create(self, payload: UserCreate, hashed_password: str) -> User:
        doc_id = self.table.insert({
            "email": payload.email,
            "hashed_password": hashed_password,
            "is_active": True,
            "role": "user",
        })
        return User.from_create(doc_id, payload, hashed_password)

    def get(self, user_id: int) -> User | None:
        doc = self.table.get(doc_id=user_id)
        return User(**doc) if doc else None

    def get_by_email(self, email: str) -> User | None:
        UserQuery = Query()
        doc = self.table.get(UserQuery.email == email)
        return User(**doc) if doc else None

    def list(self) -> list[User]:
        return [User(**doc) for doc in self.table.all()]

    def update(self, user_id: int, payload: UserUpdate) -> User | None:
        changes = payload.model_dump(exclude_none=True)
        if not changes:
            return self.get(user_id)
        self.table.update(changes, doc_ids=[user_id])
        return self.get(user_id)

    def delete(self, user_id: int) -> bool:
        return bool(self.table.remove(doc_ids=[user_id]))
```

**Conceptos clave del repositorio:**

- **`Query()`** de TinyDB permite búsquedas por campo (ej. `UserQuery.email == email`).
- **`doc_ids=[user_id]`** permite operar por ID de documento (que es el mismo que nuestro `user_id`).
- **`exclude_none=True`** en `model_dump()` evita sobrescribir campos con `None`.
- Si no hay cambios, `update()` retorna el usuario actual sin tocar la BD.

El `ProfileRepository` sigue el mismo patrón pero con un detalle importante:

```python
class ProfileRepository:
    def __init__(self, db: TinyDB):
        self.table = get_profiles_table(db)

    def create(self, user_id: int, payload: ProfileCreate) -> Profile:
        doc_id = self.table.insert({"user_id": user_id, **payload.model_dump()})
        return Profile.from_create(doc_id, user_id, payload)

    def get_by_user_id(self, user_id: int) -> Profile | None:
        ProfileQuery = Query()
        doc = self.table.get(ProfileQuery.user_id == user_id)
        return Profile(**doc) if doc else None

    def update(self, user_id: int, payload: ProfileUpdate) -> Profile | None:
        ProfileQuery = Query()
        changes = payload.model_dump(exclude_none=True)
        if not changes:
            return self.get_by_user_id(user_id)
        self.table.update(changes, ProfileQuery.user_id == user_id)
        return self.get_by_user_id(user_id)

    def delete_by_user_id(self, user_id: int) -> bool:
        ProfileQuery = Query()
        removed = self.table.remove(ProfileQuery.user_id == user_id)
        return len(removed) > 0
```

**Detalle importante**: `ProfileRepository.update()` actualiza por `user_id`,
no por `profile_id`. Esto está diseñado intencionadamente para el futuro endpoint
`/profiles/me`, donde el usuario autenticado actualizará su propio perfil sin
necesidad de conocer el ID del perfil.

### La relación User ↔ Profile

| Aspecto | Detalle |
|---|---|
| Cardinalidad | 1 User : 1 Profile (relación 1:1) |
| Clave foránea | `Profile.user_id` apunta a `User.id` |
| ¿TinyDB impone la unicidad? | No. TinyDB no tiene constraints. La unicidad se gestiona desde la lógica de negocio. |
| Eliminación | Se debe eliminar el Profile **primero**, luego el User (cascade manual). |

### Tests (`test_auth_unit2.py`)

43 tests distribuidos en 6 clases:

| Clase de test | Tests | ¿Qué verifica? |
|---|---|---|
| `UserModelTests` | 10 | Validación de campos, `EmailStr`, `from_create`, UTC, rol por defecto |
| `UserRepositoryTests` | 14 | CRUD completo, búsqueda por email, listado vacío, eliminación |
| `ProfileModelTests` | 3 | Campos requeridos, `from_create` con/sin opcionales |
| `ProfileRepositoryTests` | 11 | CRUD por `user_id`, relación 1:1, aislamiento entre usuarios |
| `UserProfileIntegrationTests` | 1 | Eliminación en cascada: Profile → User |
| `UserRoleTests` | 4 | Exactamente 3 roles, valores correctos, rechazo de inválidos |

### ¿Qué hemos aprendido en la Unidad 2?

1. Cómo modelar entidades de autenticación (User + Profile) con Pydantic v2.
2. Cómo usar TinyDB con múltiples tablas para separar dominios.
3. El patrón Repository para abstraer la persistencia.
4. Por qué se separa `UserCreate` (input del usuario) de `User` (modelo persistido).
5. Cómo usar `EmailStr` y `ConfigDict(extra="forbid")` para validación estricta.
6. Cómo usar Enums de string para roles con tipado estático.
7. La importancia de TinyDB `doc_id` como identificador único.
8. Por qué los tests deben usar `TemporaryDirectory` para no contaminar la BD real.

---

## Unidad 3: Auth Service + JWT + get_current_user

### ¿Qué vamos a hacer?

Vamos a crear el **servicio de autenticación** (`AuthService`) y la **dependencia `get_current_user`** que permitirá proteger rutas mediante JWT. Esta unidad introduce una **capa de servicio** entre los endpoints HTTP y el repositorio.

### Arquitectura en capas

```
FastAPI Router
    ↓ (dependencia)
get_current_user (dependencies.py)
    ↓
AuthService (service.py)
    ↓
UserRepository (repository.py)
    ↓
TinyDB (database.py)
```

El `AuthService` nunca accede a TinyDB directamente. Todo el acceso a datos pasa por `UserRepository`.

### `app/auth/service.py`

```python
class AuthenticationError(Exception):
    """Error genérico de autenticación. No revela detalles internos."""

class AuthService:
    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository

    def authenticate(self, email: str, password: str) -> User:
        user = self.repository.get_by_email(email)
        if user is None or not verify_password(password, user.hashed_password):
            raise AuthenticationError("Invalid credentials")
        if not user.is_active:
            raise AuthenticationError("Invalid credentials")
        return user

    def create_token(self, user: User) -> str:
        return create_access_token(
            data={"sub": str(user.id)},
            expires_delta=ACCESS_TOKEN_EXPIRE_DELTA,
        )
```

**Conceptos clave:**

1. **`AuthenticationError`**: Excepción personalizada genérica. El mensaje es siempre `"Invalid credentials"` independientemente de si falló email, password o usuario inactivo. Esto evita **filtración de información** (no le decimos al atacante *qué* campo está mal).

2. **`sub` es el user_id, no el email**: El JWT almacena `str(user.id)` en el campo `sub`. Esto es importante porque:
   - Los IDs son inmutables (el email podría cambiar).
   - Los IDs son secuenciales y compactos.
   - Si usáramos el email en `sub`, cualquier cambio de email invalidaría el token.

3. **`AuthService.create_token`** delega en `security.create_access_token`, agregando el ID del usuario como `sub`.

### `app/auth/dependencies.py`

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import ExpiredSignatureError, JWTError

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def get_repository() -> UserRepository:
    db = get_database()
    return UserRepository(db)

def get_current_user(
    token: str = Depends(_oauth2_scheme),
    repository: UserRepository = Depends(get_repository),
) -> User:
    try:
        payload = decode_access_token(token)
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    sub = payload.get("sub")
    if sub is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = int(sub)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = repository.get(user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user
```

**Conceptos clave:**

1. **`OAuth2PasswordBearer(tokenUrl="/auth/login")`**: Esquema de seguridad de FastAPI que:
   - Extrae el token del header `Authorization: Bearer <token>`.
   - Si no hay token, retorna 401 automáticamente.
   - `tokenUrl` informa a Swagger/OpenAPI dónde enviar las credenciales.
   - NO valida el token — solo lo extrae.

2. **Flujo de `get_current_user`**:
   - **Paso 1 — Decodificar JWT**: `decode_access_token()` lanza `ExpiredSignatureError` si expiró o `JWTError` si la firma es inválida.
   - **Paso 2 — Extraer `sub`**: El claim `sub` debe existir y ser un string convertible a int.
   - **Paso 3 — Buscar usuario**: `repository.get(user_id)` retorna `None` si no existe.
   - **Paso 4 — Verificar activo**: `user.is_active` debe ser `True`.
   - **Cualquier fallo → 401 con `WWW-Authenticate: Bearer`**.

3. **`get_repository()` es público**: Se declara como función pública para que los tests puedan sobrescribirla mediante `app.dependency_overrides[get_repository]`. Así los tests usan una TinyDB temporal en lugar de `data/auth.json`.

4. **401 vs 403**:
   - **401 Unauthorized**: El cliente no está autenticado o el token no es válido. Siempre incluye `WWW-Authenticate: Bearer`.
   - **403 Forbidden**: El cliente está autenticado pero no tiene permiso para acceder al recurso. **NO se usa en auth** — reservado para autorización (Unidad 4+).

5. **Stateless**: La API no guarda sesiones. Cada request debe incluir el JWT. No hay estado en el servidor más allá de la clave secreta.

### Tests (`test_auth_unit3.py`)

19 tests distribuidos en 3 clases:

| Clase de test | Tests | ¿Qué verifica? |
|---|---|---|
| `AuthServiceTests` | 9 | `authenticate` (válido, email inválido, password incorrecta, usuario inactivo, mensaje genérico), `create_token` (sub, exp, sin email) |
| `GetCurrentUserTests` | 10 | Token válido retorna User; token expirado, firma inválida, malformado, sin sub, sub inválido → 401; usuario inexistente, inactivo → 401; token ausente → 401; header `WWW-Authenticate: Bearer` |
| `AuthHttpSemanticTests` | 1 | Verifica que ningún error de autenticación devuelve 403 (solo 401) |

### Aislamiento de BD en tests

Para que `get_current_user` no consulte la BD real (`data/auth.json`) durante los tests:

```python
def _make_test_app(repo: UserRepository) -> FastAPI:
    app = FastAPI()

    def _override_repo() -> UserRepository:
        return repo

    app.dependency_overrides[get_repository] = _override_repo

    @app.get("/me")
    def _read_me(user: User = Depends(get_current_user)) -> User:
        return user

    return app
```

Así los tests crean una TinyDB en `TemporaryDirectory`, crean usuarios allí, y la app consulta esa BD temporal.

### PENDIENTE para Unidad 4

- Endpoints CRUD de usuarios (crear, listar, obtener, actualizar, eliminar)
- Endpoint `/auth/login` que recibe email+password y retorna un JWT
- Proteger rutas con `Depends(get_current_user)`
- Manejo de roles y autorización (permisos)

### ¿Qué hemos aprendido en la Unidad 3?

1. Cómo separar la capa de servicio (`AuthService`) del repositorio y los endpoints.
2. Cómo se obtiene el usuario actual mediante un JWT en el header `Authorization: Bearer`.
3. La diferencia entre autenticación (401) y autorización (403).
4. Por qué los mensajes de error deben ser genéricos ("Invalid credentials").
5. Cómo hacer tests de dependencias FastAPI con `dependency_overrides`.
6. El patrón stateless: no hay sesión en el servidor, todo está en el token.
7. Por qué `sub` debe ser el user_id (inmutable) y no el email (cambiable).

---

## Unidad 4: Auth + Users + Profiles HTTP API

### ¿Qué vamos a hacer?

Vamos a crear todos los **endpoints HTTP** de autenticación, gestión de usuarios y perfiles. Esta unidad completa la API de auth con:

- `POST /api/auth/login` — Iniciar sesión y obtener un JWT
- `GET /api/auth/me` — Obtener el usuario autenticado (con su perfil)
- CRUD completo de usuarios (`/api/users/*`)
- GET/PUT del perfil propio (`/api/profiles/me`)
- Reglas de autorización por roles (self, admin, manager)

### Arquitectura final de auth

```
services/api/app/auth/
├── __init__.py
├── config.py             # (Unidad 1) Variables de entorno
├── security.py           # (Unidad 1) Hashing + JWT
├── database.py           # (Unidad 2) TinyDB
├── models.py             # (Unidad 2) User, Profile, UserRole
├── repository.py         # (Unidad 2) UserRepository, ProfileRepository
├── service.py            # (Unidad 3) AuthService
├── dependencies.py       # (Unidad 3) get_current_user, get_repository, get_profile_repository
├── schemas.py            # (NUEVO) Esquemas de request/response (sin hashed_password)
└── routers/
    ├── auth_router.py    # (NUEVO) POST /api/auth/login, GET /api/auth/me
    ├── users_router.py   # (NUEVO) CRUD /api/users/**
    └── profiles_router.py# (NUEVO) GET/PUT /api/profiles/me
```

### `app/auth/schemas.py` — Esquemas de request/response

Los schemas de respuesta **nunca exponen `hashed_password`**:

```python
class TokenResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    access_token: str
    token_type: str = "bearer"

class UserMeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int
    email: str
    is_active: bool
    role: UserRole
    created_at: datetime
    profile: Profile | None = None

class UserResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int
    email: str
    is_active: bool
    role: UserRole
    created_at: datetime

class UserCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(min_length=1)
    is_active: bool = True
    role: UserRole = UserRole.USER
    profile: ProfileCreate | None = None

class UserUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr | None = None
    role: UserRole | None = None
```

**Puntos clave**:
- `UserResponse` solo expone campos seguros: nunca `hashed_password`.
- `UserMeResponse` incluye el perfil anidado (`Profile | None`).
- `UserUpdateRequest` no permite cambiar la contraseña (eso será en Unidad 5).
- `extra="forbid"` evita inyección de campos no solicitados (ej. `user_id` en update de perfil).

### `app/auth/routers/auth_router.py` — Login y /me

```python
router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/login")
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    try:
        user = service.authenticate(form.username, form.password)
    except AuthenticationError:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = service.create_token(user)
    return TokenResponse(access_token=token)

@router.get("/me")
def me(
    current_user: User = Depends(get_current_user),
    profile_repo: ProfileRepository = Depends(get_profile_repository),
) -> UserMeResponse:
    profile = profile_repo.get_by_user_id(current_user.id)
    return UserMeResponse(**current_user.model_dump(), profile=profile)
```

**¿Qué es `OAuth2PasswordRequestForm`?**
Es un formulario OAuth2 estándar con campos `username` y `password`. FastAPI lo provee para compatibilidad con Swagger UI. Cuando el usuario hace clic en "Authorize" en Swagger, Swagger envía las credenciales a `tokenUrl="/api/auth/login"`.

### `app/auth/routers/users_router.py` — CRUD de usuarios

```python
router = APIRouter(prefix="/api/users", tags=["users"])

@router.post("", status_code=201)
def create_user(
    payload: UserCreateRequest,
    repo: UserRepository = Depends(get_repository),
    profile_repo: ProfileRepository = Depends(get_profile_repository),
) -> UserResponse:
    """Público (no requiere auth)."""
    hashed = hash_password(payload.password)
    user = repo.create_with_attrs(
        payload, hashed,
        is_active=payload.is_active,
        role=payload.role,
    )
    if payload.profile:
        try:
            profile_repo.create(user.id, payload.profile)
        except Exception:
            repo.delete(user.id)
            raise HTTPException(500, "Profile creation failed")
    return UserResponse(**user.model_dump(include={"id", "email", "is_active", "role", "created_at"}))

@router.get("")
def list_users(
    current_user: User = Depends(get_current_user),
    repo: UserRepository = Depends(get_repository),
) -> list[UserResponse]:
    return [UserResponse(**u.model_dump()) for u in repo.list()]

@router.get("/{user_id}")
def get_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    repo: UserRepository = Depends(get_repository),
) -> UserResponse:
    target = repo.get(user_id)
    if target is None:
        raise HTTPException(404, "User not found")
    if current_user.id != target.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(403, "Forbidden")
    return UserResponse(**target.model_dump())

@router.put("/{user_id}")
def update_user(
    user_id: int,
    payload: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    repo: UserRepository = Depends(get_repository),
) -> UserResponse:
    target = repo.get(user_id)
    if target is None:
        raise HTTPException(404, "User not found")
    if current_user.id != target.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(403, "Forbidden")
    if current_user.id != target.id and payload.role is not None and current_user.role != UserRole.ADMIN:
        raise HTTPException(403, "Only admin can change role")
    if current_user.id == target.id and payload.role is not None and current_user.role != UserRole.ADMIN:
        raise HTTPException(403, "You cannot change your own role")
    updated = repo.update(user_id, payload)
    return UserResponse(**updated.model_dump())

@router.delete("/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    repo: UserRepository = Depends(get_repository),
    profile_repo: ProfileRepository = Depends(get_profile_repository),
) -> None:
    target = repo.get(user_id)
    if target is None:
        raise HTTPException(404, "User not found")
    if current_user.id != target.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(403, "Forbidden")
    profile_repo.delete_by_user_id(user_id)
    repo.delete(user_id)
```

**Reglas de autorización**:

| Operación | Self | Admin | Manager | User |
|---|---|---|---|---|
| `GET /api/users` | — | ✅ | ✅ | ✅ |
| `GET /api/users/{id}` (propio) | ✅ | ✅ | — | — |
| `GET /api/users/{id}` (otro) | — | ✅ | ❌ 403 | ❌ 403 |
| `PUT /api/users/{id}` (self, email) | ✅ | ✅ | — | — |
| `PUT /api/users/{id}` (cambio de rol) | ❌ 403 | ✅ | ❌ 403 | ❌ 403 |
| `DELETE /api/users/{id}` | ✅ | ✅ | ❌ 403 | ❌ 403 |

### `app/auth/routers/profiles_router.py` — Perfil propio

```python
router = APIRouter(prefix="/api/profiles", tags=["profiles"])

@router.get("/me")
def get_my_profile(
    current_user: User = Depends(get_current_user),
    profile_repo: ProfileRepository = Depends(get_profile_repository),
) -> Profile:
    profile = profile_repo.get_by_user_id(current_user.id)
    if profile is None:
        raise HTTPException(404, "Profile not found")
    return profile

@router.put("/me")
def update_my_profile(
    payload: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    profile_repo: ProfileRepository = Depends(get_profile_repository),
) -> Profile:
    existing = profile_repo.get_by_user_id(current_user.id)
    if existing is None:
        raise HTTPException(404, "Profile not found")
    updated = profile_repo.update(current_user.id, payload)
    return updated
```

**Importante**: `ProfileUpdate` usa `extra="forbid"`, por lo que no se puede enviar `user_id` o `id` en el body. El cliente solo puede modificar `name`, `phone` y `address`.

---

### Registro de routers en `main.py`

```python
from app.auth.routers.auth_router import router as auth_router
from app.auth.routers.users_router import router as users_router
from app.auth.routers.profiles_router import router as profiles_router

app = FastAPI(title="Nexova API")
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(profiles_router)
app.include_router(suppliers_router)  # existente de Units anteriores
```

### 401 vs 403 — La diferencia clave

| Código | Significado | Cuándo usarlo |
|---|---|---|
| **401 Unauthorized** | No autenticado o token inválido | Token faltante, expirado, firma inválida, usuario inactivo. Siempre con `WWW-Authenticate: Bearer`. |
| **403 Forbidden** | Autenticado pero sin permiso | Un usuario no-admin intenta acceder/modificar/eliminar a otro usuario. |
| **404 Not Found** | El recurso no existe | `GET /users/999` cuando el ID 999 no existe. |

### ¿Cómo probar manualmente en Swagger?

1. Arranca la API: `uvicorn app.main:app --port 8000`.
2. Abre `http://localhost:8000/docs`.
3. **Crear usuario**: `POST /api/users` — sin Authorize. Usa el botón "Try it out".
4. **Iniciar sesión**: `POST /api/auth/login` — Swagger espera `OAuth2PasswordRequestForm`. Introduce email en "username" y la contraseña.
5. **Authorize**: Copia el `access_token` de la respuesta, haz clic en "Authorize" en Swagger y pégalo como `Bearer <token>`.
6. **Probar rutas protegidas**: Ahora `GET /api/auth/me`, `GET /api/users`, etc. funcionarán.

### Tests (`test_auth_unit4.py`)

62 tests distribuidos en 10 clases:

| Clase de test | Tests | ¿Qué verifica? |
|---|---|---|
| `AuthLoginTests` | 7 | Login válido → 200 + token, token_type=bearer, credenciales inválidas → 401, inactivo → 401, compatible OAuth2 |
| `AuthMeTests` | 8 | /me con token válido, con Profile, sin Profile, sin hashed_password, sin token, token inválido |
| `CreateUserTests` | 7 | Creación pública, password hasheada, sin hashed_password en respuesta, rol por defecto, custom, con/sin profile |
| `ListUsersTests` | 3 | Autenticado → 200, sin token → 401, sin hashed_password |
| `GetUserTests` | 6 | Self → 200, admin → otro, user→otro → 403, manager→otro → 403, inexistente → 404 |
| `UpdateUserTests` | 9 | Self email, admin cambia rol, user cambia otro → 403, manager cambia otro → 403, self cambia rol → 403 |
| `DeleteUserTests` | 6 | Self, admin, user→otro → 403, manager→otro → 403, elimina también Profile |
| `GetProfileMeTests` | 4 | Con perfil → 200, sin perfil → 404, sin token → 401 |
| `UpdateProfileMeTests` | 6 | Actualizar name/phone/address, evitar user_id → 422 (extra="forbid") |
| `AuthSemanticTests` | 3 | Endpoints protegidos sin token → 401, token inválido → 401, error de autorización → 403 |

### Aislamiento de BD en tests

Similar a Unit 3, los tests de Unit 4 sobrescriben **ambos** repositorios:

```python
app.dependency_overrides[get_repository] = lambda: repo
app.dependency_overrides[get_profile_repository] = lambda: profile_repo
```

Así `data/auth.json` nunca se toca durante los tests. Cada test usa `TemporaryDirectory`.

### ¿Qué hemos aprendido en la Unidad 4?

1. Cómo crear endpoints HTTP protegidos con `Depends(get_current_user)`.
2. La diferencia entre 401 (no autenticado) y 403 (sin permiso).
3. Cómo implementar autorización por roles (self, admin, manager).
4. Cómo separar schemas de request (con password) de schemas de response (sin password).
5. Cómo Swagger UI se comunica con el backend mediante OAuth2PasswordBearer.
6. El patrón de compensación: si falla la creación del Profile, se elimina el User.
7. Por qué `profiles/me` no acepta `user_id`: el servidor lo obtiene del token JWT.
8. Cómo se elimina el Profile antes que el User (cascade manual).

---

## Unidad 5: Protección de rutas existentes con JWT

### ¿Qué vamos a hacer?

Vamos a proteger los **endpoints de suppliers** (que ya existían antes de implementar autenticación) mediante JWT, reutilizando `Depends(get_current_user)` de la Unidad 3.

Los endpoints de incidents se analizan por separado y se decide mantenerlos públicos.

### Rutas inspeccionadas

#### Suppliers (6 endpoints — SENSIBLES → protegidos)

| Endpoint | Operación | ¿Por qué es sensible? |
|---|---|---|
| `POST /api/suppliers` | Crear proveedor | Añade un nuevo partner de negocio al sistema |
| `GET /api/suppliers` | Listar proveedores | Expone datos de la red de suministro |
| `GET /api/suppliers/{id}` | Obtener proveedor | Datos detallados de un partner |
| `PATCH /api/suppliers/{id}/rate` | Actualizar tarifa | Modifica condiciones económicas |
| `PATCH /api/suppliers/{id}/status` | Cambiar estado | Activar/suspender un partner |
| `DELETE /api/suppliers/{id}` | Eliminar proveedor | Elimina un partner del sistema |

**Decisión**: Los 6 endpoints son operaciones CRUD sobre datos de negocio estratégicos (directorio de proveedores). Cualquier acceso no autenticado podría exponer o modificar información sensible de la red de suministro. Se protegen todos.

#### Incidents (2 endpoints — HERRAMIENTA → públicos)

| Endpoint | Operación | ¿Por qué se deja público? |
|---|---|---|
| `POST /api/incidents/analyze` | Subir CSV y obtener análisis | Herramienta de análisis, no expone datos persistentes |
| `GET /api/incidents/results/export` | Descargar último resultado | Exporta solo métricas agregadas (sin emails, sin datos raw) |

**Decisión**: Son endpoints funcionales de análisis. No gestionan datos persistentes del sistema. Las respuestas ya están sanitizadas (no incluyen emails ni datos raw). No hay especificación que exija protección. Se mantienen públicos.

### Cómo se implementa la protección

Se añade `Depends(get_current_user)` como dependencia en cada función de ruta de suppliers. El mismo `get_current_user` de la Unidad 3 se reutiliza **sin modificaciones**:

```python
from app.auth.dependencies import get_current_user
from app.auth.models import User

@router.post("", response_model=Supplier, status_code=201)
def create_supplier(
    payload: SupplierCreate,
    current_user: User = Depends(get_current_user),   # ← NUEVO
    repository: SupplierRepository = Depends(get_repository),
) -> Supplier:
    return repository.create(payload)
```

No se introducen nuevas reglas de autorización por roles en esta unidad. Cualquier usuario autenticado puede acceder a los endpoints de suppliers. La protección se limita a verificar que el token JWT sea válido.

### Impacto en tests existentes

Los tests funcionales de suppliers (`test_supplier_api.py`) necesitan sobrescribir `get_current_user` mediante `app.dependency_overrides` para poder ejecutarse sin un token real:

```python
_FAKE_USER = User(id=999, email="test@nexova.com", hashed_password="fake",
                  is_active=True, role=UserRole.ADMIN, created_at=...)

def setUp(self):
    app.dependency_overrides[get_current_user] = lambda: _FAKE_USER
    ...

def tearDown(self):
    app.dependency_overrides.pop(get_current_user, None)
    ...
```

### Tests Unit 5 (`test_auth_unit5.py`)

22 tests distribuidos en 3 clases:

| Clase de test | Tests | ¿Qué verifica? |
|---|---|---|
| `SupplierAuthTests` | 18 | 6 endpoints × (sin token → 401 + token inválido → 401 + token válido → accesible) |
| `IncidentsPublicTests` | 2 | Incidents siguen públicos (devuelven 400/404, no 401) |
| `AuthSemanticTests` | 2 | 401 incluye `WWW-Authenticate: Bearer` con/sin token inválido |

### ¿Cómo probar manualmente en Swagger?

1. **Sin token**: Abre cualquier endpoint de suppliers (ej. `GET /api/suppliers`) → 401.
2. **Login**: `POST /api/auth/login` con email+password de un usuario existente.
3. **Authorize**: Copia el `access_token` y haz clic en "Authorize" en Swagger → `Bearer <token>`.
4. **Repetir endpoint**: Ahora `GET /api/suppliers` → 200.
5. **Token inválido**: En "Authorize", introduce un token basura → 401.

### Resultado de la regresión

```
Unit 5 tests:         22/22  OK
Auth cumulative:     165/165 OK  (19+43+19+62+22)
Full suite:          215 tests — FAILED (6 failures, 7 errors)
   → 3× ConfigTests          (pre-existente: orden alfabético)
   → 3× IncidentCliTests     (pre-existente: falta incidents-nexova.csv)
   → 7× incidents errors     (pre-existente: falta incidents-nexova.csv)
   → 0 regresiones nuevas de Unit 5 ✅
```

### Mapa completo de rutas (públicas vs protegidas)

```
🔓 POST /api/auth/login              → Público (emite tokens)
🔒 GET  /api/auth/me                 → Autenticado
🔓 POST /api/users                   → Público (registro)
🔒 GET  /api/users                   → Autenticado
🔒 GET  /api/users/{id}              → Autenticado + autorización
🔒 PUT  /api/users/{id}              → Autenticado + autorización
🔒 DELETE /api/users/{id}            → Autenticado + autorización
🔒 GET  /api/profiles/me             → Autenticado
🔒 PUT  /api/profiles/me             → Autenticado
🔒 POST /api/suppliers               → Autenticado (NUEVO)
🔒 GET  /api/suppliers               → Autenticado (NUEVO)
🔒 GET  /api/suppliers/{id}          → Autenticado (NUEVO)
🔒 PATCH /api/suppliers/{id}/rate    → Autenticado (NUEVO)
🔒 PATCH /api/suppliers/{id}/status  → Autenticado (NUEVO)
🔒 DELETE /api/suppliers/{id}        → Autenticado (NUEVO)
🔓 POST /api/incidents/analyze      → Público
🔓 GET  /api/incidents/results/export → Público
```

### ¿Qué hemos aprendido en la Unidad 5?

1. Cómo proteger rutas existentes sin cambiar su lógica funcional.
2. A reutilizar `Depends(get_current_user)` en cualquier router.
3. La diferencia entre rutas sensibles (CRUD de datos de negocio) y herramientas de análisis.
4. Cómo adaptar tests existentes con `dependency_overrides`.
5. Cómo comprobar que un endpoint devuelve 401 en lugar de 403 cuando no hay token.
6. Que no todos los endpoints necesitan protección — depende del contexto de negocio.
7. El esquema de seguridad Swagger/OpenAPI se reutiliza, no se duplica.

### PENDIENTE para futuras unidades

- Protección granular por roles en suppliers (admin vs manager vs user)
- Endpoint de cambio de contraseña
- Refresh token / rotación de claves
- Rate limiting
- Logging de accesos

---

## Resumen del progreso

```
Unidad 1 (COMPLETADA) ──► Dependencias + config.py + security.py + tests (19 tests)
Unidad 2 (COMPLETADA) ──► database.py + models.py + repository.py + tests (43 tests)
Unidad 3 (COMPLETADA) ──► Auth service + JWT + get_current_user + tests (19 tests)
Unidad 4 (COMPLETADA) ──► Auth + Users + Profiles HTTP API + tests (62 tests)
Unidad 5 (COMPLETADA) ──► Protección rutas suppliers + tests (22 tests)
```