# Book Store (FastAPI) — Build From Scratch, Step by Step

This is a **hands-on build manual**. Follow it top to bottom and you will recreate
the entire project from an empty folder: environment, configuration, the database
tables, the validation schemas, the auth guards, every router (JSON API + HTML web),
the templates, and the final wiring — then run it.

It uses the **feature-first** layout (each domain is its own package). Cross-cutting
infrastructure lives in `app/core/`; shared auth guards live in `app/auth/`.

> **How to read this:** each step says *which file to create*, *the full code to put
> in it*, and *why*. Type the code yourself — you learn far more than copy-pasting.

---

## 0. Prerequisites

| Need | Why | Check |
|------|-----|-------|
| Python 3.11+ | Modern typing (`str \| None`, `Mapped[...]`) | `python --version` |
| MySQL running | The app stores data here (XAMPP is fine) | XAMPP → Start MySQL |
| A code editor | VS Code recommended | — |

---

## 1. Create the project skeleton

Open PowerShell and run:

```powershell
# 1. Make and enter the project folder
mkdir Book_Store_FastAPI
cd Book_Store_FastAPI

# 2. Create an isolated virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1      # prompt now shows (.venv)

# 3. Create the package folders
mkdir app
mkdir app\core
mkdir app\auth app\books app\cart app\wishlist app\address app\orders app\feedback
mkdir app\dashboard app\users app\password
mkdir app\templates app\static\book-covers
```

Every Python package needs an `__init__.py` so Python treats the folder as importable.
Create an **empty** `__init__.py` in `app` and in every sub-package:

```powershell
# Empty package markers
ni app\__init__.py
ni app\core\__init__.py
foreach ($f in 'auth','books','cart','wishlist','address','orders','feedback','dashboard','users','password') { ni app\$f\__init__.py }
```

You will end up with this structure (files added over the next steps):

```
Book_Store_FastAPI/
├── run.py
├── requirements.txt
├── .env  /  .env.example
└── app/
    ├── main.py
    ├── core/        config.py · database.py · security.py · templating.py
    ├── auth/        models.py · schemas.py · dependencies.py · api.py · web.py
    ├── books/       models.py · schemas.py · api.py · web.py
    ├── cart/  wishlist/  address/  orders/  feedback/   (same shape)
    ├── dashboard/  users/  password/   (web.py only)
    ├── templates/   base.html + per-feature .html
    └── static/book-covers/
```

---

## 2. Install the libraries

Create **`requirements.txt`**:

```
fastapi
uvicorn[standard]
sqlalchemy
pymysql
pydantic[email]
pydantic-settings
passlib[bcrypt]
pyjwt
jinja2
python-multipart
itsdangerous
```

Then install:

```powershell
pip install -r requirements.txt
```

What each one does:

| Library | Role |
|---------|------|
| **fastapi** | The web framework (routes, validation, dependency injection). |
| **uvicorn** | The ASGI server that runs the app. |
| **sqlalchemy** | The ORM — Python classes instead of raw SQL. |
| **pymysql** | The driver SQLAlchemy uses to reach MySQL. |
| **pydantic / -settings** | Validates request bodies and loads typed settings from `.env`. |
| **passlib[bcrypt]** | Hashes passwords (compatible with Laravel's `$2y$`). |
| **pyjwt** | Creates/reads the JWT token for the API. |
| **jinja2** | HTML templating for the web UI. |
| **python-multipart** | Lets FastAPI read HTML form posts and file uploads. |
| **itsdangerous** | Signs the session cookie so it can't be tampered with. |

---

## 3. Configuration — `app/core/config.py`

Everything else needs settings (DB credentials, secret key). Read them from a `.env`
file using Pydantic so they are typed and validated.

**`app/core/config.py`**

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Book Store"
    secret_key: str = "insecure-dev-secret-change-me"
    access_token_expire_minutes: int = 1440
    algorithm: str = "HS256"

    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_database: str = "book_store_product"
    db_username: str = "root"
    db_password: str = ""

    create_tables: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.db_username}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_database}?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
