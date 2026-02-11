# Development Guide - Indigo Admin Panel

## Development Environment Setup

### Prerequisites

- Docker 29.x or higher
- Docker Compose v5.x or higher
- Git
- Text editor (VS Code recommended)
- Access to Samba AD DC server (for LDAP testing)

### Initial Setup

1. **Clone the repository**
```bash
git clone https://github.com/ghanitoos/indigo.git
cd indigo
```

2. **Create environment file**
```bash
cp .env.example .env
nano .env  # Configure your settings
```

3. **Start development environment**
```bash
docker compose up -d
```

4. **Check containers status**
```bash
docker ps
```

5. **Access the application**
```
http://localhost:8080
```

## Docker Commands

### Starting Services

```bash
# Start all services
docker compose up -d

# Start specific service
docker compose up -d core-app

# View logs
docker compose logs -f

# View logs for specific service
docker compose logs -f core-app
```

### Stopping Services

```bash
# Stop all services
docker compose down

# Stop and remove volumes
docker compose down -v
```

### Rebuilding

```bash
# Rebuild after code changes
docker compose up -d --build

# Rebuild specific service
docker compose up -d --build core-app
```

### Accessing Containers

```bash
# Access Flask container shell
docker exec -it admin-panel-core bash

# Access PostgreSQL
docker exec -it admin-panel-postgres psql -U adminuser -d adminpanel
```

## Project Structure

```
/opt/admin-panel/
├── core-app/              # Main Flask application
│   ├── app.py            # Entry point (to be created)
│   ├── config.py         # Configuration
│   ├── models/           # Database models
│   ├── auth/             # Authentication
│   ├── modules/          # Feature modules
│   ├── api/              # REST API
│   ├── templates/        # HTML templates
│   ├── static/           # CSS, JS, images
│   ├── translations/     # i18n files
│   └── utils/            # Helper functions
├── nginx-proxy/          # Nginx reverse proxy
├── data/                 # Persistent data
│   ├── postgres/         # Database files
│   └── logs/             # Application logs
├── docker-compose.yml    # Container orchestration
├── .env.example          # Environment template
└── .gitignore           # Git ignore rules
```

## Coding Standards

### Python Code Style

- Follow PEP 8
- Use type hints on all functions
- Document all public functions/classes with docstrings
- Maximum line length: 100 characters
- Maximum file length: 300 lines

### File Naming

- Python files: `snake_case.py`
- Classes: `PascalCase`
- Functions/variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`

### Example Code

```python
"""
Module description.
"""
from typing import Optional


class UserManager:
    """Manages user-related operations."""
    
    def get_user_by_id(self, user_id: int) -> Optional[dict]:
        """
        Retrieve user by ID.
        
        Args:
            user_id: The user's unique identifier
            
        Returns:
            User dictionary if found, None otherwise
        """
        # Implementation
        pass
```

## Module Development

### Creating a New Module

1. **Create module directory**
```bash
mkdir -p core-app/modules/my_module
cd core-app/modules/my_module
```

2. **Create required files**
```bash
touch __init__.py routes.py services.py config.json translations.json README.md
```

3. **Implement module registration** (`__init__.py`)
```python
"""My Module - description."""

def register_module(app):
    """Register module with Flask app."""
    from .routes import bp
    app.register_blueprint(bp, url_prefix='/my-module')
```

4. **Implement routes** (`routes.py`)
```python
"""Routes for My Module."""
from flask import Blueprint, render_template

bp = Blueprint('my_module', __name__)

@bp.route('/')
def index():
    """Module main page."""
    return render_template('modules/my_module/index.html')
```

5. **Add translations** (`translations.json`)
```json
{
  "de": {
    "title": "Mein Modul",
    "description": "Beschreibung"
  },
  "en": {
    "title": "My Module",
    "description": "Description"
  }
}
```

6. **Enable module** (in `.env`)
```
ENABLED_MODULES=dashboard,users,my_module
```

## Database Management

### Running Migrations

```bash
# Access container
docker exec -it admin-panel-core bash

# Initialize migrations (first time only)
flask db init

# Create migration
flask db migrate -m "Description of changes"

# Apply migration
flask db upgrade

# Rollback migration
flask db downgrade
```

### Database Access

```bash
# Connect to PostgreSQL
docker exec -it admin-panel-postgres psql -U adminuser -d adminpanel

# Common queries
\dt              # List tables
\d table_name    # Describe table
SELECT * FROM users LIMIT 10;
```

## Testing

### Running Tests

```bash
# Run all tests
docker exec -it admin-panel-core pytest

