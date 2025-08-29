# AIMaster API and Setup

This repository exposes a JSON API via Flask and Flask-AppBuilder. Use the routes documented below to connect your frontend. The running app mounts a blueprint at `/api` and supports either token auth (from `POST /api/login`) or a logged-in Flask session (via the FAB UI).

## Quick Start

1. Install dependencies (example):
   - `pip install -r requirements.txt` (if present) or install Flask, Flask-AppBuilder, SQLAlchemy, Flask-Login.
2. Run the app:
   - `python run.py` (serves on `http://0.0.0.0:8080`).
3. Base URL for the API:
   - `http://localhost:8080/api`

Notes:
- The `backend/` folder contains a separate sample Flask app and is not used by `run.py`.
- Tokens are stored in-memory and are cleared on process restart.

## Authentication

- Obtain a token with `POST /api/login`.
- Send the token as `Authorization: <token>` header or `?token=<token>` query param.
- Alternatively, authenticate via the Flask-AppBuilder (FAB) UI session and omit the token.

## Users & Auth

### POST `/api/register`
- Auth: none
- Body: `{ "email": string, "password": string }`
- 201: `{ "id": number, "email": string }`
- 400: `{ "error": "email and password required" | "email already registered" }`
- 500: `{ "error": string }`

### POST `/api/login`
- Auth: none
- Body: `{ "email": string, "password": string }`
- 200: `{ "id": number, "email": string, "token": string }`
- 401: `{ "error": "invalid credentials" }`

### GET `/api/user`
- Auth: required
- 200: `{ "id": number, "email": string, "credits": number }`
- 401: `{ "error": "authentication required" }`

### POST `/api/logout`
- Auth: required
- Effect: invalidates the provided token
- 200: `{ "success": true }`

## Credits

### GET `/api/user/credits`
- Auth: required
- 200: `{ "credits": number }`

### POST `/api/user/credits`
- Auth: required
- Body: `{ "amount": number }` (positive integer)
- 200: `{ "credits": number }` (new total)
- 400: `{ "error": "amount must be positive" }`
- 500: `{ "error": string }`

## Decks

Deck object shape (response):

```
{
  "id": string,                  // serialized as string
  "name": string,
  "description": string|null,
  "owner_id": number,
  "nodes": array,                // defaults to []
  "created_at": ISO8601 string
}
```

### GET `/api/decks`
- Auth: required
- 200: `[ Deck ]` (owned by current user)

### POST `/api/decks`
- Auth: required
- Body:
  - `name: string` (required) — alias accepted: `stack`
  - `description: string` (optional)
  - `nodes: array` (optional; defaults `[]`) — alias accepted: `order`
- 201: `Deck` (adds `order` in response if provided in request)
- 400: `{ "error": "name required" | "nodes must be a list" }`

### GET `/api/decks/<deck_id>`
- Auth: required
- 200: `Deck`
- 404: `{ "error": "not found" }`

### PUT `/api/decks/<deck_id>`
- Auth: required
- Body (partial update): `name`, `description`, `nodes` (if present must be array)
- 200: `Deck`
- 400: `{ "error": "nodes must be a list" }`
- 404: `{ "error": "not found" }`

### DELETE `/api/decks/<deck_id>`
- Auth: required
- 200: `{ "success": true }`
- 404: `{ "error": "not found" }`

## Routines

Routine object shape (response):

```
{
  "id": string,
  "name": string,
  "stack": string|null,
  "deck_id": string|null,
  "nodes": array,
  "owner_id": number,
  "created_at": ISO8601 string,
  "last_run_at": ISO8601 string|null
}
```

### GET `/api/routines`
- Auth: required
- 200: `[ Routine ]` (owned by current user)

### POST `/api/routines`
- Auth: required
- Body:
  - `name: string` (required)
  - `nodes: array` (optional; defaults `[]`)
  - `deck_id: number` (optional; must belong to user if provided)
  - `stack: string` (optional; alias `deck_name`. If `deck_id` not set, server will try to find a deck by this name for the user.)
- 201: `Routine`
- 400: `{ "error": "name required" | "nodes must be a list" }`
- 404: `{ "error": "deck not found or unauthorized" }`

### GET `/api/routines/<routine_id>`
- Auth: required
- 200: `Routine`
- 404: `{ "error": "not found" }`

### PUT `/api/routines/<routine_id>`
- Auth: required
- Body (partial update): `name`, `stack`, `nodes`, `deck_id` (if non-null, must be owned)
- 200: `Routine`
- 400: `{ "error": "nodes must be a list" }`
- 404: `{ "error": "not found" | "deck not found or unauthorized" }`

### DELETE `/api/routines/<routine_id>`
- Auth: required
- 200: `{ "success": true }`
- 404: `{ "error": "not found" }`

## Curl Examples

Login:

```
curl -X POST http://localhost:8080/api/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"user@example.com","password":"pw"}'
```

Authenticated call (header):

```
curl http://localhost:8080/api/user \
  -H "Authorization: token-<id>-<ts>"
```

Authenticated call (query param):

```
curl "http://localhost:8080/api/decks?token=token-<id>-<ts>"
```

## Implementation Notes

- API blueprint is defined in `app/api.py` and registered in `app/__init__.py`.
- SQL models live in `app/models.py` (`Deck`, `Routine`) and extend the FAB user model with a `credits` column.
- A duplicate GET `/api/user/credits` exists via FAB view in `app/views.py`; for token-based auth, prefer the blueprint version.
