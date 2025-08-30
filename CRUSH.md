# CRUSH.md for Flask-AppBuilder Repository

## Build/Lint/Test Commands

- Run all tests with coverage (multiple DB envs supported):
  ```tox -e api-sqlite```  # Change env for mysql, postgres, mssql, mongodb

- Run a single test file:
  ```nose2 path/to/test_file.py```

- Run flake8 lint check:
  ```tox -e flake8```

- Check code formatting with black:
  ```tox -e black```

- Run mypy type checks:
  ```mypy flask_appbuilder tests```

## Code Style Guidelines

- **Imports**: Follow Google import order style enforced by flake8 config.
  Group imports as: stdlib, 3rd party, local application.

- **Formatting**:
  - Max line length set to 90 characters
  - Use black for consistent code formatting
  - Ignore some conflicting flake8 errors: E203, W503, W605

- **Typing**:
  - Use type hints where possible
  - Some internal modules enforce stricter typing (disallow untyped defs)
  - Ignore missing imports and some mypy errors globally for dependencies

- **Naming**:
  - Use snake_case for variables and functions
  - Use PascalCase for classes

- **Error handling**:
  - Prefer explicit exception handling
  - Raise meaningful errors for invalid states
  - Avoid bare excepts

- **Testing**:
  - Tests live in `tests/` directory
  - Use `nose2` test runner
  - Tests include config for multiple databases, use `-A` flag to select

- **Localization/Internationalization**:
  - Uses babel for translation (.pot and .po files in babel/ and app translations)


This file is intended for agentic coding assistants operating in this repository.
Keep it up to date as tooling or conventions evolve.
