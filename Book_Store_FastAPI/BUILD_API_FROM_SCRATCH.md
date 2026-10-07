# Book Store API (FastAPI) — Backend-Only, Build From Scratch (Step by Step)

This guide builds **only the JSON REST API backend** — no HTML, no templates, no
session cookies, no file uploads. Just clean endpoints that take/return JSON and are
protected by a **JWT bearer token**. Perfect for a mobile app, a SPA frontend, or Postman.

Layout is **feature-first**: shared infrastructure in `app/core/`, shared auth guards in
`app/auth/`, and one package per domain holding its `models.py`, `schemas.py`, `api.py`.

> Type the code yourself as you go — you learn far more than copy-pasting.

---

## 0. What "backend-only" changes

Compared to a full-stack build, the API-only version **drops** these:

| Dropped | Why |
|---------|-----|
| `web.py` routers | No server-rendered HTML pages. |
| `templates/`, Jinja2 | Nothing to render. |
| `SessionMiddleware`, cookies | Auth is stateless JWT, not a login cookie. |
| `dashboard/`, `users/`, `password/` web packages | Those were web-only screens. |
| `python-multipart`, file uploads | Book covers are passed as a string URL, not a file. |
| `core/templating.py`, `RedirectException` | Web-only concerns. |

What stays: config, database, security (JWT), the 7 tables, schemas, JWT guards, and the
seven API routers.

---

## 1. Prerequisites

| Need | Why | Check |
|------|-----|-------|
| Python 3.11+ | Modern typing (`str \| None`, `Mapped[...]`) | `python --version` |
| MySQL running | Stores the data (XAMPP is fine) | XAMPP → Start MySQL |
| Postman or curl | To call the endpoints | — |

---

## 2. Create the project skeleton

```powershell
mkdir Book_Store_API
cd Book_Store_API

python -m venv .venv
.\.venv\Scripts\Activate.ps1        # prompt shows (.venv)

mkdir app
mkdir app\core
mkdir app\auth app\books app\cart app\wishlist app\address app\orders app\feedback
```

Add an **empty** `__init__.py` to every package:

```powershell
ni app\__init__.py
ni app\core\__init__.py
foreach ($f in 'auth','books','cart','wishlist','address','orders','feedback') { ni app\$f\__init__.py }
```

Final structure:

```
Book_Store_API/
├── run.py
├── requirements.txt
├── .env  /  .env.example
└── app/
    ├── main.py
    ├── core/      config.py · database.py · security.py
    ├── auth/      models.py · schemas.py · dependencies.py · api.py
    ├── books/     models.py · schemas.py · api.py
    └── cart/ wishlist/ address/ orders/ feedback/   (same shape)
```

---

## 3. Install the libraries

**`requirements.txt`** (note: no jinja2 / multipart / itsdangerous — those were web-only):

```
fastapi
uvicorn[standard]
sqlalchemy
pymysql
pydantic[email]
pydantic-settings
passlib[bcrypt]
pyjwt
```

```powershell
pip install -r requirements.txt
```

| Library | Role |
|---------|------|
| **fastapi** | Web framework: routes, validation, dependency injection, auto Swagger docs. |
| **uvicorn** | ASGI server that runs the app. |
| **sqlalchemy** | ORM — Python classes instead of raw SQL. |
| **pymysql** | Driver SQLAlchemy uses to reach MySQL. |
| **pydantic / -settings** | Validates request bodies; loads typed settings from `.env`. |
| **passlib[bcrypt]** | Hashes passwords. |
| **pyjwt** | Creates/reads the JWT bearer token. |

---

## 4. Configuration — `app/core/config.py`

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Book Store API"
    secret_key: str = "insecure-dev-secret-change-me"   # signs the JWT
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

**`.env`** (and a committable `.env.example` with the same keys, blank secrets):

```
APP_NAME=Book Store API
SECRET_KEY=change-me-to-a-long-random-string
DB_HOST=127.0.0.1
DB_PORT=3306
DB_DATABASE=book_store_product
DB_USERNAME=root
DB_PASSWORD=
CREATE_TABLES=true
```

---

## 5. Database engine — `app/core/database.py`