```

Now create your secret file **`.env`** (and a committable template `.env.example`):

```
APP_NAME=Book Store
SECRET_KEY=change-me-to-a-long-random-string
DB_HOST=127.0.0.1
DB_PORT=3306
DB_DATABASE=book_store_product
DB_USERNAME=root
DB_PASSWORD=
CREATE_TABLES=true
```

> **Why a `database_url` property?** The rest of the app never assembles the
> connection string by hand — it just asks `settings.database_url`. Field names like
> `DB_PASSWORD` in `.env` map automatically to `db_password`.

---

## 4. The database engine — `app/core/database.py`

This file opens the connection pool, gives each request its own short-lived session,
and defines the `Base` class plus a `TimestampMixin` that every table reuses.

**`app/core/database.py`**

```python
from collections.abc import Generator
from datetime import datetime

from sqlalchemy import DateTime, create_engine, func
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from .config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


class Base(DeclarativeBase):
    """Every model inherits from this. It carries the table metadata."""
    pass


class TimestampMixin:
    """Adds created_at / updated_at to any model that mixes it in."""
    created_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: open a session, hand it over, always close it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

> **Key idea — `get_db`:** any endpoint that needs the database writes
> `db: Session = Depends(get_db)`. FastAPI runs `get_db`, gives you a session, and the
> `finally` guarantees it is closed. You never leak connections.

---

## 5. Passwords + tokens — `app/core/security.py`

**`app/core/security.py`**

```python
from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from .config import settings

# bcrypt accepts both `$2y$` (Laravel/PHP) and `$2b$` hashes — fully interoperable.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(plain, hashed)
    except ValueError:
        return False


def create_access_token(subject: str | int, expires_minutes: int | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.access_token_expire_minutes
    )
    payload = {"sub": str(subject), "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> str | None:
    """Return the subject (user id as str) or None if the token is invalid/expired."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload.get("sub")
    except jwt.PyJWTError:
        return None
```

- **Hashing** means a database leak never exposes real passwords.
- **JWT** is a signed string proving "I am user 5" without a server-side session — the
  API door uses it. (The web door uses a cookie session instead; see step 11.)

---

## 6. Creating the database tables (models)

This is the heart of "table creation". In SQLAlchemy you **describe a table as a Python
class**; on startup `Base.metadata.create_all()` issues the `CREATE TABLE` for any table
that does not yet exist. One class = one table, one `mapped_column` = one column.

There are **7 tables**, each owned by its feature package:

| Table | Class | Lives in | Belongs to feature |
|-------|-------|----------|--------------------|
| `users` | `User` | `app/auth/models.py` | auth |
| `books` | `Book` | `app/books/models.py` | books |
| `carts` | `Cart` | `app/cart/models.py` | cart |
| `wishlists` | `WishList` | `app/wishlist/models.py` | wishlist |
| `addresses` | `Address` | `app/address/models.py` | address |
| `orders` | `Order` | `app/orders/models.py` | orders |
| `feedbacks` | `Feedback` | `app/feedback/models.py` | feedback |

> **Cross-feature links without circular imports.** A `User` *has many* `Book`s, but
> `auth/models.py` must not import `books/models.py` at load time (and vice-versa). The
> trick: reference the other class by **string name** in `relationship("Book")`, and put
> the real import behind `TYPE_CHECKING` (used only by type-checkers, never at runtime).
> SQLAlchemy resolves the string later, once every model has been imported.

### 6.1 `users` — `app/auth/models.py`

```python
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.address.models import Address
    from app.books.models import Book
    from app.cart.models import Cart
    from app.feedback.models import Feedback
    from app.wishlist.models import WishList


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role: Mapped[str] = mapped_column(String(255), default="user")   # "user" | "admin"
    first_name: Mapped[str] = mapped_column(String(255))
    last_name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    phone_no: Mapped[str] = mapped_column(String(255))
    password: Mapped[str] = mapped_column(String(255))               # stores the HASH

    # one User → many of each (string class names = no import cycles)
    books: Mapped[list["Book"]] = relationship(back_populates="user")
    carts: Mapped[list["Cart"]] = relationship(back_populates="user")
    wishlists: Mapped[list["WishList"]] = relationship(back_populates="user")
    addresses: Mapped[list["Address"]] = relationship(back_populates="user")
    feedbacks: Mapped[list["Feedback"]] = relationship(back_populates="user")
```