# Run specific test file
docker exec -it admin-panel-core pytest tests/test_auth.py

# Run with coverage
docker exec -it admin-panel-core pytest --cov=.
```

### Writing Tests

```python
"""Test authentication module."""
import pytest
from auth.ldap_connector import LDAPConnector


def test_ldap_connection():
    """Test LDAP server connection."""
    connector = LDAPConnector()
    assert connector.test_connection() == True
```

## Translation Management

### Adding New Translations

1. Edit `core-app/translations/de.json`
2. Add same keys to `core-app/translations/en.json`
3. Restart application

### Using Translations in Code

```python
from utils.i18n import translate

# In Python code
message = translate('common.success')

# In Jinja2 templates
{{ _('common.success') }}
```

## Styling and Theming

### Design Tokens

Edit `core-app/static/css/variables.css`:

```css
:root {
  /* Colors */
  --primary-color: #667eea;
  --secondary-color: #764ba2;
  --success-color: #10b981;
  --danger-color: #ef4444;
  --warning-color: #f59e0b;
  --info-color: #3b82f6;
  
  /* Typography */
  --font-family: 'Arial', sans-serif;
  --font-size-base: 16px;
  
  /* Spacing */
  --spacing-unit: 8px;
  --spacing-xs: calc(var(--spacing-unit) * 0.5);
  --spacing-sm: var(--spacing-unit);
  --spacing-md: calc(var(--spacing-unit) * 2);
  --spacing-lg: calc(var(--spacing-unit) * 3);
  
  /* Borders */
  --border-radius: 8px;
  --border-color: #e5e7eb;
}
```

Changes apply immediately without rebuild.

## Git Workflow

### Commit Convention

```
type(scope): subject

Types:
- feat: New feature
- fix: Bug fix
- docs: Documentation
- style: Formatting
- refactor: Code restructuring
- test: Adding tests
- chore: Maintenance

Scope: module or component name
```

### Examples

```bash
git commit -m "feat(auth): add LDAP authentication"
git commit -m "fix(users): correct group membership display"
git commit -m "docs(readme): update installation instructions"
```

### Branching

- `main`: Production-ready code
- `develop`: Development branch
- `feature/name`: Feature branches
- `fix/name`: Bug fix branches

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker compose logs core-app

# Check container status
docker ps -a

# Rebuild container
docker compose up -d --build core-app
```

### Database Connection Issues

```bash
# Check PostgreSQL status
docker exec -it admin-panel-postgres pg_isready

# Check database logs
docker compose logs postgres

# Reset database
docker compose down -v
docker compose up -d
```

### LDAP Connection Issues

1. Verify LDAP server is accessible
2. Check `.env` LDAP settings
3. Test LDAP connection:
```bash
docker exec -it admin-panel-core python
>>> from auth.ldap_connector import LDAPConnector
>>> conn = LDAPConnector()
>>> conn.test_connection()
```

### Permission Issues

```bash
# Fix file permissions
sudo chown -R $(whoami):$(whoami) /opt/admin-panel
```

## Performance Optimization

### Development Mode

- `DEBUG=True`
- `SQLALCHEMY_ECHO=True` (see SQL queries)
- Hot reload enabled

### Production Mode

- `DEBUG=False`
- `SQLALCHEMY_ECHO=False`
- Use production WSGI server (gunicorn)
- Enable caching
- Minify static assets

## Logging

### Log Locations

- Application logs: `data/logs/app.log`
- Nginx logs: `data/logs/nginx/`
- Container logs: `docker compose logs`

### Log Levels

- `DEBUG`: Detailed information
- `INFO`: General information
- `WARNING`: Warning messages
- `ERROR`: Error messages
- `CRITICAL`: Critical issues

### Configuring Logging

In `.env`:
```
LOG_LEVEL=INFO
LOG_FILE=/app/logs/app.log
```

## Security Best Practices

1. **Never commit `.env` file**
2. **Use strong SECRET_KEY** in production
3. **Keep dependencies updated**
4. **Use HTTPS** in production
5. **Regularly backup database**
6. **Monitor logs** for suspicious activity
7. **Limit LDAP bind user** permissions

## Resources

- Flask Documentation: https://flask.palletsprojects.com/
- SQLAlchemy Documentation: https://docs.sqlalchemy.org/
- ldap3 Documentation: https://ldap3.readthedocs.io/
- Docker Documentation: https://docs.docker.com/

## Support

For issues and questions:
1. Check this documentation
2. Review ARCHITECTURE.md
3. Check container logs
4. Contact network administration team
