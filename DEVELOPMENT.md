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
├── core-app/              # Main Flask application (canonical module location)
│   ├── app.py            # Entry point (to be created)
│   ├── config.py         # Configuration
│   ├── models/           # Database models
│   ├── auth/             # Authentication
│   ├── modules/          # Feature modules (use `core-app/modules/`)
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

Note: An earlier duplicate `modules/` directory at the repository root has been removed. The canonical location for all modules is `core-app/modules/`.

## Backup / GitHub (recommended safe workflow)

This section documents a reliable, secure workflow to back up the project source and recommended additional backups for runtime data. Follow these steps to avoid accidental disclosure of secrets and to make restores straightforward.

1) Prepare repository for backup

- Ensure working tree is clean and all intended changes are committed locally:

```bash
cd /opt/admin-panel
git status --porcelain
git add -A
git commit -m "chore: backup snapshot" || true
```

- Keep a dedicated backup branch (optional):

```bash
git checkout -b backup/$(date -I)
git push -u origin HEAD
```

2) Secrets handling (DO NOT accidentally push secrets)

- Add sensitive files to `.gitignore` (if not already):

```
.env
.env.*
~/.secrets
```

- Prefer NOT to store secrets in the repo. Use one of these alternatives:
  - Use a secrets manager (HashiCorp Vault, AWS Secrets Manager, etc.).
  - Use `git-crypt` or GPG to store only encrypted artifacts in the repo.
  - Use deploy keys or GitHub Actions secrets for automated CI pushes.

3) Authentication options for pushing

- Recommended: use deploy keys or a machine user with a minimal-scope Personal Access Token (PAT) stored securely on the server.
- If using a PAT on the server, store it in a protected file and restrict file permissions:

```bash
mkdir -p ~/.secrets
echo "<YOUR_GITHUB_TOKEN>" > ~/.secrets/github_token
chmod 600 ~/.secrets/github_token
```

- Prefer the `gh` CLI or credential helpers to avoid exposing tokens on the command line:

```bash
# interactive login (safer)
gh auth login --with-token < ~/.secrets/github_token

# or use credential helper to cache creds
git config --global credential.helper store
```

4) Push (example using token file)

```bash
GITHUB_TOKEN=$(cat ~/.secrets/github_token)
git push https://<github-username>:${GITHUB_TOKEN}@github.com/<github-username>/<repo>.git
```

Notes: avoid putting the token in shell history or logs. Using `gh` or deploy keys removes that risk.

5) Verifying backup and provenance

- Verify the remote branch and commit are present:

```bash
git remote -v
git ls-remote origin HEAD
```

- Tag releases or snapshots so restores can reference stable points:

```bash
git tag -a backup-$(date +%F) -m "Backup snapshot"
git push origin --tags
```

6) Backing up runtime data (essential)

Source code backup alone is not sufficient. Back up runtime data and DB regularly.

- PostgreSQL data (example using `pg_dump` inside container):

```bash
docker exec -t admin-panel-postgres pg_dump -U adminuser adminpanel > /opt/admin-panel/data/backups/adminpanel-$(date +%F).sql
```

- Back up volumes and persistent folders (example for `data/`):

```bash
tar -czf /opt/admin-panel/data/backups/data-backup-$(date +%F).tgz -C /opt/admin-panel/data .
```

- Consider automating DB + file backups with a cron job or scheduled CI pipeline and rotate backups (keep retention policy).

7) Encrypted repository artifacts (optional)

- If you must keep configuration in the repo, encrypt it with `git-crypt` or GPG. Document decryption and key distribution.

8) Mirroring and offline bundles

- For extra safety create a mirror or bundle:

```bash
git clone --mirror /opt/admin-panel /opt/admin-panel-mirror.git
cd /opt/admin-panel-mirror.git
git remote add backup https://github.com/<user>/<backup-repo>.git
git push --mirror backup

# or create bundle
git -C /opt/admin-panel bundle create /opt/admin-panel/data/backups/indigo.bundle --all
```

9) Restore steps (high-level)

- To restore source from GitHub: `git clone https://github.com/<user>/<repo>.git` and checkout the desired tag/branch.
- To restore database: `psql -U adminuser -d adminpanel < adminpanel-YYYY-MM-DD.sql` (inside the postgres container or via networked psql).

10) Token and access governance

- Limit PAT scope to only the privileges needed (typically `repo` for private repos). Rotate tokens periodically and revoke lost tokens immediately.
- Prefer deploy keys for a single machine push, or use a machine user with 2FA-backed credentials.

11) Automation & CI

- Consider automating backups (source + DB dumps + archives) via a scheduled CI workflow or a server cron that runs backup scripts and pushes artifacts to an encrypted backup repo or object storage.

Checklist before any push:

- [ ] `.env` and other secrets are ignored or encrypted
- [ ] All code changes are committed and tests (if any) pass
- [ ] Backup branch or tag created for snapshot
- [ ] DB dump and data archive created and stored offsite

If you want, I can add a small backup script (`scripts/backup.sh`) and a sample cron entry to automate DB + repo snapshot and push.

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

### Module Independence and Rules

- **Each module must be fully independent.** A module's routes, business logic, templates, static assets, translations and `config.json` must live inside `core-app/modules/<module_name>/`.
- **No direct coupling:** Modules must not import or call each other directly. Any shared functionality should be provided by `core-app/utils/`, core models, or through the core API.
- **Registration & Enablement:** Modules must implement a safe registration function in `__init__.py` and handle missing dependencies gracefully. Enable modules via `ENABLED_MODULES` and do not assume other modules are present at runtime.
- **Translations:** Provide `translations.json` for all user-visible strings; the UI defaults to German with English as a fallback.
- **Documentation:** Each module must include a `README.md` and `config.json`. Developer-facing comments and docstrings may be in English.

### LDAP Group Permissions (development notes)

- The admin UI at `/admin/group-permissions` is the authoritative place to map LDAP groups to Roles and module permissions. Tests and development should account for this flow when implementing access control.


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

## Active LDAP Group (session)

When users log in, the application records an `active` LDAP group in the session (`session['active_ldap_group']`). Key points for developers and operators:

- If a user belongs to multiple LDAP groups, the system prefers the group that has a corresponding local `Role` with the most permissions and marks it active.
- Permission decorators and UI decisions may prefer the active group when evaluating access.
- A module-level permission named `<module>.access` grants access to all permissions under that module (i.e., `module.*`) when the user's active group maps to the Role that holds that permission.
- To ensure expected behavior, verify that LDAP groups are added as local `Role` records via the `Manage Group Permissions` UI and that the required `<module>.access` permissions are assigned.

This behavior was added to simplify group-based module access in multi-group scenarios.