### 6.2 `books` — `app/books/models.py`

```python
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.auth.models import User


class Book(Base, TimestampMixin):
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(String(1000))
    author: Mapped[str] = mapped_column(String(255))
    image: Mapped[str] = mapped_column(String(255))
    price: Mapped[str] = mapped_column("price", String(255))
    quantity: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped["User"] = relationship(back_populates="books")
```

> `ForeignKey("users.id")` is what makes `books.user_id` point at `users.id`. The
> `back_populates` on both sides keeps the Python objects in sync (a `Book.user` and the
> matching `User.books` are two views of the same link).

### 6.3 `carts` — `app/cart/models.py`

```python
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.auth.models import User
    from app.books.models import Book


class Cart(Base, TimestampMixin):
    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    book_id: Mapped[int] = mapped_column(Integer, ForeignKey("books.id"))
    book_quantity: Mapped[int] = mapped_column(Integer, default=1)

    user: Mapped["User"] = relationship(back_populates="carts")
    book: Mapped["Book"] = relationship()
```

### 6.4 `wishlists` — `app/wishlist/models.py`

```python
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.auth.models import User
    from app.books.models import Book


class WishList(Base, TimestampMixin):
    __tablename__ = "wishlists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    book_id: Mapped[int] = mapped_column(Integer, ForeignKey("books.id"))

    user: Mapped["User"] = relationship(back_populates="wishlists")
    book: Mapped["Book"] = relationship()
```

### 6.5 `addresses` — `app/address/models.py`

```python
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.auth.models import User


class Address(Base, TimestampMixin):
    __tablename__ = "addresses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    address: Mapped[str] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(255))
    state: Mapped[str] = mapped_column(String(255))
    landmark: Mapped[str] = mapped_column(String(255))
    pincode: Mapped[int] = mapped_column(Integer)
    address_type: Mapped[str] = mapped_column(String(255), default="home")

    user: Mapped["User"] = relationship(back_populates="addresses")
```

### 6.6 `orders` — `app/orders/models.py`

```python
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.address.models import Address
    from app.auth.models import User
    from app.books.models import Book


class Order(Base, TimestampMixin):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    book_id: Mapped[int] = mapped_column(Integer, ForeignKey("books.id"))
    address_id: Mapped[int] = mapped_column(Integer, ForeignKey("addresses.id"))
    order_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    user: Mapped["User"] = relationship()
    book: Mapped["Book"] = relationship()
    address: Mapped["Address"] = relationship()
```

### 6.7 `feedbacks` — `app/feedback/models.py`

```python
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.auth.models import User
    from app.books.models import Book


class Feedback(Base, TimestampMixin):
    __tablename__ = "feedbacks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    book_id: Mapped[int] = mapped_column(Integer, ForeignKey("books.id"))
    feedback: Mapped[str] = mapped_column(String(255))
    rating: Mapped[int] = mapped_column(Integer)

    user: Mapped["User"] = relationship(back_populates="feedbacks")
    book: Mapped["Book"] = relationship()
```

> **When do the tables actually get created?** Not yet. They are created in step 12,
> when `main.py`'s startup hook runs `Base.metadata.create_all(bind=engine)`. By then
> `main.py` has imported every router (which import every model), so SQLAlchemy knows all
> 7 tables and emits the `CREATE TABLE` statements for any that are missing.

---

## 7. Validation schemas (Pydantic) — per feature `schemas.py`

A **model** is a database table (SQLAlchemy). A **schema** is the *shape of a
request/response* (Pydantic). If an incoming JSON body does not match the schema,
FastAPI rejects it with a `422` **before your code runs**.

### 7.1 `app/auth/schemas.py`

```python
from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    role: str = Field(pattern="^(user|admin)$")
    first_name: str = Field(min_length=2, max_length=50)
    last_name: str = Field(min_length=2, max_length=50)
    phone_no: str = Field(min_length=10)
    email: EmailStr = Field(max_length=100)
    password: str = Field(min_length=6)
    confirm_password: str

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v, info):
        if v != info.data.get("password"):
            raise ValueError("confirm_password must match password")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr = Field(max_length=100)


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=6)
    confirm_password: str

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v, info):
        if v != info.data.get("new_password"):
            raise ValueError("confirm_password must match new_password")
        return v
```