```python
from collections.abc import Generator
from datetime import datetime

from sqlalchemy import DateTime, create_engine, func
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from .config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

> Every endpoint that touches the DB takes `db: Session = Depends(get_db)`. FastAPI opens
> the session, hands it over, and the `finally` always closes it.

---

## 6. Passwords + JWT — `app/core/security.py`

```python
from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from .config import settings

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
    return jwt.encode({"sub": str(subject), "exp": expire},
                      settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload.get("sub")
    except jwt.PyJWTError:
        return None
```

- **Login** mints a token with `create_access_token(user.id)`.
- **Every protected call** sends `Authorization: Bearer <token>`; the guard decodes it
  back to a user id.

---

## 7. The database tables (models)

Seven tables, each a Python class in its feature package. On startup
`Base.metadata.create_all()` issues `CREATE TABLE` for any missing table.

| Table | Class | File |
|-------|-------|------|
| `users` | `User` | `app/auth/models.py` |
| `books` | `Book` | `app/books/models.py` |
| `carts` | `Cart` | `app/cart/models.py` |
| `wishlists` | `WishList` | `app/wishlist/models.py` |
| `addresses` | `Address` | `app/address/models.py` |
| `orders` | `Order` | `app/orders/models.py` |
| `feedbacks` | `Feedback` | `app/feedback/models.py` |

> **Cross-feature links without import cycles:** reference the other class by **string
> name** in `relationship("Book")`, and put the real import behind `TYPE_CHECKING`.
> SQLAlchemy resolves the string later, after every model has been imported.

**`app/auth/models.py`**

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
    password: Mapped[str] = mapped_column(String(255))               # the HASH
    books: Mapped[list["Book"]] = relationship(back_populates="user")
    carts: Mapped[list["Cart"]] = relationship(back_populates="user")
    wishlists: Mapped[list["WishList"]] = relationship(back_populates="user")
    addresses: Mapped[list["Address"]] = relationship(back_populates="user")
    feedbacks: Mapped[list["Feedback"]] = relationship(back_populates="user")
```

**`app/books/models.py`**

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
    image: Mapped[str] = mapped_column(String(255))     # a URL string, not an upload
    price: Mapped[str] = mapped_column("price", String(255))
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    user: Mapped["User"] = relationship(back_populates="books")
```

**`app/cart/models.py`** and **`app/wishlist/models.py`** (join tables)

```python
# cart/models.py
class Cart(Base, TimestampMixin):
    __tablename__ = "carts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    book_id: Mapped[int] = mapped_column(Integer, ForeignKey("books.id"))
    book_quantity: Mapped[int] = mapped_column(Integer, default=1)
    user: Mapped["User"] = relationship(back_populates="carts")
    book: Mapped["Book"] = relationship()

# wishlist/models.py
class WishList(Base, TimestampMixin):
    __tablename__ = "wishlists"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    book_id: Mapped[int] = mapped_column(Integer, ForeignKey("books.id"))
    user: Mapped["User"] = relationship(back_populates="wishlists")
    book: Mapped["Book"] = relationship()
```

**`app/address/models.py`**, **`app/orders/models.py`**, **`app/feedback/models.py`**

```python
# address/models.py
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

# orders/models.py
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

# feedback/models.py
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

(Each of these files starts with the same `from __future__ / TYPE_CHECKING` header as the
two above — importing `Base`, `TimestampMixin`, and the related class names.)

---

## 8. Validation schemas — per feature `schemas.py`

A **model** is a table; a **schema** is the shape of a request body. A bad body is
rejected with `422` before your code runs.

**`app/auth/schemas.py`**

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
    def match(cls, v, info):
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
    def match(cls, v, info):
        if v != info.data.get("new_password"):
            raise ValueError("confirm_password must match new_password")
        return v
```

**`app/books/schemas.py`**

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


class BookId(BaseModel):    id: int
class AddQuantity(BaseModel):    id: int; quantity: int = Field(ge=1)
class SearchRequest(BaseModel):  search: str
```

**The smaller schemas**

```python
# cart/schemas.py
class BookIdRequest(BaseModel):     book_id: int
class CartIdRequest(BaseModel):     cart_id: int
class WishlistIdRequest(BaseModel): wishlist_id: int

# wishlist/schemas.py
class BookIdRequest(BaseModel):     book_id: int
class WishlistIdRequest(BaseModel): wishlist_id: int

# address/schemas.py
class AddressCreate(BaseModel):
    address: str = Field(min_length=2, max_length=600)
    city: str = Field(min_length=2, max_length=100)
    state: str = Field(min_length=2, max_length=100)
    landmark: str = Field(min_length=2, max_length=100)
    pincode: int
    address_type: str = Field(min_length=2, max_length=100)
class AddressUpdate(AddressCreate): id: int
class AddressId(BaseModel):         id: int

# orders/schemas.py
class OrderRequest(BaseModel):
    name: str
    address_id: int
    quantity: int = Field(ge=1)

# feedback/schemas.py
class FeedbackRequest(BaseModel):
    book_id: int
    feedback: str = Field(min_length=4, max_length=1000)
    rating: int = Field(ge=1, le=5)
class AverageRatingRequest(BaseModel):
    book_id: int
```

---

## 9. JWT guards — `app/auth/dependencies.py`

Backend-only, so this file has **just the JWT guards** (no web/session helpers).

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token

from .models import User

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
    """Factory: returns a guard that also enforces the user's role."""
    def checker(user: User = Depends(get_current_api_user)) -> User:
        if user.role != role:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Only {role}s are allowed to do this")
        return user
    return checker
```

> Using `HTTPBearer` also makes the **Authorize** button appear in Swagger (`/docs`), so
> you can paste a token and try protected endpoints right in the browser.

---

## 10. The API routers — `app/<feature>/api.py`

Every endpoint follows the same recipe: **schema** validates the body → **guard** checks
the token/role → **session** opens → **model** read/write → `commit` → return a dict
(FastAPI turns it into JSON).

### 10.1 `app/auth/api.py`

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


@router.post("/register", status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == payload.email)):
        raise HTTPException(401, "The email has already been taken")
    user = User(role=payload.role, first_name=payload.first_name, last_name=payload.last_name,
                phone_no=payload.phone_no, email=payload.email,
                password=hash_password(payload.password))
    db.add(user); db.commit(); db.refresh(user)
    return {"status": 201, "message": "User successfully registered", "user_id": user.id}


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email))
    if not user or not verify_password(payload.password, user.password):
        raise HTTPException(401, "Wrong email or password")
    return {"access_token": create_access_token(user.id), "token_type": "bearer", "expires_in": 3600}


@router.post("/logout")
def logout(_: User = Depends(get_current_api_user)):
    return {"status": 200, "message": "User successfully logged out"}  # JWT is stateless


@router.post("/forgotPassword")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email))
    if not user:
        raise HTTPException(404, "we can not find the user with that e-mail address")
    return {"status": 200, "message": "Password reset token generated", "token": create_access_token(user.id)}


@router.post("/resetPassword")
def reset_password(payload: ResetPasswordRequest,
                   user: User = Depends(get_current_api_user), db: Session = Depends(get_db)):
    user.password = hash_password(payload.new_password)
    db.commit()
    return {"status": 201, "message": "Password reset successful!"}
```

### 10.2 `app/books/api.py` (admin mutates, anyone logged-in reads)

```python
from fastapi import APIRouter, Depends, HTTPException
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
def adding_book(payload: BookCreate, admin: User = Depends(require_api_role("admin")),
                db: Session = Depends(get_db)):
    book = Book(user_id=admin.id, name=payload.name, description=payload.description,
                author=payload.author, image=payload.image,
                price=str(payload.price), quantity=payload.quantity)
    db.add(book); db.commit(); db.refresh(book)
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


@router.post("/addQuantityToExistBook")
def add_quantity(payload: AddQuantity, admin: User = Depends(require_api_role("admin")),
                 db: Session = Depends(get_db)):
    book = db.get(Book, payload.id)
    if not book:
        raise HTTPException(404, "Could not find a book with that id")
    book.quantity += payload.quantity; db.commit()
    return {"status": 201, "message": "Quantity updated to existing book successfully"}


@router.get("/displayAllBooks")
def display_all_books(_: User = Depends(get_current_api_user), db: Session = Depends(get_db)):
    books = db.scalars(select(Book).order_by(Book.name)).all()
    return {"status": 200, "books": [_serialize(b) for b in books]}


@router.get("/sortPriceLowToHigh")
def sort_low(_: User = Depends(get_current_api_user), db: Session = Depends(get_db)):
    books = sorted(db.scalars(select(Book)).all(), key=lambda b: float(b.price))
    return {"status": 200, "books": [_serialize(b) for b in books]}


@router.get("/sortPriceHighToLow")
def sort_high(_: User = Depends(get_current_api_user), db: Session = Depends(get_db)):
    books = sorted(db.scalars(select(Book)).all(), key=lambda b: float(b.price), reverse=True)
    return {"status": 200, "books": [_serialize(b) for b in books]}


@router.post("/searchBookByKeyword")
def search_book(payload: SearchRequest, _: User = Depends(get_current_api_user),
                db: Session = Depends(get_db)):
    like = f"%{payload.search}%"
    books = db.scalars(select(Book).where(or_(Book.name.like(like), Book.author.like(like)))).all()
    return {"status": 200, "books": [_serialize(b) for b in books]}
```

### 10.3 `app/cart/api.py` (role `user`; note the ownership check)

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import require_api_role
from app.auth.models import User
from app.books.models import Book
from app.core.database import get_db
from app.wishlist.models import WishList

from .models import Cart
from .schemas import BookIdRequest, CartIdRequest, WishlistIdRequest

router = APIRouter(tags=["cart"])
user_role = require_api_role("user")


@router.post("/addBookToCartByBookId", status_code=201)
def add_to_cart(payload: BookIdRequest, user: User = Depends(user_role), db: Session = Depends(get_db)):
    book = db.get(Book, payload.book_id)
    if not book:                 raise HTTPException(404, "Book not found")
    if book.quantity == 0:       raise HTTPException(400, "OUT OF STOCK")
    if db.scalar(select(Cart).where(Cart.book_id == book.id, Cart.user_id == user.id)):
        raise HTTPException(409, "Book already added to the cart")
    db.add(Cart(book_id=book.id, user_id=user.id)); db.commit()
    return {"status": 201, "message": "Book added to cart Successfully"}


@router.get("/getAllBooksInCart")
def get_cart(user: User = Depends(user_role), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Book.id, Book.name, Book.author, Book.price, Cart.book_quantity)
        .join(Book, Cart.book_id == Book.id).where(Cart.user_id == user.id)
    ).all()
    return {"status": 200, "books": [dict(r._mapping) for r in rows]}


