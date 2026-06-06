# FastAPI CRUD

A simple CRUD REST API for managing items, built with FastAPI + SQLAlchemy (SQLite).

## Setup

```powershell
pip install -r requirements.txt
```

## Run

```powershell
uvicorn main:app --reload
```

Open http://127.0.0.1:8000/docs for the interactive Swagger UI.

## Endpoints

| Method | Path           | Description        |
|--------|----------------|--------------------|
| GET    | /items         | List items         |
| POST   | /items         | Create an item     |
| GET    | /items/{id}    | Get one item       |
| PUT    | /items/{id}    | Update an item     |
| DELETE | /items/{id}    | Delete an item     |

## Example

```powershell
curl -X POST http://127.0.0.1:8000/items `
  -H "Content-Type: application/json" `
  -d '{"name": "Coffee", "description": "Dark roast", "price": 4.5}'
```