### 7.2 `app/books/schemas.py`

```python
from pydantic import BaseModel, ConfigDict, Field


class BookCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str = Field(min_length=5, max_length=1000)
    author: str = Field(min_length=5, max_length=300)
    image: str
    price: float = Field(ge=0, alias="Price")
    quantity: int = Field(ge=0)
    model_config = ConfigDict(populate_by_name=True)


class BookUpdate(BaseModel):
    id: int
    name: str = Field(min_length=2, max_length=100)
    description: str = Field(min_length=5, max_length=1000)
    author: str = Field(min_length=5, max_length=300)
    price: float = Field(ge=0, alias="Price")
    model_config = ConfigDict(populate_by_name=True)


class BookId(BaseModel):
    id: int


class AddQuantity(BaseModel):
    id: int
    quantity: int = Field(ge=1)


class SearchRequest(BaseModel):
    search: str
```

### 7.3 The smaller schemas (cart, wishlist, address, orders, feedback)

```python
# app/cart/schemas.py
from pydantic import BaseModel
class BookIdRequest(BaseModel):     book_id: int
class CartIdRequest(BaseModel):     cart_id: int
class WishlistIdRequest(BaseModel): wishlist_id: int

# app/wishlist/schemas.py
from pydantic import BaseModel
class BookIdRequest(BaseModel):     book_id: int
class WishlistIdRequest(BaseModel): wishlist_id: int

# app/address/schemas.py
from pydantic import BaseModel, Field
class AddressCreate(BaseModel):
    address: str = Field(min_length=2, max_length=600)
    city: str = Field(min_length=2, max_length=100)
    state: str = Field(min_length=2, max_length=100)
    landmark: str = Field(min_length=2, max_length=100)
    pincode: int
    address_type: str = Field(min_length=2, max_length=100)
class AddressUpdate(AddressCreate): id: int
class AddressId(BaseModel):         id: int

# app/orders/schemas.py
from pydantic import BaseModel, Field
class OrderRequest(BaseModel):
    name: str
    address_id: int
    quantity: int = Field(ge=1)

# app/feedback/schemas.py
from pydantic import BaseModel, Field
class FeedbackRequest(BaseModel):
    book_id: int
    feedback: str = Field(min_length=4, max_length=1000)
    rating: int = Field(ge=1, le=5)
class AverageRatingRequest(BaseModel):
    book_id: int
```

---

## 8. The auth guards — `app/auth/dependencies.py`

"Dependencies" are reusable checks attached to endpoints. They answer *"who are you,
and are you allowed here?"* in one place. They live in `auth` because every other
feature imports them.

**`app/auth/dependencies.py`**

```python
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token

from .models import User


class RedirectException(Exception):
    """Raised by web guards to bounce the browser to another URL with a flash."""
    def __init__(self, url: str, error: str | None = None, status: str | None = None):
        self.url = url
        self.error = error
        self.status = status


# ---- API door (JWT) ----
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_api_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authorization token not found")
    sub = decode_access_token(credentials.credentials)
    if sub is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    user = db.get(User, int(sub))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user


def require_api_role(role: str):
    """Factory: returns a guard that also checks the user's role."""
    def checker(user: User = Depends(get_current_api_user)) -> User:
        if user.role != role:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Only {role}s are allowed to do this")
        return user
    return checker


# ---- Web door (cookie session) ----
def get_optional_web_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.get(User, int(user_id))


def require_web_user(request: Request, db: Session = Depends(get_db)) -> User:
    user = get_optional_web_user(request, db)
    if user is None:
        raise RedirectException("/login", error="Please sign in to continue.")
    return user


def require_web_role(role: str):
    def checker(user: User = Depends(require_web_user)) -> User:
        if user.role != role:
            raise RedirectException("/dashboard", error="You are not allowed to access that area.")
        return user
    return checker
```

> **The payoff:** an admin-only endpoint just writes
> `admin: User = Depends(require_api_role("admin"))`. No auth code is repeated inside the
> endpoint — the guard runs first, and if it fails the endpoint body never executes.

---

