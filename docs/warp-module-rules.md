# Indigo Admin Panel – Module Development Rules for Warp

This document defines **non-negotiable rules** for implementing and modifying modules in the Indigo Admin Panel project.

Always read and follow these rules before making ANY changes.

Project root: `/opt/admin-panel`

---

## 1. High-Level Architecture

- The application is **module-based**.
- Each module implements one feature area (e.g. `admin`, `profile`, `dashboard`).
- Access to modules is controlled via **RBAC**:
  - LDAP groups → mapped to **Roles** (`roles` table).
  - Roles → have **Permissions** (`permissions` table) that are usually tied to Modules.
  - Each module must be connectable to roles via permissions so the admin can enable/disable it per group.
- Modules live under:  
  `core-app/modules/<module_name>/`

### 1.1 Core Models (DO NOT CHANGE without explicit request)

Location: `core-app/models/rbac.py`

- `Role` – groups permissions; some are system roles (`is_system=True`).
- `Module` – represents a feature module in the system (name, display_name, icon, enabled flag, url_prefix).
- `Permission` – specific permissions, optionally linked to a module.

Unless explicitly instructed, **do not modify** core RBAC model structure or remove fields.

---

## 2. Creating a New Module

### 2.1 Directory Structure

For a module named `example`, create:

```text
core-app/modules/example/
├── __init__.py
├── routes.py
├── forms.py                # optional
├── services.py             # optional
├── config.json
└── templates/
    └── example/
        ├── index.html
        └── ...
```

Rules:
- All module-specific templates belong under `core-app/modules/<name>/templates/<name>/`.
- Shared templates go under `core-app/templates/` only if explicitly requested.
- Business logic that is reusable can go into `core-app/utils/` or service files.

### 2.2 Module Config (REQUIRED)

Every module **must** have a `config.json` file, e.g.:

```json
{
  "name": "profile",
  "display_name_de": "Profil",
  "icon": "fa-user",
  "route_prefix": "/profile",
  "order": 5,
  "enabled": true
}
```

Requirements:
- `name`: machine name, unique (used in permissions, URLs, etc.).
- `display_name_de`: German display name used in menus.
- `icon`: Font Awesome class (without the `fas` prefix).
- `route_prefix`: URL prefix used by the blueprint.
- `order`: integer defining sidebar order.
- `enabled`: whether the module is considered active by default.

Never hard-code module names elsewhere; rely on `Module` records and config.json.

### 2.3 Blueprint Definition

In `core-app/modules/<name>/__init__.py`:

```python
from flask import Blueprint

bp = Blueprint('<name>', __name__, template_folder='templates', url_prefix='/<name>')

from . import routes  # noqa
```

Rules:
- The blueprint **must** be named consistently with the module name.
- `template_folder='templates'` is required so module templates resolve correctly.

The app factory / registration logic is already in place; do not add new global Flask app instances.

---

## 3. RBAC & Permissions Integration

### 3.1 Module Registration in Database

We rely on the **Module** model and a registry utility.

Location: `core-app/utils/module_registry.py`.

Rules when adding a module:
1. Ensure `config.json` exists.
2. Ensure the module is discoverable by `ModuleRegistry` (it scans `core-app/modules/**/config.json`).
3. After adding/modifying modules, run (document in report, but do not hard-code):
   - `flask init-rbac` (or the project-specific sync command, if present).

NEVER assume a module is usable if it does not have a corresponding `Module` row.

### 3.2 Permissions Naming Convention

- For basic module access, use the pattern:
  - `<module_name>.access` (e.g. `profile.access`, `admin.access`).
- More fine-grained permissions (if needed) follow:
  - `<module_name>.<action>` (e.g. `users.read`, `users.write`).

When you implement a new module, you MUST:
1. Decide which permissions it needs.
2. Ensure those permissions are created in the database when syncing RBAC.
3. Ensure the group-permissions UI can see and toggle them for roles.

### 3.3 Group Permissions UI Dependency

