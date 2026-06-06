# Book Store — FastAPI

A faithful port of the Laravel **Book Store** project to **FastAPI**. Like the
original, it exposes **two interfaces** over the same data:

| Interface | Original (Laravel) | This project (FastAPI) |
|-----------|--------------------|------------------------|
| JWT REST API | `routes/api.php` + `App\Http\Controllers\*` | `app/routers/api/*` mounted under **`/api`** |
| Session web UI (server-rendered) | `routes/web.php` + `App\Http\Controllers\AI\*` + Blade views | `app/routers/web/*` + Jinja2 templates, mounted at **`/`** |

Both share the same SQLAlchemy models and run against the **same MySQL schema**
(`book_store_product`) used by the Laravel app — `bcrypt` password hashes are
cross-compatible (`$2y$` ↔ `$2b$`), so accounts created in either app work in
both.

## Features (parity with the Laravel app)

- **Auth & roles** — register / login / logout, two roles: `admin`, `user`.
- **Books** — list, search (name/author), sort by price; admin-only create,
  update, delete and restock. Covers stored under `app/static/book-covers/`.
- **Cart** — add, increment, decrement (auto-remove at 0), remove. *(user)*
- **Wishlist** — add, move-to-cart, remove. *(user)*
- **Address** — CRUD, scoped to the signed-in user. *(user)*
- **Orders** — place an order (stock check + decrement, random order id) and
  view history. *(user)*
- **Feedback** — submit a 1–5 rating and view a book's average. *(user)*
- **Users directory** — admin-only list of accounts.
- **Password** — forgot (generates a reset token) + reset.

## Requirements

- Python 3.11+
- A running MySQL (XAMPP's MySQL is fine). Create the database if it does not
  exist: `CREATE DATABASE book_store_product;` — tables are created
  automatically on startup (`CREATE_TABLES=true`).

## Setup

```powershell
cd C:\xampp\htdocs\Book_Store_FastAPI

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt

copy .env.example .env   # then edit DB credentials if needed
```

## Run

```powershell
python run.py
# or: uvicorn app.main:app --reload
```

- Web UI:        http://127.0.0.1:8000/
- Swagger (API): http://127.0.0.1:8000/docs
- ReDoc:         http://127.0.0.1:8000/redoc

## Using the JWT API

```bash
# Register
curl -X POST http://127.0.0.1:8000/api/register -H "Content-Type: application/json" \
  -d '{"role":"admin","first_name":"Ada","last_name":"Lovelace","phone_no":"9999999999","email":"ada@example.com","password":"secret1","confirm_password":"secret1"}'

# Login -> returns {"access_token": "..."}
curl -X POST http://127.0.0.1:8000/api/login -H "Content-Type: application/json" \
  -d '{"email":"ada@example.com","password":"secret1"}'

# Authenticated call
curl http://127.0.0.1:8000/api/displayAllBooks -H "Authorization: Bearer <token>"
```

All API endpoint names match the Laravel routes (`addingBook`,
`addBookToCartByBookId`, `placeOrder`, `getAverageRatingByBookId`, …).

## API endpoint map (→ Laravel)

| Method & path | Role | Laravel controller |
|---------------|------|--------------------|
| `POST /api/register` `/login` `/logout` | – | UserController |
| `POST /api/forgotPassword` `/resetPassword` | – / token | ForgotPasswordController |
| `POST /api/addingBook` `/updateBookById` `/deleteBookById` `/addQuantityToExistBook` | admin | BookController |
| `GET /api/displayAllBooks` `/sortPriceLowToHigh` `/sortPriceHighToLow` · `POST /api/searchBookByKeyword` | any | BookController |
| `POST /api/addBookToCartByBookId` `/deleteBookByCartId` `/increamentBookQuantityInCart` `/decrementBookQuantityInCart` `/addBookToCartByWishlistId` · `GET /api/getAllBooksInCart` | user | CartController |
| `POST /api/addBookToWishlistByBookId` `/deleteBookByWishlistId` · `GET /api/getAllBooksInWishlist` | user | WishlistController |
| `POST /api/addAddress` `/updateAddress` `/deleteAddress` `/getAddress` | user | AddressController |
| `POST /api/placeOrder` | user | OrderController |
| `POST /api/feedback` `/getAverageRatingByBookId` | user | FeedbackController |

## Project layout

```
app/
├── main.py            # app wiring, middleware, exception handlers, routers
├── config.py          # env-driven settings (.env)
├── database.py        # SQLAlchemy engine/session
├── models.py          # ORM models matching the Laravel schema
├── schemas.py         # Pydantic request models (API)
├── security.py        # bcrypt + JWT
├── deps.py            # auth/role guards (API JWT + web session)
├── templating.py      # Jinja2 env, flash messages, render()
├── routers/api/*      # JWT REST API (routes/api.php parity)
├── routers/web/*      # session web UI (routes/web.php parity)
├── templates/*        # Jinja2 templates (Blade view parity)
└── static/book-covers # uploaded book covers
```

## Notes / intentional differences

- The Laravel API stored covers on **S3** and sent **queued e-mails** for
  orders and password resets. As the Laravel *web* views already did, this port
  keeps things self-contained: covers go to local `static/`, and reset tokens
  are shown/returned instead of e-mailed.
- JWT is stateless, so `logout` just instructs the client to drop the token.