## 9. The routers (the endpoints)

Each feature exposes its URLs through two routers: **`api.py`** (returns JSON, JWT
guarded) and **`web.py`** (returns HTML/redirects, cookie-session guarded). Read the
first example slowly — every line maps to a layer you already built.

### 9.1 `app/auth/api.py` — register / login / logout / password

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token, hash_password, verify_password

from .dependencies import get_current_api_user
from .models import User
from .schemas import ForgotPasswordRequest, LoginRequest, RegisterRequest, ResetPasswordRequest

router = APIRouter(tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == payload.email)):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "The email has already been taken")
    user = User(
        role=payload.role, first_name=payload.first_name, last_name=payload.last_name,
        phone_no=payload.phone_no, email=payload.email,
        password=hash_password(payload.password),
    )
    db.add(user); db.commit(); db.refresh(user)
    return {"status": 201, "message": "User successfully registered", "user_id": user.id}


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email))
    if not user or not verify_password(payload.password, user.password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password")
    token = create_access_token(user.id)
    return {"access_token": token, "token_type": "bearer", "expires_in": 3600}


@router.post("/logout")
def logout(_: User = Depends(get_current_api_user)):
    return {"status": 200, "message": "User successfully logged out"}  # JWT is stateless


@router.post("/forgotPassword")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email))
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "we can not find the user with that e-mail address")
    return {"status": 200, "message": "Password reset token generated", "token": create_access_token(user.id)}


@router.post("/resetPassword")
def reset_password(payload: ResetPasswordRequest,
                   user: User = Depends(get_current_api_user),
                   db: Session = Depends(get_db)):
    user.password = hash_password(payload.new_password)
    db.commit()
    return {"status": 201, "message": "Password reset successful!"}
```

### 9.2 `app/books/api.py` — the canonical CRUD example

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_api_user, require_api_role
from app.auth.models import User
from app.core.database import get_db

from .models import Book
from .schemas import AddQuantity, BookCreate, BookId, BookUpdate, SearchRequest

router = APIRouter(tags=["books"])


def _serialize(b: Book) -> dict:
    return {"id": b.id, "name": b.name, "description": b.description, "author": b.author,
            "image": b.image, "Price": b.price, "quantity": b.quantity}


@router.post("/addingBook", status_code=201)
def adding_book(
    payload: BookCreate,                               # ← schema validates the body
    admin: User = Depends(require_api_role("admin")),  # ← guard: must be admin
    db: Session = Depends(get_db),                     # ← a DB session, auto-closed
):
    book = Book(user_id=admin.id, name=payload.name, description=payload.description,
                author=payload.author, image=payload.image,
                price=str(payload.price), quantity=payload.quantity)
    db.add(book); db.commit(); db.refresh(book)        # ← INSERT into `books`
    return {"status": 201, "message": "Book created successfully", "book": _serialize(book)}


@router.post("/updateBookById")
def update_book(payload: BookUpdate, admin: User = Depends(require_api_role("admin")),
                db: Session = Depends(get_db)):
    book = db.get(Book, payload.id)
    if not book:
        raise HTTPException(404, "Could not find a book with that id")
    book.name, book.description = payload.name, payload.description
    book.author, book.price = payload.author, str(payload.price)
    db.commit()
    return {"status": 201, "message": "Book updated successfully"}


@router.post("/deleteBookById")
def delete_book(payload: BookId, admin: User = Depends(require_api_role("admin")),
                db: Session = Depends(get_db)):
    book = db.get(Book, payload.id)
    if not book:
        raise HTTPException(404, "Could not find a book with that id")
    db.delete(book); db.commit()
    return {"status": 201, "message": "Book deleted Successfully"}


@router.get("/displayAllBooks")
def display_all_books(_: User = Depends(get_current_api_user), db: Session = Depends(get_db)):
    books = db.scalars(select(Book).order_by(Book.name)).all()
    return {"status": 200, "books": [_serialize(b) for b in books]}


@router.post("/searchBookByKeyword")
def search_book(payload: SearchRequest, _: User = Depends(get_current_api_user),
                db: Session = Depends(get_db)):
    like = f"%{payload.search}%"
    books = db.scalars(select(Book).where(or_(Book.name.like(like), Book.author.like(like)))).all()
    return {"status": 200, "books": [_serialize(b) for b in books]}
```