Location: `core-app/modules/admin/templates/admin/group_permissions.html`  
JS: `core-app/static/js/admin_groups.js`

Rules:
- New modules must appear in the modules list used by this UI.
- The modules are loaded from the `Module` table; if a new module is missing here,
  administrators cannot enable it for any LDAP group.
- When adding a module, verify that after `init-rbac` it appears in `/admin/group-permissions`.

---

## 4. LDAP & Roles

### 4.1 Role Creation from LDAP Groups

Location: `core-app/models/rbac.py` and `core-app/modules/admin/routes.py`.

- Roles are created from LDAP group CNs using `Role.create_from_ldap_group()`.
- Admins manage group→module access from `/admin/group-permissions`.

Rules for modules:
- Do **not** hard-code per-user logic inside modules.
- Always check permissions/roles using decorators or helpers:
  - e.g. `@require_role('admin')` or `@require_permission('module.action')`.
- A module must function purely based on current user roles/permissions; it must not
  perform additional LDAP queries on every view unless explicitly required.

---

## 5. UI & Layout Rules (VERY IMPORTANT)

These rules exist to prevent visual breakage of the entire site.

### 5.1 Global Layout Files – DO NOT TOUCH

Unless explicitly requested, **do NOT modify**:

- `core-app/templates/base.html`
- `core-app/templates/auth/login.html`
- `core-app/static/css/variables.css`
- `core-app/static/css/base.css`

You may **only**:
- Use the existing blocks (`title`, `content`, `extra_css`, `extra_js`).
- Add module-specific CSS/JS through these blocks from module templates.

### 5.2 Module-Specific Assets

For any non-trivial module UI:

```text
core-app/static/css/modules/<module_name>.css
core-app/static/js/modules/<module_name>.js
```

In the module’s main template (e.g. `templates/example/index.html`):

```jinja2
{% extends "base.html" %}

{% block extra_css %}
  {{ super() }}
  <link rel="stylesheet" href="{{ url_for('static', filename='css/modules/example.css') }}">
{% endblock %}

{% block extra_js %}
  {{ super() }}
  <script src="{{ url_for('static', filename='js/modules/example.js') }}"></script>
{% endblock %}
```

Rules:
- NEVER add new CSS/JS CDNs directly to `base.html`.
- Keep JS for each module isolated and namespaced where possible.
- Do not change header/sidebar structure from within modules.

---

## 6. Module Independence

- Each module should be as **independent** as possible:
  - Its routes, templates, static files and business logic should only depend on
    shared utilities (e.g. `utils/*`) and core services (auth, RBAC, LDAP).
- Do not:
  - Reach into another module’s templates or JS directly.
  - Modify another module’s routes unless the task explicitly states so.

Recommended pattern:
- Use service/helper functions in `core-app/utils/` if multiple modules need a feature.
- Keep module APIs clean and documented in comments.

---

## 7. Testing & Reporting Expectations (for Warp tasks)

When a module is created or modified, every task/prompt should:

1. **Describe Files Touched**
   - List all created files with full paths and a one-line description.
   - List all modified files with a summary of changes and important line ranges.

2. **Confirm RBAC Integration**
   - Show how the module is registered in `Module` (via config/registry).
   - Show what permissions were created/used (names like `module.access`).
   - Confirm the module appears and is manageable in `/admin/group-permissions`.

3. **Confirm UI Safety**
   - Explicitly state that global layout/CSS files listed in §5.1 were *not* changed.
   - If they were changed by explicit request, detail exactly what and why.

4. **Manual Test Steps**
   - Provide step-by-step instructions to test:
     - module visibility in sidebar,
     - access control (enabled/disabled for certain groups),
     - basic functionality (happy path and main error paths).

5. **Git State**
   - Ensure `git status` is clean after the work.
   - Mention commit hash and message.

---

## 8. Things Warp MUST NOT Do (Unless Explicitly Asked)

