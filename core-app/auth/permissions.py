from functools import wraps
from flask import abort, redirect, url_for, flash, session
from flask_login import current_user
# We don't import models here to avoid Circular Import if models import auth
# But we rely on current_user methods which are on the User model.

def require_role(role_name):
    """
    Decorator to restrict access to users with a specific role.
    
    Args:
        role_name (str): The name of the role required (e.g. 'admin')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))
            
            # If an active LDAP group is set in the session, treat that as the
            # effective role for permission decisions. This lets users who are
            # members of multiple LDAP groups select the one that grants the
            # special access (managed from Manage Group Permissions).
            active_group = session.get('active_ldap_group')

            # Admin role still bypasses checks
            if current_user.has_role('admin'):
                return f(*args, **kwargs)

            if active_group:
                # If the active LDAP group has a local Role record that grants
                # module-level access for the requested role_name (e.g. a
                # permission 'admin.access' or 'admin.*'), allow access.
                try:
                    from models.rbac import Role as RbacRole
                    r = RbacRole.query.filter_by(name=active_group).first()
                    if r:
                        # Allow if the active role name exactly matches requested
                        # role_name and user actually has that role locally.
                        if active_group == role_name and current_user.has_role(active_group):
                            return f(*args, **kwargs)

                        # Or allow if the role grants any permission for the
                        # requested role_name, e.g. 'admin.access' or
                        # 'admin.roles.read'.
                        for perm in getattr(r, 'permissions', []):
                            if perm.name == f"{role_name}.access" or perm.name.startswith(f"{role_name}."):
                                return f(*args, **kwargs)
                except Exception:
                    # On error, fall back to strict role name check below
                    pass
            else:
                # fallback: original behaviour - user must have the named role
                if not current_user.has_role(role_name):
                    flash('You do not have permission to access this resource.', 'danger')
                    return redirect(url_for('main.index'))
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def require_permission(permission_name):
    """
    Decorator to restrict access to users with a specific permission.
    
    Args:
        permission_name (str): The name of the permission required (e.g. 'backup.read')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))
            
            # Admin role bypasses permission checks
            if current_user.has_role('admin'):
                return f(*args, **kwargs)

            # If an active LDAP group is set, only consider permissions granted
            # via that group's local Role record. This enforces the UI model
            # where admins toggle module access per LDAP group.
            active_group = session.get('active_ldap_group')
            if active_group:
                # Check if the user has that role locally
                module = permission_name.split('.', 1)[0] if '.' in permission_name else permission_name
                for role in getattr(current_user, 'roles', []):
                    if role.name == active_group:
                        for perm in getattr(role, 'permissions', []):
                            # Exact permission match
                            if perm.name == permission_name:
                                return f(*args, **kwargs)
                            # Module-level access (e.g., 'admin.access') grants all 'admin.*' permissions
                            if perm.name == f"{module}.access":
                                return f(*args, **kwargs)
                        # role found but permission not present
                        break

                flash(f'Permission denied: {permission_name} required.', 'danger')
                return redirect(url_for('main.index'))

            # No active group: fallback to checking all user roles/permissions
            if not current_user.has_permission(permission_name):
                flash(f'Permission denied: {permission_name} required.', 'danger')
                return redirect(url_for('main.index'))
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator
