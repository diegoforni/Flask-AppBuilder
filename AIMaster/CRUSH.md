# CRUSH.md

## Build/Lint/Test

- No explicit build or lint tools configured.
- To install dependencies:
```
pip install flask-appbuilder
```
- To run the app in development:
```
export FLASK_APP=app
flask fab create-admin  # Create admin user the first time
flask run
```
- No automated tests detected. Manual testing through running the app and browser is expected.
- To add testing, use pytest or unittest and run tests with:
```
pytest tests/<test_file>.py
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
- Use `logging.getLogger(__name__)` in modules.

## Flask-AppBuilder Specific

- Use `ModelView` and `ModelRestApi` for views and REST APIs.
- Register views and APIs with `appbuilder.add_view()` / `appbuilder.add_api()`.
- Use SQLAInterface for datamodel.

## Other Notes

- No Cursor or Copilot specific rules found in repo.
- Configuration managed via `config.py` with environment-specific options.
- Database URL configured for SQLite by default.

---

This CRUSH.md is designed to enable future autonomous agents to understand and work effectively in this repository.
