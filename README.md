# Thanatos

A modern Python project template and framework.

## Project Structure

```text
Thanatos/
├── docs/           # Documentation files
├── src/            # Source code for thanatos package
│   └── thanatos/
│       └── __init__.py
├── tests/          # Automated test suite
│   ├── __init__.py
│   └── test_basic.py
├── .gitignore      # Git ignore patterns
├── pyproject.toml  # Project configuration and packaging
└── README.md       # Project overview
```

## Getting Started

### Installation

To set up the project locally for development:

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Linux/macOS:
# source .venv/bin/activate

# Install in editable mode with development dependencies
pip install -e ".[dev]"
```

### Running Tests

```bash
pytest
```

## License

MIT