@router.post("/deleteBookByCartId")
def delete_cart(payload: CartIdRequest, user: User = Depends(user_role), db: Session = Depends(get_db)):
    cart = db.get(Cart, payload.cart_id)
    if not cart or cart.user_id != user.id:        # never trust the id alone
        raise HTTPException(404, "Cart not found for this user")
    db.delete(cart); db.commit()
    return {"status": 201, "message": "Book deleted from cart Successfully"}

# increamentBookQuantityInCart / decrementBookQuantityInCart / addBookToCartByWishlistId
# follow the same pattern (load, check ownership, mutate, commit).
```

### 10.4 The rest (same recipe — build each `api.py`)

- **`app/wishlist/api.py`** — `addBookToWishlistByBookId`, `getAllBooksInWishlist`,
  `deleteBookByWishlistId`. Guard: `require_api_role("user")`.
- **`app/address/api.py`** — `addAddress`, `updateAddress`, `deleteAddress`, `getAddress`
  (every write checks `address.user_id == user.id`).
- **`app/orders/api.py`** — `placeOrder`: find the book by name, verify stock, verify the
  address belongs to the user, create the `Order` with a random `order_id`, decrement
  `book.quantity`, return the total.
- **`app/feedback/api.py`** — `feedback` (insert a row) and `getAverageRatingByBookId`
  (`select(func.avg(Feedback.rating)).where(Feedback.book_id == book_id)`).

Example — `placeOrder`:

```python
import random, string
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.address.models import Address
from app.auth.dependencies import require_api_role
from app.auth.models import User
from app.books.models import Book
from app.core.database import get_db
from .models import Order
from .schemas import OrderRequest