> That `adding_book` function **is the whole architecture in miniature**: schema (7) →
> guard (8) → session (4) → model (6) → DB. Every other endpoint is a variation on it.
> The full project also has `addQuantityToExistBook`, `sortPriceLowToHigh`,
> `sortPriceHighToLow` — same pattern.

### 9.3 The remaining API routers (same recipe)

Each one is `APIRouter(...)` + a role guard + `select`/`db.get` + `commit`. Build them
the same way:

- **`app/cart/api.py`** — `addBookToCartByBookId`, `getAllBooksInCart`,
  `deleteBookByCartId`, `increamentBookQuantityInCart`, `decrementBookQuantityInCart`,
  `addBookToCartByWishlistId`. Guard: `require_api_role("user")`.
- **`app/wishlist/api.py`** — `addBookToWishlistByBookId`, `getAllBooksInWishlist`,
  `deleteBookByWishlistId`.
- **`app/address/api.py`** — `addAddress`, `updateAddress`, `deleteAddress`, `getAddress`.
- **`app/orders/api.py`** — `placeOrder` (checks stock, decrements `books.quantity`,
  generates a random `order_id`).
- **`app/feedback/api.py`** — `feedback`, `getAverageRatingByBookId` (uses
  `func.avg(Feedback.rating)`).

Example of the "owns this row" check used throughout the user features:

```python
# inside app/cart/api.py
@router.post("/deleteBookByCartId")
def delete_book_by_cart_id(payload: CartIdRequest,
                           user: User = Depends(require_api_role("user")),
                           db: Session = Depends(get_db)):
    cart = db.get(Cart, payload.cart_id)
    if not cart or cart.user_id != user.id:          # ← never trust the id alone
        raise HTTPException(404, "Cart not found for this user")
    db.delete(cart); db.commit()
    return {"status": 201, "message": "Book deleted from cart Successfully"}
```

### 9.4 The web routers — `app/<feature>/web.py`

The web version of any feature returns a **redirect + flash message** instead of JSON,
and reads **form fields** (`Form(...)`) instead of a JSON schema. Example —
`app/books/web.py` (store a new book with a cover upload):

```python
@router.post("")
def store(request: Request,
          name: str = Form(...), author: str = Form(...), description: str = Form(...),
          Price: float = Form(...), quantity: int = Form(...),
          image: UploadFile = File(...),
          user: User = Depends(require_web_role("admin")),
          db: Session = Depends(get_db)):
    image_url = _save_image(image)                       # write file under static/
    db.add(Book(user_id=user.id, name=name, author=author, description=description,
                image=image_url, price=str(Price), quantity=quantity))
    db.commit()
    flash(request, f'Book "{name}" created successfully.')  # one-time message
    return RedirectResponse("/books", status_code=303)      # Post/Redirect/Get
```

> **Why redirect after a POST (the PRG pattern)?** So a browser refresh does not resubmit
> the form. The success message survives the redirect via a one-time "flash" stored in the
> signed session cookie.

The web routers to build (each an `APIRouter(prefix="/<feature>")`):

| File | Prefix | Pages / actions |
|------|--------|-----------------|
| `app/auth/web.py` | (root) | `/login`, `/register`, `/logout`, `/` → `/dashboard` |
| `app/dashboard/web.py` | (root) | `/dashboard` (admin vs user counts) |
| `app/books/web.py` | `/books` | list, create, edit, update, add-quantity, delete |
| `app/cart/web.py` | `/cart` | list, add, increment, decrement, delete |
| `app/wishlist/web.py` | `/wishlist` | list, add, move-to-cart, delete |
| `app/address/web.py` | `/address` | list, create, edit, update, delete |
| `app/orders/web.py` | `/orders` | list (own/all), place order |
| `app/feedback/web.py` | `/feedback` | submit feedback, show average |
| `app/users/web.py` | `/users` | admin-only directory of accounts |
| `app/password/web.py` | `/password` | forgot (token) + reset |

---

## 10. Web rendering — `app/core/templating.py` + `app/templates/`

**`app/core/templating.py`** sets up Jinja2 and a `render()` helper that always injects
the current user + any flash messages.

