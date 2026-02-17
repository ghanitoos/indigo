# Indigo Admin Panel - Architecture Documentation

## Project Overview

A modular web-based administration panel for school network management, built with Docker, Flask, and PostgreSQL. The system integrates with Samba AD DC, pfSense, file servers, BorgBackup, and FOG Project.

## Technology Stack

- **Backend**: Python 3.12, Flask
- **Database**: PostgreSQL 16
- **Frontend**: Jinja2 templates, vanilla JavaScript, CSS
- **Authentication**: LDAP via ldap3 library
- **Deployment**: Docker, Docker Compose
- **Reverse Proxy**: Nginx

## System Architecture

### Container Architecture

```
┌─────────────────────────────────────────────┐
│          Client Browser                      │
└──────────────────┬──────────────────────────┘
                   │ HTTP :8080
┌──────────────────▼──────────────────────────┐
│       nginx-proxy Container                  │
│       (Reverse Proxy)                        │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│       core-app Container                     │
│       Flask Application (Python 3.12)        │
│       ├── Authentication (LDAP)             │
│       ├── Modules (users, pfsense, etc.)    │
│       └── API                                │
└──────────┬──────────────────────────────────┘
           │
┌──────────▼──────────────────────────────────┐
│       postgres Container                     │
│       PostgreSQL 16                          │
└──────────────────────────────────────────────┘
```

### Application Structure

```
core-app/
├── app.py                  # Application entry point
├── config.py               # Configuration management
├── models/                 # Database models
├── auth/                   # Authentication & authorization
├── modules/                # Feature modules (pluggable)
├── api/                    # REST API
├── templates/              # Jinja2 HTML templates
├── static/                 # CSS, JS, images
├── translations/           # i18n strings
└── utils/                  # Helper functions
```

## Module System

### Module Architecture

Each module is self-contained and follows this structure:

```
modules/module_name/
├── __init__.py            # Module registration
├── routes.py              # Flask routes/views
├── services.py            # Business logic
├── forms.py               # Form definitions (optional)
├── config.json            # Module configuration
├── translations.json      # Module-specific strings
└── README.md              # Module documentation
```

### Module Registration

Modules are automatically discovered and registered based on:
1. Presence in `core-app/modules/` directory
2. Listed in `ENABLED_MODULES` environment variable
3. Valid `__init__.py` with registration function

### Module Communication

- Modules do NOT communicate directly with each other
- All inter-module communication goes through the core app
- Shared data accessed via database models
- Events can be published/subscribed via the core event system

### Module Independence (clarification)

- Each module must be fully self-contained: routes, services, templates, static assets, translations and module-specific config must live inside the module directory.
- Modules expose features only via the core application (registration + DB/models/API). Direct imports or tight coupling between modules is prohibited.
- Enablement is controlled centrally (for example via the `ENABLED_MODULES` environment variable); modules must safely register/unregister without relying on other modules being present.

### LDAP Group Permissions UI

- The application provides an administrative view to map LDAP groups to module permissions and roles. In this deployment the page is available at `/admin/group-permissions` (e.g. `http://<server>:8080/admin/group-permissions`) and allows network admins to assign which modules and actions are enabled for each LDAP group.

### Localization & Code Comments

- The user-facing UI defaults to German with English as fallback. All user-visible strings should exist in the translation files.
- Source-code comments and developer-facing documentation may be written in English. This keeps in-code explanations consistent while the UI remains German.

## Configuration System

### Configuration Hierarchy

1. **Environment Variables** (`.env` file)
   - Highest priority
   - Used for secrets and deployment-specific settings

2. **config.py** 
   - Python configuration classes
   - Environment-specific configs (dev, prod, test)

3. **Module configs** (`modules/*/config.json`)
   - Module-specific settings
   - Can be overridden by environment variables

### Configuration Classes

- `Config`: Base configuration with common settings
- `DevelopmentConfig`: Development environment
- `ProductionConfig`: Production environment with security hardening
- `TestingConfig`: Testing environment with in-memory database

## Authentication & Authorization

### LDAP Integration

- **Primary authentication** via Samba AD DC
- Users authenticate with their domain credentials
- LDAP groups mapped to application roles

### Active LDAP Group (session-level)

The application now records an "active" LDAP group in the user's session on login. When a user is a member of multiple LDAP groups, the active group is selected (preferentially the group that has the richest local Role permissions) and stored as `session['active_ldap_group']`.

Permission checks and UI decisions may prefer the active group when evaluating access. Module-level access can be granted to a Role via permissions such as `<module>.access` which implies access to `module.*` permissions for users whose active group maps to that Role.

### Session Management

- Server-side sessions stored in database
- 30-minute default timeout
- Secure, HTTP-only cookies
- CSRF protection on all forms

### Role-Based Access Control (RBAC)