router = APIRouter(tags=["orders"])
user_role = require_api_role("user")


@router.post("/placeOrder", status_code=201)
def place_order(payload: OrderRequest, user: User = Depends(user_role), db: Session = Depends(get_db)):
    book = db.scalar(select(Book).where(Book.name == payload.name))
    if not book:                          raise HTTPException(404, "We do not have this book in the store")
    if book.quantity < payload.quantity:  raise HTTPException(400, "This much stock is unavailable")
    address = db.get(Address, payload.address_id)
    if not address or address.user_id != user.id:
        raise HTTPException(404, "This address id is not available")
    order_id = "".join(random.choices(string.digits + string.ascii_lowercase, k=10))
    db.add(Order(user_id=user.id, book_id=book.id, address_id=address.id, order_id=order_id))
    book.quantity -= payload.quantity
    db.commit()
    return {"status": 201, "message": "Order placed Successfully", "order_id": order_id,
            "total_price": payload.quantity * float(book.price)}
```

---

## 11. Wire it together — `app/main.py`

Backend-only: **no** SessionMiddleware, **no** static mount, **no** templating. Just the
table-creation hook and the API routers. (FastAPI already returns a clean `422` JSON for
bad bodies, so no custom validation handler is needed.)

```python
from fastapi import FastAPI

from app.address import api as address_api
from app.auth import api as auth_api
from app.books import api as books_api
from app.cart import api as cart_api
from app.core.config import settings
from app.core.database import Base, engine
from app.feedback import api as feedback_api
from app.orders import api as orders_api
from app.wishlist import api as wishlist_api

app = FastAPI(title=settings.app_name, version="1.0.0")


@app.on_event("startup")
def on_startup():
    if settings.create_tables:
        Base.metadata.create_all(bind=engine)     # CREATE TABLE for all 7 tables


# All routers under /api  (drop the prefix if you want them at the root)
for module in (auth_api, books_api, cart_api, wishlist_api,
               address_api, orders_api, feedback_api):
    app.include_router(module.router, prefix="/api")
```

> Importing every router here pulls in every `models.py`, so when `create_all` runs,
> SQLAlchemy knows all 7 tables and the string relationships resolve.

---

## 12. Run + test

**`run.py`**

```python
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
```

Create the database once, start MySQL, then run:

```sql
CREATE DATABASE IF NOT EXISTS book_store_product;
```
```powershell
python run.py
```

Open **http://127.0.0.1:8000/docs** — the interactive Swagger UI lists every endpoint.

### The auth flow with curl

```bash
# 1) Register an admin
curl -X POST http://127.0.0.1:8000/api/register -H "Content-Type: application/json" \
  -d '{"role":"admin","first_name":"Ada","last_name":"Lovelace","phone_no":"9999999999","email":"ada@example.com","password":"secret1","confirm_password":"secret1"}'

# 2) Log in -> copy the access_token
curl -X POST http://127.0.0.1:8000/api/login -H "Content-Type: application/json" \
  -d '{"email":"ada@example.com","password":"secret1"}'

# 3) Call a protected endpoint with the token
curl http://127.0.0.1:8000/api/displayAllBooks -H "Authorization: Bearer <PASTE_TOKEN>"

# 4) Add a book (admin only)
curl -X POST http://127.0.0.1:8000/api/addingBook -H "Authorization: Bearer <PASTE_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"name":"Clean Code","description":"A handbook","author":"Robert C. Martin","image":"https://x/y.jpg","Price":499,"quantity":10}'
```

In Swagger, click **Authorize**, paste the token once, and every protected endpoint is
unlocked for browser testing.

---

## 13. Endpoint map

| Method & path | Role | Purpose |
|---------------|------|---------|
| `POST /api/register` `/login` `/logout` | – | Account + JWT |
| `POST /api/forgotPassword` `/resetPassword` | – / token | Password reset |
| `POST /api/addingBook` `/updateBookById` `/deleteBookById` `/addQuantityToExistBook` | admin | Manage catalogue |
| `GET /api/displayAllBooks` `/sortPriceLowToHigh` `/sortPriceHighToLow` · `POST /api/searchBookByKeyword` | any | Browse |
| `POST /api/addBookToCartByBookId` `/deleteBookByCartId` `/increamentBookQuantityInCart` `/decrementBookQuantityInCart` `/addBookToCartByWishlistId` · `GET /api/getAllBooksInCart` | user | Cart |
| `POST /api/addBookToWishlistByBookId` `/deleteBookByWishlistId` · `GET /api/getAllBooksInWishlist` | user | Wishlist |
| `POST /api/addAddress` `/updateAddress` `/deleteAddress` `/getAddress` | user | Address |
| `POST /api/placeOrder` | user | Orders |
| `POST /api/feedback` `/getAverageRatingByBookId` | user | Feedback |

---

## 14. Build-order checklist

1. `requirements.txt` → install.
2. `app/core/config.py` → `.env`.
3. `app/core/database.py` (engine, Base, TimestampMixin, get_db).
4. `app/core/security.py` (hashing + JWT).
5. **Models** (tables): `auth → books → cart → wishlist → address → orders → feedback`.
6. **Schemas** per feature.
7. `app/auth/dependencies.py` (JWT guards).
8. **API routers** per feature (`api.py`).
9. `app/main.py` (table creation + include routers).
10. `run.py` → `python run.py` → test in `/docs`.

---

## 15. Common gotchas

- **401 on every call.** You must send `Authorization: Bearer <token>`. Get it from
  `POST /api/login`. In `/docs` use the **Authorize** button.
- **403 Forbidden.** The endpoint needs a specific role (admin vs user). Register with the
  right `role`.
- **Table missing a new column.** `create_all` only creates *missing* tables; it never
  alters existing ones. Drop the table and restart, or use Alembic migrations.
- **Can't connect to MySQL.** Is it running? Do `.env` credentials match? Does
  `book_store_product` exist?
- **Relationship "failed to locate a name".** A model never got imported. `main.py` must
  import every router so every model loads before first use.
- **Never commit `.env`.** Git-ignore it; commit `.env.example` instead.
```