```python
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .config import settings

if TYPE_CHECKING:
    from app.auth.models import User

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def flash(request: Request, message: str, category: str = "status") -> None:
    request.session.setdefault("_flash", {})[category] = message


def flash_errors(request: Request, errors: list[str], old: dict[str, Any] | None = None) -> None:
    request.session["_errors"] = errors
    request.session["_old"] = old or {}


def _pop(request: Request, key: str, default: Any):
    return request.session.pop(key, default)


def render(request: Request, template: str, context: dict[str, Any] | None = None,
           *, user: "User | None" = None, status_code: int = 200) -> HTMLResponse:
    flash_messages = _pop(request, "_flash", {})
    base = {
        "app_name": settings.app_name, "current_user": user,
        "status": flash_messages.get("status"), "error": flash_messages.get("error"),
        "errors": _pop(request, "_errors", []), "old": _pop(request, "_old", {}),
    }
    if context:
        base.update(context)
    return templates.TemplateResponse(request, template, base, status_code=status_code)
```

**`app/templates/base.html`** is the shared skeleton; every page extends it:

```html
<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>{{ app_name }}</title></head>
<body>
  <nav>
    {% if current_user %}
      Hi {{ current_user.first_name }} ·
      <a href="/dashboard">Dashboard</a> · <a href="/books">Books</a>
      <form action="/logout" method="post" style="display:inline">
        <button>Logout</button></form>
    {% else %}
      <a href="/login">Login</a> · <a href="/register">Register</a>
    {% endif %}
  </nav>

  {% if status %}<p class="ok">{{ status }}</p>{% endif %}
  {% if error %}<p class="err">{{ error }}</p>{% endif %}
  {% for e in errors %}<p class="err">{{ e }}</p>{% endfor %}

  {% block content %}{% endblock %}
</body>
</html>
```

A page template just fills the `content` block, e.g. **`app/templates/books/index.html`**:

```html
{% extends "base.html" %}
{% block content %}
  {% for book in books %}
    <div class="card">{{ book.name }} — ₹{{ book.price }} · {{ book.author }}</div>
  {% endfor %}
{% endblock %}
```

Create the template folders/files you reference: `auth/login.html`, `auth/register.html`,
`dashboard.html`, `books/index.html`, `books/edit.html`, `cart/index.html`,
`wishlist/index.html`, `address/index.html`, `address/edit.html`, `orders/index.html`,
`feedback.html`, `users/index.html`, `password/index.html`.

---

## 11. Wire it all together — `app/main.py`

Built last because it imports everything. It creates the app, enables the session
cookie, mounts static files, **creates the tables on startup**, registers the
web-redirect/validation exception handlers, and includes every router.

**`app/main.py`**

```python
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.address import api as address_api, web as address_web
from app.auth import api as auth_api, web as auth_web
from app.auth.dependencies import RedirectException
from app.books import api as books_api, web as books_web
from app.cart import api as cart_api, web as cart_web
from app.core.config import settings
from app.core.database import Base, engine
from app.core.templating import flash, flash_errors
from app.dashboard import web as dashboard_web
from app.feedback import api as feedback_api, web as feedback_web
from app.orders import api as orders_api, web as orders_web
from app.password import web as password_web
from app.users import web as users_web
from app.wishlist import api as wishlist_api, web as wishlist_web

app = FastAPI(title=f"{settings.app_name} API", version="1.0.0")
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, max_age=60 * 60 * 24 * 7)

STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(exist_ok=True)
(STATIC_DIR / "book-covers").mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.on_event("startup")
def on_startup():
    if settings.create_tables:
        Base.metadata.create_all(bind=engine)        # ← CREATE TABLE for all 7 tables


@app.exception_handler(RedirectException)
async def redirect_exception_handler(request: Request, exc: RedirectException):
    if exc.error:  flash(request, exc.error, "error")
    if exc.status: flash(request, exc.status, "status")
    return RedirectResponse(exc.url, status_code=303)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    if request.url.path.startswith("/api"):
        return JSONResponse(status_code=422, content={"detail": exc.errors()})
    messages = []
    for err in exc.errors():
        loc = " → ".join(str(p) for p in err["loc"] if p not in ("body", "query"))
        messages.append(f"{loc}: {err['msg']}" if loc else err["msg"])
    flash_errors(request, messages)
    return RedirectResponse(request.headers.get("referer", "/dashboard"), status_code=303)


# JWT REST API → mounted under /api
for module in (auth_api, books_api, cart_api, wishlist_api, address_api, orders_api, feedback_api):
    app.include_router(module.router, prefix="/api")

# Session web UI → mounted at /
for module in (auth_web, dashboard_web, books_web, cart_web, wishlist_web,
               address_web, orders_web, feedback_web, users_web, password_web):
    app.include_router(module.router)
```

