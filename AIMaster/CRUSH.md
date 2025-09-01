# CRUSH.md

## Build/Lint/Test

- Install dependencies:
```
pip install -r requirements.txt
```
- Run the app in development:
```
python run.py  # serves on http://0.0.0.0:5000
```
- Run unit tests:
```
python -m unittest -v
```
- Optional end-to-end API/CORS check:
```
python scripts/rn_cors_api_tester.py
```

## Code Style Guidelines

### Imports
- Standard library imports first.
- Followed by 3rd party imports (flask, flask_appbuilder).
- Followed by local application imports.
- Use absolute imports within the app, e.g. `from app import views`.

### Formatting
- Use 4 spaces indentation.
- Use triple double-quoted docstrings for modules, classes and functions.
- Keep lines under 79 characters.
- Use blank lines to separate top-level functions and classes.

### Types
- Use Python type hints where applicable, though none detected.
- SQLAlchemy models and fields follow flask_appbuilder conventions.

### Naming Conventions
- Use CapWords for class names.
- Use lowercase_with_underscores for functions and variables.
- Constants in ALL_CAPS.

### Error Handling
- Use Flask error handlers registered with `@appbuilder.app.errorhandler()`.
- Return proper HTTP status codes and render templates for errors.
- Use try/except blocks where needed.

### Logging
- Logging configured with `logging.basicConfig()` at DEBUG level.
- Use `logging.getLogger(__name__)` in modules where applicable.

## Flask-AppBuilder Specific

- The app uses Flask-AppBuilder for auth/users and SQLAlchemy session management.
- A blueprint in `app/api.py` exposes JSON endpoints under `/api`.
- The user model is augmented at startup to include a `credits` column when missing.

## Other Notes

- No Cursor or Copilot specific rules found in repo.
- Configuration lives in `config.py`.
- SQLite database is used by default (see `app.db`).

---

This CRUSH.md is designed to enable future autonomous agents to understand and work effectively in this repository.