- Do NOT:
  - Change DB schema (migrations) unless the prompt specifically asks for it.
  - Rename existing modules or permissions.
  - Remove or alter core auth / LDAP / RBAC behavior.
  - Introduce new global dependencies via CDN in `base.html`.
  - Break the separation between logic and presentation (no heavy logic in templates).

If a task seems to require any of the above, Warp must:
1. Propose the change in the report / explanation.
2. Wait for an explicit follow-up prompt confirming that change.

---

## 9. Quick Checklist for Any New/Updated Module

Before finishing any module-related task, confirm:

- [ ] `core-app/modules/<name>/` structure is correct.
- [ ] `config.json` exists and is valid.
- [ ] `Module` entry is (or will be) synced from `config.json` (via registry/init command).
- [ ] Required permissions (`<name>.access`, etc.) exist or are created.
- [ ] Module appears in `/admin/group-permissions` and can be toggled per role.
- [ ] No forbidden global files were modified.
- [ ] Module-specific CSS/JS is isolated and included via `extra_css` / `extra_js`.
- [ ] Manual test steps are documented.


---

## 10. Localization & Language Rules

- **Site language**: All visible UI text (labels, buttons, messages, headings, navigation) must be in **German**.
- **Translations**:
  - Reuse existing keys in `core-app/translations/de.json` where possible.
  - For new UI text, always add keys under the appropriate namespace (e.g. `profile.*`, `admin.*`, `modules.<name>.*`).
  - Never hard-code German strings directly in Python/JS/HTML except in the translation files.
- **Code comments & documentation**:
  - Comments, docstrings, and internal documentation should be written in **English** to stay consistent for developers.
- **Prompts & communication**:
  - All interaction with the project owner (Salman) is in **Persian**, but code and config must respect the German/English rule above.

## 11. UI Style & Visual Consistency

Goal: All module pages should share a consistent look & feel similar to the existing
`/admin/group-permissions` page.

### 11.1 Layout

- Every module template must extend the global base layout:
  - `{% extends "base.html" %}`
- Use the same main container structure:
  - `<div class="container-fluid">` as the outer wrapper inside `{% block content %}`.
  - Grid system via Bootstrap rows/cols (`<div class="row">`, `<div class="col-md-*">`).
- Use cards for major content blocks (`<div class="card">`, `.card-header`, `.card-body`, `.card-footer`).

### 11.2 Colors & Components

- Use the existing design tokens from `variables.css` and base Bootstrap classes.
- Primary actions: `.btn-primary` or `.btn-success` (as seen on group-permissions).
- Destructive actions: `.btn-danger`.
- Neutral/secondary actions: `.btn-secondary`, `.btn-outline-*`.
- Use Bootstrap alerts for status messages (`.alert`, `.alert-success`, `.alert-danger`, etc.).
- Icons must use Font Awesome and follow the same pattern as existing pages:
  - `<i class="fas {{ module.icon }}"></i>` or similar.

### 11.3 Typography & Spacing

- Headings:
  - Use `<h1>` for page title with an icon on the left (e.g. `fa-users-cog` for group-permissions).
  - Use `<h2>`, `<h3>` inside cards if needed, but keep hierarchy shallow and clean.
- Spacing:
  - Use Bootstrap spacing utilities (`mb-3`, `mb-4`, `pt-3`, etc.) instead of custom inline styles where possible.

### 11.4 Behaviour & Feedback

- When a user performs an action (save, delete, etc.):
  - Provide immediate, visible feedback on the page (alert, toast, or inline message) in **German**.
- For AJAX-based actions:
  - Disable buttons while the request is in progress and show a spinner/icon if appropriate.
  - Re-enable and update the UI based on the result.

### 11.5 Reuse of Existing Patterns

- The page `/admin/group-permissions` is the **reference style** for admin-style pages.
- New admin modules should:
  - Reuse the same card layout, button style, heading pattern and icon usage.
  - Avoid inventing completely new visual patterns unless explicitly asked.

When in doubt about UI design, follow:
1. Existing `/admin/group-permissions` layout.
2. Bootstrap default components.
3. Design tokens defined in `variables.css`.