> **This import block is also what makes table creation work.** Importing every
> `api`/`web` module pulls in every `models.py`, so by the time `create_all` runs,
> SQLAlchemy's metadata holds all 7 tables and their relationships resolve.

---

## 12. Run it

Create **`run.py`** in the project root:

```python
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
```

Make sure the database exists once:

```sql
CREATE DATABASE IF NOT EXISTS book_store_product;
```

Start MySQL (XAMPP), then run:

```powershell
python run.py
```

On startup you should see `Application startup complete`. Open:

- Web UI → http://127.0.0.1:8000/
- Swagger (try the API live) → http://127.0.0.1:8000/docs

The **first run creates all 7 tables automatically**. Confirm in phpMyAdmin or:

```sql
USE book_store_product;
SHOW TABLES;   -- users, books, carts, wishlists, addresses, orders, feedbacks
```

---

## 13. Follow one full request (the "aha" moment)

**A logged-in admin adds a book through the API:**

1. Client → `POST /api/addingBook` with a JSON body + `Authorization: Bearer <token>`.
2. `main.py` routed `/api/*` to the books API router → matches `adding_book`.
3. FastAPI sees `payload: BookCreate` → **validates the JSON** (schema). Bad data ⇒ auto-422.
4. FastAPI sees `Depends(require_api_role("admin"))` → **guard**: decode token, load user,
   check `role == "admin"`. Not admin ⇒ 403.
5. FastAPI sees `Depends(get_db)` → opens a **DB session**.
6. Your code builds a `Book` **model**, `db.add` + `db.commit` ⇒ SQLAlchemy emits the
   `INSERT` via PyMySQL ⇒ MySQL stores the row in `books`.
7. You return a dict ⇒ FastAPI serializes it to JSON ⇒ client gets `201 Created`.
8. The session is **closed automatically** (`get_db`'s `finally`).

Every layer you built appears exactly once. That is the whole app.

---

## 14. Build order checklist

1. `requirements.txt` → install.
2. `app/core/config.py` → `.env`.
3. `app/core/database.py` (engine, Base, TimestampMixin, get_db).
4. `app/core/security.py` (hashing + JWT).
5. **Models** (tables): `auth → books → cart → wishlist → address → orders → feedback`.
6. **Schemas** per feature.
7. `app/auth/dependencies.py` (guards).
8. **API routers** per feature (`api.py`).
9. **Web routers** per feature (`web.py`).
10. `app/core/templating.py` + `app/templates/`.
11. `app/main.py` (wiring + table creation on startup).
12. `run.py` → `python run.py`.

---

## 15. Common gotchas

- **"Table is missing my new column."** `create_all` only *creates missing tables*; it
  does **not** alter existing ones. While learning, drop the table and restart. Real apps
  use migrations (Alembic).
- **Can't connect to MySQL.** Is MySQL running? Do `.env` credentials match? Does
  `book_store_product` exist?
- **401 on API calls.** Log in (`POST /api/login`), copy `access_token`, send it as
  `Authorization: Bearer <token>`. In `/docs` click **Authorize**.
- **Web pages bounce to `/login`.** The web door uses the cookie session, not the JWT.
  Log in through the web form.
- **`RuntimeError: Form data requires "python-multipart"`.** Install it (it's in
  `requirements.txt`).
- **Relationship error "expression 'Book' failed to locate a name".** A model was never
  imported. Ensure `main.py` imports every router so every model loads before first use.
- **Never commit `.env`.** Add it to `.gitignore`; commit `.env.example` instead.
```