```
User ──> Roles ──> Permissions ──> Resources
```

- Users can have multiple roles
- Roles contain multiple permissions
- Permissions grant access to specific resources/actions
- Permissions checked at route level via decorators

## Database Schema

### Core Tables

- **users**: Cached LDAP user information
- **roles**: Role definitions
- **permissions**: Permission definitions
- **role_permissions**: Many-to-many mapping
- **user_roles**: Many-to-many mapping
- **sessions**: User sessions
- **audit_logs**: All administrative actions
- **module_configs**: Runtime module configuration

### Migration Strategy

- Flask-Migrate for schema changes
- All migrations in version control
- Forward and rollback migrations tested
- Database backups before migrations

## Security Architecture

### Security Layers

1. **Network Security**
   - Nginx reverse proxy
   - Rate limiting
   - SSL/TLS termination (production)

2. **Application Security**
   - CSRF tokens on all forms
   - Input validation and sanitization
   - SQL injection protection (SQLAlchemy ORM)
   - XSS protection (Jinja2 auto-escaping)

3. **Authentication Security**
   - Secure password storage (never stored locally)
   - LDAP over secure connection
   - Session fixation protection
   - Brute force protection

4. **Authorization Security**
   - Role-based access control
   - Principle of least privilege
   - Audit logging of all actions

### Secrets Management

- No secrets in code or config files
- All secrets in environment variables
- `.env` file never committed to git
- Production secrets in secure vault

## Translation System

### Structure

- Base translations in `core-app/translations/`
- Module translations in `core-app/modules/*/translations.json`
- German as primary language
- English as fallback

### Translation Files

```json
{
  "common": {
    "key": "Translated text"
  },
  "modules": {
    "module_name": {
      "key": "Translated text"
    }
  }
}
```

### Usage in Code

```python
from utils.i18n import translate

translated_text = translate('common.login')
```

## Development Workflow

### Phase-Based Development

Development is organized into phases:

**Phase 1: Foundation**
- Project structure
- Configuration system
- Translation system
- Database models

**Phase 2: Authentication**
- LDAP integration
- Session management
- Login/Logout UI
- RBAC implementation

**Phase 3: Dashboard**
- Main dashboard
- User widgets
- System status

**Phase 4+: Feature Modules**
- User management
- pfSense integration
- File server management
- Backup monitoring
- FOG integration

### Testing Strategy

1. **Unit Tests**: Test individual functions/classes
2. **Integration Tests**: Test module interactions
3. **Manual Tests**: UI/UX testing checklist

## Coding Standards

### Naming Conventions

- Files: `snake_case.py`
- Classes: `PascalCase`
- Functions/variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`

### Code Quality Requirements

- Type hints on all functions
- Docstrings on all public functions/classes
- Maximum file length: 300 lines
- One responsibility per file
- Comments in English
- UI text in German (via translations)

### Git Commit Convention

```
type(scope): subject

Types: feat, fix, docs, style, refactor, test, chore
Scope: module name or component
```

Example: `feat(auth): add LDAP authentication support`

## Visual Customization

### Design Token System

All visual styling controlled via CSS custom properties:

```css
:root {
  --primary-color: #667eea;
  --secondary-color: #764ba2;
  --success-color: #10b981;
  --danger-color: #ef4444;
  --warning-color: #f59e0b;
  --font-family: 'Arial', sans-serif;
  --spacing-unit: 8px;
}
```

### Theme Changes

- Edit `static/css/variables.css` to change colors/fonts
- No need to modify HTML or Python code
- Changes apply immediately (no rebuild required)

## Deployment

### Docker Compose

Three containers orchestrated via docker-compose:

1. **postgres**: Database
2. **core-app**: Flask application
3. **nginx-proxy**: Reverse proxy

### Environment Variables

Required variables in `.env`:

- `SECRET_KEY`: Flask secret key
- `DATABASE_URL`: PostgreSQL connection string
- `LDAP_SERVER`: LDAP server URL
- `LDAP_BIND_DN`: LDAP bind DN
- `LDAP_BIND_PASSWORD`: LDAP password
- `LDAP_BASE_DN`: LDAP base DN

### Backup Strategy

- Daily automated database backups
- Configuration files in version control
- Logs rotated and archived

## Future Enhancements

- REST API for external integrations
- Real-time notifications via WebSockets
- Visual theme editor
- Multi-factor authentication
- Mobile-responsive UI improvements
- Advanced reporting and analytics

## Support and Maintenance

### Logging

- Application logs: `/app/logs/app.log`
- Nginx logs: `/var/log/nginx/`
- Database logs: PostgreSQL container logs

### Monitoring

- Health check endpoints
- Container health checks
- Database connection monitoring

### Troubleshooting

Common issues and solutions documented in `DEVELOPMENT.md`.
